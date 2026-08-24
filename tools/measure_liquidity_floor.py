"""Recompute DR-003's liquidity plateau over the stored population instead of a 115-name sample.

**The question, and it is DR-003's own.** That record's Consequence 5 says the plateau "was located
on 115 instruments and should be re-checked on the population", and its Known gap 3 says the sample
is "not adequate for tail percentiles". This is that re-check. Nothing here proposes a value; it
measures what each candidate floor admits so a ruling has a population under it rather than 115
names.

**What this deliberately does NOT measure.** Effective spread per liquidity tier. `PR-010` already
ran EDGE across ADTV thirds and read 25.45 / 27.90 / 24.02 bp - flat, with the most liquid third the
lowest - and `HANDOFF.md` section 7 closes the spread LEVEL from daily OHLC by evidence. A sweep of
modelled spread against the floor would re-run a refuted measurement and dress it as new. The
admitted POPULATION is measurable; the spread it would pay is not.

**The production path, not a parallel one.** ADTV comes from `average_dollar_volume` and admission
from the same three comparisons `LiquidityRule.admits` makes, so a floor's membership here is the
membership the daily run would compute. A measurement that reimplemented the rule could disagree
with the rule and nobody would know which was wrong.

**The sample is not random, and the tool says so rather than assuming it away.** The store holds
whatever `tools/refresh_universe.py` has fetched, and that tool queues never-fetched symbols first
in directory order - so the stored set is closer to a prefix of the directory than to a draw from
it. `DR-003` gap 2 records separately that warrants, units and rights fetch as nothing at all, which
is a systematic absence rather than a random one. The output carries the rank distribution of stored
symbols within the directory so the bias is a number a reader can weigh rather than a caveat they
have to trust.

Offline. Reads `data/bars.duckdb` and `data/directory.duckdb` at the bar store's own latest
knowledge time, so two runs over an unchanged store return the same answer.

    python tools/measure_liquidity_floor.py \\
        --data C:/PycharmProjects/SwingDesk/data \\
        --out docs/decisions/measurements/liquidity-floor-2026-08-23.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.application.universe import ADTV_WINDOW
from swingdesk.contracts.market import Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.reference_data import universe as rules
from swingdesk.reference_data.directory import DirectoryStore

#: ADTV floors to sweep, in USD per day. Spans three orders of magnitude around DR-003's 5M so the
#: plateau that record located between 5M and 25M is confirmed or refuted, and so the cliff it
#: rejected at 1M is measured rather than remembered.
ADTV_FLOORS = (
    Decimal(100_000), Decimal(250_000), Decimal(500_000), Decimal(1_000_000),
    Decimal(2_000_000), Decimal(5_000_000), Decimal(10_000_000), Decimal(25_000_000),
    Decimal(50_000_000), Decimal(100_000_000),
)

#: Price floors to sweep, holding ADTV and history at the ratified values. DR-003 justifies 5.00 on
#: the cost side rather than the population side, so what it costs in names is worth a number.
PRICE_FLOORS = (Decimal(0), Decimal(1), Decimal(2), Decimal(5), Decimal(10), Decimal(20))

#: The reference ADTV floor the price sweep holds fixed: DR-003's ratified value.
RATIFIED_ADTV = Decimal(5_000_000)

PERCENTILES = (5, 10, 25, 50, 75, 90, 95, 99)

#: `DR-003`'s seeded 115-name random sample, quoted from that record's own table so the population
#: can be diffed against it here rather than by eye. It is carried as a constant because it is
#: history: the record must not be rewritten, and the comparison has to live somewhere a tool can
#: recompute it. Gap 3 of that record says these tail figures should not be quoted as precise, which
#: is exactly what the diff below tests.
DR003_SAMPLE_ADTV = {
    "p5": 12_974.0, "p10": 31_265.0, "p25": 191_371.0,
    "p50": 1_241_658.0, "p75": 34_056_034.0, "p90": 110_426_657.0,
}


@dataclass(frozen=True, slots=True)
class Measured:
    """One stored instrument reduced to what the rule reads. Values only, no verdict."""

    instrument_id: str
    is_etf: bool
    close: Decimal
    adtv: Decimal
    bars: int
    last_session: date
    rank: int


def percentiles(values: list[Decimal], points: tuple[int, ...] = PERCENTILES) -> dict[str, float]:
    """Nearest-rank percentiles: exact order statistics, never a value between two real names."""
    if not values:
        return {}
    ordered = sorted(values)
    out: dict[str, float] = {}
    for point in points:
        index = min(len(ordered) - 1, max(0, round(point / 100 * len(ordered)) - 1))
        out[f"p{point}"] = float(ordered[index])
    return out


def measure(data: Path) -> tuple[datetime, int, int, list[Measured]]:
    """Every stored, eligible instrument with a full ADTV window, measured the way the run does."""
    with (
        BarStore(data / "bars.duckdb") as store,
        DirectoryStore(data / "directory.duckdb") as directory,
    ):
        as_of = store.latest_knowledge_time()
        if as_of is None:
            raise SystemExit("bar store is empty - nothing to measure")

        entries = directory.as_of(as_of, eligible_only=True)
        stored = set(store.instrument_ids(as_of))

        population: list[Measured] = []
        for rank, entry in enumerate(entries):
            if entry.symbol not in stored:
                continue
            series = store.as_of(entry.symbol, Interval.DAY, Series.RAW, as_of)
            if not series.bars:
                continue
            adtv = rules.average_dollar_volume(series, ADTV_WINDOW)
            if adtv is None:
                # Fewer than 20 stored bars. NOT a rejection by the rule: the window could not be
                # formed, so this instrument is unanswerable rather than illiquid, and counting it
                # as excluded would inflate every floor's rejection rate by the same amount.
                continue
            population.append(
                Measured(
                    instrument_id=entry.symbol,
                    is_etf=entry.is_etf,
                    close=series.bars[-1].close,
                    adtv=adtv,
                    bars=len(series.bars),
                    last_session=series.bars[-1].session_date,
                    rank=rank,
                )
            )
        return as_of, len(entries), len(stored), population


def admit(population: list[Measured], min_price: Decimal, min_adtv: Decimal,
          min_history: int) -> list[Measured]:
    """The three comparisons `LiquidityRule.admits` makes, applied to already-measured values."""
    return [
        member for member in population
        if member.bars >= min_history
        and member.close >= min_price
        and member.adtv >= min_adtv
    ]


def _delta(previous: int | None, current: int) -> str:
    return "-" if previous is None else f"-{previous - current}"


def elasticity(previous: int, current: int, from_floor: Decimal, to_floor: Decimal) -> float:
    """Share of membership lost per DOUBLING of the floor, between two adjacent sweep points.

    The raw delta between two floors cannot be compared across a sweep whose steps are not equal
    multiples - 2M to 5M is 1.32 doublings and 5M to 10M is one, so the larger step loses more names
    for reasons that have nothing to do with the distribution. Dividing by log2 of the ratio is what
    makes "is this floor on a plateau?" a question the numbers can answer.

    This is the quantity `DR-003` argued from in words ("a doubling ... changes membership by two
    instruments out of 115") and never computed, which is why a sample too small to resolve it read
    as a plateau.
    """
    if previous <= 0:
        return 0.0
    doublings = (to_floor / from_floor).ln() / Decimal(2).ln()
    return float((Decimal(previous - current) / Decimal(previous)) / doublings)


def main() -> int:
    parser = argparse.ArgumentParser(prog="measure_liquidity_floor")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--min-price", type=Decimal, default=Decimal("5.00"),
                        help="held fixed while ADTV is swept (DR-003)")
    parser.add_argument("--min-history", type=int, default=250,
                        help="held fixed while ADTV is swept (DR-003)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    as_of, eligible, stored, population = measure(args.data)
    if not population:
        raise SystemExit("no instrument has a full ADTV window - nothing to measure")

    print(f"as of      {as_of.isoformat()}  (the bar store's own latest knowledge time)")
    print(f"directory  {eligible} eligible symbols")
    print(f"stored     {stored} with bars ({stored / eligible:.1%} of eligible)")
    print(f"measurable {len(population)} with a full {ADTV_WINDOW}-bar window\n")

    # How representative the stored set is. Measured, because the answer decides how far any
    # percentile below may be read as a statement about the directory rather than about us.
    ranks = [Decimal(member.rank) for member in population]
    first_half = sum(1 for member in population if member.rank < eligible / 2)
    rank_share = first_half / len(population)
    rank_pcts = percentiles(ranks)
    print("REPRESENTATIVENESS - the stored set is not a random draw")
    print(f"  measured names in the directory's first half: {rank_share:.1%} "
          f"(a uniform draw reads 50.0%)")
    print(f"  directory rank p25/p50/p75: {rank_pcts['p25']:,.0f} / {rank_pcts['p50']:,.0f} / "
          f"{rank_pcts['p75']:,.0f} of {eligible}")

    sessions = sorted({member.last_session for member in population})
    behind = sum(1 for member in population if member.last_session != sessions[-1])
    print(f"  last stored session spans {sessions[0]} to {sessions[-1]}; {behind} of "
          f"{len(population)} are behind the newest ({behind / len(population):.1%})\n")

    # The distributions DR-003 gap 3 says its 115 names could not support.
    adtv_pcts = percentiles([member.adtv for member in population])
    print(f"ADTV over {len(population)} measured names, USD/day"
          f"  (DR-003's 115-name sample beside it)")
    sample_diff: dict[str, float] = {}
    for key, value in adtv_pcts.items():
        sampled = DR003_SAMPLE_ADTV.get(key)
        if sampled is None:
            print(f"  {key:>4}  {value:>18,.0f}")
            continue
        ratio = value / sampled
        sample_diff[key] = round(ratio, 3)
        print(f"  {key:>4}  {value:>18,.0f}   sample {sampled:>15,.0f}   x{ratio:.2f}")

    close_pcts = percentiles([member.close for member in population])
    print("\nLast close, USD")
    for key, value in close_pcts.items():
        print(f"  {key:>4}  {value:>18,.2f}")

    # The plateau. Membership at each floor and the MARGINAL move between adjacent floors, which is
    # the quantity DR-003 actually argued from ("two instruments out of 115").
    print(f"\nADMISSION by ADTV floor, price >= {args.min_price}, history >= {args.min_history}")
    print(f"{'floor':>14} {'admitted':>9} {'of measured':>12} {'ETF share':>10} "
          f"{'vs previous':>12} {'lost/doubling':>14}")
    adtv_sweep: list[dict[str, object]] = []
    admitted_by_floor: dict[int, int] = {}
    curve: list[tuple[int, float]] = []
    previous: int | None = None
    previous_floor: Decimal | None = None
    for floor in ADTV_FLOORS:
        admitted = admit(population, args.min_price, floor, args.min_history)
        etfs = sum(1 for member in admitted if member.is_etf)
        share = len(admitted) / len(population)
        etf_share = etfs / len(admitted) if admitted else 0.0
        per_doubling = (
            None if previous is None or previous_floor is None
            else elasticity(previous, len(admitted), previous_floor, floor)
        )
        print(f"{int(floor):>14,} {len(admitted):>9} {share:>11.1%} {etf_share:>10.1%} "
              f"{_delta(previous, len(admitted)):>12} "
              f"{'-' if per_doubling is None else f'{per_doubling:.1%}':>14}")
        adtv_sweep.append({
            "min_adtv": int(floor),
            "admitted": len(admitted),
            "etfs": etfs,
            "share_of_measured": round(share, 4),
            "lost_vs_previous_floor": None if previous is None else previous - len(admitted),
            "share_lost_per_doubling": None if per_doubling is None else round(per_doubling, 4),
        })
        admitted_by_floor[int(floor)] = len(admitted)
        if per_doubling is not None:
            curve.append((int(floor), per_doubling))
        previous = len(admitted)
        previous_floor = floor

    # `DR-003`'s plateau claim, tested as the claim was actually made. That record chose 5M because
    # "the choice is insensitive anywhere on the 5M-25M plateau" and argued it from one step: 5M to
    # 10M moving membership "by two instruments out of 115", which is 5.3% of that sample's admitted
    # set. So the test is not generic curvature - it is what the named range costs here.
    at_low = admitted_by_floor[5_000_000]
    at_mid = admitted_by_floor[10_000_000]
    at_high = admitted_by_floor[25_000_000]
    one_doubling = elasticity(at_low, at_mid, Decimal(5_000_000), Decimal(10_000_000))
    whole_range = elasticity(at_low, at_high, Decimal(5_000_000), Decimal(25_000_000))
    print("\nPLATEAU CHECK - DR-003's named 5M-25M range, tested as claimed")
    print(f"  5M admits {at_low}, 10M admits {at_mid}, 25M admits {at_high}")
    print(f"  5M -> 10M  loses {at_low - at_mid} names, {one_doubling:.1%} per doubling "
          f"(the sample read 5.3%)")
    print(f"  5M -> 25M  loses {at_low - at_high} names, "
          f"{(at_low - at_high) / at_low:.1%} of membership, {whole_range:.1%} per doubling")
    plateau = one_doubling <= 0.053
    print(f"  verdict: the range is {'FLAT as claimed' if plateau else 'NOT flat - no plateau'}")

    cheapest = min(curve, key=lambda point: point[1])
    dearest = max(curve, key=lambda point: point[1])
    print(f"  across the whole sweep the cheapest step ends at {cheapest[0]:,} "
          f"({cheapest[1]:.1%} per doubling) and the dearest at {dearest[0]:,} "
          f"({dearest[1]:.1%})")

    print(f"\nADMISSION by price floor, ADTV >= {int(RATIFIED_ADTV):,}, "
          f"history >= {args.min_history}")
    print(f"{'floor':>14} {'admitted':>9} {'vs previous':>12}")
    price_sweep: list[dict[str, object]] = []
    previous = None
    for floor in PRICE_FLOORS:
        admitted = admit(population, floor, RATIFIED_ADTV, args.min_history)
        print(f"{float(floor):>14,.2f} {len(admitted):>9} "
              f"{_delta(previous, len(admitted)):>12}")
        price_sweep.append({
            "min_price": float(floor),
            "admitted": len(admitted),
            "lost_vs_previous_floor": None if previous is None else previous - len(admitted),
        })
        previous = len(admitted)

    # What the ratified rule admits today, so the record can quote one number for itself.
    ratified = admit(population, args.min_price, RATIFIED_ADTV, args.min_history)
    history_only = [member for member in population if member.bars >= args.min_history]
    print(f"\nAt DR-003's ratified values: {len(ratified)} admitted of {len(population)} measurable")
    print(f"  history alone (>= {args.min_history} bars) admits {len(history_only)}")

    result = {
        "as_of": as_of.isoformat(),
        "adtv_window": ADTV_WINDOW,
        "directory_eligible": eligible,
        "stored_with_bars": stored,
        "measurable": len(population),
        "representativeness": {
            "share_in_directory_first_half": round(rank_share, 4),
            "directory_rank_percentiles": rank_pcts,
            "last_session_min": str(sessions[0]),
            "last_session_max": str(sessions[-1]),
            "behind_newest_session": behind,
        },
        "adtv_percentiles_usd_per_day": adtv_pcts,
        "adtv_percentile_ratio_to_dr003_sample": sample_diff,
        "plateau_check": {
            "claim": "DR-003: the choice is insensitive anywhere on the 5M-25M plateau",
            "sample_read_per_doubling": 0.053,
            "admitted_at_5m": at_low,
            "admitted_at_10m": at_mid,
            "admitted_at_25m": at_high,
            "share_lost_per_doubling_5m_to_10m": round(one_doubling, 4),
            "share_lost_per_doubling_5m_to_25m": round(whole_range, 4),
            "share_of_5m_membership_lost_by_25m": round((at_low - at_high) / at_low, 4),
            "range_is_flat_as_claimed": plateau,
            "cheapest_step_min_adtv": cheapest[0],
            "cheapest_step_share_lost_per_doubling": cheapest[1],
            "dearest_step_min_adtv": dearest[0],
            "dearest_step_share_lost_per_doubling": dearest[1],
        },
        "close_percentiles_usd": close_pcts,
        "held_fixed": {"min_price": float(args.min_price), "min_bar_history": args.min_history},
        "adtv_sweep": adtv_sweep,
        "price_sweep": price_sweep,
        "ratified_rule_admits": len(ratified),
        "history_alone_admits": len(history_only),
        "not_measured": (
            "effective spread per liquidity tier - PR-010 measured EDGE flat across ADTV thirds "
            "and HANDOFF section 7 closes the spread level from daily OHLC by evidence"
        ),
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
