# PREREG: does leaving leveraged and inverse funds out of CARD-001's picks earn more against SPY?

```
id:            PR-026
date:          2026-09-19
author:        Claude, on the owner's choice of 2026-09-19. Shown that CARD-001 breaks even entered
               at 15:55 (PR-024) and asked for ideas, the owner picked four and asked that they not
               be mixed: this is the first, and PR-027..PR-029 are the others. All four share the
               design in sections 4 and 5 here, one baseline, one draw and one pass
status:        reported   (2026-09-19 - results/PR-026-report.md)
verdict:       INCONCLUSIVE, branch NULL, as section 3 predicted - leaving leveraged and inverse
               funds out moves the card's excess over SPY by -0.007% a trade [-0.039, +0.018]
```

---

## 0. Refutation-family check

**searched:** `docs/prereg/`, `EVIDENCE_SUMMARY.md`, `docs/decisions/measurements/`.

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-020` | the screen's decile held against its own universe | refused by §9 — the decile held T-bill funds in a bear market, which weighted the null |
| `PR-021` | last week's losers | stocks only, by the directory's `is_etf`, because "a leveraged or inverse fund sits in the loser tail by construction" — the only study here to remove funds, and it removed all of them |
| `entry-features-2026-09-19` | `PR-024`'s own entries sliced by what the signal close knew — EXPLORATORY | the source of this idea; it looked at the answer on 2022-09..2026-08 |

**distinct because no study has asked whether the card's own picks include funds it should not
hold.** `CARD-001` ranks every admitted name, funds included, by how it has moved against `SPY`; a
3× fund on a rising index ranks near the top by construction and decays in a sideways one. The
exploration found such funds in the 15:55 arm doing worse than the rest; this asks it on the 48
months before, which the exploration never read.

**What is known in advance.** The author knows `PR-024`'s numbers and the exploration's slices on
2022-09..2026-08. Nothing here has priced 2018-09..2022-08 at the close or against `SPY`.

## 1. Question

Over 2018-09..2022-08, do `CARD-001`'s entries earn more per dollar against `SPY` over their own
days when the leveraged and inverse funds are left out?

## 2. Hypothesis

**H1.** The per-date difference — the mean excess over `SPY` of the entries that are not leveraged
or inverse funds, less the mean of all of that date's entries — has a 95% interval wholly above zero.

**H0.** It does not.

## 3. Prediction, stated numerically before the run

```
primary quantity:  per date, [mean excess of the kept entries] - [mean excess of all entries];
                   averaged over dates, month-clustered bootstrap
predicted:         NULL. Leveraged and inverse funds are a few percent of the decile's entries, so
                   even a whole point a trade worse moves the book by hundredths: centre +0.00% to
                   +0.05%. The filter is worth having for what it keeps out of a four-name book, not
                   for its mean
if H1 were TRUE:   the interval wholly above zero
minimum detectable effect:  0.03 points per dollar (half-width 0.022 at 90% complete x (1.96 + 0.84) / 1.96) - the difference the registered sample
                   detects with 80% power, from tools/power_pr026.py (PR-026-power.json): the
                   verdict estimator's own width on a pilot of every fourth date, scaled to the
                   window and to the lowest admitted complete share. Widths only
power floor:       0.30 points end to end (0.0030 per dollar), PR-024's; it gates NULL only
```

```bash
PYTHONPATH=$PWD/src python tools/power_pr026.py --report
```

| study | k = 10 | k = 20 | **k = 40 — the draw** | readable at the 0.30 floor |
|---|---|---|---|---|
| `PR-026` garbage | 0.079 | 0.048 | **0.044** | yes — `NULL` reachable |
| `PR-027` pullback | 0.563 | 0.533 | **0.522** | no — the sign of an effect beyond about ±0.26 |
| `PR-028` exit | 2.102 | 2.027 | **2.048** | no — the sign beyond about ±1.02 |
| `PR-029` regime | 1.092 | 0.932 | **0.952** | no — the sign beyond about ±0.48 |

End-to-end widths in points per dollar, at the window's 1,006 dates and a 90% complete share.
**More names a date barely help**: what the dates share - the market's path over each hold - is
most of the width, and `PR-024` found the same. `k = 40` is the power tool's registered rule: the
smallest `k` at which all four read at the floor, or the largest when some cannot. Three cannot,
so three of the four registrations can read only a large effect's sign, and each says so in its §3.
`PR-028` is widest because a 60-session hold carries forty more days of each name's own drift
against the index than the baseline's; that is the question's own noise, not the sample's.

## 4. Data — shared by PR-026..PR-029

```
store:         the owner's daily store, copied read-only on 2026-09-16 (PR-024's copy);
               knowledge_time 2026-09-16T19:30:10.930516-05:00
