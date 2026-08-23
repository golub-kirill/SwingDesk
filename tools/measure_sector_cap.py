"""Calibrate `risk.max_sector_risk` against the only trade log this project holds.

**The question.** `DR-006` §2 argued 2R as *one third of the book* against a 6R anchor. §8.3 moved
the anchor to 4R and this number did not move, so 2R is now HALF the book. That may still be right;
it is a different statement from the one that was argued, and §13 carries it as an owner ruling.
This is the measurement the ruling needs.

**What it measures, and what it cannot.** `PR-005`'s log holds 26,351 trades over 68 instruments,
and its base slice (arm `NONE`, regime `1x`) held a **median of 20 positions at once, maximum 54**.
It is a per-instrument backtest with no capital constraint, so it never simulated a four-position
book and cannot be replayed as one. What it can supply is the POPULATION a four-position book would
have drawn from on each day, and that is what this samples: four names drawn uniformly from the
positions open that day, scored against candidate caps.

**Uniform draw, and it is not laziness.** `rs.ranking_method` is `unset` and `ALLOCATION_SPEC` §6
rule 4 forbids falling back to any order the system happens to have. A uniform draw is the only
assumption that does not smuggle in a ranking the system refuses to make.

**Three limitations, stated because they bound every trade-log number below.**

  1. The sectors are TODAY's, not the ones in force in 2016 (`DR-006` §8.4 d). A name that changed
     sector is misfiled for its whole history.
  2. 59 usable instruments is a thin cross-section, and it leans heavily financial - financial
     services is the most-represented sector on 57% of days. **`--wide` answers this one**, by
     measuring the sector mix and the correlation cross-tab over the whole admitted universe, which
     needs no trade log at all. Measured that way the universe is NOT financial-heavy: the 57% is a
     property of these 68 names (`DR-006` §16.1).
  3. Nine of the 68 are refused by §8.7's degeneracy guard and contribute to no sector at all, so
     the measured concentration is an understatement by however much they hold.

**`--wide` cannot fix limitation 1, and cannot touch OUTCOMES at all.** Expectancy and gap
clustering need a trade log; only a backtest over a wider sample moves those.

Network tool only in the sense that its INPUT came from one: classifications are read from a saved
file, or from the store `tools/refresh_classifications.py` fills. Re-run offline.

    python tools/measure_sector_cap.py --wide \\
        --classifications docs/decisions/measurements/sector-classifications-2026-08-23.json \\
        --out docs/decisions/measurements/sector-cap-calibration-2026-08-23.json
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.application import universe as universe_builder
from swingdesk.contracts.market import Interval, Series
from swingdesk.contracts.reference import Classification, SectorWeight
from swingdesk.derived_observations import correlation
from swingdesk.market_data import BarStore
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data.classification import (
    ClassificationStore,
    Exposure,
    look_through,
)
from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.trade_management.sizing import Refusal

REPO = Path(__file__).resolve().parents[1]
TRADES = REPO / "docs" / "prereg" / "results" / "PR-005-trades.csv"

#: The base slice: no overlay, one regime. Mixing arms would overlap trades from variants that were
#: never live at the same time, and the concurrency this measures would be an artefact of that.
ARM, REGIME = "NONE", "1x"

#: One position's risk in R under THIS system's sizing, not `PR-005`'s. Shares round down and costs
#: are spent against the same budget, so a candidate asks for slightly under 1R - 0.98 is what the
#: run report shows on the fixture book.
R_PER_POSITION = Decimal("0.98")

#: Caps compared. 1.33R is "one third of a 4R book", the reading §2 originally argued; 2R is what
#: the registry carries; 3R is included because `DR-006` §4 predicted that a cap set too loose
#: would never bind, and a prediction is worth checking rather than repeating.
CANDIDATE_CAPS = (Decimal("1.33"), Decimal(2), Decimal(3))

SEED = 20260823
DRAWS_PER_DAY = 200

#: Sessions kept per instrument before the universe-wide correlation cross-tab. `measure` takes the
#: last 60 sessions a pair SHARES and is O(history) per call, and the universe produces hundreds of
#: thousands of pairs over streams reaching back decades. Generous slack for holidays and halts; a
#: pair that cannot find 60 shared sessions inside it is skipped, which is the right answer for a
#: name that stale.
RECENT_WINDOW = 200

#: The book this system caps: three held plus the candidate is the fourth.
BOOK = 3

#: The ratified correlation threshold, as a literal. This measurement is evidence ABOUT that
#: value and must not silently move when someone edits the registry.
CORRELATION_THRESHOLD = Decimal("0.70")

#: Books drawn from the universe. Enough that the rarest cap moves in the third decimal.
UNIVERSE_DRAWS = 20_000


def _exposures(path: Path) -> dict[str, Exposure]:
    """Saved vendor classifications, judged by the same guard the run uses."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    judged: dict[str, Exposure] = {}
    for symbol, entry in raw.items():
        if "error" in entry:
            continue
        classification = Classification(
            instrument_id=symbol,
            quote_type=entry["quote_type"],
            industry=entry.get("industry"),
            weights=tuple(
                SectorWeight(sector=sector, weight=Decimal(weight))
                for sector, weight in entry["weights"].items()
            ),
            knowledge_time=now,
        )
        judged[symbol] = look_through(classification, symbol)
    return judged


