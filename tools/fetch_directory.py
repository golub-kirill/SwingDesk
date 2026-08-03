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
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.reference_data import universe  # noqa: E402
from swingdesk.reference_data.directory import DirectoryStore  # noqa: E402

SOURCE = "nasdaqtrader.com/SymDir"
FILES = {
    "nasdaqlisted.txt": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "otherlisted.txt": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}


def _download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "swingdesk/0.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser(prog="fetch_directory")
    parser.add_argument("--data", type=Path, default=Path("data"))
    args = parser.parse_args()

    entries = [
        *universe.parse_nasdaq_listed(_download(FILES["nasdaqlisted.txt"])),
        *universe.parse_other_listed(_download(FILES["otherlisted.txt"])),
    ]
    eligible = [e for e in entries if e.is_eligible]
    knowledge_time = datetime.now(timezone.utc)

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
