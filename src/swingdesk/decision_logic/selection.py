"""The cross-sectional screen: which of the candidates that cleared every gate are actually taken.

**This is `CARD-001`'s entry trigger, and the card says why there is no other one.** A
cross-sectional rule *selects*; it does not wait for a price level. So membership of the selection
set at the close of the decision session IS the trigger, and until 2026-09-01 nothing computed it —
every candidate that cleared the caps ended the run as `Watch`, "sized; awaiting a trigger", for a
trigger that did not exist.

**Why it cannot live inside the candidate loop.** A rank is a property of the cross-section, not of
a candidate. The pipeline's loop decides one instrument at a time and cannot know a name's rank
until every name has been scored, which is why this runs once, after the loop, over the survivors.

**Everything here refuses rather than defaulting.** `ALLOCATION_SPEC` §6 rule 4: falling back to
whatever order the system happens to have is an alphabetical bias silently applied. An unset
parameter leaves every candidate at `Watch` naming the parameter, which is the fail-closed design
and is what the run did for every day of its life before this module existed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from swingdesk.decision_logic.ranking import Ranked

#: Cutoff rules `screen.relative_strength_rule` may name. One entry today, and the mapping exists so
#: a second is a registry edit that this module refuses until it is taught the rule - never a string
#: it silently fails to recognise.
TOP_DECILE = "top_decile"
CUTOFF_FRACTIONS: dict[str, Decimal] = {TOP_DECILE: Decimal("0.10")}

#: Ranking rules `rs.ranking_method` may name. `descending` is the only method both `PR-012` and
#: `PR-013` operationalised; the rankings themselves already return best-first.
DESCENDING = "descending"


@dataclass(frozen=True, slots=True)
class Refusal:
    """The screen could not run. Carries the parameter so a `Skip` can name it."""

    code: str
    reason: str
    parameter_id: str | None = None


@dataclass(frozen=True, slots=True)
class Selection:
    """Which instruments the screen takes, and the whole ordering it took them from.

    `ordered` is kept because a report that showed only the winners could not answer *why not me*
    for the 1,000 names that lost, and a rank is the only honest answer to that question.
    """

    selected: frozenset[str]
    ordered: tuple[str, ...]
    cutoff: int
    rule: str

    def rank_of(self, instrument_id: str) -> int | None:
        """1-based rank, or `None` for a name that was not in the cross-section at all."""
        try:
            return self.ordered.index(instrument_id) + 1
        except ValueError:
            return None


def select(
    ordered: list[Ranked],
    method: str,
    rule: str,
) -> Selection | Refusal:
    """Take the top slice of an already-ranked cross-section.

    `ordered` comes from a `decision_logic.ranking` implementation, which has already applied the
    score and the stable tiebreak. This function does not rank; it cuts. Keeping the two apart is
    what lets the cut be tested without a bar in sight.

    **The cutoff rounds UP.** A cross-section of 12 names at one decile is 1.2, and taking one name
    rather than two is the conservative reading: fewer positions, and the ratified book cap is what
    decides how many are actually taken anyway.
    """
    if method != DESCENDING:
        return Refusal(
            "DATA",
            f"rs.ranking_method is {method!r} and this system implements {DESCENDING!r}. A method "
            f"it does not recognise must refuse, never fall back to the order it happens to have "
            f"(ALLOCATION_SPEC 6 rule 4).",
            parameter_id="rs.ranking_method",
        )

    fraction = CUTOFF_FRACTIONS.get(rule)
    if fraction is None:
        return Refusal(
            "DATA",
            f"screen.relative_strength_rule is {rule!r} and this system implements "
            f"{', '.join(sorted(CUTOFF_FRACTIONS))}. An unrecognised cutoff refuses.",
            parameter_id="screen.relative_strength_rule",
        )

    names = tuple(candidate.instrument_id for candidate in ordered)
    if not names:
        # Not a refusal. A run whose gates admitted nobody has an empty cross-section, and that is
        # an ordinary quiet day rather than a fault.
        return Selection(frozenset(), (), 0, rule)

    cutoff = int(-(-len(names) * fraction // 1))  # ceil, on Decimal, without importing math
    cutoff = max(1, min(cutoff, len(names)))
    return Selection(frozenset(names[:cutoff]), names, cutoff, rule)
