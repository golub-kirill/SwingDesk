# SYSTEM MODES

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored, measured against the tree

Master ТЗ §35 requires the modes a system runs in to be named, because almost every other section's
guarantees are conditional on one. `SPEC_GAP_ANALYSIS.md` §2 recorded this section as **ABSENT** and
ranked it third — cheap, and widely referenced.

This document names the six modes and says, for each, what it may read, what it may write, what
guarantees hold, and **what in this tree implements it today**. Three of the six do not exist here.
Saying so is the point: a mode taxonomy that describes six modes when three are unbuilt is a map of
somewhere else.

---

## 1. The one that changes the taxonomy

The ТЗ's mode ladder ends at LIVE, where a system trades. **This system never trades** — owner
decision D1, `CHARTER.md` §3, and the first of the non-negotiables in `AGENTS.md` §3.

So the ladder's top rung means something different here, and the difference is not cosmetic:

> In this project, LIVE means *the daily run prepares decisions and records them.* A human places
> every order. There is no mode in which the system acts on a market.

That collapses part of the ТЗ's distinction between SHADOW and LIVE — a shadow system is normally
one that computes without acting, which is what this system does in every mode it has. What
separates them here is **whether the output is presented to the operator as actionable**, not
whether an order follows.

## 2. The six modes

| Mode | Reads | Writes | Network | Deterministic | Exists here |
|---|---|---|---|---|---|
| **RESEARCH** | vendors, the stores | `data/`, measurements, study results | **yes** | no — above the boundary | **yes** — `tools/` |
| **BACKTEST** | a pinned snapshot | study results | no | yes | **yes** — `validation/backtest/` |
| **REPLAY** | a stored manifest | nothing | no | yes, by definition | **yes** — gate 9 |
| **PAPER** | live snapshot | a simulated journal | no | yes | **no** |
| **SHADOW** | live snapshot | journal, marked non-actionable | no | yes | **no** |
| **LIVE** | live snapshot | journal, presented to the operator | no | yes | **partially** — see §4 |

### RESEARCH

The only mode permitted to touch the network, and the only one above the determinism boundary.
`tools/fetch_directory.py`, `refresh_universe.py`, `sample_liquidity.py`, `measure_spread.py` and the
study runners all live here.

Its rules are already enforced rather than merely stated: nothing in `src/` imports a tool, CI never
runs one (`CI_POLICY.md` §4), and the import contracts in `pyproject.toml` keep the decision path
from reaching a vendor at all.

**RESEARCH output is an input to another mode, never a decision.** A measurement it produces becomes
a parameter only by way of a decision record or a pre-registered study — `DR-005` is the worked
example, and the parameter it set stayed `assumed` rather than `validated` precisely because a
measurement is not a study.

### BACKTEST

Reads a pinned snapshot and charges costs. Implemented by `validation/backtest/engine.py` and
governed by `BACKTEST_PROTOCOL.md`.

Two properties that hold here and are easy to lose:

- **It never fetches.** The snapshot is the determinism boundary (`DETERMINISM_SPEC.md` §4); a fetch
  inside the decision path would put a network response underneath a reproducible number.
- **Costs are charged, never mentioned.** `costs.commission_model` and `costs.slippage_model` are
  applied to the fill, and every result is reported net at both the base and the stressed vector
  (`validation.stress_cost_multiplier`).

**The known structural defect lives in this mode.** `engine.py` owns the entry trigger and
`application/pipeline.py` — the LIVE path — has none of its own. `REQUIREMENTS.md` §3
(`REQ-VALIDATION-002`) records why that is cheap to fix now and expensive later: the moment the live
path acquires a trigger, this repository holds two independently written implementations of one
strategy.

### REPLAY

Takes a stored run manifest and reproduces its `output_hash`, or fails. This is gate 9, run by
`tools/replay.py`, and it is also asserted from `pytest` so a bare test run is not silently weaker
than CI.

REPLAY writes nothing and decides nothing. It exists to answer one question — *has behaviour changed
since this manifest was frozen?* — and it cannot answer whether the behaviour was right to begin
with. `tools/replay.py` says so in its own docstring, and the distinction matters: recording a
manifest freezes current behaviour as the reference, including any defect it contains.

### PAPER — does not exist

Simulated fills against a live snapshot, journalled as if real. Nothing in the tree implements it.

It is the natural home for the forward test that `DR-004` and `PR-006` both depend on: measured live
slippage against modelled has no source until fills are being recorded. **`PR-006` cannot run until
this mode exists**, which is why it sits in `docs/prereg/README.md` blocked on a forward test.

### SHADOW — does not exist

The same computation as LIVE, journalled and explicitly marked non-actionable. Its purpose is to
accumulate a decision record before any decision is acted on.

Under D1 the gap between SHADOW and LIVE is narrow — the system does not act in either — so the
distinction that survives is a **reporting** one: a SHADOW record must be marked so that it can never
be counted in a live performance statistic. That marking does not exist yet and would need a journal
field.

### LIVE — partially, and less than the name suggests

`application/pipeline.py` is the daily run. It builds the universe, sizes candidates, and reaches
`"sized; awaiting a trigger"`.

**It implements no strategy.** There is no entry trigger on this path, so it produces no trade
candidates, and `0` of `465` registered components are `active`. LIVE is therefore unreachable in the
sense the ТЗ means it — not by a policy switch, but by construction. Anything this document says
about LIVE guarantees is a specification of what must hold when it exists, not a description of
something running.

## 3. What holds in every mode

These are not per-mode guarantees; a mode that breaks one is misconfigured, not specialised.

1. **No orders.** D1. There is no mode in which the system places one.
2. **Fail closed.** Missing, stale or conflicting input yields a coded refusal, never a guess
   (`FAIL_CLOSED_POLICY.md`).
3. **`unset` is not a default.** A parameter with no value makes its component refuse, in RESEARCH
   exactly as in LIVE.
4. **Records are immutable.** Corrections create versions.
5. **Provenance travels.** A number computed from an `assumed` parameter is marked as
   assumption-derived wherever it appears, including in a research measurement.

## 4. Mode is not a runtime flag

There is deliberately **no `SYSTEM_MODE` setting** in this tree, and adding one would be a
regression.

Modes are separated structurally instead: research code lives in `tools/` and cannot be imported by
`src/`; the backtest path lives in `validation/`; the live path lives in `application/`; and the
import contracts in `pyproject.toml` make a crossing a build failure rather than a runtime condition.
A flag would move that boundary from the layer graph — where gate 6 checks it on every commit — into
a variable that can be wrong at 09:31 on a Tuesday.

The one thing that *is* a runtime value is the **snapshot**: a named `knowledge_time`
(`POINT_IN_TIME_SPEC.md` §5). BACKTEST pins it to the decision bar and LIVE pins it to now, and
`DETERMINISM_SPEC.md` is explicit that there is no third option, because a third option is how
look-ahead gets in.

## 5. Open items

- [ ] **PAPER and SHADOW need journal support before they can exist** — specifically a field marking
      a record non-actionable, so a shadow trade can never be counted in a live statistic. That is a
      `JOURNAL_SCHEMA.md` change and it should precede either mode.
- [ ] **`REQ-VALIDATION-002` spans BACKTEST and LIVE** and is unmet. The trigger should be written
      once, in a layer both call, before the live path acquires one.
- [ ] **No mode currently declares its permitted writes in an enforceable form.** The table in §2 is
      accurate and is prose; the layer contracts enforce the import direction but not, for example,
      that BACKTEST never writes to `data/`.
