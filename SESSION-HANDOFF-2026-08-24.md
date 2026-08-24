# Session handoff — 2026-08-24

**Read `HANDOFF.md` first, then `TODO.md`.** This covers only what changed in the session that
ratified the liquidity floor, applied three owner rulings, opened the backtest engine to more than
one strategy family, gave it a portfolio, priced the trial budget, and wrote the project's first
strategy card. **Delete it once §1 is actioned.**

**It replaces the earlier `SESSION-HANDOFF-2026-08-24.md`**, deleted rather than edited as its own
header instructed. Nothing in it lived only there: its §1 is restated below and still live, its §2
inventory is in `DR-006` and `DR-016`, its §4 rulings are all taken, and its §5 sequence is the plan
that this session executed.

---

## 1. The first thing to check, and it is still not code

**Did the scheduled run survive Monday evening?**

```bash
python tools/verify_schedule.py
```

Gate 26. It was **red** when this was written, and for a reason that has not changed since Friday:
both passes last ran **2026-08-21** and both exited 1 on the `initial_costs_per_share` schema drift.
`positions.duckdb` carries the column again, so **Monday 2026-08-24's 18:30 and 19:30 passes are the
first that can get past it.** At the time of writing they had not yet run.

- **Green** → the outage that began 08-18 is genuinely closed and `a.run_completes` starts counting.
- **Still red** → read `data/daily_run.log` before anything else.

**`a.run_completes` stands at 0/20 and the owner ruled on 2026-08-24 to leave the threshold at 20.**
The question *"can we just fetch the missing 20 days?"* was put and answered with the run history:

| sessions | outcome |
|---|---|
| 08-09 → 08-17, 7 trading days | all `exit 0` |
| 08-18 → 08-21, 4 trading days | **all `exit 1`** |

**The best this system has ever done is 7 consecutive clean days, and its most recent record is a
four-day unbroken failure nobody noticed.** Twenty days is not a waiting period; it is a test that
has never been passed. Backfilling is also impossible by the criterion's own text — *"produces a
report **before the next session open**"* — so a replay run tonight for a July session cannot
satisfy it.

**The 20 days cost nothing, because nothing waits on them.** Track A runs in parallel with Track B
(`HANDOFF.md` §4). The binding constraint is **not the calendar but the freeze**: the counter has
reset three times from changes to decision output, never from a fault. **Sequence work to protect
it** — `validation/` is not frozen and `application/pipeline.py` is.

## 2. What was built, in one place

