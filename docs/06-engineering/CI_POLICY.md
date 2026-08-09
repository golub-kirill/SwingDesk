# CI POLICY

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored

An architecture rule that is not executed is decoration (`DEPENDENCY_LAW.md`). This lists every gate
that must pass to merge, and what each one exists to catch.

---

## 1. Gates

Ordered fastest-first, so a cheap failure does not wait behind an expensive suite.

| # | Gate | Catches | Status |
|---|---|---|---|
| 1 | `verify_parameters.py` | a value without provenance; `assumed` without a citation; a parameter with no course reference | **exists** |
| 2 | `verify_transcription.py` | a `verbatim` block that no longer matches its source; an enum drifting from its spec | **exists** |
| 3 | `build_course_index.py --check-only` | the course index no longer extracting to its known shape | **exists** |
| 3b | `build_frd.py --check-only` | the FRD drifting from the registry it is generated from | **exists** |
| 3c | `build_components.py --check-only` | a generated component field hand-edited; the registry going stale against the course | **exists** — 465 rows |
| 3ci | `build_coverage.py --check-only` | the coverage matrix drifting from the registries it is counted from | **exists** — ТЗ §5, generated rather than authored |
| 3d | `build_checklists.py --check-only` | the checklist registry drifting from the transcription it is parsed from | **exists** — 84 items |
| 3e | `verify_docs.py` | a document citing a spec, parameter or component id that does not exist; a status outside the ladder | **exists** — caught 4 dangling references on its first run, one of them cited by three documents |
| 3f | `verify_studies.py` | a report with no pre-registration; the prereg index disagreeing with the report it points at; a `validated:` parameter citing a study that did not ACCEPT; a `\| Studies \|` row whose numbers do not match the reports on disk | **exists** — caught `4 studies, 3 refuted` quoted in five documents against three reports with two REJECTs |
| 3g | `verify_criteria.py` | a criterion in force referencing a parameter with no value; a reference to a parameter or criterion that does not exist; a status outside the ladder | **exists** — the narrow half of `REQ-VALIDATION-001` |
| 4 | `ruff` | unused imports, naive datetimes, blind excepts, import order | **exists** — 10 rule families, chosen deliberately |
| 5 | `mypy --strict` | type errors | **exists** — clean over `src`; `tools/` is out of scope, see §7 |
| 6 | `lint-imports` | a package importing across a layer or forbidden boundary | **exists** — 4 contracts. Caught a reversed layer order on first run |
| 7 | no-wall-clock check | `datetime.now` / `date.today` / `time.time` in `derived_observations`, `decision_logic`, `trade_management` | **exists** — AST-parsed, not string-matched, so a mention in a docstring does not trip it |
| 7b | `golden.py` | a component's output changing without its version and vectors changing with it | **exists** — 25 vectors, 6 components |
| 8 | `pytest` | unit, property and golden-vector tests | **exists** — 253 tests, fully offline |
| 9 | determinism replay | a stored manifest no longer reproducing its `output_hash` | **exists** — 1 case, 4 instruments covering all four decision branches |
| 10 | traceability | a course id with no requirement row, a requirement with no test, a spec id cited by no test | to build |
| 11 | `verify_components.py` | `implements` not injective; an `active` component missing `implements`/`verification`/`spec`; a dangling parameter reference; an `active` component with an `unset` parameter; an `implements` pointing at a symbol that does not exist; a non-Definition topic with no row | **exists** — caught two components sharing one function on its first run |

Everything except 10 runs today via `tools/check_gates.py` — **18 gates**. Gates 2, 3 and 3f are
stdlib-only; the rest need the project venv (`pip install -e ".[dev]"`).

Gates 7b and 9 are also asserted from `pytest`, so a bare `pytest` run is not silently weaker than
CI. The duplication is deliberate — they are the two gates whose subject is *change over time*, and
they are the ones a developer is most likely to run without.

## 2. What each gate protects

Not busywork — each maps to a specific way this project could quietly go wrong:

| Gate | The failure it prevents |
|---|---|
| 1 | a guessed threshold acquiring the authority of a measurement |
| 2 | documents drifting from the course while still claiming to transcribe it — **already caught two real errors** and two undeclared sources |
| 3 | an extraction change silently altering the component catalogue |
| 6 | a strategy fetching its own facts; an indicator owning a decision; the journal being written from a pure layer — **caught a reversed layer order on its first run, and forced `application` out of `presentation` on its second** |
| 7 | reproducibility breaking invisibly — one hurried commit is enough |
| 7b | a behaviour change slipping in unversioned; and, via the file hashes, the cheaper failure of pasting whatever the code now prints into the expected values |
| 9 | non-determinism entering the decision path — **caught `config_hash` covering only which parameters were set, so a changed threshold would have been reported as a determinism defect** |
| 4 | a wall-clock call or an unused binding surviving review. Both are invisible in a diff and neither is caught by a test that happens to pass |
| 5 | a declared type and the real contract drifting apart. **Caught the `Fetcher` alias describing positional arguments while every call site passed `period` by keyword** |
| 3e | a document asserting something about the system that stopped being true. Every defect of this kind found by hand so far read as correct — a stale claim does not look like a bug |
| 3f | the summary of the evidence drifting from the evidence. Gate 3e cannot see it, because every reference in the wrong sentence resolves; only recomputing from the reports does |
| 3g | a safeguard that cannot fire. A ratified criterion whose threshold is unset reads as protection and provides none, and nobody looks for a second one |
| 3ci | a coverage claim drifting from what is actually covered. The ТЗ forbids claiming coverage without a formal basis, and a hand-maintained matrix of counts is the most rot-prone document a project can own |
| 10 | a course requirement being dropped without anyone noticing |
| 11 | two implementations of one component — the thing §3.8 forbids and import analysis cannot see, because both imports are perfectly legal. **Caught `M12-T0201` and `M12-T0202` both claiming `pivots:compute`**, which a linter would never question |

