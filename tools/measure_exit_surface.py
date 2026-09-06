"""Expectancy over the stop x target grid, NET of costs. `DR-029` §5's lever 1, priced.

**Why this exists, and what nobody had priced.** `DR-029` set the target at 1R and deferred the
research to three levers, calling the first — a tighter stop — *"the strongest candidate for opening
the range"*: at `1.0 x ATR` one R halves, so 2R becomes as reachable as 1R is now, *"at the cost of a
higher stop-out rate"*. That record says of its own table: **"Gross of costs."**

**A higher stop-out rate is not the only cost, and it is not the one that bites.** `DR-005` charges
25 bps of PRICE per side; R is `stop_multiple x ATR`. Halving the stop multiple halves R and
therefore **doubles what the same slippage costs in R**. That mechanism is measured — `DR-006` §10.3
found gap cost monotone in `2 x ATR / price`, from −1.401R above 0.05 to −5.490R below 0.005 — and
`DR-029`'s lever was argued without it.

So this sweeps both axes and reports gross AND net. The gross table reproduces the shape `DR-029`
reasoned from; the net table is the one a decision should read.

**EXPLORATORY. It sets no parameter.** `measure_target_reachability` is the precedent and carries the
same sentence.

**On trials, stated rather than assumed.** Entries are unselected — every `STEP` sessions on every
admitted name — so no cell measures an EDGE: a signal is what would make expectancy a claim about
skill, and there is none here. What the grid measures is the EXIT POLICY against the market, which
is why `PR-008` and `PR-010` sit in `trial_budget.py`'s `NO_SPEND` list for the same reason.
**Choosing a cell is a different act from measuring the grid**, and `DR-029` already set the
precedent for how that choice is made here: a decision record on unselected-entry evidence, not a
study. That distinction is recorded so a future reader can disagree with it deliberately.

**Bar-order ambiguity resolves against the strategy**, three ways and each conservative:

  * a bar that OPENS below the stop fills at the OPEN — worse than the stop
  * a bar whose LOW reaches the stop fills at the stop, and is checked BEFORE the target
  * a bar that opens ABOVE the target fills at the TARGET, not at the open — the favourable gap is
    not credited

    PYTHONPATH=$PWD/src python tools/measure_exit_surface.py --data <store>
"""

from __future__ import annotations

import argparse
import json
import math
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

ATR_PERIOD = 14

#: `DR-012` ratified 2.0. The rest are the sweep, and 0.5 is included because that is where the
#: cost-in-R mechanism should bite hardest if it bites at all.
STOPS = (Decimal("0.5"), Decimal("1.0"), Decimal("1.5"), Decimal("2.0"), Decimal("3.0"))

#: `DR-029` ratified 1.0. The grid matches `measure_target_reachability`'s so the two are readable
#: against each other.
TARGETS = (Decimal("0.5"), Decimal("1.0"), Decimal("1.5"), Decimal("2.0"), Decimal("3.0"))

#: `DR-012`, ratified, reaffirmed by the owner 2026-08-31.
HOLD = 20
STEP = HOLD

#: `DR-005`, ratified.
SLIPPAGE_BPS = Decimal("25")

RULE = rules.LiquidityRule(
    min_price=Decimal("5.00"), min_adtv=Decimal(5_000_000),
    adtv_window=20, min_history=250, adtv_lag=0,
)

ATR_REGISTRY = ParameterRegistry({
    "atr.period": {"id": "atr.period", "value": ATR_PERIOD, "provenance": "assumed:DR-012",
                   "status": "assumed", "unit": "sessions", "named_in": ["M22-T0340"]},
})


def _walk(window, stop_price: Decimal, target_price: Decimal) -> tuple[Decimal, str]:
    """First touch, resolved pessimistically. Returns (quoted exit price, outcome).

    The outcome is returned because a cell's expectancy cannot be read without its mix: a
    wider stop produces more TIME exits, and a time exit over 2016-2026 carries the decade's
    drift. Without the share beside the mean, "the exit policy is better" and "this cell held
    longer in a rising market" look identical.
    """
    for bar in window:
        if bar.open <= stop_price:
            return bar.open, "gap"        # gapped through: the fill is the open
        if bar.low <= stop_price:
            return stop_price, "stop"     # stop before target, always
        if bar.high >= target_price:
            return target_price, "hit"    # a favourable gap is NOT credited above the target
    return window[-1].close, "time"       # time exit


