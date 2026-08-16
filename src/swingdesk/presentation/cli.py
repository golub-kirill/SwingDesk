"""Command-line entry point. The complete surface (PRODUCT_SURFACES 3.1)."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from swingdesk.application import universe as universe_builder
from swingdesk.application.pipeline import run
from swingdesk.contracts.position import Position
from swingdesk.contracts.reference import Instrument
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.market_data import BarStore
from swingdesk.platform.clock import FixedClock, SystemClock
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.presentation import report
from swingdesk.reference_data import calendar as cal
from swingdesk.reference_data.directory import DirectoryStore

# `_costs_per_share` carries a leading underscore because `sizing.py` never expected a second
# caller - and it still cannot be promoted to a public name today, because `sizing.py` is one of
# the three files frozen since 2026-08-11 (HANDOFF.md 5) and a rename is a change to it regardless
# of size. Reused as-is rather than duplicating DR-010's formula, which would create the exact
# two-implementations-of-one-number problem AGENTS.md 10.5 exists to prevent. Promote this to a
# public name once the freeze lifts (TODO.md).
from swingdesk.trade_management.sizing import Refusal, _costs_per_share

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

    opened = sub.add_parser(
        "open-position",
        help="record a position already opened at the broker (D1: this never places the order)",
    )
    opened.add_argument("ticker", help="e.g. AAPL or CNQ.TO")
    opened.add_argument("--entry", type=Decimal, required=True, help="fill price, per share")
    opened.add_argument("--shares", type=int, required=True)
    opened.add_argument("--stop", type=Decimal, required=True, help="initial stop, per share")
    opened.add_argument("--opened-on", default=None,
                        help="ISO date the fill happened; defaults to today")
    opened.add_argument("--costs-per-share", type=Decimal, default=None,
                        help="override the DR-010 round-trip cost estimate with the real one, "
                             "once a broker confirmation names it")
    opened.add_argument("--strategy", default="unspecified")
    opened.add_argument("--position-id", default=None,
                        help="override the default POS-<instrument id>-<opened-on> identity")
    opened.add_argument("--data", type=Path, default=DEFAULT_DATA)
    opened.add_argument("--as-of", default=None,
                        help="ISO instant this is being recorded as of; defaults to now")

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
            print(report.render(result))
        return 0

    if args.command == "open-position":
        from datetime import date as date_cls
        from datetime import datetime

        # This RECORDS a fact, and computes nothing that would let it be mistaken for one (D1).
        # `--as-of` is when the record is being MADE, not when the fill happened - `opened_on`
        # carries that, kept separately on purpose (bitemporal store: event time vs knowledge time).
        clock = (
            FixedClock(datetime.fromisoformat(args.as_of).replace(tzinfo=UTC))
            if args.as_of
            else SystemClock()
        )
        now = clock.now()
        opened_on = date_cls.fromisoformat(args.opened_on) if args.opened_on else now.date()
        instrument = _instrument(args.ticker)
        registry = ParameterRegistry.load()

        if args.costs_per_share is not None:
            costs = args.costs_per_share
        else:
            costs_result = _costs_per_share(args.entry, instrument.currency, registry)
            if isinstance(costs_result, Refusal):
                # Same fail-closed rule sizing itself follows: a missing cost parameter is refused,
                # never assumed. `--costs-per-share` is the owner's own escape hatch once a broker
                # confirmation names the real number.
                print(f"costs REFUSED  {costs_result}", file=sys.stderr)
                return 2
            costs, _bp_use, _floor_use = costs_result

        position_id = args.position_id or f"POS-{instrument.id}-{opened_on.isoformat()}"
        try:
            position = Position(
                position_id=position_id, version=1, instrument_id=instrument.id,
                opened_on=opened_on, entry_price=args.entry, shares=args.shares,
                initial_stop=args.stop, current_stop=args.stop,
                initial_costs_per_share=costs, strategy=args.strategy, knowledge_time=now,
            )
        except ValidationError as invalid:
            print(f"position REFUSED  {invalid}", file=sys.stderr)
            return 2

        with PositionStore(args.data / "positions.duckdb") as store:
            try:
                store.record(position)
            except ValueError as duplicate:
                # Append-only: a second `open-position` for the same instrument on the same date
                # is refused rather than silently duplicated - the store's own guard, not a new one
                # written here (positions.py: "Rejects a version that already exists").
                print(f"position REFUSED  {duplicate}", file=sys.stderr)
                return 2

        print(
            f"recorded {position.position_id}: {position.shares} sh {instrument.id} @ "
            f"{position.entry_price}, stop {position.initial_stop}, costs {costs}/share"
        )
        print(
            f"  R denominator {position.initial_risk_per_share}/share "
            f"({position.initial_risk} total) - this is what every R on this position is "
            f"measured against, and it never changes (RISK_SPEC 2)"
        )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
