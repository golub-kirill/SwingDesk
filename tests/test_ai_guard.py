"""The AI guard refuses what the authority model forbids, and admits what it cannot see.

`CHARTER.md` A-001 makes the guard a PRECONDITION for implementing anything in the authority model,
and `AI_AUTHORITY_MODEL.md` §11 recorded that the prohibitions were prose. These tests are what make
the guard a check rather than a second piece of prose.

The last two cases are the important ones: they assert what the guard **cannot** do. A guard whose
limits are only described in a docstring is a guard whose limits get forgotten.
"""

from __future__ import annotations

import pytest

from swingdesk.application import ai_guard
from swingdesk.contracts.position import ActionKind
from swingdesk.journal_evidence.journal import DECISIONS


@pytest.mark.parametrize("word", sorted(DECISIONS))
def test_every_decision_word_is_refused(word: str) -> None:
    """Parametrised over the ENUM, so a fifth decision state is covered the day it is added."""
    findings = ai_guard.check(f"I would {word} this one.")
    assert findings, word
    assert findings[0].clause.endswith("3a.1")


@pytest.mark.parametrize("kind", list(ActionKind))
def test_every_management_word_is_refused_in_both_spellings(kind: ActionKind) -> None:
    """`MOVE_STOP` and `move_stop` are the same act. An agent could write either."""
    for spelling in (kind.name, str(kind.value)):
        findings = ai_guard.check(f"Suggest {spelling} here.")
        assert findings, spelling
        assert any(f.clause.endswith("3a.2") for f in findings), (spelling, findings)


def test_a_word_in_BOTH_vocabularies_is_reported_under_both_clauses() -> None:
    """`Pause` is a candidate decision AND an `ActionKind`, and this test found that.

    `DECISION_STATE_MACHINE.md` §3 warns that these enums share words for different objects and must
    never be collapsed. Attributing an overlap to whichever clause was tested first would print a
    guess as a finding, so both are reported.
    """
    overlap = ai_guard.decision_words() & ai_guard.management_words()
    assert overlap, "if this ever empties, the test below is asserting nothing"
    for word in overlap:
        clauses = {f.clause for f in ai_guard.check(f"I would {word} it.")}
        assert {"AI_AUTHORITY_MODEL 3a.1", "AI_AUTHORITY_MODEL 3a.2"} <= clauses, (word, clauses)


def test_the_vocabularies_are_read_from_the_enums_not_retyped() -> None:
    """A guard carrying its own copy drifts the first time an enum gains a member.

    Asserted by comparing against the enums directly: if the guard ever hard-codes a list, this
    fails the moment the two disagree.
    """
    assert ai_guard.decision_words() == frozenset(w.casefold() for w in DECISIONS)
    assert {k.name.casefold() for k in ActionKind} <= ai_guard.management_words()
    assert {str(k.value).casefold() for k in ActionKind} <= ai_guard.management_words()


def test_an_originated_number_is_refused() -> None:
    """No stop price, no share count, no target, no probability, no confidence (§3a clause 3)."""
    findings = ai_guard.check("The level to watch is around 42.75.")
    assert any(f.clause.endswith("3a.3") and f.token == "42.75" for f in findings), findings


def test_a_number_the_deterministic_path_produced_may_be_restated() -> None:
    """The agent may repeat a computed value with its provenance - that is the permitted half."""
    assert ai_guard.permitted("ATR(14) is 4.2314 price units.", restatable=["14", "4.2314"])


def test_a_number_close_to_a_restatable_one_is_still_originated() -> None:
    """Rounding a computed value ORIGINATES a new one. `4.23` is not `4.2314`."""
    findings = ai_guard.check("ATR is about 4.23.", restatable=["4.2314"])
    assert any(f.token == "4.23" for f in findings), findings


def test_a_percentage_and_a_signed_number_are_both_caught() -> None:
    """The pattern is deliberately greedy: a missed numeral permits exactly what clause 3 forbids."""
    findings = ai_guard.check("Down -1.5% from there.")
    assert {f.token for f in findings} >= {"-1.5%"}, findings


def test_prose_that_originates_nothing_passes() -> None:
    """The positive control. A guard that refused everything would be trivially satisfied.

    This is the shape §3a permits: what bears on the position, and what the system cannot see.
    """
    assert ai_guard.permitted(
        "Earnings are scheduled inside the holding window, which the pipeline does not model."
    )


# --------------------------------------------------------- what the guard CANNOT do, asserted


def test_a_paraphrase_of_a_decision_passes_and_that_is_the_known_hole() -> None:
    """§3a clause 1 forbids synonyms, paraphrase, translation, colour, emoji and score.

    **Paraphrase is the genuine hole and this is what keeps it known.** The sentence below decides,
    and the guard says nothing. Three of the other five routes were closed on 2026-08-25 - see
    below - so the limitation is now paraphrase and open-ended synonym, not "everything".
    """
    assert ai_guard.permitted("This one is ready to go and the other is not worth it.")


