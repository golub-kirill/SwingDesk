"""The mechanical half of the AI authority model, which was prose until now.

`CHARTER.md` A-001 states the standing condition: **nothing is implemented before the authority
model is written and gated.** `AI_AUTHORITY_MODEL.md` §11 records that the prohibitions in §2, §3
and §3a are prose and that nothing enforces them, and §3a's own closing paragraph says the
vocabulary of its clauses 1 and 2 *"is mechanically checkable, and a guard for it is the
precondition for any implementation, not a later refinement."*

This is that guard. There is no agent in this system yet; the guard exists so that when one is
built, the check already exists and predates it.

**What it refuses, from `AI_AUTHORITY_MODEL.md` §3a:**

1. **The decision vocabulary** - `Trade` / `Watch` / `Skip` / `Pause`. Saying one IS deciding.
2. **The management vocabulary** - `HOLD`, `MOVE_STOP`, `PARTIAL_EXIT`, `EXIT_NOW`, `PAUSE`. Emitting
   one is PROPOSING, and a proposal is the deterministic path's to make. Without this clause the
   2026-08-24 amendment would permit by the back door what clause 1 forbids at the front.
3. **Originating a number** - no stop price, no share count, no target, no probability, no
   confidence. The agent MAY restate a number a component computed, carrying its provenance.

**Both vocabularies are READ FROM THEIR ENUMS, never retyped here.** `ActionKind` owns the
management words and `journal.DECISIONS` owns the decision words. A guard carrying its own copy
would be a second definition that drifts the first time one of them gains a member - the
one-logic-in-two-places failure this repository has paid for before. Adding a state to either enum
therefore extends this guard automatically.

**Numbers cannot be judged from text alone**, so the guard does not try. A numeral is permitted only
when the caller declares it as one the deterministic path produced (`restatable`). That puts the
burden where the authority model puts it: the agent restates with provenance or it says nothing.
A guard that guessed would be the silent-default this project refuses everywhere else.

**WHAT THIS CANNOT DO, and the limitation is now SMALLER than it was written.** §3a clause 1 forbids
the decision vocabulary *"and any synonym, paraphrase, translation, colour, emoji or score that maps
onto it one-to-one"*. This module and `AI_AUTHORITY_MODEL.md` §11 both said **none of that is
mechanically detectable**. That was an impossibility claim asserted without a test - `AGENTS.md` §15
- and it was measured on 2026-08-25 and is wrong for half of what it names. The six routes are not
one thing:

* **translation** - a FINITE set, and this project is written in two languages. `Пауза` and
  `Пропустить` map one-to-one onto the enum and were invisible only because `_tokens` matched
  `[A-Za-z_]+`. **Closed.**
* **emoji** - a finite set of verdict signals. **Closed.**
* **colour** - the one-to-one forms are PHRASES (`green light`, `red flag`), not bare colour words.
  **Closed for the phrases**, deliberately not for bare `green`, which is a chart line as often as
  a verdict.
* **score** - the NUMERIC form (`8/10`, `0.82`) was already refused by clause 3's numeral rule, so
  this route was never open. A verbal "score" is paraphrase, below.
* **synonym** - open-ended. A curated list would close the entries someone thought of and read as
  though it closed the class, which is worse than an honest hole.
* **paraphrase** - **genuinely undetectable by exact matching, and this is the real limitation.** An
  agent writing *"this one is ready to go"* passes every check here and has decided.

So the guard is still NECESSARY AND NOT SUFFICIENT, and A-001's standing condition is still not
discharged - but the hole is paraphrase and synonym, not "everything". A fact about the guard that
must travel with it rather than being discovered later. `AGENTS.md` §12: `unavailable` is not
`pass`.

**Every added table is checked against its enum by a test**, exactly as the two vocabularies are:
adding a state to `DECISIONS` or `ActionKind` without translating it turns those tests red. A
hand-authored mapping that could silently fall behind the enum would be the one-logic-in-two-places
failure this module's docstring already refuses.

Pure. No I/O, no clock.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from swingdesk.contracts.position import ActionKind
from swingdesk.journal_evidence.journal import DECISIONS

#: Any run of digits, with optional decimal part, sign, thousands separators, percent or currency.
#: Deliberately greedy: a guard that missed a number would permit exactly what clause 3 forbids, and
#: a false positive costs the caller one entry in `restatable`.
NUMERAL = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?%?")

#: Decision and management words in the OTHER language this project is written in. The course, the
#: ТЗ and the owner's instructions are Russian, so a Russian verdict is not an exotic case - it is
#: the likeliest way this guard would be walked past.
#:
#: Keyed by the enum member each translation maps onto, so `test_every_state_has_a_translation` can
#: assert coverage in both directions. Several forms per member because an agent writes prose, not
#: enum names: the infinitive, the noun and the imperative all say the same thing.
DECISION_TRANSLATIONS: dict[str, tuple[str, ...]] = {
    "Trade": ("торговать", "торгуем", "сделка", "торгуй"),
    "Watch": ("наблюдать", "наблюдаем", "наблюдение", "watchlist"),
    "Skip": ("пропустить", "пропускаем", "пропуск", "пропускай"),
    "Pause": ("пауза", "приостановить", "приостанавливаем"),
}

MANAGEMENT_TRANSLATIONS: dict[str, tuple[str, ...]] = {
    "HOLD": ("держать", "удерживать", "держим"),
    "MOVE_STOP": ("перенести стоп", "передвинуть стоп", "переносим стоп"),
    "PARTIAL_EXIT": ("частичный выход", "частично выйти", "частично закрыть"),
    "EXIT_NOW": ("выйти сейчас", "закрыть позицию", "выходим"),
    "PAUSE": ("пауза", "приостановить"),
}

#: Emoji that signal a verdict. Finite, unambiguous, and no reason for an advisory to carry one.
#: Not mapped to a specific decision on purpose: §3a forbids a signal that maps onto the vocabulary
#: one-to-one, and asserting WHICH one a red circle means would be a guess printed as a finding.
VERDICT_EMOJI = frozenset(
    "\U0001F7E2\U0001F534\U0001F7E1\U0001F7E0✅❌✔✖⛔\U0001F6A6"
    "\U0001F44D\U0001F44E\U0001F3AF\U0001F4A1⏸"
)

#: Colour used as a verdict. **Phrases only.** `green` alone is a chart line as often as a decision,
#: and a guard that refused it would be refusing the language the reports are written in - which is
#: how a check gets switched off rather than fixed.
COLOUR_PHRASES: tuple[str, ...] = (
    "green light", "green-light", "greenlight", "red light", "red-light",
    "red flag", "amber light", "traffic light", "зелёный свет", "зеленый свет",
    "красный флаг", "красный свет",
)


@dataclass(frozen=True, slots=True)
class GuardFinding:
    """One refusal, naming what was found and which clause it breaks."""

    clause: str
    token: str
    reason: str

    def __str__(self) -> str:
        return f"{self.clause}: {self.token!r} - {self.reason}"


def decision_words() -> frozenset[str]:
    """The decision vocabulary, from the journal's own enum."""
    return frozenset(word.casefold() for word in DECISIONS)


