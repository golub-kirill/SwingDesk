# PR-039 RESULT: a hold through a results announcement exits through a gap four times as often — and on average costs nothing

```
prereg:        PR-039
ran:           2026-09-26
verdict:       ACCEPT, branch RISK_ONLY. Holds that span an announcement exit THROUGH the stop at
               16.0% against 3.9% for holds that do not: +12.1 points [+5.5, +19.5], wholly above
               zero and past the minimum detectable 5.7. Their mean net R is -0.026 against
               -0.061: +0.036R [-0.247, +0.294], which contains zero - the cost side cannot tell
               them apart
status:        final. Run once, from the registration commit d00377d, over committed files
tool:          tools/run_pr039.py; calendar from tools/fetch_earnings_dates.py (SEC EDGAR)
evidence:      PR-039.json; PR-039-announcements.csv; PR-039-coverage.csv; PR-039-power.json;
               PR-016-trades-sample.csv (committed with PR-016)
trials:        1. The filter - leave out every hold that spans an announcement - is a
               configuration evaluated on the data. 166 -> 167
```

---

## Read this first

**The owner asked how much of `CARD-001`'s losses fall on results announcements.** On the card's
own arm — `PR-016`'s four-name book, 400 sampled trades — the answer is:

| `CARD-001` (`ranked_top4`) | trades | share of trades | loss in R | **share of all loss** | exits through a gap |
|---|---|---|---|---|---|
| held through an announcement | 28 | 7.0% | 21.5 | **10.2%** | 3 |
| a company, no announcement in the hold | 234 | 58.5% | 120.7 | 57.4% | 9 |
| a fund (no results to announce) | 113 | 28.3% | 57.3 | 27.2% | 8 |
| results undatable (a foreign issuer on Form 6-K) | 25 | 6.3% | 10.8 | 5.1% | 3 |

**A tenth of the card's loss, from 7% of its trades.** That is the descriptive answer, and 28
trades are far too few to decide anything on their own — which is why the registered question was
asked of all four one-times-cost arms together, where 144 holds spanned an announcement.

**What the pool says, and it is two statements that point in different directions:**

1. **The tail is real.** A hold through an announcement exits through a gap **four times as
   often**: 23 of 144 (16.0%) against 35 of 903 (3.9%). A gap is the loss the stop cannot bound —
   `EVIDENCE_SUMMARY` §17.2 puts it at −1.56R against −1.03R for an ordinary stop — so these are
   the trades whose realised loss is not the 1R every cap and the kill switch are written in.
2. **The average is not worse.** Exposed holds averaged −0.026R, unexposed −0.061R. The
   difference, +0.036R, is inside an interval half a unit of R wide. **The literature said this
   would happen** (`TODO.md`'s search, 2026-08-30): prices rise around scheduled announcements on
   average — the announcement premium — so the holds that eat the gaps are also the holds that
   collect it. Here the two roughly cancel.

**So a filter would buy a thinner tail and nothing else.** Leaving the exposed holds out moves the
book's mean from −0.056R to −0.061R — a hair worse, and far inside what this sample can see.

## §9, as registered, shown first

| check | registered | measured | |
|---|---|---|---|
| intraday share of announcements since 2017 | under 20% | **4.6%** of 37,865 | pass — the acceptance instant tracks the release |
| median announcements per company a year | 3 or more | **4.06** | pass — the calendar is not thin |
| realised half-width against §3's 0.040 | between half and twice | **0.070**, 1.75 times | pass, and wider than predicted |

**The width is the one thing the prediction got wrong**, and it stays inside the registered band.
*Conjecture, not checked (`AGENTS.md` §10.4):* the permuted-label estimate spread exposure over
months at random, while real announcements cluster in reporting seasons, so a month-block
bootstrap moves more of them together.

## The registered reading

| | exposed | unexposed | difference | 95% interval |
|---|---|---|---|---|
| **exits through a gap** (primary) | **16.0%** | **3.9%** | **+12.1 points** | **[+5.5, +19.5]** |
| mean net R (the cost side) | −0.026 | −0.061 | +0.036 | [−0.247, +0.294] |

**§3 predicted exposed about 20%, unexposed about 7%, +13 points.** Realised: 16.0%, 3.9%, +12.1.
The level was lower on both sides and the difference landed a point away. **The cost side was
predicted at about −0.10R and inside the band**; it came out +0.036R, inside the band, and the
opposite sign — which is the announcement premium doing what the literature says it does, not
something this sample can separate from zero.

## Where the loss sits across the whole pool

| pool (1,591 distinct trades) | trades | share | share of all loss | exits through a gap |
|---|---|---|---|---|
| held through an announcement | 144 | 9.1% | 10.1% | 23 |
| a company, no announcement in the hold | 903 | 56.8% | 51.7% | 35 |
| a fund | 389 | 24.5% | 27.8% | 43 |
| undatable | 155 | 9.7% | 10.5% | 22 |

**Funds gap too** — 43 of 389, 11.1%, more often than unexposed companies. A fund has no
announcement, so its gaps are the market's own overnight moves; they are outside this study's
question and are recorded here so nobody reads "avoid announcements" as "avoid gaps".

## What this licenses — and what it does not

**Licensed, in §6's own sentence:** *an announcement inside the hold is a measured source of losses
beyond 1R.* The owner may set `screen.earnings_buffer_days` as `assumed`, citing `PR-039`, as tail
control: long enough that a planned hold never spans a known announcement.

**Not licensed:**

* **an expectancy argument for the filter.** The mean does not move, and the cost side cannot see
  anything under 0.28R a trade;
* **a live filter without a forward calendar.** EDGAR records announcements after they happen. A
  rule that must know the NEXT announcement date needs a source of scheduled dates, and none is
  built — that is a separate decision and a separate piece of work;
* **anything about `CARD-001`'s edge.** Its source has not passed its own test
  (`RETURN_SOURCE_REGISTER` §2.1); a filter on a strategy with no measured edge trims its tail and
  nothing more.

## What was built to get here

* `tools/fetch_earnings_dates.py` — the Item 2.02 calendar from SEC EDGAR, paced under the
  fair-access policy, with the store's own ETF flags. **One defect found before registering**:
  SEC spells a share class with a hyphen and the store with a dot, so `BRK.B`, `BF.B`, `HEI.A` and
  `MOG.A` first read as unknown.
* `tools/run_pr039.py` — the exposure rule, the buckets and the bootstrap; `tests/test_run_pr039.py`
  covers them, among them acceptance instants in every slot, an early close and both sides of the
  winter open.
