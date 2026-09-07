# PR-015 RESULT: no signal earns anything at four positions, and the four positions are why

```
prereg:        PR-015
ran:           2026-09-07
verdict:       INCONCLUSIVE - the only arm whose interval excludes zero is one that LOSES
tool:          tools/run_pr015.py
evidence:      PR-015.json
trials:        5, declared before the run
```

---

## Read this first

**Four of the five signals produced nothing separable from zero, and the fifth reliably lost.**
`LOWVOL_126` is the only arm whose interval excludes zero on the primary window — at **−18.22% a
year** — and it does so on all four cells. §6's both-negative branch fires and the verdict is
`inconclusive`, because comparing a losing arm to a losing universe is not a finding.

**But the verdict is not the result.** The result is what the study measured about the BOOK:

| | the four-name book | the decile it selects from |
|---|---|---|
| `MOM_252_21` across four cells | **+1.57% to +40.72%** | +5.83% to +10.21% |
| `REVERSAL_21` across four cells | **−76.45% to +20.18%** | −0.46% to +7.04% |

Same signal. Same dates. Same universe. **The only difference is how many names it holds** — and
the four-name book's four readings disagree by up to **96.63 points** where the decile's disagree by
**7.50**. The book is not measuring the signal. It is measuring which four names it happened to
hold.

**`risk.max_concurrent_positions` is the binding constraint on this whole family of strategy**, and
that is now measured rather than argued.

## What ran

**10,330 instruments, 454 formation dates**, every one of them carrying at least 100 admitted names
in **both** halves of the split. First usable formation **2017-08-24** — later than `PR-014`'s
2016-08-22, because this study needs 252 sessions of history for every arm (§5: the floor is the
maximum any arm needs, applied once, so a difference between arms is a difference between signals)
and needs it in each half separately.

**Four concurrent positions, each held 20 sessions, entered 5 sessions apart** — amendment A-2, the
owner's correction. `risk.max_concurrent_positions` is 4, `status: owner`. The freed slot takes the
best eligible name not already held.

**The book was full 3.97 times out of four.** Three rebalances per half ran short, and all of them
fall inside the first four — the book filling from empty. **`slots_the_screen_could_not_fill` is
zero in every cell.** A-2 registered that this branch would almost never fire under a top-decile
eligibility screen and that the study would count rather than assume it. It counted; it never fired.

## The numbers

Annualised **net** excess over `rs.benchmark`, long only, four positions, 20-session hold:

| arm | turn/reb | cost/yr | PRIMARY net | interval | n | HOLD-TIME | HOLD-NAMES | decile (gross) |
|---|---|---|---|---|---|---|---|---|
| `PATH_126` | 17.9% | 4.52% | −9.53% | [−31.73, +13.49] | 220 | −10.09% | +2.51% | +3.18% |
| `HIGH_52W` | 23.8% | 5.99% | −17.64% | [−40.34, +5.86] | 220 | −15.17% | −11.56% | −11.36% |
| **`LOWVOL_126`** | 4.2% | 1.06% | **−18.22%** ✗ | **[−32.68, −0.81]** | 220 | **−12.99%** ✗ | **−19.44%** ✗ | −13.92% |
| `MOM_252_21` | 13.5% | 3.41% | +14.62% | [−33.39, +68.85] ⚠ | 220 | +40.72% | +39.26% | +9.75% |
| `REVERSAL_21` | 24.1% | 6.07% | −26.96% | [−72.25, +14.84] ⚠ | 220 | −76.45% | +20.18% | +7.04% |

✗ marks an interval excluding zero with §8's sample rule met. ⚠ marks an interval **wider than §8's
50-point power floor**, where a null is evidence of nothing. `decile` is the whole eligible decile's
gross excess — a diagnostic (A-2), never read by §6.

`holdout_time` has n=233; `holdout_names` n=220.

## The verdict, arrived at by the registered rule

§6 selects **the arm with the largest primary net excess whose interval excludes zero**. Exactly one
arm qualifies — `LOWVOL_126` — and its interval excludes zero **on the losing side**. §6's
both-negative branch then fires: the arm is at −18.22% and the equal-weighted admitted universe is
at −1.55%, so both are below zero and the rule refuses to make a finding out of which loses less.

**`INCONCLUSIVE`.** At 3× costs the selected arm is −20.34%.

The rule is applied by `run_pr015.decide` and the tool prints the branch it took. It is the same
mechanical treatment `PR-014` used, and the reason there is no step here for a reader's judgement
to enter.

## The finding that is not the verdict: four positions cannot carry a cross-sectional signal

```bash
PYTHONPATH=$PWD/src python tools/run_pr015.py --report
```

