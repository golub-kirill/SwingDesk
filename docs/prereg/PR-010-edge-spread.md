# PREREG: Does EDGE resolve the spread level that Corwin-Schultz and Abdi-Ranaldo could not?

```
id:      PR-010   (PR-009 is the drawdown study; see docs/prereg/README.md)
date:    2026-08-09
author:  owner
status:  registered
blocked: nothing - runs offline against data/bars.duckdb
```

## 0. Refutation-family check

- **searched:** `docs/prereg/` for cost and spread studies; `DR-004`, `DR-005`; `PR-008`'s report
  and its correction; the published literature (`AGENTS.md` §10.3).
- **found:** `PR-008` ran Corwin-Schultz and Abdi-Ranaldo and returned **inconclusive**. `DR-005`
  measured 25.44bp per side with Abdi-Ranaldo. Both efforts hit the same wall: the estimate tracks
  volatility rather than liquidity.
- **distinct because:** EDGE (Ardia, Guidotti & Kroencke, *JFE* 2024) is a **different estimator**,
  not a variant — it uses the **open**, which neither of the others reads, and it was built to
  correct exactly the bias both rediscovered. This is not another draw from a refuted family; it is
  the instrument the literature says supersedes it.

## 1. Question

Can EDGE produce a spread level for this universe that is distinguishable from its own noise?

## 2. Hypothesis

EDGE's estimate on the `DR-003`-eligible universe exceeds its zero-spread floor at this universe's
**measured** volatility, by enough that the level can be used to set `costs.slippage_model`.

## 3. Prediction, and the calibration that is already done

**This is registered before the run and it is not encouraging.** The instrument was calibrated
first, on synthetic series matched to volatility measured from `data/bars.duckdb` — overnight sd
**2.992%**, intraday sd **3.579%**, over 1,484,431 sessions.

Zero-spread floors at that volatility, 500 sessions, 15 seeds, in **bp per side**:

| True spread | EDGE | Abdi-Ranaldo | Corwin-Schultz |
|---|---|---|---|
| **0** | **41.87** | **33.85** | 0.00 |
| 5 | 40.57 | 36.09 | 0.00 |
| 25 | 33.61 | 49.29 | 0.00 |
| 50 | 52.41 | 66.44 | 0.71 |

Two things follow, both fixed here before any real bar is read:

1. **`DR-005`'s 25.44bp is below Abdi-Ranaldo's own 33.85bp zero-spread floor** at this volatility.
   The number it reports is smaller than what the same estimator reads on nothing.
2. **EDGE is not monotonic** across this range — it reads *less* at a true 25bp than at 0.

**If TRUE:** EDGE's estimate on real bars exceeds ~42bp per side by a margin that survives a seed
sweep, and rises with a rising true spread in the calibration.

**If FALSE:** the estimate sits at or below the floor, and no level is obtainable from OHLC on this
universe by any of the three estimators.

## 4. Data

```
universe:      DR-003 liquidity rule, as PR-008
window:        data/bars.duckdb as committed, 2024-08-05 to 2026-08-03
snapshot:      the store's own maximum knowledge_time
costs:         none charged - this measures a cost
survivorship:  ABSENT, and conservative here as in PR-008
```

## 5. Method

EDGE per instrument over its full series, transcribed from the reference implementation
(`github.com/eguidotti/bidask`) and unit-tested against a known spread. Statistic: **median per-side
half-spread in bp**, compared against the 41.87bp floor from §3.

## 6. Decision rule

```
accept:        median exceeds 2x the calibrated floor (>= 84bp per side) - a level this large
               would be usable even allowing for the floor
reject:        median at or below the floor (<= 42bp) - no level is obtainable
inconclusive:  between; or EDGE non-monotonic on the calibration, which it already is
```

**§3's calibration means `inconclusive` is the most likely outcome and that is recorded now, not
discovered later.** A decision rule written after seeing a number is not a decision rule.

## 7. Stopping rule

One pass. No re-running with a different window or estimator.

## 8. Sample

Minimum 200 eligible instruments, as `PR-008` §8. Below that, report coverage and refuse.

## 9. What would refute this

An estimate at or below the calibrated floor. That would establish — for the third estimator, and
the one built to fix the other two — that **the spread level is not obtainable from daily OHLC on
this universe at this volatility**, and that the only remaining route is `PR-006`: real fills.

It would **not** mean there is no spread. `PR-008`'s sign test settles that there is: real bars
clamp at 19.1% against 51.5% for spreadless synthetic at measured overnight volatility. Direction
and level are different claims, and only the second is in question.

## 10. Amendments

None.
