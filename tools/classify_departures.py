"""Classify the symbols that left the directory: delisting, rename, or still listed.

`DR-008` consequence 3 records the ambiguity this closes: *"a departure is an observation, not a
delisting - a ticker change looks the same"*. `EVIDENCE_SUMMARY.md` §3 puts a number on why it
matters: `PR-002`'s only positive finding is erased by 1.6-2.3% of trades missing at -2R, and
survivorship is the mechanism that would make them missing. Counting departures is the **universe**
half of that bound. The RETURN half stays closed - no free source serves the price path of a symbol
that has gone - so this constrains the exposure's SIZE and never its magnitude.

**This was believed to need an owner action for fifteen days and did not.** `TODO.md` recorded that
a lookup by ticker needs `SWINGDESK_EDGAR_CONTACT` because `www.sec.gov` returns 403. Retested
2026-08-25 with the header held constant: **`www.sec.gov` needs a `User-Agent` AND an `Accept`
header**, and the original comparison had sent `Accept` to one host and not the other. The host was
never the variable. `tools/probe_edgar.py` re-derives that table on every run now.

**Two discriminators, and they disagree at short horizons - which is the finding.**

* **The filer's ticker list** (`submissions/CIK….json`) is what `probe_edgar.py` validated on a 2024
  delisting, and it is **not timely**. Measured over 87 departures from a three-week window: 34 of
  the 36 resolvable names still carried their departed ticker in EDGAR's metadata while being absent
  from the vendor's live directory. Right for history, useless for last week.
* **The Form 25 / 25-NSE date** IS timely. 26 of those 36 filed one inside the observation window,
  and the dates line up with the pull the symbol vanished at - `AVB` left between the 08-14 and
  08-17 pulls and filed on 08-17; `WBS` left between 08-19 and 08-20 and filed on 08-20.

So a recent departure is classified by the FORM DATE, not by the ticker list. `probe_edgar.py`'s
control still governs how to read one: **a Form 25 is not a company delisting** - Apple files them
to retire individual securities - so the claim here is deliberately narrow: *this SECURITY was
delisted*, which is exactly what a departure from a symbol directory is about.

**Structured symbols are counted apart, never mixed in.** Warrants, units, rights and share classes
carry a `.` or `$` and "depart" on separation rather than on any corporate failure. `DR-003` records
them as systematically preferred shares and units rather than a random slice, so folding them into a
delisting rate would inflate it with events that are not delistings.

Network tool. Read-only: it writes nothing to any store.

    python tools/classify_departures.py
    python tools/classify_departures.py --data data --out departures.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.reference_data.directory import DirectoryStore

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
TICKER_MAP = "https://www.sec.gov/files/company_tickers.json"

#: Both are required by `www.sec.gov`; `data.sec.gov` needs only the first. Sending both everywhere
#: keeps the two calls comparable, which is the discipline whose absence produced the false 403.
DELAY_SECONDS = 0.15

#: A warrant, unit, right or share class. `.` and `$` are the vendor's own suffix markers.
STRUCTURED = re.compile(r"[.$]")

DELISTING_FORMS = ("25", "25-NSE")


def _user_agent() -> str:
    """Descriptive, with a contact only if the operator supplied one. No address is invented."""
    contact = os.environ.get("SWINGDESK_EDGAR_CONTACT", "").strip()
    base = "SwingDesk research probe"
    return f"{base} ({contact})" if contact else f"{base} (contact not configured)"


def _headers() -> dict[str, str]:
    return {"User-Agent": _user_agent(), "Accept": "application/json"}


def _get(url: str) -> dict | None:
    request = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def ticker_to_cik() -> dict[str, int]:
    """Today's SEC ticker map. Empty on failure rather than raising - the caller reports coverage."""
    raw = _get(TICKER_MAP)
    if not raw:
        return {}
    return {row["ticker"].upper(): int(row["cik_str"]) for row in raw.values()}


