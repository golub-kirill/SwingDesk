"""Golden vectors: frozen input, frozen output, checked in.

This is what makes COMPONENT_REGISTRY_SPEC 6 enforceable rather than aspirational. Changing a
component's behaviour requires bumping its version, regenerating its vectors, and writing a decision
record - and the regeneration shows up in review as a diff of numbers. A silent behaviour change is
not possible.

Three separate things are checked, and each catches a different way of going wrong:

  1. the recorded value still recomputes        - behaviour has not drifted
  2. the file hash still matches the manifest   - a vector was not quietly edited to match new code
  3. the manifest version equals the module's   - behaviour did not change without a version bump

Check 2 is the one that matters. Without it, the cheapest way past a failing vector is to paste in
whatever the code now prints, which converts the gate into a formality.

Values are compared as Decimals, not as strings: Decimal("2") == Decimal("2.00"), and downstream
arithmetic is value-based, so representation is not behaviour. Byte-level output is pinned
separately by the replay gate's output_hash (DETERMINISM_SPEC 7).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.contracts.observation import ObservationSeries, ParameterUse
from swingdesk.derived_observations import atr, moving_average
from swingdesk.platform.parameters import ParameterRegistry

GOLDEN_ROOT = Path(__file__).resolve().parents[3] / "golden" / "components"
MANIFEST = GOLDEN_ROOT / "manifest.json"


def _run_atr(series: BarSeries, parameters: dict[str, Any]) -> ObservationSeries:
    return atr.compute(series, _registry_for(parameters))


def _run_sma(series: BarSeries, parameters: dict[str, Any]) -> ObservationSeries:
    """SMA takes its period from the caller, not the registry - it has no period of its own."""
    period = int(parameters["sma.period"])
    return moving_average.compute(
        series, period,
        ParameterUse(id="sma.period", value=str(period), provenance="golden vector"),
    )


#: Component id -> (module, runner). The module supplies VERSION; the runner knows how to call it,
#: because components legitimately differ in how they receive parameters. An `active` component
#: missing from this map has no vectors, which COMPONENT_REGISTRY_SPEC 3 says it may not be.
IMPLEMENTATIONS: dict[str, tuple[ModuleType, Any]] = {
    atr.COMPONENT: (atr, _run_atr),
    moving_average.COMPONENT: (moving_average, _run_sma),
}


@dataclass(frozen=True, slots=True)
class Vector:
    """One frozen case."""

    path: Path
    component: str
    component_version: int
    case: str
    parameters: dict[str, Any]
    instrument_id: str
    knowledge_time: datetime
    bars: BarSeries
    expected: tuple[Decimal | None, ...]


def _registry_for(parameters: dict[str, Any]) -> ParameterRegistry:
    """A registry holding exactly the vector's parameters, so it never reads the real one.

    A vector whose result depends on registry/parameters.yml would change meaning every time a
    value is ratified, which is the opposite of frozen.
    """
    return ParameterRegistry(
        {
            key: {
                "id": key,
                "value": value,
                "provenance": "golden vector",
                "unit": "",
                "named_in": ["golden vector"],
            }
            for key, value in parameters.items()
        }
    )


def load(path: Path) -> Vector:
    document = json.loads(path.read_text(encoding="utf-8"))
    knowledge_time = datetime.fromisoformat(document["knowledge_time"])
    interval = Interval(document["interval"])
    series = Series(document["series"])

    bars: list[Bar] = []
    for row in document["bars"]:
        session_date = date.fromisoformat(row[0])
        bars.append(
            Bar(
                instrument_id=document["instrument_id"],
                interval=interval,
                series=series,
                # Synthetic vectors: the pure function walks the series it is given and never
                # consults a calendar, so a midnight UTC stamp is sufficient and unambiguous.
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

    return Vector(
        path=path,
        component=document["component"],
        component_version=int(document["component_version"]),
        case=document["case"],
        parameters=document["parameters"],
        instrument_id=document["instrument_id"],
        knowledge_time=knowledge_time,
        bars=BarSeries(
            instrument_id=document["instrument_id"],
            interval=interval,
            series=series,
            knowledge_time=knowledge_time,
            bars=tuple(bars),
        ),
        expected=tuple(None if value is None else Decimal(value) for value in document["expected"]),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recompute(vector: Vector) -> tuple[Decimal | None, ...]:
    _, run = IMPLEMENTATIONS[vector.component]
    produced = run(vector.bars, vector.parameters)
    return tuple(observation.value for observation in produced.observations)


def verify(root: Path = GOLDEN_ROOT) -> list[str]:
    """Every failure found, most structural first. Empty means the vectors hold."""
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return [f"no manifest at {manifest_path}"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures: list[str] = []

    for component, entry in sorted(manifest["components"].items()):
        entry_impl = IMPLEMENTATIONS.get(component)
        if entry_impl is None:
            failures.append(f"{component}: manifest names it, but no implementation is registered")
            continue
        module, _ = entry_impl

        if module.VERSION != entry["version"]:
            failures.append(
                f"{component}: module is version {module.VERSION}, manifest froze version "
                f"{entry['version']}. A version bump regenerates the vectors and resets validation "
                f"status (COMPONENT_REGISTRY_SPEC 6)."
            )
            continue

        directory = root / component
        on_disk = {path.name for path in sorted(directory.glob("*.json"))}
        recorded = set(entry["vectors"])
        for name in sorted(recorded - on_disk):
            failures.append(f"{component}/{name}: in the manifest, missing from disk")
        for name in sorted(on_disk - recorded):
            failures.append(f"{component}/{name}: on disk, not in the manifest - register it")

        for name in sorted(recorded & on_disk):
            path = directory / name
            digest = _sha256(path)
            if digest != entry["vectors"][name]:
                failures.append(
                    f"{component}/{name}: content changed (sha256 {digest[:12]}, manifest holds "
                    f"{entry['vectors'][name][:12]}). If the change is intended, bump the component "
                    f"version and carry a decision record in the same commit."
                )
                continue

            vector = load(path)
            if vector.component_version != module.VERSION:
                failures.append(
                    f"{component}/{name}: vector declares version {vector.component_version}, "
                    f"module is {module.VERSION}"
                )
                continue

            produced = _recompute(vector)
            if len(produced) != len(vector.expected):
                failures.append(
                    f"{component}/{name}: produced {len(produced)} observations, expected "
                    f"{len(vector.expected)}"
                )
                continue
            for index, (got, want) in enumerate(zip(produced, vector.expected)):
                if got is None and want is None:
                    continue
                if got is None or want is None or got != want:
                    failures.append(
                        f"{component}/{name}[{index}]: expected {want}, got {got}"
                    )

    return failures


def rehash(root: Path = GOLDEN_ROOT) -> list[str]:
    """Record the hash of every vector on disk, leaving `expected` untouched.

    For adding a hand-authored vector: the expected values stay as written, so `verify` still has
    to prove them against the implementation. This is the safe operation - it can register a new
    case but can never make a failing case pass.
    """
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    registered: list[str] = []

    for component, entry in sorted(manifest["components"].items()):
        vectors: dict[str, str] = {}
        for path in sorted((root / component).glob("*.json")):
            digest = _sha256(path)
            if entry.get("vectors", {}).get(path.name) != digest:
                registered.append(f"{component}/{path.name}")
            vectors[path.name] = digest
        entry["vectors"] = vectors

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return registered


def regenerate(root: Path = GOLDEN_ROOT) -> list[str]:
    """Rewrite every vector's `expected` from the current implementation, then rehash.

    Deliberately blunt: it does not ask what changed, because the review of the resulting diff is
    where that question belongs. Running this is an assertion that the new numbers are correct.
    """
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    changed: list[str] = []

    for component, entry in sorted(manifest["components"].items()):
        module, _ = IMPLEMENTATIONS[component]
        entry["version"] = module.VERSION
        vectors: dict[str, str] = {}
        for path in sorted((root / component).glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            vector = load(path)
            produced = _recompute(vector)
            expected = [None if value is None else str(value) for value in produced]
            if document["expected"] != expected or document["component_version"] != module.VERSION:
                changed.append(f"{component}/{path.name}")
            document["expected"] = expected
            document["component_version"] = module.VERSION
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            vectors[path.name] = _sha256(path)
        entry["vectors"] = vectors

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return changed