def _universe_cross_section(data: Path) -> dict[str, object]:
    """The same questions §14 asked of 68 names, asked of the whole admitted universe.

    §14.5 limit 2 is why this exists: 59 usable instruments is a thin cross-section and it leaned
    heavily financial, so every refusal rate it produced was more likely overstated than
    understated. The universe is what a run actually nominates from, it needs no trade log - only
    stored bars and stored classifications - and it can therefore be measured at full width as soon
    as `tools/refresh_classifications.py` has run.

    What this still CANNOT widen: anything needing trade OUTCOMES. Expectancy and the same-session
    gap stay bound to `PR-005`'s 68-name sample until a backtest runs over a wider one.
    """
    registry = ParameterRegistry.load()
    built = universe_builder.rule_from_registry(registry)
    if isinstance(built, Refusal):
        return {"unavailable": str(built)}

    rule, parameters = built
    with (
        BarStore(data / "bars.duckdb") as bars,
        ClassificationStore(data / "classifications.duckdb") as store,
        DirectoryStore(data / "directory.duckdb") as directory,
    ):
        if bars.latest_knowledge_time() is None:
            return {"unavailable": "the bar store holds nothing"}
        # NOW, not the bar store's latest knowledge time.
        #
        # Both stores are read as-of, and they are filled by DIFFERENT passes at different
        # instants: bars by the evening run, classifications by `refresh_classifications.py`
        # whenever it is run. Reading the classification store at the BAR store's as-of therefore
        # hides every classification pulled since the last bar refresh - which on a first run is
        # all of them, and this tool duly reported zero classified over a store holding 1,148. The
        # live path has it right: `pipeline.py` reads both at the RUN's clock, which is what this
        # reproduces.
        as_of = datetime.now(UTC)
        selection = universe_builder.select(
            directory, bars, rule, as_of, parameters=parameters
        )
        members = sorted(member.instrument.id for member in selection.members)
        stored = {symbol: store.as_of(symbol, as_of) for symbol in members}
        judged = {
            symbol: look_through(classification, symbol)
            for symbol, classification in stored.items()
        }
        usable = {symbol: e for symbol, e in judged.items() if e.is_available}

        # The sector MIX of the universe, by weight. What §14.5 limit 2 was really about.
        mix: dict[str, Decimal] = defaultdict(Decimal)
        for exposure in usable.values():
            for weight in exposure.weights:
                mix[weight.sector] += weight.weight
        total = sum(mix.values()) or Decimal(1)

        dominant = {
            symbol: max(exposure.weights, key=lambda weight: weight.weight).sector
            for symbol, exposure in usable.items()
        }
        streams = {}
        for symbol in sorted(dominant):
            stream = correlation.daily_returns(
                bars.as_of(symbol, Interval.DAY, Series.RAW, as_of)
            )
            if len(stream) >= 60:
                streams[symbol] = stream[-RECENT_WINDOW:]

    names = sorted(streams)
    same: list[float] = []
    cross: list[float] = []
    #: The pairs the correlation cap would refuse, kept so one draw can be scored against BOTH
    #: caps - which is how step 6 applies them, one after the other on the same book.
    hot: set[frozenset[str]] = set()
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            measured = correlation.measure(streams[left], streams[right], 60)
            if measured.r is None:
                continue
            (same if dominant[left] == dominant[right] else cross).append(float(measured.r))
            if measured.r >= CORRELATION_THRESHOLD:
                hot.add(frozenset((left, right)))

    def summarise(values: list[float]) -> dict[str, float]:
        over = sum(1 for value in values if value >= float(CORRELATION_THRESHOLD))
        return {
            "pairs": len(values),
            "median_r": statistics.median(values),
            "p90_r": sorted(values)[int(0.90 * (len(values) - 1))],
            "fraction_over_threshold": over / len(values),
        }

    return {
        "admitted": len(members),
        "measured_with_bars": selection.measured,
        "eligible": selection.eligible,
        "coverage": float(selection.coverage),
        # Counted from the STORE rather than inferred from a refusal message. Three different
        # facts, and a reader needs all three apart: admitted by the rule, classified at all, and
        # usable once `DR-006` §8.7's guard has judged the answer.
        "classified": sum(1 for value in stored.values() if value is not None),
        "usable": len(usable),
        "sector_mix": {sector: float(mix[sector] / total) for sector in sorted(mix)},
        "correlation_cross_section": {
            "instruments": len(names),
            "same_dominant_sector": summarise(same) if same else {},
            "different_sector": summarise(cross) if cross else {},
        },
        "four_position_books": _draw_from_universe(names, usable, hot),
    }


