"""Command-line entry point. The complete surface (PRODUCT_SURFACES 3.1)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from swingdesk.contracts.reference import Instrument
from swingdesk.journal_evidence.journal import Journal
from swingdesk.market_data import BarStore
from swingdesk.platform.clock import FixedClock, SystemClock
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.presentation import report
from swingdesk.presentation.pipeline import run
from swingdesk.reference_data import calendar as cal

DEFAULT_DATA = Path("data")


def _instrument(ticker: str) -> Instrument:
    exchange = cal.exchange_for(ticker)
    base = ticker.upper().removesuffix(".TO")
    return Instrument(
        id=base if exchange.value == "NYSE" else f"{base}.TO",
        ticker=base,
        exchange=exchange,
        currency="USD" if exchange.value == "NYSE" else "CAD",
    )


def _force_utf8_output() -> None:
    """Windows consoles default to cp1252, which cannot encode the course's own vocabulary.

    Skip reasons and code descriptions are quoted from a Russian-language source, so a report that
    cannot render them is a report that crashes exactly when it has something to say.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    parser = argparse.ArgumentParser(prog="swingdesk", description="Swing-trading decision support")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="run the daily pipeline and produce a report")
    scan.add_argument("tickers", nargs="+", help="e.g. AAPL CNQ.TO")
    scan.add_argument("--data", type=Path, default=DEFAULT_DATA)
    scan.add_argument("--lookback", default="1y")
    scan.add_argument("--as-of", default=None,
                      help="ISO instant; pins the clock so the run is reproducible")

    args = parser.parse_args(argv)

    if args.command == "scan":
        from datetime import datetime, timezone

        clock = (
            FixedClock(datetime.fromisoformat(args.as_of).replace(tzinfo=timezone.utc))
            if args.as_of
            else SystemClock()
        )
        registry = ParameterRegistry.load()
        instruments = [_instrument(t) for t in args.tickers]

        with BarStore(args.data / "bars.duckdb") as store, Journal(args.data / "journal.duckdb") as journal:
            result = run(instruments, clock, registry, store, journal, lookback=args.lookback)
            print(report.render(result))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
