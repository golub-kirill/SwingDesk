"""Download the NASDAQ Trader symbol directory and record it as one dated pull.

The two files cover every US venue in scope. There is no equivalent for Canada, which is why the
`.TO` universe is still a list rather than a rule (DR-003 gap 1).

Run this before the universe can be built, and periodically after - each run adds a snapshot, and
consecutive snapshots are the only free survivorship evidence available to this project. Skipping
runs does not lose accuracy today; it loses the departure record permanently.

Network tool. Never imported by anything in src/, never run in CI (CI_POLICY 4).

    python tools/fetch_directory.py
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.reference import Exchange
from swingdesk.reference_data import calendar as cal
from swingdesk.reference_data import universe
from swingdesk.reference_data.directory import DirectoryStore

SOURCE = "nasdaqtrader.com/SymDir"
USER_AGENT = "swingdesk/0.0"
FILES = {
    "nasdaqlisted.txt": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "otherlisted.txt": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}

#: Response cap (DR-008). Applied to Content-Length AND to bytes actually read, so a server that
#: omits or misstates the header cannot bypass it.
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

#: Per-machine switch. Ignored by git, never committed, and absent means OFF - the same
#: fail-closed rule the parameter registry uses. There is deliberately no committed default.
LOCAL_CONFIG = ".swingdesk-local.json"
REPO = Path(__file__).resolve().parents[1]


def collection_enabled(root: Path) -> bool:
    """True only for an explicit boolean true. Missing, false, malformed or non-boolean refuse."""
    config = root / LOCAL_CONFIG
    if not config.is_file():
        return False
    try:
        loaded = json.loads(config.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    value = loaded.get("directory_pull_enabled") if isinstance(loaded, dict) else None
    return value is True


def _download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        declared = response.headers.get("Content-Length")
        if declared is not None and int(declared) > MAX_RESPONSE_BYTES:
            raise ValueError(f"{url}: declared {declared} bytes exceeds the cap")
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(f"{url}: body exceeds the {MAX_RESPONSE_BYTES} byte cap")
    return body.decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(prog="fetch_directory")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="honour the local switch and the exchange calendar; the manual form ignores both, "
             "because a human asked for it",
    )
    args = parser.parse_args()

    if args.scheduled:
        if not collection_enabled(REPO):
            print(f"directory pull disabled - no {LOCAL_CONFIG} with directory_pull_enabled: true")
            return 0
        if not cal.is_open(Exchange.NYSE, datetime.now(UTC).date()):
            print("not an NYSE session - nothing to collect")
            return 0

    entries = [
        *universe.parse_nasdaq_listed(_download(FILES["nasdaqlisted.txt"])),
        *universe.parse_other_listed(_download(FILES["otherlisted.txt"])),
    ]
    eligible = [e for e in entries if e.is_eligible]
    knowledge_time = datetime.now(UTC)

    with DirectoryStore(args.data / "directory.duckdb") as store:
        previous = store.latest_pull(knowledge_time)
        store.record(entries, knowledge_time, SOURCE)
        print(f"recorded {len(entries)} rows ({len(eligible)} eligible) at {knowledge_time:%Y-%m-%d %H:%M}Z")

        if previous is None:
            print("first pull - no departures to report, and none are recoverable for earlier dates")
            return 0

        gone = store.departures(previous, knowledge_time)
        arrived = len(
            {e.symbol for e in entries} - {e.symbol for e in store.as_of(previous)}
        )
        print(f"since {previous:%Y-%m-%d}: {len(gone)} symbol(s) gone, {arrived} new")
        for symbol in gone[:20]:
            print(f"    gone: {symbol}")
        if len(gone) > 20:
            print(f"    ... and {len(gone) - 20} more")
        print("\nA departure is an observation, not a delisting - a ticker change looks the same.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
