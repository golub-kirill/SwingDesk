"""How clean is the delisted universe, before anybody spends hours fetching it?

**The repair `DR-047` §3.9 requires is a fetch, and this is the measurement that must precede it.**
`BACKTEST_PROTOCOL` §6 records that Alpaca serves 19,188 inactive US equity assets and returned a
full daily path for every delisted name probed. What it does NOT record is whether those paths mean
what a study would read them as - and one hazard is structural rather than incidental.

**A ticker is not an identity.** Alpaca gives every asset a UUID; the bars endpoint is keyed by
SYMBOL. So when a ticker is retired and later reissued to a different company, one request returns
one series spliced out of two businesses. `tools/probe_alpaca_delisted.py` walked into exactly that
on 2026-09-21: `SEMG` returned 1,147 daily bars running 2016-01-04 to 2025-12-30, and SemGroup was
acquired in 2019. **A momentum study reading that series would rank a company against its own
successor's prices.**

So this counts the hazard before the fetch is designed around it:

* how many inactive assets there are, and how many sit on a real exchange;
* **how many SYMBOLS are claimed by more than one inactive asset**;
* **how many inactive symbols collide with an asset that is still ACTIVE today**, which is the
  worse case - the live company's prices would be spliced onto a dead one's;
* what share of the universe is clean, which is what a study would actually get.

**It also settles what `BACKTEST_PROTOCOL` §6 calls the first thing to settle.** The probe could not
say whether SIP historical data is a free-tier entitlement or an attribute of this account. Alpaca's
own subscription table answers it: the **Basic** plan, the default for both paper and live accounts,
is free and carries *"Historical data timeframe: Since 2016"*, a restriction only on *"the latest 15
minutes"*, and **200 historical API calls a minute**. Read 2026-09-21. So the entitlement is the
free tier's, the 2016 floor is everybody's, and **200 a minute is the pace any repair must hold**.

    python tools/measure_delisted_universe.py

Read-only: GET only, no write verb, no order, no account mutation. Needs `APCA_API_KEY_ID` and
`APCA_API_SECRET_KEY`; reports UNAVAILABLE without them. Network tool, never run in CI
(`CI_POLICY` §4).
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]

ASSETS = "https://paper-api.alpaca.markets/v2/assets"
OUT = REPO / "docs" / "decisions" / "measurements" / "delisted-universe-2026-09-21.json"

#: The exchanges a study would actually trade on. `probe_alpaca_delisted.py` uses the same set, and
#: it is the same reason: an OTC stub is not a name any rule here would have bought.
REAL_EXCHANGES = {"NASDAQ", "NYSE", "ARCA", "AMEX"}

#: Alpaca's Basic plan, read from their subscription table on 2026-09-21. Recorded as constants
#: because the repair's pace and its earliest possible window both follow from them, and a number
#: living only in a docstring is a number nothing can check.
BASIC_CALLS_PER_MINUTE = 200
BASIC_HISTORY_FROM = "2016-01-01"

UNAVAILABLE = 4

Getter = Callable[[str], tuple[int, object]]


def get(url: str) -> tuple[int, object]:
    """One GET. A non-200 is returned rather than raised - a measurement reports, it does not die."""
    headers = {
        "APCA-API-KEY-ID": os.environ.get("APCA_API_KEY_ID", ""),
        "APCA-API-SECRET-KEY": os.environ.get("APCA_API_SECRET_KEY", ""),
        "User-Agent": "SwingDesk-measure-universe/1.0",
    }
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")[:300]
    except Exception as error:  # noqa: BLE001 - the message is the point
        return -1, f"{type(error).__name__}: {error}"


def listed(assets: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assets on a real exchange with an alphabetic symbol - what a study could have traded."""
    return [a for a in assets
            if a.get("exchange") in REAL_EXCHANGES and str(a.get("symbol", "")).isalpha()]


