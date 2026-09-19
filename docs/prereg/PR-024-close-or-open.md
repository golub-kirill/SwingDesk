# PREREG: does CARD-001 earn more per dollar entering five minutes before the close than at the open?

```
id:            PR-024
date:          2026-09-16
author:        Claude, on the owner's choice of 2026-09-16. Asked "Начинаем с переноса исполнения
               на конец сессии?", the owner answered "Да, начать с этого" - the first study after
               CHARTER A-003 reopened research (EVIDENCE_SUMMARY §24). Owed by DR-040 §9.4
status:        reported   (2026-09-17 - results/PR-024-report.md)
verdict:       ACCEPT, against section 3's prediction - entering at 15:55 instead of the open
               earned +0.311% per dollar a trade [+0.228, +0.418] on 8,878 entries, net of each
               name's own spread; cost-adverse +0.200%. All of it the spread: the gross part is
               -0.016% [-0.105, +0.090]. At 15:55 the card itself earns +0.024% [-0.396, +0.456]
```

---

## 0. Refutation-family check

**searched:** every reported study in `docs/prereg/`, every committed measurement in
`docs/decisions/measurements/`, `EVIDENCE_SUMMARY.md`, and `DR-040`. The censuses live in
`HANDOFF.md` §2 and are not restated here (`AGENTS.md` §10.5).

**found:**

| prior work | what it asked | verdict |
|---|---|---|
| `DR-040` §1–§5 | the quoted SIP spread by time of day, across the admitted universe | median half-spread **21.9–30.2 bps at 09:30 against 1.9–4.0 bps at 15:55**, by year |
| `DR-040` §9, exploratory, 3 trials | the same entry priced at 09:30, 11:00 and 15:30, 60 instruments, 6,176 pairs | net **+0.311% ±0.246** at 11:00 and **+0.310% ±0.314** at 15:30; **+0.049%** when dates are weighted equally. §9.2–§9.4 say why it settles nothing |
| `PR-016` | `CARD-001`'s screen under the ratified exit, entered at the open | `ACCEPT`, preliminary — the screen loses less (−0.100R a trade against −0.192R); both arms lose |

**distinct because it replaces exactly the three things `DR-040` §9 said it got wrong:**

* **the population.** §9 drew from the admitted universe. This draws from `CARD-001`'s own
  selection — `run_pr016`'s ranked rule, scored by the same streamed code.
* **the cost term.** §9 charged every entry the difference between two MEDIAN spreads of the whole
  universe, from a distribution with a p10 of 3 bps and a p90 of 114. Here every entry pays **its own
  name's quoted spread at the moment it entered**, read from SIP quotes stored for this study.
* **the weighting.** §9's answer flipped from +0.310% to +0.049% when dates were weighted equally.
  Here every date carries the same number of names, so the two weightings agree up to exclusions,
  and both are reported.

**What is known in advance, stated first.** The author wrote `DR-040` §9 and knows its numbers:
the gross decay from the open to 15:30 on the admitted universe (−0.138% ±0.314) and the saving the
median spreads implied (+0.449%). The author also knows `PR-016`'s trade-level results at the open.
No file here holds this study's population priced at any moment other than the daily open, nor any
of its quotes; the power estimate below read daily bars and widths only.

## 1. Question

Over the last 48 months, does an entry `CARD-001` selects, bought at **15:55 on the entry session**
instead of at its **09:30 open**, and exited under the ratified policy, earn more per dollar
invested, net of the spread its own name was quoted at when it traded?

## 2. Hypothesis

**H1.** The per-entry difference `C − O` in net return per dollar has a 95% interval wholly above
zero.

**H0.** It does not.

**A second arm, registered and counted, never carrying the verdict:** `T`, the same entry at 11:00.
`DR-040` §9 read its narrowest interval there, so it is measured beside `C` and reported with its
own branch — and never replaces `C`'s.

It concerns `CARD-001` version 1's `entry.method`, which is the open today. Nothing is changed by
this study; §6 says what each outcome licenses, and changing the card is the owner's.

## 3. Prediction, stated numerically before the run

