# POINT-IN-TIME SPEC

**Status:** drafting · **Tier:** 3 (data) · **Content:** authored, required by tier 0 and 2

<!-- verbatim-sources: Appendix_A_Slovar_terminov_v2.0.pdf, Appendix_J_Ruchnoi_bektest_v2.0.pdf, Module_72_Istoricheskoe_testirovanie_v4.0.pdf -->

---

## 1. The requirement is definitional, not optional

The course defines the term and then forbids violating it. Appendix A:

> "Данные, действительно доступные на момент исторического решения."

Appendix J, the backtest protocol's second stage:

> "Скрыть будущие свечи; решения только по доступным данным."

And Appendix A again, naming the failure mode by name:

> "Искажение от исключения исчезнувших инструментов из истории."

M72 lists `Исключение look-ahead bias`, `Survivorship bias` and `Corporate actions` as required
controls, and the shared validation standard makes it an acceptance gate:
*"Вселенная, fundamentals и events доступны на дату решения"* → *"Нет survivorship/look-ahead
leakage."*

**No vendor at the $0 ceiling provides this.** Both measured sources overwrite rather than version,
and neither serves delisted instruments (`ADR-0001` conditions 2 and 6). So the system builds its
own point-in-time record going forward. That is the entire purpose of this document.

## 2. The bitemporal model

Every stored fact carries **two** times:

| Field | Meaning |
|---|---|
| `event_time` | when the fact was true — the bar's session date/time, the earnings date, the split date |
| `knowledge_time` | when **we** learned it — the moment of the fetch that produced this value |

A query is always *"the best value for `event_time` T that was known at `knowledge_time` K"*.
Backtests set K to the decision bar; live sets K to now. **There is no third mode**, and no query
that ignores `knowledge_time` — that is how look-ahead gets in.

**Revisions are inserts.** A changed value is a new row with a later `knowledge_time`, never an
update. The prior value stays readable forever, because a backtest run last month must still
reproduce.

### 2.1 Two times are a collapse of eight, and the collapse is only safe for bars

The full model distinguishes **eight** instants (master ТЗ §12):

| Time | Meaning |
|---|---|
| `event_time` | when the event occurred in the world |
| `observation_time` | when the value became observable |
| `publication_time` | when the source published it |
| **`available_time`** | **when it became available to us — the one that decides admissibility** |
| `ingestion_time` | when the system accepted it |
| `processing_time` | when processing finished |
| `decision_time` | when the system decided |
| `execution_time` | when the decision was executed |

The rule that matters: a decision at `decision_time = T` may use only values with
`available_time ≤ T`. A report published at 16:05, transmitted at 16:05:07 and processed at
16:05:12 **may not** inform a decision stamped 16:05:00.

**This store implements two of the eight, and that has cost nothing so far — because the subject is
daily bars.** For a bar, `event_time` is the session, and observation, publication and availability
all collapse onto the session close: the bar is knowable the moment the session ends and not before.
`knowledge_time` then carries the whole right-hand side of the table. The collapse is correct, not
lazy.

**It stops being correct the moment a non-bar source arrives.** For an earnings date, an SEC filing
or a news item, `publication_time` and `available_time` genuinely differ — a filing published at
16:05 may reach a free feed minutes or hours later, and a *scheduled* earnings date is known long
before the earnings themselves occur. Collapsing those onto one field silently grants look-ahead.

So this is a **latent** defect, not a live one: nothing in the tree reads a non-bar source today
(`EVENT_SPEC.md` §4 — there is no event feed at all). The obligation is recorded here so that
whoever wires the first non-bar source extends the model *before* using it, rather than discovering
the gap from an unreproducible result.

**`available_time` is the field to add first**, because it is the only one of the six missing that
a correctness rule references directly.

## 3. Revision deltas, not snapshots

The naive implementation of §2 — write everything you fetched — is unworkable, and specifically
unworkable *because of how Yahoo behaves*: a refetch rewrites the full adjusted history, so
"append what came back" writes ~20 M rows every day (`NFR.md` §2).

**Rule: compare before writing.** A fetch writes a row only where the value differs from the current
known value, plus genuinely new bars.

| Event | Rows written |
|---|---|
| ordinary day | ~1,500 new daily bars + new intraday |
| corporate action on one instrument | that instrument's adjusted history rewritten |
| vendor-wide re-adjustment | large, and **visible** — an unexplained mass revision is a data-quality alarm, not a routine write |

