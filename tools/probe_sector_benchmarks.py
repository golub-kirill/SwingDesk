"""Is there a benchmark series per sector, and does the vendor itself confirm the pairing?

**What blocks `E05`, stated exactly.** `application/checklist.py` says comparing a candidate to its
sector needs a BENCHMARK series per sector and that *"no sector-to-index mapping exists"*. That is
true of this repository and says nothing about whether one can be had - the distinction
`AGENTS.md` §15 rule 2 draws, and the one that cost `DR-003` gap 1 its qualifier.

**This probe does not author the mapping. It measures whether the vendor agrees with a proposed
one**, so a decision record can cite a measurement rather than the author's recollection. The
proposal is the SPDR Select Sector family, which is one fund per sector and the same eleven sectors
`reference_data/classification.py` already canonicalises.

**Three things it reports, and the third is the one nobody would predict.**

1. **Is the proxy listed and eligible?** Read from `directory.duckdb` rather than assumed.
2. **Does the vendor's own look-through put the proxy in the sector it is proposed for?** Asked
   through `market_data/vendor_yahoo.fetch_classification` - the same call the daily run makes, so
   the answer is in the same vocabulary the sector cap already spends. A mapping confirmed by the
   classification source is a measurement; one confirmed by the author is a memory.
3. **Would `DR-006` §8.7's degeneracy guard REFUSE the proxy?** That guard exists because a
   short-maturity bond fund came back as healthcare 100.0%, and it is deliberately EXACT: exactly
   one sector at exactly 100%. A sector ETF is the instrument closest to that shape in the whole
   universe, so whether the eleven clear it is a real question with a measured answer, not a
   formality.

**What it does not settle.** It says nothing about whether a sector-relative comparison HELPS - that
is a study, and `PR-012` already found point-to-point relative strength decorative on one
cross-section. It also does not fetch bars: none of the eleven is in the bar store today, which is
the same alphabetical-prefix gap `DR-018` found for `SPY`, and closing it is a deliberate write to a
single-writer store rather than something a probe should do.

**Read-only, writes nothing, and paced.** One vendor call per second.

    python tools/probe_sector_benchmarks.py
    python tools/probe_sector_benchmarks.py --data data
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.reference import Exchange, Instrument
from swingdesk.reference_data.classification import canonical_sector, look_through

#: The proposed pairing: one canonical sector to the fund proposed as its benchmark. The sector keys
#: are exactly what `canonical_sector` produces, so a typo here cannot silently create a twelfth
#: bucket - the check below compares against that function's output rather than against this table.
PROPOSED: dict[str, str] = {
    "basic materials": "XLB",
    "communication services": "XLC",
    "consumer cyclical": "XLY",
    "consumer defensive": "XLP",
    "energy": "XLE",
    "financial services": "XLF",
    "healthcare": "XLV",
    "industrials": "XLI",
    "real estate": "XLRE",
    "technology": "XLK",
    "utilities": "XLU",
}

DELAY_SECONDS = 1.0


def listed(data: Path, symbols: list[str]) -> dict[str, str] | None:
    """Symbol to venue for those present in the directory, or None when it cannot be read."""
    store = data / "directory.duckdb"
    if not store.is_file():
        print(f"  directory: UNAVAILABLE - no directory.duckdb under {data}")
        return None
    try:
        import duckdb
    except ImportError:
        print("  directory: UNAVAILABLE - duckdb is not importable here")
        return None
    try:
        connection = duckdb.connect(str(store), read_only=True)
    except duckdb.IOException as error:
        # Single-writer by ADR-0004: a held store is UNAVAILABLE, never a traceback.
        print(f"  directory: UNAVAILABLE - {error}")
        return None
    try:
        query = ("SELECT symbol, any_value(venue) FROM directory "
                 "WHERE symbol IN ? AND NOT is_test_issue GROUP BY symbol")
        return {str(row[0]): str(row[1]) for row in connection.execute(query, [symbols]).fetchall()}
    finally:
        connection.close()


def stock_position(symbol: str) -> float | None:
    """The share of a fund held in EQUITY, as the vendor reports it, or None when it does not.

    `DR-006` §8.7's guard is about a fund that holds no equity at all. It infers that from the shape
    of the sector weights; this asks for it. Kept in the probe rather than in `src/` on purpose -
    measuring a discriminator is not the same act as adopting one, and adopting one amends an
    accepted decision record.
    """
    import yfinance as yf

    try:
        classes = yf.Ticker(symbol).funds_data.asset_classes or {}
        value = classes.get("stockPosition")
        return float(value) if value is not None else None
    except Exception:  # noqa: BLE001 - a probe reports "not answered", never raises
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="probe_sector_benchmarks", description=__doc__)
    parser.add_argument("--data", default=os.environ.get("SWINGDESK_DATA", "data"),
                        help="the directory holding directory.duckdb")
    args = parser.parse_args(argv)

    from swingdesk.market_data.vendor_yahoo import VendorUnavailable, fetch_classification

    print(f"probe_sector_benchmarks: {len(PROPOSED)} proposed pairing(s)\n")

    known = listed(Path(args.data), sorted(PROPOSED.values()))
    if known is not None:
        absent = sorted(symbol for symbol in PROPOSED.values() if symbol not in known)
        print(f"  directory: {len(PROPOSED) - len(absent)} of {len(PROPOSED)} listed and not a "
              f"test issue" + (f"; absent: {', '.join(absent)}" if absent else ""))

    # One clock read, at the top, for every classification in this run. A per-call `now` would put
    # rows on different knowledge times for one measurement (`AGENTS.md` §12's partially pinned
    # clock, one layer down).
    asked_at = datetime.now(UTC)

    print("\n  sector                    proxy   vendor's dominant sector        weight   guard"
          "    stock%")
    confirmed, contradicted, unavailable = 0, 0, 0
    refused: list[str] = []
    for index, (sector, symbol) in enumerate(sorted(PROPOSED.items())):
        if index:
            time.sleep(DELAY_SECONDS)
        instrument = Instrument(id=symbol, ticker=symbol, exchange=Exchange.NYSE, currency="USD")
        try:
            classification = fetch_classification(instrument, asked_at)
        except VendorUnavailable as error:
            unavailable += 1
            print(f"  {sector:<24}  {symbol:<6}  UNAVAILABLE - {error}")
            continue

        merged: dict[str, Decimal] = {}
        for weight in classification.weights:
            key = canonical_sector(weight.sector)
            merged[key] = merged.get(key, Decimal(0)) + weight.weight
        if not merged:
            unavailable += 1
            print(f"  {sector:<24}  {symbol:<6}  the vendor served no sector weights")
            continue

        dominant = max(merged, key=lambda key: merged[key])
        share = merged[dominant]
        exposure = look_through(classification, symbol)
        guard = "refused" if exposure.unavailable else "clears"
        if exposure.unavailable:
            refused.append(symbol)
        agrees = "=" if dominant == sector else "!"
        if dominant == sector:
            confirmed += 1
        else:
            contradicted += 1
        equity = stock_position(symbol)
        held = "  n/a" if equity is None else f"{equity:>5.1%}"
        print(f"  {sector:<24}  {symbol:<6}  {agrees} {dominant:<28} {share:>6.1%}   "
              f"{guard:<7}  {held}")

    print(f"\n  confirmed by the vendor: {confirmed}, contradicted: {contradicted}, "
          f"unavailable: {unavailable}")

    if refused:
        # The finding this column exists for. `DR-006` §12.1 argued the guard is EXACT so that a
        # genuine sector ETF - "legitimately almost all one sector" - would clear it. Measured
        # here: the ones that do not clear it report EXACTLY one sector, which is the same shape a
        # fund holding no equity produces. The guard infers "holds no equity" from the SHAPE of the
        # sector weights, and the vendor serves that fact directly in `asset_classes`, which is
        # `AGENTS.md` §12's proxy trap with a measurement available beside it.
        print(f"\n  {len(refused)} proxy(ies) REFUSED by DR-006 8.7's degeneracy guard: "
              f"{', '.join(sorted(refused))}")
        print("  Their stock% above is what makes this worth reading: the guard's stated reason is "
              "'a fund holding no equity at all', and every refused proxy above holds almost "
              "nothing else. Compare NEAR, the bond fund the guard was written for:")
        near = stock_position("NEAR")
        print(f"    NEAR stock%: {'n/a' if near is None else f'{near:.1%}'}")
        print("  Changing the guard is an amendment to an accepted decision record and is NOT this "
              "probe's business (AGENTS.md sections 8 and 14). The measurement is.")

    print("\nprobe_sector_benchmarks: this measures the PAIRING only. Whether a sector-relative "
          "comparison improves a decision is a study, and none of the eleven has bars stored - "
          "that is a deliberate write to a single-writer store, not a probe's business.")
    return 0 if contradicted == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
