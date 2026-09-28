# DR-057: a claim that something raises the owner's income is judged after tax, in a taxable account, at the owner's rate

```
date:            2026-09-28
status:          accepted — ruled by the owner 2026-09-28: asked which directions to take next,
                 the owner chose the offered "tax standard for the research"; the same day, that
                 the book runs in a regular taxable account rather than the TFSA, and, from the
                 bands offered, a combined marginal rate of "about 20-30%"
parameters:      tax.marginal_rate_low, tax.marginal_rate_high (owner); tax.treatment (unset)
components:      none new
implemented_by:  tools/measure_after_tax.py :: rate_band
```

## 1. What was ruled

1. **A study whose question is whether something raises the owner's income reports its excess over
   holding `SPY` AFTER tax**, beside its registered primary: the strategy taxed in the year each gain
   is realised, `SPY` held taxed on its dividends yearly and on its price gain only when sold -
   `tools/measure_after_tax.py`'s model (`EVIDENCE_SUMMARY` §41 carries the first reading).
2. **At both ends of the owner's rate band**, `tax.marginal_rate_low` and `tax.marginal_rate_high`.
   The owner gave a range, and a claim that holds at one end and not the other is not a claim about
   the owner.
3. **Under both treatments while `tax.treatment` is `unset`.** Whether frequent round trips are
   capital gains or business income is an accountant's answer, not this project's. Until it is
   given, a reading is reported both ways and the less favourable one is the one a claim must pass.
4. **A registered decision rule is not changed by this.** A study's verdict stays what its
   registration said; the after-tax reading is reported beside it and is what a claim about INCOME
   rests on. A verdict and an income claim are different statements, and this record keeps them apart.
5. **`DR-055`'s two proofs are pre-tax and unchanged.** Whether the after-tax reading also gates real
   money is the owner's call, asked when the proofs are met; until then §41 is read beside them.

## 2. Why

**Turnover realises tax; an index defers it.** A strategy that trades every session pays tax on
each year's gain in that year - possibly at the full rate, as business income - while the same money
in `SPY` compounds untaxed until it is sold. Measured on the main hypothesis the day before this
ruling (§41), at 20-30%: the book's decade margin of +4.41% a year before tax is +2.10% to +2.88% as
capital gains and −0.26% to +1.31% as business income, and its last-48-month margin of +0.74% is
negative in every cell. **A pre-tax edge of a few points is roughly the size of the tax a daily
strategy pays and the index does not**, so a pre-tax verdict alone answers a different question from
the one the owner asked.

**The account.** The owner holds a TFSA and ruled on 2026-09-28 that this strategy runs in a regular
taxable account instead: a TFSA carrying on a business of trading is taxed on it (*Ahamed v. The
King*, 2023 TCC 17, upheld 2024 FCA 108), and the owner would not build on that question.

## 3. The model, and what it leaves out

The model is `tools/measure_after_tax.py`'s, stated in its docstring. What it leaves out, each named
there as well: the superficial loss rule (which makes capital-gains readings OPTIMISTIC for a strategy
that buys back what it sold within thirty days), currency and its conversion, and every provincial
detail beyond one combined marginal rate. **Nothing in this project is tax advice.**

## 4. Parameters

| id | value | status |
|---|---|---|
| `tax.marginal_rate_low` | 0.20 | owner, 2026-09-28 |
| `tax.marginal_rate_high` | 0.30 | owner, 2026-09-28 |
| `tax.treatment` | none | `unset` - an accountant's answer; a reading reports both treatments |

## 5. Consequences

* `tools/measure_after_tax.py` reads the band from the registry and marks the owner's rows; its grid
  from 20% to 50% stays, so a reader can see how far the answer moves with the rate.
* A registration from this date whose question is income names its after-tax reading among its
  diagnostics. **No gate checks that yet** - it is recorded as open work rather than claimed.
