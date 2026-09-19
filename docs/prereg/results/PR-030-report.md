# PR-030 RESULT: a limit-on-open earns +0.12% a signal over today's day limit — not established; a day limit that also joins the cross earns +0.145%, and that interval is clear of zero

```
prereg:        PR-030
ran:           2026-09-19
verdict:       INCONCLUSIVE, as §3 put near even odds. G - D, the limit-on-open less today's day
               limit, +0.123% per drawn entry [-0.075, +0.305], 0.38 wide against a predicted 0.37
status:        final. The verdict and every cell were computed as registered; amendment A-1
               (made after the run) corrected one §9 check that checked nothing and added one
               diagnostic, and a second run reproduced the first to the digit
tool:          tools/run_pr030.py
evidence:      PR-030.json, PR-030-qa-sample.csv; PR-024's draw, PR-025's stores at their instants
trials:        3, declared before the run (D, G, J)
```

---

## Read this first

**Changing today's order to a limit-on-open is worth about +0.12% a signal, and that is not
established.** Every drawn entry counts, and an order that never fills earns 0. The limit-on-open
(`G`) earned **+0.123%** more than the card's day limit (`D`), with an interval from −0.075% to
+0.305%. Most of that is the spread saved where today's order meets the ask at the open. The rest
is what the day limit loses on the entries it only catches later in the day.

**The order that clearly wins is one the registration counted and did not read.** `J` is a limit
at the signal close that joins the opening cross when the cross is under the limit, and otherwise
rests at the limit for the rest of the day. It earned **+0.145%** a signal more than today's order,
**[+0.119, +0.174]**. It keeps the auction's saving on the entries the auction takes and the day
limit's cheap fills on the rest. It is a secondary reading, so it is reported and never read.

**None of the four orders makes the card money.** Per drawn entry, each order's own net is:
`G` +0.074% [−0.137, +0.273], `J` +0.095% [−0.260, +0.457], `M` +0.001% [−0.413, +0.424]. Today's
`D` comes out at about −0.05% by subtraction. That is break-even, as `PR-024` and `PR-025` found.

## §9, as registered, shown first

| check | registered | realised |
|---|---|---|
| `M` against `PR-025`'s `A` QA rows | no row may differ | **none checked as registered.** The check asked `M` for the fill `"M"` where its fills are `crossed`. Corrected (A-1): **400 of 400**, 0 differ |
| a marketable `D` against `PR-024`'s `O` QA rows | no row may differ | **126 checked, 0 differ.** 205 rows are entries where `D` was not marketable; 69 are entries it missed |
| realised half-width against the predicted 0.185 | half to twice | **0.190**, 1.03× |
| `D`'s split against `DR-040` §4's 50.6 / 32.8 / 16.6 | within 15 points on each part | **FAILED:** 31.0 / 50.5 / 18.5, marketable 19.6 points low and resting 17.7 high |
| entries with no opening cross flagged | under a tenth | **67 of 9,820**, 0.7% |

**Why the split check failed, measured after the run (A-1).** `DR-040` §4 called an order marketable
when the open PRINTED at or under the limit. This study calls it marketable only when the ASK is,
which is the print plus the name's own half-spread, 37.8 bps on average for these names. The same
entries classed by `DR-040`'s own test split **47.2 / 34.3 / 18.4**, within 3.4 points of its numbers
on every part. So the order is simulated as `DR-040` counted it. The gap is the spread: **1,590
entries** (16.5%) printed under the limit at the open while their ask stood above it. The registered
tolerance did not allow for the definition the study itself chose, and this is recorded as a check
that failed, not one that passed.

## The readings

| per drawn entry, missed = 0 | estimate | 95% interval |
|---|---|---|
| **`G − D`, limit-on-open less today's day limit (net)** | **+0.123%** | **[−0.075, +0.305]** |
| gross | −0.023% | [−0.215, +0.140] |
| cost-adverse (a crossed fill charged 15:55's spread, exits at the open's) | +0.201% | [+0.007, +0.372] |
| `G`'s own net | +0.074% | [−0.137, +0.273] |
| **`J − D`, a day limit that joins the cross** (counted, never read) | **+0.145%** | **[+0.119, +0.174]** |
| `M − D`, a market-on-open (counted, never read) | +0.049% | [−0.031, +0.138] |