```
primary quantity:  mean over entries of [net per dollar (C) - net per dollar (O)], same entry,
                   same ratified exit, month-clustered bootstrap, 48 months to the snapshot
predicted:         NULL or INCONCLUSIVE - a difference near zero. Two forces, both measured
                   elsewhere and neither on this population: the entry spread saved (its own open
                   half-spread less its own close half-spread; for liquid decile names nearer the
                   universe's p10 of 3 bps than its median of 26), against the drift a later entry
                   pays for (-0.138% on the universe). Under the engine's convention the stop and
                   the target move with each arm's own fill, so at those exits most of the entry
                   difference comes back out; only clock and gap exits keep it all. Centre of the
                   prediction: -0.10% to +0.10%
if H1 were TRUE:   C's interval wholly above zero - a difference above about +0.15 points,
                   and +0.21 to be found four times in five
minimum detectable effect:  0.21 points per dollar (0.0021) - the difference the registered sample
                   detects with 80% power even at the lowest complete share section 8 admits: its
                   predicted half-width at 90% complete, 0.146 points, x (1.96 + 0.84) / 1.96. From
                   tools/power_pr024.py (PR-024-power.json): the between-date and within-date
                   dispersion of the same walk on daily-bar proxies over 60 pilot dates, plus a
                   bound on the entry spread's own dispersion. Widths only; nothing is held out
power floor:       0.30 points end to end on the difference (0.0030 per dollar); it gates NULL only
```

```bash
PYTHONPATH=$PWD/src python tools/power_pr024.py --report
```

| sample | half-width | at 90% complete | requests | readable at the floor |
|---|---|---|---|---|
| 500 dates × 6 | 0.221 | 0.233 | 12,000 | no |
| 750 dates × 10 | 0.158 | 0.167 | 30,000 | no |
| every session × 8 | 0.146 | 0.154 | 31,424 | no |
| **every session × 10** | **0.138** | **0.146** | **39,280** | **yes — the draw** |
| every session × 12 | 0.133 | 0.140 | 47,136 | yes |

Half-widths in points per dollar. **What sets them:** the pilot's per-date averages spread by
**1.63%** and names around their own date's average by **4.69%**, against **0.43%** for the entry
spread itself (the widest opening-window p10–p90 range in `DR-040`'s rows, read as a normal
spread). The second is the move from the open to the close of the entry session, which a clock exit
keeps whole; it is why ten names a date are needed, and the first is why only every date will do —
a round 1,000 sits past the window's **982** sessions. The formula reproduced the pilot's own
month-clustered bootstrap at **0.878** of its width.

**The grid was widened after its first run, and it read widths only.** That run stopped at 1,000
dates and ten names and judged readability with every entry priced; it found nothing readable
inside the calendar. The last row, every formation session, and a twelve-name column were added, and
readability now allows for the 10% of the draw §8 lets go unpriced.

**Why per dollar and not in R.** `CHARTER` A-003 §2 names the unit. Both arms risk the same
2 × ATR a share, so R divides each entry's difference by its own name's volatility and a quiet
name's saving counts for more than a volatile one's; per dollar weighs each entry by what it cost.
The difference in R is reported beside it and never read.

## 4. Data

