"""What a stop-out actually costs, in R, on the universe this system now trades.

**MEASUREMENT, not a study. It sets no parameter and spends no trial against `b.deflated_sharpe`.**
`trial_budget.py`'s `NO_SPEND` list already carries this shape twice - `PR-008` and `PR-010` measure
*a cost input rather than an edge*, so there is no Sharpe to deflate. Nothing here is selected for
performance: the stop, the hold and the entry method are the ratified ones and only one
configuration is evaluated.

**The question, and why it is load-bearing.** `DR-006` §8 lowered `risk.max_concurrent_positions`
from 6 to 4 on one number: a stop-out that GAPS costs **-1.692R**, not -1R, so a session in which
the whole book gaps costs 6 x 1.692 = 10.15R rather than 6R. Every argument about the book's size
rests on it, including how long `b.min_sample` takes to reach.

**It was measured on sixty-eight instruments.** `PR-005-trades.csv` holds 26,351 trades across 68
distinct names; the admitted universe holds thousands. `DR-006` §9 measured the raw ingredient -
overnight down-gaps in ATR units - and found the admitted set gaps **0.82x as often and 0.93x as
hard**, so the figure looked conservative. What §9 could not do is convert that into R, because the
conversion needs the stop's position relative to the entry and the exit rule. This does that.

**The method is `measure_target_reachability`'s, with the question changed.** Entries every `HOLD`
sessions on every admitted name - not the ones a card would select, so this measures the POPULATION
under the ratified exit rule rather than a strategy. Entry at the next session's open, stop at
`entry - 2 x ATR(14)`, time exit at session 20.

**Three outcomes, and the split is the whole point:**

  * **clean stop** - a session's low reached the stop while its open was still above it, so the
    exit fills AT the stop and costs exactly -1R
  * **gap stop** - a session OPENED below the stop, so the exit fills at the open and costs more
    than 1R. This is the -1.692R population
  * **time exit** - neither, within the hold. Priced at the close of session 20

**Bar-order ambiguity resolves against the strategy**, the same way `manage.evaluate` and
`measure_target_reachability` resolve it: the stop is tested first, so a bar containing both is a
stop. Assuming the favourable order would make every number here flatter than the system that trades
it.

**Gross and net are both reported.** `DR-006` §8.1's figures are NET - the record does not say so,
and `gross_r` in the same log gives -1.047R and -1.618R, close enough to look right and wrong by 4%.
Costs are `DR-005`'s 25 bps per side; commission is zero (`DR-039`), and the venue's regulatory fees
are not charged here because they are billed per DAY per account and this measurement has no book.

    PYTHONPATH=$PWD/src python tools/measure_gap_cost.py --data <store>
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_target_reachability import _admitted_dates
from swingdesk.contracts.market import Interval, Series
from swingdesk.derived_observations import atr
from swingdesk.market_data import BarStore
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data import universe as rules

#: `DR-012`, ratified. The stop distance IS one R.
ATR_PERIOD = 14
STOP_MULTIPLE = Decimal("2.0")

#: `DR-012`, ratified, reaffirmed by the owner 2026-08-31.
HOLD = 20

#: Non-overlapping windows, so one instrument's outcomes are independent of each other.
STEP = HOLD

#: `DR-005`, ratified: 25 bps of price each side, applied to the fill.
SLIPPAGE_BPS = Decimal("25")

#: `DR-003`'s rule, pinned exactly as `measure_target_reachability` pins it.
RULE = rules.LiquidityRule(
    min_price=Decimal("5.00"), min_adtv=Decimal(5_000_000),
    adtv_window=20, min_history=250, adtv_lag=0,
)

ATR_REGISTRY = ParameterRegistry({
    "atr.period": {"id": "atr.period", "value": ATR_PERIOD, "provenance": "assumed:DR-012",
                   "status": "assumed", "unit": "sessions", "named_in": ["M22-T0340"]},
})


def _r_multiples(series, dates: set) -> dict[str, list[float]]:
    """Every entry window's outcome in R, split by how it ended.

    Returns gross and net lists per outcome. Net charges `DR-005`'s slippage on both fills - the
    buyer pays up, the seller receives less - which is what makes these comparable with §8.1.
    """
    out: dict[str, list[float]] = {
        "clean_gross": [], "clean_net": [],
        "gap_gross": [], "gap_net": [],
        "time_gross": [], "time_net": [],
        # 2 x ATR / entry, per entry. `DR-005` charges slippage as a fraction of PRICE and R
        # is a multiple of ATR, so this ratio is what decides whether costs are a rounding
        # error or larger than the risk itself. Carried for every entry, banded on report.
        "risk_over_price": [],
        # gap outcomes paired with their ratio, so the net figure can be read by band
        # rather than as one number over a population that is not homogeneous.
        "gap_net_by_ratio": [],
    }
    bars = series.bars
    values = atr.compute(series, ATR_REGISTRY)
    by_time = {o.event_time: o.value for o in values.observations}
    slip = SLIPPAGE_BPS / Decimal(10_000)

    for index in range(ATR_PERIOD + 1, len(bars) - HOLD - 1, STEP):
        decision = bars[index]
        if decision.session_date not in dates:
            continue
        atr_value = by_time.get(decision.event_time)
        if atr_value is None or atr_value <= 0:
            continue

        quoted_entry = bars[index + 1].open
        risk = STOP_MULTIPLE * atr_value
        if risk <= 0 or quoted_entry <= 0:
            continue

        # The stop is set from the QUOTED entry, because that is what a decision would compute it
        # from; the fill then slips against us. Setting it from the slipped fill would quietly make
        # every R smaller and flatter every number below.
        stop_price = quoted_entry - risk
        entry_fill = quoted_entry * (Decimal(1) + slip)

        window = bars[index + 1: index + 1 + HOLD]
        kind, quoted_exit = "time", window[-1].close
        for forward in window:
            if forward.open <= stop_price:
                # Opened through the stop: the fill is the OPEN, not the stop.
                kind, quoted_exit = "gap", forward.open
                break
            if forward.low <= stop_price:
                kind, quoted_exit = "clean", stop_price
                break

        exit_fill = quoted_exit * (Decimal(1) - slip)
        ratio = float(risk / quoted_entry)
        net = float((exit_fill - entry_fill) / risk)
        out[f"{kind}_gross"].append(float((quoted_exit - quoted_entry) / risk))
        out[f"{kind}_net"].append(net)
        out["risk_over_price"].append(ratio)
        if kind == "gap":
            out["gap_net_by_ratio"].append(ratio)
            out["gap_net_by_ratio"].append(net)
    return out


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "mean": statistics.mean(ordered),
        "median": statistics.median(ordered),
        "p01": ordered[int(0.01 * (len(ordered) - 1))],
        "worst": ordered[0],
        "share_worse_than_minus_1_5R": sum(1 for v in ordered if v < -1.5) / len(ordered),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None, help="cap instruments, for a quick look")
    args = parser.parse_args()

    as_of = datetime.now().astimezone()
    totals: dict[str, list[float]] = {
        key: [] for key in
        ("clean_gross", "clean_net", "gap_gross", "gap_net", "time_gross", "time_net",
         "risk_over_price", "gap_net_by_ratio")
    }

    with BarStore(args.data / "bars.duckdb") as store:
        names = sorted(store.instrument_ids(as_of))
        if args.limit:
            names = names[: args.limit]
        measured = 0
        for name in names:
            series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
            if len(series.bars) < 300:
                continue
            calendar = [bar.session_date for bar in series.bars]
            admitted = _admitted_dates(series, RULE, calendar)
            if not admitted:
                continue
            found = _r_multiples(series, admitted)
            if not any(found.values()):
                continue
            measured += 1
            for key, values in found.items():
                totals[key].extend(values)

    stops = len(totals["clean_net"]) + len(totals["gap_net"])
    entries = stops + len(totals["time_net"])
    print(f"instruments measured : {measured}")
    print(f"entries              : {entries}")
    if not entries:
        print("nothing to report")
        return 0
    print(f"stop-outs            : {stops}  ({stops / entries:.1%} of entries)")
    print(f"  of those, GAPPED   : {len(totals['gap_net'])}  "
          f"({len(totals['gap_net']) / stops:.1%} of stop-outs)" if stops else "")
    print()
    print(f"  stop {STOP_MULTIPLE} x ATR({ATR_PERIOD}) = 1R, hold {HOLD}, entry at the next open, "
          f"slippage {SLIPPAGE_BPS}bp per side")
    print()

    report: dict[str, object] = {
        "measured_on": datetime.now().astimezone().date().isoformat(),
        "instruments": measured, "entries": entries, "stop_outs": stops,
        "stop_multiple": str(STOP_MULTIPLE), "hold": HOLD,
        "slippage_bps": str(SLIPPAGE_BPS),
    }
    print(f"{'outcome':>12} {'n':>8} {'mean R':>9} {'median':>9} {'p01':>9} {'worst':>9} {'< -1.5R':>9}")
    for kind in ("clean", "gap", "time"):
        for basis in ("gross", "net"):
            values = totals[f"{kind}_{basis}"]
            if not values:
                continue
            s = _summary(values)
            report[f"{kind}_{basis}"] = s
            print(f"{kind + ' ' + basis:>12} {s['n']:>8,d} {s['mean']:>+9.3f} {s['median']:>+9.3f} "
                  f"{s['p01']:>+9.3f} {s['worst']:>+9.3f} {s['share_worse_than_minus_1_5R']:>8.1%}")

    print()
    print("  DR-006 8.1, on PR-005's 68 names, NET: clean -1.070R, gap -1.692R, "
          "35% of gaps worse than -1.5R")

    # ---- why net and gross disagree, and it is not the gap ----
    ratios = sorted(totals["risk_over_price"])
    if ratios:
        def at(p: float) -> float:
            return ratios[int(p * (len(ratios) - 1))]
        print()
        print("  R AS A FRACTION OF PRICE (2 x ATR / entry). DR-005 charges 25bp of PRICE per")
        print("  side, so this ratio decides whether cost is a rounding error or exceeds the risk.")
        print(f"    p01 {at(0.01):.5f}   p10 {at(0.10):.5f}   median {at(0.50):.5f}   "
              f"p90 {at(0.90):.5f}")
        report["risk_over_price"] = {
            "p01": at(0.01), "p10": at(0.10), "median": at(0.50), "p90": at(0.90),
        }

    paired = totals["gap_net_by_ratio"]
    if paired:
        pairs = [(paired[i], paired[i + 1]) for i in range(0, len(paired), 2)]
        bands = ((0.0, 0.005), (0.005, 0.01), (0.01, 0.02), (0.02, 0.05), (0.05, 1.0))
        print()
        print("  GAP COST BY BAND. One number over a population this heterogeneous is a mean")
        print("  of two different things.")
        print(f"    {'2xATR/price':>16} {'n':>8} {'gap net R':>11}")
        banded = {}
        for low, high in bands:
            inside = [net for ratio, net in pairs if low <= ratio < high]
            if not inside:
                continue
            mean = statistics.mean(inside)
            banded[f"{low}-{high}"] = {"n": len(inside), "gap_net_mean": mean}
            print(f"    {low:>7.3f}-{high:<8.3f} {len(inside):>8,d} {mean:>+11.3f}")
        report["gap_net_by_band"] = banded

    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
