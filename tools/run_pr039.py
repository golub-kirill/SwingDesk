"""PR-039: does a hold that spans a results announcement jump the stop more often - and what would
avoiding it cost?

Reads two committed things and fetches nothing: `PR-016`'s seeded trade sample (the ratified exit,
so every trade carries its `exit_reason`, and `stop_gap` is the session opening THROUGH the stop),
and the announcement calendar `tools/fetch_earnings_dates.py` read from SEC EDGAR for the same names
(`results/PR-039-announcements.csv`, `results/PR-039-coverage.csv`).

**A trade is EXPOSED when an announcement's price impact lands while it is held.** The impact
session comes from the instant EDGAR accepted the Item 2.02 8-K, in New York time: before the open
of a session day, that session's OPEN; during the session, that session INTRADAY; after the close
or on a closed day, the NEXT session's open. An open impact on the entry day was already in the
entry price, so it does not expose the trade; one on any later day through the exit does. An
intraday impact exposes any day of the hold, the entry day included.

    PYTHONPATH=$PWD/src python tools/run_pr037.py --count     # sample sizes only, no outcome read
    PYTHONPATH=$PWD/src python tools/run_pr037.py --power     # the widths, labels permuted
    PYTHONPATH=$PWD/src python tools/run_pr037.py             # the registered run
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from swingdesk.contracts.reference import Exchange
from swingdesk.reference_data import calendar as cal

RESULTS = REPO / "docs" / "prereg" / "results"
TRADES = RESULTS / "PR-016-trades-sample.csv"
CALENDAR = RESULTS / "PR-039-announcements.csv"
COVERAGE = RESULTS / "PR-039-coverage.csv"

#: `PR-016`'s arms at ONE times costs. The `_3x` arms are the same entries costed three times over
#: and would count a trade twice; the exit and the gap do not depend on the cost.
POOL_ARMS = ("ranked", "ranked_top4", "unselected", "unselected_two_slot")
#: The arm that IS `CARD-001` as it trades: the four-name book (`DR-030`).
CARD_ARM = "ranked_top4"

NEW_YORK = ZoneInfo("America/New_York")
SEED = 20260927
RESAMPLES = 10_000
BLOCK = 3

#: Registered in the pre-registration's section 8; below any of them the run refuses.
MIN_POOL = 600
MIN_EXPOSED = 100
MIN_COVERAGE = 0.80


@dataclass(frozen=True, slots=True)
class Trade:
    arm: str
    instrument_id: str
    entry_date: date
    exit_date: date
    exit_reason: str
    net_r: float

    @property
    def month(self) -> str:
        return f"{self.entry_date:%Y-%m}"

    @property
    def gapped(self) -> bool:
        return self.exit_reason == "stop_gap"


def load_trades(path: Path = TRADES) -> list[Trade]:
    with path.open(encoding="utf-8") as handle:
        return [Trade(row["arm"], row["instrument_id"], date.fromisoformat(row["entry_date"]),
                      date.fromisoformat(row["exit_date"]), row["exit_reason"],
                      float(row["net_r"]))
                for row in csv.DictReader(handle)]


def pool(trades: Sequence[Trade]) -> list[Trade]:
    """The one-times-cost arms, each distinct trade once - arms sampled the same trade sometimes."""
    seen: set[tuple[str, date, date]] = set()
    out = []
    for trade in trades:
        key = (trade.instrument_id, trade.entry_date, trade.exit_date)
        if trade.arm in POOL_ARMS and key not in seen:
            seen.add(key)
            out.append(trade)
    return out


def coverage(path: Path = COVERAGE) -> dict[str, str]:
    """Each symbol's bucket rule input: `dated` (a company with results on file), `fund`, `unknown`.

    Only an ETF, by the project's own symbol directory, is a fund. A registrant with no Item 2.02
    8-K is NOT assumed to have no results: most are foreign issuers reporting on Form 6-K, which
    carries no item codes, so their results exist and cannot be dated here.
    """
    with path.open(encoding="utf-8") as handle:
        return {row["symbol"]: ("dated" if row["status"] == "with_announcements"
                                else "fund" if row.get("is_etf") == "true" else "unknown")
                for row in csv.DictReader(handle)}


def impacts(path: Path = CALENDAR) -> dict[str, list[tuple[date, str]]]:
    """Each symbol's announcement impacts: the session and whether it lands at the open or intraday."""
    out: dict[str, list[tuple[date, str]]] = defaultdict(list)
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            accepted = datetime.fromisoformat(row["accepted"].replace("Z", "+00:00"))
            out[row["symbol"]].append(impact(accepted))
    return out


