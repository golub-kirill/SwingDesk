"""Run PR-005: do the trend definitions' populations behave differently, net of costs?

Orchestration only. Every number comes from `validation.backtest` and
`validation.studies.trend_performance`, both pure and tested.

The constants below are read from the pre-registration. They are NOT registry values, and that is
deliberate: a study records what it actually ran under, rather than inheriting whatever gets
ratified later.

Network tool. Never imported by anything in src/, never run in CI.

    python tools/run_pr005.py --sample 320
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.market import BarSeries, Interval
from swingdesk.contracts.observation import ParameterUse
from swingdesk.decision_logic import trend
from swingdesk.decision_logic.trend import TrendDefinition, is_uptrend
from swingdesk.derived_observations import atr as atr_component
from swingdesk.derived_observations import moving_average, pivots
from swingdesk.market_data import vendor_yahoo
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data import universe
from swingdesk.validation.backtest import (
    BacktestConfig,
    BreakoutHigh,
    CostModel,
    ExitPolicy,
    run_arm,
)
from swingdesk.validation.studies import trend_performance as study

DIRECTORY = {
    "nasdaq": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "other": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}

# --- PR-005 section 5, fixed at registration -------------------------------------------
SMA_SHORT, SMA_LONG = 50, 200
PIVOT_LEFT, PIVOT_RIGHT, PIVOT_COUNT = 3, 3, 2
ATR_PERIOD = 14
TRIGGER_LOOKBACK = 20
ATR_STOP_MULTIPLE = Decimal("2.0")
MAX_HOLDING_BARS = 20
RISK_PER_TRADE = Decimal(1000)
COMMISSION_PER_SHARE = Decimal("0.005")
SLIPPAGE_BPS = Decimal(5)
STRESS_MULTIPLE = Decimal(3)
BOOTSTRAP_RESAMPLES = 10_000
SEED = 20260802

# --- section 8 --------------------------------------------------------------------------
MIN_TRADES_PRIMARY = 200
MIN_TRADES_HOLDOUT = 60
HOLDOUT_FRACTION = Decimal("0.30")

# --- DR-003 -----------------------------------------------------------------------------
RULE = universe.LiquidityRule(
    min_price=Decimal("5.00"), min_adtv=Decimal("5000000"),
    adtv_window=20, min_history=250,
    adtv_lag=0,  # DR-017's lag postdates this study; 0 is the rule it ran under
)

ARMS: dict[str, TrendDefinition | None] = {
    "NONE": None,
    "A": TrendDefinition.ABOVE_LONG_MA,
    "B": TrendDefinition.MA_STACK,
    "C": TrendDefinition.PRICE_AND_STACK,
    "D": TrendDefinition.STRUCTURE,
}


def _download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "swingdesk-research/0.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def _atr_registry() -> ParameterRegistry:
    return ParameterRegistry({
        "atr.period": {"id": "atr.period", "value": ATR_PERIOD, "provenance": "assumed:PR-005",
                       "unit": "bars", "named_in": ["PR-005"]},
    })


def _gates(series: BarSeries) -> dict[str, list[bool | None]]:
    """Every arm's per-bar verdict, computed once per instrument."""
    short_p = ParameterUse(id="sma.period", value=str(SMA_SHORT), provenance="assumed:PR-005")
    long_p = ParameterUse(id="sma.period", value=str(SMA_LONG), provenance="assumed:PR-005")
    short = moving_average.compute(series, SMA_SHORT, short_p)
    long = moving_average.compute(series, SMA_LONG, long_p)
    highs = pivots.pivots(series, PIVOT_LEFT, PIVOT_RIGHT, highs=True)
    lows = pivots.pivots(series, PIVOT_LEFT, PIVOT_RIGHT, highs=False)

    per_arm: dict[str, list[bool | None]] = {name: [] for name in ARMS}
    for index, bar in enumerate(series.bars):
        inputs = trend.inputs_from_series(
            index, bar.close, sma_short=short, sma_long=long, highs=highs, lows=lows
        )
        for name, definition in ARMS.items():
            if definition is None:
                per_arm[name].append(True)  # ungated reference: the trigger alone
            else:
                per_arm[name].append(is_uptrend(definition, inputs, pivot_count=PIVOT_COUNT))
    return per_arm


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_pr005")
    parser.add_argument("--sample", type=int, default=320)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--period", default="10y")
    parser.add_argument("--min-bars", type=int, default=2000)
    parser.add_argument("--out", type=Path, default=Path("docs/prereg/results/PR-005.json"))
    args = parser.parse_args()

    entries = [
        *universe.parse_nasdaq_listed(_download(DIRECTORY["nasdaq"])),
        *universe.parse_other_listed(_download(DIRECTORY["other"])),
    ]
    eligible = sorted((e for e in entries if e.is_eligible), key=lambda e: e.symbol)
    rng = random.Random(args.seed)
    sample = sorted(rng.sample(eligible, min(args.sample, len(eligible))), key=lambda e: e.symbol)
    print(f"directory {len(entries)} rows, {len(eligible)} eligible, sampled {len(sample)}")

    as_of = datetime.now(UTC)
    admitted: dict[str, BarSeries] = {}
    rejected = short_history = failed = 0

    for index, entry in enumerate(sample, start=1):
        instrument = universe.to_instrument(entry)
        try:
            series = vendor_yahoo.fetch(instrument, Interval.DAY, as_of, period=args.period)
        except Exception:  # noqa: BLE001 - research tool; failures counted, not raised
            failed += 1
            continue
        if not RULE.admits(series):
            rejected += 1
            continue
        if len(series.bars) < args.min_bars:
            short_history += 1
            continue
        admitted[instrument.id] = series
        if index % 50 == 0:
            print(f"  [{index}/{len(sample)}] admitted={len(admitted)}")

    print(f"universe: {len(admitted)} admitted, {rejected} rejected by rule, "
          f"{short_history} short history, {failed} fetch failures")
    if not admitted:
        print("nothing admitted; refusing to continue")
        return 1

    # Holdout split by session date, taken from the longest series so the boundary is one date for
    # every instrument rather than a per-instrument fraction.
    all_sessions = sorted({bar.session_date for s in admitted.values() for bar in s.bars})
    split_index = int(len(all_sessions) * (Decimal(1) - HOLDOUT_FRACTION))
    boundary = all_sessions[split_index]
    print(f"sessions {all_sessions[0]} -> {all_sessions[-1]}, holdout begins {boundary}")

    base_costs = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    regimes = {"1x": base_costs, "3x": base_costs.stressed(STRESS_MULTIPLE)}

    # trades[regime][arm][period] -> list
    collected: dict[str, dict[str, dict[str, list]]] = {
        regime: {arm: {"primary": [], "holdout": []} for arm in ARMS} for regime in regimes
    }

    registry = _atr_registry()
    for count, (_instrument_id, series) in enumerate(sorted(admitted.items()), start=1):
        atr_series = atr_component.compute(series, registry)
        gates = _gates(series)
        for regime, costs in regimes.items():
            for arm in ARMS:
                config = BacktestConfig(
                    arm=arm,
                    exits=ExitPolicy(ATR_STOP_MULTIPLE, MAX_HOLDING_BARS),
                    costs=costs,
                    risk_per_trade=RISK_PER_TRADE,
                    trigger=BreakoutHigh(TRIGGER_LOOKBACK),
                )
                result = run_arm(series, gates[arm], atr_series, config)
                for trade in result.trades:
                    period = "holdout" if trade.entry_date >= boundary else "primary"
                    collected[regime][arm][period].append(trade)
        if count % 20 == 0:
            print(f"  simulated {count}/{len(admitted)} instruments")

    report: dict = {
        "prereg": "PR-005",
        "run_at": as_of.isoformat(),
        "seed": args.seed,
        "survivorship": "absent",
        "country": "US",
        "instruments": sorted(admitted),
        "sampled": len(sample),
        "rejected_by_rule": rejected,
        "short_history_exclusions": short_history,
        "fetch_failures": failed,
        "window": [str(all_sessions[0]), str(all_sessions[-1])],
        "holdout_from": str(boundary),
        "parameters": {
            "sma_short": SMA_SHORT, "sma_long": SMA_LONG,
            "pivot_left": PIVOT_LEFT, "pivot_right": PIVOT_RIGHT, "pivot_count": PIVOT_COUNT,
            "atr_period": ATR_PERIOD, "trigger_lookback": TRIGGER_LOOKBACK,
            "atr_stop_multiple": str(ATR_STOP_MULTIPLE), "max_holding_bars": MAX_HOLDING_BARS,
            "risk_per_trade": str(RISK_PER_TRADE),
            "commission_per_share": str(COMMISSION_PER_SHARE), "slippage_bps": str(SLIPPAGE_BPS),
            "stress_multiple": str(STRESS_MULTIPLE),
            "liquidity_rule": {"min_price": str(RULE.min_price), "min_adtv": str(RULE.min_adtv)},
        },
        "regimes": {},
    }

    for regime in regimes:
        block: dict = {"arms": {}, "comparisons": {}, "ranking": {}}
        for period in ("primary", "holdout"):
            stats = [
                study.summarise_arm(arm, collected[regime][arm][period]) for arm in ARMS
            ]
            block["arms"][period] = {
                s.arm: {
                    "trades": s.trades, "mean_r": str(s.mean_r), "median_r": str(s.median_r),
                    "hit_rate": str(s.hit_rate), "mean_mfe": str(s.mean_mfe),
                    "mean_mae": str(s.mean_mae), "mean_holding_days": str(s.mean_holding_days),
                    "gap_exits": s.gap_exits, "exit_reasons": s.exit_reasons,
                }
                for s in stats
            }
            block["ranking"][period] = list(study.ranking(stats))

            comparisons = {}
            reference = collected[regime]["NONE"][period]
            for arm in ARMS:
                if arm == "NONE":
                    continue
                comparison = study.compare_to_reference(
                    arm, collected[regime][arm][period], reference,
                    seed=args.seed, resamples=BOOTSTRAP_RESAMPLES,
                )
                comparisons[arm] = {
                    "difference": str(comparison.difference),
                    "ci_low": str(comparison.ci_low), "ci_high": str(comparison.ci_high),
                    "outside_interval": comparison.outside_interval,
                }
            block["comparisons"][period] = comparisons

            print(f"\n--- {regime} costs, {period}")
            print(f"{'arm':<6} {'trades':>7} {'mean R':>9} {'median':>8} {'hit':>7} "
                  f"{'MFE':>7} {'MAE':>7} {'gaps':>5}")
            for s in stats:
                print(f"{s.arm:<6} {s.trades:>7} {float(s.mean_r):>9.4f} "
                      f"{float(s.median_r):>8.3f} {float(s.hit_rate):>7.3f} "
                      f"{float(s.mean_mfe):>7.2f} {float(s.mean_mae):>7.2f} {s.gap_exits:>5}")
            for arm, c in comparisons.items():
                mark = "OUTSIDE" if c["outside_interval"] else "inside"
                print(f"   {arm} vs NONE: {float(Decimal(c['difference'])):+.4f}R  "
                      f"null [{float(Decimal(c['ci_low'])):+.4f}, "
                      f"{float(Decimal(c['ci_high'])):+.4f}]  {mark}")

        report["regimes"][regime] = block

    # --- PR-005 section 6, applied ---------------------------------------------------
    primary = report["regimes"]["1x"]
    counts = {arm: primary["arms"]["primary"][arm]["trades"] for arm in ARMS}
    holdout_counts = {arm: primary["arms"]["holdout"][arm]["trades"] for arm in ARMS}
    underpowered = sorted(
        arm for arm in ARMS
        if counts[arm] < MIN_TRADES_PRIMARY or holdout_counts[arm] < MIN_TRADES_HOLDOUT
    )

    separated = [
        arm for arm, c in primary["comparisons"]["primary"].items() if c["outside_interval"]
    ]
    stress_rank = report["regimes"]["3x"]["ranking"]["primary"]
    primary_rank = primary["ranking"]["primary"]
    holdout_rank = primary["ranking"]["holdout"]

    survivors = [
        arm for arm in separated
        if primary_rank.index(arm) == stress_rank.index(arm)
        and primary_rank.index(arm) == holdout_rank.index(arm)
    ]

    if underpowered:
        verdict = "refused"
        why = f"under-powered arms: {underpowered}"
    elif survivors:
        verdict = "accept"
        why = f"arms separating and holding rank: {survivors}"
    elif separated:
        verdict = "inconclusive"
        why = f"separated at 1x but rank moved under stress or in holdout: {separated}"
    else:
        verdict = "reject"
        why = "every arm inside NONE's interval at 1x costs"

    report["verdict"] = verdict
    report["verdict_reason"] = why
    report["underpowered_arms"] = underpowered
    report["separated_arms"] = separated
    report["rank_survivors"] = survivors

    print(f"\nrank 1x primary: {primary_rank}")
    print(f"rank 3x primary: {stress_rank}")
    print(f"rank 1x holdout: {holdout_rank}")
    print(f"\nVERDICT: {verdict} - {why}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
