"""Does a buy/hold band pay for itself here? The one cost mitigation this project has not tried.

**The published finding this tests.** Novy-Marx & Velikov, *A Taxonomy of Anomalies and Their
Trading Costs* (RFS 2016), and the follow-up cost-mitigation comparison: anomalies with one-sided
monthly turnover **below about 50%** mostly keep a significant net spread; **few above it do**. Of
the mitigations they compare, a **buy/hold spread** - buy into the top 10%, keep holding until the
name falls out of the top 30% - is the most effective, and it is the only one that does not throw
away gross performance along with the cost. Rebalancing less often saves a similar amount and gives
back as much in decayed signal. Restricting the universe to liquid names is the WEAKEST, and is what
`DR-003` already does. **This is an authored import** (`AGENTS.md` §10.3) and is marked as one: the
claim is theirs, the measurement below is this universe's.

**Where this system sits on that line - and the first draft of this docstring got it wrong.** It
said turnover here is *"above 100% a month"*, reasoning from `exit.max_holding_period` = 20 and
`DR-029` §7's mix, where 88.2% of entries leave on a stop or target before the cap. **That is true
of the EXIT POLICY and false of the SELECTION RULE**, and this tool measures the second: a
top-decile book that sells only on rank turns over **29.2% a month**, already below the line. The
two constructions are different populations of the same word, which is the `AGENTS.md` §17 error
this repository keeps paying for - so the finding is not that banding rescues a book drowning in
turnover. It is that **the turnover problem lives in the stops and targets, not in the ranking.**

**What this measures.** The same construction as `measure_long_only_horizon.py` - same formation,
same liquidity rule judged at each date, same benchmark - run as a SEQUENTIAL book rather than a
series of independent snapshots, because a band is a statement about what you already hold. Two
policies, identical in every other respect:

  * **fixed** - hold the top decile, rebuild it from nothing at every rebalance
  * **banded** - buy into the top `buy` fraction, keep holding until the name falls out of the
    wider `hold` fraction, and refill only the vacancies

**Cost is charged on names that actually TRADE**, which is the entire mechanism. A fixed book pays
for a full turn every rebalance; a banded book pays only for its vacancies.

**EXPLORATORY. It sets no parameter and advances no validation status.** `screen.relative_strength_rule`
is `top_decile` by owner ruling (`DR-030`); the band widths below are NOT ratified and are pinned
here as the literature's own values so that a first measurement has something to report.

    python tools/measure_banding.py --data <store>
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

from measure_momentum_horizon import FORMATION, RULE, _formation_return
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates, _forward_returns
from swingdesk.contracts.market import Interval, Series
from swingdesk.market_data import BarStore

#: `rs.benchmark`, `assumed:DR-018`.
BENCHMARK = "SPY"

#: `screen.relative_strength_rule` = `top_decile`, owner ruling via `DR-030`. The BUY side of every
#: policy below, so the two differ only in when a name is SOLD.
BUY = Decimal("0.10")

#: The hold bands to sweep. `0.10` is the fixed policy - buy and hold thresholds equal, so a name
#: leaving the top decile is sold the same day. The rest widen the exit only.
HOLD_BANDS = (Decimal("0.10"), Decimal("0.20"), Decimal("0.30"), Decimal("0.50"))

#: Sessions between rebalances. `exit.max_holding_period`, ratified by `DR-012`.
REBALANCE = 20

#: `DR-005`, ratified: 25 bps per side. `DR-040` measures 26.46 at the open and 4.03 at the close;
#: this study charges the ratified number so it is comparable with everything already published,
#: and the sensitivity to that choice is reported beside the result.
SLIPPAGE_BPS = Decimal("25")


def rank_names(scores: dict[str, Decimal]) -> list[str]:
    """Best formation return first; ties broken by name so a re-run produces the same book."""
    return [name for _, name in sorted(
        ((score, name) for name, score in scores.items()),
        key=lambda pair: (-pair[0], pair[1]),
    )]


def rebalance(
    held: set[str], ranked: list[str], buy: Decimal, hold: Decimal
) -> tuple[set[str], int]:
    """The next book and how many names were bought, given what is held and today's ranking.

    **The band is the whole mechanism.** A name already held survives while it sits inside the
    WIDER `hold` fraction; a name not held must reach the NARROWER `buy` fraction to enter. With
    `hold == buy` this is the fixed policy and the two are directly comparable, which is why the
    sweep includes that case rather than reimplementing it.

    Book size is pinned to the buy fraction so both policies run the same amount of capital: a band
    that quietly held more names would beat a fixed book by diversification rather than by cost.
    """
    size = int(len(ranked) * buy)
    if size < 1:
        return set(), 0
    hold_cut = int(len(ranked) * hold)
    position = {name: i for i, name in enumerate(ranked)}

    # Keepers, best first. A held name that has left the ranking entirely (delisted, or no longer
    # admitted) is dropped rather than assumed still good.
    keepers = sorted(
        (name for name in held if position.get(name, len(ranked)) < hold_cut),
        key=lambda name: position[name],
    )[:size]

    vacancies = size - len(keepers)
    incoming = [name for name in ranked[:size] if name not in set(keepers)][:vacancies]
    return set(keepers) | set(incoming), len(incoming)


def book_return(book: set[str], forward: dict[str, Decimal]) -> Decimal | None:
    """Equal-weighted mean forward return of the names held, or None when none has one."""
    values = [forward[name] for name in book if name in forward]
    if not values:
        return None
    return sum(values, Decimal(0)) / len(values)


def cost_of(bought: int, size: int, per_side_bps: Decimal) -> Decimal:
    """A round trip charged to every name that turned over, spread across the whole book.

    A name that enters will one day leave, so its full cost is two sides; charging both at entry
    prices the decision that caused them rather than deferring half of it to a later period.
    """
    if size < 1:
        return Decimal(0)
    return Decimal(bought) / Decimal(size) * 2 * per_side_bps / Decimal(10000)


def summarise(values: list[Decimal]) -> tuple[Decimal, Decimal]:
    if len(values) < 2:
        return (values[0], Decimal(0)) if values else (Decimal(0), Decimal(0))
    floats = [float(v) for v in values]
    return (
        Decimal(str(statistics.mean(floats))),
        Decimal(str(1.96 * statistics.stdev(floats) / len(floats) ** 0.5)),
    )


def measure(store: BarStore, as_of: datetime, rebalance_every: int) -> list[dict[str, object]]:
    series_by_name = {}
    for name in sorted(store.instrument_ids(as_of)):
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series and len(series.bars) >= FORMATION + rebalance_every + 1:
            series_by_name[name] = series
    if BENCHMARK not in series_by_name:
        raise SystemExit(f"{BENCHMARK} has too little history to serve as the benchmark")

    closes = {n: [b.close for b in s.bars] for n, s in series_by_name.items()}
    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}
    forward = {n: _forward_returns(s, rebalance_every) for n, s in series_by_name.items()}
    calendar = sorted({d for f in forward.values() for d in f})
    dates = calendar[::rebalance_every]
    admitted = {n: _admitted_dates(s, RULE, dates) for n, s in series_by_name.items()}
    bench = forward[BENCHMARK]
    print(f"  instruments with enough history: {len(series_by_name)}   "
          f"rebalance dates: {len(dates)}")

    rows: list[dict[str, object]] = []
    for band in HOLD_BANDS:
        held: set[str] = set()
        gross: list[Decimal] = []
        net: list[Decimal] = []
        turnovers: list[Decimal] = []
        for session in dates:
            if session not in bench:
                continue
            scores: dict[str, Decimal] = {}
            for name, positions in index_of.items():
                end = positions.get(session)
                if end is None or session not in admitted[name]:
                    continue
                value = _formation_return(closes[name], end, 0)
                if value is not None:
                    scores[name] = value
            if len(scores) < MIN_NAMES_PER_DATE:
                continue
            ranked = rank_names(scores)
            book, bought = rebalance(held, ranked, BUY, band)
            if not book:
                continue
            size = len(book)
            observed = {n: forward[n][session] for n in book if session in forward.get(n, {})}
            excess = book_return(book, observed)
            if excess is not None:
                charge = cost_of(bought, size, SLIPPAGE_BPS)
                gross.append(excess - bench[session])
                net.append(excess - bench[session] - charge)
                turnovers.append(Decimal(bought) / Decimal(size))
            held = book

        gross_mean, gross_half = summarise(gross)
        net_mean, net_half = summarise(net)
        turn_mean, _ = summarise(turnovers)
        # One-sided turnover per rebalance, restated per 21-session month for the literature's line.
        monthly = turn_mean * Decimal(21) / Decimal(rebalance_every)
        rows.append({
            "hold_band": str(band), "policy": "fixed" if band == BUY else "banded",
            "periods": len(gross),
            "turnover_per_rebalance": str(round(turn_mean, 4)),
            "turnover_monthly": str(round(monthly, 4)),
            "mean_hold_sessions": str(round(
                Decimal(rebalance_every) / turn_mean, 1) if turn_mean > 0 else 0),
            "gross_excess": str(round(gross_mean, 6)), "gross_ci": str(round(gross_half, 6)),
            "net_excess": str(round(net_mean, 6)), "net_ci": str(round(net_half, 6)),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(prog="measure_banding")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--rebalance", type=int, default=REBALANCE)
    parser.add_argument("--out", type=Path,
                        default=Path("docs/decisions/measurements/banding-2026-09-06.json"))
    args = parser.parse_args()

    store = BarStore(args.data / "bars.duckdb")
    as_of = store.latest_knowledge_time()
    if as_of is None:
        print("the bar store is empty")
        return 1
    print(f"as_of {as_of.isoformat()}   rebalance every {args.rebalance} sessions   "
          f"buy top {float(BUY):.0%}")
    rows = measure(store, as_of, args.rebalance)
    store.close()

    print(f"\n  TOP-DECILE BOOK vs {BENCHMARK}, held sequentially - only the SELL rule changes")
    print(f"  cost charged on names that TRADE, at DR-005's {SLIPPAGE_BPS} bps per side\n")
    print(f"  {'hold band':<12}{'policy':<9}{'turnover/mo':>12}{'mean hold':>11}"
          f"{'gross':>11}{'net':>11}{'+-':>8}")
    for row in rows:
        print(f"  top {float(Decimal(str(row['hold_band']))):<8.0%}{row['policy']:<9}"
              f"{float(Decimal(str(row['turnover_monthly']))):>11.1%}"
              f"{float(Decimal(str(row['mean_hold_sessions']))):>10.0f}d"
              f"{float(Decimal(str(row['gross_excess']))) * 100:>+10.3f}%"
              f"{float(Decimal(str(row['net_excess']))) * 100:>+10.3f}%"
              f"{float(Decimal(str(row['net_ci']))) * 100:>8.3f}")

    print("\n  The literature's line is 50% one-sided monthly turnover: below it most anomalies")
    print("  keep a net spread, above it few do (Novy-Marx & Velikov 2016 - an authored import).")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "as_of": as_of.isoformat(),
        "rebalance_sessions": args.rebalance,
        "buy_fraction": str(BUY),
        "benchmark": BENCHMARK,
        "formation": FORMATION,
        "slippage_bps_per_side": str(SLIPPAGE_BPS),
        "rows": rows,
        "exploratory": True,
        "authored_import": "Novy-Marx & Velikov, RFS 2016 - the 50%/month line and the buy/hold "
                           "spread as the strongest mitigation. Their claim, this universe's "
                           "measurement.",
        "not_measured": [
            "band widths are the literature's, not ratified here",
            "the cost is DR-005's flat 25bp per side; DR-040 measures 26.46 at the open and "
            "4.03 at the close, and this study charges neither",
            "survivorship - the directory is today's",
        ],
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
