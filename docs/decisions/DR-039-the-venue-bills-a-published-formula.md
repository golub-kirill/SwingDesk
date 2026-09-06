# DR-039: the venue bills a published formula, and the model charges an assumed rate for a commission nobody takes

```
date:            2026-09-05
status:          proposed
parameters:      costs.commission_model (commission component only), costs.regulatory_fee_schedule (new)
components:      none - swingdesk.validation.backtest.costs implements the model; this sets its inputs
supersedes:      DR-004's COMMISSION component. DR-005's 25bp slippage stands untouched, and so does
                 DR-004's reasoning for charging slippage to the fill rather than deducting it after
evidence:        measurements/venue-fees-2026-09-05.json
implementation:  none - proposed. Section 6 says what accepting it would cost the code, and the
                 shape currently in `CostModel` cannot express it
```

## 1. What made this necessary: the first real fee this project has ever seen

The owner supplied an Alpaca account statement on 2026-09-05 showing three fees on the `AIS` round
trip — the first completed trade this system has journalled (`positions.duckdb`,
`POS-AIS-2026-09-03`, closed 2026-09-04).

| | billed | side |
|---|---|---|
| REG fee, on a proceed of $1,190.51 | **$0.03** | sell |
| TAF fee, on 17 shares / 1 trade | **$0.01** | sell |
| CAT fee, on 1 trade | **$0.01** | both |

**Not one of these categories appears anywhere in this repository.** `git grep` for `TAF`, `FINRA`,
`CAT fee` and `Section 31` across every `.md` and `.py` returns nothing outside this record.

Meanwhile `registry/parameters.yml` holds `costs.commission_model` = **0.005 USD per share, each
side**, provenance `assumed:DR-004`, `read_by: none`. On this trade that model charges **$0.170** —
**3.4× the entire real fee bill** — for a commission this venue does not take.

**This was half-known and the wrong half was recorded.** The commit of 2026-08-11 found `DR-004`'s
commission wrong against *Wealthsimple*, which charges none and takes 1.5% on CAD-USD conversion.
The venue has since changed to Alpaca and the finding was never re-derived against it. A cost model
wrong about one broker was left standing while the project changed brokers.

## 2. Why this is a decision record and not a pre-registration

`AGENTS.md` §8 says a threshold the course does not supply needs a pre-registration rather than a
guess, and the course quantifies nothing here — M72-T1081 (`Комиссии`) names the concept and gives
no number, which is `DR-004`'s own starting point.

**§8's rule is about a value that must be MEASURED. These values are PUBLISHED.** The SEC sets the
Section 31 rate and FINRA sets the TAF rate; both appear in dated notices. A study would be the
wrong instrument — there is nothing here for a sample to discover, and running one would produce an
estimate of a number that is already stated exactly. What this needs is a **citation**, which is
what a decision record carries.

That distinction is the whole argument for this record and it is worth stating plainly: *a rate
somebody publishes is not a threshold somebody has to find.*

## 3. What was verified, and how one observation was enough

**Predicted from the published rate, rounded up to the cent, against the billed amount:**

**Corrected 2026-09-05 against Alpaca's own schedule — see §9. The rates below are the
schedule's, not the ones this record was first written with.**

| fee | rate, from Alpaca's schedule | predicted | billed |
|---|---|---|---|
| SEC Transaction Fee | **$0.0000206 × trade value**, sells only | 1190.51 × 0.0000206 = 0.024525 → **$0.03** | **$0.03** ✓ |
| FINRA TAF | **$0.000195 per share**, sells only | 17 × 0.000195 = 0.003315 → **$0.01** | **$0.01** ✓ |
| CAT, sell day | **$0.000003 per equivalent share**, both sides | 17 × 0.000003 = 0.000051 → **$0.01** | **$0.01** ✓ |
| CAT, buy day 09-03 | same, over **47 shares** aggregated | 47 × 0.000003 = 0.000141 → **$0.01** | **$0.01** ✓ |

**One trade is normally not a sample, and here that objection does not apply.** Section 31 and TAF
are *deterministic functions* of proceeds and of share count. A single observation **checks a
formula**; it estimates nothing about a distribution. The same single observation says exactly
nothing about slippage, and this record claims nothing about slippage.