def impact(accepted: datetime) -> tuple[date, str]:
    """The session an announcement accepted at `accepted` first moves, and how."""
    local = accepted.astimezone(NEW_YORK)
    today = cal.session(Exchange.NYSE, local.date())
    if today is not None and local < today.open_time:
        return today.session_date, "open"
    if today is not None and local < today.close_time:
        return today.session_date, "intraday"
    nxt = cal.sessions(Exchange.NYSE, local.date() + timedelta(days=1),
                       local.date() + timedelta(days=12))[0]
    return nxt.session_date, "open"


def exposed(trade: Trade, dates: Sequence[tuple[date, str]]) -> bool:
    for session, kind in dates:
        if kind == "open" and trade.entry_date < session <= trade.exit_date:
            return True
        if kind == "intraday" and trade.entry_date <= session <= trade.exit_date:
            return True
    return False


def split(trades: Sequence[Trade], status: dict[str, str],
          calendar: dict[str, list[tuple[date, str]]]) -> dict[str, list[Trade]]:
    """Every trade in exactly one bucket: a company's exposed or unexposed hold, a fund, unknown."""
    buckets: dict[str, list[Trade]] = {"exposed": [], "unexposed": [], "fund": [], "unknown": []}
    for trade in trades:
        kind = status.get(trade.instrument_id, "unknown")
        if kind == "dated":
            bucket = "exposed" if exposed(trade, calendar[trade.instrument_id]) else "unexposed"
        else:
            bucket = kind
        buckets[bucket].append(trade)
    return buckets


# ------------------------------------------------------------------ the statistics


def gap_rate(trades: Sequence[Trade]) -> float:
    return sum(t.gapped for t in trades) / len(trades) if trades else float("nan")


def mean_r(trades: Sequence[Trade]) -> float:
    return sum(t.net_r for t in trades) / len(trades) if trades else float("nan")


def difference(stat: Callable[[Sequence[Trade]], float]) -> Callable[[Sequence[tuple[Trade, bool]]], float]:
    """The statistic on the exposed trades minus the same on the unexposed ones."""
    def measure(labelled: Sequence[tuple[Trade, bool]]) -> float:
        return (stat([t for t, e in labelled if e]) - stat([t for t, e in labelled if not e]))
    return measure


def block_bootstrap(labelled: Sequence[tuple[Trade, bool]],
                    measure: Callable[[Sequence[tuple[Trade, bool]]], float],
                    permute: bool = False) -> tuple[float, float, float]:
    """Point, and a 95% moving-block bootstrap over entry months (block `BLOCK`).

    `permute` re-draws the exposure labels inside every resample, at the observed share - the null
    the power estimate needs, which lets the WIDTH out without the difference itself.
    """
    by_month: dict[str, list[tuple[Trade, bool]]] = defaultdict(list)
    for item in labelled:
        by_month[item[0].month].append(item)
    months = sorted(by_month)
    share = sum(e for _, e in labelled) / len(labelled)
    rng = random.Random(SEED)
    draws = []
    for _ in range(RESAMPLES):
        chosen: list[str] = []
        while len(chosen) < len(months):
            start = rng.randrange(len(months) - BLOCK + 1)
            chosen.extend(months[start:start + BLOCK])
        sample = [item for month in chosen[:len(months)] for item in by_month[month]]
        if permute:
            sample = [(t, rng.random() < share) for t, _ in sample]
        draws.append(measure(sample))
    draws.sort()
    point = measure(labelled)
    return point, draws[int(0.025 * RESAMPLES)], draws[int(0.975 * RESAMPLES) - 1]


