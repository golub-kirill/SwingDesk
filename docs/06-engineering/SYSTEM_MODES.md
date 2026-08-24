# SYSTEM MODES

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored, measured against the tree

Master ТЗ v1.0 §35, ranked third of the nine absent sections in `SPEC_GAP_ANALYSIS.md` §4 — cheap,
and referenced by almost everything else, because a rule, a gate or a status claim is only meaningful
once you can say **in which mode it holds**.

---

## 1. The usual discriminator does not work here

Mode ladders in trading systems are ordered by one question: *does this run send orders?* Owner
decision D1 makes that question constant-false. This system never places orders in any mode, so a
ladder built on it would have six rungs and one value.

So modes here are discriminated by four properties that **do** vary, and every one of them is already
a real distinction in the code:

| Axis | Values | Where it lives today |
|---|---|---|
| **Time** | system clock · pinned instant | `swingdesk.platform.clock` — `SystemClock` / `FixedClock` |
| **Facts** | vendor · stored snapshot · recorded fixture | `swingdesk.market_data.store` vs the injected `Fetcher` |
| **Writes** | real journal · throwaway workspace · study artefact | `Journal(...)` path, or a `TemporaryDirectory` |
| **Authority** | authorises nothing · supports a study verdict · supports an owner decision | prose only |

The fourth axis is the one that matters and the only one with no representation in code. It is what
`REQ-EVIDENCE-001` is about: a validation stage must reference a run that actually executed, and
*which mode it executed in* decides what that run can be evidence of.

## 2. The six modes

Definitions first, audit second. Each mode is a **declared** property of a run, not a shape a run
happens to have.

| Mode | Purpose | Time | Facts | Writes | Authorises |
|---|---|---|---|---|---|
| `RESEARCH` | answer a pre-registered question | pinned by the study | stored snapshot, as-of | study artefact | a study verdict, once reported |
| `BACKTEST` | walk bars for one strategy version | pinned by the study | stored snapshot, as-of | study artefact | nothing on its own; it is `RESEARCH`'s engine |
| `REPLAY` | prove a stored run reproduces | the manifest's instant | the run's recorded fixture | throwaway | nothing — it proves reproduction, not correctness |
| `PAPER` | run the real schedule with no capital at risk | system clock | vendor, then stored | real journal | a forward-test record |
| `SHADOW` | run a candidate version beside the incumbent | whatever the incumbent uses | same inputs as the incumbent | divergence record only | nothing; it reports difference |
| `LIVE` | prepare today's decisions for the owner | system clock | vendor, then stored | real journal | **an owner decision, and nothing else** |

Two clauses are load-bearing and easy to lose:

- **`LIVE` authorises an owner decision, not an action by the system.** The run proposes; the human
  disposes (`CHARTER.md` §2, D6). Every `ManagementAction` this system produces is a proposal, and
  `RunResult.actionable` is named for what the *owner* may act on.
- **`SHADOW` must not be able to change anything.** A candidate rule running in shadow that can move
  a verdict is not in shadow; it is deployed with extra logging.

## 3. What this tree actually runs

Measured, not planned.

| Mode | Exists | Entry point | Notes |
|---|---|---|---|
| `RESEARCH` | **yes** | `tools/run_pr001.py`, `tools/run_pr002.py`, `tools/run_pr005.py`, `tools/run_pr008.py` | the reported studies reported; each pins its own parameters and reads no registry |
| `BACKTEST` | **yes** | `validation/backtest/engine.py` | invoked only from a study — there is no `swingdesk backtest` command, and that is correct |
| `REPLAY` | **yes** | `tools/replay.py`, `validation/replay.py` | the only mode with a merge gate (gate 9) |
| `PAPER` | **no** | — | needs the scheduled run plus recording of misses and delays; see §5 |
| `SHADOW` | **no** | — | no second version has ever run beside a first |
| `LIVE` | **yes** | `swingdesk scan` | declared since 2026-08-08; see immediately below |

**The mode used to be inferred from the argument list.** `swingdesk scan AAPL` with no `--as-of`
takes a `SystemClock`, fetches from the vendor and writes the real journal — that is `LIVE`, and
nothing said so. `RunManifest` had no `mode` field, so a journal entry could not answer "was this a
real run?" except by inference from `snapshot_id` and whether a fixture was injected — and inference
is exactly what a manifest exists to remove.

