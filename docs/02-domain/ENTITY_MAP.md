# ENTITY MAP — the specification's object types against this tree

**Status:** drafting · **Tier:** 2 (domain) · **Content:** authored, measured against the tree

Master ТЗ v1.0 §7. `SPEC_GAP_ANALYSIS.md` recorded the shortfall as *"the ТЗ's 22-entity table is not
mapped one-to-one"*. This is that mapping, and the first thing it has to disclose is a discrepancy in
its own source.

---

## 0. The source is second-hand, and it does not agree with the gap analysis

**The master specification is not in this repository.** What exists is the parallel track's
restatement of it — `03_Domain_Ontology.md` §2, preserved verbatim in commit `dee8f37` — and that
table lists **24 object types**. `SPEC_GAP_ANALYSIS.md` row 7 says the ТЗ has **22**.

One of those numbers is wrong and **this document cannot tell which**. Both possibilities are live:
the restatement may have added two types, or the "22" may have been a miscount by a reader who also
did not have the original.

So the mapping below is against the 24-row restatement, labelled as such. Two consequences, stated
rather than worked around:

1. **A row here is evidence about the restatement, not about the ТЗ.** `AGENTS.md` §1 —
   never trust a document's claim about another source without checking — and the check is not
   available.
2. **This document closes §7 conditionally.** It is complete against what the repository holds and
   would need one pass against the original to be complete against the specification.

## 1. The mapping

`this tree` names the place the object actually lives. **`—`** means the concept exists only as
prose.

| # | Object type | Where it lives here | State |
|---:|---|---|---|
| 1 | `Raw Data` | `Bar` with `Series.RAW`, `market_data.store` | **built** |
| 2 | `Normalized Data` | `Series.ADJUSTED`, stored separately by contract | **built** |
| 3 | `Observation` | `Observation` / `ObservationSeries` | **built** |
| 4 | `Feature` | `derived_observations/` | **built** — 6 with golden vectors |
| 5 | `Indicator` | ATR `M18-T0280`, SMA `M25-T0382` | **built** |
| 6 | `Rule` | `RULE_SPEC.md`, `decision_logic/` | **specified**; no object carries `scope` or `evidence_status` |
| 7 | `Event` | `EVENT_SPEC.md` — the **market**-event catalogue | **catalogued**; no event source is wired |
| 7′ | *(the ТЗ's Event)* | `TRANSITION_SPEC.md` — renamed to end the collision | **specified** |
| 8 | `State` | `DECISION_STATE_MACHINE.md` — five enums | **partial**: no instrument state machine, no hysteresis |
| 9 | `Regime` | `REGIME_SPEC.md`, `derived_observations/regime.py` | **built**, and the only `validated` parameter |
| 10 | `Setup` | `STRATEGY_CARD_SPEC.md` | **prose only** — no Setup object with expiration |
| 11 | `Trigger` | `breakout_high` in the backtest engine | **built in backtest, absent live** — `REQUIREMENTS.md` §3 |
| 12 | `Constraint` | `CODES.md` (12 + 12), `FAIL_CLOSED_POLICY.md` | **partial**: no object with `priority` / `override_policy` |
| 13 | `Strategy` | `STRATEGY_CARD_SPEC.md` | **specified, zero instances** — no card exists |
| 14 | `Decision` | `DecisionRecord`, the journal's `decisions` table | **built** |
| 15 | `Order` | `JOURNAL_SCHEMA.md`'s `Order` entity | **DEFERRED by D1** — recorded if the owner supplies it, never placed |
| 16 | `Fill` | `JOURNAL_SCHEMA.md`'s `Fill` entity | **not built** — needs the post-trade loop |
| 17 | `Position` | `contracts/position.py` | **built**, append-only, read as-of |
| 18 | `Trade` | `contracts/trade.py` | **built** — backtest only; no live trade exists |
| 19 | `Outcome` | `Trade.net_r`, `mfe`, `mae` | **built**; intrabar ambiguity policy in `EXECUTION_MODEL.md` §4 |
| 20 | `Expectation` | `EXPECTATION_MODEL.md` | **specified, no instance** — nothing is addressable |
| 21 | `Evidence` | `contracts/evidence.py`, three reports | **built**, three disclosures required |
| 22 | `Parameter` | `registry/parameters.yml`, `ParameterUse` | **built** — 96 rows, gate 1 |
| 23 | `Policy` | `ExitPolicy`; the mode rules in `SYSTEM_MODES.md` §6 | **partial** — no general Policy object |
| 24 | `Decision Agent` | — | **DEFERRED** — `CHARTER.md` §3 v1 non-goal |

## 2. What the mapping shows

**Twelve of twenty-four are built as real objects.** Not "documented" — instantiated, with a contract
or a registry row behind them.

**Two are deferred by decision rather than missing**: `Order` (D1 — the system never places one) and
`Decision Agent` (a v1 non-goal). Their place in the ontology is fixed, which is what `DEFERRED`
means in `SPEC_GAP_ANALYSIS.md` §1.

**Three are specified with zero instances** — `Strategy`, `Expectation`, and the ТЗ's `Event`. All
three are the same shape of gap: the form is frozen and nothing has been created against it. The
strategy card is the one that unblocks the others, which is why `ROADMAP.md` §4 **P5** makes it
load-bearing for phase 3.

**One is split in two, deliberately.** Row 7 and 7′ are the terminology collision
`TRANSITION_SPEC.md` §1 resolved: *event* means the market's, *transition* means the system's. This
is the only place where the mapping is not one-to-one, and it is one-to-two on purpose.

## 3. What this does not claim

- **Not a schema.** The ТЗ's `common_metadata` block (§9) applies across object types and is a
  separate shortfall; this maps identity, not shape.
- **Not a completeness proof.** Twelve built of twenty-four is a count of objects, not of coverage —
  `COVERAGE_MATRIX.md` §4 says the same thing about its own columns.
- **Not verified against the ТЗ** (§0).

## 4. Open items

- [ ] **Resolve 22 vs 24** against the master specification when it is available. Until then
      `SPEC_GAP_ANALYSIS.md` row 7 and this document disagree in public, which is the honest state.
- [ ] **`Policy` has no general form** (row 23). `ExitPolicy` is one instance and the mode rules are
      another; whether a Policy object is worth having is a question the first strategy card answers.
- [ ] **`Setup` and `Trigger` as separate objects with expiration** — `SPEC_GAP_ANALYSIS.md` row 19's
      shortfall, and rows 10 and 11 here are the same gap seen from the ontology's side.