```
bars:          the owner's daily store, copied read-only to a scratchpad on 2026-09-16 after the
               evening pass finished; knowledge_time 2026-09-16T19:30:10.930516-05:00
minutes:       Alpaca SIP one-minute bars (adjustment=split, regular hours) for every drawn entry
               session, fetched by tools/fetch_minutes.py into a scratchpad MinuteStore; an entry
               whose minutes do not reproduce its daily bar is excluded, and counted
quotes:        Alpaca SIP NBBO, the first 25 quotes at 09:30:05, 11:00:00 and 15:55:00 (12:55 on a
               half day) of every drawn entry session, fetched by tools/fetch_entry_quotes.py into a
               scratchpad QuoteStore. Both stores' fetch instants are recorded with the result
universe:      CARD-001's selection - run_pr016's ranked rule: ByMarketPathStrength over 126
               sessions against SPY, the top decile of the names admitted that day, a date with
               fewer than 100 admitted names skipped. Admission is PR-016's pinned rule - price
               5.00, 20-session ADTV 5,000,000, 250 sessions of history - with an ADTV lag of 0
               where the live registry's universe.adtv_lag_sessions is 3 (DR-017). Kept, so that O
               is PR-016's configuration; the lag moves which names are admitted by three sessions
               of volume, and it moves them identically in all three arms
window:        the last 48 months before the snapshot's latest session, 2022-09-16 .. 2026-09-16:
               982 formation sessions, 2022-09-16 to 2026-08-17 - the last one early enough for a
               full 20-session hold - and entries from 2022-09-19 to 2026-08-18. The 48-month
               default (AGENTS.md 19), so no window rationale is owed
country:       USA - US-listed names on US venues
survivorship:  present. The store holds names that still trade, which lifts both arms' levels;
               the difference is a same-name, same-day comparison and is exposed only through
               which names are drawn
costs:         commission 0 (DR-039). Entry at the arm's own measured half-spread,
               (ask - bid) / mid / 2, the median over the window's two-sided quotes; a window whose
               first quote arrives more than 60 s after its instant, or with no two-sided quote,
               excludes the entry.
               Exits at the same name's ENTRY-session half-spread matched to the exit's moment: a gap
               through the stop at 09:30, an intraday stop or target at 11:00, a clock exit at 15:55.
               Regulatory fees excluded - they are proportional to the sale, which is nearly the
               same in all three arms
```

## 5. Method

* **The sample.** Every session of the window is a formation date. `D` of them are drawn with seed
  20260916, and on each, `k` of the date's selected names with seed `20260916 + date.toordinal()`,
  so no date's draw depends on another's (`D` and `k` below, from the power estimate). The draw reads
  only what was known at each signal and is committed with this registration as
  `results/PR-024-sample.jsonl`, before any minute or quote is fetched.
* **The arms.** Signal on session T, entry on T+1. `O` fills at the open of the 09:30 minute; `C`
  at the open of the minute starting at 15:55 (12:55 on a half day); `T` at 11:00. A fill minute
  that does not start within five minutes of its instant excludes the entry. All three prices come
  from the same Alpaca minute basis.
* **The walk.** Each arm is walked exactly as `engine.run_arm` walks a position — stop at the fill
  less 2 × ATR(14) at T, target 1R above the fill, 20 sessions, `DR-042`'s minute tie-break for an
  ambiguous bar — with one difference that is the point of the study: **the entry session is read
  only from the regular-hours minutes at or after each arm's own fill.** From T+2 the daily bars take
  over. `tools/run_pr024.py --parity` proves the walk is the engine: priced at the daily open with
  `PR-016`'s costs, it must equal `run_arm` trade for trade.
* **The statistic.** Per entry, `C`'s net return per dollar minus `O`'s. Its mean, and a 95%
  moving-block bootstrap over ENTRY MONTHS, block 3, 10,000 resamples, seed 20260916
  (`run_pr016.block_bootstrap`). Beside it and read by §6: `C`'s own net per dollar with the same
  interval, and the `cost_adverse` reading.

### 5a. The split, and what it buys

```
split:           none
split buys:      nothing is selected - two moments fixed here and one baseline, each read, none
                 chosen - and the rule the entries come from was already split by PR-016. Pairing
                 removes the market's level; the month-clustered interval and the date-equal
                 reading are the protections a split would have bought (PREREG_TEMPLATE 7)
perturbations:   cost_adverse - C at 3x its own spread, O at 1x, every exit at its own 09:30
                   spread; section 6 reads it on an ACCEPT
                 exits_at_registry - every exit at DR-005's 25 bps, PR-016's convention
                 anchored_stop - stop and target placed from the SIGNAL close, as the live bracket
                   places them (DR-027 §3), so the entry saving is not handed back at the legs
                 instrument_clustered - an iid bootstrap over names; DR-040 §9.2's second dependence
                 date_weighted - each date's mean, then months
```

**Diagnostics, printed and never read by §6:** the gross and cost parts of the difference; the
difference in R; each arm's exit reasons and entry spreads; the tie-breaks the walk asked; every
exclusion by reason.

## 6. Decision rule

