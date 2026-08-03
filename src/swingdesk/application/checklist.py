"""Fill the pre-trade checklist from a run.

`CHARTER.md` §4 requires the pre-trade checklist generated with its machine-verifiable items
pre-filled. This is that generator, and its most important property is what it refuses to claim.

`CHECKLIST_SPEC.md` §1 says twelve of Appendix E's eighteen items are machine-checkable "given the
data the system already holds". The system does not hold all of that data yet. Rather than tick the
items anyway or quietly demote them to human questions, each evaluator returns `UNAVAILABLE` and
names what is missing — so the checklist reports the truth about the system as well as about the
candidate.

Four of eighteen are genuinely answerable today. That number is meant to be read, and to go up.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from swingdesk.contracts.checklist import Checklist, ChecklistItem, ItemState
from swingdesk.trade_management.sizing import Refusal

REGISTRY = Path(__file__).resolve().parents[3] / "registry" / "checklists.yml"


def _load_items(appendix: str = "E") -> list[dict]:
    import yaml

    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return [item for item in data["items"] if item["appendix"] == appendix]


def _instrument_identity(context: dict) -> tuple[ItemState, str]:
    instrument = context["instrument"]
    if instrument.ticker and instrument.exchange and instrument.currency:
        return ItemState.PASS, (
            f"{instrument.ticker} · {instrument.exchange.value} · {instrument.currency}"
        )
    return ItemState.FAIL, "one of ticker, exchange or currency is missing"


def _risk_recomputed(context: dict) -> tuple[ItemState, str]:
    risk = context["risk"]
    if risk is None:
        return ItemState.UNAVAILABLE, "sizing did not run for this candidate"
    if isinstance(risk, Refusal):
        return ItemState.FAIL, f"sizing refused: {risk.code} {risk.reason}"
    return ItemState.PASS, (
        f"recomputed this run: {risk.shares} shares, risk/share {risk.risk_per_share}"
    )


def _time_stop_recorded(context: dict) -> tuple[ItemState, str]:
    policy = context.get("exits")
    if policy is None:
        return ItemState.UNAVAILABLE, "no exit policy was supplied to the run"
    return ItemState.PASS, (
        f"time stop {policy.max_holding_bars} bars; protective stop "
        f"{policy.atr_stop_multiple}xATR. Targets and trailing are NOT set - two of the course's "
        f"four exit slots are unimplemented (EXIT_MODEL_SPEC)"
    )


def _no_skip_condition(context: dict) -> tuple[ItemState, str]:
    decision = context.get("decision")
    if decision is None:
        return ItemState.UNAVAILABLE, "the candidate has no decision yet"
    if decision.decision == "Skip":
        return ItemState.FAIL, f"skipped: {decision.reason_code} {decision.reason}"
    return ItemState.PASS, f"no skip condition fired; decision {decision.decision}"


def _unavailable(reason: str):
    def evaluate(_context: dict) -> tuple[ItemState, str]:
        return ItemState.UNAVAILABLE, reason
    return evaluate


#: Evidence key -> evaluator. Every key in registry/checklists.yml must appear here, and the ones
#: that are not yet answerable say exactly which machinery is missing rather than being omitted.
EVALUATORS = {
    "instrument_identity": _instrument_identity,
    "risk_recomputed": _risk_recomputed,
    "time_stop_recorded": _time_stop_recorded,
    "no_skip_condition": _no_skip_condition,

    "universe_membership": _unavailable(
        "the run takes an explicit instrument list; the DR-003 liquidity rule is not applied as a "
        "universe filter yet (ROADMAP X1)"
    ),
    "data_freshness": _unavailable(
        "session completeness is checked, but corporate actions are not - and this item requires "
        "both. Half an answer is not an answer"
    ),
    "regime_recorded": _unavailable(
        "the regime classifier exists (M30-T0450) and is not wired into the daily run; "
        "regime.breadth_cutoffs is unset"
    ),
    "sector_benchmark": _unavailable(
        "Instrument.sector and .industry are None - no free point-in-time sector source is in hand"
    ),
    "trigger_not_late": _unavailable(
        "the run has no trigger and no maximum entry, so `Late` is not computable (CODES LATE)"
    ),
    "entry_zone_recorded": _unavailable(
        "entry is recorded; maximum entry is not, and this item requires both"
    ),
    "event_proximity": _unavailable(
        "no event calendar - screen.earnings_buffer_days is unset and no source is wired"
    ),
    "liquidity_acceptable": _unavailable(
        "dollar volume is computable from stored bars; spread and expected slippage are not "
        "observable on free data (costs.slippage_model is a MODEL, not a measurement)"
    ),
    "exposure_within_limits": _unavailable(
        "open risk is computable from the position store; sector, currency and event buckets are "
        "not - risk.max_sector_risk and friends are unset"
    ),
}


def generate(
    instrument,
    run_id: str,
    generated_at: datetime,
    *,
    risk=None,
    decision=None,
    exits=None,
    appendix: str = "E",
) -> Checklist:
    """One filled pre-trade checklist for one candidate."""
    context = {
        "instrument": instrument,
        "risk": risk,
        "decision": decision,
        "exits": exits,
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
    """(answerable today, total). Reported so the gap is a number rather than an impression."""
    rows = _load_items(appendix)
    answerable = sum(
        1 for row in rows
        if row.get("evidence") and EVALUATORS.get(row["evidence"]) is not None
        and getattr(EVALUATORS[row["evidence"]], "__name__", "") != "evaluate"
    )
    return answerable, len(rows)


__all__ = ["EVALUATORS", "generate", "machine_coverage"]