~~**The rounding is inferred, not published.**~~ **IT IS PUBLISHED, and it is not per trade.**
Alpaca's schedule, page 4: *"Fees are calculated on the exact executed quantity, including
fractional shares, with no rounding of share quantity. Each fee type is aggregated separately at
the **daily, per-account** level. After aggregation, each fee total is rounded **up** to the
nearest cent $0.01."*
**That resolves the CAT puzzle completely and it was never about trades.** $0.01 on one trade and
$0.01 on twelve looked non-linear because CAT is a per-SHARE fee aggregated over the DAY: 47
shares bought on 09-03 cost $0.000141, and 17 sold on 09-04 cost $0.000051. Both round up to a
cent. The statement line *"CAT fee for proceed of 12 trades"* is a daily total, not a per-trade
charge.

## 4. The decision

**1. `costs.commission_model` — the commission component of `DR-004` is superseded.**

| | |
|---|---|
| ~~0.005 USD per share, each side~~ | **0.00 USD per share** |

**Confirmed from the schedule, page 1:** *"Alpaca Securities does not charge commissions, except
as described below"* — the exceptions being index options, the Elite Smart Router, and order flow
determined non-retail. A standard retail US equity account pays none of them.

`DR-004` is left otherwise unedited, exactly as `DR-005` left it when it replaced the slippage
component. Its 3× stress regime and its fill-price reasoning both stand.

**2. `costs.regulatory_fee_schedule` — new, and kept separate from commission deliberately.**

| fee | rate | side | applied to |
|---|---|---|---|
| SEC Transaction Fee | **$0.0000206 × trade value** | **sell only** | proceeds |
| FINRA TAF | **$0.000195 per share**, max **$9.79** per trade (the cap binds at 50,205 shares) | **sell only** | share count |
| CAT | **$0.000003 per executed equivalent share** | **both** | NMS equities 1 share = 1 equivalent share; **OTC equities 1 share = 0.01** |

**Aggregated per fee type at the DAILY, PER-ACCOUNT level, then each total rounded up to the
cent — once.** Not per trade. This is the schedule's own rule and it is the part most likely to
be implemented wrongly, because charging each trade and summing over-charges every day with more
than one trade in it.

**Why not folded into commission.** `DR-004` already argues that a per-share and a percentage
schedule are different functions. These are more different still: a broker sets a commission and
can change it as a business decision; a regulator sets these and changes them on its own calendar
for its own reasons. Merging them would put two clocks behind one number.

**Provenance is `owner` or a citation, never `assumed`.** `assumed` promises a study will replace
the value. No study will, because these are published — and marking them `assumed` would put them
in the "awaiting evidence" queue forever, which is exactly the sort of permanent-pending state
`AGENTS.md` §15 is about.

## 5. What this does NOT change, stated first because it is the part most likely to be misread

**It does not rescue any finding, and nobody should hope it will.**

```
regulatory fees   $0.05   = 0.42 bp of the sell side
modelled slippage $5.77   = 25 bp per side (DR-005)
fees / slippage   0.9%
```

`EVIDENCE_SUMMARY.md` records that the base strategy is **negative at measured costs across the
whole admissible universe**. Slippage dominates that by two orders of magnitude. Removing a
commission the venue never charged makes the model *slightly less pessimistic*; adding regulatory
fees makes it *slightly more*. Neither moves a verdict, and this record does not re-open one.

**What it changes is honesty, not arithmetic.** An `assumed` model is a promissory note. This
replaces one component of it with a formula anybody can check against a regulator's own notice.

## 6. What accepting this costs the code, and the current shape cannot express it

`swingdesk.validation.backtest.costs.CostModel` charges commission as:

```python
def commission(self, shares: int) -> Decimal:
    """Both sides, so twice the per-share rate."""
    return self.commission_per_share * shares * 2
```

**Symmetric by construction.** Section 31 and TAF fall on the **sell only**, and Section 31 is a
function of *proceeds* rather than of shares — a quantity `commission()` is never given. So this is
a signature change and a new cost term, not a value swap. Named here so that accepting the record
is not mistaken for a one-line edit.

