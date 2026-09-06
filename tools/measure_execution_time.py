"""Does moving the trade off the open survive the gross it gives up? `DR-040` §6, run.

`DR-040` measured what the admitted universe costs to cross and found the constant `DR-005` set is
**right about 09:30 and four to fourteen times too high afterwards**. `CARD-001` enters at
`next session's open`, so the project pays the worst value the session offers.

**And `DR-040` §4 refused to draw the obvious conclusion**, because a later entry is not the same
trade at a better price - it changes the GROSS as well as the cost, and every gross figure in this
project was measured on entries struck at the open. Subtracting a smaller cost from an unchanged
gross is the error `DR-029` §5 made. This tool measures the gross.

**Paired by construction, and that is what makes it cheap.** The same instrument, the same entry
date, the same holding period; only the CLOCK moves. A difference between two execution times is
therefore a paired difference, and the market-wide variation that dominates the level cancels out
of it. Comparing three unpaired samples of the same size would need far more of them to see the
same effect.

**Read the paired columns, not the levels.** The level is one sample of one decade and carries all
of that decade's drift; the paired difference is what this tool exists to report.

**EXPLORATORY. It sets no parameter and advances no validation status.** It evaluates the
`exit.max_holding_period` hold at three execution times, which is three configurations of a return
- unlike `DR-040`, this one is a strategy measurement and would spend trials if it were registered.

**What it is NOT.** Not the store: 30-minute bars come from the venue, split-adjusted, and this
project holds no intraday series (`TODO.md` §4 carries whether it should). Not selected: the walk
takes every admitted name rather than a ranked subset, so it measures the CLOCK and not the card.
Not survivorship-free: the sample is drawn from names admitted today.

    python tools/measure_execution_time.py --data <store> --sample 250
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.application import universe as selection_rules
from swingdesk.market_data import BarStore
from swingdesk.reference_data import universe as rules
from swingdesk.reference_data.directory import DirectoryStore

EASTERN = ZoneInfo("America/New_York")
HOST = "https://data.alpaca.markets"

#: `DR-003`'s rule, pinned rather than read from the registry.
MIN_PRICE = Decimal("5.00")
MIN_ADTV = Decimal(5_000_000)
ADTV_WINDOW = 20
MIN_HISTORY = 250
ADTV_LAG = 0

#: `exit.max_holding_period`, ratified by `DR-012`.
HOLD = 20

#: The three moments, and the price each one means. A 30-minute bar stamped 09:30 opens at the
#: opening print and a bar stamped 15:30 closes at the closing print, so both ends of the session
#: are reachable without a second timeframe.
EXECUTIONS: tuple[tuple[str, str, str], ...] = (
    ("09:30 open", "09:30", "open"),
    ("11:00", "11:00", "open"),
    ("15:30 close", "15:30", "close"),
)

#: Median per-side spread at each moment, 2026, from `measurements/quoted-spread-2026-09-06.json`.
#: Pinned here rather than read, so this study records the cost it actually charged - the same
#: practice `measure_spread.py` follows with the liquidity rule.
SPREAD_BPS_PER_SIDE: dict[str, Decimal] = {
    "09:30 open": Decimal("26.46"),
    "11:00": Decimal("5.75"),
    "15:30 close": Decimal("4.03"),
}

START = "2016-01-04T00:00:00Z"
MIN_SECONDS_BETWEEN_CALLS = 0.32


class FeedUnavailable(RuntimeError):
    """The venue would not serve bars. Raised rather than degraded to a guess."""


def _credentials() -> tuple[str, str]:
    key = os.environ.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise FeedUnavailable("APCA_API_KEY_ID and APCA_API_SECRET_KEY must both be set")
    return key, secret


def fetch_sessions(
    ticker: str, start: str, end: str, credentials: tuple[str, str]
) -> dict[date, dict[str, Decimal]]:
    """Session date -> {execution label: price}, reduced page by page as the venue serves them."""
    key, secret = credentials
    out: dict[date, dict[str, Decimal]] = {}
    page: str | None = None
    while True:
        query = {
            "start": start, "end": end, "timeframe": "30Min", "limit": 10000,
            "feed": "sip", "adjustment": "split",
        }
        if page:
            query["page_token"] = page
        request = urllib.request.Request(
            f"{HOST}/v2/stocks/{urllib.parse.quote(ticker)}/bars?{urllib.parse.urlencode(query)}",
            headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret},
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    body = json.loads(response.read().decode())
                break
            except urllib.error.HTTPError as error:
                if error.code == 429:
                    time.sleep(2 * (attempt + 1))
                    continue
                return out
            except (urllib.error.URLError, TimeoutError):
                time.sleep(1)
        else:
            return out
        # Reduced page by page rather than accumulated. A decade of 30-minute bars including the
        # extended session is roughly 86,000 per instrument, and only three of every 32 are ever
        # read - holding the other 29 in memory to throw them away is the 2.6-million-objects
        # mistake `DR-024` §7 already paid for once, in the same shape.
        reduce_into(out, body.get("bars") or [])
        page = body.get("next_page_token")
        time.sleep(MIN_SECONDS_BETWEEN_CALLS)
        if not page:
            return out


def reduce_into(by_session: dict[date, dict[str, Decimal]], bars: list[dict[str, object]]) -> None:
    """Fold one page of bars into the session map, keeping only the three moments that are read.

    **Pre- and post-market bars are dropped by the label lookup itself**, not by a time filter: only
    09:30, 11:00 and 15:30 are read. Three of every thirty-two bars survive, which is why this runs
    per page instead of over an accumulated decade.
    """
    wanted = {stamp: (label, field) for label, stamp, field in EXECUTIONS}
    for bar in bars:
        raw = bar.get("t")
        if not isinstance(raw, str):
            continue
        when = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(EASTERN)
        found = wanted.get(when.strftime("%H:%M"))
        if not found:
            continue
        label, field = found
        price = bar.get("o" if field == "open" else "c")
        if not isinstance(price, (int, float)) or price <= 0:
            continue
        by_session.setdefault(when.date(), {})[label] = Decimal(str(price))


def complete_sessions(
    by_session: dict[date, dict[str, Decimal]],
) -> dict[date, dict[str, Decimal]]:
    """Only sessions carrying all three moments.

    A half-day that closes at 13:00 contributes nothing rather than contributing an exit price from
    a different clock than its entry - which would silently make the comparison unpaired on exactly
    the sessions where the clock matters most.
    """
    complete = {label for label, _, _ in EXECUTIONS}
    return {d: v for d, v in by_session.items() if set(v) == complete}


def paired_returns(
    sessions: dict[date, dict[str, Decimal]], hold: int
) -> list[tuple[date, dict[str, Decimal]]]:
    """One entry per non-overlapping window: the same trade priced at each execution time.

    Entry on session `i`, exit on session `i + hold`, both at the SAME moment of the day - which is
    what makes the three columns a paired comparison rather than three separate strategies.

    **The entry date travels with the row**, because the rows are not independent of one another:
    the difference between an 09:30 entry and an 11:00 entry is mostly the overnight gap, and that
    is a market-wide event. `clustered_by_date` is what turns that into an honest interval.
    """
    days = sorted(sessions)
    out: list[tuple[date, dict[str, Decimal]]] = []
    for i in range(0, len(days) - hold, hold):
        entry_day, exit_day = days[i], days[i + hold]
        row: dict[str, Decimal] = {}
        for label, _, _ in EXECUTIONS:
            entry = sessions[entry_day][label]
            row[label] = (sessions[exit_day][label] - entry) / entry
        out.append((entry_day, row))
    return out


def clustered_by_date(deltas: list[tuple[date, Decimal]]) -> list[Decimal]:
    """One observation per entry DATE: the mean paired difference across instruments that day.

    Kept as a diagnostic rather than as the headline. Equal-weighting DATES is not the same
    estimator as equal-weighting ENTRIES, and where a date carries one instrument and another
    carries a dozen the two means genuinely differ - measured 2026-09-06, -0.365% against -0.103%.
    A reader shown only one of them cannot see that the choice moved the answer.
    """
    grouped: dict[date, list[Decimal]] = {}
    for when, value in deltas:
        grouped.setdefault(when, []).append(value)
    return [sum(v, Decimal(0)) / len(v) for _, v in sorted(grouped.items())]


def cluster_robust(deltas: list[tuple[date, Decimal]]) -> tuple[Decimal, Decimal, int]:
    """Entry-weighted mean with a date-clustered standard error: `(mean, half_width, clusters)`.

    **This is the headline estimator and the two above are its bookends.** The point estimate is the
    plain mean over entries - the quantity a book actually earns - and only the UNCERTAINTY is
    corrected, by allowing entries that share a date to move together.

    The usual sandwich: `Var(mean) = (1/N^2) * sum_over_dates( (sum of that date's deviations)^2 )`.
    With one entry per date it collapses to the independent-sample variance; with every entry on one
    date it collapses to zero degrees of freedom, which is the honest answer to a single observation
    repeated. Half-width is 1.96 standard errors.
    """
    if len(deltas) < 2:
        return (deltas[0][1], Decimal(0), 1) if deltas else (Decimal(0), Decimal(0), 0)
    values = [float(v) for _, v in deltas]
    n = len(values)
    mean = statistics.mean(values)
    grouped: dict[date, float] = {}
    for when, value in deltas:
        grouped[when] = grouped.get(when, 0.0) + (float(value) - mean)
    variance = sum(total * total for total in grouped.values()) / (n * n)
    return Decimal(str(mean)), Decimal(str(1.96 * variance ** 0.5)), len(grouped)


def net_of_spread(gross: Decimal, per_side_bps: Decimal) -> Decimal:
    """Gross less a round trip at the quoted half-spread for that moment."""
    return gross - per_side_bps * 2 / Decimal(10000)


def summarise(values: list[Decimal]) -> tuple[Decimal, Decimal]:
    """Mean and a 1.96-standard-error half-width."""
    if len(values) < 2:
        return (values[0], Decimal(0)) if values else (Decimal(0), Decimal(0))
    floats = [float(v) for v in values]
    mean = statistics.mean(floats)
    return Decimal(str(mean)), Decimal(str(1.96 * statistics.stdev(floats) / len(floats) ** 0.5))


def admitted(data: Path) -> tuple[list[str], datetime]:
    store = BarStore(data / "bars.duckdb")
    directory = DirectoryStore(data / "directory.duckdb")
    try:
        as_of = store.latest_knowledge_time()
        if as_of is None:
            raise FeedUnavailable("the bar store is empty")
        rule = rules.LiquidityRule(
            min_price=MIN_PRICE, min_adtv=MIN_ADTV, adtv_window=ADTV_WINDOW,
            min_history=MIN_HISTORY, adtv_lag=ADTV_LAG,
        )
        selection = selection_rules.select(directory, store, rule, as_of)
        return sorted(m.instrument.ticker for m in selection.members), as_of
    finally:
        store.close()
        directory.close()


def main() -> int:
    parser = argparse.ArgumentParser(prog="measure_execution_time")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--sample", type=int, default=250)
    parser.add_argument("--seed", type=int, default=20260906)
    parser.add_argument("--hold", type=int, default=HOLD)
    parser.add_argument("--out", type=Path,
                        default=Path("docs/decisions/measurements/execution-time-2026-09-06.json"))
    args = parser.parse_args()

    credentials = _credentials()
    names, as_of = admitted(args.data)
    random.seed(args.seed)
    drawn = sorted(random.sample(names, min(args.sample, len(names))))
    end = as_of.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"as_of {as_of.isoformat()}   admitted {len(names)}   sampled {len(drawn)} "
          f"(seed {args.seed})   hold {args.hold}")
    print(f"30-minute bars, split-adjusted, {START[:10]} to {end[:10]}\n")

    per_execution: dict[str, list[Decimal]] = {label: [] for label, _, _ in EXECUTIONS}
    dated: dict[str, list[tuple[date, Decimal]]] = {label: [] for label, _, _ in EXECUTIONS}
    entries = instruments = 0
    started = time.monotonic()
    for n, ticker in enumerate(drawn, 1):
        rows = paired_returns(
            complete_sessions(fetch_sessions(ticker, START, end, credentials)), args.hold
        )
        if not rows:
            continue
        instruments += 1
        entries += len(rows)
        for when, row in rows:
            for label in per_execution:
                per_execution[label].append(row[label])
                dated[label].append((when, row[label]))
        if n % 25 == 0:
            print(f"  {n}/{len(drawn)}  instruments {instruments}  entries {entries:,}  "
                  f"({time.monotonic() - started:.0f}s)")

    if not entries:
        print("no paired entries; nothing to compare")
        return 1

    print(f"\ninstruments {instruments:,}   paired entries {entries:,}\n")
    print(f"FORWARD {args.hold}-SESSION RETURN BY EXECUTION TIME - same trades, only the clock moves")
    print(f"  {'executed at':<14}{'gross':>10}{'+-':>8}   {'per side':>9}{'net':>10}{'+-':>8}")
    rows_out: list[dict[str, object]] = []
    for label, _, _ in EXECUTIONS:
        gross, half = summarise(per_execution[label])
        spread = SPREAD_BPS_PER_SIDE[label]
        net = net_of_spread(gross, spread)
        rows_out.append({
            "execution": label, "entries": entries,
            "gross_mean": str(round(gross, 6)), "ci_half_width": str(round(half, 6)),
            "per_side_bps_charged": str(spread), "net_mean": str(round(net, 6)),
        })
        print(f"  {label:<14}{float(gross) * 100:>+9.3f}%{float(half) * 100:>8.3f}   "
              f"{float(spread):>8.2f}b{float(net) * 100:>+9.3f}%{float(half) * 100:>8.3f}")

    print("\nPAIRED DIFFERENCES against the ratified open - this is the measurement")
    base_dated = dated["09:30 open"]
    pairs: list[dict[str, object]] = []
    for label, _, _ in EXECUTIONS:
        if label == "09:30 open":
            continue
        paired = [
            (when, a - b) for (when, a), (_, b) in zip(dated[label], base_dated, strict=True)
        ]
        _, naive_half = summarise([value for _, value in paired])
        mean, half, clusters = cluster_robust(paired)
        by_date_mean, by_date_half = summarise(clustered_by_date(paired))
        cost_saved = (SPREAD_BPS_PER_SIDE["09:30 open"] - SPREAD_BPS_PER_SIDE[label]) * 2 / 10000
        net = mean + cost_saved
        pairs.append({
            "execution": label,
            "gross_delta_mean": str(round(mean, 6)),
            "ci_half_width_cluster_robust": str(round(half, 6)),
            "ci_half_width_naive": str(round(naive_half, 6)),
            "gross_delta_equal_weighted_by_date": str(round(by_date_mean, 6)),
            "ci_half_width_equal_weighted_by_date": str(round(by_date_half, 6)),
            "clusters": clusters,
            "gross_delta_excludes_zero": abs(mean) > half,
            "cost_saved": str(round(cost_saved, 6)),
            "net_delta": str(round(net, 6)),
            "net_excludes_zero": abs(net) > half,
        })
        print(f"  {label:<14} gross {float(mean) * 100:+7.3f}%  "
              f"+-{float(half) * 100:.3f} cluster-robust over {clusters} date(s)   "
              f"(naive +-{float(naive_half) * 100:.3f})")
        print(f"  {'':<14} cost saved {float(cost_saved) * 100:+7.3f}%   "
              f"NET {float(net) * 100:+7.3f}% +-{float(half) * 100:.3f}   "
              f"{'EXCLUDES zero' if abs(net) > half else 'includes zero - NOT established'}")
        print(f"  {'':<14} (equal-weighting dates instead gives "
              f"{float(by_date_mean) * 100:+7.3f}% +-{float(by_date_half) * 100:.3f})")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "as_of": as_of.isoformat(), "hold": args.hold, "seed": args.seed,
        "instruments": instruments, "paired_entries": entries,
        "bars": "30Min, split-adjusted, venue SIP - NOT the project's store",
        "spread_source": "measurements/quoted-spread-2026-09-06.json, 2026 medians",
        "by_execution": rows_out,
        "paired_against_open": pairs,
        "exploratory": True,
        "not_measured": [
            "selection - every admitted name, not a ranked subset",
            "market impact",
            "survivorship - the sample is drawn from names admitted today",
        ],
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
