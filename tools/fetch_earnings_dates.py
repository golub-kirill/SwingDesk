"""When did each company report its results? Read from SEC EDGAR, as the company filed it.

**The source is the filing, not a calendar vendor.** A US-listed company that releases quarterly
results furnishes a Form 8-K carrying **Item 2.02, Results of Operations and Financial
Condition**, and EDGAR stamps the instant it accepted it. That instant is point-in-time by
construction - it is when the market could first read the filing - and it is free, official and
reaches back to 2001. Built for `PR-039` (does a hold that spans an announcement lose beyond 1R?).

**What it does not see, and says so rather than guessing:**

  * a ticker with no CIK in SEC's current map - a delisted name, most funds, some foreign issuers -
    is written to the coverage file as `no_cik`;
  * a registrant that files no 8-K Item 2.02 - every fund, and foreign private issuers, who report
    on Form 6-K with no item codes - is `no_item_202`, which for a fund is the truth (a fund has no
    earnings) and for a foreign issuer is a blind spot;
  * the press release itself. The 8-K usually follows it within minutes, so the acceptance instant
    lands in the same pre-open, in-session or after-close slot; the study reads the SLOT, never the
    minute.

Read-only against EDGAR, under SEC's fair-access policy: a descriptive `User-Agent` carrying the
contact in `SWINGDESK_EDGAR_CONTACT` if the operator set one, and never more than eight requests a
second.

    python tools/fetch_earnings_dates.py --symbols AAPL MSFT --out <dir>
    python tools/fetch_earnings_dates.py --from-trades <trade log.csv> --out <dir> --directory <store>
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

TICKER_MAP = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
PAGE = "https://data.sec.gov/submissions/{name}"

#: SEC's fair-access ceiling is ten a second; eight leaves room for a clock that runs fast.
MIN_INTERVAL = 1 / 8

#: Filings older than this are not read: every trade this was built for entered after 2016.
FIRST_YEAR = 2015

RESULTS_ITEM = "2.02"


def user_agent() -> str:
    """A descriptive agent, with a contact only if the operator supplied one - never invented."""
    contact = os.environ.get("SWINGDESK_EDGAR_CONTACT", "").strip()
    base = "SwingDesk research (earnings dates)"
    return f"{base} ({contact})" if contact else f"{base} (contact not configured)"


_last_request = [0.0]


def get_json(url: str) -> Any:
    """One GET, paced, with both headers `www.sec.gov` requires (`tools/probe_edgar.py`)."""
    wait = MIN_INTERVAL - (time.monotonic() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    _last_request[0] = time.monotonic()
    request = urllib.request.Request(
        url, headers={"User-Agent": user_agent(), "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def ticker_map(payload: dict[str, Any]) -> dict[str, int]:
    """SEC's current ticker-to-CIK map, upper-cased, as served. A missing ticker is left out."""
    return {str(row["ticker"]).upper(): int(row["cik_str"]) for row in payload.values()}


def cik_for(symbol: str, ciks: dict[str, int]) -> int | None:
    """The CIK for a ticker as the bar store spells it.

    SEC writes a share class with a HYPHEN (`BRK-B`) and the store writes it with a DOT (`BRK.B`),
    so the first fetch found no CIK for `BRK.B`, `BF.B`, `HEI.A` or `MOG.A` and would have filed
    four companies that report every quarter as unknown.
    """
    upper = symbol.upper()
    return ciks.get(upper, ciks.get(upper.replace(".", "-")))


def etf_flags(directory: Path) -> dict[str, bool]:
    """Which symbols the project's own symbol directory marks as ETFs - read from a COPY.

    A fund files no results, so a fund held through a quarter is truly unexposed; a company whose
    results cannot be dated is not. The directory is the store's word for which is which.
    """
    import shutil
    import tempfile

    import duckdb

    with tempfile.TemporaryDirectory() as scratch:
        copy = Path(scratch) / "directory.duckdb"
        shutil.copy(directory, copy)
        connection = duckdb.connect(str(copy), read_only=True)
        try:
            rows = connection.execute(
                "SELECT symbol, bool_or(is_etf) FROM directory GROUP BY symbol").fetchall()
        finally:
            connection.close()
    return {str(symbol): bool(flag) for symbol, flag in rows}


