"""The run report.

Every displayed number resolves to a registered component with a version, a recorded parameter
provenance, and a validation status (CHARTER 4, the ratified v1 finish line). A value computed from
`assumed` inputs is marked as such adjacent to the number it produced - not in a footnote
(PARAMETER_REGISTRY 5).
"""

from __future__ import annotations

from swingdesk.application.pipeline import RunResult
from swingdesk.trade_management.sizing import Refusal

_RULE = "─" * 78


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
        "",
    ]

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