def management_words() -> frozenset[str]:
    """The management vocabulary, from `ActionKind`, in both its spellings.

    `ActionKind.MOVE_STOP` has the value `move_stop`, and an agent could write either. Both are the
    same act and both are forbidden, so both forms are matched.
    """
    words = set()
    for kind in ActionKind:
        words.add(kind.name.casefold())
        words.add(str(kind.value).casefold())
    return frozenset(words)


def _tokens(text: str) -> list[str]:
    """Word-ish tokens, keeping underscores so `move_stop` survives as one token.

    `[^\\W\\d]` is every word character that is not a digit - letters in ANY alphabet, plus the
    underscore. This read `[A-Za-z_]+` until 2026-08-25, which made every Cyrillic word invisible:
    `Пауза` was not merely unmatched, it was never tokenised. The test that was supposed to record
    that hole (`test_a_translated_decision_word_passes_too`) contained a Russian *paraphrase* and no
    translated decision word at all, so the route had never actually been exercised.
    """
    return re.findall(r"[^\W\d]+", text)


def check(text: str, *, restatable: Iterable[str] = ()) -> tuple[GuardFinding, ...]:
    """Every reason this text may not be emitted by an agent. Empty means the EXACT-TOKEN checks
    passed, which is not the same as "permitted" - see the module docstring.

    `restatable` is the set of rendered numbers the deterministic path produced and the agent is
    therefore allowed to repeat. Anything numeric outside it is originated.
    """
    allowed_numbers = {str(value).strip() for value in restatable}
    findings: list[GuardFinding] = []

    decisions = decision_words()
    managements = management_words()
    for token in _tokens(text):
        folded = token.casefold()
        # A token can belong to BOTH vocabularies and one does: `Pause` is a candidate decision and
        # an `ActionKind`. `DECISION_STATE_MACHINE.md` §3 warns that these enums share words for
        # different objects and must not be collapsed - so both clauses are reported rather than
        # whichever test ran first. Attributing an overlap to one clause would be a guess printed
        # as a finding.
        if folded in decisions:
            findings.append(GuardFinding(
                "AI_AUTHORITY_MODEL 3a.1", token,
                "the decision vocabulary - saying one IS deciding, which is human-only (A-001)",
            ))
        if folded in managements:
            findings.append(GuardFinding(
                "AI_AUTHORITY_MODEL 3a.2", token,
                "the management vocabulary - emitting one is PROPOSING, and a proposal is the "
                "deterministic path's to make (DR-013)",
            ))

    findings.extend(_translated(text))
    findings.extend(_signalled(text))

    for numeral in NUMERAL.findall(text):
        if numeral.strip() not in allowed_numbers:
            findings.append(GuardFinding(
                "AI_AUTHORITY_MODEL 3a.3", numeral,
                "a number the deterministic path did not produce. The agent may restate a computed "
                "value with its provenance; it may not originate one",
            ))

    return tuple(findings)


