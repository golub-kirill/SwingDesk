"""Fetch Kenneth French's factor returns, so `DR-049`'s attribution is a rule and not a wish.

**Five factors and momentum, daily and monthly, free and without registration.** Measured
2026-09-21: the daily five-factor file carries 15,876 rows from 1963-07-01 and the daily momentum
file 26,195 rows from 1926-11-03. Both are built from the `202607` CRSP database, so **the series
end about two months behind the present**, and that lag is a property of the source rather than of
this tool - a study running to last week can be attributed only to the library's last month.

**Stored exactly as published, in PERCENT.** The same rule the bar store follows: keep the vendor's
numbers and convert on read (`factor_attribution.to_fraction`). A store holding pre-divided numbers
cannot be checked against the source it came from.

    python tools/fetch_factors.py --data <store dir>

Network tool, never imported by anything in `src/`, never run in CI (`CI_POLICY` §4). No key, no
account, no terms beyond the library's own.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from factor_attribution import FACTORS

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"

#: `(frequency, five-factor archive, momentum archive, the date width its rows carry)`.
SOURCES = (
    ("daily", "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
     "F-F_Momentum_Factor_daily_CSV.zip", 8),
    ("monthly", "F-F_Research_Data_5_Factors_2x3_CSV.zip",
     "F-F_Momentum_Factor_CSV.zip", 6),
)

Getter = Callable[[str], bytes | None]


def get(url: str) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": "SwingDesk-research/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return bytes(response.read())
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return None


def rows_of(archive: bytes, width: int, columns: int) -> dict[str, list[str]]:
    """Every data row of the first CSV in the archive, keyed by its date token.

    French's files carry a prose header, then the table, then - in the monthly files - a SECOND
    table of annual returns under its own heading. A row is taken only when its first field is a
    date of exactly the expected width and it has the expected number of columns, which is what
    stops the annual block being read as twelve more months.
    """
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        text = bundle.read(bundle.namelist()[0]).decode("latin-1")
    out: dict[str, list[str]] = {}
    for line in text.splitlines():
        fields = [f.strip() for f in line.split(",")]
        if len(fields) != columns + 1:
            continue
        if not re.fullmatch(rf"\d{{{width}}}", fields[0]):
            continue
        out[fields[0]] = fields[1:]
    return out


def merged(five: dict[str, list[str]], momentum: dict[str, list[str]]) -> list[list[str]]:
    """The dates BOTH files carry, as `date, Mkt-RF, SMB, HML, RMW, CMA, MOM, RF`.

    An inner join: the momentum file starts in 1926 and the five-factor file in 1963, and a row
    with five of six factors is not a row this can regress on.
    """
    return [[day, *five[day][:5], momentum[day][0], five[day][5]]
            for day in sorted(five) if day in momentum]


def write(path: Path, rows: list[list[str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", *FACTORS, "RF"])
        writer.writerows(rows)
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True, help="the directory to write into")
    args = parser.parse_args(argv)

    print(f"factors  fetched {datetime.now(UTC).isoformat(timespec='seconds')}")
    written = 0
    for frequency, five_name, momentum_name, width in SOURCES:
        five_raw, momentum_raw = get(BASE + five_name), get(BASE + momentum_name)
        if five_raw is None or momentum_raw is None:
            print(f"  {frequency:8s} UNAVAILABLE - the library did not answer")
            continue
        rows = merged(rows_of(five_raw, width, 6), rows_of(momentum_raw, width, 1))
        if not rows:
            print(f"  {frequency:8s} UNAVAILABLE - no row carried all six factors")
            continue
        path = args.data / f"factors-{frequency}.csv"
        count = write(path, rows)
        written += 1
        print(f"  {frequency:8s} {count:,} rows  {rows[0][0]} .. {rows[-1][0]}  -> {path}")
    return 0 if written else 4


if __name__ == "__main__":  # pragma: no cover - the entry point
    raise SystemExit(main())
