# PR-021 RESULT: last week's losers lose to the index at every hold, and before costs they do not beat their own universe either

```
prereg:        PR-021
ran:           2026-09-13
verdict:       REJECT. On half B of the names, which neither the selection nor the power
               estimate ever loaded, the five-session book half A selected trails SPY by
               -24.95 points a year [-38.82, -10.09], net of DR-005 on measured turnover - the
               interval wholly below zero. Every other hold on half B is further below. Before
               any cost the same book is -3.67 [-17.62, +11.21] against SPY and +1.59 [-8.29,
               +11.89] against the stocks it was drawn from: no reversal edge was there to pay for
status:        final - no stop, no target, no ambiguous bar; the sign is read whatever the width,
               as section 6 registered before the run
tool:          tools/run_pr021.py, sized by tools/power_pr021.py
evidence:      PR-021.json, PR-021-power.json
trials:        5, declared before the run
```

---

## Read this first

**Short-term reversal, as this system would trade it, does not work here.** The owner chose the
class on 2026-09-13; this is its first registered test. Buying each session's bottom decile of US
stocks by five-session return at the next open and holding one to five sessions **loses to holding
`SPY` over the same days at every hold, on both halves of the names**, and on the half the verdict
is read on every interval lies wholly below zero.

**The cost is not the whole reason, and that is the finding that matters more than the verdict.**
Before any cost the book does not beat its own admitted universe: **+1.59 points a year [−8.29,
+11.89]** on half B at the selected hold, **−0.82** on half A. The weekly reversal the literature
documents is not measurable in this universe over these 48 months, at this construction. So
trading later in the day, where `DR-040` measured the spread six times narrower, cannot rescue it:
the break-even cost against `SPY` is **negative at every hold on both halves**. No execution price
makes a book with a negative gross edge beat the index.

**And the store flatters this book.** A loser is likelier than a winner to be delisted, and a name
that died is missing (§4). The true figure is lower than the one reported.

## §9, which had to hold before the verdict could be read

| check | registered limit | realised |
|---|---|---|
| half B's width against half A's predicted one | at most 1.5× | **28.73 against 32.78 — 0.88×** |
| name-sessions without a price | at most 1% | **41 of about 555,000 — 0.007%** |
| typical cohort | at least 50 names | **111**, smallest 99 |
| thin formations | at most 5% | **none** |

**All four hold.** The halves behaved as one instrument, and the power estimate was, if anything,
pessimistic: half B read 12% narrower than half A predicted.

## The verdict, as §6 reads it

**The selection, on half A** — the hold with the largest mean of `book net − SPY`:

| hold | 1 | 2 | 3 | 4 | **5** |
|---|---|---|---|---|---|
| half A, points a year | −57.51 | −40.53 | −34.17 | −30.29 | **−28.43** |

**Five, the least negative**, and the ordering is the cost ladder: every hold on half A has the same
gross to within three points, and the one that trades least loses least.

**Half B at five sessions:**

```
book net - SPY:        -24.95 points a year  [-38.82, -10.09]   width 28.73
branch:                REJECT - the interval lies wholly below zero
```

`REJECT`, and it does not rest on the order §6 registered. Under the older order, where the floor
comes first, a width of 28.73 against the 20-point floor would have read `INCONCLUSIVE`: that is
exactly the reading `PR-019b` was refused on, and the reason §6 was registered the other way round.
Nothing about this interval is borderline: its top is ten points below zero.

**Every hold on half B**, printed and not read:

| hold | book net − `SPY` | gross − `SPY` | net − own pool | gross − own pool (the signal) |
|---|---|---|---|---|
| 1 | −49.75 [−63.92, −34.46] | −1.37 [−15.63, +13.94] | −44.48 [−55.62, −32.97] | +3.90 [−7.47, +15.54] |
| 2 | −35.42 [−49.68, −19.76] | −1.15 [−15.48, +14.60] | −30.15 [−41.28, −18.73] | +4.12 [−7.17, +15.58] |
| 3 | −28.33 [−42.63, −13.02] | −0.40 [−14.82, +14.95] | −23.06 [−33.66, −12.17] | +4.87 [−5.84, +15.89] |
| 4 | −26.10 [−40.23, −11.16] | −2.08 [−16.27, +12.93] | −20.83 [−30.91, −10.46] | +3.19 [−6.97, +13.66] |
| **5** | **−24.95 [−38.82, −10.09]** | −3.67 [−17.62, +11.21] | −19.68 [−29.47, −9.43] | +1.59 [−8.29, +11.89] |

Points a year, ×252, arithmetic; 95% moving-block intervals, block 10, 10,000 resamples.

## §3's prediction, graded

