"""Command-line entry point. The complete surface (PRODUCT_SURFACES 3.1)."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC
from pathlib import Path

from swingdesk.application import universe as universe_builder
from swingdesk.application.pipeline import run
from swingdesk.contracts.reference import Instrument
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.market_data import BarStore
from swingdesk.platform.clock import FixedClock, SystemClock
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.presentation import notify, report
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
    scan.add_argument("--report-dir", type=Path, default=None,
                      help="where the run's report file is written; defaults to <data>/reports")
    scan.add_argument("--no-notify", action="store_true",
                      help="skip the local desktop notice (DR-011). The report is written either "
                           "way; this only suppresses the pop-up")

    args = parser.parse_args(argv)

    if args.command == "scan":
        from datetime import datetime

        if bool(args.tickers) == bool(args.universe):
            parser.error("pass either tickers or --universe, not both and not neither")

        # The mode is declared here and travels on the manifest. `--as-of` pins the clock and still
        # fetches fresh, so it is LIVE_AS_OF and not REPLAY however much it resembles one
        # (SYSTEM_MODES 7): it compares against nothing.
        clock = (
            FixedClock(datetime.fromisoformat(args.as_of).replace(tzinfo=UTC))
            if args.as_of
            else SystemClock()
        )
        mode = RunMode.LIVE_AS_OF if args.as_of else RunMode.LIVE
        registry = ParameterRegistry.load()
        instruments = [_instrument(t) for t in args.tickers]
        selection = None

        with (
            BarStore(args.data / "bars.duckdb") as store,
            Journal(args.data / "journal.duckdb") as journal,
            # Appendix T requires open positions evaluated before new candidates, and until
            # 2026-08-16 this command never opened a PositionStore at all - "positions run first"
            # was proven only in tests, never in the scheduled job. Passing a store with nothing
            # recorded in it is safe: `run()` reads `positions is not None` to decide whether the
            # positions step ran at all, so an empty store correctly makes `result.steps` read
            # `("positions", "candidates")` - "checked, and there were none" - rather than the
            # `("candidates",)` a caller with no store produces. Nothing currently writes to this
            # store outside tests (TODO.md 6b item 1); wiring it in is what stops that being the
            # reason a recorded position could never be evaluated by the scheduled run.
            PositionStore(args.data / "positions.duckdb") as positions,
        ):
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
                         mode=mode, lookback=args.lookback, universe=selection,
                         positions=positions)

            # Persist BEFORE printing, so the durable artifact exists even if writing to the
            # console then fails - the log has swallowed enough already.
            written: Path | None = None
            try:
                written = report.write(result, args.report_dir or args.data / "reports")
            except OSError as unwritable:
                # Not fatal, and not silent. The report WAS produced - it is on stdout below - so
                # the run did what `a.run_completes` measures, and resetting a 20-day counter over
                # a disk error would be a worse outcome than the error. But a delivery channel that
                # fails quietly is the exact defect this whole change is closing, so it is loud.
                print(f"report NOT persisted  {unwritable}", file=sys.stderr)

            print(report.render(result))
            if written is not None:
                print(f"\nreport written  {written}")

            # The notice goes LAST, after the report is on disk and on the console, so a run is
            # never delayed or endangered by the act of announcing itself.
            if not args.no_notify:
                notice = notify.notify(result.manifest.run_id, notify.Outcome.COMPLETE)
                if notice.delivered:
                    print("notice delivered")
                else:
                    # Loud, never fatal - same reasoning as the report write above, and the same
                    # rule: unnoticed non-delivery is the defect this exists to close.
                    print(f"notice NOT delivered  {notice.detail}", file=sys.stderr)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