directory:     the owner's symbol directory, copied read-only on 2026-09-19; its latest pull. The
               leveraged-or-inverse rule reads fund NAMES, and only current names are stored, so a
               fund renamed since would be read by its new name
window:        formation sessions 2018-09-04 .. 2022-08-31: 1,006 sessions, 48 months - the 48
               before PR-024's, which the exploration never read. The default window
               (AGENTS.md 19), so no rationale is owed
universe:      CARD-001's selection, as in PR-024: run_pr016's ranked rule, the top decile, PR-016's
               pinned admission
sample:        every formation session x 40 names, seeded per date (SAMPLE_SEED 20260919), drawn
               and committed with this registration as results/PR-026-sample.jsonl
country:       USA
survivorship:  present; it lifts levels, and every study here reads a difference within one draw
entry:         the CLOSE of the session after the signal - the daily price nearest PR-024's 15:55.
               No minutes or quotes exist for this window, so the entry session is not walked
costs:         PR-024's measured half-spreads of the card's own names, by moment: 5.0 bps to enter
               at the close; exits at 8.4 bps for an intraday stop or target, 37.8 for a gap through
               the stop, 5.0 for the clock. The SPY leg is charged nothing, which leans against the
               card. Commission 0 (DR-039)
```

## 5. Method — shared by PR-026..PR-029

* **The baseline** is the card as it is at the close: stop 2 × ATR(14) below the fill, target 1R,
  20 sessions, the ratified exit walked by `run_pr024.walk_entry` (`PR-024`'s `--parity`-proved
  walk). An ambiguous daily bar resolves stop-first: no minutes exist for this window.
* **Every trade is read in excess of `SPY`** over its own days: its net return per dollar less
  `SPY`'s from the entry session's close to the exit session's close.
* **The statistic** is a per-date mean, averaged over dates, with a 95% moving-block bootstrap over
  signal months, block 3, 10,000 resamples, seed 20260919.
* **`level`** is the arm's own mean excess over `SPY`, read by `BOTH_NEGATIVE`.

### 5a. The split, and what it buys

```
split:           none
split buys:      nothing is selected - one rule, fixed here - and the window is one the idea was
                 not found on
perturbations:   cost_adverse - every fill at 3x its moment's cost; gross - no cost at all
```

**This study's arm.** A fund is leveraged or inverse when the directory marks it an ETF and its name
carries a hard mark — "leveraged", "inverse", "bear", a multiple such as "3X", "Daily … Bull" — or
a soft one — "ultra", "short" — without a bond word, or from ProShares (`run_pr026.levered_name`,
tested against the directory's own fund names).

## 6. Decision rule

By `run_pr026.branch_for`, in `PR-024`'s order with the sample rule in dates: `REFUSED` under 90% of
drawn entries priced, 500 dates or 24 months; `BOTH_NEGATIVE` if the difference is wholly above zero
and the kept entries' own excess over `SPY` wholly below; `COST_FRAGILE` if wholly above and the
cost-adverse difference not above zero; `ACCEPT` wholly above; `REJECT` wholly below; `INCONCLUSIVE`
containing zero and wider than 0.30; `NULL` containing zero inside it.

* `ACCEPT` — *leaving leveraged and inverse funds out earned more against `SPY`*.
* `NULL` — *it made no difference the sample could see*; it may still be worth doing for what it
  keeps out of a four-name book, which is a risk argument this study does not make.
* `REJECT` — *the funds earned more than the rest*.

Changing the card is the owner's call whatever the branch.

## 6a. Trials

**One.** The four registrations take the count from **127 to 131** and the hurdle from **2.614 to
2.624** sd(SR); this one is the first.

**Registered as NOT run:** dropping all funds; dropping the illiquid; other name rules.

## 7. Stopping rule

One draw, one pass at the pinned instants, shared with `PR-027`..`PR-029`. Nothing tried after the
first result is seen.

## 8. Sample

```
minimum:       90% of drawn entries priced, 500 dates, 24 months
power floor:   0.30 points end to end, gating NULL only
if not met:    report the measurement and REFUSE to read it as evidence
```

## 9. What would refute this

**H1 is refuted** by `REJECT` or `NULL`. **The study is refuted** by a realised width outside half to
twice the predicted, or by the pass pricing fewer than 90% of the draw.

## 10. Amendments

None.
