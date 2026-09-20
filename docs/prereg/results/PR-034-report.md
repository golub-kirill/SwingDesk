# PR-034 RESULT: small caps' night earns 13.8% a year, survives a cent a share, and is the first thing here to beat holding per unit of risk

```
prereg:        PR-034
ran:           2026-09-20
verdict:       ACCEPT. The IJR+VB basket's overnight arm +0.0549% a day [+0.0207, +0.0895] -
               13.83% a year at a Sharpe ratio of 1.06 against holding the same two funds' 0.59.
               All three gates cleared: at a whole cent a share a side +0.0463% [+0.0120, +0.0809];
               the last 590 sessions +0.0624%; the Sharpe ratio above holding's
status:        final. Run once from the registration commit's snapshot at the pinned instants
tool:          tools/run_pr034.py (PR-033's arms, imported unchanged)
evidence:      PR-034.json; IJR, VB and MDY minutes 2016-01-04 .. 2026-09-18 and their dividends
trials:        6, declared before the run (two arms x three funds)
```

---

## Read this first

**This is the first result in this project that beats holding the asset per unit of risk.**
`EVIDENCE_SUMMARY` §20-§23 records four strategy classes that did not; `PR-031` beat `SPY` and then did
not generalise; `PR-033` found the night paying and still losing to holding. Here, on `IJR` and
`VB` over 2,692 sessions:

| | a year | volatility | Sharpe | worst drawdown |
|---|---|---|---|---|
| **the night** (buy the close, sell the next open) | **+13.8%** | 13.1% | **1.06** | −31.6% |
| the session (buy the open, sell the close) | **−5.4%** | 16.8% | −0.32 | −64.8% |
| holding the same two funds, with dividends | +12.9% | 21.8% | 0.59 | −42.2% |

**In small caps the session actively destroys money.** Not "adds little" — it loses 5.4% a year
before the night's gain is counted. The whole of these funds' decade came overnight, and more than
the whole.

**Every gate the registration set was cleared**, and they were the gates `PR-033` failed:

| gate | needed | realised |
|---|---|---|
| the interval above zero | net, at half a cent a share a side | **+0.0549%** [+0.0207, +0.0895] |
| a whole cent a share a side | above zero | **+0.0463%** [+0.0120, +0.0809] — 11.7% a year |
| the last 590 sessions | a positive estimate | **+0.0624%** — 15.7% a year at a Sharpe ratio of 1.24 |
| better than holding | a higher Sharpe ratio | **1.06 against 0.59** |

**§3 predicted +0.048% a day before the run; the measurement is +0.0549%.**

## §9, as registered, shown first

| check | registered | realised |
|---|---|---|
| the two arms compounded equal holding, on sessions with no dividend | a rounding error | **3e-16** on all three funds |
| sessions unread, any fund | under a tenth | **0**, bar one session each for `VB` and `MDY` with no closing minute |
| realised half-width against §3's 0.0344 | half to twice | **0.0344**, 1.00× |
| each fund's dividends against its published yield | within a tenth | `IJR` $14.82, `VB` $28.12, `MDY` $54.72 over the window — each within a tenth |

## Every fund, both halves of the day

| | night, a year | night Sharpe | session, a year | session Sharpe | holding, a year | holding Sharpe |
|---|---|---|---|---|---|---|
| `IJR` (S&P SmallCap 600) | +10.5% | 0.78 | −3.4% | −0.19 | +13.0% | 0.57 |
| `VB` (Vanguard Small-Cap) | **+17.3%** | **1.36** | −7.4% | −0.45 | +12.9% | 0.61 |
| `MDY` (S&P MidCap 400, the boundary, never read) | +7.8% | 0.61 | +3.4% | +0.21 | +12.6% | 0.60 |

**The boundary case behaves like a boundary.** `MDY` holds bigger companies, its night earns less
and its session stops losing — the same ordering `PR-033` found across `SPY`, `DIA` and `IWM`. The
smaller the companies, the more of the return is overnight. That is a pattern across five funds
now, and it was predicted by the hypothesis rather than found in it.

## What this establishes, and what it does not

**Established:** over 2016-2026, holding `IJR` and `VB` only overnight earned 13.8% a year net of
two trades a day at half a cent a share, 11.7% at a cent, with a Sharpe ratio above holding the
same funds outright, and it was not weaker over the last two years. The arms are an exact
decomposition of holding, so nothing is fitted: the only choices are the cost and which half of the
day to own.

**Not established, and §0 said the first of these before the run:**

* **that this is independent of `PR-033`'s `IWM` reading.** `IJR`, `VB` and `IWM` hold overlapping
  companies. This shows `IWM`'s number was not one wrapper's quirk and that it survives the gates;
  it is not a second sample of small-cap returns.
* **that it is low risk.** A −31.6% drawdown is an equity drawdown. The night holds full market
  exposure while it holds anything, and 2020 is in the window.
* **that these prices are tradeable at this cost.** Every fill is an auction — market-on-close to
  buy, market-on-open to sell — and this project has priced auctions only in `PR-025` and `PR-030`,
  on stocks. A cent a share on `IJR` is 0.9 bps; whether the auctions give that is unmeasured.
* **what it does after tax, and in a real account.** Every gain is short-term; nothing here models
  that, and `DR-039` sets commission to zero because Alpaca charges none.

## What it changes

* **The first candidate for a specification.** The registration licensed exactly this: *worth a
  specification for a paper trial*. It needs what `CHARTER` A-003 §4 records as absent — a pass that
  places `cls` orders before 15:50 ET and `opg` orders after 19:00 ET — and `DR-027` §3.3's `day`
  time-in-force places neither.
* **The session is the thing to avoid, not the night to chase.** On these funds the session's own
  Sharpe ratio is −0.32. That is the same statement from the other side, and it is what makes the
  night's number arithmetic rather than a signal.
* **Nothing is built.** The owner decides whether a specification and a paper trial are worth it.

## What the study cost

8,079 requests for the minutes and 3 for the dividends; one run of six minutes. Six trials, 159 to
165.