def _cells(series, dates: set) -> dict[tuple, list[tuple[float, float, str]]]:
    """(stop, target) -> list of (gross R, net R, outcome) for every entry window."""
    out: dict[tuple, list[tuple[float, float, str]]] = {
        (str(s), str(t)): [] for s in STOPS for t in TARGETS
    }
    out[("hold", "hold")] = []
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
        entry = bars[index + 1].open
        if entry <= 0:
            continue
        window = bars[index + 1: index + 1 + HOLD]
        if not window:
            continue
        entry_fill = entry * (Decimal(1) + slip)

        # THE NULL: hold the window, exit at the close, no stop and no target. Denominated
        # in the RATIFIED R so it is comparable with the grid rather than with itself.
        hold_risk = Decimal("2.0") * atr_value
        if hold_risk > 0:
            close = window[-1].close
            out[("hold", "hold")].append((
                float((close - entry) / hold_risk),
                float((close * (Decimal(1) - slip) - entry_fill) / hold_risk),
                "time",
            ))

        for stop_multiple in STOPS:
            risk = stop_multiple * atr_value
            if risk <= 0:
                continue
            stop_price = entry - risk
            for target_multiple in TARGETS:
                target_price = entry + target_multiple * risk
                quoted, kind = _walk(window, stop_price, target_price)
                exit_fill = quoted * (Decimal(1) - slip)
                out[(str(stop_multiple), str(target_multiple))].append((
                    float((quoted - entry) / risk),
                    float((exit_fill - entry_fill) / risk),
                    kind,
                ))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None, help="cap instruments, for a quick look")
    args = parser.parse_args()

    as_of = datetime.now().astimezone()
    totals: dict[tuple, list[tuple[float, float, str]]] = {
        (str(s), str(t)): [] for s in STOPS for t in TARGETS
    }
    totals[("hold", "hold")] = []

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
            found = _cells(series, admitted)
            if not any(found.values()):
                continue
            measured += 1
            for key, values in found.items():
                totals[key].extend(values)

    entries = len(totals[(str(STOPS[0]), str(TARGETS[0]))])
    if not totals[("hold", "hold")]:
        print("no control entries; the grid cannot be read without its null")
        return 0
    print(f"instruments measured : {measured}")
    print(f"entries per cell     : {entries:,}")
    if not entries:
        print("nothing to report")
        return 0
    print(f"hold {HOLD}, entry at the next open, slippage {SLIPPAGE_BPS}bp per side")
    print()

    report: dict[str, object] = {
        "measured_on": as_of.date().isoformat(), "instruments": measured,
        "entries_per_cell": entries, "hold": HOLD, "slippage_bps": str(SLIPPAGE_BPS),
        "cells": {},
    }

    for basis, column in (("GROSS", 0), ("NET", 1)):
        print(f"  EXPECTANCY IN R, {basis} — rows are the stop multiple, columns the target")
        print("  a cell is +/- 1.96 standard errors; * marks an interval excluding zero")
        control = [v[column] for v in totals[("hold", "hold")]]
        base = statistics.mean(control)
        base_half = 1.96 * statistics.stdev(control) / math.sqrt(len(control))
        print(f"    NULL: hold {HOLD} sessions, no stop, no target  =  "
              f"{base:+.3f}R +- {base_half:.3f}   (in ratified 2.0xATR R units)")
        header = "    stop |" + "".join(f"{'T=' + str(t):>18}" for t in TARGETS)
        print(header)
        print("    " + "-" * (len(header) - 4))
        for stop_multiple in STOPS:
            row = f"    {stop_multiple!s:>4} |"
            for target_multiple in TARGETS:
                values = [v[column] for v in totals[(str(stop_multiple), str(target_multiple))]]
                mean = statistics.mean(values)
                half = 1.96 * statistics.stdev(values) / math.sqrt(len(values))
                # Beats the NULL, not merely zero. A cell that cannot beat buy-and-hold has
                # found nothing, however positive it looks.
                mark = "*" if mean - half > base else " "
                row += f"{mean:>+8.3f}{mark}+-{half:<6.3f}".rjust(18)
                report["cells"].setdefault(
                    f"stop={stop_multiple},target={target_multiple}", {}
                )[basis.lower()] = {"mean": mean, "ci_half_width": half,
                                    "beats_buy_and_hold": mean - half > base}
            print(row)
        print("    * = the cell's lower bound is above the NULL, not above zero")
        report.setdefault("null_buy_and_hold", {})[basis.lower()] = {
            "mean": base, "ci_half_width": base_half}
        print()

    # The confound, printed rather than mentioned: a wider stop holds longer, and a time
    # exit over 2016-2026 carries the decade's drift.
    print("  OUTCOME MIX — share of entries, by cell. A time exit carries market drift.")
    header = "    stop |" + "".join(f"{'T=' + str(t):>16}" for t in TARGETS)
    print(header + "     (hit / stop+gap / time)")
    print("    " + "-" * (len(header) - 4))
    for stop_multiple in STOPS:
        row = f"    {stop_multiple!s:>4} |"
        for target_multiple in TARGETS:
            kinds = [v[2] for v in totals[(str(stop_multiple), str(target_multiple))]]
            n = len(kinds)
            hit = kinds.count("hit") / n
            out_ = (kinds.count("stop") + kinds.count("gap")) / n
            time = kinds.count("time") / n
            row += f"{hit:>5.0%}/{out_:>4.0%}/{time:>4.0%}".rjust(16)
            report["cells"][f"stop={stop_multiple},target={target_multiple}"]["mix"] = {
                "hit": hit, "stopped": out_, "time": time}
        print(row)
    print()

    # The mechanism DR-029 did not price, reported rather than argued.
    print("  WHAT THE SAME SLIPPAGE COSTS IN R, BY STOP MULTIPLE")
    print("    a round trip is price x 0.005; R is stop_multiple x ATR")
    for stop_multiple in STOPS:
        cell = totals[(str(stop_multiple), str(Decimal("1.0")))]
        gross = statistics.mean(v[0] for v in cell)
        net = statistics.mean(v[1] for v in cell)
        print(f"    stop {stop_multiple!s:>4} x ATR   gross {gross:+.3f}R   net {net:+.3f}R   "
              f"costs {gross - net:.3f}R at the 1R target")
        report.setdefault("cost_in_R", {})[str(stop_multiple)] = gross - net

    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
