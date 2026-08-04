"""The run report.

Every displayed number resolves to a registered component with a version, a recorded parameter
provenance, and a validation status (CHARTER 4, the ratified v1 finish line). A value computed from
`assumed` inputs is marked as such adjacent to the number it produced - not in a footnote
(PARAMETER_REGISTRY 5).
"""

from __future__ import annotations

from swingdesk.application.pipeline import InstrumentOutcome, RunResult
from swingdesk.application.universe import UniverseSelection
from swingdesk.trade_management.sizing import Refusal

_RULE = "─" * 78


def _universe_block(result: RunResult) -> list[str]:
    """How the candidates were chosen, and how complete that choice was.

    The coverage line is the point. "47 instruments" reads like the rule's answer; "47 admitted, out
    of 312 measured of 13,048 eligible" reads like what it is - a subset that will grow as bars are
    fetched. Printing only the first would let a partial universe be mistaken for the population.
    """
    selection = result.universe
    if selection is None:
        return []

    rule = selection.rule
    lines = [
        "UNIVERSE — selected by rule, not by a list (DR-003)",
        _RULE,
        f"  rule           close >= {rule.min_price} · {rule.adtv_window}d ADTV >= "
        f"{rule.min_adtv:,.0f} · >= {rule.min_history} bars",
        f"  members        {len(selection.members)}",
        f"  coverage       {selection.measured} of {selection.eligible} eligible symbols have "
        f"stored bars ({selection.coverage:.1%})",
    ]
    if selection.directory_pull is not None:
        lines.append(f"  directory      pulled {selection.directory_pull:%Y-%m-%d}")
    for parameter in selection.parameters:
        flag = "  <- ASSUMED, not evidence" if parameter.is_assumed else ""
        lines.append(f"      {parameter.id:<26} {parameter.value}   [{parameter.provenance}]{flag}")

    if selection.is_partial:
        lines += [
            "",
            "  PARTIAL UNIVERSE. This is a subset of what the rule admits, not the rule's answer:",
            "  a symbol with no stored bars cannot be measured, so it cannot be admitted. Run",
            "  tools/refresh_universe.py to raise coverage.",
        ]
    if selection.capped_from is not None:
        lines += [
            "",
            f"  CAPPED to {len(selection.members)} of {selection.capped_from} admitted, by dollar",
            "  volume. A cap is a RANKING and the rule is not — these results are about the most",
            "  liquid members, and do not describe the universe.",
        ]
    return lines


def render_empty_universe(selection: UniverseSelection) -> str:
    """What to say when the rule admits nobody. Not an error, and not silence either."""
    return "\n".join([
        _RULE,
        "UNIVERSE EMPTY — no instrument met the DR-003 liquidity rule",
        _RULE,
        f"  eligible symbols in the directory   {selection.eligible}",
        f"  of those, with stored bars          {selection.measured}",
        "  admitted by the rule                0",
        "",
        "  With no bars stored, this is a coverage problem rather than a market one:",
        "    python tools/fetch_directory.py     # if the directory is empty",
        "    python tools/refresh_universe.py    # to fetch bars for eligible symbols",
        _RULE,
    ])


def _positions_block(result: RunResult) -> list[str]:
    """Open positions first, because that is the order the run used and the order that matters.

    A proposal is shown as a proposal. Nothing here has happened; D6 routes stop moves and partial
    exits through the owner, and a report that reads like a confirmation would be lying about that.
    """
    if not result.positions:
        return []

    lines = ["", "OPEN POSITIONS — evaluated before candidates (CHECKLIST_SPEC 4)", _RULE]
    for outcome in result.positions:
        position = outcome.position
        flag = "  [STALE DATA]" if outcome.stale else ""
        lines.append(
            f"  {position.instrument_id:<12} {position.shares:>5} sh @ {position.entry_price}"
            f"  stop {position.current_stop}  open risk {position.open_risk}{flag}"
        )
        if outcome.action is not None:
            action = outcome.action
            marker = "NEEDS YOUR APPROVAL" if action.is_actionable else "no action"
            lines.append(f"      proposed: {action.kind.value:<14} {marker}")
            lines.append(f"      because:  {action.reason}")
    pending = len(result.actionable)
    if pending:
        lines.append("")
        lines.append(f"  {pending} proposal(s) await your approval. Nothing has been done.")
    return lines


