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
from typing import Any

from swingdesk.contracts.component import ComponentSpec
from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.contracts.observation import ObservationSeries, ParameterUse
from swingdesk.derived_observations import atr, breadth, moving_average, pivots, regime
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


def _run_pivot(series: BarSeries, parameters: dict[str, Any]) -> ObservationSeries:
    left, right = int(parameters["pivot.left"]), int(parameters["pivot.right"])
    return pivots.compute(
        series, left, right,
        ParameterUse(id="pivot.left", value=str(left), provenance="golden vector"),
        ParameterUse(id="pivot.right", value=str(right), provenance="golden vector"),
        highs=bool(parameters["pivot.highs"]),
    )


def _run_breadth(document: dict[str, Any]) -> list[Any]:
    """Cross-sectional: a panel of members in, one ratio per session out.

    The vector supplies each member's closes and its own moving average directly, rather than bars
    plus a period. That keeps the case about BREADTH - a member whose average is missing must be
    excluded from both sides of the ratio - instead of re-testing the SMA, which has its own
    vectors.
    """
    from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
    from swingdesk.contracts.observation import Observation, ObservationSeries

    knowledge = datetime.fromisoformat(document["knowledge_time"])
    sessions = [date.fromisoformat(d) for d in document["sessions"]]

    series_by_id: dict[str, BarSeries] = {}
    sma_by_id: dict[str, ObservationSeries] = {}
    for member_id, member in sorted(document["members"].items()):
        offset = int(member.get("first_session_index", 0))
        member_sessions = sessions[offset: offset + len(member["closes"])]
        bars = tuple(
            Bar(
                instrument_id=member_id, interval=Interval.DAY, series=Series.RAW,
                event_time=datetime(s.year, s.month, s.day, tzinfo=knowledge.tzinfo),
                session_date=s, open=Decimal(c), high=Decimal(c), low=Decimal(c),
                close=Decimal(c), volume=1_000_000, knowledge_time=knowledge,
            )
            for s, c in zip(member_sessions, member["closes"], strict=False)
        )
        series_by_id[member_id] = BarSeries(
            instrument_id=member_id, interval=Interval.DAY, series=Series.RAW,
            knowledge_time=knowledge, bars=bars,
        )
        sma_by_id[member_id] = ObservationSeries(
            component=moving_average.SPEC.component, component_version=1,
            instrument_id=member_id, units="price units", parameters=(),
            validation_status="Not Applicable", knowledge_time=knowledge,
            observations=tuple(
                Observation(
                    component=moving_average.SPEC.component, component_version=1,
                    instrument_id=member_id, event_time=bar.event_time,
                    value=None if v is None else Decimal(v),
                    units="price units", knowledge_time=knowledge,
                )
                for bar, v in zip(bars, member["sma"], strict=False)
            ),
        )

    points = breadth.above_average(
        series_by_id, sma_by_id, min_members=int(document["parameters"]["min_members"])
    )
    return [point.value for point in points]


def _run_regime(document: dict[str, Any]) -> list[Any]:
    """Fit on a training window, then answer point queries. Two operations, one vector.

    Splitting them into separate vectors would let the fit drift from the apply without either
    vector noticing, and the fit/apply split is the whole point of the component.
    """
    variant = regime.Variant(document["parameters"]["variant"])
    train_breadth = [None if v is None else Decimal(v) for v in document["train_breadth"]]
    train_volatility = [None if v is None else Decimal(v) for v in document["train_volatility"]]
    classifier = regime.fit(variant, train_breadth, train_volatility)

    produced: list[Any] = [str(cut) for cut in classifier.breadth_cuts]
    produced += [str(cut) for cut in classifier.volatility_cuts]
    for query in document["queries"]:
        b = None if query[0] is None else Decimal(query[0])
        v = None if query[1] is None else Decimal(query[1])
        produced.append(classifier.label(b, v))
    return produced