**For `C`, by `run_pr024.branch_for`, in this order:**

1. `REFUSED` — fewer than 90% of drawn entries complete, fewer than 1,000 pairs, or fewer than 24
   entry months.
2. `BOTH_NEGATIVE` — the difference's interval wholly above zero AND `C`'s own net per dollar wholly
   below it. A cheaper way to lose is not a finding.
3. `COST_FRAGILE` — wholly above zero and the `cost_adverse` difference not above zero.
4. `ACCEPT` — wholly above zero.
5. `REJECT` — wholly below zero.
6. `INCONCLUSIVE` — containing zero and wider than the 0.30-point floor.
7. `NULL` — containing zero and inside the floor.

**The study's `verdict:` is `C`'s.** `T`'s branch is reported beside it and never replaces it.
`NULL`, `BOTH_NEGATIVE` and `COST_FRAGILE` are reported under `inconclusive` with the branch named.

**What each licenses — one sentence, and no parameter:**

* `ACCEPT` — *`CARD-001`'s entries, bought five minutes before the close, earned more per dollar than
  at the open, net of their own spreads.* Changing `entry.method` is a new card version and the
  owner's call.
* `REJECT` — *entering near the close cost more than it saved; the open is the better moment for
  this card.*
* `NULL` — *the moment does not matter for this card within ±0.15 points per entry*, so the open's
  spread is not what makes it lose.
* `INCONCLUSIVE` — *not established at this width.*

## 6a. Trials

**Two** — `C` and `T`. `O` is `PR-016`'s configuration priced on minutes and is already counted. The
tool derives the cumulative figure: it read **123** before this registration; two more take it to
**125** and the hurdle from **2.603 to 2.608** sd(SR).

```bash
PYTHONPATH=$PWD/src python tools/trial_budget.py
```

**Registered as NOT run:** entering at 15:55 on the SIGNAL session itself (it needs the decision
before the close it is computed from); a market-on-close or limit order; VWAP or TWAP execution;
moving the exits to another moment; any other moment, sample size or seed. Each is another
configuration.

## 7. Stopping rule

One draw, committed with this registration. One fetch of minutes and quotes, repeated only to fill
windows that failed, never to replace one that was served. One run at pinned knowledge instants for
all three stores. No moment, arm, window, cost or weighting is tried after the first result is seen.

## 8. Sample

```
minimum:       1,000 complete pairs across at least 24 entry months, and 90% of drawn entries
               complete - below that, the exclusions (halts, late openings, names that did not
               print: news days) are large enough to be the result
power floor:   0.30 points end to end on the difference, gating NULL only
if not met:    report the measurement and REFUSE to read it as evidence
```

The registered draw is **every one of the 982 formation sessions × 10 names = 9,820 entries**, no
date too thin to draw from, **2,348 distinct names** (`results/PR-024-sample.jsonl`). They are the
card's own picks, leveraged funds included — the screen admits them, and per dollar weighs them by
what they cost rather than by their R.

## 9. What would refute this

**H1 is refuted** by `REJECT` or `NULL`.

**What would refute the STUDY rather than the hypothesis**, and the report shows it first:

* any `--parity` mismatch — the walk and the engine must agree on every drawn entry at the daily
  open;
* a realised half-width outside half to twice the predicted 0.138 points. The pilot has about one
  date a month, so it cannot see dates within a month moving together; `PR-019b`'s estimate missed
  by 1.69× for a cousin of that reason, and this one says where it could miss before it runs;
* an arm filled before its instant, or an entry-session exit priced from a minute before its fill;
* minutes that do not reproduce their bar on more than a tenth of the drawn entries.

**What would NOT settle anything:** an `ACCEPT` read as *the card now makes money*. The difference
is the moment; `BOTH_NEGATIVE` exists because the card may lose at either.

**What neither arm measures.** The live order is a day LIMIT at the sizing price (`DR-027` §3.1),
which does not fill when the market has moved past it. Both arms here fill at the market, so the
entries a limit would refuse are in both — at the open, a gap up; near the close, a day's drift.
Which moment the limit refuses more often is a second question, and it is not this one.

## 10. Amendments

None.