## 3. Merge rules

- **All gates pass, or no merge.** No "fix it in the next commit".
- A gate that is wrong gets **fixed or removed**, never skipped. A routinely-bypassed gate is worse
  than no gate: it teaches the operator that red is normal.
- **Golden vectors changing is a blocking failure** unless the commit also contains the decision
  record explaining the behaviour change and a component version bump
  (`COMPONENT_REGISTRY_SPEC.md` §6).
- Adding a `verbatim` document requires its `verbatim-sources` declaration in the same commit,
  otherwise gate 2 silently skips it. **Gate 2 only checks documents that opt in** — that is its one
  weakness and it is worth stating.

## 4. What CI must never do

- **Touch the network.** Vendor responses are recorded fixtures; a suite that fetches is neither
  deterministic nor available offline, and it would hammer a rate-limited free tier.
- **Write to the real data store.** Fixtures only.
- **Depend on the current date.** A suite that passes today and fails in January is a suite that
  will be disabled in January.

That third one deserves emphasis given this project's subject matter: half-days, holidays and
month-end are exactly the conditions where date-dependent tests break, and they are also exactly the
conditions the system must handle correctly.

## 5. Local equivalence

Every gate runs locally with one command, and the CI definition calls the same script it does. If
the two can disagree, the local run stops being trusted and the feedback loop lengthens to a push.

```bash
python tools/check_gates.py
```

There is deliberately no `--skip` flag.

## 6. What the gates have actually caught

Kept as a record, because the argument for a gate is empirical and this is the evidence:

| Gate | Caught |
|---|---|
| 2 | two real transcription errors, and four documents citing sources they had not declared |
| 6 | `reference_data` placed above `market_data`, which would have let calendars import bars |
| 6 | the pipeline sitting in `presentation`, unreachable by the replay harness that needs it |
| 9 | `config_hash` hashing set-ness instead of values |
| 9 | a replay fixture whose bars had constant true range, making it blind to the ATR period |
| 11 | swing high and swing low sharing one function, so `implements` could not say which component a symbol served |
| 4 | **`date.today()` in the pipeline's completeness window.** On the empty-bars branch the run measured completeness against the wall clock instead of its own pinned clock, so a replay of an old manifest would have used the date of the replay. Gate 7 could not see it — `application` is not one of the pure packages it guards |
| 5 | **`ExitDecision(exited=True)` constructible with no price and no reason**, which would have produced a Trade with a None exit price. The invariant now lives in `__post_init__` |
| 5 | the `Fetcher` type declaring four positional arguments while every caller passed `period` by keyword |
| 3e | **`INVARIANTS.md` cited by three documents and never written** — `TEST_STRATEGY.md` described it as "not prose to be read", `RISK_SPEC.md` and `SCREENER_SPEC.md` deferred to it. Writing it surfaced that invariant 4 is enforced by a function signature rather than a test, and that `DETERMINISM_SPEC.md` §7 claimed general shuffle-invariance coverage while testing one component |
| 3e | `RECONCILIATION_SPEC.md`, cited by `FAIL_CLOSED_POLICY.md`'s safety row and never written |
| 3g | **`k.drawdown_pause`, ratified since 2026-08-02 with `validation.max_allowable_drawdown` unset.** Found by hand on 2026-08-03 and closed by `DR-005` on 2026-08-08; the gate exists so the next one is not found by hand. Mutation-checked on all three of its checks, including the quiet one — a typo in a criterion's `status` would exempt it from the parameter check, so the ladder is verified before anything else |
| 3f | **`4 studies, 3 refuted` in five documents.** Three pre-registrations are reported and two of them REJECT; the fourth "study" is the post-hoc survivorship bound, which carries no verdict at all. The evidence was right and every summary of it was wrong, in the direction of overstating how much had been tested |

Two of these deserve a note. The constant-true-range fixture was the useful kind of failure — the
gate was green, the fixture was wrong, and only trying to make the gate fail on purpose revealed it.
The shared `pivots:compute` is the other kind: a gate finding a real defect the first time it ran,
before anyone had a chance to trust the thing it was checking.

## 7. Open items

- [ ] Choose the runner. **A remote exists** (`origin`, GitHub) as of 2026-08-08, so Actions is now
      available; a local pre-commit hook plus a script still suits a single-user offline-first
      project better. The choice is open, the constraint that decided it is gone.
- [ ] **Gate 10 (traceability) would pass vacuously today, which is why it is still not wired.**
      Its strongest available check is "every `active` component has a test", and there are
      **zero** `active` components — five are blocked on an unset parameter, which is the
      fail-closed design working. A green gate that asserts nothing trains the operator to
      trust it. It lands with the first `active` component.
- [ ] **`mypy --strict` covers `src` only.** `tools/` carried 53 further errors, mostly
      `type-arg` and `no-any-return` in study runners. Two sites are worth a look rather than a
      blanket annotation pass: `run_pr002.py:209` calls `min(key=...)` over a key that can
      return `None`, and `run_pr005.py:267` builds a `Decimal` from an `object`. Neither
      affected a reported result — checked, not assumed — because the runs completed.
- [ ] Runtime budget. Gates 1–3 take about a minute (dominated by re-extracting 116 PDFs). If that
      becomes friction, cache extraction by file hash rather than weakening the check.