**And a study must not silently inherit it.** That module's docstring already carries the rule —
*"a study pins its own values and records them"* — and it matters more here than usual, because the
Section 31 rate is **time-varying**: it was **$0.00 per million** until 2026-04-04. A backtest over
2016–2026 charging today's rate across the whole window would be wrong in a way no test would
catch. Any implementation must be point-in-time, which this project already has the machinery for.

## 7. What is NOT established, and none of it is decoration

1. **Whether a paper account is billed the live schedule.** These fees came from a paper account.
   That paper bills anything is itself informative, but paper-equals-live is unverified. **This is
   the only one of the four still open.**
2. ~~**The CAT rate.**~~ **RESOLVED**: $0.000003 per executed equivalent share, both sides. It read
   as *"not linear in trades"* because it is not a function of trades at all.
3. ~~**The TAF per-trade maximum.**~~ **RESOLVED**: $9.79, binding at 50,205 shares — and
   50,205 × 0.000195 = $9.79 exactly, so the cap and the rate corroborate each other.
4. ~~**Whether Alpaca's round-up is policy.**~~ **RESOLVED**: published, page 4, and the
   aggregation is daily and per-account rather than per trade.

## 8. What would overturn this

- ~~**Alpaca's own fee schedule read directly.** … That is the first thing to close.~~ **CLOSED the
  same day, on the owner's prompt.** Read with `pdfplumber` in a throwaway environment outside the
  project, so no dependency was added to `pyproject.toml`. §9 records what it changed.
- **A live-account statement** disagreeing with the paper one, which settles §7 item 1.
- **A second CAT observation** at a different trade count, which would constrain item 2.
- **A rate change.** Section 31 moves roughly annually; the record's rate carries its effective date
  so a future reader can tell a stale rate from a wrong one.

## 9. CORRECTED THE SAME DAY, AND THE CHECK HAD PASSED ON A WRONG RATE

This record was first written from **FINRA's and the SEC's own pages**, because they set the
rates and Alpaca passes them through. The owner then supplied the route to Alpaca's schedule.
**It disagrees, and it is the document that actually bills.**

| | first written | Alpaca's schedule |
|---|---|---|
| SEC transaction fee | $20.60 per $1M | **$0.0000206 × value** — the same number |
| FINRA TAF | $0.000166 / share | **$0.000195 / share** |
| TAF maximum | $8.30, marked uncertain | **$9.79**, binding at 50,205 shares |
| CAT | *not established* | **$0.000003 / equivalent share, both sides** |
| rounding | inferred from two amounts | **published, and aggregated DAILY per account** |

**THE PART WORTH CARRYING IS NOT THE RATE. IT IS THAT THE CHECK PASSED ANYWAY.** §3 predicted
$0.01 of TAF from 0.000166 and the venue billed $0.01 — but 17 × 0.000195 also rounds up to
$0.01. **The observation never discriminated between the two rates**, and a verification that
cannot fail is not a verification. The cent that made the arithmetic legible is the same cent
that made it undiscriminating.
**What would have caught it:** a trade large enough for the rates to differ by a cent — about
**345 shares** — or reading the billing document first. The second is cheaper and is the rule:
**a claim about what you are CHARGED is tested against the schedule that charges you**, not
against the regulator who sets the rate the schedule quotes. `AGENTS.md` §15 rule 2 says test a
claim about a source against the source; the source here is the broker.

**And CAT was not unknowable, it was mis-modelled.** Two observations of $0.01 — one trade and
twelve — were read as *"not linear in trades"* and then as *"so no rate is constrained"*. The
first half was right and the second did not follow: CAT is per SHARE and aggregated per DAY, so
trade count was never the variable. Assuming the wrong denominator turned a legible fee into an
unestablished one.

## Sources

- FINRA, *Trading Activity Fee* — <https://www.finra.org/rules-guidance/guidance/trading-activity-fee>
- FINRA Information Notice 03/17/26, *New Rate for Fees Paid Under Section 31* —
  <https://www.finra.org/rules-guidance/notices/information-notice-20260317>
- Alpaca, *Regulatory Fees* — <https://docs.alpaca.markets/docs/regulatory-fees>
- **Alpaca Clearing, *Brokerage Fee Schedule*, template updated 2026-09-01 — the operative
  document** — <https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf>
