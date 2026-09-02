"""Which R target is REACHABLE inside the holding period this project actually runs?

**EXPLORATORY. It sets no parameter and advances no validation status.** It is a measurement taken
before authoring anything, which is what `AGENTS.md` §8 asks for, and it exists because a question
became answerable rather than because a result was wanted.

**The question, and why the course frames it.** `M53-T0807`, `T0808` and `T0809` are the course's
own target definitions - *exit at 1R*, *exit at 2R*, *exit at 3R* - and like every threshold here
the course names the form and picks no value. The owner ruled on 2026-09-01 that a target is
mandatory: a trade is carried from discovery to close and then observed, so the research data comes
from a COMPLETED trade rather than from one that timed out.

**Two ratified numbers make the choice measurable rather than a matter of taste.** The stop is
`2.0 x ATR(14)` and the maximum hold is `20 sessions` (`DR-012`, both ratified). So `R` per share is
about two ATR, and the question *"is 3R reachable?"* is really *"do these names travel six ATR in
twenty sessions?"* - which this store can answer directly instead of being reasoned about.

**What it measures.** For every admitted instrument and a grid of entry dates, it walks forward at
most `HOLD` sessions from the next session's open and asks which happened FIRST:

  - the low touched `entry - R`            -> stopped
  - the high touched `entry + k x R`       -> target hit, for each k
  - neither, within the hold                -> timed out

**Bar-order ambiguity is resolved against the strategy, deliberately.** When one session's range
contains both the stop and the target, this counts a STOP. Daily bars cannot say which came first,
and `manage.evaluate` already resolves the same ambiguity the same way - the stop is checked first,
so a bar satisfying both is a stop-out. Assuming the favourable order would make every number here
flatter than the system that will trade it.

**What it is NOT.** Gross of costs, and not a strategy: entries are every Nth session on every
admitted name, not the ones a card would select. It measures how far these instruments TRAVEL, which
is the input to choosing a target, and says nothing about whether an edge exists.

    PYTHONPATH=$PWD/src python tools/measure_target_reachability.py --data <store>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from run_pr013 import _admitted_dates
from swingdesk.contracts.market import Interval, Series
from swingdesk.derived_observations import atr
from swingdesk.market_data import BarStore
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data import universe as rules

#: `DR-012`, ratified: the protective stop is 2.0 x ATR(14). R per share is that distance, so every
#: target below is expressed against the same denominator the position would carry.
ATR_PERIOD = 14
STOP_MULTIPLE = Decimal("2.0")

#: `DR-012`, ratified, and reaffirmed by the owner 2026-08-31 ("20 tight, it is a rule").
HOLD = 20

#: The course's own three, `M53-T0807/0808/0809`. Halves are included as context rather than as
#: candidates - the question is where the reachable range ENDS, and a grid that stops at the
#: candidates cannot show that.
TARGETS = (Decimal("0.5"), Decimal("1.0"), Decimal("1.5"), Decimal("2.0"), Decimal("3.0"))

#: Sessions between entry dates. Non-overlapping windows, so one instrument's outcomes are
#: independent of each other - the same reason `measure_momentum_horizon` steps by its horizon.
STEP = HOLD

#: `DR-003`'s rule, pinned exactly as `PR-012` and `PR-013` pin it.
RULE = rules.LiquidityRule(
    min_price=Decimal("5.00"), min_adtv=Decimal(5_000_000),
    adtv_window=20, min_history=250, adtv_lag=0,
)


#: `atr.compute` reads its period from a registry rather than an argument, which is the design
#: working: a component that took a bare integer could be called with a period nobody recorded.
#: This is the real value from the real registry, not a fixture.
ATR_REGISTRY = ParameterRegistry({
    "atr.period": {"id": "atr.period", "value": ATR_PERIOD, "provenance": "assumed:DR-012",
                   "status": "assumed", "unit": "sessions", "named_in": ["M22-T0340"]},
})


def _outcomes(series, dates: set) -> dict[str, int]:
    """Classify every entry window by FIRST TOUCH, separately for each candidate target.

    **First touch, not "reached at some point", and the difference is the whole point.** A window
    that trades up to 2R and then reverses to the stop is a WINNER under a 2R target and a LOSER
    under a 3R one. A cumulative "did it ever reach k" column cannot express that, so it cannot
    produce an expectancy - and expectancy is the only thing that distinguishes the course's three
    candidate values from each other.

    So each target gets its own walk: stop first is -1R, target first is +kR, neither inside the
    hold is a time exit whose outcome this tool does not price.
    """
    counts = {"entries": 0}
    for target in TARGETS:
        for suffix in ("hit", "stop", "time"):
            counts[f"{suffix}_{target}"] = 0

    bars = series.bars
    values = atr.compute(series, ATR_REGISTRY)
    # Keyed by `event_time`: an `Observation` carries that, not a session date, and aligning by
    # LIST INDEX would be an assumption about warm-up padding rather than a lookup.
    by_time = {o.event_time: o.value for o in values.observations}

    for index in range(ATR_PERIOD + 1, len(bars) - HOLD - 1, STEP):
        decision = bars[index]
        if decision.session_date not in dates:
            continue
        atr_value = by_time.get(decision.event_time)
        if atr_value is None or atr_value <= 0:
            continue

        # Entry at the NEXT session's open - `CARD-001`'s own entry method, so the measurement
        # cannot benefit from a fill at the price the decision was made on.
        entry = bars[index + 1].open
        risk = STOP_MULTIPLE * atr_value
        if risk <= 0 or entry <= 0:
            continue
        counts["entries"] += 1

        stop_price = entry - risk
        window = bars[index + 1: index + 1 + HOLD]
        for target in TARGETS:
            level = entry + target * risk
            for forward in window:
                # The stop is tested FIRST on every bar. A daily bar cannot say which side traded
                # first, and `manage.evaluate` resolves the same ambiguity the same way - so this
                # measurement is pessimistic exactly where the system is.
                if forward.low <= stop_price:
                    counts[f"stop_{target}"] += 1
                    break
                if forward.high >= level:
                    counts[f"hit_{target}"] += 1
                    break
            else:
                counts[f"time_{target}"] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None, help="cap instruments, for a quick look")
    args = parser.parse_args()

    as_of = datetime.now().astimezone()
    totals = {"entries": 0}
    for target in TARGETS:
        for suffix in ("hit", "stop", "time"):
            totals[f"{suffix}_{target}"] = 0

    with BarStore(args.data / "bars.duckdb") as store:
        names = sorted(store.instrument_ids(as_of))
        if args.limit:
            names = names[: args.limit]
        measured = 0
        for name in names:
            series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
            if len(series.bars) < 300:
                continue
            calendar = [b.session_date for b in series.bars]
            admitted = _admitted_dates(series, RULE, calendar)
            if not admitted:
                continue
            counts = _outcomes(series, admitted)
            if not counts["entries"]:
                continue
            measured += 1
            for key, value in counts.items():
                totals[key] += value

    print(f"instruments measured: {measured}")
    print(f"entries:              {totals['entries']}")
    if not totals["entries"]:
        print("nothing to report")
        return 0

    entries = totals["entries"]
    print()
    print(f"  stop is 1R below entry, hold {HOLD} sessions, entry at the next open")
    print()
    print(f"{'target':>8} {'hit':>8} {'stopped':>9} {'timed out':>10} {'expectancy':>12}")
    for target in TARGETS:
        hit = totals[f"hit_{target}"]
        stop = totals[f"stop_{target}"]
        timed = totals[f"time_{target}"]
        # Expectancy over RESOLVED windows only. A time exit's outcome is not -1R and not +kR; it
        # is whatever the position was worth on session 20, which this tool does not price. Folding
        # it in as zero would be inventing a number, so the resolved share is printed beside it.
        resolved = hit + stop
        expectancy = (Decimal(hit) * target - Decimal(stop)) / resolved if resolved else None
        shown = f"{float(expectancy):>+11.3f}R" if expectancy is not None else f"{'-':>12}"
        print(f"{target:>7}R {hit / entries:>7.1%} {stop / entries:>8.1%} "
              f"{timed / entries:>9.1%} {shown}")
    print()
    print("EXPECTANCY IS OVER RESOLVED WINDOWS ONLY - hit or stopped. A time exit is worth whatever")
    print("the position was on session 20, which this tool does not price; counting it as zero")
    print("would be inventing a number. The timed-out column is how much is being left out.")
    print()
    print("EXPLORATORY and GROSS. Sets no parameter. Entries are every 20th session on every")
    print("admitted name, not what a card would select - this measures how far these instruments")
    print("TRAVEL, which is the input to choosing a target, not whether an edge exists.")
    if args.out:
        args.out.write_text(json.dumps({
            "exploratory": True,
            "atr_period": ATR_PERIOD, "stop_multiple": str(STOP_MULTIPLE), "hold": HOLD,
            "targets": [str(t) for t in TARGETS], "instruments": measured,
            "totals": totals, "run_at": as_of.isoformat(),
        }, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
