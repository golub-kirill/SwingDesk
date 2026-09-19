# PREREG: re-priced at the close, does PR-019's wide exit earn more against SPY than the ratified exit?

```
id:            PR-028
date:          2026-09-19
author:        Claude, on the owner's choice of 2026-09-19 - the third of four single changes
               registered together (PR-026 carries the shared design, sections 4 and 5)
status:        registered
```

---

## 0. Refutation-family check

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `PR-018` | the ratified exit against holding to the clock, on selected entries | `INCONCLUSIVE`; holding earned more and bought a tail |
| `PR-019` | holds × stop widths on selected entries, one selected in sample (2016-2021) | `INCONCLUSIVE`; §6 selected **`h60_stop4.0`**, +0.189R over the ratified exit out of sample |
| `PR-019b` | that cell against `SPY` over each trade's own days | `INCONCLUSIVE` for precision; `SPY` earned +0.2071R, the cell −0.1543R [−0.2930, −0.0501] less |

**distinct because it is a RE-PRICE, and says so.** `PR-019` chose this exit on 2016-2021 — which
overlaps this window — at the open, with `DR-005`'s 25 bps a side, in R. This walks the same cell on
the card's entries at the CLOSE, with the card's measured spreads by moment, and reads it per dollar
against `SPY` over the same days, which is where `PR-019b` found it short. It selects nothing; it
asks whether the cheaper entry changes `PR-019b`'s answer.

**What is known in advance.** The author knows `PR-019`'s in-sample results for these years in R.

## 1. Question

Over 2018-09..2022-08, on the same entries, does a 4 ATR stop with no target held 60 sessions earn
more per dollar against `SPY` over its own days than the ratified exit does over its own?

## 2. Hypothesis

**H1.** Per entry, the wide exit's excess over `SPY` less the ratified exit's has a 95% interval
wholly above zero. **H0.** It does not.

## 3. Prediction, stated numerically before the run

```
primary quantity:  per entry [excess over SPY, wide exit] - [excess over SPY, ratified exit],
                   averaged within dates, then over dates; month-clustered bootstrap
predicted:         INCONCLUSIVE: the interval is about 2 points wide (PR-026 §3's table), so only an
                   effect beyond about +/-1.0 point a trade reads. PR-019's +0.19R is roughly one
                   point a trade in dollars, at the edge of what this can see. Centre +0.0% to
                   +0.6%; behind SPY on its own days, as PR-019b found
if H1 were TRUE:   the interval wholly above zero
minimum detectable effect:  1.46 points per dollar (half-width 1.024 at 90% complete) - from tools/power_pr026.py
                   (PR-026-power.json), as PR-026 §3 describes. Widths only
power floor:       0.30 points end to end, gating NULL only
```

## 4. Data and 5. Method

`PR-026` §4 and §5. **This study's arm:** the same entries under `ExitPolicy(4.0, 60, no target)`,
walked by the same code. A 60-session hold reads bars past the window's last formation date; the
store holds them.

```
split:           none - PR-019's selection is re-priced, not re-made
split buys:      nothing is selected
perturbations:   cost_adverse, gross - as PR-026
```

## 6. Decision rule

`PR-026` §6's table. `ACCEPT` — *the wide exit earned more against `SPY` than the ratified exit*.
`BOTH_NEGATIVE` — *more, and still behind the index over its own days*. `NULL`, `REJECT`, as there.

## 6a. Trials

**One** — the third of four (127 → 131). It re-prices a counted cell, and is counted anyway: a new
price and a new yardstick are a new reading somebody could keep.

**Registered as NOT run:** any other hold, stop or target; a close-basis stop.

## 7. Stopping rule, 8. Sample, 9. Refutation

As `PR-026`.

```
minimum detectable effect:  see section 3
power floor:                0.30 points end to end, gating NULL only
```

## 10. Amendments

None.
