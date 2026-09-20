# PR-032 RESULT: on three funds it was never fitted to, the rule earns nothing — and it earned nothing on them before publication either

```
prereg:        PR-032
ran:           2026-09-19
verdict:       INCONCLUSIVE, branch NULL, as section 3 put at even odds. The basket of IWM, DIA
               and EFA since publication, -0.0054% a day [-0.0293, +0.0199] - zero inside the 0.08
               floor, on a 0.049 interval
status:        final. Run from the registration commit's snapshot at the pinned instant; amendment
               A-1 (after the run) fixed the verdict WORD the result file writes, and the re-run
               reproduced every cell to the digit
tool:          tools/run_pr032.py (PR-031's rule, imported unchanged)
evidence:      PR-032.json; IWM, DIA, EFA and PR-031's SPY minutes, 2,693 sessions each
trials:        3, declared before the run (IWM, DIA, EFA)
```

---

## Read this first

**The rule does not generalise.** On an equally weighted basket of `IWM`, `DIA` and `EFA` — three
funds picked for what they are, before a minute of them was fetched — it earned **−0.0054% a day**
since publication, an interval from −0.029% to +0.020%. That is the `NULL` branch: zero, inside a
floor worth about ±10% a year.

**And the diagnostic that matters more is the one §6 never reads.** Over the 2,678 sessions
**before** publication — the years `PR-031` found the rule earning 10.7% a year on `SPY` — the same
basket earned **+0.0035% a day [−0.0092, +0.0159]**: 0.88% a year, a Sharpe ratio of 0.14. **The
rule never worked on these funds.** Not before publication, not after.

**So `PR-031`'s `ACCEPT` is about `SPY`, not about intraday momentum.** Two of the project's
readings now point the same way: the effect is absent on `SPY` since the paper appeared, and absent
on three other index funds throughout. What is left is `SPY` before 2024 and `QQQ`, which are the
two funds the paper itself is about and the one this project looked at next — the smallest possible
population for a claim about markets.

## §9, as registered, shown first

| check | registered | realised |
|---|---|---|
| `SPY` through this tool's loader against `PR-031`'s own estimate | under 1e-12 | **1.0e-20** — the same number to the last bit |
| sessions unread, any fund | under a tenth | **0**; the 15 warm-up sessions are the only exclusion |
| realised half-width against §3's 0.0237 | half to twice | **0.0246**, 1.04× |
| mean leverage, any fund | 1 to 4 | **1.74** (`IWM`), 2.69 (`DIA`), 2.38 (`EFA`) |

## The readings

| mean daily net return | estimate | 95% interval |
|---|---|---|
| **the basket, since publication** (the verdict) | **−0.0054%** | **[−0.0293, +0.0199]** |
| the paper's cost ($0.0045) | −0.0048% | [−0.0287, +0.0205] |
| cost-adverse (a cent a side) | −0.0111% | [−0.0352, +0.0142] |
| gross, no cost at all | +0.0003% | [−0.0236, +0.0258] |
| **the basket, BEFORE publication** (counted, never read) | **+0.0035%** | **[−0.0092, +0.0159]** |
| `IWM` since publication (counted, never read) | −0.0179% | [−0.0571, +0.0185] |
| `DIA` since publication (counted, never read) | −0.0052% | [−0.0459, +0.0331] |
| `EFA` since publication (counted, never read) | +0.0069% | [−0.0114, +0.0284] |

**Gross is the sentence.** Before any cost the basket earns +0.0003% a day — a third of a basis
point. There is nothing here for a cheaper fill to rescue: the rule is not paying for its costs
because it is not earning anything to pay with.

**Described, never read by §6:**

| since publication | a year | volatility | Sharpe | worst drawdown | sessions traded | holding it, Sharpe |
|---|---|---|---|---|---|---|
| the basket | −1.4% | 6.4% | −0.21 | −7.3% | | |
| `IWM` | −4.5% | 9.1% | −0.50 | −14.6% | 177 of 590 | 0.77 |
| `DIA` | −1.3% | 9.5% | −0.14 | −13.5% | 188 of 590 | 0.86 |
| `EFA` | +1.7% | 6.3% | +0.28 | −5.7% | 164 of 590 | 0.78 |
| the basket, before publication | +0.9% | 6.4% | +0.14 | −10.2% | | |

## What this establishes, and what it does not

**Established:** over the 590 sessions since publication, `PR-031`'s rule earns within about ±5% a
year of nothing on `IWM`, `DIA` and `EFA`, and it is slightly negative net of a half-cent. On the
same three funds over 2016 to publication it earned 0.9% a year at a Sharpe ratio of 0.14 —
**the rule's edge was never present on them.**

**Not established:**

* **that the rule is dead on `SPY` and `QQQ`.** Nothing here re-reads them. `PR-031`'s `SPY` is
  what it is: 8.5% a year over the whole window, 0.45% since publication, and `QQQ` at 8.6% since
  publication, counted and never read there.
* **why `SPY` and `QQQ` differ from these three.** Both are the most heavily optioned funds in the
  market, and the intraday flow that hedges those options is a candidate explanation. This study
  measured none of it, and an explanation invented after a result is a hypothesis, not a finding.
* **that a long-and-short version would read the same.** The short leg was never run here.

## What it changes

* **The case for a live paper trial is weaker than `PR-031` left it.** `PR-031`'s `ACCEPT`
  licensed a specification; this says the thing it licensed works on two funds out of five tried,
  one of which has been flat for two years. Whether to specify one anyway is the owner's call, and
  it should be made knowing this.
* **The next question, if the family is pursued, is WHERE the effect lives** — the funds with the
  deepest options flow, and whether `QQQ`'s two good years survive being asked properly. Both are
  new registrations; `QQQ` in particular cannot be read from `PR-031`, where it was chosen after
  the fact.

## §10, amendment A-1 — the verdict's word, not its branch

The runner wrote `"verdict": "null"`. This project's result files speak four words — `accept`,
`reject`, `inconclusive`, `refused` — and a branch like `NULL` is reported as `INCONCLUSIVE` with
the branch beside it (`run_pr024.TOKEN`, `PR-026`'s report, enforced by `tools/verify_studies.py`).
`run_pr031.TOKEN` invented a fifth word and `run_pr032` inherited it. **Fixed after the run**: the
token table now maps `NULL`, `COST_FRAGILE` and `PUBLICATION_FRAGILE` to `inconclusive`, with a test.
The branch, the readings, the decision rule and every number are untouched, and the re-run
reproduced the first run's cells exactly. `PR-031`'s own verdict, `accept`, is unaffected.

## What the study cost

8,079 requests to the vendor over 80 minutes for the minutes; one run of four minutes. Three
trials, 146 to 149.
