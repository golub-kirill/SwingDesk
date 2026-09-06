"""What the admitted universe actually costs to cross, from the venue's own NBBO.

`DR-005` set `costs.slippage_model` to **25.44 bps per side** from two daily-OHLC estimators, and was
careful about its own status: `assumed`, never `validated`. `EVIDENCE_SUMMARY` §2 went further and
said the level is **"not obtainable from daily OHLC"**, which is true, and then drew a conclusion
that is not - *"`PR-006`, real fills, is the only route left"*. `DR-004` had already written the
premise underneath it:

> spread-derived slippage from quoted bid/ask: correct and unavailable - no free source serves
> historical intraday spreads point-in-time

**That premise is false and `tools/probe_quotes.py` refutes it live.** The venue this project already
holds an account with serves consolidated NBBO quotes back to 2016 on the free tier; only the last
fifteen minutes are withheld. So the quantity `DR-005` estimated can be measured, and this tool
measures it - same population, same instant, same `S/2 per side` convention, so the two numbers are
comparable rather than merely adjacent (`AGENTS.md` §17).

**Two things it finds that a single constant cannot express.**

  1. **The spread is a function of the time of day**, by roughly a factor of six between the opening
     minute and late morning. A backtest that charges one number charges the wrong one twice.
  2. **`CARD-001` enters at `next session's open`**, which is the most expensive minute of the
     session - so the ratified entry convention sits at the bad end of that curve.

**What this does NOT measure, stated because the gap matters.** A quoted spread is what an order
pays *to cross*. It is an upper bound for an aggressive order and an over-charge for a passive one:
the live path sends `order_type: limit` resting at the decision session's close
(`registry/broker_policy.yml`, `application/pipeline.py` `entry = stored.bars[-1].close`), and a
resting limit that fills has not crossed anything. Market impact is not measured either - this is a
top-of-book quantity and says nothing about depth. Both limits are reported beside the numbers
rather than left for a reader to discover.

**Nothing here sets a parameter.** `costs.slippage_model` is ratified at 25.44 and only the owner
moves it; this is the measurement a proposal would have to argue from.

    python tools/measure_quoted_spread.py --sample 120
    python tools/measure_quoted_spread.py --sample 60 --years 2016 2021 2026
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
from datetime import time as clock
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.market import Bar, Interval, Series
from swingdesk.market_data import BarStore

#: `DR-003`'s liquidity rule, pinned rather than read from the registry - the same practice
#: `tools/measure_spread.py` uses, and for the same reason: a committed measurement records what it
#: actually ran under, so a later ratification cannot silently change what it means.
MIN_PRICE = Decimal("5.00")
MIN_ADTV = Decimal(5_000_000)
ADTV_WINDOW = 20
MIN_HISTORY = 250

#: `DR-005` measured under `adtv_lag=0`; `DR-017`'s lag postdates it. Matching it keeps the
#: population identical, which is the whole point of running this at all.
ADTV_LAG = 0

#: The number this tool exists to be compared against, in bps per side.
DR005_PER_SIDE_BPS = Decimal("25.44")

EASTERN = ZoneInfo("America/New_York")
HOST = "https://data.alpaca.markets"

#: Times of the session, in Eastern, converted per-date so a winter date is not sampled an hour out.
#: The first is five seconds into continuous trading - `CARD-001`'s own `next session's open`.
WINDOWS: tuple[tuple[str, clock], ...] = (
    ("09:30 open", clock(9, 30, 5)),
    ("10:00", clock(10, 0)),
    ("11:00", clock(11, 0)),
    ("15:55 close", clock(15, 55)),
)

#: Quotes read per (instrument, date, window). One quote is a tick; the median of a handful is an
#: estimate. Kept small because the request count is the binding cost, not the response size.
QUOTES_PER_WINDOW = 25

#: Free tier documents 200 requests/minute. Sleep between calls rather than discovering the limit.
MIN_SECONDS_BETWEEN_CALLS = 0.32


class QuoteFeedUnavailable(RuntimeError):
    """The venue would not serve quotes. Raised rather than degraded to a guess."""


def _credentials() -> tuple[str, str]:
    key = os.environ.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise QuoteFeedUnavailable(
            "APCA_API_KEY_ID and APCA_API_SECRET_KEY must both be set. This reads the venue's "
            "market-data host, which is not the trading host `registry/broker_policy.yml` "
            "allowlists, and it issues GET only."
        )
    return key, secret


def utc_start(day: date, at: clock) -> str:
    """Eastern wall-clock to a UTC instant, so a January date is not sampled an hour early."""
    return (
        datetime.combine(day, at, tzinfo=EASTERN)
        .astimezone(ZoneInfo("UTC"))
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def fetch_quotes(
    ticker: str, start: str, limit: int, credentials: tuple[str, str], opener=urllib.request.urlopen
) -> list[dict[str, object]]:
    """The first `limit` NBBO updates at or after `start`. An empty list means the venue had none."""
    query = urllib.parse.urlencode({"start": start, "limit": limit, "feed": "sip"})
    url = f"{HOST}/v2/stocks/{urllib.parse.quote(ticker)}/quotes?{query}"
    key, secret = credentials
    request = urllib.request.Request(
        url,
        headers={
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": secret,
            "Accept": "application/json",
        },
    )
    for attempt in range(4):
        try:
            with opener(request, timeout=30) as response:
                return json.loads(response.read().decode()).get("quotes") or []
        except urllib.error.HTTPError as error:
            if error.code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            if error.code in (401, 403):
                raise QuoteFeedUnavailable(
                    f"{error.code} from the market-data host. The free tier serves SIP quotes older "
                    f"than fifteen minutes; a refusal here is a credential or entitlement problem, "
                    f"not a missing feed."
                ) from error
            return []
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    return []


def proportional_spread_bps(quotes: list[dict[str, object]]) -> Decimal | None:
    """Median `(ask - bid) / mid` in bps. `None` when no quote in the window was two-sided.

    Crossed and locked books are dropped rather than clamped to zero: a locked market is a real
    state of the tape and its spread is not zero, it is undefined, and averaging a zero in would
    pull the estimate toward the flattering side.
    """
    values: list[Decimal] = []
    for quote in quotes:
        bid, ask = quote.get("bp"), quote.get("ap")
        if not isinstance(bid, (int, float)) or not isinstance(ask, (int, float)):
            continue
        if bid <= 0 or ask <= bid:
            continue
        bid_d, ask_d = Decimal(str(bid)), Decimal(str(ask))
        values.append((ask_d - bid_d) / ((ask_d + bid_d) / 2) * 10000)
    if not values:
        return None
    return Decimal(str(statistics.median(values)))


def percentiles(values: list[Decimal]) -> dict[str, Decimal]:
    """p10 / median / p90 / mean of an already-populated sample."""
    ordered = sorted(values)
    n = len(ordered)

    def at(fraction: float) -> Decimal:
        return ordered[min(n - 1, int(n * fraction))]

    return {
        "p10": at(0.10),
        "median": at(0.50),
        "p90": at(0.90),
        "mean": sum(ordered, Decimal(0)) / n,
    }


def break_even_round_trip_bps(
    gross_r: Decimal, cost_r: Decimal, charged_round_trip_bps: Decimal
) -> Decimal | None:
    """The round-trip cost, in bps of price, at which a gross expectancy in R reaches zero.

    `cost_r` is what `charged_round_trip_bps` costs in R units at some stop multiple - the exit
    surface publishes both - and the relation is linear, because `DR-005` charges a fraction of
    PRICE while R is a multiple of ATR. So the break-even scales straight off the published pair.

    `None` when the gross expectancy is not positive: a strategy that loses before costs has no
    cost at which it starts winning, and returning 0 would read as "free would be enough".
    """
    if gross_r <= 0 or cost_r <= 0:
        return None
    return charged_round_trip_bps * gross_r / cost_r


def admissible_on(bars: list[Bar], when: date) -> bool:
    """Would `DR-003`'s rule have admitted this instrument on `when`, from the bars up to `when`?

    **The store cannot answer this the usual way and that is the point.** `application/universe.py`
    `select()` takes a KNOWLEDGE time, and every bar in this store was ingested recently, so asking
    it for the 2016 universe returns nothing - we knew nothing in 2016. The rule is therefore
    re-applied here against the price and volume history a decision on that date would have had.

    **What this does NOT repair: the directory is today's.** A name that delisted before `when` is
    absent, so the reconstructed universe is survivorship-biased toward names that made it. That
    biases the measured spread DOWN - survivors are the liquid ones - so a finding that costs were
    HIGHER in the past survives the bias rather than being produced by it.
    """
    index = None
    for i, bar in enumerate(bars):
        if bar.session_date <= when:
            index = i
        else:
            break
    if index is None or index + 1 < MIN_HISTORY:
        return False
    if bars[index].close < MIN_PRICE:
        return False
    # No partial-window guard, deliberately: `MIN_HISTORY` is 250 and `ADTV_WINDOW` is 20, so the
    # history floor above already guarantees a full window. A guard nothing can trip is a guard no
    # test can prove, and mutation testing found this one alive - it survived being deleted.
    window = bars[index - ADTV_WINDOW + 1: index + 1]
    adtv = sum((b.close * b.volume for b in window), Decimal(0)) / ADTV_WINDOW
    return adtv >= MIN_ADTV


def universes_by_date(data: Path, days: list[date]) -> tuple[dict[date, list[str]], datetime]:
    """The admissible ticker set on each sampled date, and the store's knowledge instant.

    One pass over the store: every instrument's series is read once and tested against every date,
    because re-reading 12,000 series per date is the population-times-per-item cost this project
    has already paid for once.
    """
    store = BarStore(data / "bars.duckdb")
    try:
        as_of = store.latest_knowledge_time()
        if as_of is None:
            raise QuoteFeedUnavailable("the bar store is empty; there is no universe to measure")
        by_date: dict[date, list[str]] = {d: [] for d in days}
        for instrument_id in store.instrument_ids(as_of):
            series = store.as_of(instrument_id, Interval.DAY, Series.RAW, as_of)
            bars = list(series.bars) if series else []
            if len(bars) < MIN_HISTORY:
                continue
            for day in days:
                if admissible_on(bars, day):
                    by_date[day].append(instrument_id)
        return {d: sorted(v) for d, v in by_date.items()}, as_of
    finally:
        store.close()


def sample_dates(years: list[int], horizon: date) -> list[date]:
    """Two mid-month Wednesdays a year - February and August - up to but not including `horizon`.

    Wednesday because Monday and Friday carry weekend effects, mid-month because the third Friday's
    expiry week distorts the tape around it. Fixed rather than random: a re-run must produce the
    same population or the comparison across years is not one.

    **`horizon` is the store's own knowledge date, never the machine clock** (`REQ-DATA-001`, gate
    7). "In the future" is a statement about what the data knows; a wall clock would make this
    sampler return a different population on two machines and call both reproducible.
    """
    days: list[date] = []
    for year in years:
        for month in (2, 8):
            day = date(year, month, 15)
            while day.weekday() != 2:
                day = day.replace(day=day.day + 1)
            if day < horizon:
                days.append(day)
    return days


def main() -> int:
    parser = argparse.ArgumentParser(prog="measure_quoted_spread")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--sample", type=int, default=60,
                        help="instruments drawn from the admitted universe")
    parser.add_argument("--seed", type=int, default=20260906)
    parser.add_argument("--years", type=int, nargs="+",
                        default=[2016, 2019, 2022, 2024, 2026])
    parser.add_argument("--against", type=Path,
                        default=Path("docs/decisions/measurements/exit-surface-2026-09-06.json"),
                        help="the published surface whose break-even cost this prices")
    parser.add_argument("--out", type=Path,
                        default=Path("docs/decisions/measurements/quoted-spread-2026-09-06.json"))
    args = parser.parse_args()

    credentials = _credentials()
    # The dates are chosen before the universes, because each universe is the one that date had.
    probe_store = BarStore(args.data / "bars.duckdb")
    knowledge = probe_store.latest_knowledge_time()
    probe_store.close()
    if knowledge is None:
        print("the bar store is empty; nothing to measure")
        return 1
    days = sample_dates(args.years, knowledge.date())
    by_date, as_of = universes_by_date(args.data, days)

    # **Sampled per date, from that date's own universe.** Drawing one sample from TODAY's admitted
    # names and pricing it in 2016 measures what today's survivors cost then, which is a different
    # and much less useful quantity - and it is the population error `AGENTS.md` §17 keeps catching.
    drawn_by_date: dict[date, list[str]] = {}
    for day in days:
        pool = by_date[day]
        random.seed(args.seed + day.toordinal())
        drawn_by_date[day] = sorted(random.sample(pool, min(args.sample, len(pool))))

    calls_planned = sum(len(drawn_by_date[d]) for d in days) * len(WINDOWS)
    print(f"as_of {as_of.isoformat()}   seed {args.seed}")
    print(f"{'date':<12}{'admissible that day':>21}{'sampled':>9}")
    for day in days:
        print(f"{day.isoformat():<12}{len(by_date[day]):>21,}{len(drawn_by_date[day]):>9}")
    print(f"\nwindows: {len(WINDOWS)}   calls: {calls_planned:,}\n")

    # (window, year) -> ticker -> the per-date medians for that ticker
    collected: dict[tuple[str, int], dict[str, list[Decimal]]] = {}
    calls = empty = 0
    started = time.monotonic()
    for label, at in WINDOWS:
        for day in days:
            start = utc_start(day, at)
            for ticker in drawn_by_date[day]:
                spread = proportional_spread_bps(
                    fetch_quotes(ticker, start, QUOTES_PER_WINDOW, credentials)
                )
                calls += 1
                time.sleep(MIN_SECONDS_BETWEEN_CALLS)
                if spread is None:
                    empty += 1
                    continue
                collected.setdefault((label, day.year), {}).setdefault(ticker, []).append(spread)
        print(f"  {label:12s} done  ({time.monotonic() - started:.0f}s elapsed)")

    print(f"\ncalls {calls:,}   windows with no two-sided quote: {empty:,} "
          f"({empty / calls:.1%})\n")

    rows: list[dict[str, object]] = []
    print("PER-SIDE SPREAD (S/2), bps - the same quantity DR-005 reports at 25.44")
    print(f"{'window':<13}{'year':>6}{'names':>7}{'p10':>9}{'median':>9}{'p90':>9}"
          f"{'mean':>9}   vs DR-005")
    print("-" * 78)
    for label, _ in WINDOWS:
        for year in sorted(args.years):
            per_ticker = collected.get((label, year))
            if not per_ticker:
                continue
            medians = [Decimal(str(statistics.median(v))) / 2 for v in per_ticker.values()]
            stats = percentiles(medians)
            ratio = DR005_PER_SIDE_BPS / stats["median"] if stats["median"] > 0 else None
            rows.append({
                "window": label, "year": year, "instruments": len(medians),
                **{k: str(round(v, 3)) for k, v in stats.items()},
                "dr005_over_measured": str(round(ratio, 2)) if ratio else None,
            })
            print(f"{label:<13}{year:>6}{len(medians):>7}"
                  f"{float(stats['p10']):>9.2f}{float(stats['median']):>9.2f}"
                  f"{float(stats['p90']):>9.2f}{float(stats['mean']):>9.2f}"
                  f"   {float(ratio):>5.1f}x" if ratio else "")
        print()

    # ---------------------------------------------------------------------------------
    # What the constant is WORTH. The exit surface published a gross expectancy and the R
    # cost of the charged 25 bps together, so the cost at which each result turns is
    # arithmetic on committed numbers rather than a new claim (`AGENTS.md` §10.6 rule 4:
    # a derived fact is derived by a tool, in the same change that introduces it).
    # ---------------------------------------------------------------------------------
    turning_points: list[dict[str, object]] = []
    if args.against.exists():
        surface = json.loads(args.against.read_text(encoding="utf-8"))
        charged = Decimal(str(surface["slippage_bps"])) * 2
        ratified_stop = "2.0"
        cost_r = Decimal(str(surface["cost_in_R"][ratified_stop]))
        subjects = [
            ("buy and hold, no stop, no target",
             Decimal(str(surface["null_buy_and_hold"]["gross"]["mean"]))),
            (f"the ratified cell (stop {ratified_stop} x ATR, target 1R)",
             Decimal(str(surface["cells"][f"stop={ratified_stop},target=1.0"]["gross"]["mean"]))),
        ]
        print("WHAT THE CONSTANT IS WORTH")
        print(f"  `{args.against.name}` charges {charged} bps round trip, which is "
              f"{float(cost_r):.3f}R at a {ratified_stop} x ATR stop.")
        print(f"  {'subject':<44}{'gross R':>9}   {'break-even round trip':>26}")
        for label, gross in subjects:
            point = break_even_round_trip_bps(gross, cost_r, charged)
            turning_points.append({
                "subject": label, "gross_r": str(round(gross, 6)),
                "break_even_round_trip_bps": str(round(point, 2)) if point else None,
                "break_even_per_side_bps": str(round(point / 2, 2)) if point else None,
            })
            shown = f"{float(point):.1f} bps ({float(point) / 2:.1f} per side)" \
                if point else "never - it loses gross"
            print(f"  {label:<44}{float(gross):>+9.3f}   {shown:>26}")
        print()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "as_of": as_of.isoformat(),
        # The store's knowledge date, not a wall clock: this file must be reproducible from the
        # same store on any machine and on any day (`REQ-DATA-001`).
        "measured_as_of": as_of.date().isoformat(),
        "population": {
            "rebuilt_per_date": True,
            "seed": args.seed,
            "by_date": {
                day.isoformat(): {
                    "admissible": len(by_date[day]), "sampled": len(drawn_by_date[day]),
                } for day in days
            },
            "liquidity_rule": {
                "min_price": str(MIN_PRICE), "min_adtv": str(MIN_ADTV),
                "adtv_window": ADTV_WINDOW, "min_history": MIN_HISTORY, "adtv_lag": ADTV_LAG,
            },
        },
        "convention": "S = (ask - bid) / mid, per side = S/2, identical to DR-005",
        "source": "consolidated SIP NBBO via the venue's market-data host, free tier",
        "dates": [d.isoformat() for d in days],
        "quotes_per_window": QUOTES_PER_WINDOW,
        "dr005_per_side_bps": str(DR005_PER_SIDE_BPS),
        "empty_windows": empty,
        "calls": calls,
        "rows": rows,
        "priced_against": str(args.against),
        "turning_points": turning_points,
        "not_measured": [
            "market impact - this is top of book and says nothing about depth",
            "the cost of a PASSIVE fill; a resting limit that fills has crossed nothing",
            "realised effective spread, which price improvement can put below the quote",
        ],
    }, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
