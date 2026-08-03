"""The daily run, as one vertical slice.

Order follows the course's own pipeline (SCREENER_SPEC 3) with the constraint from Appendix T that
open positions are evaluated before new candidates - a run-order rule, not a suggestion.

This is the walking skeleton: one instrument, one feed, one derived observation, one risk
calculation, one journal entry, one report. It deliberately exercises both paths - a component that
computes and a component that refuses - because the refusal path is the harder machinery and a
ratified Track A criterion.
"""

from __future__ import annotations

import hashlib
import json
import platform as platform_info
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from swingdesk.contracts.market import BarSeries as BarSeriesLike
from swingdesk.contracts.market import Interval, Series
from swingdesk.contracts.observation import ObservationSeries
from swingdesk.contracts.position import ActionKind, ManagementAction, Position
from swingdesk.contracts.reference import Instrument
from swingdesk.contracts.run import RunManifest
from swingdesk.derived_observations import atr
from swingdesk.journal_evidence.journal import DecisionRecord, Journal
from swingdesk.market_data import BarStore, VendorUnavailable, YAHOO, check
from swingdesk.market_data import vendor_yahoo
from swingdesk.platform.clock import Clock
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data import calendar as cal
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.trade_management import manage
from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.trade_management.sizing import Refusal, RiskSnapshot, size_long


@dataclass
class InstrumentOutcome:
    """Everything one instrument produced, and why it ended where it did."""

    instrument: Instrument
    bars: int = 0
    completeness_findings: tuple = ()
    observations: ObservationSeries | None = None
    risk: RiskSnapshot | Refusal | None = None
    decision: DecisionRecord | None = None


@dataclass
class PositionOutcome:
    """One open position and what the run proposed for it."""

    position: Position
    action: ManagementAction | None = None
    stale: bool = False


@dataclass
class RunResult:
    manifest: RunManifest
    outcomes: list[InstrumentOutcome] = field(default_factory=list)
    positions: list[PositionOutcome] = field(default_factory=list)
    steps: tuple[str, ...] = ()

    @property
    def decisions(self) -> list[DecisionRecord]:
        return [o.decision for o in self.outcomes if o.decision is not None]

    @property
    def actionable(self) -> list[ManagementAction]:
        """Proposals needing the owner's answer before anything happens (D6)."""
        return [p.action for p in self.positions if p.action is not None and p.action.is_actionable]

    @property
    def positions_ran_first(self) -> bool:
        """The run's own record of its order, not an assertion about it.

        `CHECKLIST_SPEC` §4 requires open positions and gaps to be checked first, and a claim that
        they were is worth less than a trace showing it.
        """
        if "positions" not in self.steps or "candidates" not in self.steps:
            return "positions" in self.steps
        return self.steps.index("positions") < self.steps.index("candidates")


def _held_instrument(instrument_id: str) -> Instrument:
    """An Instrument for a position whose id is not among today's candidates.

    A position is held regardless of whether the screener still nominates it, so the run must be
    able to fetch it anyway. The exchange comes from the same symbology rule the CLI uses; nothing
    here is guessed beyond what that rule already encodes.
    """
    exchange = cal.exchange_for(instrument_id)
    base = instrument_id.upper().removesuffix(".TO")
    return Instrument(
        id=instrument_id,
        ticker=base,
        exchange=exchange,
        currency="USD" if exchange.value == "NYSE" else "CAD",
    )


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True,
            cwd=Path(__file__).resolve().parents[3],
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - a missing git is not a run failure
        return "unknown"


