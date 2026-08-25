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

**WHAT THIS CANNOT DO, and it is the load-bearing limitation.** §3a clause 1 forbids the decision
vocabulary *"and any synonym, paraphrase, translation, colour, emoji or score that maps onto it
one-to-one"*. **None of that is mechanically detectable**, and this guard does not pretend
otherwise: an agent writing *"this one is ready to go"* passes every check here and has decided.
So the guard is NECESSARY AND NOT SUFFICIENT - it closes the exact-token route and leaves the
paraphrase route open, which is a fact about the guard that must travel with it rather than being
discovered later. `AGENTS.md` §12: `unavailable` is not `pass`.

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
    """Word-ish tokens, keeping underscores so `move_stop` survives as one token."""
    return re.findall(r"[A-Za-z_]+", text)


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

    for numeral in NUMERAL.findall(text):
        if numeral.strip() not in allowed_numbers:
            findings.append(GuardFinding(
                "AI_AUTHORITY_MODEL 3a.3", numeral,
                "a number the deterministic path did not produce. The agent may restate a computed "
                "value with its provenance; it may not originate one",
            ))

    return tuple(findings)


def permitted(text: str, *, restatable: Iterable[str] = ()) -> bool:
    """`True` when no exact-token rule fires. **Never sufficient on its own** - the paraphrase route
    is undetectable and the module docstring says so."""
    return not check(text, restatable=restatable)
