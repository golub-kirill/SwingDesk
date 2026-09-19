# PR-024 RESULT: buying CARD-001's picks five minutes before the close instead of at the open earns +0.31% a trade — all of it the spread, none of it the price

```
prereg:        PR-024
ran:           2026-09-17
verdict:       ACCEPT, against section 3's prediction. On 8,878 complete entries over 48 months,
               entering at 15:55 instead of the 09:30 open earns +0.311% per dollar a trade
               [+0.228, +0.418], net of each name's own quoted spread; the interval is 0.190 wide
               against the 0.30 floor and survives the registered cost stress at +0.200%
               [+0.099, +0.319]. The price part is -0.016% [-0.105, +0.090]: the whole difference is
               the spread. Beside it and never read by section 6: at 15:55 the card itself earns
               +0.024% a trade [-0.396, +0.456] - it stops losing, it does not start winning
status:        final - three moments fixed before the run, no selection, no split. Section 9's
               checks held: parity with the engine on all 9,820 entries, a realised width 0.69 of
               the predicted one. The section headed "Exploratory" was chosen after the result
tool:          tools/run_pr024.py, sized by tools/power_pr024.py, quotes by
               tools/fetch_entry_quotes.py, minutes by tools/fetch_minutes.py; the exploratory
               readings by tools/attribute_pr024.py
evidence:      PR-024.json, PR-024-power.json, PR-024-sample.jsonl, PR-024-qa-sample.csv,
               PR-024-ambiguous-bars.jsonl, PR-024-attribution.json
trials:        2, declared before the run (C and T; O is PR-016's configuration)
```

---

## Read this first

**The moment `CARD-001` buys at is worth about a third of a percent a trade, and the card has been
buying at the worst one.** Every entry the card's screen chose over the last four years was bought
three ways on its entry session — at the 09:30 open, at 11:00 and at 15:55 — each paying its own
name's SIP quoted spread at that moment and exiting under the ratified stop, target and clock.
Five minutes before the close beat the open by **+0.311% of the money invested per trade**, and
11:00 by +0.313%.

**All of it is the spread.** The card's names cost **37.8 bps** a side at the open on average and
**5.0 bps** at 15:55; the difference, 32.8 bps, is the measured saving to within a basis point. The
price itself did not move against the late entry: the gross part of the difference is **−0.016%**,
with an interval across zero. `DR-040` §4's worry — that a later entry buys the same name higher —
read −0.138% ±0.314 on the universe in §9; on these names over these four years it is zero within
about ±0.10%.

**It does not make the card profitable.** At 15:55 the card earns **+0.024% a trade**, an interval
from −0.40% to +0.46%; at the open it loses about 0.29%, the difference of the two. Moving the
clock turns a losing rule into one that breaks even. Whether that beats holding `SPY` is not what this measured.

**§3 predicted `NULL` or `INCONCLUSIVE`, and was wrong for two reasons** worth keeping (below).

## §9, which had to hold before anything else could be read

| check | registered | realised |
|---|---|---|
| the walk against `engine.run_arm`, at the daily open with `PR-016`'s costs | no entry may differ | **0 of 9,820** differ |
| realised half-width against the predicted 0.138 | between half and twice | **0.095**, 0.69 of it |
| minutes that do not reproduce their bar | under a tenth of the draw | **116 of 9,820**, 1.2% |
| an arm filled before its instant; an entry-day exit from before the fill | none | none — the close arm exited on its entry session **0** times, the open arm 142 |
| complete share | at least 90% | **90.4%** — 8,878 of 9,820 |
| pairs, entry months | 1,000 and 24 | **8,878** and **48** |

**The width came in narrower than predicted**, 0.190 end to end against 0.276, so the estimate
erred on the safe side. The likeliest reason, not measured: the pilot proxied the close arm by the
day's closing print with no spread and read its dispersion there, while the realised difference
also carries a spread saving that moves less from name to name.

**The complete share cleared by 0.4 points**, and much of what it lost was not the verdict's arm:
the 11:00 arm found no print within five minutes on 481 entries and no fresh quote on 181 (an entry
can fail more than one check; `PR-024-attribution.json` counts every failure). The Exploratory
section measures what that rule cost.

## The verdict, as §6 reads it

