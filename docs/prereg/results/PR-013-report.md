# PR-013 RESULT: the sample rule was met, and the ordering carries nothing measurable before costs

```
prereg:     PR-013 (registered 2026-08-24)
status:     reported
run:        2026-08-24
verdict:    INCONCLUSIVE by the registered rule - and it understates what was measured
data:       PR-013.json
trials:     3 configurations, spent
```

---

**EXPLORATORY by declaration** (`PR-013` §0b, written before the run). This advances no validation
status and sets no parameter. It exists to decide whether a confirmatory trial is worth spending.

Derive every figure with `python tools/run_pr013.py --data <store>`, never from this line.

## What the study was for, and the one thing it fixed

`PR-012` asked whether a four-position book ranked by relative strength beats one ranked by
momentum, and **refused a verdict**: four concurrent positions held at most twenty sessions produce
about fifty entries a year, so its holdout supplied 181–203 trades against its own 200 minimum.

The owner's constraint on 2026-08-24 made that permanent rather than unlucky: **six months is 126
trading sessions, which at those caps is twenty-five live trades against a ratified floor of one
hundred.** Waiting for evidence and waiting for the caps to change are the same wait.

So this study moved the question off the book and onto the signal, and **the sample rule was met**:
142 holdout formation dates against a minimum of 100, fixed in §8 before the run.

**What bought the sample was the horizon, not the unit.** Ranking names rather than trades does not
by itself add information — every name ranked on one date shares that date's market move, so a
cross-section is ONE observation. What five-session formation gives is five times as many
independent dates as a twenty-session holding period permits trades to be opened. That correction
was made while designing and is recorded in the runner, because the intuition it replaces — *more
names means more sample* — is wrong and attractive.

## What ran

| | |
|---|---|
| Snapshot | `2026-08-24T07:15:39-05:00` |
| Names read | 1,140 · classified into a sector: 1,013 |
| Window | 2017-02-22 → 2026-08-21, 2,388 sessions — **inherited from `PR-012`**, not chosen |
| Formation dates | 478 non-overlapping, every 5th session · **26 dropped** as too thin to decile |
| Holdout from | 2023-10-12 — **inherited from `PR-012`**, not chosen |
| Lookback | 126 sessions — **inherited from `PR-012`**, so no lookback was searched |
| Arms | market path, sector, and raw return as the control |
| Trials | **3** |

Admission was evaluated **at each formation date's own bar index** (amendment A-2), which removes
the look-ahead `PR-012` carried by admitting once at the snapshot and using that set throughout.

## The numbers

Spread = mean forward 5-session return of the top decile minus the bottom decile, averaged over
formation dates, 95% percentile bootstrap resampling **dates** (10,000 resamples, seed 20260824).
Net subtracts one constant per formation date: four sides at 25 bps. Commission is excluded and the
omission biases every net figure **upward** (amendment A-1).

| arm | period | dates | mean gross | 95% CI (gross) | mean net | 95% CI (net) | net @3× cost |
|---|---|---:|---:|---|---:|---|---:|
| MOMENTUM | primary | 310 | +0.000889 | [−0.003300, +0.005004] | −0.009111 | [−0.013300, −0.004996] | −0.029111 |
| MOMENTUM | holdout | 142 | +0.002062 | [−0.003054, +0.006994] | −0.007938 | [−0.013054, −0.003006] | −0.027938 |
| MARKET | primary | 310 | +0.000750 | [−0.001957, +0.003351] | −0.009250 | [−0.011957, −0.006649] | −0.029250 |
| MARKET | holdout | 142 | +0.002405 | [−0.001476, +0.006066] | −0.007595 | [−0.011476, −0.003934] | −0.027595 |
| SECTOR | primary | 310 | −0.000187 | [−0.003661, +0.003196] | −0.010187 | [−0.013661, −0.006804] | −0.030187 |
| SECTOR | holdout | 142 | +0.001862 | [−0.003277, +0.006726] | −0.008138 | [−0.013277, −0.003274] | −0.028138 |

## The finding, and it is in the gross column

