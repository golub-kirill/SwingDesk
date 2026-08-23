"""Calibrate the correlation cap: what it would have refused, and what that would have cost.

**The question.** `DR-006` §11.3 reading 1 built the cap to REFUSE a correlated candidate, because
`RISK_SPEC` §4 names *"correlation threshold and its size adjustment"* and only the threshold has a
value. Halving the size instead is defensible and needs a multiplier nobody has authored. §13
carries it as an owner ruling; this is the measurement the ruling needs.

**Point-in-time throughout.** Every correlation is computed over the 60 sessions ending strictly
BEFORE the candidate's entry date, from the same `derived_observations.correlation.pearson` the run
uses. A calibration that correlated with today's window would be answering a question the system
never gets to ask.

**Three measurements, because they answer different halves.**

  1. **The bite.** How often the cap refuses - both in `PR-005`'s own book, which held a median of
     22 names at once, and on the FOUR-position book this system actually caps. The second is the
     production number and it is computed exactly rather than sampled: given `n` names held and `k`
     of them correlated with the candidate, the chance a three-name book contains at least one is
     `1 - C(n-k,3)/C(n,3)`.
  2. **The cost.** What the refused trades returned, against what the admitted ones returned, with
     a **block bootstrap by calendar year**. A naive standard error here would be badly optimistic:
     the same trade appears in many co-held pairs and the same year's trades share a regime, so the
     events are nowhere near independent. Resampling whole years is the cheapest honest interval.
  3. **The premise, on two measures that disagree.** §2 justifies the threshold by saying two names
     sharing half their variance are one bet. That is testable rather than quotable, and the answer
     depends entirely on which joint outcome is measured:

     * `P(both lose)` over the whole holding period - the coarse measure. Two names can move
       together daily and still exit weeks apart for unrelated reasons, so this washes the effect
       out and is reported because a calibration that quoted only the supportive measure would be
       the `PR-008` withdrawal repeating itself.
     * **`P(both gapped out on the SAME session)`** - the precise one, and the failure mode §8.2
       built the entire risk block around: the simultaneous overnight gap a per-trade stop cannot
       defend against, because the price it names does not trade between the close and the open.

**What this cannot do**, and it is the same ceiling `tools/measure_sector_cap.py` hits: `PR-005` is
a per-instrument backtest with no capital constraint, so it never simulated a four-position book
and cannot be replayed as one. Measurement 1 corrects for that arithmetically; measurements 2 and 3
are conditional statistics on trades that were actually taken, which is a weaker but still
point-in-time-clean claim.

    python tools/measure_correlation_cap.py \\
        --out docs/decisions/measurements/correlation-cap-calibration-2026-08-23.json
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.market import Interval, Series
from swingdesk.derived_observations import correlation
from swingdesk.market_data import BarStore

REPO = Path(__file__).resolve().parents[1]
TRADES = REPO / "docs" / "prereg" / "results" / "PR-005-trades.csv"

#: The base slice: no overlay, one regime. Mixing arms overlaps trades from variants that were
#: never live together, and every co-held pair drawn across them would be an artefact.
ARM, REGIME = "NONE", "1x"

#: The ratified pair, read as literals rather than from the registry: this measurement is evidence
#: ABOUT those values and must not silently move when someone edits them.
LOOKBACK = 60
THRESHOLD = Decimal("0.70")

#: The book this system caps. Three held plus the candidate is the fourth.
BOOK = 3

BOOTSTRAP_DRAWS = 2000
SEED = 20260823


def _trades() -> list[dict[str, str]]:
    rows = [
        row
        for row in csv.DictReader(TRADES.open(encoding="utf-8"))
        if row["arm"] == ARM and row["regime"] == REGIME
    ]
    return sorted(rows, key=lambda row: (row["entry_date"], row["instrument_id"]))


def _return_streams(data: Path, names: list[str]) -> dict[str, tuple]:
    with BarStore(data / "bars.duckdb") as store:
        as_of = store.latest_knowledge_time()
        if as_of is None:
            raise SystemExit("the bar store holds nothing")
        return {
            name: correlation.daily_returns(
                store.as_of(name, Interval.DAY, Series.RAW, as_of)
            )
            for name in names
        }


class _Pairs:
    """Shared return windows per instrument pair, built once and sliced by entry date.

    Built lazily and cached because the alternative - calling `correlation.measure` per event - is
    O(history) per call over streams reaching back to 1962, and there are tens of thousands of
    events. The statistic itself is `correlation.pearson`, unchanged, so these are the numbers the
    run would have produced.
    """

    def __init__(self, streams: dict[str, tuple]) -> None:
        self._streams = streams
        self._cache: dict[tuple[str, str], tuple[list, list]] = {}

    def correlate(self, left: str, right: str, before: date) -> Decimal | None:
        key = (left, right) if left < right else (right, left)
        if key not in self._cache:
            other = {item.session_date: item.value for item in self._streams[key[1]]}
            shared = [
                (item.session_date, item.value, other[item.session_date])
                for item in self._streams[key[0]]
                if item.session_date in other
            ]
            self._cache[key] = (shared, [row[0] for row in shared])
        shared, dates = self._cache[key]
        end = bisect.bisect_left(dates, before)
        if end < LOOKBACK:
            return None
        window = shared[end - LOOKBACK:end]
        return correlation.pearson([row[1] for row in window], [row[2] for row in window])


def _block_bootstrap(by_year: dict[int, list[float]]) -> tuple[float, float]:
    """A 95% interval by resampling whole calendar years.

    Trades within a year share a regime and overlap in time, so treating them as independent draws
    would produce an interval far tighter than the evidence supports. Years are the coarsest block
    this sample can afford and still the honest one.
    """
    rng = random.Random(SEED)
    years = sorted(by_year)
    means = []
    for _ in range(BOOTSTRAP_DRAWS):
        pool = [value for year in (rng.choice(years) for _ in years) for value in by_year[year]]
        means.append(statistics.mean(pool))
    means.sort()
    return means[int(0.025 * len(means))], means[int(0.975 * len(means))]


def _summarise(events: list[tuple[int, float]]) -> dict[str, float]:
    values = sorted(value for _, value in events)
    by_year: dict[int, list[float]] = defaultdict(list)
    for year, value in events:
        by_year[year].append(value)
    low, high = _block_bootstrap(by_year)
    return {
        "trades": len(values),
        "mean_net_r": statistics.mean(values),
        "block_ci_95": [low, high],
        "median_net_r": statistics.median(values),
        "p5_net_r": values[len(values) // 20],
        "loss_rate": sum(1 for value in values if value < 0) / len(values),
        "total_net_r": sum(values),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="measure_correlation_cap")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    trades = _trades()
    names = sorted({row["instrument_id"] for row in trades})
    pairs = _Pairs(_return_streams(args.data, names))

    refused: list[tuple[int, float]] = []
    admitted: list[tuple[int, float]] = []
    book_probability: list[float] = []
    correlated_share: list[float] = []
    joint_above: list[tuple[float, float]] = []
    joint_below: list[tuple[float, float]] = []
    #: (year, both gapped out on the same session), split above and below the threshold.
    gap_above: list[tuple[int, bool]] = []
    gap_below: list[tuple[int, bool]] = []

    for index, candidate in enumerate(trades):
        entry = date.fromisoformat(candidate["entry_date"])
        net_r = float(candidate["net_r"])
        held = sorted(
            {
                row["instrument_id"]
                for row in trades[:index]
                if date.fromisoformat(row["entry_date"])
                <= entry
                < date.fromisoformat(row["exit_date"])
                and row["instrument_id"] != candidate["instrument_id"]
            }
        )
        gapped = candidate["exit_reason"] == "stop_gap"
        exit_date = candidate["exit_date"]
        hot = 0
        for name in held:
            r = pairs.correlate(name, candidate["instrument_id"], entry)
            if r is None:
                continue
            partner = next(
                (
                    row
                    for row in trades[:index]
                    if row["instrument_id"] == name
                    and date.fromisoformat(row["entry_date"])
                    <= entry
                    < date.fromisoformat(row["exit_date"])
                ),
                None,
            )
            if partner is not None:
                above = r >= THRESHOLD
                (joint_above if above else joint_below).append(
                    (net_r, float(partner["net_r"]))
                )
                # The precise premise test: both stopped out on a GAP, on the SAME session.
                together = (
                    gapped
                    and partner["exit_reason"] == "stop_gap"
                    and partner["exit_date"] == exit_date
                )
                (gap_above if above else gap_below).append((entry.year, together))
            if r >= THRESHOLD:
                hot += 1

        (refused if hot else admitted).append((entry.year, net_r))
        if len(held) >= BOOK:
            clean = len(held) - hot
            uncorrelated_books = math.comb(clean, BOOK) if clean >= BOOK else 0
            book_probability.append(1.0 - uncorrelated_books / math.comb(len(held), BOOK))
            correlated_share.append(hot / len(held))

    def joint(events: list[tuple[float, float]]) -> dict[str, float]:
        both = sum(1 for a, b in events if a < 0 and b < 0)
        return {
            "pairs": len(events),
            "p_both_lose": both / len(events) if events else 0.0,
            "mean_combined_net_r": statistics.mean(a + b for a, b in events) if events else 0.0,
        }

    def same_session_gap() -> dict[str, object]:
        """`P(both gapped out on the same session)`, above and below, with a bootstrapped lift.

        The lift is resampled by calendar YEAR rather than by pair. The events are rare and heavily
        clustered - `DR-006` §8.6 measured 89 sessions holding 52% of all gap exits - so a binomial
        interval over pairs would describe a sample that does not exist.
        """
        rng = random.Random(SEED)
        above_by_year: dict[int, list[bool]] = defaultdict(list)
        below_by_year: dict[int, list[bool]] = defaultdict(list)
        for year, together in gap_above:
            above_by_year[year].append(together)
        for year, together in gap_below:
            below_by_year[year].append(together)
        years = sorted(set(above_by_year) & set(below_by_year))

        lifts = []
        for _ in range(BOOTSTRAP_DRAWS):
            picked = [rng.choice(years) for _ in years]
            above = [v for y in picked for v in above_by_year[y]]
            below = [v for y in picked for v in below_by_year[y]]
            if not above or not below or not sum(below):
                continue
            lifts.append((sum(above) / len(above)) / (sum(below) / len(below)))
        lifts.sort()

        rate_above = sum(t for _, t in gap_above) / len(gap_above)
        rate_below = sum(t for _, t in gap_below) / len(gap_below)
        return {
            "at_or_over_threshold": {
                "pairs": len(gap_above),
                "events": sum(t for _, t in gap_above),
                "rate": rate_above,
            },
            "under": {
                "pairs": len(gap_below),
                "events": sum(t for _, t in gap_below),
                "rate": rate_below,
            },
            "lift": rate_above / rate_below,
            "lift_block_ci_95": [
                lifts[int(0.025 * len(lifts))],
                lifts[int(0.975 * len(lifts))],
            ],
        }

    result = {
        "measured_on": datetime.now(UTC).date().isoformat(),
        "source": f"{TRADES.name}, arm {ARM}, regime {REGIME}",
        "threshold": str(THRESHOLD),
        "lookback_sessions": LOOKBACK,
        "trades": len(trades),
        "bite": {
            "in_pr005_own_book": {
                "median_names_held": statistics.median(
                    len(
                        {
                            row["instrument_id"]
                            for row in trades[:i]
                            if date.fromisoformat(row["entry_date"])
                            <= date.fromisoformat(c["entry_date"])
                            < date.fromisoformat(row["exit_date"])
                        }
                    )
                    for i, c in enumerate(trades)
                ),
                "refused_fraction": len(refused) / len(trades),
            },
            "on_a_four_position_book": {
                "candidates": len(book_probability),
                "mean_refusal_probability": statistics.mean(book_probability),
                "never_refused_fraction": sum(1 for p in book_probability if p == 0)
                / len(book_probability),
                "mean_correlated_share_of_held": statistics.mean(correlated_share),
            },
        },
        "cost": {"refused": _summarise(refused), "admitted": _summarise(admitted)},
        "premise": {
            "both_lose_over_the_holding_period": {
                "at_or_over_threshold": joint(joint_above),
                "under": joint(joint_below),
            },
            "both_gapped_out_on_the_same_session": same_session_gap(),
        },
        "bootstrap": {"draws": BOOTSTRAP_DRAWS, "seed": SEED, "block": "calendar year"},
    }

    document = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(document + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