| `C − O`, per dollar a trade | estimate | 95% interval |
|---|---|---|
| **net — what §6 reads** | **+0.311%** | **[+0.228, +0.418]** |
| gross part (no costs at all) | −0.016% | [−0.105, +0.090] |
| cost part | +0.327% | — |
| **cost-adverse** — `C` at 3× its spread, exits at the open's | **+0.200%** | [+0.099, +0.319] |
| exits all at 25 bps (`PR-016`'s convention) | +0.310% | [+0.227, +0.415] |
| legs from the signal close, as the live bracket places them | +0.296% | [+0.228, +0.355] |
| each date weighted equally | +0.325% | [+0.243, +0.430] |
| clustered by instrument | +0.311% | [+0.205, +0.420] |
| in R | +0.056R | [+0.041, +0.073] |
| **`C`'s own net, per trade** | **+0.024%** | [−0.396, +0.456] |

§6 in its order: the sample rule is met; the interval lies wholly above zero; `C`'s own interval is
not wholly below zero, so not `BOTH_NEGATIVE`; the cost-adverse reading is above zero, so not
`COST_FRAGILE`. **`ACCEPT`.**

**`T`, 11:00 — counted, never read:** +0.313% [+0.212, +0.415], gross +0.003%, cost-adverse +0.309%.
It would read `ACCEPT` on its own. Its spread is 8.4 bps against the close's 5.0, and its stress
leaves it alone because §5a tripled only the close arm.

**Every reading agrees.** Weighting dates equally — the estimator that turned `DR-040` §9's +0.310%
into +0.049% — gives +0.325% here, because every date carries ten names. Clustering by name instead
of month moves the interval by a hundredth.

## §3's prediction, graded

§3 predicted a difference near zero, centred between −0.10% and +0.10%. It came in at +0.311%.

**Wrong about the population.** It expected the decile's names to trade near the universe's p10 of 3
bps at the open. They trade near its median and above: **p10 3.8, median 24.5, p90 85.1 bps**. A
screen that ranks by how a name has moved against the market picks names that move — small, volatile
and wide at the open — and `DR-040`'s liquid-universe intuition does not carry over.

**Wrong about the mechanism.** It argued that under the engine's convention the stop and target move
with each arm's own fill, so a stop or target exit would hand most of the entry cost back. At any
single stop or target exit that is true — the median difference is **−0.001%**, and `C` beat `O` on
only 48.6% of entries. But a fill paid higher sits its stop closer and its target further in price,
so more trades end at the stop: the premium is not handed back, it is lost as odds. The mean
difference lives almost entirely in the entries where one arm hit its target and the other its
stop (the Exploratory section splits it by exit).

**Right about the price.** The gross part is zero within ±0.10%, which is inside what §3 allowed.

## Diagnostics — registered, printed, never read by §6

| arm | entry half-spread, bps: p10 / p50 / p90 / average | target | stop | time | stop gap | exited the entry day |
|---|---|---|---|---|---|---|
| `O` 09:30 | 3.8 / 24.5 / 85.1 / **37.8** | 4,034 | 3,437 | 708 | 695 | 142 |
| `T` 11:00 | 1.1 / 5.2 / 19.0 / 8.4 | 4,254 | 3,168 | 770 | 681 | 24 |
| `C` 15:55 | 0.9 / 3.1 / 10.6 / **5.0** | 4,238 | 3,182 | 796 | 659 | 0 |

**Exclusions**, by the first check that failed: no print within five minutes of an arm's instant 447,
no fresh two-sided quote 239, a stop not below the entry 129, minutes not reproducing the bar 116,
zero shares 8, a stop not above zero 2, minutes unavailable 1 (`ALB$A`, a preferred the vendor does
not list). Tie-breaks from the minutes: 14, all resolved.

## Exploratory, after the run — what the exclusions cost, and whether it is a few names

`tools/attribute_pr024.py`, `PR-024-attribution.json`. **Chosen after the result was seen; nothing
here is evidence and nothing here changes §6.**

**The registered rule drops an entry when ANY arm or costing fails**, so a failure of the 11:00 arm
(never read) or of the anchored-stop perturbation drops the entry from `C − O` as well. That is a
design fault, stated here rather than discovered by a reader, and it is measured:

| population | entries | `C − O` | 95% interval | median | 1% trimmed | `C` ahead | without the 8 largest |
|---|---|---|---|---|---|---|---|
| registered (§6) | 8,878 | +0.311% | [+0.228, +0.418] | −0.002% | +0.299% | 48.6% | +0.311% |
| the three net walks only | 9,007 | +0.356% | [+0.283, +0.456] | −0.001% | +0.340% | 48.7% | +0.356% |
| `O` and `C` only | 9,431 | +0.370% | [+0.295, +0.469] | −0.001% | +0.356% | 48.9% | +0.369% |

**The fault worked against `C`.** The 129 entries the anchored stop dropped are ones where the price
had already fallen more than two ATR below the signal close by the fill — mostly by 15:55 — so the
open arm bought before the fall and the close arm after it. Re-admitted, they lift the difference.
**It is not a few names**: the eight largest single differences, up to ±79%, carry 2.8% of the
absolute total, and the mean without them does not move.

**By the open's own spread**, on the two-arm population — the cleanest statement of where it comes
from:

| quintile | open spread | close spread | `C − O` | gross part |
|---|---|---|---|---|
| Q1 | 3.9 bps | 1.9 bps | +0.095% | +0.075% |
| Q2 | 12.3 | 3.3 | +0.188% | +0.109% |
| Q3 | 25.3 | 4.8 | +0.328% | +0.099% |
| Q4 | 45.7 | 5.9 | +0.401% | −0.022% |
| Q5 | 111.7 | 10.6 | **+0.838%** | −0.102% |

The saving climbs with the open's spread in every step. On the widest names the price does drift
against a late entry, by a tenth of a percent, and the spread outweighs it eightfold.

**By how the open arm left**: when `O` hit its target, `C` did 1.10% worse on average; when `O` was
stopped, `C` did 1.79% better; on clock exits, where both arms leave at one price, `C` was ahead by
0.38% with a median of +0.23%. The flips carry the mean; the clock exits show it plainly.

## What this establishes, and what it does not

**Established, on the registered reading:** for the names `CARD-001`'s screen selects, over
2022-09 to 2026-08, buying five minutes before the close of the entry session instead of at the
open earned +0.31% of the money invested per trade, net of each name's own quoted spread — and the
whole of it is the spread.

**Not established:**

* **that the card makes money.** It breaks even at 15:55, [−0.40%, +0.46%] a trade; and nothing here
  compares it with `SPY`, which §20–§23 found no rule here beats.
* **the opening auction.** The open arm is priced as an order meeting the continuous book seconds
  after 09:30 — the print of the 09:30 minute plus the half-spread quoted at 09:30:05, `DR-040`'s
  convention. **An order in the opening auction pays the auction's single price and no quoted
  spread.** Alpaca's `opg` time-in-force guarantees that; whether a `day` order queued overnight —
  what the card sends today (`DR-027` §3.3) — takes part in the auction, Alpaca's order
  documentation does not say. If it does, this study measured the saving against the wrong open,
  and the true saving is smaller. The same holds at the other end: a market-on-close order (`cls`)
  pays the closing auction's price and no spread either.
* **a limit order's fills.** The live order is a day limit at the sizing price (`DR-027` §3.1). Both
  arms here fill at the market, so neither measures the entries a limit would refuse.
* **market impact, fees or fills of real size.** Top of book, four positions.
* **the future.** Four years; survivors only.

## What this licenses

`ACCEPT`: *`CARD-001`'s entries, bought five minutes before the close, earned more per dollar than
at the open, net of their own spreads.* **Changing `entry.method` is the owner's call**, and it is
a new card version (`STRATEGY_CARD_SPEC` §5 rule 2), which resets the card's validation claims —
there are none to reset. It also needs something that does not exist: an order placed during the
session. The card's orders are sent in the evening and wait for the open; a 15:55 entry needs a
pass shortly before the close, which `CONSTRAINTS` §4 records as a build gap since `CHARTER` A-003.

## What it changes

* **`DR-040` §9's question is answered**, on the right population and with each entry's own cost:
  +0.311% where §9 read +0.310% — the same number, now with an interval that does not depend on the
  weighting. §10 is appended there.
* **Every net figure this programme published at the open was charged the most expensive moment of
  the day**, on names that pay about 38 bps a side there. None of §20–§23's verdicts is overturned
  by it — §20's selection effects were differences at the same moment — but every single-stock
  level that entered at the open paid the open's spread, which on this card's names is 0.3% a
  trade more than the same entries at 15:55.
* **The next question is the auction**: an `opg` order at the open, against 15:55, against a `cls`
  order at the close. If the opening auction is as cheap as the close, the saving here is a routing
  choice rather than a clock one — and that is cheaper to adopt.

## What the study cost

39,280 requests to the vendor over six hours overnight — 9,820 minute sessions, 29,460 quote
windows — with one symbol the vendor does not list. The power estimate and the draw took about
half an hour, parity 3 minutes, the run 7. Two trials, 123 → 125.
