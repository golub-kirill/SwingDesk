"""Is a later pass worth running tonight? Asked of the journal, not assumed.

`DR-015` §3 gave the evening a second scheduled pass so a fetch that failed inside the run gets one
more chance. It has run unconditionally ever since, and **it has never changed an outcome**:
measured 2026-08-24 across every evening that ran both passes, the two runs carry the same
`output_hash` every time.

**The failure it insures against has not been observed here either.** `market_data/retry.py`'s own
docstring records ten scheduled runs across roughly 11,200 instrument-fetches with **zero**
`VendorUnavailable`. So the pass costs a full run every evening for a case that has not occurred.

**What DOES occur is a different thing, and the second pass at 19:30 could not fix it.** On
2026-08-24 the run left 86 admitted candidates refused one session behind. Re-asking the same vendor
the same evening - with the run's own request shape - returned every one of those sessions, clean.
The bars had not been published when the run asked, and were published later. That is a late
arrival, not a failed fetch, and an hour was not enough of a wait.

So this tool answers the narrow question the wrapper needs: **did tonight's run refuse anything a
later attempt could plausibly repair?** A `DATA` refusal is exactly that class - stale, incomplete or
absent source data. Anything else (`RISK`, `STOP`, `LIQ`) is a decision about the trade and no
amount of waiting changes it.

**It reads the journal rather than a sentinel file.** The decisions are already recorded, so a
marker would be a second copy of a fact the store already holds (`AGENTS.md` §10.5).

    python tools/retry_needed.py [--data DIR] [--as-of YYYY-MM-DD]

    exit 0  a later pass is warranted - today's run recorded at least one DATA refusal
    exit 1  nothing to retry
    exit 4  UNAVAILABLE - no journal here, so this cannot answer (AGENTS.md §10.6 rule 2)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

WARRANTED = 0
NOTHING_TO_RETRY = 1
UNAVAILABLE = 4

#: The one refusal class a later attempt can repair. `DATA` covers stale, incomplete and absent
#: source data; every other code in `CODES.md` is a statement about the trade rather than the feed.
REPAIRABLE = "DATA"


def _data_dir(argument: str | None) -> Path:
    if argument:
        return Path(argument)
    return Path(os.environ.get("SWINGDESK_DATA") or REPO / "data")


def count_repairable(journal: Path, session: date) -> int | None:
    """How many `DATA` refusals the given day recorded, or `None` if it cannot be measured."""
    if not journal.is_file():
        return None
    try:
        import duckdb
    except ImportError:
        return None
    try:
        connection = duckdb.connect(str(journal), read_only=True)
    except duckdb.Error:
        # A held store is not an answer of zero. `AGENTS.md` §12: UNAVAILABLE, never a traceback.
        return None
    try:
        row = connection.execute(
            "SELECT count(*) FROM decisions WHERE decision = 'Skip' AND reason_code = ? "
            "AND cast(recorded_at AS DATE) = ?",
            [REPAIRABLE, session],
        ).fetchone()
    except duckdb.Error:
        return None
    finally:
        connection.close()
    return int(row[0]) if row else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=None)
    parser.add_argument("--as-of", default=None,
                        help="the session to ask about; defaults to today on the local clock")
    args = parser.parse_args()

    # `--as-of` is a SESSION, not an instant, so it is parsed as a date rather than as a naive
    # datetime that would then need a timezone it does not have. The default is a real instant and
    # is made aware before its date is taken - the run's own local day is the one being asked about.
    session = date.fromisoformat(args.as_of) if args.as_of else datetime.now().astimezone().date()
    journal = _data_dir(args.data) / "journal.duckdb"
    found = count_repairable(journal, session)

    if found is None:
        print(f"retry: UNAVAILABLE - no readable journal at {journal}")
        return UNAVAILABLE
    if found:
        print(f"retry: WARRANTED - {session} recorded {found} {REPAIRABLE} refusal(s); "
              f"a later pass may repair them")
        return WARRANTED
    print(f"retry: nothing to retry - {session} recorded no {REPAIRABLE} refusal")
    return NOTHING_TO_RETRY


if __name__ == "__main__":
    sys.exit(main())