def loss_shares(buckets: dict[str, list[Trade]]) -> dict[str, dict[str, float]]:
    """How much of the arm's trades, and of its total loss in R, sits in each bucket."""
    total_trades = sum(len(v) for v in buckets.values())
    total_loss = sum(-t.net_r for v in buckets.values() for t in v if t.net_r < 0)
    return {name: {"trades": len(v), "share_of_trades": len(v) / total_trades,
                   "loss_r": sum(-t.net_r for t in v if t.net_r < 0),
                   "share_of_loss": sum(-t.net_r for t in v if t.net_r < 0) / total_loss,
                   "gap_exits": sum(t.gapped for t in v)}
            for name, v in buckets.items()}


# ------------------------------------------------------------------ the run


def inputs() -> tuple[list[Trade], dict[str, list[Trade]], dict[str, list[Trade]]]:
    trades = load_trades()
    status, calendar = coverage(), impacts()
    return trades, split(pool(trades), status, calendar), \
        split([t for t in trades if t.arm == CARD_ARM], status, calendar)


def counts() -> dict[str, object]:
    """Sample sizes and coverage. Reads no outcome - `exit_reason` and `net_r` are untouched."""
    trades, pooled, card = inputs()
    known = len(pooled["exposed"]) + len(pooled["unexposed"]) + len(pooled["fund"])
    total = sum(len(v) for v in pooled.values())
    return {"pool": {k: len(v) for k, v in pooled.items()},
            "card": {k: len(v) for k, v in card.items()},
            "coverage_of_pool": known / total,
            "months": len({t.month for v in pooled.values() for t in v}),
            "span": [str(min(t.entry_date for t in trades)), str(max(t.entry_date for t in trades))],
            "arms": dict(Counter(t.arm for t in trades))}


def power() -> dict[str, object]:
    """The widths the registered statistics will have, from permuted labels - no split is read."""
    _, pooled, _ = inputs()
    labelled = [(t, True) for t in pooled["exposed"]] + [(t, False) for t in pooled["unexposed"]]
    out: dict[str, object] = {"prereg": "PR-039", "trials": 0, "resamples": RESAMPLES,
                              "block": BLOCK, "seed": SEED}
    for name, stat in (("gap_rate_difference", gap_rate), ("mean_r_difference", mean_r)):
        _, low, high = block_bootstrap(labelled, difference(stat), permute=True)
        out[name] = {"null_low": low, "null_high": high, "half_width": (high - low) / 2,
                     "minimum_detectable": (high - low) / 2 * (1.96 + 0.84) / 1.96}
    return out


def verdict(pooled: dict[str, list[Trade]], gap: tuple[float, float, float],
            mean: tuple[float, float, float], mde: float) -> tuple[str, str]:
    """Section 6 of the pre-registration, in its order.

    `NULL` is an interval that contains zero AND rules out the registered minimum detectable effect;
    one that contains zero and reaches past it is `INCONCLUSIVE` - it could not see the effect.
    """
    total = sum(len(v) for v in pooled.values())
    known = total - len(pooled["unknown"])
    if (len(pooled["exposed"]) + len(pooled["unexposed"]) < MIN_POOL
            or len(pooled["exposed"]) < MIN_EXPOSED or known / total < MIN_COVERAGE):
        return "refused", "REFUSED"
    _, gap_low, gap_high = gap
    _, mean_low, mean_high = mean
    if gap_low > 0:
        if mean_high < 0:
            return "accept", "FILTER_HELPS"
        if mean_low > 0:
            return "accept", "FILTER_COSTS"
        return "accept", "RISK_ONLY"
    if gap_high < 0:
        return "reject", "REJECT"
    return "inconclusive", "NULL" if gap_high < mde else "INCONCLUSIVE"