Six merged pull requests, [#33](https://github.com/golub-kirill/SwingDesk/pull/33) through
[#38](https://github.com/golub-kirill/SwingDesk/pull/38). Full records in the decision documents.

| | |
|---|---|
| Liquidity floor | `DR-003` **ratified**; its plateau argument refuted. `tools/measure_liquidity_floor.py` |
| Three owner rulings | `data.revision_epsilon` scoped to `close`, `risk.max_sector_risk` 2R, correlation cap refuses. `DR-006` **fully ratified**, `DR-016` §10 |
| Entry rule injectable | `EntryTrigger` protocol; `BacktestConfig.trigger` with **no default** |
| The book | `validation/backtest/book.py` — a session axis, competing candidates, bounded capacity |
| Trial budget | `docs/08-pm/TRIAL_BUDGET.md` + `tools/trial_budget.py`, **owner-pending** |
| The first strategy card | `registry/cards.yml`, `CARD-001`, **gate 27** |
| The benchmark | `DR-018`; `SPY`/`QQQ`/`IWM`/`IVV`/`VOO` stored; `tools/measure_benchmark.py` |

One new merge gate landed — **27**, the strategy-card contract. Derive every count with
`python tools/check_gates.py`; `HANDOFF.md` §2 owns the census and no other document states it.

## 3. Five things a fresh session must not get wrong

- **Point-to-point relative strength cannot use a benchmark.** `(1 + own) / (1 + benchmark)` on one
  cross-section is a strictly monotone transform of the name's own return — the benchmark's return
  is one constant for every name that day. Measured as a control that must return exactly 1:
  **15 of 15** pairs give Spearman 1.000000 over 1,148 names. **It is momentum with a decorative
  denominator.** A path-dependent form escapes the identity (ρ ≈ 0.6 against raw return) and there
  the index choice bites — SPY against QQQ at 0.616. The **index** is the decision; the **proxy**
  is not (SPY against IVV: 0.973).
- **A trial is a CONFIGURATION EVALUATED, not a pre-registration filed.** 13 are spent against a
  study census that reads 5. And the hurdle grows logarithmically, so rationing trials late buys
  almost nothing — what buys the control is declaring and counting them.
- **The backtest still has no sector or correlation cap, deliberately.** `run_book` enforces
  position count and open risk. The other four `DR-006` caps need point-in-time classification a
  backtest does not have, and admitting them would let a cap **appear to have been tested** when it
  was not.
- **Two stores, two clocks.** Bars and corporate actions are filled by different passes. Reading
  actions at the bar store's knowledge time hides every action fetched since the last bar refresh —
  on a first run, all of them. This session's benchmark tool tripped exactly that wire and reported
  "0 payments" for five funds holding 101 dividends.
- **Coverage is an ALPHABETICAL PREFIX, not a sample.** 99.0% of measured names sit in the
  directory's first half. It is liquidity-neutral — a seeded random sample of 115 and the prefix
  agree on five of six ADTV percentiles — but it is why `SPY` was missing while `DIA` was present.

## 4. On the owner — what is pending

None of these blocks anything. `DR-014` keeps the project paper-only.

| | recommendation |
|---|---|
| `TRIAL_BUDGET.md` | 25 trials total, 12 remaining (+0.29 sd(SR) for the whole remainder) |
| `DR-018` | ratify `rs.benchmark = SPY`; leave `rs.benchmark_form` unset for a pre-registration |
| `DR-003` | `min_price` and `min_bar_history` are still `assumed` — only the ADTV floor was ruled |

Also open and unchanged: `DR-017` (ADTV lag), `account.fx_rate_cad`,
`data.staleness_action_threshold`, and `DR-016` / `DR-017` remain `proposed`.

## 5. What the next session should pick up

The plan is
[`docs/08-pm/plans/2026-08-24-from-machinery-to-evidence.md`](docs/08-pm/plans/2026-08-24-from-machinery-to-evidence.md).
**Its steps 1 through 4 are done.** What remains is step 5 — spend the budget on families — and
`CARD-001` names exactly what stands between here and there, in `registry/cards.yml` `blocked_by`:

1. **Sector-relative strength.** The *other* way out of §3's identity: a per-name denominator is not
   a common factor. The classification store holds 1,148 classified names, so this is measurable
   today, and it decides whether the card's measure is market-relative or sector-relative.
2. **The first pre-registration for the selection rule** — `rs.benchmark_form`, `rs.lookback`,
   `rs.ranking_method` and `screen.relative_strength_rule` all come from a study.
   `ALLOCATION_SPEC` §3 forbids a decision record here.
3. **A study runner that calls `run_book`.** The engine can express the family; nothing has run it.
4. **Activate the four components** `CARD-001` needs. G6's denominator is **four**, not 465.

Below those, unchanged: the write-time revision fault does not reach the decision path (a frozen
`pipeline.py` change — sequence it against §1's counter), the 12 dirty-tree journalled runs hold
`a.reproducible` short, and bar coverage is under a third — `tools/refresh_universe.py --budget 500`,
repeatedly, is pure throughput and resets nothing.

## 6. Before you start

```bash
git worktree list && git branch -a
```

Run the gates with `PYTHONPATH=$PWD/src`. From a worktree, gates 23, 24 and 26 correctly report
`UNAVAILABLE`; point them at the real stores with `SWINGDESK_DATA=C:/PycharmProjects/SwingDesk/data`
when you need the runtime figures.

**Re-index the code graph** — `src/` changed in three of this session's merges. Pass
`name="swingdesk"`; omitting it creates a duplicate project, which this session did and had to
delete.

**Nothing this session touched `application/pipeline.py`**, so no counter reset was spent. Keep it
that way until §1 is green and the streak is worth protecting.