**How much the four cells disagree**, book against the decile it selects from. The book is net and
the decile is gross, so the LEVELS are not comparable and the **spreads are** — a cost charged to
every cell alike cannot make four cells disagree with each other.

| arm | book: worst → best | spread | decile: worst → best | spread |
|---|---|---|---|---|
| `PATH_126` | −10.09% → +2.51% | 12.60 | −2.75% → +3.18% | 5.93 |
| `HIGH_52W` | −17.64% → −11.56% | 6.09 | −13.01% → −10.12% | 2.89 |
| `LOWVOL_126` | −19.44% → −12.99% | 6.45 | −13.92% → −11.64% | 2.28 |
| **`MOM_252_21`** | **+1.57% → +40.72%** | **39.15** | +5.83% → +10.21% | **4.38** |
| **`REVERSAL_21`** | **−76.45% → +20.18%** | **96.63** | −0.46% → +7.04% | **7.50** |

**Read the last two rows twice.** `MOM_252_21`'s decile earns between +5.83% and +10.21% on all four
cells — four independent readings agreeing within four and a half points. The same signal expressed
in four positions reads +1.57%, +14.62%, +39.26% and +40.72%. **The signal is stable and the book is
not.**

**Cross-sectional ranking is a diversification claim.** It says the top decile drifts up relative to
the pool; it does not say which name will. A four-position book cannot hold that claim — it holds
four draws from a distribution whose mean is the claim and whose variance is everything else. This
study did not set out to measure that and it is the clearest thing in it.

**What it does NOT say.** The decile column is GROSS, carries no interval, and is a diagnostic §6
never reads. It is not evidence that `MOM_252_21` works. It is evidence that the four-position book
would not have shown it either way.

## `LOWVOL_126` is the one thing that replicates, and it loses

The only arm with an interval excluding zero, and it does so **on all four cells**: −18.22%,
−12.99%, −19.44%, −14.09%. Three of those are the registered windows; the fourth is A-1's
diagnostic cell, which agrees.

**It is not a cost artefact.** `LOWVOL_126` is the CHEAPEST arm — 4.2% turnover per rebalance,
1.06% a year — because the calmest name in a cross-section stays the calmest name. Its decile loses
13.92% gross, before any cost at all.

**It is not only a style artefact either.** Against the pool it selected from it is −16.67%, −9.13%
and −17.93%. Picking the calmest names out of this universe is materially worse than picking from
it at random.

**A caveat that matters as much as the number.** 2017–2026 was an extraordinary decade for
mega-cap growth and a poor one for low volatility. This measures that decade. It is not a claim
about low-volatility investing in general and this report does not make one.

## What the power floor caught

§8's floor was registered on 2026-09-07, before any number existed, and it earned its place
immediately.

**`MOM_252_21` and `REVERSAL_21` exceed it on every cell.** `MOM_252_21`'s primary interval is 102.2
points wide; `REVERSAL_21`'s `holdout_time` interval is **202.7 points**. Those are the two arms
with the largest and most quotable point estimates in the study — +40.72% and +39.26% on both of
`MOM_252_21`'s holdouts — and **the instrument could not have distinguished them from zero, or from
each other, or from −20%.**

Without the floor, a reader would find "+40% on both holdouts, replicated" in this table. §6 never
selects those arms, because their primary intervals contain zero — but the floor is what makes the
report say *why* they cannot be read rather than leaving them looking merely unlucky.

**And A-1's fourth cell is what breaks the illusion.** `MOM_252_21` reads +40.72% and +39.26% on the
two registered holdouts and **+1.57%** on the unregistered fourth. Three cells of the same 2×2, and
the one nobody registered disagrees with the other two by 39 points. That cell exists because A-1
required computing a number the rule does not consult; had it been left out on grounds of tidiness,
this report would carry a two-of-two replication instead of a two-of-three.

## My registered prediction, and it was wrong

**On 2026-09-07, before the run, I put on record: *"I expect the primary interval to come back wider
than ±25 points."*** For the arm §6 selected it did not. `LOWVOL_126`'s primary interval is **31.9
points end to end** — ±16 — comfortably inside the floor, and so are `PATH_126`'s (45.2) and
`HIGH_52W`'s (46.2).

**Three of five arms were measurable and two were not.** The prediction was right about
`MOM_252_21` and `REVERSAL_21` and wrong about the study as a whole. The floor was worth registering
anyway — it fired where it mattered — but the blanket claim that four positions cannot be measured
at all is refuted by three arms in this table.

## Two cost readings, and §5 did not disambiguate them

