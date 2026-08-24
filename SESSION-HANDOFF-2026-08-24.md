# Session handoff — 2026-08-24

**Read `HANDOFF.md` first, then `TODO.md`.** This covers one long session that took the project from
*"the first strategy card does not exist"* to *"the first strategy-card study has run and refused a
verdict"* — fourteen merged pull requests, `#33` through `#46`. **Delete it once §1 is actioned.**

**It replaces the earlier file of the same name**, deleted rather than edited as its own header
instructs. Nothing in it lived only there.

---

## 1. The first thing to check, and it is still not code

**Did the scheduled run survive Monday evening?**

```bash
python tools/verify_schedule.py
```

Gate 26. **Red at the time of writing**, and for a reason that has not changed since Friday: both
passes last ran **2026-08-21** and both exited 1 on the `initial_costs_per_share` schema drift.
`positions.duckdb` carries the column again, so **Monday 2026-08-24's 18:30 and 19:30 passes are the
first that can clear it.** They had not yet run.

- **Green** → the outage that began 08-18 is closed and `a.run_completes` starts counting.
- **Still red** → read `data/daily_run.log` before anything else.

**The 20-session requirement was put to the owner and confirmed.** *"Can we just fetch the missing
20 days?"* was answered with the run history, not with policy: 08-09 → 08-17 is seven trading days
all exiting 0, and 08-18 → 08-21 is four all exiting 1. **The best this system has ever done is
seven consecutive clean days, and its most recent record is a four-day unbroken failure nobody
noticed.** Twenty days is a test that has never been passed, not a waiting period — and the
criterion's own text (*"produces a report before the next session open"*) makes backfilling
impossible anyway.

**The 20 days cost nothing, because nothing waits on them.** Track A runs in parallel with Track B.
The binding constraint is the **freeze**, not the calendar: the counter has reset three times from
changes to decision output and never from a fault. **Nothing this session touched
`application/pipeline.py`** — keep it that way until the streak is worth protecting.

## 2. What changed, and the four findings worth carrying

Full records in the decision documents and `TODO.md`. Derive every count with
`python tools/check_gates.py`; `HANDOFF.md` §2 owns the census.

| | |
|---|---|
| `DR-003` | **ratified** — and its plateau argument **refuted** over the population |
| Three owner rulings | `data.revision_epsilon` scoped to `close`, `risk.max_sector_risk` 2R, correlation cap refuses. `DR-006` **fully ratified** |
| The engine | entry rule injectable (`EntryTrigger`); then a **book** (`run_book`) with a session axis and capacity caps |
| `TRIAL_BUDGET.md` | 13 trials were already spent against a census reading 5. **owner-pending** |
| `CARD-001` | the first strategy card, plus **gate 27** |
| `DR-018` | the benchmark; `SPY`, `QQQ`, `IWM`, `IVV`, `VOO` stored, five years each |
| `M31-T0464` | `specified` — `derived_observations/relative_strength.py` |
| `a.reproducible` | **PASSES** on the full 1,141-instrument universe, first production measurement |
| `PR-012` | ran, and **REFUSED a verdict** |

### 2a. A benchmark cannot change a cross-sectional ranking

On one date the benchmark's return is **one constant for every name**, so dividing by it is a
strictly monotone transform of the name's own return. Measured as a control that must return
exactly 1: **15 of 15** pairs give Spearman **1.000000** over 1,148 names.

**Point-to-point relative strength is momentum with a decorative denominator.** A *path* form
escapes it (ρ ≈ 0.6 against raw return) and a *sector* denominator escapes it (ρ 0.75–0.82) — and
**further from raw return is not better**, which is the reading that is easy to get wrong.

### 2b. The backtest had no portfolio, and the card is what found it

*"Hold the strongest N at once"* is a **portfolio construction rule**, and `run_arm` walked one
instrument with unlimited capital. `run_book` fixes it. **The `EntryTrigger` seam did not reach
this** — the two look alike from a distance and only one was done.