def _config_hash(registry: ParameterRegistry) -> str:
    """Hash of the resolved parameter state. Values are hashed, never recorded (SECURITY 2.5).

    The hash covers values and provenance, not merely which ids are set. An earlier version hashed
    set-ness alone, so changing a threshold left config_hash unmoved - a replay would then report a
    different output with nothing pinned having changed, and blame the decision path for what was
    really a config edit. The replay gate surfaced that the first time it was pointed at a case.
    """
    payload = json.dumps(
        {
            pid: (
                {"value": entry.get("value"), "provenance": entry.get("provenance")}
                if entry.get("value") is not None
                else None
            )
            for pid, entry in sorted(registry._entries.items())  # noqa: SLF001
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


Fetcher = Callable[[Instrument, Interval, datetime, str | None], "BarSeriesLike"]


def run(
    instruments: list[Instrument],
    clock: Clock,
    registry: ParameterRegistry,
    store: BarStore,
    journal: Journal,
    lookback: str = "1y",
    fetcher: Fetcher | None = None,
    positions: PositionStore | None = None,
    exits: ExitPolicy | None = None,
) -> RunResult:
    """One pass of the daily pipeline.

    `fetcher` is injected so the suite can run offline against recorded fixtures. CI must never
    touch the network: a suite that fetches is neither deterministic nor available offline, and it
    would hammer a rate-limited free tier (CI_POLICY 4).
    """
    fetch = fetcher or vendor_yahoo.fetch
    started = clock.now()
    # run_id and started_at are identity, not inputs - domain code never reads them, and they are
    # excluded from output_hash. So a replay under a pinned clock must still get a unique id, or
    # re-running the same as-of date would collide in the journal. The decision inputs stay pinned;
    # only the label varies.
    unique = uuid4().hex[:8]
    run_id = f"run-{started:%Y%m%dT%H%M%SZ}-{unique}"
    snapshot_id = f"snap-{started:%Y%m%dT%H%M%SZ}-{unique}"

    manifest = RunManifest(
        run_id=run_id,
        started_at=started,
        code_hash=_git("rev-parse", "--short", "HEAD"),
        code_dirty=bool(_git("status", "--porcelain")),
        config_hash=_config_hash(registry),
        snapshot_id=snapshot_id,
        calendar_version=cal.calendar_version(),
        platform=f"{platform_info.system()} python{sys.version.split()[0]}",
        component_versions={atr.COMPONENT: atr.VERSION},
    )
    journal.start_run(manifest)
    store.create_snapshot(snapshot_id, started, started, note=run_id)

    result = RunResult(manifest=manifest)
    steps: list[str] = []

    # --- open positions, BEFORE any candidate -------------------------------------------
    # CHECKLIST_SPEC 4: "Открытые позиции и gaps проверены первыми". Not a preference about tidy
    # code - a data failure must never lock the owner out of managing risk on positions already
    # open (TEST_STRATEGY 6), so this phase runs before anything that can fail on fresh data.
    if positions is not None:
        steps.append("positions")
        known = {instrument.id: instrument for instrument in instruments}
        for position in positions.open_as_of(started):
            outcome = PositionOutcome(position=position)
            result.positions.append(outcome)

            # Refresh the held instrument's bars whether or not it is a candidate today. A position
            # is held regardless of whether the screener still likes it, and evaluating one against
            # the previous run's bars would manage yesterday's risk.
            #
            # Fetching is FAIL-OPEN (FAIL_CLOSED_POLICY row 1): a vendor failure falls back to the
            # last valid stored snapshot rather than blocking. Only when there is no snapshot at all
            # does the position pause - the one case where risk genuinely cannot be evaluated.
            instrument = known.get(position.instrument_id) or _held_instrument(position.instrument_id)
            try:
                refreshed = fetch(instrument, Interval.DAY, started, period=lookback)
            except VendorUnavailable:
                pass
            else:
                store.write(refreshed.bars, started)

            held = store.as_of(position.instrument_id, Interval.DAY, Series.RAW, started)
            if not held.bars:
                # No bars for a position we hold. Recorded as stale rather than skipped: the owner
                # must be told a position could not be evaluated, not left to infer it from silence.
                outcome.stale = True
                outcome.action = ManagementAction(
                    position_id=position.position_id, proposed_at=started,
                    kind=ActionKind.PAUSE, reason_code="DATA",
                    reason="no bars available for an open position; management cannot be evaluated",
                    old_stop=position.current_stop,
                )
            else:
                bar = held.bars[-1]
                bars_held = sum(1 for b in held.bars if b.session_date >= position.opened_on) - 1
                policy = exits or ExitPolicy(Decimal("2.0"), 20)
                observations = atr.compute(held, registry)
                latest_atr = observations.observations[-1].value
                outcome.action = manage.evaluate(
                    position, bar, policy, started, bars_held=max(bars_held, 0), atr=latest_atr
                )
            positions.propose(outcome.action, run_id=run_id)

    steps.append("candidates")

    for instrument in instruments:
        outcome = InstrumentOutcome(instrument=instrument)
        result.outcomes.append(outcome)

        # 1. Source facts. Fetching is fail-open; deciding is not.
        try:
            series = fetch(instrument, Interval.DAY, started, period=lookback)
        except VendorUnavailable as unavailable:
            outcome.decision = DecisionRecord(
                instrument.id, "Skip", "DATA", str(unavailable)[:200]
            )
            continue

        store.write(series.bars, started)
        stored = store.as_of(instrument.id, Interval.DAY, Series.RAW, started)
        outcome.bars = len(stored)

        # 2. Completeness, against the calendar. This is what separates a half-day from a gap.
        window_start = stored.bars[0].session_date if stored.bars else date.today()
        window_end = stored.bars[-1].session_date if stored.bars else date.today()
        report = check(stored, instrument.exchange, YAHOO, window_start, window_end)
        outcome.completeness_findings = report.findings
        if not report.is_complete:
            outcome.decision = DecisionRecord(
                instrument.id, "Skip", "DATA",
                f"{len(report.findings)} incomplete session(s); first: {report.findings[0]}",
            )
            continue

        # 3. Derived observation.
        outcome.observations = atr.compute(stored, registry)
        latest = outcome.observations.observations[-1]
        if latest.value is None:
            outcome.decision = DecisionRecord(
                instrument.id, "Skip", "DATA", "warm-up incomplete; no observation emitted"
            )
            continue

        # 4. Risk. Stop derived from the observation, then size. Stop before size, always.
        entry = stored.bars[-1].close
        stop = entry - latest.value
        sized = size_long(entry, stop, registry)
        outcome.risk = sized

        if isinstance(sized, Refusal):
            outcome.decision = DecisionRecord(
                instrument.id, "Skip", sized.code, sized.reason, sized.parameter_id
            )
            continue

        outcome.decision = DecisionRecord(instrument.id, "Watch", None,
                                          "sized; awaiting a trigger")

    result.steps = tuple(steps)
    journal.record_decisions(run_id, clock.now(), result.decisions)

    output_hash = hashlib.sha256(
        json.dumps(
            [
                {
                    "instrument": o.instrument.id,
                    "bars": o.bars,
                    "decision": o.decision.decision if o.decision else None,
                    "code": o.decision.reason_code if o.decision else None,
                    "atr": str(o.observations.observations[-1].value)
                    if o.observations and o.observations.observations[-1].value is not None
                    else None,
                }
                for o in result.outcomes
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()[:16]

    journal.complete_run(run_id, output_hash, clock.now())
    result.manifest = manifest.model_copy(
        update={"output_hash": output_hash, "completed_at": clock.now()}
    )
    return result
