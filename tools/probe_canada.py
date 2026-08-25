"""Can the Canadian universe be enumerated? Asked of TMX, because the claim had hardened.

**What this tests, and why it is the most expensive claim in the audit.** `DR-003` gap 1 says:
*"Canada has no free symbol directory **in hand**. The NASDAQ Trader files cover US venues only. The
rule applies to `.TO` instruments identically, but this project **cannot presently** enumerate
them."* That wording is careful and was honest - it says nobody had one, not that none exists.

**Downstream it hardened, and then it narrowed a study.** `PR-002`'s report states *"Canada cannot
be enumerated (`DR-003`), so that cannot be met"* and drops §6's requirement of significance in both
countries independently - the requirement whose failure is why `PR-002` could not reach an
affirmative verdict. A qualified "not in hand" became an unqualified "cannot", and a study lost half
its scope to it. `AGENTS.md` §15 exists for exactly this shape.

**The answer: it can be enumerated, free, with no account and no key.** TMX's own listed-company
directory is backed by a JSON endpoint, one call per leading character per exchange, returning
symbol and name and carrying a `last_updated` stamp:

    https://www.tsx.com/json/company-directory/search/{tsx|tsxv}/{A..Z,0..9}

**What that does and does not settle.**

  * It settles ENUMERATION - the thing `DR-003` gap 1 and `PR-002` both said was impossible.
  * It does **not** settle POINT-IN-TIME membership. This is today's directory, so applying it to
    old data is survivorship bias with extra steps - the same objection `DR-003` raises against
    index membership in its own table, and it is unaffected by this probe.
  * It does **not** settle bar coverage. Whether the vendor serves usable history for a given `.TO`
    symbol is a separate question this does not ask.

**It is an unofficial endpoint on a consumer site, like the bar source** (`ADR-0001`), and carries
the same standing caveat: undocumented, unversioned, and free to change without notice.

**Read-only, writes nothing, and paced.** One request every two seconds.

    python tools/probe_canada.py            # sample, a few leading characters
    python tools/probe_canada.py --full     # every character, both exchanges
"""

from __future__ import annotations

import argparse
import json
import string
import sys
import time
import urllib.error
import urllib.request

BASE = "https://www.tsx.com/json/company-directory/search/{exchange}/{letter}"
EXCHANGES = ("tsx", "tsxv")
ALPHABET = string.ascii_uppercase + string.digits

#: Polite pacing for an undocumented endpoint on somebody else's site.
DELAY_SECONDS = 2.0

USER_AGENT = "SwingDesk research probe"


def fetch(exchange: str, letter: str) -> dict | None:
    request = urllib.request.Request(
        BASE.format(exchange=exchange, letter=letter),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"  {exchange}/{letter}: UNREACHABLE - {error}")
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="probe_canada", description=__doc__)
    parser.add_argument("--full", action="store_true",
                        help="every leading character; otherwise a short sample")
    args = parser.parse_args(argv)

    letters = ALPHABET if args.full else "AMZ"
    print(f"probe_canada: {len(EXCHANGES)} exchange(s) x {len(letters)} leading character(s)\n")

    totals: dict[str, set[str]] = {exchange: set() for exchange in EXCHANGES}
    capped: list[str] = []
    stamps: set[int] = set()
    first = True
    for exchange in EXCHANGES:
        for letter in letters:
            if not first:
                time.sleep(DELAY_SECONDS)
            first = False
            payload = fetch(exchange, letter)
            if payload is None:
                return 1
            # A capped response would make every total a floor quoted as a count. The endpoint
            # reports its own `length` beside the rows, so the two are compared rather than trusted:
            # the first full run summed to exactly 3000 on TSX, which is round enough to deserve a
            # check, and the per-query counts turned out to vary naturally with no cap.
            declared = payload.get("length")
            returned = len(payload.get("results", []))
            if declared is not None and int(declared) != returned:
                capped.append(f"{exchange}/{letter}: declared {declared}, returned {returned}")
            for row in payload.get("results", []):
                for instrument in row.get("instruments") or [row]:
                    symbol = instrument.get("symbol")
                    if symbol:
                        totals[exchange].add(symbol)
            if payload.get("last_updated"):
                stamps.add(int(payload["last_updated"]))

    for exchange in EXCHANGES:
        print(f"  {exchange.upper():<5} distinct symbols over {len(letters)} character(s): "
              f"{len(totals[exchange])}")
    both = totals["tsx"] | totals["tsxv"]
    print(f"  union: {len(both)}")
    if stamps:
        newest = time.strftime("%Y-%m-%d %H:%M", time.localtime(max(stamps)))
        print(f"  the endpoint stamps its own freshness: last_updated {newest}")

    if capped:
        print("\n  TRUNCATION DETECTED - the totals above are FLOORS, not counts:")
        for line in capped:
            print(f"    {line}")
    else:
        print("  no query returned fewer rows than it declared, so the totals are counts")

    print("\nENUMERATION is settled - free, no account, no key.")
    print("POINT-IN-TIME membership is NOT: this is today's directory, and applying it to old data")
    print("is the survivorship bias DR-003's own table objects to for index membership.")
    print("Bar COVERAGE is a separate question this does not ask.")
    print("Unofficial endpoint on a consumer site, same standing caveat as the bar source (ADR-0001).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