### 2c. `PR-012`'s 70/30 split cost it the study

The sample rule fired: two of three arms under 200 holdout trades, one of them the **control**. But
the split protected against a risk this study did not carry — **it fits nothing and selects
nothing**, so train and validation were empty by construction and 70% of the sample went for
nothing. **A split is a cost, not a virtue.**

And the fix is not available to whoever noticed it: rule 3 downgrades a redesign made after seeing
the data to **exploratory**. The full accounting is in that study's report.

### 2d. Gates could not represent honest outcomes, three times

Gate 3f's verdict vocabulary had no `REFUSED`, so **the first study to obey `PREREG_TEMPLATE` §8
failed a gate for it**. `trial_budget.py` counted the new study as **0** trials. Gate 11 refused one
function claiming two catalogue rows — **correctly**, and it was right where I was wrong.

## 3. What a fresh session must not get wrong

- **`REFUSED` is not `INCONCLUSIVE`.** One says there was not enough data to look with; the other
  says the study looked and could not tell.
- **A refused study still spends its trials.** `b.deflated_sharpe` deflates by shots taken at the
  data, not by shots that produced an answer.
- **Coverage is an alphabetical prefix**, not a sample — which is why `SPY` was missing while `DIA`
  was present, and why a percentile from it is defensible only because a seeded random sample and
  the prefix agree.
- **Two stores, two clocks.** Bars and corporate actions and classifications are filled by different
  passes; reading one at another's knowledge time hides everything since. **This trap was hit twice
  more this session.**
- **The stores are single-writer** (`ADR-0004`). A long refresh pass blocks every tool that reads
  them, and the right response is `UNAVAILABLE`, never a traceback.

## 4. On the owner — what is pending

None blocks anything. `DR-014` keeps the project paper-only.

| | recommendation |
|---|---|
| `TRIAL_BUDGET.md` | 25 total, and **16 are now spent** — derive with `python tools/trial_budget.py` |
| `DR-018` | ratify `rs.benchmark = SPY`; leave `rs.benchmark_form` unset |
| `DR-003` | `min_price` and `min_bar_history` are still `assumed` — only the ADTV floor was ruled |
| `DR-016`, `DR-017` | still `proposed` |

Also open and unchanged: `account.fx_rate_cad` (needs a source and an as-of) and
`data.staleness_action_threshold` (a ruling or an explicit retirement).

## 5. What the next session should pick up

`CARD-001`'s `blocked_by` is the list, and it is shorter and harder than it was this morning.

1. **The sample problem, and it is not a data problem.** §2c. Someone who has not read `PR-012`'s
   numbers should design the confirmatory version; anyone who has can only run it labelled
   exploratory.
2. **`M31-T0465` and `M33-T0487` are still `registered`.** Both need values a study has not
   produced.
3. **The write-time revision fault does not reach the decision path** — a frozen `pipeline.py`
   change, so sequence it against §1's counter.
4. **Bar coverage is still under a third of the directory.** `tools/refresh_universe.py` is pure
   throughput and resets nothing. The admitted universe now carries ten years; the rest does not.

## 6. Before you start

```bash
git worktree list && git branch -a
```

Run the gates with `PYTHONPATH=$PWD/src`. From a worktree, gates 23, 24 and 26 report `UNAVAILABLE`;
point them at the real stores with `SWINGDESK_DATA=C:/PycharmProjects/SwingDesk/data`.

**Re-index the code graph** — `src/` changed in most of this session's merges. Pass
`name="swingdesk"`; omitting it creates a duplicate project, which happened once and had to be
deleted.

**Two long jobs are worth knowing about**: the ten-year universe deepening took about two and a
quarter hours, and `verify_reproducible.py` takes about twenty minutes a pass. Both hold the bar
store, and both are worth running in the background rather than waiting on.
