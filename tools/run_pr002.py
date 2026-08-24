"""Run PR-002: does a regime label carry decision-relevant information, or only relabel outcomes?

Orchestration only. Every number comes from `validation.backtest`, `derived_observations.regime`
and `validation.studies.regime_value`, all pure and tested.

The three-way split is the point of this script. Thresholds are fitted on TRAIN, the variant is
selected on VALIDATION by stability (never by outcome), and the separation statistic is measured on
TEST only. Any shortcut through that ordering answers the study's own question.

Network tool. Never imported by anything in src/, never run in CI.

    python tools/run_pr002.py --sample 320
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.request
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.market import BarSeries, Interval
from swingdesk.contracts.observation import ParameterUse
from swingdesk.derived_observations import atr as atr_component
from swingdesk.derived_observations import breadth, moving_average, regime
from swingdesk.derived_observations.regime import Variant
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
from swingdesk.validation.studies import regime_value

DIRECTORY = {
    "nasdaq": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "other": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}

# --- PR-002 section 5 and its amendment, fixed at registration --------------------------
BREADTH_SMA = 200
VOL_WINDOW = 20
MIN_BREADTH_MEMBERS = 10
TRAIN_FRACTION = Decimal("0.50")
VALIDATION_FRACTION = Decimal("0.20")   # test is the remaining 0.30
RESAMPLES = 1000
SEED = 20260802
MIN_TRADES_PER_CELL = 200               # validation.backtest_min_trades, per PR-002 section 8

# --- the trade generator: PR-005's ungated arm, unchanged --------------------------------
ATR_PERIOD = 14
TRIGGER_LOOKBACK = 20
ATR_STOP_MULTIPLE = Decimal("2.0")
MAX_HOLDING_BARS = 20
RISK_PER_TRADE = Decimal(1000)

# --- DR-004 ------------------------------------------------------------------------------
COMMISSION_PER_SHARE = Decimal("0.005")
SLIPPAGE_BPS = Decimal(5)
STRESS_MULTIPLE = Decimal(3)

# --- DR-003 ------------------------------------------------------------------------------
RULE = universe.LiquidityRule(
    min_price=Decimal("5.00"), min_adtv=Decimal("5000000"),
    adtv_window=20, min_history=250,
)


def _download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "swingdesk-research/0.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def _realised_volatility(series: BarSeries, window: int) -> dict[date, Decimal]:
    """Close-to-close standard deviation over `window` sessions, per session."""
    out: dict[date, Decimal] = {}
    closes = [bar.close for bar in series.bars]
    returns: list[Decimal] = [Decimal(0)]
    for index in range(1, len(closes)):
        previous = closes[index - 1]
        returns.append((closes[index] - previous) / previous if previous else Decimal(0))

    for index in range(len(closes)):
        if index < window:
            continue
        sample = returns[index - window + 1: index + 1]
        mean = sum(sample, Decimal(0)) / window
        variance = sum(((r - mean) ** 2 for r in sample), Decimal(0)) / window
        out[series.bars[index].session_date] = variance.sqrt()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_pr002")
    parser.add_argument("--sample", type=int, default=320)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--period", default="10y")
    parser.add_argument("--min-bars", type=int, default=2000)
    parser.add_argument("--out", type=Path, default=Path("docs/prereg/results/PR-002.json"))
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
        except Exception:  # noqa: BLE001
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

    print(f"universe: {len(admitted)} admitted, {rejected} rejected, "
          f"{short_history} short history, {failed} failures")
    if len(admitted) < 10:
        print("refusing to continue: too few instruments to measure breadth")
        return 1

    # --- market state -------------------------------------------------------------------
    long_p = ParameterUse(id="sma.period", value=str(BREADTH_SMA), provenance="assumed:PR-002")
    smas = {
        instrument_id: moving_average.compute(series, BREADTH_SMA, long_p)
        for instrument_id, series in admitted.items()
    }
    breadth_points = breadth.above_average(admitted, smas, min_members=MIN_BREADTH_MEMBERS)
    breadth_by_date = {point.session_date: point.value for point in breadth_points}

    vol_by_instrument = {
        instrument_id: _realised_volatility(series, VOL_WINDOW)
        for instrument_id, series in admitted.items()
    }
    volatility_by_date: dict[date, Decimal | None] = {}
    for point in breadth_points:
        values = sorted(
            v[point.session_date] for v in vol_by_instrument.values()
            if point.session_date in v
        )
        volatility_by_date[point.session_date] = (
            values[len(values) // 2] if len(values) >= MIN_BREADTH_MEMBERS else None
        )

    sessions = [point.session_date for point in breadth_points]
    train_end = int(len(sessions) * TRAIN_FRACTION)
    validation_end = int(len(sessions) * (TRAIN_FRACTION + VALIDATION_FRACTION))
    windows = {
        "train": sessions[:train_end],
        "validation": sessions[train_end:validation_end],
        "test": sessions[validation_end:],
    }
    print(f"sessions {sessions[0]} -> {sessions[-1]}  "
          f"train {len(windows['train'])} / validation {len(windows['validation'])} / "
          f"test {len(windows['test'])}")

    # --- fit on TRAIN only ---------------------------------------------------------------
    train_breadth = [breadth_by_date[d] for d in windows["train"]]
    train_vol = [volatility_by_date[d] for d in windows["train"]]
    classifiers = {}
    for variant in Variant:
        try:
            classifiers[variant] = regime.fit(variant, train_breadth, train_vol)
        except ValueError as error:
            print(f"  {variant}: cannot fit - {error}")

    # --- select on VALIDATION by STABILITY, never by outcome -----------------------------
    stability = {}
    for variant, classifier in classifiers.items():
        labels = [
            classifier.label(breadth_by_date[d], volatility_by_date[d])
            for d in windows["validation"]
        ]
        changes = regime.label_changes(labels)
        labelled = sum(1 for label in labels if label is not None)
        stability[variant] = {
            "changes": changes,
            "labelled_sessions": labelled,
            "changes_per_100": (changes / labelled * 100) if labelled else None,
        }
        print(f"  {variant.value:<16} validation flips {changes:>4} over {labelled} sessions")

    selectable = {v: s for v, s in stability.items() if s["labelled_sessions"]}
    selected = min(selectable, key=lambda v: selectable[v]["changes_per_100"])
    print(f"\nselected by stability: {selected.value}")

    # --- generate trades ------------------------------------------------------------------
    registry = ParameterRegistry({
        "atr.period": {"id": "atr.period", "value": ATR_PERIOD, "provenance": "assumed:PR-002",
                       "unit": "bars", "named_in": ["PR-002"]},
    })
    base_costs = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    regimes_of_cost = {"1x": base_costs, "3x": base_costs.stressed(STRESS_MULTIPLE)}
    trades_by_cost: dict[str, list] = {name: [] for name in regimes_of_cost}

    for count, (_instrument_id, series) in enumerate(sorted(admitted.items()), start=1):
        atr_series = atr_component.compute(series, registry)
        gate = [True] * len(series.bars)
        for cost_name, costs in regimes_of_cost.items():
            config = BacktestConfig(
                arm="NONE", exits=ExitPolicy(ATR_STOP_MULTIPLE, MAX_HOLDING_BARS),
                costs=costs, risk_per_trade=RISK_PER_TRADE,
                trigger=BreakoutHigh(TRIGGER_LOOKBACK),
            )
            trades_by_cost[cost_name].extend(run_arm(series, gate, atr_series, config).trades)
        if count % 20 == 0:
            print(f"  simulated {count}/{len(admitted)}")

    test_dates = set(windows["test"])
    report: dict = {
        "prereg": "PR-002",
        "run_at": as_of.isoformat(),
        "seed": args.seed,
        "survivorship": "absent",
        "country": "US",
        "instruments": len(admitted),
        "window": [str(sessions[0]), str(sessions[-1])],
        "split": {name: [str(w[0]), str(w[-1]), len(w)] for name, w in windows.items() if w},
        "parameters": {
            "breadth_sma": BREADTH_SMA, "vol_window": VOL_WINDOW,
            "min_breadth_members": MIN_BREADTH_MEMBERS,
            "atr_period": ATR_PERIOD, "trigger_lookback": TRIGGER_LOOKBACK,
            "atr_stop_multiple": str(ATR_STOP_MULTIPLE), "max_holding_bars": MAX_HOLDING_BARS,
            "commission_per_share": str(COMMISSION_PER_SHARE), "slippage_bps": str(SLIPPAGE_BPS),
            "resamples": RESAMPLES,
        },
        "thresholds": {
            v.value: {
                "breadth_cuts": [str(c) for c in c_.breadth_cuts],
                "volatility_cuts": [str(c) for c in c_.volatility_cuts],
                "fitted_on": c_.fitted_on,
            }
            for v, c_ in classifiers.items()
        },
        "validation_stability": {
            v.value: {**s, "changes_per_100": (
                None if s["changes_per_100"] is None else round(s["changes_per_100"], 3)
            )}
            for v, s in stability.items()
        },
        "selected_variant": selected.value,
        "results": {},
    }

    for cost_name in regimes_of_cost:
        test_trades = [t for t in trades_by_cost[cost_name] if t.signal_date in test_dates]
        block = {}
        for variant, classifier in classifiers.items():
            labelled = [
                (
                    classifier.label(
                        breadth_by_date.get(t.signal_date), volatility_by_date.get(t.signal_date)
                    ),
                    t,
                )
                for t in test_trades
            ]
            value = regime_value.evaluate(
                variant.value, labelled, seed=args.seed, resamples=RESAMPLES,
                min_trades_per_cell=MIN_TRADES_PER_CELL,
            )
            block[variant.value] = {
                "cells": [
                    {"regime": c.regime, "trades": c.trades, "mean_r": str(c.mean_r)}
                    for c in value.cells
                ],
                "observed_range": str(value.observed_range),
                "percentile": str(value.percentile),
                "baseline_p80": str(value.baseline_p80),
                "baseline_p95": str(value.baseline_p95),
                "unlabelled": value.unlabelled,
                "thin_cells": list(value.thin_cells),
                "separates": value.separates,
            }
            # POST-HOC, and labelled as such: the registered baseline permutes individual trades,
            # which assumes they are exchangeable. Dozens of instruments fire on the same session,
            # so they are not. This permutes the date->label map instead, preserving the clustering.
            labels_by_date = {
                d: classifier.label(breadth_by_date.get(d), volatility_by_date.get(d))
                for d in windows["test"]
            }
            blocked = regime_value.evaluate_by_date(
                variant.value, labels_by_date, test_trades,
                seed=args.seed, resamples=RESAMPLES,
            )
            block[variant.value]["block_permutation"] = {
                "percentile": str(blocked.percentile),
                "baseline_p95": str(blocked.baseline_p95),
                "separates": blocked.separates,
            }

            marker = "SEPARATES" if value.separates else ("refuted" if value.refuted else "middle")
            print(f"\n[{cost_name}] {variant.value}  test trades "
                  f"{sum(c.trades for c in value.cells)}  range "
                  f"{float(value.observed_range):+.4f}R  pct {float(value.percentile):.1f}  "
                  f"p95 {float(value.baseline_p95):.4f}  {marker}")
            for cell in value.cells:
                print(f"     {cell.regime:<14} {cell.trades:>6} trades  "
                      f"mean {float(cell.mean_r):+.4f}R")
            print(f"     post-hoc date-block null: pct {float(blocked.percentile):.1f} "
                  f"p95 {float(blocked.baseline_p95):.4f} "
                  f"{'SEPARATES' if blocked.separates else 'does not separate'}")
            if value.thin_cells:
                print(f"     THIN CELLS (< {MIN_TRADES_PER_CELL} trades): {list(value.thin_cells)}")
        report["results"][cost_name] = block

    # --- PR-002 section 6, applied to the SELECTED variant on TEST -----------------------
    chosen = report["results"]["1x"][selected.value]
    thin = chosen["thin_cells"]
    if thin:
        verdict, why = "refused", f"thin regime cells: {thin}"
    elif chosen["separates"]:
        stressed = report["results"]["3x"][selected.value]["separates"]
        verdict = "accept" if stressed else "inconclusive"
        why = ("separates on test at 1x and 3x" if stressed
               else "separates at 1x but not under cost stress")
    elif Decimal(chosen["percentile"]) < Decimal(80):
        verdict, why = "reject", "below the 80th percentile of the random-partition baseline"
    else:
        verdict, why = "inconclusive", "between the 80th and 95th percentiles"

    # --- PR-002 section 6's COUNTRY condition, which this runner used to omit ----------------
    # §6 permits `accept` only where the effect holds "in BOTH countries independently", and sends
    # a result "significant in one country only" to the inconclusive branch. The third amendment
    # (2026-08-02, written before any data was seen) records that Canada is unavailable and that
    # the two-country requirement is "NOT quietly dropped".
    #
    # The branches above implement the percentile thresholds and nothing else, so on 2026-08-02
    # this runner emitted `accept` on a US-only sample - recording `single_market` beside it as a
    # field, which no reader and no gate treats as part of the verdict. The prereg had already
    # decided this case; the code simply never encoded it. Corrected 2026-08-16.
    #
    # NOT retroactive: `docs/prereg/results/PR-002.json` is the record of what ran on 2026-08-02
    # and is corrected in place (PR-008's precedent), never regenerated. This runner fetches the
    # CURRENT directory and CURRENT Yahoo history, so a re-run samples a different universe over a
    # different window - it would replace a reported result with an unreported one, not reproduce it.
    countries = report.get("country")
    single_market = not isinstance(countries, list) or len(countries) < 2
    if single_market and verdict == "accept":
        verdict = "inconclusive"
        why = (f"{why}; but §6 permits accept only in BOTH countries independently and this run "
               f"covers one ({countries!r}) - a single-market finding, not generalised")

    report["verdict"] = verdict
    report["verdict_reason"] = why
    report["single_market"] = single_market
    report["post_hoc_block_permutation"] = {
        "note": "NOT part of the registered decision rule. The registered null permutes individual "
                "trades and assumes them exchangeable; they are clustered by session. This null "
                "permutes the date-to-label map instead and is strictly harder to beat.",
        "selected_1x": report["results"]["1x"][selected.value]["block_permutation"],
        "selected_3x": report["results"]["3x"][selected.value]["block_permutation"],
    }
    print(f"\nVERDICT ({selected.value}, test window, 1x costs): {verdict} - {why}")
    print("NOTE: single-market result. Canada unavailable (DR-003).")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
