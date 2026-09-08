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

#: `DR-042` §4a: the agent's stated threshold, registered before the number existed. Above this the
#: conservative rule stops being a small conservatism and becomes a systematic distortion. Printed
#: beside the answer so the reader does not have to take the interpretation on trust.
MATERIAL_SHARE = 0.15


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bars", type=Path, default=AMBIGUOUS_BARS,
                        help="the ambiguous bars run_pr016.py wrote")
    parser.add_argument("--sample", type=int, default=SAMPLE, help="how many to fetch")
    parser.add_argument("--seed", type=int, default=SEED, help="recorded with the result")
    parser.add_argument("--feed", default="sip", help="alpaca data feed")
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
        report["stop_first_share"] = share
        report["stop_first_interval"] = {"low": low, "high": high}
        print(f"\n  STOP FIRST: {share * 100:.1f}%  95% [{low * 100:.1f}%, {high * 100:.1f}%]")
        print("  The harness assumes 100%. The gap between that and this is the size of "
              "DR-042 §4's assumption.")
        overstated = 1 - share
        report["assumption_overstates_stops_by"] = overstated
        print(f"  It overstates stop-outs by {overstated * 100:.1f} percentage points of the "
              f"ambiguous bars.")
        if overstated > MATERIAL_SHARE:
            print(f"  ABOVE the {MATERIAL_SHARE:.0%} threshold registered in DR-042 §4a before this "
                  f"number existed: the conservative rule is a systematic distortion, not a small "
                  f"conservatism, and the measured split should replace it.")
        else:
            print(f"  BELOW the {MATERIAL_SHARE:.0%} threshold registered in DR-042 §4a before this "
                  f"number existed: the conservative rule is a small conservatism.")
        print("\n  This is EVIDENCE for the ruling and is not the ruling. DR-042 §8 is the owner's.")

    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