§5 registered both that a position *"reaches the cap and closes"* and that cost comes from
**measured net turnover between consecutive books**. Those disagree in exactly one place: when a
name is re-selected the instant its slot frees. The literal exit costs a round trip; the netted
reading costs nothing.

**The run answers both**, because cost enters as a constant annual subtraction from a bootstrapped
gross interval — the property `attribute_pr014_flip.py` already relies on.

| arm | netted cost | as-if-every-exit-is-an-exit | primary, netted | primary, repriced |
|---|---|---|---|---|
| `PATH_126` | 4.52% | 6.30% | −9.53% | −11.31% |
| `HIGH_52W` | 5.99% | 6.30% | −17.64% | −17.96% |
| `LOWVOL_126` | **1.06%** | 6.30% | −18.22% ✗ | **−23.46%** ✗ |
| `MOM_252_21` | 3.41% | 6.30% | +14.62% | +11.72% |
| `REVERSAL_21` | 6.07% | 6.30% | −26.96% | −27.18% |

**The verdict is identical under both readings**: `INCONCLUSIVE`, `LOWVOL_126`, both-negative. No
arm changes its qualification. So the ambiguity is moot for the decision and material for the
interpretation, which is the honest way to report it rather than picking one after the fact.

**What it is material for: the holding period the study actually delivered.**

| arm | turnover/rebalance | realised hold |
|---|---|---|
| `PATH_126` | 17.9% | 28 sessions |
| `HIGH_52W` | 23.8% | 21 sessions |
| **`LOWVOL_126`** | **4.2%** | **119 sessions** |
| `MOM_252_21` | 13.5% | 37 sessions |
| `REVERSAL_21` | 24.1% | 21 sessions |

§5 said *"20 sessions, fixed"*. Under the netted reading it delivered 21 to 119, because a name
re-selected the moment its slot frees is never sold. **`LOWVOL_126`'s "20-session hold" is a
119-session hold**, and its cheapness is the same fact stated twice. Under the repriced reading the
hold is 20 for every arm and every arm pays 6.30%. **A future study should register which of the two
it means.**

## The benchmark carries less blame here than expected

`rs.benchmark` is `SPY`, `status: assumed`, and `benchmark-fit-2026-09-06` measured this universe
losing 3.02% a year to it as a style gap. At this horizon and window the gap is smaller: the
equal-weighted admitted pool runs **−1.55%**, **−3.87%** and **−1.51%** against `SPY` on the three
registered windows.

So the benchmark is not what sank these arms. Against the pool they selected from, `HIGH_52W` and
`LOWVOL_126` still lose by 9 to 18 points, and `PATH_126` by 6 to 8 on two of three windows.

## What it costs the programme

**Five trials, declared before the run.** The total moves **90 → 95** and the hurdle **2.49 → 2.51
sd(SR)**. Derive both with `tools/trial_budget.py`; the figures are here because a report has to
say what it spent.

## What this says for the owner's question

The question was a good long-only strategy at a 14–20 session hold. **This study answers it for five
signals and the answer is no** — and it identifies the reason, which is worth more than the answer.

* **No signal earns a net excess that excludes zero on the upside**, at any of the three registered
  windows, under either cost reading.
* **The signal that looks best is the one that cannot be measured.** `MOM_252_21`'s decile is
  consistently +5.83% to +10.21% gross across four cells; its four-name book is unmeasurable.
* **The constraint is the book, not the horizon and not (on this evidence) the signal.**
  `risk.max_concurrent_positions` is a ratified `owner` parameter. Changing it is the owner's call
  and it is not a small one — it changes position sizing, `risk.max_open_risk`, and creates a new
  `CARD-001` version that resets any validation claim (`STRATEGY_CARD_SPEC` 5 rule 2).

**What I would ask next, and it is one study rather than five:** does `MOM_252_21`'s decile edge
survive an interval, a cost and a holdout on a book large enough to hold it? That needs the decile's
per-period series, which this run did not store — a defect in this tool, recorded in `TODO.md` §5.
It spends no new trials on the signal side; it does need a registered position count, and that is
the owner's number.

## Reproducing

```bash
PYTHONPATH=$PWD/src python tools/run_pr015.py --data <store>
PYTHONPATH=$PWD/src python tools/run_pr015.py --report
```

Every per-period series of the four-position book is committed in `PR-015.json`, so any interval
here can be re-tested at another block length without a re-run. The decile diagnostic's series is
**not** stored and that is the gap named above.

`--report` was added to the tool after the run and reads the committed result; it touches no store,
re-estimates nothing, and decides nothing. `AGENTS.md` §10.6 rule 4 is why the book-against-its-pool
figures, the four-cell spreads, the realised holds and the reprice are computed there rather than
typed onto this page.
