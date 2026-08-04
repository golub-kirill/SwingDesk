"""Command-line entry point. The complete surface (PRODUCT_SURFACES 3.1)."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC
from pathlib import Path

from swingdesk.application import universe as universe_builder
from swingdesk.application.pipeline import run
from swingdesk.contracts.reference import Instrument
from swingdesk.journal_evidence.journal import Journal
from swingdesk.market_data import BarStore
from swingdesk.platform.clock import FixedClock, SystemClock
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.presentation import report
from swingdesk.reference_data import calendar as cal
from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.trade_management.sizing import Refusal

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
    scan.add_argument("tickers", nargs="*", help="e.g. AAPL CNQ.TO; omit and pass --universe")
    scan.add_argument("--universe", action="store_true",
                      help="take candidates from the DR-003 liquidity rule instead of a list")
    scan.add_argument("--limit", type=int, default=None,
                      help="cap the universe by dollar volume. A cap is a RANKING, not the rule, "
                           "and the report says so")
    scan.add_argument("--data", type=Path, default=DEFAULT_DATA)
    scan.add_argument("--lookback", default="1y")
    scan.add_argument("--as-of", default=None,
                      help="ISO instant; pins the clock so the run is reproducible")

    args = parser.parse_args(argv)

    if args.command == "scan":
        from datetime import datetime

        if bool(args.tickers) == bool(args.universe):
            parser.error("pass either tickers or --universe, not both and not neither")

        clock = (
            FixedClock(datetime.fromisoformat(args.as_of).replace(tzinfo=UTC))
            if args.as_of
            else SystemClock()
        )
        registry = ParameterRegistry.load()
        instruments = [_instrument(t) for t in args.tickers]
        selection = None

        with BarStore(args.data / "bars.duckdb") as store, Journal(args.data / "journal.duckdb") as journal:
            if args.universe:
                built = universe_builder.rule_from_registry(registry)
                if isinstance(built, Refusal):
                    # Fail closed and say which parameter. A universe that silently admitted
                    # everything would be worse than no run at all.
                    print(f"universe REFUSED  {built}", file=sys.stderr)
                    return 2
                rule, parameters = built
                with DirectoryStore(args.data / "directory.duckdb") as directory:
                    selection = universe_builder.select(
                        directory, store, rule, clock.now(),
                        parameters=parameters, limit=args.limit,
                    )
                if not selection.members:
                    print(report.render_empty_universe(selection), file=sys.stderr)
                    return 3

            result = run(instruments, clock, registry, store, journal,
                         lookback=args.lookback, universe=selection)
            print(report.render(result))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