**Fixed 2026-08-08.** `RunMode` is an enum on `contracts/run.py`, `mode` is a **required field with
no default** on `RunManifest`, and `pipeline.run` takes it as a **required keyword-only argument** so
a caller can neither omit it nor pass it by accident in the wrong position. Deriving it from the
injected clock and fetcher was rejected for the obvious reason: it would be automatic, and it would
re-create the inference this section objects to.

| Caller | Mode |
|---|---|
| `swingdesk scan` | `LIVE` |
| `swingdesk scan --as-of` | `LIVE_AS_OF` — see §7 |
| `validation/replay.py` | `REPLAY` |

**Mode is recorded and deliberately not hashed.** A replay of a `LIVE` run executes in `REPLAY` mode
and must still reproduce that run's `output_hash`; pinning the mode would make every replay a
mismatch by construction. It describes the run, not the decision.

The journal column is nullable while the manifest field is required, and that asymmetry is the
honest one: rows written before the column existed cannot acquire a mode, and a `NULL` meaning "this
run predates the field" beats a backfilled guess (`AUDIT_AND_IMMUTABILITY.md` — records are
versioned, never updated). Every row written from now on carries it.

## 4. Modes and the validation ladder are the same ladder

`VALIDATION_PROGRAM.md` §1 defines what earns each validation status. Read next to §2 above, the two
ontologies turn out to be one:

| Status | Earned in mode | Why no other mode can earn it |
|---|---|---|
| `Historically Tested` | `RESEARCH` / `BACKTEST` | needs the nine stages of `BACKTEST_PROTOCOL.md` |
| `Out-of-Sample Tested` | `RESEARCH` | needs data the parameters never saw |
| `Walk-Forward Tested` | `RESEARCH` | needs multiple windows with their own verdicts |
| `Forward Test Running` | **`PAPER`** | the status *is* the mode: real schedule, no capital at risk |
| `Forward Tested` | `PAPER` | the pre-registered criteria met, on the real schedule |
| — | `REPLAY` | reproduction is not correctness (`DETERMINISM_SPEC.md` §7) |
| — | `LIVE` | live results are outcomes; a status is earned by a protocol, not by a P&L |
| — | `SHADOW` | divergence is evidence about a *change*, not about a rule's edge |

The mapping is worth stating because the failure it prevents is silent: a number computed in
`RESEARCH` and quoted as though it came from `PAPER` is precisely the claim `VALIDATION_PROGRAM.md`
§2 says a backtest structurally cannot make — misses, delays, alerts and journal quality are only
observable on the real schedule.

`REQ-EVIDENCE-001` therefore needs the mode, not just the run: "this stage references a run that
executed" is only a check once the run says which mode it executed in.

## 5. `PAPER` is the missing rung, and it is not missing much

`swingdesk scan` already does most of what a forward test needs — it fetches, decides, codes every
refusal and journals the result. Four things are absent, and only the first is machinery:

1. **A schedule.** Nothing runs the run. `HANDOFF.md` §5 item 4 makes the same point about
   `tools/fetch_directory.py` for a different reason: an unscheduled daily job accumulates no history
   and the missing days cannot be recovered later.
2. **Misses and delays as recorded fields.** A forward test measures `пропуски` and `задержки`
   (`VALIDATION_PROGRAM.md` §2). A run that completes records what it did; a run that did not happen
   records nothing, so absence has to be detected against the calendar rather than found in the log.
3. **An alert path.** `PRODUCT_SURFACES.md` names the notification surfaces; none is built, and a
   forward test measures whether alerts fire.
4. **A strategy to test.** The live path reaches `"sized; awaiting a trigger"` and has no trigger —
   `REQUIREMENTS.md` §3. A forward test of a system with no entry rule measures the plumbing only,
   which is a legitimate thing to measure and must be labelled as such.

Item 4 is why `PAPER` is not simply "turn on the schedule". Track A — is the system sound — can be
measured in `PAPER` today. Track B cannot, because there is nothing to run forward.

## 6. Mode rules

1. **A mode is declared, never inferred.** On the manifest, required, no default — the same
   discipline as every parameter here (`PARAMETER_REGISTRY.md` §4). **Enforced since 2026-08-08**:
   `pipeline.run` takes `mode` as a required keyword-only argument, so a run whose mode nobody chose
   fails at the call site rather than starting under a guess.
2. **Exactly two modes write the real journal**: `LIVE` and `PAPER`. `RESEARCH` and `BACKTEST` write
   study artefacts; `REPLAY` writes to a temporary workspace and deletes it; `SHADOW` writes only
   divergence.
