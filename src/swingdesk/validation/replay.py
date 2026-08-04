"""Replay: take a stored manifest, re-run its inputs, and compare the output hash.

`criteria.yml` `a.reproducible` is a ratified Track A criterion, and the course states determinism
as an operating procedure rather than an engineering nicety - the return condition after a screener
failure is that the repeat run matched the control run. This is the check that makes that claim
mechanical instead of remembered.

A mismatch means one of two things, and the manifest tells you which (DETERMINISM_SPEC 5):

  something pinned changed   - the calendar, the config, a component version. Expected, explainable,
                               and the diagnosis names the field.
  nothing pinned changed     - the decision path is non-deterministic. That is a defect, and it is
                               the case this gate exists to catch, because it is invisible otherwise.

Replay reads recorded bars, never a vendor. A replay that fetched would be testing today's data
against yesterday's conclusion and calling the difference a bug.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from swingdesk.application.pipeline import Fetcher, run
from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.contracts.reference import Exchange, Instrument
from swingdesk.contracts.run import RunManifest
from swingdesk.journal_evidence.journal import Journal
from swingdesk.market_data import BarStore, VendorUnavailable
from swingdesk.platform.clock import FixedClock
from swingdesk.platform.parameters import ParameterRegistry

REPLAY_ROOT = Path(__file__).resolve().parents[3] / "golden" / "replay"

#: Manifest fields that are inputs to the decision. A difference in any of these explains a
#: different output_hash. run_id, started_at and completed_at are identity, and snapshot_id is
#: derived from the clock, so none of them belong here.
PINNED_FIELDS = ("config_hash", "calendar_version", "component_versions")

#: Recorded for diagnosis but not treated as explaining a mismatch on its own: identical behaviour
#: across a code change is exactly what the component versions assert, so a code_hash difference
#: with a matching output is a pass, not a warning.
CONTEXT_FIELDS = ("code_hash", "platform")


@dataclass(frozen=True, slots=True)
class ReplayCase:
    name: str
    as_of: datetime
    lookback: str
    instruments: tuple[Instrument, ...]
    parameters: dict[str, Any]
    bars: dict[str, BarSeries]
    manifest: RunManifest | None
    inputs_digest: str = ""
    recorded_inputs_digest: str | None = None

    @property
    def inputs_intact(self) -> bool:
        """False when the recorded snapshot was edited since the manifest was frozen.

        Without this the gate would blame the decision path for a fixture edit - a different output
        from different inputs is not a determinism defect, and calling it one trains the operator to
        distrust the gate.
        """
        return (
            self.recorded_inputs_digest is None
            or self.recorded_inputs_digest == self.inputs_digest
        )


@dataclass(frozen=True, slots=True)
class ReplayResult:
    case: str
    expected: str | None
    actual: str | None
    manifest: RunManifest
    diagnosis: tuple[str, ...] = field(default=())

    @property
    def matched(self) -> bool:
        return self.expected is not None and self.expected == self.actual


def _registry_for(parameters: dict[str, Any]) -> ParameterRegistry:
    return ParameterRegistry(
        {
            key: {
                "id": key,
                "value": value,
                "provenance": "replay fixture",
                "unit": "",
                "named_in": ["replay fixture"],
            }
            for key, value in parameters.items()
        }
    )


def _bar_series(instrument_id: str, document: dict[str, Any], knowledge_time: datetime) -> BarSeries:
    interval = Interval(document["interval"])
    series = Series(document["series"])
    bars: list[Bar] = []
    for row in document["bars"]:
        session_date = date.fromisoformat(row[0])
        bars.append(
            Bar(
                instrument_id=instrument_id,
                interval=interval,
                series=series,
                event_time=datetime(
                    session_date.year, session_date.month, session_date.day,
                    tzinfo=knowledge_time.tzinfo,
                ),
                session_date=session_date,
                open=Decimal(row[1]),
                high=Decimal(row[2]),
                low=Decimal(row[3]),
                close=Decimal(row[4]),
                volume=int(row[5]),
                knowledge_time=knowledge_time,
            )
        )
    return BarSeries(
        instrument_id=instrument_id,
        interval=interval,
        series=series,
        knowledge_time=knowledge_time,
        bars=tuple(bars),
    )


def _inputs_digest(directory: Path, document: dict[str, Any]) -> str:
    """Hash of everything the run reads: the recorded bars and the inputs that select them.

    Excludes the manifest, which is the *output* of a recording and would make the digest
    self-referential.
    """
    payload = json.dumps(
        {
            "as_of": document["as_of"],
            "lookback": document.get("lookback", "1y"),
            "instruments": document["instruments"],
            "parameters": document["parameters"],
        },
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload + (directory / "bars.json").read_bytes()).hexdigest()[:16]


def load_case(directory: Path) -> ReplayCase:
    document = json.loads((directory / "case.json").read_text(encoding="utf-8"))
    as_of = datetime.fromisoformat(document["as_of"])
    recorded = json.loads((directory / "bars.json").read_text(encoding="utf-8"))

    return ReplayCase(
        inputs_digest=_inputs_digest(directory, document),
        recorded_inputs_digest=document.get("inputs_digest"),
        name=document["case"],
        as_of=as_of,
        lookback=document.get("lookback", "1y"),
        instruments=tuple(
            Instrument(
                id=entry["id"],
                ticker=entry["ticker"],
                exchange=Exchange(entry["exchange"]),
                currency=entry["currency"],
            )
            for entry in document["instruments"]
        ),
        parameters=document["parameters"],
        bars={
            instrument_id: _bar_series(instrument_id, entry, as_of)
            for instrument_id, entry in recorded.items()
        },
        manifest=RunManifest(**document["manifest"]) if document.get("manifest") else None,
    )


def _fetcher(case: ReplayCase) -> Fetcher:
    def fetch(
        instrument: Instrument,
        interval: Interval,  # noqa: ARG001
        knowledge_time: datetime,  # noqa: ARG001
        period: str | None = None,  # noqa: ARG001
    ) -> BarSeries:
        series = case.bars.get(instrument.id)
        if series is None:
            # An instrument deliberately absent from the recording. The refusal path is part of what
            # the hash covers, so it has to be exercised, not stubbed out.
            raise VendorUnavailable(f"no recorded bars for {instrument.id}")
        return series

    return fetch


def replay(case: ReplayCase, workspace: Path | None = None) -> ReplayResult:
    """Re-run a case into a throwaway workspace and compare hashes."""
    with tempfile.TemporaryDirectory() as scratch:
        root = workspace or Path(scratch)
        with (
            BarStore(root / "bars.duckdb") as store,
            Journal(root / "journal.duckdb") as journal,
        ):
            result = run(
                list(case.instruments),
                FixedClock(case.as_of),
                _registry_for(case.parameters),
                store,
                journal,
                lookback=case.lookback,
                fetcher=_fetcher(case),
            )

    expected = case.manifest.output_hash if case.manifest else None
    actual = result.manifest.output_hash
    return ReplayResult(
        case=case.name,
        expected=expected,
        actual=actual,
        manifest=result.manifest,
        diagnosis=_diagnose(case, result.manifest) if expected != actual else (),
    )


def _diagnose(case: ReplayCase, produced: RunManifest) -> tuple[str, ...]:
    """Name what changed, so a mismatch arrives as a lead rather than a verdict."""
    recorded = case.manifest
    if recorded is None:
        return ("no manifest recorded for this case; nothing to compare against",)

    if not case.inputs_intact:
        # Checked before anything else: different inputs producing a different output is correct
        # behaviour, and reporting it as non-determinism would be a false accusation.
        return (
            f"the recorded inputs were edited: digest {case.recorded_inputs_digest} -> "
            f"{case.inputs_digest}. Restore them, or re-record the case deliberately.",
        )

    notes: list[str] = []
    for name in PINNED_FIELDS:
        before, after = getattr(recorded, name), getattr(produced, name)
        if before != after:
            notes.append(f"{name} changed: {before!r} -> {after!r}")

    if not notes:
        notes.append(
            "nothing pinned changed. The decision path produced a different result from identical "
            "inputs, which is a determinism defect (DETERMINISM_SPEC 2)."
        )
        for name in CONTEXT_FIELDS:
            before, after = getattr(recorded, name), getattr(produced, name)
            if before != after:
                notes.append(f"context: {name} {before!r} -> {after!r}")

    if produced.code_dirty:
        notes.append("the working tree is dirty, so the code cannot be recovered from its hash")
    return tuple(notes)


def verify(root: Path = REPLAY_ROOT) -> list[str]:
    """Every case that failed to reproduce. Empty means every stored run replayed."""
    failures: list[str] = []
    for directory in sorted(p for p in root.iterdir() if (p / "case.json").exists()):
        case = load_case(directory)
        if case.manifest is None:
            failures.append(f"{case.name}: no recorded manifest; record it before gating on it")
            continue
        if not case.inputs_intact:
            # Reported even when the output still matches. An edited snapshot that happens to hash
            # the same is still an unrecorded change to what the gate is comparing against.
            failures.append(
                f"{case.name}: recorded inputs edited (digest {case.recorded_inputs_digest} -> "
                f"{case.inputs_digest})"
            )
            continue
        result = replay(case)
        if not result.matched:
            failures.append(
                f"{case.name}: expected output_hash {result.expected}, got {result.actual}"
            )
            failures.extend(f"  {note}" for note in result.diagnosis)
    return failures


def record(directory: Path) -> ReplayResult:
    """Run a case and store the manifest it produced.

    Bootstrapping only. This freezes current behaviour as the reference, so it can prove that
    behaviour has not changed since - it cannot prove the behaviour was right to begin with. That
    is what golden vectors and property tests are for.
    """
    case = load_case(directory)
    result = replay(case)

    path = directory / "case.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["inputs_digest"] = _inputs_digest(directory, document)
    document["manifest"] = json.loads(result.manifest.model_dump_json())
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return result