| | predicted | realised |
|---|---|---|
| branch | `REJECT` or `INCONCLUSIVE`, never `ACCEPT` | **`REJECT`** |
| where `REJECT` fires | a gross excess over `SPY` under about 5 points a year | **−3.67** |
| centre, gross against `SPY` | 0 to +10 | **−3.67** — below the band |
| centre, net against `SPY` | −11 to −21 | **−24.95** — beyond the band |
| width at five sessions | 32.78 | **28.73** |
| cost at five sessions | 21.2 points a year | **21.3** on half B |

**The branch was right and the level was too kind.** §3 expected a small positive gross edge eaten by
the cost; there was no positive edge. The cost arithmetic decided the branch exactly as §3 said it
would, and the gross came in below the band it named.

## Perturbation — three times `DR-005`

−67.49 points a year on half B at five sessions. The perturbation is read by §6 on an `ACCEPT` only
and did not need to be.

## Diagnostics — registered, printed, never read by §6

At the selected hold, half B:

| | |
|---|---|
| the book's own net return | −7.43 [−27.90, +17.60] a year |
| `SPY` over the same sessions | +17.51 [+5.53, +32.04] |
| the book's admitted pool | +12.24 [−2.57, +30.20] |
| turnover | 16.9% of the book bought a session — **21.3 points a year of cost** |
| break-even cost, a side | **−4.3 bps against `SPY`**, +1.9 bps against the pool |
| beta to `SPY` | **1.45** |
| worst drawdown, net | **−41.4%**, against `SPY`'s −20.0% |
| worst session against `SPY` | −6.01% |

**Break-even against `DR-040`'s curve.** Against `SPY` there is none: the gross edge is negative, so
the book loses at a cost of zero. Against its own pool the break-even is 1.9 bps a side at five
sessions on half B and **below zero on half A** — under the 4.0 bps `DR-040` measured at the close,
the cheapest minute of the day. **The execution-time study §6a held in reserve is not worth
registering for this book.**

**Twice `SPY`'s drawdown for less than half its return.** At beta 1.45 the book fell 41% from its
peak while the index fell 20%, and earned −7.43 points a year against the index's +17.51.

## Exploratory, after the run — how far below its own beta the book sat

*Not registered, not read by anything, and computed on arithmetic means with one factor.* A book
with beta 1.45 in a window where `SPY` returned 17.51 points a year would have earned about 25.4
from beta alone. It earned **13.84 gross** (−3.67 + 17.51). So before any cost the losers sat about
**11.5 points a year below their own beta line**: last week's losers did not bounce, they kept
underperforming the market's move. That is the opposite of the class's premise, and it is one
reading of one window — the next registration should not be built on it.

## What this establishes, and what it does not

**Established, at the registered design:**

* **At the cost of the open, the class loses to the index** — the verdict, on names the selection
  never saw, with the interval ten points clear of zero.
* **Before costs there is no edge over the universe the book is drawn from** — every hold, both
  halves, every interval containing zero, the point estimates between −3.2 and +4.9.
* **So no cheaper execution rescues it** — against the index the break-even is negative everywhere.

**Not established:**

* **That reversal is absent everywhere.** Only in US stocks above a $5m-a-day floor, over
  2022-09-13 to 2026-09-10, formed on five sessions, held at the open. De Groot, Huij & Zhou (2012)
  find it among the largest names with turnover managed; a residual or industry-adjusted signal, a
  one-day formation, or a buy/hold band are each another configuration §6a listed as not run.
* **Anything about a different market.** 48 months, one country, a window in which `SPY` returned
  17.5 points a year; a high-beta book of losers in a falling market is a different measurement.
* **A precise magnitude.** The interval is 28.73 points wide. The sign is established; the size is
  known to within about ±14 points.

## What this licenses

> *At the cost of trading at the open, buying last week's biggest losers loses to the index — and
> before any cost it does not beat the stocks it was drawn from.*

No parameter moves. `CARD-001` is untouched; nothing here was ever a card.

## What it changes

**The first new class is closed at its own level, as the relative-strength family was.** Over the
same 48 months, holding `SPY` has now beaten every active construction this project has measured:
selection, exit and sizing of the relative-strength family (`EVIDENCE_SUMMARY` §20.6–§20.9), and
short-term reversal (§21). The next step is the owner's — the index with drawdown control, another
class, or a pause in research — and not a variant of this book, which §6a's not-run list would make
another draw from the same family.

## What the study cost

**Five trials**, declared before the run. The programme's count moves from **115 to 120** and the
hurdle from **2.58 to 2.59** sd(SR) — derive both with `python tools/trial_budget.py`. The run took
six minutes from the registration commit's own snapshot, against the byte-identical store copy §4
names.