9,431 complete `G − D` pairs over 48 months (96.0%). Before any order, 116 entries' minutes did not
reproduce their bar and 1 had none.

**How each order fared** (of the entries each one reached):

| | at the open | rested, filled later | never filled |
|---|---|---|---|
| `D`, today's day limit | 2,991 (31.0%) marketable | 4,869 (50.5%) | 1,780 (18.5%) |
| `G`, limit-on-open | 4,531 (47.1%) crossed | — | 5,089 (52.9%) |
| `J`, joins the cross | 4,531 (47.1%) crossed | 3,319 (34.5%) | 1,770 (18.4%) |
| `M`, market-on-open | 9,620 (100%) crossed | — | — |

## Where the difference comes from

`G − D`, `M − D` and `J − D` split by how today's order fared. Each group's mean difference, and
its share of the reading:

| today's order was | entries | `G − D` | `M − D` | `J − D` |
|---|---|---|---|---|
| marketable at the open | 2,939 | +0.313%, share **+0.097** | +0.304%, share +0.095 | +0.311%, share +0.097 |
| resting, filled later | 4,733 | +0.052%, share +0.026 | **−0.401%**, share −0.202 | +0.095%, share +0.048 |
| never filled | 1,759 | 0, share 0 | **+0.840%**, share +0.155 | 0, share 0 |

Three things read off this table, as description:

* **The spread is the whole of the marketable part.** Where today's order meets the ask, every
  auction order saves about 0.31% an entry. That is `PR-024`'s and `PR-025`'s number, found here a
  third time.
* **The resting fills are cheap, and the auction gives them up.** On the entries where today's
  order waits and fills at the limit later, the market-on-open paid the cross and did 0.40% an entry
  worse. The limit-on-open passes on them, and does 0.05% better than holding them.
* **The entries today's order never gets are the best ones.** The market-on-open bought the names
  that opened above the limit and never came back, and made 0.84% an entry on them. These are the
  card's strongest momentum days, and any limit at the signal close misses them. That cost is the
  limit's, not any route's, and it shows in all four orders' own nets.

## What this establishes, and what it does not

**Established:** on the card's entries over 2022-09..2026-08, a limit-on-open at the signal close
cannot be told apart from today's day limit at a 0.38 width. Before costs the two are the same
(−0.023%). A day limit that also takes the cross, `J`, earned more than today's order on 48 months
of entries, but as a reading the registration never read.

**Not established:**

* **what today's live order actually is.** Whether a `day` order queued overnight joins the opening
  cross at Alpaca is not documented. If it does, today's order already is `J`, and the saving
  measured here is already being taken. The paper account's fills are simulated, so they cannot
  say.
* **that `J` can be built as it is priced here.** `J` needs an `opg` limit sent in the evening,
  which Alpaca accepts only between 19:00 and 09:28 ET. This project keeps 18:30-20:00 CT
  (19:30-21:00 ET) for its evening runs, which is inside that window. If the cross does not take it, `J` also needs a day limit
  sent after the open, and no pass runs then. And a bracket is accepted only as `day` or `gtc`, so an
  `opg` entry cannot carry the stop `DR-027` §3.2 requires from the moment of the fill.
* **that the card makes money.** It does not, whichever order carries it.

## What it changes

* **No change is proposed to `DR-027`.** The registered reading did not establish `G`. The order
  that clearly wins, `J`, is secondary, and building it means an unprotected minute and a pass that
  does not exist.
* **The limit costs more than the route.** A limit at the signal close misses 18% of entries, and
  those were the best trades. That is the next thing worth measuring about the card's entry,
  and a question for the owner.

## What the study cost

No fetch; two runs of seven minutes, the second only to correct a check. Three trials.
