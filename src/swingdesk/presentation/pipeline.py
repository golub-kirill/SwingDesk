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
from pathlib import Path
from uuid import uuid4

from swingdesk.contracts.market import BarSeries as BarSeriesLike
from swingdesk.contracts.market import Interval, Series
from swingdesk.contracts.observation import ObservationSeries
from swingdesk.contracts.reference import Instrument
from swingdesk.contracts.run import RunManifest
from swingdesk.derived_observations import atr
from swingdesk.journal_evidence.journal import DecisionRecord, Journal
from swingdesk.market_data import BarStore, VendorUnavailable, YAHOO, check
from swingdesk.market_data import vendor_yahoo
from swingdesk.platform.clock import Clock
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data import calendar as cal
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
class RunResult:
    manifest: RunManifest
    outcomes: list[InstrumentOutcome] = field(default_factory=list)

    @property
    def decisions(self) -> list[DecisionRecord]:
        return [o.decision for o in self.outcomes if o.decision is not None]


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True,
            cwd=Path(__file__).resolve().parents[3],
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - a missing git is not a run failure
        return "unknown"


def _config_hash(registry: ParameterRegistry) -> str:
    """Hash of the resolved parameter state. Values are hashed, never recorded (SECURITY 2.5)."""
    payload = json.dumps(
        {pid: registry.is_set(pid) for pid in sorted(registry._entries)},  # noqa: SLF001
        sort_keys=True,
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
