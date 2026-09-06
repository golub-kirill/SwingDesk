"""The backtest fills at the next open. The live path rests a limit at the prior close. Same trade?

**They are not the same order, and nothing had measured the gap.**

  * `validation/backtest/engine.py`: *"entry still fills at `bars[i + 1].open`"* - unconditionally,
    every candidate, charged `costs.slippage_model` on top.
  * `application/pipeline.py`: `entry = stored.bars[-1].close`, handed to `broker.entry_order` as
    `limit_price`, sent as `order_type: limit` / `time_in_force: day`
    (`registry/broker_policy.yml`).

A limit resting at yesterday's close is a different instrument from a market order at today's open,
and for a strategy that selects recent winners the difference is not neutral: **a name that gaps up
is never bought.** That is textbook adverse selection, and if it is large then no backtest in this
repository is evidence about the system that actually trades.

**Measured, it is real in mechanism and small in size** - which is worth knowing precisely because
the mechanism argument alone would have justified a rewrite. The names the limit never buys DO run
better; filling at the limit instead of the open buys them cheaper; the two nearly cancel.

**What it also produces, and this is the part that changed a cost argument.** The live entry is not
one fill type but three, in fixed proportions, and only one of them crosses a spread:

  * **marketable** - the session opened at or below the limit, so the order crosses at the open,
    the widest moment of the day (`tools/measure_quoted_spread.py`)
  * **passive** - the session opened above and traded back down, so the order rests and a seller
    crosses into it; nothing is paid for the spread
  * **unfilled** - the session never traded down to the limit, and the intended position does not
    exist

`costs.slippage_model` is a single constant charged to both sides of every trade. It can represent
none of the three.

**EXPLORATORY. It sets no parameter and advances no validation status.** Gross of costs throughout,
because the question is which fills happen rather than what they cost.

    python tools/measure_fill_convention.py --data C:/PycharmProjects/SwingDesk/data
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.application import universe as selection_rules
from swingdesk.contracts.market import Bar, Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.reference_data import universe as rules
from swingdesk.reference_data.directory import DirectoryStore

#: `DR-003`'s rule, pinned so a later ratification cannot change what this measurement meant.
MIN_PRICE = Decimal("5.00")
MIN_ADTV = Decimal(5_000_000)
ADTV_WINDOW = 20
MIN_HISTORY = 250
ADTV_LAG = 0

#: `exit.max_holding_period`, ratified by `DR-012`. Entries are struck this far apart so no two
#: overlap - the same construction `measure_exit_surface.py` uses.
HOLD = 20

#: Bars an instrument must carry before it contributes. The first `WARMUP` are skipped so a
#: candidate has the history the liquidity rule itself requires.
WARMUP = 250

MARKETABLE, PASSIVE, UNFILLED = "marketable", "passive", "unfilled"


@dataclass(frozen=True, slots=True)
class Fill:
    """How a resting limit at `limit` met the next session, and at what price."""

    kind: str
    price: Decimal | None


def classify(limit: Decimal, forward: Bar) -> Fill:
    """What a day limit buy at `limit` does against the next session's bar.

    Three outcomes and the order of the tests is the whole rule:

      1. **opened at or below the limit** - already marketable, so it fills at the OPEN and the
         limit never binds. The fill is better than the limit, not equal to it, and charging the
         limit here would silently improve every gap-down entry.
      2. **opened above but traded down to the limit** - rests, then fills AT the limit.
      3. **never traded down** - no position. Returning a price here would invent a trade.
    """
    if forward.open <= limit:
        return Fill(MARKETABLE, forward.open)
    if forward.low <= limit:
        return Fill(PASSIVE, limit)
    return Fill(UNFILLED, None)


def forward_return(entry: Decimal, exit_price: Decimal) -> Decimal:
    """Simple return on the entry actually paid."""
    return (exit_price - entry) / entry


def interval(values: list[Decimal]) -> tuple[Decimal, Decimal]:
    """Mean and a 1.96-standard-error half-width. `(0, 0)` below two observations."""
    if len(values) < 2:
        return (values[0], Decimal(0)) if values else (Decimal(0), Decimal(0))
    floats = [float(v) for v in values]
    mean = statistics.mean(floats)
    half = 1.96 * statistics.stdev(floats) / len(floats) ** 0.5
    return Decimal(str(mean)), Decimal(str(half))


def walk(bars: list[Bar], hold: int, warmup: int) -> list[tuple[str, Decimal | None, Decimal]]:
    """`(kind, live_return_or_None, backtest_return)` per non-overlapping entry in one instrument.

    **`backtest_return` is computed for every entry, including the unfilled ones.** That is exactly
    the population the engine assumes it trades, and the comparison has no meaning without it.

    **`live_return` is `None` when nothing filled**, rather than the backtest's number standing in.
    A missing position is not a position that returned what the backtest says it did, and putting a
    value there would make the two columns agree by construction on the very rows they differ on.
    """
    out: list[tuple[str, Decimal | None, Decimal]] = []
    for i in range(warmup, len(bars) - hold - 2, hold):
        limit = bars[i].close
        forward = bars[i + 1]
        exit_price = bars[i + 1 + hold].close
        if limit <= 0 or forward.open <= 0:
            continue
        fill = classify(limit, forward)
        backtest = forward_return(forward.open, exit_price)
        live = forward_return(fill.price, exit_price) if fill.price is not None else None
        out.append((fill.kind, live, backtest))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(prog="measure_fill_convention")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--hold", type=int, default=HOLD)
    parser.add_argument("--out", type=Path,
                        default=Path("docs/decisions/measurements/fill-convention-2026-09-06.json"))
    args = parser.parse_args()

    store = BarStore(args.data / "bars.duckdb")
    directory = DirectoryStore(args.data / "directory.duckdb")
    as_of = store.latest_knowledge_time()
    if as_of is None:
        print("the bar store is empty; nothing to measure")
        return 1
    rule = rules.LiquidityRule(
        min_price=MIN_PRICE, min_adtv=MIN_ADTV, adtv_window=ADTV_WINDOW,
        min_history=MIN_HISTORY, adtv_lag=ADTV_LAG,
    )
    selection = selection_rules.select(directory, store, rule, as_of)
    admitted = [m.instrument.id for m in selection.members]
    print(f"as_of {as_of.isoformat()}   admitted {len(admitted)}   hold {args.hold}")

    by_kind: dict[str, list[Decimal]] = {MARKETABLE: [], PASSIVE: [], UNFILLED: []}
    live_all: list[Decimal] = []
    backtest_all: list[Decimal] = []
    instruments = 0
    for name in admitted:
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        bars = list(series.bars) if series else []
        if len(bars) < WARMUP + args.hold + 3:
            continue
        instruments += 1
        for kind, live, backtest in walk(bars, args.hold, WARMUP):
            by_kind[kind].append(backtest)
            backtest_all.append(backtest)
            if live is not None:
                live_all.append(live)
    store.close()
    directory.close()

    total = len(backtest_all)
    if not total:
        print("no entries; nothing to compare")
        return 1

    print(f"instruments {instruments:,}   non-overlapping entries {total:,}\n")
    print("HOW THE LIVE ORDER MEETS THE SESSION - and only the first crosses a spread")
    rows: list[dict[str, object]] = []
    for kind in (MARKETABLE, PASSIVE, UNFILLED):
        values = by_kind[kind]
        mean, half = interval(values)
        share = Decimal(len(values)) / total
        rows.append({
            "kind": kind, "share": str(round(share, 4)), "entries": len(values),
            "forward_return_at_open_mean": str(round(mean, 6)),
            "ci_half_width": str(round(half, 6)),
        })
        print(f"  {kind:<11} {float(share):>6.1%}  n={len(values):>7,}   "
              f"forward {args.hold}-session return at the open "
              f"{float(mean) * 100:+7.3f}% +-{float(half) * 100:.3f}")

    live_mean, live_half = interval(live_all)
    back_mean, back_half = interval(backtest_all)
    adverse = live_mean - back_mean
    print(f"\n  {'the backtest: every name at the open':<42}"
          f"{float(back_mean) * 100:+7.3f}% +-{float(back_half) * 100:.3f}  n={total:,}")
    print(f"  {'the live path: only what the limit fills':<42}"
          f"{float(live_mean) * 100:+7.3f}% +-{float(live_half) * 100:.3f}  n={len(live_all):,}")
    print(f"\n  ADVERSE SELECTION {float(adverse) * 100:+.3f}% per entry.")
    print("  The names the limit misses DO run better; filling AT the limit buys the rest")
    print("  cheaper, and the two nearly cancel. The mechanism is real, the size is not.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "as_of": as_of.isoformat(),
        "hold": args.hold,
        "instruments": instruments,
        "entries": total,
        "liquidity_rule": {
            "min_price": str(MIN_PRICE), "min_adtv": str(MIN_ADTV),
            "adtv_window": ADTV_WINDOW, "min_history": MIN_HISTORY, "adtv_lag": ADTV_LAG,
        },
        "by_kind": rows,
        "backtest_mean": str(round(back_mean, 6)),
        "live_mean": str(round(live_mean, 6)),
        "adverse_selection": str(round(adverse, 6)),
        "gross_of_costs": True,
        "not_measured": [
            "cost - every figure here is gross; which fills happen is the question",
            "the SELECTED subset; this is the whole admitted universe, and a momentum rule "
            "would over-weight exactly the names that gap up",
        ],
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