def _draw_from_universe(
    names: list[str],
    usable: dict[str, Exposure],
    hot: set[frozenset[str]],
) -> dict[str, object]:
    """Four-position books drawn from the ADMITTED UNIVERSE, scored against both caps.

    The model §14.2 could not use. There the book had to come from `PR-005`'s open positions,
    because a cap's bite depends on what is held and only the trade log said what was held - but
    those 68 names are one study's sample, and they proved to be both more correlated with each
    other and more concentrated by sector than the universe a run actually nominates from.

    Uniform, for the reason §14.1 gives: `rs.ranking_method` is `unset`, and a weighted draw would
    smuggle in an ordering the system refuses to make.

    **Both caps are scored on the SAME draw**, because that is how step 6 applies them - book, then
    correlation, then sector. Measuring each on a book of its own would let the two refusal rates
    be added, and they overlap.
    """
    rng = random.Random(SEED)
    binds = {str(cap): 0 for cap in CANDIDATE_CAPS}
    correlated = 0
    for _ in range(UNIVERSE_DRAWS):
        drawn = rng.sample(names, BOOK + 1)
        book, candidate = drawn[:BOOK], drawn[BOOK]
        if any(frozenset((candidate, held)) in hot for held in book):
            correlated += 1
        by_sector: dict[str, Decimal] = defaultdict(Decimal)
        for name in drawn:
            for weight in usable[name].weights:
                by_sector[weight.sector] += weight.weight * R_PER_POSITION
        top = max(by_sector.values()) if by_sector else Decimal(0)
        for cap in CANDIDATE_CAPS:
            if top > cap:
                binds[str(cap)] += 1
    return {
        "books": UNIVERSE_DRAWS,
        "seed": SEED,
        "correlation_cap_refuses": correlated / UNIVERSE_DRAWS,
        "sector_cap_refuses": {cap: count / UNIVERSE_DRAWS for cap, count in binds.items()},
    }


def _open_book_by_day() -> dict[date, set[str]]:
    """Which instruments the base slice held open on each calendar day."""
    rows = [
        row
        for row in csv.DictReader(TRADES.open(encoding="utf-8"))
        if row["arm"] == ARM and row["regime"] == REGIME
    ]
    held: dict[date, set[str]] = defaultdict(set)
    for row in rows:
        day, end = date.fromisoformat(row["entry_date"]), date.fromisoformat(row["exit_date"])
        while day < end:
            held[day].add(row["instrument_id"])
            day += timedelta(days=1)
    return dict(held)


def _quantiles(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        label: ordered[int(q * (len(ordered) - 1))]
        for q, label in ((0.5, "median"), (0.75, "p75"), (0.9, "p90"), (0.95, "p95"), (0.99, "p99"))
    } | {"max": ordered[-1]}