def classify(
    symbol: str, cik: dict[str, int], window: tuple[date, date]
) -> dict[str, object]:
    """One departed symbol, judged against EDGAR.

    Returns a verdict and the evidence for it. `unresolved` is a real answer and is reported as one:
    a symbol with no CIK in today's map may be a delisted issuer, a fund that never filed under that
    ticker, or a rename - and saying so beats guessing (`AGENTS.md` §12, `unavailable` is not
    `pass`).
    """
    if STRUCTURED.search(symbol):
        return {"symbol": symbol, "verdict": "structured",
                "why": "a warrant, unit, right or share class - departs on separation"}

    number = cik.get(symbol.upper())
    if number is None:
        return {"symbol": symbol, "verdict": "unresolved",
                "why": "no CIK in today's SEC ticker map"}

    record = _get(SUBMISSIONS.format(cik=number))
    if record is None:
        return {"symbol": symbol, "verdict": "unresolved", "why": "EDGAR unreachable for this CIK"}

    recent = record.get("filings", {}).get("recent", {})
    notices = [
        (form, filed)
        for form, filed in zip(recent.get("form", []), recent.get("filingDate", []), strict=False)
        if form in DELISTING_FORMS
    ]
    tickers = [t.upper() for t in (record.get("tickers") or [])]
    start, end = window
    inside = [n for n in notices if start <= date.fromisoformat(n[1]) <= end]

    if inside:
        verdict, why = "delisted", f"{inside[0][0]} filed {inside[0][1]}, inside the window"
    elif not tickers:
        verdict, why = "delisted", "the filer lists no ticker at all"
    elif symbol.upper() not in tickers:
        verdict, why = "renamed", f"the filer now lists {tickers}"
    else:
        verdict, why = "still listed at EDGAR", (
            "the filer still lists this ticker and filed no Form 25 in the window - EDGAR's "
            "metadata lags the vendor's directory, so this is not evidence of survival"
        )
    return {
        "symbol": symbol, "verdict": verdict, "why": why,
        "name": record.get("name"), "tickers": tickers,
        "exchanges": record.get("exchanges") or [],
        "latest_form25": notices[0] if notices else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="classify_departures")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    with DirectoryStore(args.data / "directory.duckdb") as store:
        pulls = [row[0] for row in store.pulls()]
        if len(pulls) < 2:
            print("fewer than two pulls - there is nothing to compare")
            return 2
        first, last = pulls[0], pulls[-1]
        departed = store.departures(first, last)

    window = (first.date(), last.date())
    print(f"window {window[0]} -> {window[1]} over {len(pulls)} pull(s): "
          f"{len(departed)} departure(s)\n")

    cik = ticker_to_cik()
    if not cik:
        print("the SEC ticker map could not be fetched - every symbol will report `unresolved`")
    else:
        print(f"SEC ticker map: {len(cik):,} tickers\n")

    results = []
    for symbol in departed:
        results.append(classify(symbol, cik, window))
        time.sleep(DELAY_SECONDS)

    tally = Counter(str(row["verdict"]) for row in results)
    for verdict, count in tally.most_common():
        print(f"  {count:3}  {verdict}")

    delisted = [r for r in results if r["verdict"] == "delisted"]
    print(f"\n{len(delisted)} of {len(departed)} departures are confirmed delistings of that "
          f"security:")
    for row in sorted(delisted, key=lambda r: str(r.get("latest_form25") or "")):
        print(f"    {row['symbol']:8} {row['why']}")

    print("\nWhat this does NOT establish, stated so the number is not over-read:")
    print("  `unresolved` is not `not delisted` - it is a symbol this route could not place.")
    print("  `still listed at EDGAR` is not survival either: the metadata lags the vendor by more")
    print("  than this window, measured at 34 of 36 on 2026-08-25.")
    print("  And the RETURN half of the survivorship bound is untouched - no free source serves the")
    print("  price path of a symbol that has gone, so -2R stays an assumption.")

    if args.out:
        args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
