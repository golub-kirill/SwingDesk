"""The refusal funnel: what happened to a run's candidates, aggregated (US-022).

`report.py` already prints one block per candidate and a footer that says only `decisions <n>`. On
an ordinary day that is over a thousand near-identical blocks whose only information is the handful
that differ and whatever changed since yesterday - and the count that summarised them was one number
that could not distinguish a quiet day (nothing triggered) from a broken one (a parameter went
unset, a source went stale). This module is the summary that can.

Nothing here is a new measurement. Every count is read from `RunResult` / `UniverseSelection` -
never recomputed by a different rule - so the funnel and the per-instrument blocks it summarises can
never disagree about anything this module does not itself compute.

Pure. No I/O, no clock, no registry reads - the same purity boundary as `trade_management.manage`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from swingdesk.application.pipeline import RunResult


@dataclass(frozen=True, slots=True)
class SkipCause:
    """One reason a batch of candidates did not proceed.

    `code` alone is not always one cause. `RISK` covers two things `size_long` already tells
    apart: an unset parameter (`parameter_id` is set - a SYSTEM fault, and the run cannot be
    trusted until it is fixed) and a position sized to zero shares (`parameter_id` is None - a
    fact about the account, not the market). Grouping by `(code, parameter_id)` keeps them
    separate rather than collapsing both into one `RISK` count, which is exactly how 1131
    unset-parameter refusals once read as an ordinary quiet day.
    """

    code: str
    parameter_id: str | None
    count: int


@dataclass(frozen=True, slots=True)
class Funnel:
    """One run's candidates, aggregated by what happened to them.

    `eligible` / `measured` / `admitted` are 0 when the run carries no `UniverseSelection` (an
    explicit instrument list with no rule behind it) - there is no rule stage to report, not a
    rule that admitted nobody.

    `admitted` and `evaluated` coincide except when the caller passes an explicit instrument list
    alongside a universe - the documented case in `pipeline.run` where a held position that has
    fallen out of the rule is still evaluated. `evaluated` is always `len(outcomes)` and is the
    number the reconciliation below is checked against, because it is the one count nothing else
    can disagree with.
    """

    eligible: int
    measured: int
    admitted: int
    evaluated: int
    trade: int
    watch: int
    skip: int
    pause: int
    unaccounted: int
    skip_causes: tuple[SkipCause, ...]
    changed: int
    first_sighting: int

    @property
    def is_reconciled(self) -> bool:
        """Every evaluated candidate falls into exactly one bucket.

        Reported by the caller rather than asserted here (`HANDOFF.md` §8: verify before
        asserting) - a broken invariant belongs in the render where it is seen, not in an
        exception raised mid-run over a report that has already done its job.
        """
        return self.evaluated == (
            self.trade + self.watch + self.skip + self.pause + self.unaccounted
        )


def funnel(result: RunResult) -> Funnel:
    """Aggregate one run's decisions. Reads only what `result` already carries."""
    selection = result.universe
    eligible = selection.eligible if selection is not None else 0
    measured = selection.measured if selection is not None else 0
    admitted = len(selection.members) if selection is not None else len(result.outcomes)

    decided = [outcome.decision for outcome in result.outcomes if outcome.decision is not None]
    unaccounted = sum(1 for outcome in result.outcomes if outcome.decision is None)
    by_decision = Counter(record.decision for record in decided)

    skip_tally: Counter[tuple[str, str | None]] = Counter()
    for record in decided:
        if record.decision == "Skip":
            skip_tally[(record.reason_code or "", record.parameter_id)] += 1
    # Most common first - the reader wants the dominant cause on top, not alphabetical order.
    skip_causes = tuple(
        SkipCause(code=code, parameter_id=parameter_id, count=count)
        for (code, parameter_id), count in sorted(
            skip_tally.items(), key=lambda item: item[1], reverse=True
        )
    )

    changed = sum(
        1
        for record in decided
        if record.previous_decision is not None and record.previous_decision != record.decision
    )
    first_sighting = sum(1 for record in decided if record.previous_decision is None)

    return Funnel(
        eligible=eligible,
        measured=measured,
        admitted=admitted,
        evaluated=len(result.outcomes),
        trade=by_decision.get("Trade", 0),
        watch=by_decision.get("Watch", 0),
        skip=by_decision.get("Skip", 0),
        pause=by_decision.get("Pause", 0),
        unaccounted=unaccounted,
        skip_causes=skip_causes,
        changed=changed,
        first_sighting=first_sighting,
    )


__all__ = ["Funnel", "SkipCause", "funnel"]