3. **Only `LIVE` and `PAPER` may read the wall clock.** Everything else takes a pinned instant. Gate 7
   already enforces the stronger version of this inside `derived_observations`, `decision_logic` and
   `trade_management` — no wall-clock call at all, AST-parsed rather than grepped.
4. **No mode may fetch during CI.** `CI_POLICY.md` §4: vendor responses are recorded fixtures. This
   is why `REPLAY` is the only mode gated on merge — it is the only one whose inputs are wholly in
   the repository.
5. **Fail-closed applies per mode, and it is not the same rule in each.** The degradation table in
   `FAIL_CLOSED_POLICY.md` §2 governs the operating modes: in `LIVE` or `PAPER`, missing or stale
   data stops new decisions. In `RESEARCH` the same condition stops the *study* — a study that
   silently proceeds on partial data produces a number nobody can interpret — but it raises no
   operational `Pause`, because there is no live decision to suspend.
6. **A mode may never be widened at runtime.** `SHADOW` cannot become `LIVE` because a candidate
   looked good this morning. Changing mode is a new run with a new manifest.

## 6a. The declared mode is not a mode *switch*

Rule 1 above makes the mode an explicit argument, and that is deliberately **not** a `SYSTEM_MODE`
setting that reconfigures the system. There is no such setting and adding one would be a regression.

The two mechanisms operate at different scopes and both are needed:

- **Across the research / backtest / live boundary, separation is structural.** Research code lives
  in `tools/` and cannot be imported by `src/`; the backtest path lives in `validation/`; the live
  path lives in `application/`. The import contracts in `pyproject.toml` make a crossing a **build**
  failure rather than a runtime condition, and gate 6 checks it on every commit. A flag would move
  that boundary out of the layer graph and into a variable that can be wrong at 09:31 on a Tuesday.
- **Within the live path, the mode is a declared field**, because `LIVE`, `PAPER` and `SHADOW` share
  the same code and differ in what their output authorises. There is nothing structural to separate,
  so it is recorded on the manifest and required at the call site.

The one genuinely runtime value is the **snapshot**: a named `knowledge_time`
(`POINT_IN_TIME_SPEC.md` §5). `BACKTEST` pins it to the decision bar and `LIVE` pins it to now, and
`DETERMINISM_SPEC.md` is explicit that there is no third option, because a third option is how
look-ahead gets in.

## 7. What `--as-of` really is

Naming it now, before something depends on the ambiguity.

| | `REPLAY` | `swingdesk scan --as-of` |
|---|---|---|
| Clock | the manifest's instant | the instant you typed |
| Facts | the recorded fixture | a **fresh vendor fetch**, filtered as-of |
| Store | throwaway | the real store |
| Comparison | against a recorded `output_hash` | against nothing |

They share only the pinned clock. `--as-of` is `LIVE` with a stated decision time — useful for a
missed session or for reproducing yesterday's reasoning against today's data, and **not** a
determinism check. Calling it one would be the error `validation/replay.py` warns about in its own
docstring: a replay that fetched would test today's data against yesterday's conclusion and call the
difference a bug.

Proposed names, so the manifest can carry them: `LIVE` (system clock) and `LIVE_AS_OF` (pinned).
Same authority, different reproducibility, and the difference is visible.

## 8. Open items

- [x] ~~**`mode` on `RunManifest`**, required, no default~~ — **done 2026-08-08**, along with the
      journal column and the `LIVE` / `LIVE_AS_OF` / `REPLAY` call sites. The replay fixture was
      re-recorded and its `output_hash` is unchanged, which is the evidence that a manifest field was
      added and no decision moved.
- [x] ~~**Where the mode is set**~~ — a required keyword-only argument to `pipeline.run`. A CLI flag
      alone would have been forgettable, and inference was rejected on principle.
- [ ] **`SHADOW` has no consumer yet, and one is coming.** `REQ-VALIDATION-002` requires the backtest
      and live paths to agree on an identical bar; running both over one bar series and diffing the
      `Decision` is a shadow run by another name. That is the cheapest place to discharge the
      requirement, and it argues for defining `SHADOW` before the unified trigger rather than after.
- [ ] **Mode in the evidence record.** `EVIDENCE_RECORD_SPEC.md` pins component versions and
      survivorship coverage; the mode belongs in the same place for the same reason.
- [ ] Whether `PAPER` may run while the live path has no trigger. It can, and it measures Track A
      only. Decide the label before the first forward-test record exists, not after.