def results_filings(block: dict[str, list[Any]]) -> list[dict[str, str]]:
    """The 8-K filings carrying Item 2.02 in one block of a submissions record.

    `block` is `filings.recent`, or one of the older pages, which share its column layout. An
    amendment (`8-K/A`) is left out: it restates a filing already counted, and counting it would
    move the announcement to the day of the correction.
    """
    forms = block.get("form", [])
    out = []
    for index, form in enumerate(forms):
        if form != "8-K":
            continue
        items = str(block.get("items", [""] * len(forms))[index] or "")
        if RESULTS_ITEM not in {item.strip() for item in items.split(",")}:
            continue
        out.append({
            "accession": str(block["accessionNumber"][index]),
            "accepted": str(block["acceptanceDateTime"][index]),
            "filed": str(block["filingDate"][index]),
            "items": items,
        })
    return out


def announcements(cik: int) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Every Item 2.02 8-K a registrant filed since `FIRST_YEAR`, and what kind of entity it is."""
    record = get_json(SUBMISSIONS.format(cik=cik))
    about = {"entity_type": record.get("entityType"), "sic": record.get("sic"),
             "sic_description": record.get("sicDescription"), "name": record.get("name")}
    filings = results_filings(record.get("filings", {}).get("recent", {}))
    for page in record.get("filings", {}).get("files", []):
        if str(page.get("filingTo", "9999"))[:4] < str(FIRST_YEAR):
            continue
        filings += results_filings(get_json(PAGE.format(name=page["name"])))
    kept = [f for f in filings if f["filed"][:4] >= str(FIRST_YEAR)]
    return about, sorted(kept, key=lambda f: f["accepted"])


def symbols_from_trades(path: Path) -> list[str]:
    with path.open(encoding="utf-8") as handle:
        return sorted({row["instrument_id"] for row in csv.DictReader(handle)})


def fetch_all(symbols: Iterable[str], out: Path,
              etfs: dict[str, bool] | None = None) -> dict[str, int]:
    """Write `announcements.csv` and `coverage.csv` under `out`; return the coverage counts."""
    out.mkdir(parents=True, exist_ok=True)
    ciks = ticker_map(get_json(TICKER_MAP))
    flags = etfs or {}
    counts = {"symbols": 0, "no_cik": 0, "no_item_202": 0, "with_announcements": 0,
              "unreachable": 0, "announcements": 0}
    with (out / "announcements.csv").open("w", newline="", encoding="utf-8") as found, \
            (out / "coverage.csv").open("w", newline="", encoding="utf-8") as seen:
        rows = csv.writer(found)
        rows.writerow(["symbol", "cik", "accepted", "filed", "accession"])
        status = csv.writer(seen)
        status.writerow(["symbol", "cik", "status", "count", "is_etf", "entity_type", "sic",
                         "sic_description", "name"])
        for symbol in symbols:
            counts["symbols"] += 1
            cik = cik_for(symbol, ciks)
            etf = "" if symbol not in flags else str(flags[symbol]).lower()
            if cik is None:
                counts["no_cik"] += 1
                status.writerow([symbol, "", "no_cik", 0, etf, "", "", "", ""])
                continue
            try:
                about, filings = announcements(cik)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as error:
                counts["unreachable"] += 1
                status.writerow([symbol, cik, f"unreachable: {error}", 0, etf, "", "", "", ""])
                continue
            for filing in filings:
                rows.writerow([symbol, cik, filing["accepted"], filing["filed"],
                               filing["accession"]])
            kind = "with_announcements" if filings else "no_item_202"
            counts[kind] += 1
            counts["announcements"] += len(filings)
            status.writerow([symbol, cik, kind, len(filings), etf, about["entity_type"],
                             about["sic"],
                             about["sic_description"], about["name"]])
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--symbols", nargs="+", help="tickers as the bar store spells them")
    source.add_argument("--from-trades", type=Path, help="a trade log with an instrument_id column")
    parser.add_argument("--out", type=Path, required=True, help="directory for the two CSV files")
    parser.add_argument("--directory", type=Path, default=None,
                        help="the symbol directory store, read from a copy, to mark ETFs")
    args = parser.parse_args()
    symbols = args.symbols or symbols_from_trades(args.from_trades)
    print(f"fetch_earnings_dates: {len(symbols)} symbol(s), User-Agent {user_agent()!r}")
    counts = fetch_all(symbols, args.out, etf_flags(args.directory) if args.directory else None)
    print("  " + "  ".join(f"{key} {value}" for key, value in counts.items()))
    return 0 if counts["unreachable"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
