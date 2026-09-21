"""Is `PR-034`'s overnight return skill, or is it factor exposure this project could have bought?

**The first thing `DR-049`'s rule was pointed at, and it was pointed at our own best result.**
`PR-034` returned `ACCEPT`: the `IJR`+`VB` night earns 13.8% a year at a Sharpe ratio of 1.06
against holding the same funds' 0.59, and `EVIDENCE_SUMMARY` §32 calls it the first result here to
beat holding the asset per unit of risk. `DR-047` §3.4's fourth curve - `SPY` matched to the
strategy's own volatility - was the strongest test it faced, and that curve only knows about the
MARKET.

This regresses the arm's daily returns on six factors and reports what is left:

    r_night - RF  =  alpha + b*(Mkt-RF) + b*SMB + b*HML + b*RMW + b*CMA + b*MOM + e

**Exploratory, zero trials.** It evaluates no configuration and selects nothing: it re-reads a
result already reported, under a lens the registration did not carry, which is what
`tools/attribute_pr034.py` did for the year-by-year reading and what `AGENTS.md` permits as long as
the label says so.

**One property of the data that a reader must hold**, because it changes what a beta means here: a
factor day runs close to close, and the night arm is the part of it that runs close to NEXT OPEN.
So the night is a SUBSET of the factor period, and a market beta of 0.44 is not leverage - it says
the night captures 44% of the market's daily move. The alpha is still an alpha: it is what the six
factors do not explain over the same days.

    PYTHONPATH=$PWD/src python tools/measure_overnight_factors.py --data <bars> --factors <dir>

Network-free. Reads two stored files and writes one measurement.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import factor_attribution as fa
import run_pr033 as p33
import run_pr036 as p36
from swingdesk.market_data import BarStore

OUT = REPO / "docs" / "decisions" / "measurements" / "overnight-factor-alpha-2026-09-21.json"

#: `PR-034`'s own window, and the one `PR-036` read. Named rather than derived so the measurement
#: says which study each row is about.
WINDOWS = (
    ("PR-034 window", p36.OVERLAP_FIRST, p36.OVERLAP_LAST),
    ("PR-036 window", p36.BEFORE_FIRST, p36.BEFORE_LAST),
)

#: 252 sessions a year, the same convention `run_pr031.described` annualises with.
SESSIONS_A_YEAR = 252


def arms(store: BarStore, as_of: datetime) -> dict[str, dict[str, dict[date, float]]]:
    """Each fund's night, session and holding series from the stored daily bars."""
    out: dict[str, dict[str, dict[date, float]]] = {"night": {}, "session": {}, "hold": {}}
    for fund in p36.FUNDS:
        night, session, held = p33.returns_of(p36.sessions_from_bars(store, fund, as_of), 0.005)
        out["night"][fund], out["session"][fund], out["hold"][fund] = night, session, held
    return out


def basket(by_fund: dict[str, dict[date, float]], first: date, last: date) -> dict[date, float]:
    """Equal capital across the funds, inside one window.

    **Both ends are applied here.** `run_pr033.basket_of` takes a `since` and no `until`, and the
    first reading of this measurement labelled a series "2004-2015" while it silently carried
    `IJR` alone back to 2000 - the fund trades from then and the mean is taken over whatever funds
    read a session. The window is the caller's claim, so the caller closes it.
    """
    return {day: value for day, value in p33.basket_of(by_fund, first).items() if day <= last}


def measure(args: argparse.Namespace) -> dict[str, Any]:
    store = BarStore(args.data / "bars.duckdb")
    try:
        as_of = (datetime.fromisoformat(args.as_of) if args.as_of
                 else store.latest_knowledge_time())
        if as_of is None:
            raise ValueError("the bar store holds no knowledge instant")
        series = arms(store, as_of)
    finally:
        store.close()

    factors = fa.load(args.factors / "factors-daily.csv")
    rows: dict[str, Any] = {}
    for label, first, last in WINDOWS:
        for arm in ("night", "session", "hold"):
            values = basket(series[arm], first, last)
            if len(values) < 100:
                continue
            found = fa.attribute(values, factors, SESSIONS_A_YEAR)
            rows[f"{arm} | {label}"] = {
                "sessions_in_window": len(values),
                "window_claimed": [first.isoformat(), last.isoformat()],
                **found.as_dict(),
            }
    return {
        "measured": "2026-09-21",
        "asked_by": "the owner, 2026-09-21 - 'factor / beta attribution' was the stage of their "
                    "research chain DR-047 did not cover",
        "exploratory": True,
        "trials": 0,
        "why_no_trial": "it re-reads a reported result under a lens the registration did not "
                        "carry. No configuration is evaluated and nothing is selected",
        "tool": "tools/measure_overnight_factors.py",
        "factors": list(fa.FACTORS),
        "factor_source": "Kenneth French's data library, five factors plus momentum, daily",
        "as_of": {"bars": as_of.isoformat(), "measured_at": datetime.now(UTC).isoformat()},
        "rows": rows,
        "limits": {
            "the_night_is_a_SUBSET_of_the_factor_day": "a factor day is close to close and the "
                                                       "night is close to next open, so a market "
                                                       "beta of 0.44 says the night captures 44% "
                                                       "of the day's move - it is not leverage",
            "the_library_ends_early": "French's series stop about two months behind the present, "
                                      "so the last sessions of a current window are not "
                                      "attributed. The row's `periods` is what was regressed and "
                                      "`sessions_in_window` is what the window held",
            "six_factors_are_not_every_factor": "an alpha that survives these six is not an alpha "
                                                "that survives all of them - liquidity, betting "
                                                "against beta and quality are not here",
            "daily_bars_not_minutes": "PR-034 measured on minute prices and this reads daily "
                                      "bars. PR-036 checked the two against each other and they "
                                      "agreed within 0.57 points a year",
        },
    }


def report(payload: dict[str, Any]) -> None:
    print(f"overnight factor attribution   factors {', '.join(payload['factors'])}")
    for name, row in payload["rows"].items():
        verdict = "SURVIVES" if row["alpha_survives"] else "does NOT survive"
        print(f"  {name:26s} {row['periods']:>5} periods  {row['first']} .. {row['last']}")
        print(f"      alpha {100 * row['alpha_annual']:+7.2f}% a year   t {row['alpha_t']:+5.2f}"
              f"   -> {verdict}   R2 {row['r_squared']:.3f}")
        print("      " + "  ".join(f"{k} {v:+.2f}" for k, v in row["betas"].items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True, help="a store holding IJR and VB bars")
    parser.add_argument("--factors", type=Path, required=True, help="where factors-daily.csv is")
    parser.add_argument("--as-of", help="the bar store's knowledge instant")
    args = parser.parse_args(argv)
    payload = measure(args)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report(payload)
    print(f"  written to {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - the entry point
    raise SystemExit(main())