def ambiguity(inactive: Sequence[dict[str, Any]],
              active: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Which symbols cannot be fetched as one company, and how many assets they cost.

    Two shapes, and the second is the dangerous one:

    * **reissued among the dead** - one ticker, several inactive assets. A single bars request
      splices them, and nothing in the response says where one ends;
    * **reissued to the living** - a dead company's ticker now belongs to a listed one. Here the
      splice reaches all the way to today, so the dead name appears to have survived, which is the
      survivorship bias this repair exists to remove, reintroduced by the repair itself.
    """
    dead_by_symbol: dict[str, list[str]] = defaultdict(list)
    for asset in inactive:
        dead_by_symbol[str(asset["symbol"])].append(str(asset.get("id", "")))
    live = {str(asset["symbol"]) for asset in active}

    reissued_among_dead = {s: ids for s, ids in dead_by_symbol.items() if len(ids) > 1}
    reissued_to_living = sorted(s for s in dead_by_symbol if s in live)
    ambiguous = set(reissued_among_dead) | set(reissued_to_living)
    clean = [s for s in dead_by_symbol if s not in ambiguous]
    return {
        "distinct_symbols": len(dead_by_symbol),
        "reissued_among_the_dead": len(reissued_among_dead),
        "reissued_to_a_living_asset": len(reissued_to_living),
        "ambiguous_symbols": len(ambiguous),
        "clean_symbols": len(clean),
        "clean_share": len(clean) / len(dead_by_symbol) if dead_by_symbol else 0.0,
        "examples_reissued_to_living": reissued_to_living[:12],
        "examples_reissued_among_dead": sorted(reissued_among_dead)[:12],
    }


def measure(getter: Getter = get) -> dict[str, Any] | None:
    status, inactive_body = getter(f"{ASSETS}?status=inactive&asset_class=us_equity")
    if status != 200 or not isinstance(inactive_body, list):
        print(f"delisted universe: UNAVAILABLE - assets returned {status}: {str(inactive_body)[:120]}")
        return None
    status, active_body = getter(f"{ASSETS}?status=active&asset_class=us_equity")
    if status != 200 or not isinstance(active_body, list):
        print(f"delisted universe: UNAVAILABLE - active assets returned {status}")
        return None

    dead, live = listed(inactive_body), listed(active_body)
    exchanges = Counter(str(a.get("exchange")) for a in dead)
    return {
        "measured": "2026-09-21",
        "asked_by": "Claude, before designing the survivorship repair DR-047 3.9 requires - a "
                    "multi-hour fetch whose shape depends on how many tickers mean one company",
        "exploratory": True,
        "trials": 0,
        "why_no_trial": "it counts ASSETS and SYMBOLS. No return is read, no rule is evaluated and "
                        "nothing is selected on performance",
        "tool": "tools/measure_delisted_universe.py",
        "inactive_us_equity_assets": len(inactive_body),
        "inactive_on_a_real_exchange": len(dead),
        "active_on_a_real_exchange": len(live),
        "by_exchange": dict(exchanges.most_common()),
        "ambiguity": ambiguity(dead, live),
        "limits": {
            "completeness_NOT_established": "this is Alpaca's own inactive list, and how much of "
                                            "the real delisting record it holds is unmeasured. "
                                            "1,973 names on a major exchange over a decade is "
                                            "lower than the usual count of US delistings, which "
                                            "is consistent with a vendor that keeps only assets it "
                                            "ever listed. tools/probe_edgar.py established that "
                                            "the FACT and DATE of a delisting are free and "
                                            "official from SEC EDGAR, so this completeness is "
                                            "MEASURABLE and unmeasured - the same sentence "
                                            "BACKTEST_PROTOCOL 6 uses about the bias itself",
            "what_the_filter_actually_does": "it keeps symbols that are purely alphabetic on a "
                                             "major exchange. That is NOT the same as keeping "
                                             "common stock: SPAC units and warrants whose tickers "
                                             "happen to be all letters pass it - APXTU, ASPCU, "
                                             "HYACU and MUDSU are units and SLGCW is a warrant, "
                                             "and all five are in this measurement's own example "
                                             "lists. It also DROPS share classes spelled with a "
                                             "dot, which a study would have wanted. So a repair "
                                             "needs a further instrument-kind filter, and this "
                                             "count is an upper bound on the tradable names "
                                             "rather than the names themselves",
            "what_a_repair_would_still_carry": "a study reading the repaired universe removes the "
                                               "bias from the names Alpaca remembers, and cannot "
                                               "state what it removes from the ones it does not. "
                                               "That is a smaller claim than survivorship: "
                                               "REPAIRED and has to be written as the smaller one",
        },
        "vendor_plan": {
            "read": "https://docs.alpaca.markets/docs/about-market-data-api, 2026-09-21",
            "plan": "Basic - the default for both paper and live trading accounts, free",
            "historical_timeframe": "since 2016",
            "historical_limitation": "the latest 15 minutes",
            "historical_calls_per_minute": BASIC_CALLS_PER_MINUTE,
            "settles": "BACKTEST_PROTOCOL 6's limit 1 - SIP historical is a FREE-TIER entitlement, "
                       "not an attribute of this account. The 2016 floor binds everybody on Basic, "
                       "and 200 calls a minute is the pace the repair must hold",
        },
    }


def report(payload: dict[str, Any]) -> None:
    amb = payload["ambiguity"]
    print(f"inactive US equity assets           : {payload['inactive_us_equity_assets']:,}")
    print(f"  on a real exchange                : {payload['inactive_on_a_real_exchange']:,}")
    print(f"  distinct symbols among them       : {amb['distinct_symbols']:,}")
    print(f"  reissued among the dead           : {amb['reissued_among_the_dead']:,}")
    print(f"  reissued to a LIVING asset        : {amb['reissued_to_a_living_asset']:,}")
    print(f"  -> ambiguous symbols              : {amb['ambiguous_symbols']:,}")
    print(f"  -> clean, one company each        : {amb['clean_symbols']:,}"
          f"  ({100 * amb['clean_share']:.1f}%)")
    if amb["examples_reissued_to_living"]:
        print(f"  dead tickers now alive, e.g.      : "
              f"{', '.join(amb['examples_reissued_to_living'][:8])}")
    pace = payload["vendor_plan"]["historical_calls_per_minute"]
    minutes = amb["clean_symbols"] / pace if pace else 0
    print(f"  a fetch of the clean names, at {pace}/min, is at least {minutes:.0f} minutes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    parser.parse_args(argv)
    payload = measure()
    if payload is None:
        return UNAVAILABLE
    payload["as_of"] = datetime.now(UTC).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report(payload)
    print(f"  written to {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - the entry point
    raise SystemExit(main())