def run() -> dict[str, object]:
    _trades, pooled, card = inputs()
    labelled = [(t, True) for t in pooled["exposed"]] + [(t, False) for t in pooled["unexposed"]]
    gap = block_bootstrap(labelled, difference(gap_rate))
    mean = block_bootstrap(labelled, difference(mean_r))
    registered = json.loads((RESULTS / "PR-039-power.json").read_text(encoding="utf-8"))
    mde = registered["gap_rate_difference"]["minimum_detectable"]
    result_verdict, branch = verdict(pooled, gap, mean, mde)
    everything = [t for v in pooled.values() for t in v]
    first, last = min(t.entry_date for t in everything), max(t.entry_date for t in everything)
    exposed_share = len(pooled["exposed"]) / (len(pooled["exposed"]) + len(pooled["unexposed"]))
    return {
        "prereg": "PR-039", "trials": 1, "verdict": result_verdict, "branch": branch,
        "country": "USA", "as_of": {"trades": "PR-016-trades-sample.csv (committed)",
                                    "calendar": "PR-039-announcements.csv (committed)"},
        "measured_span": {"first_session": str(first), "last_session": str(last),
                          "years": round((last - first).days / 365.25, 2)},
        "split": {"registered": "none - exposed against unexposed holds of one committed sample",
                  "buys": "nothing a split could buy: no constant is chosen here"},
        "perturbations": {"registered": [], "run": []},
        "registered_settings": {"arms": list(POOL_ARMS), "card_arm": CARD_ARM,
                                "primary": "stop_gap rate, exposed minus unexposed",
                                "bootstrap": {"unit": "entry month", "block": BLOCK,
                                              "seed": SEED, "resamples": RESAMPLES},
                                "minimum_detectable": mde, "min_pool": MIN_POOL,
                                "min_exposed": MIN_EXPOSED, "min_coverage": MIN_COVERAGE},
        "slot_check": slot_check(),
        "counts": {k: len(v) for k, v in pooled.items()},
        "primary_gap_rate": {"exposed": gap_rate(pooled["exposed"]),
                             "unexposed": gap_rate(pooled["unexposed"]),
                             "difference": gap[0], "low": gap[1], "high": gap[2]},
        "secondary_mean_net_r": {"exposed": mean_r(pooled["exposed"]),
                                 "unexposed": mean_r(pooled["unexposed"]),
                                 "difference": mean[0], "low": mean[1], "high": mean[2]},
        "the_filter": {"exposed_share_of_company_trades": exposed_share,
                       "book_mean_r_all": mean_r(pooled["exposed"] + pooled["unexposed"]),
                       "book_mean_r_filtered": mean_r(pooled["unexposed"])},
        "card_001_loss_shares": loss_shares(card),
        "pool_loss_shares": loss_shares(pooled),
    }


def slot_check(path: Path = CALENDAR) -> dict[str, object]:
    """Section 9's check on the calendar itself: where the acceptance instants fall.

    Results are released outside the session almost always, so if the 8-K's acceptance tracks the
    release, intraday impacts are a small minority. A large intraday share would mean the filing
    instant is not the release instant, and the exposure rule would be reading the wrong clock.
    """
    kinds: Counter[str] = Counter()
    per_symbol: Counter[str] = Counter()
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            accepted = datetime.fromisoformat(row["accepted"].replace("Z", "+00:00"))
            if accepted.year >= 2017:
                kinds[impact(accepted)[1]] += 1
                per_symbol[row["symbol"]] += 1
    total = sum(kinds.values())
    per_year = sorted(count / 9.6 for count in per_symbol.values())   # 2017-01 to 2026-08
    return {"announcements_since_2017": total,
            "intraday_share": kinds["intraday"] / total if total else None,
            "median_per_company_per_year": per_year[len(per_year) // 2] if per_year else None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--count", action="store_true", help="sample sizes only; no outcome is read")
    mode.add_argument("--power", action="store_true", help="write the registered widths")
    args = parser.parse_args()
    if args.count:
        print(json.dumps(counts(), indent=2))
        return 0
    if args.power:
        widths = power()
        (RESULTS / "PR-039-power.json").write_text(json.dumps(widths, indent=2) + "\n",
                                                   encoding="utf-8")
        print(json.dumps(widths, indent=2))
        return 0
    result = run()
    (RESULTS / "PR-039.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
