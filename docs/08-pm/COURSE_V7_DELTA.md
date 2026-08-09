# COURSE v7.0 DELTA — measured, not adopted

**Status:** owner-pending · **Tier:** 8 (project management) · **Content:** authored, measured against the tree

A rebuilt course exists on disk and **this project does not use it.** Owner ruling, 2026-08-09:
*v7.0 is still a young version, work is still ongoing.* `v5.0`/`v4.0` remains canonical and
`registry/course_index.yml` is unchanged.

This file exists because the delta is large enough that a future session will find it, and finding
it without this record costs either a wasted re-derivation or — worse — an adoption nobody decided
on. Everything below was measured on 2026-08-09, not remembered.

```
source     Swing_Trading_Course_Canada_USA_v7.0_2026-08-08/
indexed    Swing_Trading_Course_Fixed/Swing_Trading_Course_Charts_Layout_Fixed_Verified/PDF/
```

---

## 1. What v7.0 is

96 modules and 20 appendices, 116 files, 5,307 pages. Its own `QA_REPORT.json` reports
`status: PASS`, `issue_count: 0`, and `production_rules: v3.8` — the same production rules the
indexed course was built to.

**The topic set is identical.** 1,379 topics in both, and the id sets match exactly: no topic was
added, none removed, none renumbered. That matters, because it means every `M##-T####` citation in
`docs/` still resolves under v7.0. The citations are safe. What changed is everything those
citations point *at*.

## 2. The delta, measured

| Field | Topics changed | Share |
|---|---|---|
| `claim_type` | **1,089** | 79.0% |
| `validation` | **1,143** | 82.9% |
| `stage` | 888 | 64.4% |
| `layer` | 413 | 30.0% |

Claim-type distribution, indexed → v7.0:

| Claim type | Indexed | v7.0 |
|---|---|---|
| Definition | 916 | **70** |
| Operational Course Rule | 173 | **599** |
| Derived Observation | 121 | **396** |
| Untested Hypothesis | 124 | **314** |
| Inference | 45 | **0** |

Validation: `Not Applicable` 1,209 → **70**; `Untested` 170 → **1,309**.

The `Inference` claim type does not exist in v7.0. `README.md` publishes the indexed distribution
as a headline figure, so that table is a v5.0/v4.0 fact and should not be quietly refreshed.

## 3. Why this is not a cosmetic re-render

**3.1 The component registry would roughly triple.** `tools/build_components.py` emits a row for
every non-Definition topic (owner decision D2, full-catalogue coverage). Indexed that is 463
computable topics and 465 rows. Under v7.0 it is **1,309** — the Definition class, which absorbed
most of the catalogue, is nearly gone.

**3.2 All seven `specified` components change classification.** Every one moves
`Not Applicable` → `Untested`, and five change claim type:

| Topic | Name | Claim type, indexed → v7.0 |
|---|---|---|
| `M12-T0201` | Предыдущий максимум | Operational Course Rule → Derived Observation |
| `M12-T0202` | Предыдущий минимум | Operational Course Rule → Derived Observation |
| `M18-T0280` | ATR в долларах | unchanged (Derived Observation) |
| `M25-T0382` | SMA | unchanged (Derived Observation) |
| `M30-T0450` | Определение текущего режима | Definition → Derived Observation |
| `M31-T0459` | Доля акций выше средних | Definition → Derived Observation |
| `M33-T0485` | Фильтр по тренду | Operational Course Rule → **Untested Hypothesis** |

Each component mirrors its `validation` into a `ComponentSpec` in code because the pure packages
cannot read the registry. Adopting v7.0 edits all seven mirrors. `src/swingdesk/derived_observations/atr.py`
already carries a comment about correcting exactly this field once.

The last row is worth stating plainly: **v7.0 independently reclassifies the trend filter as an
untested hypothesis**, which is where PR-001 and PR-005 put it on this project's own evidence. The
course and the studies agree, and they got there separately.

**3.3 Body text is rewritten, so `verbatim` transcriptions do not survive.** The topic bodies are
not the same prose. Worked example — `M30-T0450`, quoted in PR-002's second amendment:

> добавленная ценность проверяется против простой базовой модели

That sentence occurs **8 times** in the indexed `Module_30_..._v5.0.pdf` and **0 times** in
`Module_30_..._v7.0.pdf`; the word `измеритель` is absent from the v7.0 module entirely.

The consequence is specific and uncomfortable. PR-002's second amendment used that sentence to
reclassify the random-partition baseline from an authored design choice to a course requirement.
Under v7.0 that grounding does not exist. **The study's design is unaffected — the baseline is
still the right design — but its provenance claim would revert to authored.** PR-002 is the only
accepted study in the project, so this is the single most consequential line in this document.

More broadly: 30 documents declare `verbatim-sources` and gate 2 re-extracts 393 quotes from them.
Every declaration names a versioned filename (`..._v5.0.pdf`), so under v7.0 the gate would not
match a stale quote — it would fail to find the source file at all. Adoption means re-transcribing
all 393, not spot-checking them.

**3.4 v7.0 supplies mechanisms the indexed course does not.** The founding premise recorded in
`AGENTS.md` — the course "supplies a complete governance and taxonomy specification and **zero
numeric thresholds**" — is true of v5.0/v4.0 and is **not** true of v7.0. `M72-T1082`
(`Проскальзывание`) is the clearest case. Indexed, it is a Definition whose body is generic
boilerplate with no formula. In v7.0 it is an Operational Course Rule carrying a computation:

```
Slippage bps = signed(fill-reference)/reference x 10,000
```

and it requires that slippage be measured against a predeclared reference and modelled *separately
from commission and spread*.

`DR-004` folds spread into a single 5bp slippage term. That is a defensible modelling choice under
the indexed course, which says nothing on the point. Under v7.0 it is a conflation the source
explicitly separates. This does not invalidate `DR-004` today; it does mean the cost model is one
of the first things to revisit if v7.0 is adopted.

**3.5 It bears on `UDR-004`, which is open.** `ROADMAP.md` frames the regime-ontology decision as
the ТЗ's eight against the course's eleven (`REGIME_SPEC.md` §2). v7.0's `M30-T0450` names a
**third** list of seven — Bull, Bear, Sideways, Panic, Recovery, Mixed, Unknown — and unlike the
eleven it reads as a partition, with `Unknown` as the fail-closed state. Anyone answering `UDR-004`
should know a third candidate exists before choosing between two.

## 4. What adoption would require

Not a re-run of `build_course_index.py`. In order:

1. An owner decision that v7.0 is stable enough to be the requirements source.
2. Re-transcribe all 393 `verbatim` quotes across 30 documents against v7.0 filenames, and update
   every `verbatim-sources` declaration. Gate 2 fails loudly until this is done, which is correct.
3. Regenerate `course_index.yml` and `components.yml`; expect ~465 → ~1,309 component rows. The
   builder preserves authored fields, so this is additive rather than destructive.
4. Update the seven `ComponentSpec` mirrors in `src/`.
5. Re-check `DR-004` against `M72-T1082`'s formula, and `UDR-004` against the seven-regime list.
6. Re-examine every place the project states that the course supplies no mechanisms — `AGENTS.md`
   §0, `README.md`, `HANDOFF.md` §1. Under v7.0 that claim is false, and it is load-bearing prose,
   not a count.
7. Re-check PR-002's second amendment, per §3.3, and downgrade its provenance claim if the
   sentence is genuinely gone.

Steps 2 and 6 are the expensive ones, and 7 is the one most easily missed.

## 5. Reproducing this

The measurement is a scratch script, not a committed tool, because the project does not read v7.0
and a tool that does would imply otherwise. It parses the `STAGE / CLAIM TYPE / LAYER / VALIDATION /
COMPONENT` strip out of each v7.0 PDF's text layer with `pdftotext -enc UTF-8` and joins it to
`registry/course_index.yml` on topic number. Any reader can rebuild it from that description in
about thirty lines; the numbers in §2 are what it produced on 2026-08-09.

If v7.0 is adopted, this document is superseded by the migration rather than updated.
