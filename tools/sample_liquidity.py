"""Measure the dollar-volume distribution across a seeded random sample of US listings.

Exists to inform DR-003. A liquidity threshold picked without looking at the distribution is a
number someone liked; picked from the distribution it is at least a number with a reason.

The honest caveat, recorded here and in DR-003: choosing a threshold after seeing the data is
selection on the data. It is acceptable here because dollar volume involves no forward returns, so
it cannot leak outcome information, and PR-001's design is frozen independently. It is not nothing,
and it is stated rather than glossed.

Network tool. Never imported by anything in src/, never run in CI.

    python tools/sample_liquidity.py --sample 200 --seed 20260802
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.market import Interval  # noqa: E402
from swingdesk.market_data import VendorUnavailable, vendor_yahoo  # noqa: E402
from swingdesk.reference_data import universe  # noqa: E402

DIRECTORY = {
    "nasdaq": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "other": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}


def _download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "swingdesk-research/0.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser(prog="sample_liquidity")
    parser.add_argument("--sample", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260802,
                        help="recorded with the output; the sample must be reproducible")
    parser.add_argument("--window", type=int, default=20, help="ADTV window in bars")
    parser.add_argument("--out", type=Path,
                        default=Path("docs/decisions/measurements/liquidity-sample.json"))
    args = parser.parse_args()

    entries = [
        *universe.parse_nasdaq_listed(_download(DIRECTORY["nasdaq"])),
        *universe.parse_other_listed(_download(DIRECTORY["other"])),
    ]
    eligible = sorted((e for e in entries if e.is_eligible), key=lambda e: e.symbol)
    print(f"directory: {len(entries)} rows, {len(eligible)} eligible")

    rng = random.Random(args.seed)
    sample = sorted(rng.sample(eligible, min(args.sample, len(eligible))), key=lambda e: e.symbol)

    as_of = datetime.now(timezone.utc)
    measured: list[dict] = []
    failed = 0
    for index, entry in enumerate(sample, start=1):
        instrument = universe.to_instrument(entry)
        try:
            series = vendor_yahoo.fetch(instrument, Interval.DAY, as_of, period="6mo")
        except (VendorUnavailable, Exception) as error:  # noqa: BLE001 - a research tool
            failed += 1
            print(f"  [{index}/{len(sample)}] {entry.symbol}: {type(error).__name__}")
            continue

        adtv = universe.average_dollar_volume(series, args.window)
        measured.append({
            "symbol": entry.symbol,
            "venue": entry.venue,
            "is_etf": entry.is_etf,
            "bars": len(series.bars),
            "close": str(series.bars[-1].close) if series.bars else None,
            "adtv": str(adtv) if adtv is not None else None,
        })
        if index % 25 == 0:
            print(f"  [{index}/{len(sample)}] ok={len(measured)} failed={failed}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "seed": args.seed,
                "sample_requested": args.sample,
                "adtv_window": args.window,
                "directory_rows": len(entries),
                "eligible_rows": len(eligible),
                "measured": len(measured),
                "fetch_failures": failed,
                "as_of": as_of.isoformat(),
                "rows": measured,
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {args.out}: {len(measured)} measured, {failed} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