def _simulate(held: dict[date, set[str]], exposures: dict[str, Exposure]) -> dict[str, object]:
    """Four-position books drawn from each day's open names, scored against each candidate cap."""
    rng = random.Random(SEED)
    binds = {str(cap): 0 for cap in CANDIDATE_CAPS}
    heaviest: list[float] = []

    for day in sorted(held):
        names = sorted(held[day])
        if len(names) < 4:
            continue
        for _ in range(DRAWS_PER_DAY):
            by_sector: dict[str, Decimal] = defaultdict(Decimal)
            for name in rng.sample(names, 4):
                exposure = exposures.get(name)
                if exposure is None or not exposure.is_available:
                    continue
                for weight in exposure.weights:
                    by_sector[weight.sector] += weight.weight * R_PER_POSITION
            top = max(by_sector.values()) if by_sector else Decimal(0)
            heaviest.append(float(top))
            for cap in CANDIDATE_CAPS:
                if top > cap:
                    binds[str(cap)] += 1

    return {
        "books": len(heaviest),
        "draws_per_day": DRAWS_PER_DAY,
        "seed": SEED,
        "r_per_position": str(R_PER_POSITION),
        "heaviest_sector_r": _quantiles(heaviest),
        "refused_fraction": {cap: count / len(heaviest) for cap, count in binds.items()},
    }


def _correlation_overlap(exposures: dict[str, Exposure], data: Path) -> dict[str, object]:
    """Does the CORRELATION cap already refuse what a tight sector cap would refuse?

    The question that decides whether the two caps are redundant. Every usable pair is correlated
    over the ratified 60-session window and split by whether the two share a dominant sector.
    """
    dominant = {
        symbol: max(exposure.weights, key=lambda weight: weight.weight).sector
        for symbol, exposure in exposures.items()
        if exposure.is_available
    }
    with BarStore(data / "bars.duckdb") as store:
        as_of = store.latest_knowledge_time()
        if as_of is None:
            return {"unavailable": "the bar store holds nothing"}
        returns = {}
        for symbol in sorted(dominant):
            stream = correlation.daily_returns(
                store.as_of(symbol, Interval.DAY, Series.RAW, as_of)
            )
            if len(stream) >= 60:
                returns[symbol] = stream

    names = sorted(returns)
    same: list[float] = []
    cross: list[float] = []
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            measured = correlation.measure(returns[left], returns[right], 60)
            if measured.r is None:
                continue
            bucket = same if dominant[left] == dominant[right] else cross
            bucket.append(float(measured.r))

    def summarise(values: list[float]) -> dict[str, float]:
        over = sum(1 for value in values if value >= 0.70)
        return {
            "pairs": len(values),
            "median_r": statistics.median(values),
            "p90_r": sorted(values)[int(0.90 * (len(values) - 1))],
            "at_or_over_threshold": over,
            "fraction_over_threshold": over / len(values),
        }

    return {
        "instruments": len(names),
        "lookback_sessions": 60,
        "same_dominant_sector": summarise(same),
        "different_sector": summarise(cross),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="measure_sector_cap")
    parser.add_argument("--classifications", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--wide", action="store_true",
                        help="also measure the sector mix and the correlation cross-tab over the "
                             "WHOLE admitted universe, which needs no trade log and closes the "
                             "thin-cross-section limit in DR-006 14.5")
    args = parser.parse_args(argv)

    exposures = _exposures(args.classifications)
    usable = sorted(s for s, e in exposures.items() if e.is_available)
    refused = sorted(s for s, e in exposures.items() if not e.is_available)

    held = _open_book_by_day()
    concurrency = sorted(len(names) for names in held.values())

    result: dict[str, object] = {
        "measured_on": datetime.now(UTC).date().isoformat(),
        "source": f"{TRADES.name}, arm {ARM}, regime {REGIME}",
        "classified": len(exposures),
        "usable": usable,
        "refused_by_the_guard": refused,
        "concurrency": {
            "days": len(concurrency),
            "median": statistics.median(concurrency),
            "max": max(concurrency),
            "days_over_four": sum(1 for n in concurrency if n > 4) / len(concurrency),
        },
        "four_position_books": _simulate(held, exposures),
        "correlation_overlap": _correlation_overlap(exposures, args.data),
    }
    if args.wide:
        result["universe_cross_section"] = _universe_cross_section(args.data)

    document = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(document + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
