# RISK SPEC

**Status:** drafting · **Tier:** 2 (domain) · **Content:** `verbatim`

<!-- verbatim-sources: Appendix_C_Formuly_upravleniya_riskom_v2.0.pdf, Module_48_Stop_loss_v4.0.pdf, Module_49_Razmer_pozitsii_v4.0.pdf -->

**Source of truth:** `Appendix_C_Formuly_upravleniya_riskom_v2.0.pdf` page 2, extracted with
`pdftotext -enc UTF-8 -f 2 -l 2 <file> -`, verified 2026-08-01.

**Appendix C is one of only two places in the entire course containing arithmetic** (the other is
Appendix D, `STATISTICS_SPEC.md`). Modules 48–51 and 93 name every risk concept and quantify none;
this appendix is the whole computational basis for sizing and exposure.

The formulas below are complete and unambiguous. The **inputs** are not: `risk %` is explicitly
deferred to the user, and every cap named in the control column is unquantified. See §4.

---

## 1. The formulas, verbatim

Each line is one cell of the source table, checked individually by
`tools/verify_transcription.py`:

```verbatim
Equity × risk %
Entry − Stop + costs allowance
Stop − Entry + costs allowance
floor(Allowed risk $ / risk/share)
Shares × Entry
Σ position remaining risk
Σ risk одной темы/сектора
Long market value − Short market value
Long + |Short| market value
Net P&L / planned risk $
Local P&L × FX + currency effect
```

Mapped to their measure and control clause:

| Показатель | Формула | Контроль |
|---|---|---|
| Allowed risk $ | `Equity × risk %` | Риск % задаётся личным планом. |
| Long risk/share | `Entry − Stop + costs allowance` | Stop ниже entry. |
| Short risk/share | `Stop − Entry + costs allowance` | Добавить squeeze/gap allowance. |
| Shares | `floor(Allowed risk $ / risk/share)` | Ограничить max position value/liquidity. |
| Position value | `Shares × Entry` | Не равно риску. |
| Open risk | `Σ position remaining risk` | Считать после partials и stop changes. |
| Sector risk | `Σ risk одной темы/сектора` | Учитывать ETF и корреляции. |
| Net exposure | `Long market value − Short market value` | Не заменяет risk calculation. |
| Gross exposure | `Long + |Short| market value` | Полезно для leverage. |
| R result | `Net P&L / planned risk $` | Использовать исходный planned risk. |
| FX-adjusted P&L | `Local P&L × FX + currency effect` | Разделять asset и FX return. |

## 2. What the control column obliges

The `Контроль` column is not commentary — each entry is a rule the implementation must enforce:

| Rule | Obligation |
|---|---|
| `Stop ниже entry` | Reject a long whose stop is at or above entry. A non-positive `risk/share` is a `STOP` skip, never a division that produces a huge or negative share count. |
| `Добавить squeeze/gap allowance` | Short sizing carries an **additional** allowance beyond the long formula. Unquantified — parameter registry. |
| `Ограничить max position value/liquidity` | `Shares` from the formula is an upper bound, then capped by position-value and liquidity limits. Both caps unquantified. |
| `Не равно риску` | Position value must never be displayed or used where risk is meant. They are different columns in the journal (`Risk Snapshot`) and must not be conflated in the UI. |
| `Считать после partials и stop changes` | Open risk is **recomputed**, not decremented. Any partial exit or stop move triggers recomputation of the whole book. |
| `Учитывать ETF и корреляции` | Sector risk aggregates by *theme*, and an ETF's exposure counts toward its constituents' sector. Correlated positions are one bet. |
| `Не заменяет risk calculation` | Net exposure is a reporting figure. No gate may be written against it in place of a risk gate. |
| `Использовать исходный planned risk` | The R denominator is the **originally planned** risk, frozen at entry — not the current or adjusted risk. This makes R stable across stop moves and partials, and it is the single most commonly broken invariant in systems of this kind. It belongs in `INVARIANTS.md`. |
| `Разделять asset и FX return` | A CAD/USD position's P&L is reported as asset return and currency effect separately, never merged. |

## 3. Ordering law

From Modules 48 and 49, and stated identically in 28 topic pages:

> "Stop — точка, после которой первоначальная гипотеза больше не считается действительной. Он
> задаётся до размера позиции; технический stop не сужается ради желаемого количества акций."

And the standard attached to sizing topics:

> "Использовать формулу из equity, allowed risk и realistic risk/share; округлять вниз и применять
> portfolio/liquidity caps."

**Binding sequence — not reorderable:**

1. invalidation → stop
2. stop + costs/gap allowance → risk per share
3. equity × risk % → allowed risk $
4. `floor(allowed risk $ / risk per share)` → shares
5. apply position-value and liquidity caps
6. check open risk, sector risk, correlation and event exposure

Narrowing the stop to obtain a larger position reverses steps 1 and 4 and is error `WIDE_STOP`'s
mirror image; it is prohibited by name. Rounding is **down**, always.

## 4. Every input the course refuses to supply

Verbatim from the first control cell: `Риск % задаётся личным планом.` The course states this
explicitly rather than omitting it — the value is the user's, by design.

All of the following become required entries in `PARAMETER_REGISTRY.md` with provenance
`assumed:<citation>` under owner decision D5, editable from the web UI once it exists. Until a value
is set, the owning component returns a coded refusal (`FAIL_CLOSED_POLICY.md` §4 — *"а не догадку"*):

| Parameter | Named in | Course value |
|---|---|---|
| risk % per trade | Appendix C, M93-T1324 | none |
| costs allowance (commission + slippage) | Appendix C | none |
| squeeze/gap allowance for shorts | Appendix C | none |
| max position value | Appendix C control | none |
| liquidity cap (order size vs ADTV) | Appendix C control, `M49-T0760` | none — the owner set 1.0%, `DR-028` supplied the definition |
| max open risk | M51-T780, M93-T1326 | none |
| max sector risk | M51-T782, M93-T1327 | none |
| correlation threshold and its size adjustment | M49-T761, M51-T781 | none |
| max concurrent positions | M49-T764 | none |
| max daily loss · max weekly loss | M51-T792/793, M93-T1328/1329 | none |
| drawdown size-reduction ladder | M49-T765, M93 | none |
| risk-off ladder levels and streak triggers | `FAIL_CLOSED_POLICY.md` row 5 | none |

**Module 93 is titled "Итоговая система управления риском" and contains no numbers.** That is not an
extraction failure — its eleven topics are templated prose. Recording it here so nobody re-reads M93
hoping to find the limits.

## 5. Open items

- [ ] `costs allowance` composition: commission, spread, slippage — the course lists them as inputs
      to risk/share but does not say how they combine. Authored decision, then frozen.
- [ ] Currency handling for a CAD account trading USD names, and vice versa. `FX-adjusted P&L` is
      given; the sizing-time FX conversion is not.
- [ ] Whether `Open risk` counts a position at breakeven as zero risk or as its remaining stop
      distance. `Σ position remaining risk` implies the latter; confirm before implementing.