def _checklist_block(outcome: InstrumentOutcome) -> list[str]:
    """The pre-trade checklist, with the unanswered items shown rather than summarised away.

    An `unavailable` item is a gap in the SYSTEM, and printing it next to the passes is the only
    way the operator can tell the difference between "checked and fine" and "nobody checked".
    """
    checklist = outcome.checklist
    if checklist is None:
        return []

    counts = checklist.counts
    lines = [
        f"  pre-trade checklist  Appendix {checklist.appendix} · {checklist.terminal_state()}",
        f"      {counts['pass']} pass · {counts['fail']} fail · "
        f"{counts['unavailable']} unavailable · {counts['human']} for you",
    ]
    for item in checklist.failures:
        lines.append(f"      FAIL  {item.id}  {item.text}")
        lines.append(f"            {item.note}")
    unavailable = [i for i in checklist.items if i.state.value == "unavailable"]
    if unavailable:
        lines.append(f"      not checkable yet: {', '.join(i.id for i in unavailable)}")
    return lines


def render(result: RunResult) -> str:
    manifest = result.manifest
    lines: list[str] = [
        _RULE,
        f"SwingDesk run {manifest.run_id}",
        _RULE,
        f"  started        {manifest.started_at:%Y-%m-%d %H:%M:%S %Z}",
        f"  code           {manifest.code_hash}" + ("  DIRTY TREE" if manifest.code_dirty else ""),
        f"  config         {manifest.config_hash}",
        f"  snapshot       {manifest.snapshot_id}",
        f"  calendar       {manifest.calendar_version}",
        f"  platform       {manifest.platform}",
        f"  output hash    {manifest.output_hash}",
    ]
    if manifest.universe_hash is not None:
        lines.append(f"  universe hash  {manifest.universe_hash}")
    lines.append("")

    universe = _universe_block(result)
    if universe:
        lines.extend(universe)
        lines.append("")

    lines.extend(_positions_block(result))
    if result.positions or result.universe is not None:
        lines.extend(["", "CANDIDATES", _RULE])

    for outcome in result.outcomes:
        instrument = outcome.instrument
        lines.append(f"{instrument.ticker} ({instrument.exchange.value}, {instrument.currency})")
        lines.append(f"  bars stored          {outcome.bars}")

        if outcome.completeness_findings:
            lines.append(f"  completeness         {len(outcome.completeness_findings)} finding(s)")
            for finding in outcome.completeness_findings[:3]:
                lines.append(f"      {finding}")
        elif outcome.bars:
            lines.append("  completeness         clean (every session matched the calendar)")

        observations = outcome.observations
        if observations is not None:
            latest = observations.observations[-1]
            value = "none (warm-up)" if latest.value is None else f"{latest.value:.4f}"
            lines.append(f"  {observations.component} v{observations.component_version}")
            lines.append(f"      ATR                {value}  {observations.units}")
            lines.append(f"      validation         {observations.validation_status}")
            for parameter in observations.parameters:
                flag = "  <- ASSUMED, not evidence" if parameter.is_assumed else ""
                lines.append(
                    f"      {parameter.id:<18} {parameter.value}   [{parameter.provenance}]{flag}"
                )

        risk = outcome.risk
        if isinstance(risk, Refusal):
            lines.append(f"  risk                 REFUSED  {risk}")
        elif risk is not None:
            lines.append(f"  entry / stop         {risk.entry} / {risk.stop}")
            lines.append(f"  risk per share       {risk.risk_per_share}")
            lines.append(f"  shares               {risk.shares}   (rounded down)")
            lines.append(f"  planned risk         {risk.planned_risk}   <- R denominator, frozen")

        decision = outcome.decision
        if decision is not None:
            detail = f"  [{decision.reason_code}]" if decision.reason_code else ""
            lines.append(f"  DECISION             {decision.decision}{detail}")
            if decision.reason:
                lines.append(f"      {decision.reason}")
        lines.extend(_checklist_block(outcome))
        lines.append("")

    assumed = sorted(
        {
            parameter.id
            for outcome in result.outcomes
            if outcome.observations
            for parameter in outcome.observations.parameters
            if parameter.is_assumed
        }
    )
    lines += [
        _RULE,
        f"  decisions        {len(result.decisions)}",
        f"  assumed inputs   {len(assumed)}" + (f"  ({', '.join(assumed)})" if assumed else ""),
        "",
        "  Every setup in this system is Untested. A decision here means the components",
        "  computed what their specs say - not that the trade has an edge.",
        _RULE,
    ]
    return "\n".join(lines)