#: Component id -> (spec, runner). Keyed on the SPEC rather than the module, because one module may
#: implement more than one component - swing highs and swing lows are the same algorithm mirrored,
#: and the course gives them separate ids. An `active` component missing from this map has no
#: vectors, which COMPONENT_REGISTRY_SPEC 3 says it may not be.
IMPLEMENTATIONS: dict[str, tuple[ComponentSpec, Any]] = {
    atr.SPEC.component: (atr.SPEC, _run_atr),
    moving_average.SPEC.component: (moving_average.SPEC, _run_sma),
    pivots.SWING_HIGH.component: (pivots.SWING_HIGH, _run_pivot),
    pivots.SWING_LOW.component: (pivots.SWING_LOW, _run_pivot),
    breadth.SPEC.component: (breadth.SPEC, _run_breadth),
    regime.SPEC.component: (regime.SPEC, _run_regime),
}


@dataclass(frozen=True, slots=True)
class Vector:
    """One frozen case.

    `kind` says what shape the inputs take, because not every component consumes one instrument's
    bars. A cross-sectional measure takes a panel; a fitted classifier takes a training window and
    then answers point queries. Forcing those through a bar-series loader would have meant either
    no vectors for them - which is how `breadth` and `regime` ended up used by a reported study with
    no vectors at all - or a loader that lies about its inputs.
    """

    path: Path
    component: str
    component_version: int
    case: str
    kind: str
    parameters: dict[str, Any]
    document: dict[str, Any]
    expected: tuple[Any, ...]
    instrument_id: str = ""
    knowledge_time: datetime | None = None
    bars: BarSeries | None = None


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


def _expected(document: dict[str, Any]) -> tuple[Any, ...]:
    """Numeric expectations become Decimals; text ones stay strings.

    A label is not a number and comparing it as one would silently pass on `Decimal("0")` versus
    `"0"`. The kind decides, not a guess about the contents.
    """
    if document.get("expected_kind", "numeric") == "text":
        return tuple(document["expected"])
    return tuple(None if v is None else Decimal(v) for v in document["expected"])


def load(path: Path) -> Vector:
    document = json.loads(path.read_text(encoding="utf-8"))
    kind = document.get("kind", "series")
    if kind != "series":
        return Vector(
            path=path,
            component=document["component"],
            component_version=int(document["component_version"]),
            case=document["case"],
            kind=kind,
            parameters=document.get("parameters", {}),
            document=document,
            expected=_expected(document),
        )

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
        kind="series",
        parameters=document["parameters"],
        document=document,
        instrument_id=document["instrument_id"],
        knowledge_time=knowledge_time,
        bars=BarSeries(
            instrument_id=document["instrument_id"],
            interval=interval,
            series=series,
            knowledge_time=knowledge_time,
            bars=tuple(bars),
        ),
        expected=_expected(document),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recompute(vector: Vector) -> tuple[Any, ...]:
    _, run = IMPLEMENTATIONS[vector.component]
    if vector.kind == "series":
        produced = run(vector.bars, vector.parameters)
        return tuple(observation.value for observation in produced.observations)
    return tuple(run(vector.document))


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
        spec, _ = entry_impl

        if spec.version != entry["version"]:
            failures.append(
                f"{component}: code is version {spec.version}, manifest froze version "
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
            if vector.component_version != spec.version:
                failures.append(
                    f"{component}/{name}: vector declares version {vector.component_version}, "
                    f"code is {spec.version}"
                )
                continue

            produced = _recompute(vector)
            if len(produced) != len(vector.expected):
                failures.append(
                    f"{component}/{name}: produced {len(produced)} observations, expected "
                    f"{len(vector.expected)}"
                )
                continue
            for index, (got, want) in enumerate(zip(produced, vector.expected, strict=False)):
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
        spec, _ = IMPLEMENTATIONS[component]
        entry["version"] = spec.version
        vectors: dict[str, str] = {}
        for path in sorted((root / component).glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            vector = load(path)
            produced = _recompute(vector)
            expected = [None if value is None else str(value) for value in produced]
            if document["expected"] != expected or document["component_version"] != spec.version:
                changed.append(f"{component}/{path.name}")
            document["expected"] = expected
            document["component_version"] = spec.version
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            vectors[path.name] = _sha256(path)
        entry["vectors"] = vectors

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return changed
