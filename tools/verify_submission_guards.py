"""Run every guard a submission runs, in its order, against the LIVE state. Sends nothing.

**The complement to `probe_paper_order.py`, and the opposite trade-off.** That probe proves the
write path by putting one unfillable order on the wire, because some defects only a real order can
find — `DR-027` §9 records three of them. This gets as close to a submission as it is possible to
get **without one**: the real pipeline, the real book, two GETs at the venue, and every guard in
`_submit`'s order, reporting what would be sent and stopping there.

**Why it exists.** Each guard was built against fixtures and against an EMPTY book. On 2026-09-03,
the first day a real position existed, running them by hand against the live book is what found
`DR-034` §3.1 — a position opened in the still-running session read as *unpriced* and would have
halted every submission on the evening of the first fill. The ad-hoc script that found it is this
one, made permanent, because `AGENTS.md` §10.6's rule is that a fact a tool can derive is derived by
that tool.

**It cannot submit.** No write verb is reachable from here: it opens a client for `positions` and
`open_orders`, both `GET`, and calls the pure guards. `entry_order` is called to BUILD the payloads
so their prices can be checked against the venue's tick (`DR-033`), and the built orders are printed
rather than sent.

**A run is journalled.** It calls the same `pipeline.run` the scheduled pass does, so it writes
decisions and spends a run id. That is deliberate — a guard check against a run this system did not
actually perform would be evidence about a fixture.

    PYTHONPATH=$PWD/src python tools/verify_submission_guards.py --data data
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from swingdesk import broker as broker_pkg
from swingdesk.application import universe as universe_builder
from swingdesk.application.pipeline import run
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.market_data import BarStore, vendor_yahoo
from swingdesk.market_data.retry import RetryingFetcher
from swingdesk.platform.clock import FixedClock, SystemClock
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.presentation import cli
from swingdesk.reference_data.classification import ClassificationStore
from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.trade_management import drawdown, portfolio
from swingdesk.trade_management.sizing import RiskSnapshot

#: Exit codes, and the middle one is the point. `2` is not "the tool failed" - it is "a guard would
#: stop tonight's submission", which is a real answer and often the correct one.
OK, WOULD_STOP, UNAVAILABLE = 0, 2, 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run every submission guard against the live state. Sends nothing.")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--as-of", default=None,
                        help="ISO instant; pins the clock so the check is reproducible")
    args = parser.parse_args(argv)

    clock = (
        FixedClock(datetime.fromisoformat(args.as_of).replace(tzinfo=UTC))
        if args.as_of else SystemClock()
    )
    registry = ParameterRegistry.load()

    try:
        policy = broker_pkg.load_policy()
        client = broker_pkg.open_client(policy)
    except broker_pkg.PolicyRefused as refused:
        print(f"guards REFUSED  {refused}", file=sys.stderr)
        return UNAVAILABLE
    except broker_pkg.CredentialsMissing as missing:
        print(f"guards UNAVAILABLE  {missing}", file=sys.stderr)
        return UNAVAILABLE
    write = policy.write
    if write is None:
        print("guards REFUSED  the committed policy grants no write permission", file=sys.stderr)
        return UNAVAILABLE

    with (
        BarStore(args.data / "bars.duckdb") as store,
        Journal(args.data / "journal.duckdb") as journal,
        PositionStore(args.data / "positions.duckdb") as positions,
        ClassificationStore(args.data / "classifications.duckdb") as classifications,
    ):
        built = universe_builder.rule_from_registry(registry)
        if not isinstance(built, tuple):
            print(f"guards REFUSED  {built}", file=sys.stderr)
            return UNAVAILABLE
        rule, parameters = built
        with DirectoryStore(args.data / "directory.duckdb") as directory:
            selection = universe_builder.select(
                directory, store, rule, clock.now(), parameters=parameters, limit=None,
            )
        result = run(
            [], clock, registry, store, journal, mode=RunMode.LIVE, lookback="1y",
            universe=selection, positions=positions, classifications=classifications,
            fetcher=RetryingFetcher(vendor_yahoo.fetch),
            actions_fetcher=vendor_yahoo.fetch_actions,
        )

        # AFTER the run, deliberately. The run writes bars, and every store here is bitemporal - a
        # clock read before it would answer as of a moment those bars did not exist yet, and the
        # drawdown would report UNAVAILABLE against a book it can perfectly well value. That is the
        # exact shape of the mistake this tool exists to catch, and it caught it in its own draft.
        now = clock.now()

        try:
            held = client.positions(now)
            live = client.open_orders(now)
        except broker_pkg.BrokerUnavailable as unavailable:
            print(f"guards UNAVAILABLE  the venue could not be read: {unavailable}",
                  file=sys.stderr)
            return UNAVAILABLE

        book = positions.open_as_of(now)
        tradeable = [
            outcome for outcome in result.outcomes
            if outcome.decision is not None and outcome.decision.decision == "Trade"
            and isinstance(outcome.risk, RiskSnapshot)
        ]
        print(f"\nrun {result.manifest.run_id}")
        print(f"book {len(book)} open · venue {len(held)} position(s), {len(live)} live order(s) "
              f"· {len(tradeable)} Trade decision(s) eligible\n")

        stopped: list[str] = []

        # THE SWITCH IS REPORTED AND NEVER TREATED AS A GUARD THAT PASSED. This tool submits
        # nothing, so a stopped switch does not change what it can check - but printing
        # "WOULD SUBMIT" beside a disarmed venue would answer a question nobody asked. The line
        # says which it is and the verdict at the end says so too.
        arming = broker_pkg.read_arming(args.data, write)
        print(f"kill switch - {'ARMED' if arming.armed else 'STOPPED'} ({arming.reason})\n")

        print("reconcile - the book and the venue describe the same positions (DR-035)")
        agreement = broker_pkg.reconcile(book, held, venue=policy.label, market=policy.market)
        if agreement.agrees:
            print(f"   PASS  {len(agreement.agreed)} agreed, 0 divergences")
        else:
            stopped.append(f"{agreement.code} - {len(agreement.divergences)} divergence(s)")
            for divergence in agreement.divergences:
                print(f"   STOP  {divergence.instrument_id} ({divergence.reason}) "
                      f"{divergence.detail[:100]}")

        print("\nprotection - every open position's stop is standing at the venue (DR-036)")
        naked = broker_pkg.unprotected(book, live, policy.market)
        if naked:
            stopped.append(f"{broker_pkg.MISMATCH_CODE} - {len(naked)} position(s) unprotected")
            for finding in naked:
                print(f"   STOP  {finding.instrument_id}  {finding.reason[:110]}")
        elif book:
            print(f"   PASS  {len(book)} position(s), each with its stop standing")
        else:
            print("   PASS  nothing held")

        print("\nuncommitted exposure - nothing at the venue the caps have not seen (DR-027 §11)")
        sent_ids = journal.sent_client_order_ids()
        ours = broker_pkg.ours(live, sent_ids)
        unaccounted = broker_pkg.uncommitted_exposure(
            book, held, live, policy.market, sent_order_ids=sent_ids)
        if unaccounted:
            stopped.append(f"{broker_pkg.MISMATCH_CODE} - {len(unaccounted)} untraceable symbol(s)")
            print(f"   STOP  untraceable: {', '.join(unaccounted)}")
        else:
            print(f"   PASS  clear · {len(ours)} live order(s) recognised as ours (DR-032)")

        print("\nk.drawdown_pause - the only ratified `live` criterion (DR-034)")
        # PRIVATE ON PURPOSE, all three of them. This tool exists to exercise the submission
        # path's OWN steps; a public wrapper would be a second entry point that could drift from
        # the one `_submit` takes, and then a green check would be evidence about the wrapper.
        fall = cli._drawdown_now(positions, store, registry, now, policy.market)  # noqa: SLF001
        limit, _use = registry.decimal_value("validation.max_allowable_drawdown")
        if isinstance(fall, drawdown.Unavailable):
            stopped.append(f"the drawdown could not be measured: {fall.reason}")
            print(f"   STOP  UNAVAILABLE  {fall.reason}")
        elif fall.breaches(limit):
            stopped.append(f"k.drawdown_pause - {fall.percent}% past a {limit}% limit")
            print(f"   STOP  {fall.percent}% of a {limit}% limit  (peak {fall.peak})")
        else:
            print(f"   PASS  {fall.percent}% of a {limit}% limit  "
                  f"(peak {fall.peak}, {len(fall.curve)} session(s) on the curve)")

        print("\nthe ratified caps, across this run and what is already resting (DR-027 §10)")
        r_unit = (result.capacity.book.r_unit
                  if isinstance(result.capacity, portfolio.Capacity) else None)
        committed = cli._committed_by_live_orders(  # noqa: SLF001
            ours, journal, registry, result, r_unit=r_unit)
        # `InstrumentOutcome`, spelled loosely on purpose: importing a pipeline type into a tool
        # would pin this file to the layer it is checking rather than to the guards it checks.
        submittable: list[Any] = []
        if isinstance(committed, str):
            stopped.append(committed)
            print(f"   STOP  {committed}")
        else:
            allocation = cli._allocate(result, tradeable, committed)  # noqa: SLF001
            if isinstance(allocation, str):
                stopped.append(allocation)
                print(f"   STOP  {allocation}")
            else:
                submittable, passed_over = allocation
                resting_r = sum((entry.requested_r for entry in committed), Decimal(0))
                if isinstance(result.capacity, portfolio.Capacity):
                    print(f"   book holds {result.capacity.book.count} position(s) at "
                          f"{result.capacity.book.open_risk_r:.2f}R; resting orders hold "
                          f"{resting_r:.2f}R more")
                print(f"   PASS  {len(submittable)} within the caps, {len(passed_over)} passed over")

        print("\nthe payloads themselves - every price on the venue's tick (DR-033)")
        session = broker_pkg.trading_session(policy.market, now)
        for outcome in submittable:
            risk = outcome.risk
            assert isinstance(risk, RiskSnapshot)
            try:
                order = broker_pkg.entry_order(
                    instrument_id=outcome.instrument.id, shares=risk.shares,
                    limit_price=risk.entry, stop_price=risk.stop,
                    target=broker_pkg.target_price(risk.entry, risk.risk_per_share, registry),
                    session_date=session, write=write, market=policy.market,
                )
            except Exception as refused:  # noqa: BLE001 - every refusal is a real answer here
                stopped.append(f"{outcome.instrument.id}: {refused}")
                print(f"   STOP  {outcome.instrument.id}  {refused}")
                continue
            aligned = all(price % write.tick_size == 0 for price in
                          (order.limit_price, order.stop_price, order.target_price))
            ordered = order.stop_price < order.limit_price < order.target_price
            if not (aligned and ordered):
                stopped.append(f"{order.symbol}: a price is off the tick or the legs are out of order")
            print(f"   {'PASS ' if aligned and ordered else 'STOP '} {order.symbol:<6} "
                  f"{order.shares} sh  limit {order.limit_price}  stop {order.stop_price}  "
                  f"target {order.target_price}  {order.client_order_id}")
        if not submittable:
            print("   (nothing within the caps to build)")

    print()
    if stopped:
        print(f"WOULD NOT SUBMIT - {len(stopped)} guard(s) would stop tonight's pass:")
        for reason in stopped:
            print(f"   {reason[:150]}")
        print("\nNothing was sent. No write verb was used.")
        return WOULD_STOP

    if not arming.armed:
        print(f"Every guard passes and {len(submittable)} order(s) fit the caps, but the switch is "
              f"STOPPED, so a real pass would send nothing.")
    else:
        print(f"WOULD SUBMIT {len(submittable)} order(s), and every guard passes.")
    print("Nothing was sent. No write verb was used.")
    return OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
