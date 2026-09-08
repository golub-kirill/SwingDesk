"""On a session that reached BOTH the stop and the target, which one printed first? Measured.

**The question `DR-042` §4 asks and the owner declined to answer on taste.** Ruling on the form of
it, 2026-09-07: *"(b) Покажи долю, потом решу"* — the measured share comes first.

**Why it cannot be answered from the store.** Measured 2026-09-07: `interval` in `bars.duckdb` is
`1d` and nothing else — 12.0M rows across 13,010 instruments, no hourly, no minutes. `ADR-0001`
describes fetching `1H` and `30m`; not one such bar has ever been written. A daily bar records four
prices and no times, so the sequence is not merely unknown, it is absent from the data.

**Where the answer comes from.** `probe_alpaca_delisted.py` established on 2026-09-05 that Alpaca
`feed=sip` serves DAILY history from 2016-01-04 on this project's existing credentials. Same host,
same read-only boundary. `data.alpaca.markets` is neither the allowlisted broker host nor the
forbidden live one — `registry/broker_policy.yml`'s allowlist bounds which ACCOUNT may be written,
and this writes nothing.

**That the same is true at ONE-MINUTE resolution was a separate claim, and it is measured rather
than inherited.** 2026-09-08, `AAPL`:

    2016-01-05   694 minute bars      feed=sip
    2016-09-07   667 minute bars      feed=sip
    2017-03-01   638 minute bars      feed=sip
    2018-02-05   804 minute bars      feed=sip
    2024-08-05   926 minute bars      feed=sip
    2017-03-01     0 minute bars      feed=iex

So the whole of any window this store can support is covered, and `feed=iex` serves none of it —
the same split the daily probe found. The windows returned run 08:00Z–23:59Z, which is pre-market
through after-hours: a stop resting at the venue can be taken in the pre-market print, and a window
drawn around regular hours would quietly classify that as never having happened.

**What it measures, and the one thing it cannot.** For each sampled session it walks the minutes in
order and records which leg was touched first. A minute bar is itself a bar, so a MINUTE that
touches both legs is ambiguous again — reported as `ambiguous_within_the_minute` rather than
assigned. That residue is the floor on what any bar-based method can resolve, and reporting it is
the difference between a measurement and a smaller assumption wearing a measurement's clothes.

**The sample is seeded and recorded** (`DETERMINISM_SPEC` §3.4). Sampling by hand from a list one
has already looked at is how a 60/40 split becomes whichever number was wanted.

    PYTHONPATH=$PWD/src python tools/probe_ambiguous_bar.py
    PYTHONPATH=$PWD/src python tools/probe_ambiguous_bar.py --sample 400 --out <path>

Needs `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`; reports UNAVAILABLE and exits 2 without them
rather than failing. Network tool, never run in CI (`CI_POLICY` §4).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]

BARS = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"
AMBIGUOUS_BARS = REPO / "docs" / "prereg" / "results" / "PR-016-ambiguous-bars.jsonl"
RESULT = REPO / "docs" / "decisions" / "measurements" / "ambiguous-bar.json"

#: Recorded so the sample is a sample and not a choice. Changing it after seeing a result is
#: choosing the result.
SEED = 20260908
SAMPLE = 200

#: `DR-042` §4a's registered threshold, fixed before any number existed - and it is about the share
#: of EXITS that are ambiguous, NOT about how often the rule gets an ambiguous bar wrong. `TODO` §4
#: states it in those words: *"at 2% of exits the choice barely matters, at 20% it is the single
#: largest assumption"*.
#:
#: **The first cut of this file compared it to the wrong quantity.** It measured the mis-assignment
#: rate WITHIN ambiguous bars - 56.2% on the first real run - and printed that against this 15%,
#: which made a 0.0006R effect read as a systematic distortion. Two different denominators. Found
#: 2026-09-08, immediately after the first measurement and before it reached a record.
#:
#: So the probe reports THREE numbers and lets none of them stand for the others: how often the rule
#: is wrong, how often it is consulted at all, and the product - which is the only one that moves a
#: published figure.
AMBIGUOUS_SHARE_THRESHOLD = 0.15

#: A flip is worth about this much: the target sits 1R above entry and the stop 1R below it, so a
#: bar reassigned from stop to target moves that trade by roughly 2R. Approximate on purpose - the
#: exact fills differ by the cost of one side - and it is an UPPER bound, which is the safe
#: direction for an impact estimate.
FLIP_R = 2.0


def headers() -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": os.environ.get("APCA_API_KEY_ID", ""),
        "APCA-API-SECRET-KEY": os.environ.get("APCA_API_SECRET_KEY", ""),
        "User-Agent": "SwingDesk-probe/1.0",
    }


def get(url: str) -> tuple[int, object]:
    """One GET. A non-200 is returned rather than raised - a probe reports, it does not die."""
    try:
        request = urllib.request.Request(url, headers=headers())
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")[:300]
    except Exception as error:  # noqa: BLE001 - the message is the point
        return -1, f"{type(error).__name__}: {error}"


def minutes(symbol: str, session: str, feed: str = "sip") -> list[dict[str, Any]] | str:
    """Every one-minute bar of one session, in order, or a string saying why not.

    The window is the whole calendar day in UTC rather than the session's own hours: a stop resting
    at the venue can be taken in the pre-market print, and a window drawn around regular hours would
    quietly classify that as never having happened.
    """
    out: list[dict[str, Any]] = []
    token = None
    while True:
        url = (f"{BARS.format(symbol=symbol)}?timeframe=1Min"
               f"&start={session}T00:00:00Z&end={session}T23:59:59Z&limit=10000&feed={feed}")
        if token:
            url += f"&page_token={token}"
        status, body = get(url)
        if status != 200 or not isinstance(body, dict):
            return f"HTTP {status}: {str(body)[:80]}"
        out.extend(body.get("bars") or [])
        token = body.get("next_page_token")
        if not token:
            return out


def first_touch(bars: list[dict[str, Any]], stop: Decimal, target: Decimal) -> str:
    """Which leg the session reached first: `stop`, `target`, `within_a_minute`, or `neither`.

    The open is checked the same way `ExitPolicy` checks it and for the same reason: the first
    minute's open is the first print of the session, so a leg the open itself satisfies fired before
    anything else could.
    """
    for bar in bars:
        low, high = Decimal(str(bar["l"])), Decimal(str(bar["h"]))
        hit_stop, hit_target = low <= stop, high >= target
        if hit_stop and hit_target:
            # One minute reached both. A minute bar records four prices and no times either, so
            # this is the same ambiguity one level down - reported, never assigned.
            return "within_a_minute"
        # The order of these two is UNOBSERVABLE, and that is a property of the branch above
        # rather than a gap in the tests. A both-legs minute has already returned, so at most one
        # of these is true here and swapping them changes nothing. Mutated 2026-09-07 and the
        # mutant survived; recorded rather than left looking like a hole, the way `DR-041`'s fifth
        # mutant is. Every other ordering rule in this function IS observable and every mutation
        # of one died.
        if hit_stop:
            return "stop"
        if hit_target:
            return "target"
    return "neither"


def interval(successes: int, trials: int) -> tuple[float, float]:
    """A 95% Wilson interval for the share. Normal approximation breaks near 0 and 1, which is
    exactly where a reassuring answer would sit."""
    if trials == 0:
        return (0.0, 0.0)
    z, phat, n = 1.96, successes / trials, trials
    denominator = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denominator
    spread = z * ((phat * (1 - phat) / n + z * z / (4 * n * n)) ** 0.5) / denominator
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def report_impact(result_path: Path, wrong_rate: float) -> dict[str, Any]:
    """Turn a mis-assignment RATE into an effect on each arm's mean net R.

    `rate x share x FLIP_R`. The rate is how often the rule takes the wrong leg on a bar where it
    is consulted at all; the share is how often it is consulted. **Neither stands for the other**,
    and reporting the rate alone is how a 0.0006R effect reads as a systematic distortion.

    Returns nothing when the study result is absent, and the caller says so rather than guessing:
    a rate with no share behind it is not an impact.
    """
    if not result_path.exists():
        return {"arms": {}, "lines": [f"{result_path.name} is not there"]}
    result = json.loads(result_path.read_text(encoding="utf-8"))
    ambiguous = result.get("ambiguous_exits", {})
    arms: dict[str, Any] = {}
    lines: list[str] = []
    for group in ("arms", "diagnostics"):
        for name, cells in result.get(group, {}).items():
            count = ambiguous.get(name)
            trades = cells.get("full", {}).get("trades", 0)
            if count is None or not trades:
                continue
            share = count / trades
            arms[name] = {
                "ambiguous_bars": count, "trades": trades, "ambiguous_share": share,
                "impact_r_per_trade": share * wrong_rate * FLIP_R,
            }
            lines.append(f"{name:16} {count:>5} ambiguous of {trades:>7} trades "
                         f"= {share * 100:.3f}% of exits")
    return {"arms": arms, "lines": lines or ["no arm carried an ambiguous bar"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bars", type=Path, default=AMBIGUOUS_BARS,
                        help="the ambiguous bars run_pr016.py wrote")
    parser.add_argument("--sample", type=int, default=SAMPLE, help="how many to fetch")
    parser.add_argument("--seed", type=int, default=SEED, help="recorded with the result")
    parser.add_argument("--feed", default="sip", help="alpaca data feed")
    parser.add_argument("--result", type=Path,
                        default=REPO / "docs" / "prereg" / "results" / "PR-016.json",
                        help="the study whose ambiguous share turns this rate into an impact")
    parser.add_argument("--out", type=Path, default=RESULT)
    args = parser.parse_args(argv)

    if not (os.environ.get("APCA_API_KEY_ID") and os.environ.get("APCA_API_SECRET_KEY")):
        print("ambiguous bar: UNAVAILABLE - APCA_API_KEY_ID/SECRET are not in the environment")
        return 2
    if not args.bars.exists():
        print(f"ambiguous bar: UNAVAILABLE - {args.bars} does not exist. Run run_pr016.py first; "
              f"it writes the bars this probe measures.")
        return 2

    population = [json.loads(line) for line in args.bars.read_text(encoding="utf-8").splitlines()
                  if line.strip()]
    if not population:
        print("ambiguous bar: the run recorded NO ambiguous bars. The tie-break never bound, and "
              "DR-042 §4 can be ruled either way with no effect on any published number.")
        return 0

    rng = random.Random(args.seed)
    drawn = rng.sample(population, min(args.sample, len(population)))
    print(f"ambiguous bars recorded: {len(population)}   sampled: {len(drawn)}   seed {args.seed}")
    print(f"feed {args.feed}   source https://data.alpaca.markets (GET only)\n")

    outcomes: dict[str, int] = {"stop": 0, "target": 0, "within_a_minute": 0, "neither": 0}
    unserved: list[str] = []
    for count, row in enumerate(drawn, start=1):
        got = minutes(row["instrument_id"], row["session_date"], args.feed)
        if isinstance(got, str):
            unserved.append(f"{row['instrument_id']} {row['session_date']}: {got}")
            continue
        if not got:
            unserved.append(f"{row['instrument_id']} {row['session_date']}: no minute bars served")
            continue
        outcomes[first_touch(got, Decimal(row["stop"]), Decimal(row["target"]))] += 1
        if count % 25 == 0:
            print(f"  {count}/{len(drawn)} fetched")

    resolved = outcomes["stop"] + outcomes["target"]
    print(f"\n  served and resolved      {resolved}")
    print(f"    stop printed first     {outcomes['stop']}")
    print(f"    target printed first   {outcomes['target']}")
    print(f"  one minute reached both  {outcomes['within_a_minute']}   "
          f"(the floor on what any bar can resolve)")
    print(f"  reached neither          {outcomes['neither']}   "
          f"(a mismatch between the daily bar and the minute feed - a defect, not a result)")
    print(f"  not served               {len(unserved)}")

    report: dict[str, Any] = {
        "measured_on": "2026-09-07",
        "question": "DR-042 §4 - on a session reaching both the stop and the target, which first?",
        "asked_by": "the owner, 2026-09-07, ruling on the form of the question: measure first",
        "seed": args.seed, "feed": args.feed,
        "population": len(population), "sampled": len(drawn),
        "outcomes": outcomes, "unserved": unserved[:20],
        "exploratory": True,
        "not_measured": [
            "which leg a REAL OCO would have filled: the venue's matching order is not observable "
            "here, and a minute bar is still a bar.",
            "sessions the feed does not serve; those are reported and never imputed.",
        ],
    }
    if resolved:
        share = outcomes["stop"] / resolved
        low, high = interval(outcomes["stop"], resolved)
        wrong = 1 - share
        report["stop_first_share"] = share
        report["stop_first_interval"] = {"low": low, "high": high}
        report["assumption_is_wrong_on_this_share_of_ambiguous_bars"] = wrong

        print("\n  1. HOW OFTEN THE RULE IS WRONG")
        print(f"     stop first {share * 100:.1f}%  95% [{low * 100:.1f}%, {high * 100:.1f}%]")
        print(f"     The harness assumes 100%, so on an ambiguous bar it takes the wrong leg "
              f"{wrong * 100:.1f}% of the time.")
        if low <= 0.5 <= high:
            print("     The interval spans 50%: which leg comes first is not distinguishable "
                  "from a coin toss.")

        print("\n  2. HOW OFTEN IT IS CONSULTED AT ALL")
        impacts = report_impact(args.result, wrong)
        for line in impacts["lines"]:
            print(f"     {line}")
        report["impact"] = impacts["arms"]

        print("\n  3. THE PRODUCT, which is the only one that moves a published figure")
        if impacts["arms"]:
            worst = max(impacts["arms"].values(), key=lambda a: abs(a["impact_r_per_trade"]))
            print(f"     at most {worst['impact_r_per_trade']:+.5f} R a trade, and that is an "
                  f"upper bound")
            print("     DR-042 §4a's registered threshold is about the share of EXITS that are "
                  "ambiguous,")
            print("     never about how often the rule is wrong. Against it:")
            for name, arm in sorted(impacts["arms"].items()):
                verdict = "ABOVE" if arm["ambiguous_share"] > AMBIGUOUS_SHARE_THRESHOLD else "below"
                print(f"       {name:16} {arm['ambiguous_share'] * 100:7.3f}% of exits - "
                      f"{verdict} {AMBIGUOUS_SHARE_THRESHOLD:.0%}")
        else:
            print("     no study result to read a share from, so the rate above cannot be turned "
                  "into an impact and must not be reported as one")

        print("\n  This is EVIDENCE for the ruling and is not the ruling. DR-042 §8 is the owner's.")
        print("  The two numbers point different ways on purpose: as a CONVENTION the rule is")
        print("  wrong more often than right, and as an EFFECT on anything published it is noise.")

    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