**All six gross intervals include zero.** Before a single basis point of cost, in both periods and
in all three arms, the top-decile-minus-bottom-decile spread is not distinguishable from nothing.
The largest point estimate is **+0.24% over five sessions** and its interval runs from −0.15% to
+0.61%.

That is the answer to the question §1 asked. **The ordering does not separate forward returns**, and
the three forms do not separate from each other: every arm's interval contains every other arm's
point estimate, in both periods.

**The net column is dominated by the cost constant and says less than it appears to.** Rebalancing
both legs every five sessions costs 100 bps per formation date — roughly 50% a year — so a net
figure at this frequency measures the rebalance schedule more than it measures the signal. That the
net spreads are significantly negative is arithmetic, not a finding: subtract a constant larger than
every point estimate and every interval moves below zero. The 3× stress column is the same shift
three times over and is reported because §5 registered it, not because it discriminates.

**Survivorship makes the null stronger rather than weaker.** The directory is today's, so names
delisted mid-window are absent from every formation date, which biases every figure **upward**
(§4). A measurement biased toward finding an edge, that finds none, is harder to explain away than a
neutral one.

## The verdict is weaker than the numbers, and the rule is why

The registered rule (§6) returned **`inconclusive`** overall: `SECTOR` rejects, `MARKET` does not.

**That is a gap in the rule, not in the result, and it is disclosed rather than patched.** §6's two
reject clauses are *"the CI includes zero"* or *"the point estimate is at or below the control's"*.
`MARKET`'s holdout CI **excludes** zero — entirely below it — and its mean (−0.007595) is very
slightly **above** the control's (−0.007938). Neither clause fires, so an arm whose interval sits
wholly in negative territory lands in `inconclusive`. Confirmed directly against the registered
function rather than inferred: `verdict(market, control)` returns `'inconclusive'` with both reject
clauses evaluating false.

The rule was written to catch an arm that fails to beat momentum. It did not anticipate an arm that
loses to zero while marginally out-performing a control that is also losing to zero. **Fixing it
after seeing this data would be exactly the redesign `PREREG_TEMPLATE` rule 3 downgrades**, so it is
recorded here for whoever writes the next pre-registration: a decision rule needs a branch for *both
arms and control are negative*, and comparing two losers on which loses less is not a finding.

## What this costs the programme

**3 trials**, declared in §6a before the run. A study that reaches `inconclusive` still spends them:
`b.deflated_sharpe` deflates by shots taken at the data. Derive what remains with
`python tools/trial_budget.py`.

## What it means for the strategy card, and for the entry-rate question

`CARD-001`'s four selection inputs stay **`unset`**, and this study sets none — exploratory results
may not advance a validation status. What changes is what a confirmatory trial would be spent on:
**at a 126-session lookback and a 5-session horizon, there is nothing here to confirm.**

**It does not refute the family** (§9). One lookback and one horizon were tested and neither was
searched, deliberately, to avoid spending trials on a sweep. A different lookback or a different
horizon could carry information that this pair does not.

**For the owner's entry-rate question**, the honest reading is narrower than it looks. The study
does not say a shorter hold is unprofitable; it says the ranking used to select names does not
predict at that hold. Raising the entry rate by shortening the hold changes how often the system
acts, not whether the thing it acts on carries information.

## What would have refuted this

`PR-013` §9: a holdout in which both ranking arms' CIs excluded zero and at least one point estimate
exceeded the control's. The observation that would have supported the hypothesis was available and
did not occur.

## Limitations, all inherited and none fixed here

- **Survivorship absent** — biases upward, and is why the null is the stronger reading.
- **Commission excluded** (A-1) — biases net upward.
- **One lookback, one horizon** — not a sweep, by design and at the cost stated in §9.
- **Sector coverage is 1,013 of 1,140** — a name without a sector is excluded from that arm's
  deciles, so `SECTOR` is measured on a smaller cross-section than the other two.
- **Exploratory** (§0b) — the drafter had seen `PR-012`'s numbers before this design existed.

## Reproducing

```bash
PYTHONPATH=$PWD/src python tools/run_pr013.py --data C:/PycharmProjects/SwingDesk/data
```

Add `--write` to publish `results/PR-013.json`. The run takes about four minutes and reads the bar,
directory and classification stores; it writes nothing without `--write`.
