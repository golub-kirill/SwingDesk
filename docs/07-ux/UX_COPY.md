# UX COPY

**Status:** drafting · **Tier:** 7 (UI/UX) · **Content:** authored, constrained by `registry/` and `contracts/`

Owner decision **D7**: the product is in English, while the source course is Russian. That makes
translation a standing risk rather than a one-off task — a term rendered two ways in two places
becomes two concepts, and the states in this system are enum members that a paraphrase silently
detaches from.

This document exists to say **which words are not writable**, and to set the tone for the ones that
are.

---

## 1. The controlled vocabulary — never paraphrased

These are enum members, not labels. Every surface renders them exactly as written, in any language
setting, and a synonym is a defect rather than a style choice.

| Set | Members | Owner |
|---|---|---|
| Candidate decision | `Trade` · `Watch` · `Skip` · `Pause` | `DECISION_STATE_MACHINE.md`, gate 2 |
| Checklist terminal | `Complete` · `Research` · `Pause` · `Skip` · `Error` | `contracts/checklist.py` |
| Checklist item state | `pass` · `fail` · `unavailable` · `human` | `contracts/checklist.py` |
| Watchlist status | `Research` · `Developing` · `Watch` · `Ready` · `Triggered` · `Trade` · `Late` · `Invalid` · `Skip` | `DECISION_STATE_MACHINE.md` |
| Module gate | `PASS` · `PAUSE` · `SKIP` | `DECISION_STATE_MACHINE.md` |
| Skip reasons | 12 codes: `DATA` `LIQ` `EVENT` `REGIME` `SECTOR` `LATE` `STOP` `RISK` `CORR` `BORROW` `TECH` `PSYCH` | `CODES.md` (Appendix N) |
| Error codes | 12 codes: `NO_PLAN` `CHASE` `NO_TRIGGER` `WIDE_STOP` `AVG_DOWN` `OVERSIZE` `CORRISK` `EARLY_EXIT` `LATE_EXIT` `REVENGE` `HINDSIGHT` `DATA_ERR` | `CODES.md` (Appendix O) |
| Management action | `hold` · `move_stop` · `partial_exit` · `exit_now` · `pause` | `contracts/position.py` |
| Parameter provenance | `unset` · `assumed` · `owner` · `validated` | `PARAMETER_REGISTRY.md` |
| Validation status | `Not Applicable` · `Untested` · … | `contracts/evidence.py` |

**Gate 2 checks eleven of these enums against their spec documents on every merge.** A member added
in code and not in the document, or the reverse, fails the build. That is why this table is a
pointer rather than a copy — a thirteenth hand-copy of `Trade/Watch/Skip/Pause` is a thirteenth
place for it to drift.

### Words that are close but are not synonyms

The pairs most likely to be conflated by a writer trying to vary the prose:

| Not interchangeable | Because |
|---|---|
| `Skip` / `Pause` | `Skip` rejects this candidate. `Pause` stops **new** activity and says nothing about the candidate |
| `Watch` / `Ready` | `Watch` has no trigger yet. `Ready` has one and is waiting for it to fire |
| `Late` / `Invalid` | `Late` means the setup was real and the price has moved past maximum entry. `Invalid` means the setup is gone |
| `unavailable` / `fail` | `unavailable` is a gap in the **system**. `fail` is a fact about the **trade**. Collapsing them is the single most damaging copy error this product can make |
| `assumed` / `validated` | `assumed` is a number someone chose with a citation. `validated` survived a pre-registered study. One is provenance, the other is evidence |
| proposal / action | Nothing this system emits is an action. D1 and D6 route every one through the owner |

## 2. Tone

Three rules, and they follow from the charter rather than from taste.

**Say what was checked, and what was not.** The pre-trade checklist prints its `unavailable` items
next to its passes on purpose. Copy that summarises them away — "12 checks passed" — converts a gap
in the system into a statement about the trade. Where a count is shown, the denominator is shown.

**Never imply an action was taken.** D1 means the system has no execute verb anywhere, and D6 routes
open-position changes through the owner. So: *"proposed: move_stop — NEEDS YOUR APPROVAL"*, never
*"stop moved"*. The run report already ends its proposals block with `Nothing has been done.` and
that sentence is load-bearing.

**A number without provenance is not shown.** Every displayed value carries its component version
and, where the input was `assumed`, says so adjacent to the number rather than in a footnote
(`PARAMETER_REGISTRY.md` §5). "ATR 2.41" alone is a claim this project has not earned.

## 3. The standing warning

The run report ends with this, and it is not boilerplate to be softened:

> Every setup in this system is Untested. A decision here means the components computed what their
> specs say — not that the trade has an edge.

It is accurate: **zero of 1379 course topics carry a tested validation status**, and one parameter in
96 is `validated`. Any copy that makes the product sound more confident than that is wrong on the
facts, not merely over-enthusiastic.

## 4. Russian in an English product

Three places where the source language legitimately survives into output, and one where it must not.

| Case | Rule |
|---|---|
| `verbatim` blocks in the documentation | stay Russian, always. They are evidence, and a translated quote is not a quote |
| Skip reasons and code descriptions in the report | may render Russian text from the transcription. `presentation/cli.py` forces UTF-8 output because a Windows console defaults to cp1252 and would crash exactly when the report has something to say |
| Enum members | English, from the tables in §1. The course writes `Trade`/`Watch`/`Skip`/`Pause` in Latin script itself |
| **Operator-facing prose** | English. Never a machine translation of a course sentence — if a concept needs explaining, it is written, and the Russian original is cited beside it |

## 5. Open items

- [ ] **`GLOSSARY.md` is the authority for term wording and this document must not restate it.**
      35 terms, transcribed verbatim from Appendix A and verified 2026-08-01, and it already says
      the definitions are identical across code identifiers, database columns, UI labels and
      documents. An earlier draft of this section claimed Appendix A was untranscribed — it is not,
      and the claim would have sent someone to redo finished work. The real gap is narrower: the
      glossary gives Russian definitions of English-named terms, so a *surface* string for each term
      is still unwritten. That is copy, not transcription.
- [ ] Error-code descriptions in `CODES.md` are partly Russian with an English column, and partly
      English only. Consistent, but only by accident — worth settling before a second surface reads
      them.
