"""Fill the pre-trade checklist from a run.

`CHARTER.md` §4 requires the pre-trade checklist generated with its machine-verifiable items
pre-filled. This is that generator, and its most important property is what it refuses to claim.

`CHECKLIST_SPEC.md` §1 says twelve of Appendix E's eighteen items are machine-checkable "given the
data the system already holds". The system does not hold all of that data yet. Rather than tick the
items anyway or quietly demote them to human questions, each evaluator returns `UNAVAILABLE` and
names what is missing — so the checklist reports the truth about the system as well as about the
candidate.

Five of eighteen are genuinely answerable today. That number is meant to be read, and to go up.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from swingdesk.application.universe import UniverseSelection
from swingdesk.contracts.checklist import Checklist, ChecklistItem, ItemState
from swingdesk.contracts.reference import Instrument
from swingdesk.journal_evidence.journal import DecisionRecord
from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.trade_management.sizing import Refusal, RiskSnapshot

REGISTRY = Path(__file__).resolve().parents[3] / "registry" / "checklists.yml"

#: What an evaluator is handed. Heterogeneous by nature - a risk snapshot, a decision,
#: an exit policy and a universe selection have nothing in common but the run.
Context = dict[str, Any]
Evaluator = Callable[[Context], tuple[ItemState, str]]


@lru_cache(maxsize=4)
def _load_items(appendix: str = "E") -> list[dict[str, Any]]:
    """The checklist definition for one appendix, parsed once per process.

    Cached because `generate` is called per candidate and this re-read and re-parsed the whole
    registry every time - 50 ms x 1,141 candidates, for a file that cannot change mid-run. The
    caller only ever reads the items, so handing out the same list is not a shared-mutable-state
    hazard; a caller that mutated it would be a defect either way.
    """
    import yaml

    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return [item for item in data["items"] if item["appendix"] == appendix]


def _instrument_identity(context: Context) -> tuple[ItemState, str]:
    instrument = context["instrument"]
    if instrument.ticker and instrument.exchange and instrument.currency:
        return ItemState.PASS, (
            f"{instrument.ticker} · {instrument.exchange.value} · {instrument.currency}"
        )
    return ItemState.FAIL, "one of ticker, exchange or currency is missing"


def _risk_recomputed(context: Context) -> tuple[ItemState, str]:
    risk = context["risk"]
    if risk is None:
        return ItemState.UNAVAILABLE, "sizing did not run for this candidate"
    if isinstance(risk, Refusal):
        return ItemState.FAIL, f"sizing refused: {risk.code} {risk.reason}"
    return ItemState.PASS, (
        f"recomputed this run: {risk.shares} shares, risk/share {risk.risk_per_share}"
    )


def _time_stop_recorded(context: Context) -> tuple[ItemState, str]:
    policy = context.get("exits")
    if policy is None:
        return ItemState.UNAVAILABLE, "no exit policy was supplied to the run"
    return ItemState.PASS, (
        f"time stop {policy.max_holding_bars} bars; protective stop "
        f"{policy.atr_stop_multiple}xATR. Targets and trailing are NOT set - two of the course's "
        f"four exit slots are unimplemented (EXIT_MODEL_SPEC)"
    )


def _universe_membership(context: Context) -> tuple[ItemState, str]:
    """E02: is this instrument in the admissible trading universe?

    Answerable only when the run built one. An explicit ticker list is not a universe, and reporting
    PASS because the operator typed the symbol would make the item mean "you asked for it".

    A partial universe still answers this item. Coverage bounds which OTHER symbols might qualify;
    it does not weaken the measurement on a symbol that was measured. The caveat is printed anyway,
    because a member of a 40-name universe and a member of a 4,000-name one are different facts.
    """
    selection = context.get("universe")
    if selection is None:
        return ItemState.UNAVAILABLE, (
            "this run took an explicit instrument list, so no universe was constructed. "
            "`swingdesk scan --universe` applies the DR-003 liquidity rule"
        )

    instrument = context["instrument"]
    member = selection.by_id.get(instrument.id)
    rule = selection.rule
    if member is None:
        return ItemState.FAIL, (
            f"not admitted by the DR-003 rule as of {selection.as_of:%Y-%m-%d}: requires close "
            f">= {rule.min_price}, {rule.adtv_window}d ADTV >= {rule.min_adtv:,.0f} and "
            f"{rule.min_history} bars of history"
        )

    note = (
        f"admitted: close {member.close}, {rule.adtv_window}d ADTV {member.adtv:,.0f} "
        f"(floor {rule.min_adtv:,.0f}), {member.bars} bars. "
        f"Universe of {len(selection.members)} as of {selection.as_of:%Y-%m-%d}"
    )
    if selection.is_partial:
        note += (
            f"; PARTIAL - bars stored for {selection.measured} of {selection.eligible} eligible "
            f"symbols, so this universe is a subset of the rule's answer"
        )
    if selection.capped_from is not None:
        note += f"; capped to {len(selection.members)} of {selection.capped_from} by dollar volume"
    return ItemState.PASS, note


def _no_skip_condition(context: Context) -> tuple[ItemState, str]:
    decision = context.get("decision")
    if decision is None:
        return ItemState.UNAVAILABLE, "the candidate has no decision yet"
    if decision.decision == "Skip":
        return ItemState.FAIL, f"skipped: {decision.reason_code} {decision.reason}"
    return ItemState.PASS, f"no skip condition fired; decision {decision.decision}"


class Unavailable:
    """An item the system cannot answer, and the registry facts that reason rests on.

    `blocked_by` maps a parameter id to the status it must still have for `reason` to be true. It
    is not documentation: gate 32 reads it and goes red the day the registry disagrees, so a reason
    cannot outlive the fact it cites. That is the failure `AGENTS.md` §12 names as this repository's
    most persistent one - a citation correct when written, still standing after the cited fact moved
    - and the pre-trade checklist is where it costs the most, because a stale reason keeps an item
    `UNAVAILABLE` after the thing blocking it was supplied.

    An empty mapping is honest rather than exempt: the blocker is a missing capability, not a
    parameter, and the gate names those every run instead of passing over them.
    """

    def __init__(self, reason: str, blocked_by: Mapping[str, str] | None = None) -> None:
        self.reason = reason
        self.blocked_by: Mapping[str, str] = dict(blocked_by or {})

    def __call__(self, _context: Context) -> tuple[ItemState, str]:
        return ItemState.UNAVAILABLE, self.reason


#: Evidence key -> evaluator. Every key in registry/checklists.yml must appear here, and the ones
#: that are not yet answerable say exactly which machinery is missing rather than being omitted.
EVALUATORS: dict[str, Evaluator] = {
    "instrument_identity": _instrument_identity,
    "universe_membership": _universe_membership,
    "risk_recomputed": _risk_recomputed,
    "time_stop_recorded": _time_stop_recorded,
    "no_skip_condition": _no_skip_condition,

    "data_freshness": Unavailable(
        "session completeness is checked, but corporate actions are not - and this item requires "
        "both. Half an answer is not an answer. The blocker is a capability rather than a value: "
        "DR-016 fetches actions for HELD names only, so a candidate has none"
    ),
    "regime_recorded": Unavailable(
        "the regime classifier exists (M30-T0450) and is not wired into the daily run; "
        "regime.breadth_cutoffs is unset",
        {"regime.breadth_cutoffs": "unset"},
    ),
    "sector_benchmark": Unavailable(
        "a sector is now known for a classified instrument (DR-006 12) and this item needs more "
        "than that: comparing a candidate to its sector requires a BENCHMARK series per sector, "
        "and no sector-to-index mapping exists. The classification is also today's, not the one "
        "in force on an older date. The blocker is that missing mapping, which is a registry "
        "table nobody has authored rather than a parameter anyone can set"
    ),
    "trigger_not_late": Unavailable(
        "the run has no trigger and no maximum entry, so `Late` is not computable (CODES LATE). "
        "The trigger is screen.breakout_definition and its pullback and contraction siblings, all "
        "unset and all needing a pre-registration; the ceiling is entry.maximum_entry_atr, which "
        "DR-020 3 authored and deliberately left unset",
        {
            "screen.breakout_definition": "unset",
            "screen.pullback_definition": "unset",
            "screen.contraction_definition": "unset",
            "entry.maximum_entry_atr": "unset",
        },
    ),
    "entry_zone_recorded": Unavailable(
        "entry is recorded; maximum entry is not, and this item requires both. "
        "entry.maximum_entry_atr is the value it waits on",
        {"entry.maximum_entry_atr": "unset"},
    ),
    "event_proximity": Unavailable(
        "no event calendar is wired, AND the course supplies no buffer to apply if one were: "
        "M34/M40 give one criterion for all 20 catalyst types and no lead time at all (EVENT_SPEC). "
        "screen.earnings_buffer_days needs a decision record or a study, not a transcription",
        {"screen.earnings_buffer_days": "unset"},
    ),
    "liquidity_acceptable": Unavailable(
        "dollar volume is computable from stored bars; spread and expected slippage are not "
        "observable on free data (costs.slippage_model is a MODEL, not a measurement)",
        {"costs.slippage_model": "assumed"},
    ),
    "exposure_within_limits": Unavailable(
        "open risk, correlation to the book and sector are all enforced at step 6 - but sector "
        "only for a candidate whose classification has been fetched, and the CURRENCY and EVENT "
        "buckets this item also requires are not enforced at all. Half an answer is not an answer. "
        "The currency bucket waits on account.fx_rate_cad; the event bucket waits on the same "
        "absent calendar as E11",
        {"account.fx_rate_cad": "unset"},
    ),
}


def generate(
    instrument: Instrument,
    run_id: str,
    generated_at: datetime,
    *,
    risk: RiskSnapshot | Refusal | None = None,
    decision: DecisionRecord | None = None,
    exits: ExitPolicy | None = None,
    universe: UniverseSelection | None = None,
    appendix: str = "E",
) -> Checklist:
    """One filled pre-trade checklist for one candidate."""
    context = {
        "instrument": instrument,
        "risk": risk,
        "decision": decision,
        "exits": exits,
        "universe": universe,
    }

    items: list[ChecklistItem] = []
    for row in _load_items(appendix):
        key = row.get("evidence")
        if not key:
            items.append(ChecklistItem(id=row["id"], text=row["text"], state=ItemState.HUMAN))
            continue
        evaluator = EVALUATORS.get(key)
        if evaluator is None:
            raise KeyError(
                f"{row['id']} names evidence {key!r} with no evaluator. Every key in "
                f"registry/checklists.yml must be answerable or explicitly unavailable."
            )
        state, note = evaluator(context)
        items.append(ChecklistItem(id=row["id"], text=row["text"], state=state, note=note))

    return Checklist(
        appendix=appendix,
        instrument_id=instrument.id,
        run_id=run_id,
        generated_at=generated_at,
        items=tuple(items),
    )


def machine_coverage(appendix: str = "E") -> tuple[int, int]:
    """(answerable today, total). Reported so the gap is a number rather than an impression.

    Counts what the SYSTEM can answer, not what a given run did answer. E02 is answerable because
    the universe path exists; a run that took an explicit ticker list still reports it `unavailable`,
    and that is a property of the run rather than a missing capability.
    """
    rows = _load_items(appendix)
    answerable = sum(
        1 for row in rows
        if row.get("evidence") and EVALUATORS.get(row["evidence"]) is not None
        and not isinstance(EVALUATORS[row["evidence"]], Unavailable)
    )
    return answerable, len(rows)


__all__ = ["EVALUATORS", "Unavailable", "generate", "machine_coverage"]