That last line is a benefit, not a cost: with delta storage, a vendor quietly re-adjusting the world
shows up as a spike in revision volume. With snapshot storage it would be invisible.

## 4. Raw and adjusted are separate series

Stored independently, never one derived from the other on read:

| Series | Property |
|---|---|
| `raw` | what traded. Immutable in principle — a raw bar should never change. |
| `adjusted` | raw restated for splits and dividends. **Mutable by nature** — every corporate action rewrites history behind it. |
| `actions` | the split and dividend records themselves, with their own `knowledge_time`. |

**A raw bar that changes is a data-quality event**, not a routine revision. It means the vendor
corrected a print, or is wrong now, or was wrong before. It raises `DATA`.

Which series a component reads is part of its specification (`ALGORITHM_SPEC.md`), not a runtime
choice. Getting this wrong is silent: indicators on adjusted series are comparable across time,
liquidity checks on adjusted dollar volume are not.

## 5. Snapshots and runs

A **snapshot** is a named `knowledge_time` — a pinned point in the revision history, not a copy of
the data.

- Every run records its snapshot id in the manifest.
- Re-running against the same snapshot reproduces byte-identically (`criteria.yml` `a.reproducible`).
- Comparisons between strategy variants must use **one snapshot for both legs**. Comparing across
  snapshots compares data revisions as much as strategies.

That last rule is not theoretical. It is the single discipline that a prior project had to retrofit
after a verdict was retracted, and it is cheap here only because the bitemporal store exists from
the start.

## 6. Universe membership is a point-in-time fact

The A-tier universe is recomputed daily from a liquidity rule (`CONSTRAINTS.md` §6). Membership on
date D **is itself a fact with an `event_time` and a `knowledge_time`**, stored like any other.

A backtest on date D uses the membership computed from data available at D — never today's
membership. Using today's list is exactly the survivorship mechanism the course names, and it would
be self-inflicted, unlike the delisting gap which is imposed by the vendor.

**Implemented 2026-08-03.** `reference_data.directory.DirectoryStore` holds symbol-directory pulls
and reads them as-of; `application.universe.select` joins them with as-of bars and applies the
DR-003 rule. The store differs from `BarStore` in one deliberate way: **a pull is a complete
snapshot, not a set of independent facts**, so `as_of` reads the latest pull at or before K rather
than the union of everything known by K. Unioning would keep a symbol in the universe forever after
it stopped being listed — manufacturing survivorship bias in the store that is supposed to bound it.

That choice buys the one thing free data can still give us: `departures()` reports what was in an
earlier pull and is absent from a later one. It is the **only survivorship evidence this project can
ever collect**, it only ever looks forward, and it is an observation rather than a delisting — a
ticker change looks identical from here. Recording it costs one directory pull; not recording it
loses the evidence permanently.

## 7. What we still cannot fix

Stated plainly so it is never mistaken for solved:

| Gap | Status |
|---|---|
| Delisted instruments have no history on either free source | **permanent at $0** — measured on Yahoo and Questrade |
| Vendor revisions before our first fetch | unrecoverable — our record starts the day we start |
| Vendor point-in-time fundamentals | unavailable |

Consequence: **every backtest result carries a survivorship-bias marker** (`criteria.yml`
`b.survivorship_caveat`), and results from before this system's first fetch cannot claim
point-in-time correctness at all — only results going forward can.

## 8. Storage shape

Requirements rather than a schema; the schema belongs in `contracts/`.

- Append-only. No `UPDATE`, no `DELETE` on fact tables.
- `(instrument, series, interval, event_time, knowledge_time)` uniquely identifies a row.
- As-of queries must be efficient — the common query is "latest value per `event_time` where
  `knowledge_time <= K`", and it runs on every bar of every backtest.
- Retention: indefinite. The revision history *is* the point-in-time record; pruning it destroys
  reproducibility.

## 9. Open items

- [ ] Whether raw and adjusted are separate tables or one table with a `series` discriminator.
      Depends on the storage engine choice (`ARCHITECTURE.md` §7 open item).
- [ ] Tolerance for "a value differs" on floats — an exact comparison will produce spurious revisions
      from vendor float noise. Needs a stated epsilon per series, in `DATA_QUALITY_SPEC.md`.
- [ ] Whether the second source is stored as its own series (enabling conflict detection over
      history) or consulted only live. Storing it doubles volume but makes disagreements auditable
      after the fact.
