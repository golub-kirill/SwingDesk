"""What the vendor actually rewrites, per field, and where a threshold could cut.

**The question.** `DR-016` §3 proposes `data.revision_epsilon = 0.001` and scopes it to *"`open`,
`high`, `low`, `close` on the `raw` series"*. §6 of that record names its own overturning condition
— a longer capture window — and the window is now longer. This re-measures it, and it re-measures
each field APART, which is the part §2's table left blank for the open.

**Why per-field is the whole point.** `DR-016`'s central finding is that one epsilon cannot cover
fields whose revision distributions differ by orders of magnitude, and it applied that finding to
take VOLUME out of the rule. The same test, run on the four price fields, does not give the same
answer for all four.

**Settled bars only.** A bar first captured before its own session's close is a mid-session
snapshot, and a later "revision" of it is the session finishing rather than the vendor restating
anything. The close time comes from the calendar, not from the data.

**Consecutive versions, not first-against-last.** A bar revised twice is two events, and collapsing
them would hide the smaller one and understate how often a gate would fire.

Reads `data/bars.duckdb` and nothing else. No network.

    python tools/measure_revisions.py --data data
    python tools/measure_revisions.py --data data --out docs/decisions/measurements/revisions-2026-08-23.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from itertools import groupby, pairwise
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import duckdb

from swingdesk.contracts.reference import Exchange
from swingdesk.reference_data import calendar as cal

#: The four price fields §4 of `DATA_QUALITY_SPEC` calls immutable on the raw series.
PRICE_FIELDS = ("open", "high", "low", "close")

#: Candidate thresholds. 0.001 is what `DR-016` §3 proposes; the others bracket it so the reader can
#: see how fast the fire rate moves rather than taking one number on trust.
CANDIDATES = (
    Decimal("0.0005"),
    Decimal("0.001"),
    Decimal("0.005"),
    Decimal("0.01"),
    Decimal("0.05"),
)

#: Quantiles reported per field. The top three matter most: a threshold has to sit above the noise
#: population, and where that population ends is the only question this tool exists to answer.
QUANTILES = (0.5, 0.75, 0.9, 0.95, 0.99, 1.0)


def _versions(data: Path) -> list[tuple]:
    """Every stored version of every daily raw bar that has more than one, oldest first."""
    connection = duckdb.connect(str(data / "bars.duckdb"), read_only=True)
    try:
        return connection.execute(
            """
            SELECT instrument_id, event_time, session_date, knowledge_time,
                   open, high, low, close, volume
            FROM bars
            WHERE interval = '1d' AND series = 'raw'
              AND (instrument_id, event_time) IN (
                    SELECT instrument_id, event_time FROM bars
                    WHERE interval = '1d' AND series = 'raw'
                    GROUP BY 1, 2 HAVING COUNT(*) > 1)
            ORDER BY instrument_id, event_time, knowledge_time
            """
        ).fetchall()
    finally:
        connection.close()


def _session_closes() -> dict[date, datetime]:
    """Close time per session, from the calendar rather than from the bars.

    `CALENDAR_SPEC` §5 makes the calendar the authority on when a session ends, and taking it from
    the data instead would let a mis-stamped bar declare itself settled.
    """
    return {
        session.session_date: session.close_time
        for session in cal.sessions(Exchange.NYSE, date(2016, 1, 1), date(2026, 12, 31))
    }


def measure(data: Path) -> dict[str, object]:
    closes = _session_closes()
    moved: dict[str, list[float]] = {field: [] for field in PRICE_FIELDS}
    volume_moved: list[float] = []
    fires: dict[str, Counter[str]] = {field: Counter() for field in (*PRICE_FIELDS, "ANY")}
    sessions_seen: set[date] = set()
    #: Instruments and sessions behind the widest revisions, so a cluster can be told from a
    #: population. A tail concentrated in one session is a vendor event; a tail spread across the
    #: universe is what the field simply does.
    wide_instruments: Counter[str] = Counter()
    wide_sessions: Counter[date] = Counter()
    pairs = settled = 0

    for _, group in groupby(_versions(data), key=lambda row: (row[0], row[1])):
        versions = list(group)
        close_time = closes.get(versions[0][2])
        # The FIRST capture decides. A bar taken mid-session and revised at the close is the
        # session finishing, not a restatement, however many versions follow.
        if close_time is None or versions[0][3] < close_time:
            pairs += len(versions) - 1
            continue
        sessions_seen.add(versions[0][2])
        for earlier, later in pairwise(versions):
            pairs += 1
            settled += 1
            relative: dict[str, Decimal] = {}
            for offset, field in enumerate(PRICE_FIELDS, start=4):
                before = Decimal(str(earlier[offset]))
                after = Decimal(str(later[offset]))
                relative[field] = abs((after - before) / before) if before else Decimal(0)
                if before and after != before:
                    moved[field].append(float(relative[field]))
                    if field == "open" and relative[field] > Decimal("0.01"):
                        wide_instruments[versions[0][0]] += 1
                        wide_sessions[versions[0][2]] += 1
            if earlier[8] and later[8] != earlier[8]:
                volume_moved.append(abs((later[8] - earlier[8]) / earlier[8]))
            for candidate in CANDIDATES:
                hit = [field for field in PRICE_FIELDS if relative[field] > candidate]
                for field in hit:
                    fires[field][str(candidate)] += 1
                if hit:
                    fires["ANY"][str(candidate)] += 1

    def quantiles(values: list[float]) -> dict[str, float]:
        ordered = sorted(values)
        return {
            f"p{int(q * 100)}": ordered[min(int(q * (len(ordered) - 1)), len(ordered) - 1)]
            for q in QUANTILES
        }

    sessions = len(sessions_seen) or 1
    return {
        "measured_on": datetime.now(UTC).date().isoformat(),
        "version_pairs": pairs,
        "settled_version_pairs": settled,
        "sessions_covered": len(sessions_seen),
        "revised": {
            field: {"count": len(moved[field]), **quantiles(moved[field])}
            for field in PRICE_FIELDS
            if moved[field]
        },
        "volume": {
            "count": len(volume_moved),
            "median": float(statistics.median(volume_moved)) if volume_moved else 0.0,
            "max": float(max(volume_moved)) if volume_moved else 0.0,
        },
        "would_fire": {
            field: {
                str(candidate): {
                    "events": fires[field][str(candidate)],
                    "share_of_settled": fires[field][str(candidate)] / settled if settled else 0.0,
                    "per_session": fires[field][str(candidate)] / sessions,
                }
                for candidate in CANDIDATES
            }
            for field in (*PRICE_FIELDS, "ANY")
        },
        "widest_open_revisions": {
            "threshold": "0.01",
            "distinct_instruments": len(wide_instruments),
            "sessions": {day.isoformat(): count for day, count in sorted(wide_sessions.items())},
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="measure_revisions")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if not (args.data / "bars.duckdb").is_file():
        print(f"UNAVAILABLE: no bar store at {args.data / 'bars.duckdb'}")
        return 2

    result = measure(args.data)
    document = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(document + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
