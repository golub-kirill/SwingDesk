# PREREG: do CARD-001's picks earn more against SPY when bought on a pullback below their 20-day mean?

```
id:            PR-027
date:          2026-09-19
author:        Claude, on the owner's choice of 2026-09-19 - the second of four single changes
               registered together (PR-026 carries the shared design, sections 4 and 5)
status:        reported   (2026-09-19 - results/PR-027-report.md)
verdict:       INCONCLUSIVE - the pullback entries less all entries, -0.094% a trade
               [-0.392, +0.176]; the exploration's +0.57% did not come back
```

---

## 0. Refutation-family check

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-015` `REVERSAL_21` | buying the 21-day LOSERS of the universe, held 20 sessions | lost, with `LOWVOL_126` |
| `PR-021` | buying last week's losers of the whole universe | `REJECT` — no edge before costs either |
| `entry-features-2026-09-19` | `PR-024`'s entries sliced at the signal close — EXPLORATORY | entries whose close sat below their 20-day mean read best of every slice; the source of this idea |

**distinct because the losers here are LEADERS.** `PR-015` and `PR-021` bought the universe's
losers; this keeps the card's own top decile by six-month strength and asks only whether buying the
ones that have just dipped beats buying the whole decile — a short-term reversal inside a long-term
winner, which is a different claim from reversal on its own.

**What is known in advance.** The exploration saw this slice lead on 2022-09..2026-08 and it is the
author's favourite of the four. That is why it is tested on the 48 months the exploration never
read, and why §3 predicts it smaller there.

## 1. Question

Over 2018-09..2022-08, do the card's entries whose signal close is below their own 20-session mean
earn more per dollar against `SPY` over their own days than the card's entries as a whole?

## 2. Hypothesis

**H1.** Per date, the pullback entries' mean excess over `SPY` less all entries' has a 95% interval
wholly above zero. **H0.** It does not.

## 3. Prediction, stated numerically before the run

```
primary quantity:  per date, [mean excess of the pullback entries] - [mean excess of all entries];
                   averaged over dates holding a pullback entry, month-clustered bootstrap
predicted:         positive and smaller than the exploration's: centre +0.1% to +0.3%, so
                   INCONCLUSIVE - the interval reads only an effect beyond about +/-0.26 (PR-026 §3's
                   table). ACCEPT only if the exploration's size holds on a window it never read;
                   BOTH_NEGATIVE if it does and the pullback entries still trail SPY on their own
if H1 were TRUE:   the interval wholly above zero
minimum detectable effect:  0.37 points per dollar (half-width 0.261 at 90% complete) - from tools/power_pr026.py
                   (PR-026-power.json), as PR-026 §3 describes. Widths only
power floor:       0.30 points end to end, gating NULL only
```

## 4. Data and 5. Method

`PR-026` §4 and §5, unchanged. **This study's arm:** an entry is a pullback when its signal close is
below the mean of its own last 20 closes, the signal's included (`run_pr026.features`).

```
split:           none - one rule fixed here, on a window it was not found on
split buys:      nothing is selected
perturbations:   cost_adverse, gross - as PR-026
```

## 6. Decision rule

`PR-026` §6's table on this contrast. `ACCEPT` — *the card's picks bought on a pullback earned more
against `SPY` than its picks as a whole*. `BOTH_NEGATIVE` — *more, and still behind the index*.
`NULL` — *no difference the sample could see*. `REJECT` — *less*.

## 6a. Trials

**One** — the second of four (127 → 131, hurdle 2.614 → 2.624).

**Registered as NOT run:** other means (10, 50 sessions); a depth of pullback; a pullback in ATR.

## 7. Stopping rule, 8. Sample, 9. Refutation

As `PR-026`.

```
minimum detectable effect:  see section 3
power floor:                0.30 points end to end, gating NULL only
```

## 10. Amendments

None.
