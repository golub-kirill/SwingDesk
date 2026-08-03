"""Run PR-001: does the trend definition change which population is selected?

Orchestration only. Every number this produces comes from
`swingdesk.validation.studies.trend_overlap`, which is pure and tested; this script fetches, applies
the DR-003 liquidity rule, assembles inputs and writes the result.

The parameters below are read from the pre-registration, not from the registry. A study pins what it
actually ran under into its own record, rather than inheriting whatever the registry says later.

Network tool. Never imported by anything in src/, never run in CI.

    python tools/run_pr001.py --sample 150
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.market import Interval  # noqa: E402
from swingdesk.contracts.observation import ParameterUse  # noqa: E402
from swingdesk.decision_logic import trend  # noqa: E402
from swingdesk.derived_observations import moving_average, pivots  # noqa: E402
from swingdesk.market_data import vendor_yahoo  # noqa: E402
from swingdesk.reference_data import universe  # noqa: E402
from swingdesk.validation.studies import trend_overlap as study  # noqa: E402

DIRECTORY = {
    "nasdaq": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "other": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}

# --- from PR-001, fixed at registration -------------------------------------------------
SMA_SHORT = 50
SMA_LONG = 200
PIVOT_LEFT = 3
PIVOT_RIGHT = 3
PIVOT_COUNT = 2
ACCEPT_MEDIAN, ACCEPT_P10 = Decimal("0.70"), Decimal("0.50")
REJECT_MEDIAN, REJECT_P10 = Decimal("0.40"), Decimal("0.25")
# Section 8: at least 2000 trading sessions, and at least 30 instruments with FULL history over the
# window. Both, not either - the first run met the instrument floor with 45 and failed the session
# floor with 277, because the common window is bounded by the youngest instrument admitted.
MIN_SESSIONS = 2000
MIN_INSTRUMENTS = 30

# --- from DR-003 ------------------------------------------------------------------------
RULE = universe.LiquidityRule(
    min_price=Decimal("5.00"),
    min_adtv=Decimal("5000000"),
    adtv_window=20,
    min_history=250,
)


def _download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "swingdesk-research/0.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_pr001")
    parser.add_argument("--sample", type=int, default=150,
                        help="symbols drawn from the directory before the liquidity rule")
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument("--period", default="10y")
    parser.add_argument("--min-bars", type=int, default=MIN_SESSIONS,
                        help="instruments with less history than this are excluded; PR-001 8 "
                             "requires full history over the window")
    parser.add_argument("--out", type=Path, default=Path("docs/prereg/results/PR-001.json"))
    args = parser.parse_args()

    entries = [
        *universe.parse_nasdaq_listed(_download(DIRECTORY["nasdaq"])),
        *universe.parse_other_listed(_download(DIRECTORY["other"])),
    ]
    eligible = sorted((e for e in entries if e.is_eligible), key=lambda e: e.symbol)
    rng = random.Random(args.seed)
    sample = sorted(rng.sample(eligible, min(args.sample, len(eligible))), key=lambda e: e.symbol)
    print(f"directory {len(entries)} rows, {len(eligible)} eligible, sampled {len(sample)}")

    as_of = datetime.now(timezone.utc)
    admitted: dict[str, object] = {}
    rejected = failed = short_history = 0

    for index, entry in enumerate(sample, start=1):
        instrument = universe.to_instrument(entry)
        try:
            series = vendor_yahoo.fetch(instrument, Interval.DAY, as_of, period=args.period)
        except Exception:  # noqa: BLE001 - a research tool; failures are counted, not raised
            failed += 1
            continue
        if not RULE.admits(series):
            rejected += 1
            continue
        if len(series.bars) < args.min_bars:
            # Admitted by liquidity, excluded by history. A young listing shortens the window
            # common to the whole universe, and the common window is what the statistic runs on.
            short_history += 1
            continue
        admitted[instrument.id] = series
        if index % 25 == 0:
            print(f"  [{index}/{len(sample)}] admitted={len(admitted)} "
                  f"rejected={rejected} failed={failed}")

    print(f"\nuniverse: {len(admitted)} admitted, {rejected} rejected by the rule, "
          f"{failed} fetch failures")
    if len(admitted) < 30:
        print("REFUSING A VERDICT: PR-001 section 8 requires at least 30 instruments.")

    # Per-instrument observations, computed once.
    short_p = ParameterUse(id="sma.period", value=str(SMA_SHORT), provenance="assumed:PR-001")
    long_p = ParameterUse(id="sma.period", value=str(SMA_LONG), provenance="assumed:PR-001")
    left_p = ParameterUse(id="pivot.left", value=str(PIVOT_LEFT), provenance="assumed:PR-001")
    right_p = ParameterUse(id="pivot.right", value=str(PIVOT_RIGHT), provenance="assumed:PR-001")

    prepared: dict[str, dict] = {}
    for instrument_id, series in admitted.items():
        prepared[instrument_id] = {
            "series": series,
            "short": moving_average.compute(series, SMA_SHORT, short_p),
            "long": moving_average.compute(series, SMA_LONG, long_p),
            "highs": pivots.pivots(series, PIVOT_LEFT, PIVOT_RIGHT, highs=True),
            "lows": pivots.pivots(series, PIVOT_LEFT, PIVOT_RIGHT, highs=False),
        }

    # Sessions common to the whole universe, so every definition sees the same days.
    session_sets = [
        {bar.session_date for bar in item["series"].bars} for item in prepared.values()
    ]
    sessions = sorted(set.intersection(*session_sets)) if session_sets else []
    print(f"sessions common to every instrument: {len(sessions)}")

    index_by_date = {
        instrument_id: {bar.session_date: i for i, bar in enumerate(item["series"].bars)}
        for instrument_id, item in prepared.items()
    }

    daily: list[study.DailySelection] = []
    for session in sessions:
        inputs = {}
        for instrument_id, item in prepared.items():
            position = index_by_date[instrument_id].get(session)
            if position is None:
                continue
            inputs[instrument_id] = trend.inputs_from_series(
                position,
                item["series"].bars[position].close,
                sma_short=item["short"],
                sma_long=item["long"],
                highs=item["highs"],
                lows=item["lows"],
            )
        daily.append(study.select(session, inputs, pivot_count=PIVOT_COUNT))

    result = study.summarise("US", len(prepared), daily)
    verdict = result.verdict(ACCEPT_MEDIAN, ACCEPT_P10, REJECT_MEDIAN, REJECT_P10)

    # Section 8, both conditions. A verdict on an under-powered sample is a number with a label,
    # and the pre-registration says to report the coverage and refuse.
    valid = len(prepared) >= MIN_INSTRUMENTS and len(sessions) >= MIN_SESSIONS
    shortfall = []
    if len(prepared) < MIN_INSTRUMENTS:
        shortfall.append(f"{len(prepared)} instruments < {MIN_INSTRUMENTS}")
    if len(sessions) < MIN_SESSIONS:
        shortfall.append(f"{len(sessions)} common sessions < {MIN_SESSIONS}")

    print(f"\n{'pair':<40} {'sessions':>9} {'median':>8} {'p10':>8} {'min':>8} {'width':>7}")
    for pair in sorted(result.pairs, key=lambda p: p.median):
        print(f"{pair.label:<40} {pair.sessions:>9} {float(pair.median):>8.3f} "
              f"{float(pair.p10):>8.3f} {float(pair.minimum):>8.3f} "
              f"{float(pair.mean_decidable):>7.1f}")

    print(f"\nmean selected per session (of {len(prepared)}):")
    for name, mean in sorted(result.mean_selected.items()):
        print(f"  {name:<20} {float(mean):>7.2f}   undecided rate "
              f"{float(result.undecided_rate[name]):.3f}")
    print(f"\nVERDICT: {verdict}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "prereg": "PR-001",
                "run_at": as_of.isoformat(),
                "seed": args.seed,
                "sampled": len(sample),
                "admitted": sorted(prepared),
                "rejected_by_rule": rejected,
                "fetch_failures": failed,
                "sessions": len(sessions),
                "window": [str(sessions[0]), str(sessions[-1])] if sessions else None,
                "survivorship": "absent",
                "country": "US",
                "definitions": [d.name for d in study.RUNNABLE],
                "parameters": {
                    "sma_short": SMA_SHORT, "sma_long": SMA_LONG,
                    "pivot_left": PIVOT_LEFT, "pivot_right": PIVOT_RIGHT,
                    "pivot_count": PIVOT_COUNT,
                    "liquidity_rule": {
                        "min_price": str(RULE.min_price), "min_adtv": str(RULE.min_adtv),
                        "adtv_window": RULE.adtv_window, "min_history": RULE.min_history,
                    },
                },
                "pairs": [
                    {
                        "left": p.left, "right": p.right, "sessions": p.sessions,
                        "median": str(p.median), "p10": str(p.p10), "min": str(p.minimum),
                        "mean_decidable": str(p.mean_decidable),
                    }
                    for p in result.pairs
                ],
                "mean_selected": {k: str(v) for k, v in result.mean_selected.items()},
                "undecided_rate": {k: str(v) for k, v in result.undecided_rate.items()},
                "short_history_exclusions": short_history,
                "verdict": verdict if valid else "refused",
                "verdict_if_sample_had_been_met": verdict,
                "verdict_valid": valid,
                "sample_shortfall": shortfall,
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