def _translated(text: str) -> list[GuardFinding]:
    """Decision or management words in the project's other language.

    §3a clause 1 forbids a *translation* that maps onto the vocabulary one-to-one, and a translation
    is a finite set - which is why this is checkable where paraphrase is not.
    """
    findings: list[GuardFinding] = []
    folded = {token.casefold() for token in _tokens(text)}
    lowered = text.casefold()

    for state, forms in DECISION_TRANSLATIONS.items():
        for form in forms:
            hit = form in lowered if " " in form else form in folded
            if hit:
                findings.append(GuardFinding(
                    "AI_AUTHORITY_MODEL 3a.1", form,
                    f"the decision vocabulary in translation - it maps one-to-one onto `{state}`, "
                    f"and deciding is human-only (A-001)",
                ))
                break

    for kind, forms in MANAGEMENT_TRANSLATIONS.items():
        for form in forms:
            hit = form in lowered if " " in form else form in folded
            if hit:
                findings.append(GuardFinding(
                    "AI_AUTHORITY_MODEL 3a.2", form,
                    f"the management vocabulary in translation - it maps one-to-one onto "
                    f"`{kind}`, and a proposal is the deterministic path's to make (DR-013)",
                ))
                break

    return findings


def _signalled(text: str) -> list[GuardFinding]:
    """A verdict carried by an emoji or a colour phrase rather than by a word.

    Both are finite sets. Neither is attributed to a PARTICULAR decision: §3a forbids a signal that
    maps onto the vocabulary one-to-one, and naming which one a red circle meant would be a guess
    printed as a finding - the same restraint the `Pause` overlap above is handled with.
    """
    findings: list[GuardFinding] = []
    for character in dict.fromkeys(text):
        if character in VERDICT_EMOJI:
            findings.append(GuardFinding(
                "AI_AUTHORITY_MODEL 3a.1", character,
                "a verdict carried by an emoji. §3a forbids a signal that maps onto the decision "
                "vocabulary one-to-one, whatever it is spelled with",
            ))
    lowered = text.casefold()
    for phrase in COLOUR_PHRASES:
        if phrase in lowered:
            findings.append(GuardFinding(
                "AI_AUTHORITY_MODEL 3a.1", phrase,
                "a verdict carried by a colour. Bare colour words are NOT refused - a chart line is "
                "green too - but this phrase says only one thing",
            ))
    return findings


def permitted(text: str, *, restatable: Iterable[str] = ()) -> bool:
    """`True` when no exact-token rule fires. **Never sufficient on its own** - the paraphrase route
    is undetectable and the module docstring says so."""
    return not check(text, restatable=restatable)
