"""Does a free source serve delisting history? Asked of SEC EDGAR, because nobody had asked.

**The claim this probe was written to test.** `VENDOR_COMPARISON.md` §7 and `EVIDENCE_SUMMARY.md`
state that **no free source serves delisted history**, and that claim is load-bearing: it is the
premise under the survivorship bound that erases `PR-002`, the one positive finding this project
has. It had never been tested against a source. `AGENTS.md` §15 is the rule that says an
impossibility is a claim.

**The answer is that the claim is TRUE OF PRICES and FALSE OF THE DELISTING ITSELF**, and those are
different halves of the bound:

  * **Prices for a delisted name** - still unobtainable on the free tier. Yahoo serves no bars for a
    symbol that has gone, and this probe changes nothing about that.
  * **The FACT and DATE of a delisting** - freely and officially available. SEC EDGAR keeps every
    filer that ever reported, back to 1993, including companies long gone. Form **25** and
    **25-NSE** are the delisting notifications, they carry filing dates, and a delisted issuer's
    submissions record shows empty `tickers` and `exchanges`.

**Why that matters even without prices.** The survivorship bound currently rests on an ASSUMED rate
of trades lost to delisting. Knowing which admitted names delisted, and when, turns the universe
half of that bound from an assumption into a measurement - a name that vanished can be counted even
when its price path cannot be recovered.

**Cost, registration and terms.** None, none, and a fair-access policy: requests must carry a
descriptive `User-Agent` and are rate-limited. **No email is sent by this tool.** The SEC asks for a
contact address in the header and the operator can supply one through `SWINGDESK_EDGAR_CONTACT`;
nothing here transmits an address it was not given.

**~~THE TWO HOSTS BEHAVE DIFFERENTLY~~ - RETESTED 2026-08-25 AND THEY DO NOT. Both are open, and
nothing needs configuring.**

This block used to read: *"`data.sec.gov` 200, `www.sec.gov` 403 ... the ticker-to-CIK map lives on
`www.sec.gov`, so a lookup BY TICKER needs the operator to declare a contact."* Measured again with
the header held constant, and **the host was never the variable**:

| Headers sent | `data.sec.gov` | `www.sec.gov` |
|---|---|---|
| none | 403 | 403 |
| `User-Agent` only | 200 | **403** |
| `User-Agent` + `Accept` | 200 | **200** |
| `Accept` only | - | 403 |

**`www.sec.gov` requires BOTH a `User-Agent` and an `Accept` header.** Six probes, isolated one
header at a time, repeated three times against flakiness.

**How the wrong conclusion was reached, which is the transferable part.** `fetch()` has always sent
`Accept: application/json`; the `www.sec.gov` probe was made separately and sent only a
`User-Agent`. **The two hosts were compared with different headers**, the difference was attributed
to the host, and a real measurement was parked behind an owner action that was never needed. That is
`AGENTS.md` §17 exactly - verify at the right granularity - and §15's asymmetry: the wrong
impossibility cost fifteen days of a measurement nobody could take.

**The contact address is still worth setting and is no longer a blocker.** The SEC's fair-access
policy asks for one and `SWINGDESK_EDGAR_CONTACT` still supplies it; nothing here transmits an
address it was not given. What changed is that lookup BY TICKER works without it.

**Read-only, and it writes nothing.** It fetches a handful of submission records to demonstrate the
route and prints what it found.

    python tools/probe_edgar.py
    SWINGDESK_EDGAR_CONTACT="ops@example.com" python tools/probe_edgar.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "https://data.sec.gov/submissions/CIK{cik:010d}.json"

#: The ticker-to-CIK map. Lives on `www.sec.gov`, which was believed closed to this tool until
#: 2026-08-25 - see the header block. About 10,400 currently-registered tickers.
TICKER_MAP = "https://www.sec.gov/files/company_tickers.json"

#: SEC fair access allows ten requests a second. One every two seconds is far inside it and this
#: probe fetches a handful of records, so politeness costs nothing worth optimising.
DELAY_SECONDS = 2.0

#: Known cases, chosen to test both directions rather than only the convenient one.
#: A live listing must still look live, or "delisted" would be indistinguishable from "any company".
CASES: tuple[tuple[int, str, bool], ...] = (
    (320193, "Apple Inc.", True),            # listed - the control
    (1322439, "Eagle Bulk Shipping", False),  # delisted, Form 25 in 2023 and 25-NSE in 2024
)

DELISTING_FORMS = ("25", "25-NSE")


def _user_agent() -> str:
    """A descriptive agent, with a contact only if the operator supplied one.

    The SEC's fair-access policy asks for a contact address. This tool never invents one and never
    reaches for an address it found elsewhere in the environment: an address is transmitted only
    when the operator sets it deliberately.
    """
    contact = os.environ.get("SWINGDESK_EDGAR_CONTACT", "").strip()
    base = "SwingDesk research probe"
    return f"{base} ({contact})" if contact else f"{base} (contact not configured)"


def fetch(cik: int) -> dict | None:
    request = urllib.request.Request(
        BASE.format(cik=cik), headers={"User-Agent": _user_agent(), "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"  CIK {cik}: UNREACHABLE - {error}")
        return None


def describe(record: dict) -> tuple[bool, list[tuple[str, str]]]:
    """Whether the issuer still lists anywhere, and every delisting notice with its date."""
    listed = bool(record.get("tickers")) and bool(record.get("exchanges"))
    recent = record.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    notices = [
        (forms[i], dates[i]) for i in range(min(len(forms), len(dates)))
        if forms[i] in DELISTING_FORMS
    ]
    return listed, notices


def host_reachability() -> list[tuple[str, str]]:
    """Re-derive the host/header table on every run instead of trusting the block above.

    **This exists because that block was wrong for fifteen days**, and wrong in the direction that
    closes work: it reported `www.sec.gov` as forbidden and sent a real measurement to wait on an
    owner action that was never needed. A reachability fact decides what work is possible, so it
    earns the same treatment `AGENTS.md` §10.6 gives a measured count - derived, not remembered.
    Three requests.
    """
    results = []
    for label, url, headers in (
        ("data.sec.gov  UA+Accept", BASE.format(cik=320193),
         {"User-Agent": _user_agent(), "Accept": "application/json"}),
        ("www.sec.gov   UA only", TICKER_MAP, {"User-Agent": _user_agent()}),
        ("www.sec.gov   UA+Accept", TICKER_MAP,
         {"User-Agent": _user_agent(), "Accept": "application/json"}),
    ):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                results.append((label, str(response.status)))
        except urllib.error.HTTPError as error:
            results.append((label, f"{error.code} {error.reason}"))
        except (urllib.error.URLError, TimeoutError) as error:
            results.append((label, f"UNREACHABLE {error}"))
        time.sleep(DELAY_SECONDS)
    return results


def main() -> int:
    print(f"probe_edgar: {len(CASES)} case(s), User-Agent {_user_agent()!r}\n")

    print("  host reachability, re-measured now rather than quoted:")
    for label, status in host_reachability():
        print(f"      {label:26} {status}")
    print("      `www.sec.gov` needs BOTH headers. The host was never the variable; the header was.")
    print()

    failures = 0
    for index, (cik, name, expected_listed) in enumerate(CASES):
        if index:
            time.sleep(DELAY_SECONDS)
        record = fetch(cik)
        if record is None:
            failures += 1
            continue
        listed, notices = describe(record)
        state = "listed" if listed else "NOT listed"
        print(f"  {record.get('name', name)}")
        print(f"      {state}   tickers={record.get('tickers')}  exchanges={record.get('exchanges')}")
        print(f"      delisting notices: {notices or 'none'}")
        if listed != expected_listed:
            print("      UNEXPECTED - this case no longer demonstrates what it was chosen for")
            failures += 1

    print("\nWhat this establishes: the FACT and DATE of a delisting are free and official.")
    print("What it does NOT: prices for a delisted name are still unobtainable on the free tier,")
    print("so the RETURN half of the survivorship bound is untouched by this route.")
    print("")
    print("AND WHAT THE CONTROL TAUGHT, which is why a listed case is in here: Apple files Form 25")
    print("and 25-NSE too, and is listed. Those retire individual SECURITIES - notes, warrants,")
    print("preferred series - not the company. A Form 25 is therefore NOT a company delisting. The")
    print("field that discriminates is an empty ticker and exchange list; the form dates it.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