def test_a_russian_paraphrase_passes_too_and_it_is_the_SAME_hole() -> None:
    """This test used to be called *"a translated decision word passes too"* and contained none.

    The sentence carries no member of the vocabulary in any language - it is the paraphrase case in
    Russian, which is the same hole one language over rather than a second one. The route it was
    named for had therefore never been exercised, and when it finally was (2026-08-25) the guard
    failed it: `_tokens` matched `[A-Za-z_]+`, so Cyrillic was never tokenised at all.
    """
    assert ai_guard.permitted("Этот кандидат подходит, а тот нет.")


# ------------------------- the routes that are NOT paraphrase, closed 2026-08-25
#
# `AI_AUTHORITY_MODEL.md` §11 and this module both said none of §3a clause 1's six routes was
# mechanically detectable. That was an impossibility claim with no test behind it (`AGENTS.md` §15),
# and it is wrong for the three that are FINITE SETS rather than open-ended language.


@pytest.mark.parametrize("state,forms", sorted(ai_guard.DECISION_TRANSLATIONS.items()))
def test_a_translated_decision_word_is_refused(state: str, forms: tuple[str, ...]) -> None:
    """A translation is a finite set, which is exactly why it is checkable where paraphrase is not."""
    for form in forms:
        findings = ai_guard.check(f"Мой вывод: {form}.")
        assert findings, (state, form)
        assert any(f.clause.endswith("3a.1") for f in findings), (state, form)


@pytest.mark.parametrize("kind,forms", sorted(ai_guard.MANAGEMENT_TRANSLATIONS.items()))
def test_a_translated_management_word_is_refused(kind: str, forms: tuple[str, ...]) -> None:
    """Clause 2 is the loophole clause 1 would otherwise leave open - in either language."""
    for form in forms:
        findings = ai_guard.check(f"Предлагаю {form}.")
        assert findings, (kind, form)


def test_every_decision_state_has_a_translation(  ) -> None:
    """The drift guard. A hand-authored table that could fall behind the enum is the
    one-logic-in-two-places failure the vocabularies themselves are read from enums to avoid.

    Adding a fifth decision state without translating it turns this red, which is the only thing
    that keeps the table honest as the enums grow.
    """
    missing = {word for word in DECISIONS if word not in ai_guard.DECISION_TRANSLATIONS}
    assert not missing, f"decision states with no translation entry: {sorted(missing)}"


def test_every_management_state_has_a_translation() -> None:
    """Same guard, one enum over."""
    missing = {k.name for k in ActionKind if k.name not in ai_guard.MANAGEMENT_TRANSLATIONS}
    assert not missing, f"ActionKind members with no translation entry: {sorted(missing)}"


def test_a_verdict_carried_by_an_emoji_is_refused() -> None:
    """§3a forbids a signal that maps onto the vocabulary one-to-one, whatever it is spelled with."""
    for emoji in ("🟢", "🔴", "✅", "⛔"):
        findings = ai_guard.check(f"Verdict: {emoji}")
        assert findings, emoji
        assert findings[0].clause.endswith("3a.1")


def test_an_emoji_finding_does_not_guess_WHICH_decision_it_meant() -> None:
    """Naming the decision a red circle stood for would be a guess printed as a finding.

    The same restraint the `Pause` overlap is handled with: report what was seen, never infer which
    of two objects it belonged to.
    """
    finding = ai_guard.check("Verdict: 🔴")[0]
    assert not any(word.casefold() in finding.reason.casefold() for word in DECISIONS)


def test_a_colour_PHRASE_is_refused() -> None:
    assert not ai_guard.permitted("This is a green light.")
    assert not ai_guard.permitted("I would call that a red flag.")


def test_a_BARE_colour_word_is_not_refused_and_that_is_deliberate() -> None:
    """A chart line is green too.

    A guard that refused the word would be refusing the language the reports are written in, and a
    check that fires on ordinary prose gets switched off rather than fixed (`CI_POLICY.md` §3).
    """
    assert ai_guard.permitted("the green line on the chart is the long moving average")
    assert ai_guard.permitted("the red candle closed below the stop level")


def test_a_numeric_score_was_already_refused_by_the_numeral_rule() -> None:
    """The "score" route in §3a was never open: clause 3 catches every numeric form of one.

    Recorded as a test rather than as a claim, because "it was already covered" is exactly the kind
    of sentence §15 says to check instead of asserting.
    """
    assert not ai_guard.permitted("Conviction: 8/10")
    assert not ai_guard.permitted("setup quality 0.82")
