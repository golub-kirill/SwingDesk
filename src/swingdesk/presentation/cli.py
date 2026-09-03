"""Command-line entry point. The complete surface (PRODUCT_SURFACES 3.1)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from swingdesk.application import universe as universe_builder
from swingdesk.application.pipeline import InstrumentOutcome, RunResult, run
from swingdesk.contracts.observation import ParameterUse
from swingdesk.contracts.position import ActionStatus, Fill, ManagementAction, Position
from swingdesk.contracts.reference import Instrument
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal, Submission
from swingdesk.journal_evidence.positions import CapOverride, PositionStore
from swingdesk.market_data import BarStore, vendor_yahoo
from swingdesk.market_data.retry import RetryingFetcher
from swingdesk.platform.clock import FixedClock, SystemClock
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset
from swingdesk.presentation import notify, report
from swingdesk.reference_data import calendar as cal
from swingdesk.reference_data import classification
from swingdesk.reference_data.classification import ClassificationStore
from swingdesk.reference_data.directory import DirectoryStore

# `costs_per_share` was `_costs_per_share` until 2026-08-22 and carried a comment saying it could
# not be renamed while `sizing.py` was frozen. The freeze lifted on 2026-08-17 and the amendment
# that replaced it costs a Track A restart per merge, which this change is already paying - so the
# private import is gone rather than being explained again. Same reasoning promoted
# `to_base_currency`, which the portfolio cap needs for exactly the DR-010 reason this note gives:
# reuse the one implementation, never copy the formula.
from swingdesk.trade_management import manage, portfolio
from swingdesk.trade_management.sizing import (
    Refusal,
    RiskSnapshot,
    allowed_risk,
    costs_per_share,
    to_base_currency,
)

DEFAULT_DATA = Path("data")

#: What `sync-fills` writes into `Position.strategy`. The card that decided the entry
#: (`DR-030`), not a literal typed twice - a position whose strategy tag says `unspecified`
#: cannot be grouped with the trades that validate the card it came from.
STRATEGY_TAG = "CARD-001"


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
    scan.add_argument("--submit", action="store_true",
                      help="submit this run's Trade decisions to the paper venue as bracket "
                           "orders (CHARTER A-002, DR-027). Does nothing unless the kill switch "
                           "file has been armed - it is stopped by default and the refusal says "
                           "which guard stopped it")
    scan.add_argument("--no-notify", action="store_true",
                      help="skip the local desktop notice (DR-011). The report is written either "
                           "way; this only suppresses the pop-up")

    pending = sub.add_parser(
        "pending", help="proposals on open positions awaiting your answer (US-010)")
    pending.add_argument("--data", type=Path, default=DEFAULT_DATA)
    pending.add_argument("--as-of", default=None,
                         help="ISO instant to judge staleness at (DR-013); defaults to now")

    respond = sub.add_parser(
        "respond",
        help="answer a proposal. D1: this records a decision, it never places an order",
    )
    respond.add_argument("position_id", help="e.g. POS-AAPL-2026-08-10")
    respond.add_argument("sequence", type=int, help="the proposal's number, from `pending`")
    choice = respond.add_mutually_exclusive_group(required=True)
    choice.add_argument("--approve", action="store_true")
    choice.add_argument("--reject", action="store_true")
    respond.add_argument("--reason", required=True,
                         help="why. Required - Production Rules 3.8: an approval with no stated "
                              "reason is an unlogged judgment")
    respond.add_argument("--data", type=Path, default=DEFAULT_DATA)
    respond.add_argument("--as-of", default=None,
                         help="ISO instant this answer is recorded at; defaults to now")

    fill = sub.add_parser(
        "record-fill",
        help="report what the broker actually did for an approved action (US-011)",
    )
    fill.add_argument("position_id")
    fill.add_argument("sequence", type=int, help="the approved action this settles")
    fill.add_argument("--price", type=Decimal, required=True, help="the actual fill price")
    fill.add_argument("--shares", type=int, required=True, help="shares actually transacted")
    fill.add_argument("--commission", type=Decimal, required=True,
                      help="as charged, not the modelled estimate")
    fill.add_argument("--filled-on", default=None, help="ISO date; defaults to today")
    fill.add_argument("--data", type=Path, default=DEFAULT_DATA)
    fill.add_argument("--as-of", default=None,
                     help="ISO instant this is recorded at; defaults to now")

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
    opened.add_argument("--acknowledge-over-cap", default=None, metavar="REASON",
                        help="record this position even though it breaches a ratified portfolio "
                             "cap (DR-006 8.3). The reason is written to the store, not just "
                             "printed - an override nobody can audit is not an override")
    opened.add_argument("--position-id", default=None,
                        help="override the default POS-<instrument id>-<opened-on> identity")
    opened.add_argument("--data", type=Path, default=DEFAULT_DATA)
    opened.add_argument("--as-of", default=None,
                        help="ISO instant this is being recorded as of; defaults to now")

    sync = sub.add_parser(
        "sync-fills",
        help="record positions for entries THIS system placed that have since filled (DR-031). "
             "Reads the venue, writes the book, places no order",
    )
    sync.add_argument("--data", type=Path, default=DEFAULT_DATA)
    sync.add_argument("--as-of", default=None,
                      help="ISO instant this is recorded at; defaults to now")
    sync.add_argument("--dry-run", action="store_true",
                      help="say what would be recorded and record nothing")

    broker_cmd = sub.add_parser(
        "broker",
        help="read the paper account and reconcile it against the book. Reads only - it has no "
             "way to place, amend or cancel anything (D1/BR-1, DR-026)",
    )
    broker_cmd.add_argument("--data", type=Path, default=DEFAULT_DATA)
    broker_cmd.add_argument("--as-of", default=None,
                            help="ISO instant this observation is recorded as of; defaults to now")
    broker_cmd.add_argument("--fills", action="store_true",
                            help="also list the venue's executions")
    broker_cmd.add_argument("--since", default=None,
                            help="ISO instant; with --fills, the earliest execution to ask for")

    args = parser.parse_args(argv)

    if args.command == "record-fill":
        return _record_fill(args)

    if args.command == "broker":
        return _broker(args)
    if args.command == "sync-fills":
        return _sync_fills(args)

    if args.command == "pending":
        return _pending(args)

    if args.command == "respond":
        return _respond(args)

    if args.command == "open-position":
        return _open_position(args)

    if args.command == "scan":
        if bool(args.tickers) == bool(args.universe):
            parser.error("pass either tickers or --universe, not both and not neither")

        code, run_id, outcome = _scan(args)

        # The notice goes last of ALL - outside the store block, not merely at the bottom of it.
        # Two defects were found here by review on 2026-08-16 and both are closed by this
        # placement: it used to run inside the `with`, holding three DuckDB locks open for up to
        # the notifier's full 15s timeout to display a pop-up; and both refusal paths returned
        # before ever reaching it, so a refused run said nothing at all - the exact silence
        # `DR-011` 5 claims to remove, made worse by `track_a_streak` counting exit 2 as a clean
        # day. Silence now means the scheduler did not fire, which is the only thing it should
        # ever mean.
        if not args.no_notify:
            notice = notify.notify(run_id, outcome)
            if notice.delivered:
                print("notice delivered")
            else:
                # Loud, never fatal - same reasoning as the report write, and the same rule:
                # unnoticed non-delivery is the defect this exists to close.
                print(f"notice NOT delivered  {notice.detail}", file=sys.stderr)
        return code

    return 1


def _committed_by_live_orders(
    live: Sequence[object], journal: Journal, registry: ParameterRegistry,
    result: RunResult, r_unit: Decimal | None,
) -> list[portfolio.Allocatable] | str:
    """How much of the ratified caps this system's own resting orders are already holding.

    Returns them shaped as `Allocatable` so `allocate` consumes them through the SAME walk it uses
    for candidates, or one string saying why the question could not be answered - in which case
    nothing may be submitted. `DR-032` §3.

    **Every number comes from the submission we journalled before sending**, never from the venue's
    echo of it: `shares`, `limit_price` and `stop_price` are ours, and the cost model is `DR-010`'s.
    That is `DR-031`'s split of authority applied to a leg that has not filled - the venue knows an
    order is resting, and only we know what it was sized against.

    **A resting order we cannot price STOPS the run.** It is holding a slot whose size is unknown,
    and the alternative - treating it as zero - is the `unavailable`-admits-unchecked inversion in
    the one place it would be paid for in orders.
    """
    if not live:
        return []
    if r_unit is None or r_unit <= 0:
        return ("this system has live orders at the venue and 1R could not be priced, so what "
                "they are holding of the cap is unknown")

    committed: list[portfolio.Allocatable] = []
    # The candidate loop already judged the sector composition of everything in today's universe,
    # so a name we have an order out for is looked up rather than re-judged.
    exposures = {
        outcome.instrument.id: outcome.sector.candidate
        for outcome in result.outcomes
        if isinstance(outcome.sector, portfolio.SectorCapacity)
    }
    for order in live:
        client_order_id = getattr(order, "client_order_id", "")
        submission = journal.submission_by_order_id(client_order_id)
        if submission is None:  # pragma: no cover - `ours` selected these from the same table
            return (f"{client_order_id} is resting at the venue and its journalled submission "
                    f"could not be read, so what it holds of the cap is unknown")

        costs = costs_per_share(submission.limit_price, "USD", registry)
        if isinstance(costs, Refusal):
            return (f"{submission.instrument_id} has a resting order and its cost per share has "
                    f"no value, so its R cannot be computed: {costs}")
        costs_value, _bp, _floor = costs
        risk_per_share = submission.limit_price - submission.stop_price + costs_value
        if risk_per_share <= 0:
            return (f"{submission.instrument_id} has a resting order whose stop is at or above its "
                    f"limit, so it has no R denominator and what it holds cannot be measured")

        # ONLY THE PART THAT HAS NOT FILLED. `DR-032` §3.1.
        #
        # A partial fill is counted TWICE otherwise: `sync-fills` records a position for the shares
        # that filled and the book prices those, while this would price the whole order again. On
        # 17 shares with 5 filled that reads 1.29R against a real 1R - over-counting, so it refuses
        # a legitimate candidate rather than admitting an illegitimate one, which is the safe
        # direction and still the wrong number.
        #
        # `filled_shares` is the venue's and the ordered quantity is ours, which is the same split
        # of authority `DR-031` §2 sets out: the venue knows what filled, we know what was asked.
        resting = submission.shares - int(getattr(order, "filled_shares", 0) or 0)
        if resting <= 0:
            # Fully filled and still listed as open - a leg of the bracket, not the entry. The
            # position it produced is in the book and is already consuming the slot.
            continue

        committed.append(portfolio.Allocatable(
            instrument_id=submission.instrument_id,
            requested_r=resting * risk_per_share / r_unit,
            # A name outside today's universe cannot be attributed, and `assess_sector` admits an
            # unclassifiable candidate unchecked (`DR-006` §3) while the count cap still bounds it.
            exposure=exposures.get(
                submission.instrument_id,
                classification.Exposure(
                    instrument_id=submission.instrument_id, weights=(),
                    unavailable="a resting order for a name outside this run's universe",
                ),
            ),
        ))
    return committed


def _allocate(
    result: RunResult, tradeable: list[InstrumentOutcome],
    committed: Sequence[portfolio.Allocatable] = (),
) -> tuple[list[InstrumentOutcome], list[tuple[InstrumentOutcome, str]]] | str:
    """Which of this run's `Trade` decisions fit inside the ratified caps TOGETHER.

    Returns `(submittable, passed_over)` in rank order, or ONE STRING saying why the question could
    not be answered - in which case nothing may be submitted. `DR-027` §10.

    **Every input is something the run already computed**, and that is deliberate rather than
    convenient: `result.capacity.book` is the priced book, `result.sector_book` is its sector split
    and each `outcome.sector` carries the `requested_r` and the exposure the candidate loop judged
    it on. Recomputing any of them here would put the FX rule or the R conversion in a second place,
    which is the `DR-010` mistake `to_base_currency` exists to prevent.

    **The order is `CARD-001`'s ranking and nothing else.** `ALLOCATION_SPEC` §6 rule 4 forbids
    falling back to the order the system happens to hold, so a run whose screen did not produce a
    `Selection` cannot be allocated at all - it returns the refusal rather than submitting the
    first four alphabetically.

    **Every branch that cannot measure a cap refuses**, and there is no branch that admits on a gap.
    A book that was never priced, a sector split that refused, a cap with no value, a candidate the
    sector check never reached: each of those is `unavailable`, and `unavailable` here means STOPPED.
    """
    if result.selection is None:
        return ("no cross-sectional ranking on this run, so there is no ratified order to take "
                "names in; ALLOCATION_SPEC 6 rule 4 forbids falling back to the order the system "
                "happens to hold")
    if not isinstance(result.capacity, portfolio.Capacity):
        # `None` is "no position store, so the book was never priced"; a `Refusal` is "priced and it
        # failed". Both are the same answer here: the caps cannot be applied, so nothing goes.
        unmeasured = (
            result.capacity.reason if isinstance(result.capacity, Refusal)
            else "the book was never priced, so this run cannot say what is already at risk"
        )
        return f"the book cap could not be measured: {unmeasured}"
    if not isinstance(result.sector_book, portfolio.SectorBook):
        unmeasured = (
            result.sector_book.reason if isinstance(result.sector_book, Refusal)
            else "the open book was never split by sector"
        )
        return f"the sector cap could not be measured: {unmeasured}"
    if not isinstance(result.sector_limit, Decimal):
        unmeasured = (
            result.sector_limit.reason if isinstance(result.sector_limit, Refusal)
            else f"{portfolio.MAX_SECTOR_RISK} was never read"
        )
        return f"the sector cap has no value: {unmeasured}"

    # Bound to a local before the sort: a lambda closing over `result.selection` re-reads an
    # optional attribute on every comparison, which mypy is right to refuse.
    screen = result.selection
    ranked = sorted(
        tradeable,
        # A name the screen did not rank sorts last and is then refused below rather than here, so
        # the reason it carries names the missing rank instead of a position in a list.
        key=lambda outcome: (screen.rank_of(outcome.instrument.id) or len(tradeable) + 1,
                             outcome.instrument.id),
    )
    offered: list[portfolio.Allocatable] = []
    for outcome in ranked:
        if not isinstance(outcome.sector, portfolio.SectorCapacity):
            return (f"{outcome.instrument.id} reached a Trade decision without a sector verdict, "
                    f"so its share of the sector budget is unknown")
        offered.append(portfolio.Allocatable(
            instrument_id=outcome.instrument.id,
            requested_r=outcome.sector.requested_r,
            exposure=outcome.sector.candidate,
        ))

    # ALREADY COMMITTED FIRST, and taking them through the same walk is the point (`DR-032` §3).
    # A live order of ours is not a candidate to weigh - it is capacity already spent - so it is
    # offered ahead of everything and `allocate` grows the book with it exactly as it would with a
    # name it took. Seeding a Book by hand instead would be a second implementation of "how does an
    # order consume a slot", and the two would agree until the day they did not.
    verdicts = portfolio.allocate(
        [*committed, *offered], result.capacity.book, result.capacity.caps,
        result.sector_book, result.sector_limit,
    )
    by_id = {outcome.instrument.id: outcome for outcome in ranked}
    # The committed entries carry no outcome and are dropped from both lists: they were not decided
    # by this run and reporting them as passed over would invent a candidate.
    verdicts = tuple(v for v in verdicts if v.instrument_id in by_id)
    submittable = [by_id[v.instrument_id] for v in verdicts if v.taken]
    passed_over = [(by_id[v.instrument_id], v.reason) for v in verdicts if not v.taken]
    return submittable, passed_over


def _submit(
    result: RunResult, data: Path, now: datetime, journal: Journal,
    registry: ParameterRegistry, positions: PositionStore | None = None,
) -> None:
    """Send this run's `Trade` decisions to the paper venue, and journal every attempt.

    **Never fatal to the run.** `a.run_completes` measures whether the run produced its decisions
    and its report, and both happened before this is reached. A venue that refused an order is a
    fact about the venue, and resetting a twenty-day counter over one would be the `DR-011` mistake
    in a more expensive place. Loud, never fatal - the same reasoning as the report write above.

    `CHARTER` A-002 authorises submission with no per-order approval; `DR-027` 2 says what may be
    sent and 4 lists the four guards. **Nothing here decides anything**: the run already did, and
    this reads its decisions in the order they came out.

    **Every eligible candidate gets a journal row, including the ones a guard stopped.** That is
    `DR-027` 6 and it is most of the record's value: afterwards, a session on which the machine
    would have entered three names and was stopped is otherwise indistinguishable from a session on
    which it found nothing.
    """
    from swingdesk import broker as broker_pkg

    run_id = result.manifest.run_id

    def _record(
        order_id: str, instrument_id: str, shares: int, limit: Decimal, stop: Decimal,
        outcome: str, detail: str | None = None, venue_order_id: str | None = None,
        venue_status: str | None = None,
    ) -> None:
        """Write the attempt, and never let a journal failure take the run down with it.

        The record matters and the run matters more: a store that could not be written is a fact
        the operator needs on stderr, not a traceback that loses the report as well.
        """
        try:
            journal.record_submission(Submission(
                run_id=run_id, client_order_id=order_id, attempted_at=now, session_date=session,
                instrument_id=instrument_id, shares=shares, limit_price=limit, stop_price=stop,
                outcome=outcome, detail=detail, venue_order_id=venue_order_id,
                venue_status=venue_status,
            ))
        except Exception as unwritable:  # noqa: BLE001 - loud, never fatal
            print(f"  NOT JOURNALLED {instrument_id}  {unwritable}", file=sys.stderr)

    try:
        policy = broker_pkg.load_policy()
        # The exchange session, not the clock's date (`DR-027` 9). At 19:30 New York the UTC date
        # has already rolled over, so the retry pass would key on a different day than the 18:30
        # pass and resubmit every entry.
        session = broker_pkg.trading_session(policy.market, now)
        arming = broker_pkg.read_arming(data, policy.write)
        client = broker_pkg.open_client(policy, arming=arming)
    except broker_pkg.PolicyRefused as refused:
        print(f"submit REFUSED  {refused}", file=sys.stderr)
        return
    except broker_pkg.CredentialsMissing as missing:
        print(f"submit UNAVAILABLE  {missing}", file=sys.stderr)
        return
    except LookupError as no_session:
        print(f"submit UNAVAILABLE  no completed session to key an order on: {no_session}",
              file=sys.stderr)
        return

    # Counted first and printed either way. A run that would have submitted nothing and a run that
    # was stopped from submitting something are different facts, and a line that only appeared when
    # the switch was armed would hide the second.
    tradeable = [
        outcome for outcome in result.outcomes
        if outcome.decision is not None and outcome.decision.decision == "Trade"
        and isinstance(outcome.risk, RiskSnapshot)
    ]
    print()
    print(f"submission  {len(tradeable)} Trade decision(s) sized and eligible")

    write = policy.write
    if write is None:  # pragma: no cover - `policy.load` refuses write_enabled without a section
        print("submit REFUSED  the policy grants writing and carries no write section",
              file=sys.stderr)
        return

    def _key(instrument_id: str) -> str:
        """The order id, or a synthetic one when it cannot be derived.

        An attempt that could not even be keyed is still an attempt, and a row naming the
        instrument is worth more than no row at all.
        """
        try:
            return broker_pkg.client_order_id(session, instrument_id, write)
        except broker_pkg.PolicyRefused:
            return f"unkeyed-{session.isoformat()}-{instrument_id}"

    def _journal_passed_over(passed: list[tuple[InstrumentOutcome, str]]) -> None:
        for outcome, why in passed:
            risk = outcome.risk
            assert isinstance(risk, RiskSnapshot)
            _record(_key(outcome.instrument.id), outcome.instrument.id, risk.shares,
                    risk.entry, risk.stop, "stopped", why)

    def _journal_all(reason: str) -> None:
        for outcome in tradeable:
            risk = outcome.risk
            assert isinstance(risk, RiskSnapshot)
            _record(_key(outcome.instrument.id), outcome.instrument.id, risk.shares,
                    risk.entry, risk.stop, "stopped", reason)

    # A DISARMED RUN STOPS HERE, and still says which names the caps would have taken.
    #
    # It allocates against the BOOK ALONE. The resting-order half of the cap (`DR-032` §3) needs
    # the venue, and the venue is read only after this check - `AlpacaClient.guards`' own ordering,
    # so that a refusal saying *the venue is unreachable* never stands in for *nobody armed it*.
    # Nothing can be submitted on this path anyway, so the record is the whole purpose and a
    # book-only reading of it is the honest one.
    if arming.stopped:
        book_only = _allocate(result, tradeable)
        if isinstance(book_only, str):
            print(f"  STOPPED  {book_only}", file=sys.stderr)
            _journal_all(book_only)
            return
        would_take, would_pass = book_only
        _journal_passed_over(would_pass)
        print(f"  STOPPED  {arming.reason}")
        if would_pass:
            print(f"  {len(would_pass)} passed over by the ratified caps; "
                  f"{len(would_take)} within them")
        for outcome in would_take:
            risk = outcome.risk
            assert isinstance(risk, RiskSnapshot)
            _record(_key(outcome.instrument.id), outcome.instrument.id, risk.shares,
                    risk.entry, risk.stop, "stopped", arming.reason)
        return

    print(f"  armed    {arming.reason}")

    # THE VENUE IS ASKED WHAT IT ALREADY HOLDS, BEFORE ANYTHING IS ADDED. `DR-027` §11.
    #
    # §10's caps are measured against `positions.duckdb`, and NOTHING WRITES TO IT automatically
    # except `sync-fills` (`DR-031`), which a person can forget to schedule. So the book can read
    # empty on an evening something filled, and the caps would take four more names on top.
    #
    # `TECH` is the course's own code for the two disagreeing and its prescribed action is *pause
    # new entries* - and `DR-027` §7 already ruled that on this path a divergence stops submission
    # rather than being noted.
    def _stop_all(reason: str) -> None:
        print(f"  STOPPED  {reason}", file=sys.stderr)
        _journal_all(reason)

    if positions is None:
        _stop_all("no position store, so what the venue already holds cannot be compared against "
                  "anything; submission needs a book to add to")
        return

    try:
        held = client.positions(now)
        live_orders = client.open_orders(now)
    except broker_pkg.BrokerUnavailable as unavailable:
        # UNAVAILABLE IS STOPPED. A venue that cannot be read is a venue whose holdings are
        # unknown, and adding to an unknown book is the one thing this guard exists to prevent.
        _stop_all(f"the venue could not be read before submitting: {unavailable}")
        return

    # OUR OWN LIVE ORDERS ARE NOT A MYSTERY. `DR-032`.
    #
    # An order this system sent an hour ago and journalled BEFORE sending is the exposure it can
    # account for best, not least. Halting on it is what killed `DR-015`'s 19:30 retry: the first
    # pass submitted, the second found its own orders resting at the venue, called them a mismatch
    # and stopped - so a candidate that failed on the first pass was never retried.
    #
    # Identified by an id in our own record, never by the shape of the id. A prefix test would
    # adopt anything typed into the dashboard with the right first word.
    sent_ids = journal.sent_client_order_ids()
    unaccounted = broker_pkg.uncommitted_exposure(
        positions.open_as_of(now), held, live_orders, policy.market, sent_order_ids=sent_ids,
    )
    if unaccounted:
        _stop_all(
            f"{broker_pkg.MISMATCH_CODE}: the venue holds {len(unaccounted)} symbol(s) this "
            f"system's book does not carry ({', '.join(unaccounted[:8])}"
            f"{', ...' if len(unaccounted) > 8 else ''}). The caps were measured against the book, "
            f"so they were not measured against these. Pause new entries: record them with "
            f"`open-position`, or close them at the venue."
        )
        return

    # Excluding our resting orders above obliges this to count them here (`DR-032` §3). They hold a
    # slot and their R until they fill or expire; leaving them out of both would let the retry pass
    # add four more names on top of four already resting.
    committed = _committed_by_live_orders(
        broker_pkg.ours(live_orders, sent_ids), journal, registry, result,
        r_unit=result.capacity.book.r_unit if isinstance(result.capacity, portfolio.Capacity)
        else None,
    )
    if isinstance(committed, str):
        _stop_all(committed)
        return
    if committed:
        held_r = sum((entry.requested_r for entry in committed), Decimal(0))
        print(f"  {len(committed)} live order(s) of ours already hold {held_r:.2f}R of the cap")

    # THE RATIFIED CAPS, ACROSS THIS RUN'S OWN OUTPUT AND WHAT IS ALREADY RESTING. `DR-027` §10.
    #
    # `pipeline` prices the book ONCE and measures every candidate against it, which is correct for
    # the question it asks - may this name be held at all - and leaves the question this path asks
    # unanswered: do 114 of them fit together. On 2026-09-02 they did not, by a factor of 28.
    allocation = _allocate(result, tradeable, committed)
    if isinstance(allocation, str):
        # FAIL CLOSED, and this polarity is the whole point. A cap that could not be measured
        # admitting everything is the `unavailable`-admits-unchecked inversion `DR-025` §2.1
        # records this project paying for once already - and here it would pay at a venue.
        _stop_all(allocation)
        return

    submittable, passed_over = allocation
    _journal_passed_over(passed_over)
    if passed_over:
        # Counted, never listed. A hundred lines naming every name the book had no room for would
        # bury the four it did, and the journal holds each one with its own reason.
        print(f"  {len(passed_over)} passed over by the ratified caps; "
              f"{len(submittable)} within them")

    halted: str | None = None
    for outcome in submittable:
        risk = outcome.risk
        assert isinstance(risk, RiskSnapshot)
        instrument_id = outcome.instrument.id

        if halted is not None:
            # A guard that stopped one order stops every remaining one for the same reason. They
            # were eligible and were not attempted, and the row says which.
            _record(_key(instrument_id), instrument_id, risk.shares, risk.entry, risk.stop,
                    "stopped", halted)
            continue

        try:
            # The target is read here rather than passed down, so an unset one refuses THIS order
            # and names the parameter, instead of the venue refusing a malformed bracket.
            order = broker_pkg.entry_order(
                instrument_id=instrument_id, shares=risk.shares,
                limit_price=risk.entry, stop_price=risk.stop,
                target=broker_pkg.target_price(risk.entry, risk.risk_per_share, registry),
                session_date=session, write=write, market=policy.market,
            )
        except ParameterUnset as unset:
            print(f"  REFUSED  {instrument_id}  no take-profit target: {unset.parameter_id} is "
                  f"unset, and a bracket needs both legs", file=sys.stderr)
            _record(_key(instrument_id), instrument_id, risk.shares, risk.entry, risk.stop,
                    "refused", f"{unset.parameter_id} is unset")
            continue
        except (broker_pkg.PolicyRefused, ValueError) as refused:
            print(f"  REFUSED  {instrument_id}  {refused}", file=sys.stderr)
            _record(_key(instrument_id), instrument_id, risk.shares, risk.entry, risk.stop,
                    "refused", str(refused))
            continue

        try:
            placed = client.submit(order, now)
        except broker_pkg.SubmissionStopped as stopped:
            print(f"  STOPPED  {instrument_id}  {stopped}", file=sys.stderr)
            halted = str(stopped)
            _record(order.client_order_id, instrument_id, order.shares, order.limit_price,
                    order.stop_price, "stopped", halted)
            continue
        except broker_pkg.BrokerUnavailable as unavailable:
            # Includes the venue rejecting a duplicate `client_order_id`, which is idempotency
            # working rather than an error - the reason travels so a reader can tell which it was.
            print(f"  NOT SENT {instrument_id}  {unavailable}", file=sys.stderr)
            _record(order.client_order_id, instrument_id, order.shares, order.limit_price,
                    order.stop_price, "rejected", str(unavailable))
            continue

        _record(order.client_order_id, instrument_id, order.shares, order.limit_price,
                order.stop_price, "sent", venue_order_id=placed.order_id,
                venue_status=placed.status)
        print(f"  SENT     {order.instrument_id:<10} {order.shares} sh "
              f"limit {order.limit_price} stop {order.stop_price}  "
              f"{placed.status}  {placed.client_order_id}")


def _sync_fills(args: argparse.Namespace) -> int:
    """Record a `Position` for every entry THIS system placed that has since filled. `DR-031`.

    **This is the step that was a person, and it is the last one in the loop.** `DR-027` §11 stops
    submission whenever the venue holds something the book does not carry - which, before this
    command existed, meant every evening after the first, because `positions.duckdb` was written
    only by hand. The guard was right and the manual step was the cost of it.

    **It writes the book and never the venue.** No order is placed, amended or cancelled here; the
    only network calls are two GETs. `D1` is untouched - this records a fill that has already
    happened, which is exactly what `open-position` does, with the typing done from our own record
    instead of by an operator at 18:35.

    Three exit codes, and the middle one is the point:

        0  the book now describes every holding this system placed
        2  the venue could not be read, or a cost parameter has no value - nothing was written
        3  the venue holds something that traces to no order of ours. NOT an error in this
           command: it is `TECH`, and the action is a person's
    """
    from swingdesk import broker as broker_pkg
    from swingdesk.trade_management import adoption

    clock = (
        FixedClock(datetime.fromisoformat(args.as_of).replace(tzinfo=UTC))
        if args.as_of
        else SystemClock()
    )
    now = clock.now()
    registry = ParameterRegistry.load()

    try:
        policy = broker_pkg.load_policy()
        client = broker_pkg.open_client(policy)
    except broker_pkg.PolicyRefused as refused:
        print(f"sync REFUSED  {refused}", file=sys.stderr)
        return 2
    except broker_pkg.CredentialsMissing as missing:
        print(f"sync UNAVAILABLE  {missing}", file=sys.stderr)
        return 2

    try:
        held = client.positions(now)
        # The fills feed is read for ONE field the positions endpoint does not carry: the session
        # the fill happened in. `opened_on` is event time and `knowledge_time` is when we learned
        # it - the bitemporal split `open-position` keeps by hand, kept here by machine.
        fills = client.fills(now)
    except broker_pkg.BrokerUnavailable as unavailable:
        print(f"sync UNAVAILABLE  {unavailable}", file=sys.stderr)
        return 2

    opened_on: dict[str, date] = {}
    for fill in fills:
        # EARLIEST fill wins. A position built up over several partial fills was opened when the
        # first one printed, not when the last one completed it.
        session = fill.transaction_time.date()
        if fill.symbol not in opened_on or session < opened_on[fill.symbol]:
            opened_on[fill.symbol] = session

    print(f"{policy.label}  {len(held)} holding(s) at the venue")

    recorded = 0
    untraceable: list[str] = []
    refusals: list[str] = []

    with (
        Journal(args.data / "journal.duckdb") as journal,
        PositionStore(args.data / "positions.duckdb") as store,
    ):
        known = {position.instrument_id for position in store.open_as_of(now)}
        for holding in held:
            if holding.symbol in known:
                continue

            submission = journal.latest_sent_submission(holding.symbol)
            if submission is None:
                # NOT adopted, and this is the branch that keeps the system honest. A holding we
                # cannot trace to an order of ours is somebody trading by hand, and `DR-027` §11's
                # guard should go on stopping submission until a person deals with it.
                untraceable.append(holding.symbol)
                continue

            if holding.symbol not in opened_on:
                # A holding with no fill in the feed cannot be dated, and `opened_on` is what every
                # holding-period rule counts from. Refused rather than dated from a clock.
                refusals.append(
                    f"{holding.symbol}: held at the venue with no fill in the activities feed, so "
                    f"the session it opened in is unknown"
                )
                continue

            position = adoption.adopt(
                holding=holding,
                submitted=adoption.SubmittedEntry(
                    instrument_id=submission.instrument_id,
                    stop_price=submission.stop_price,
                    client_order_id=submission.client_order_id,
                ),
                opened_on=opened_on[holding.symbol],
                knowledge_time=now,
                registry=registry,
                strategy=STRATEGY_TAG,
            )
            if isinstance(position, Refusal):
                refusals.append(f"{holding.symbol}: {position}")
                continue

            if args.dry_run:
                print(f"  WOULD RECORD  {position.instrument_id:<10} {position.shares} sh "
                      f"entry {position.entry_price} stop {position.current_stop}")
                recorded += 1
                continue

            try:
                store.record(position)
            except Exception as unwritable:  # noqa: BLE001 - loud, and the rest still record
                refusals.append(f"{holding.symbol}: could not be recorded: {unwritable}")
                continue
            recorded += 1
            print(f"  RECORDED  {position.instrument_id:<10} {position.shares} sh "
                  f"entry {position.entry_price} stop {position.current_stop} "
                  f"costs {position.initial_costs_per_share}/sh  opened {position.opened_on}")

    if not recorded and not untraceable and not refusals:
        print("  nothing to record - the book already describes every holding")

    for reason in refusals:
        print(f"  REFUSED  {reason}", file=sys.stderr)

    if untraceable:
        print(f"  {broker_pkg.MISMATCH_CODE}  {len(untraceable)} holding(s) trace to no order this "
              f"system sent: {', '.join(untraceable)}. Not adopted - record them with "
              f"`open-position` or close them at the venue. New entries stay paused until then.",
              file=sys.stderr)
        return 3

    if refusals:
        return 2
    return 0


def _broker(args: argparse.Namespace) -> int:
    """Read the paper account, print it, and say whether it agrees with the book.

    **Three exit codes, because there are three different answers** and collapsing any two of them
    is the error `AGENTS.md` 12 calls the most damaging this product can make:

        0  the venue and the book describe the same positions
        2  the venue could not be read - UNAVAILABLE, which is not agreement and not disagreement
        3  both were read and they disagree - the course's `TECH`, whose action is "pause new
           entries"

    Nothing here writes. The reconciliation prints what it found and the owner records it with
    `open-position` or `record-fill`; a command that repaired the book from the venue would be
    deciding what a divergence meant, and a divergence is exactly the state in which this system
    has least right to decide anything.
    """
    from swingdesk import broker as broker_pkg

    clock = (
        FixedClock(datetime.fromisoformat(args.as_of).replace(tzinfo=UTC))
        if args.as_of
        else SystemClock()
    )
    now = clock.now()

    try:
        policy = broker_pkg.load_policy()
        client = broker_pkg.open_client(policy)
    except broker_pkg.PolicyRefused as refused:
        print(f"broker REFUSED  {refused}", file=sys.stderr)
        return 2
    except broker_pkg.CredentialsMissing as missing:
        print(f"broker UNAVAILABLE  {missing}", file=sys.stderr)
        return 2

    try:
        account = client.account(now)
        held = client.positions(now)
        fills = (
            client.fills(now, after=datetime.fromisoformat(args.since).replace(tzinfo=UTC)
                         if args.since else None)
            if args.fills else ()
        )
    except broker_pkg.BrokerUnavailable as unavailable:
        print(f"broker UNAVAILABLE  {unavailable}", file=sys.stderr)
        return 2

    print(f"{policy.label}  {account.base_url}")
    print(f"  account       {account.fingerprint}  {account.status}  {account.currency}")
    print(f"  equity        {account.equity}")
    print(f"  cash          {account.cash}")
    print(f"  buying power  {account.buying_power}")
    if account.trading_blocked or account.account_blocked:
        # Printed as a finding rather than a footnote: a blocked account explains an empty
        # position list, and an empty list read as "flat" is a book this system would trust.
        print(f"  BLOCKED       trading={account.trading_blocked} "
              f"account={account.account_blocked}")

    print(f"\nvenue positions ({len(held)})")
    for holding in held:
        print(f"  {holding.symbol:<10} {holding.shares:>12} @ {holding.average_entry_price}"
              f"  {holding.side.value}  {holding.asset_class}")
    if not held:
        print("  (none)")

    with PositionStore(args.data / "positions.duckdb") as positions:
        book = positions.open_as_of(now)
    report_ = broker_pkg.reconcile(book, held, venue=policy.label, market=policy.market)

    print(f"\nreconciliation against the book ({len(book)} open)")
    for agreement in report_.agreed:
        print(f"  AGREED     {agreement.instrument_id:<10} {agreement.shares} sh @ "
              f"{agreement.book_entry_price}")
    for divergence in report_.divergences:
        print(f"  {report_.code}  {divergence.reason:<12} {divergence.instrument_id}")
        print(f"             {divergence.detail}")
    for instrument_id in report_.out_of_scope:
        # Not a divergence. This venue does not trade the TSX, so its silence about a Canadian
        # holding is not evidence of anything (AGENTS 3: USA and Canada are never merged).
        print(f"  out of scope  {instrument_id} - {policy.label} does not trade this market")
    if report_.agrees and not report_.out_of_scope:
        print("  the venue and the book describe the same positions")

    if args.fills:
        print(f"\nvenue executions ({len(fills)})")
        for fill in fills:
            print(f"  {fill.transaction_time.isoformat()}  {fill.symbol:<10} "
                  f"{fill.side.value:<4} {fill.shares:>10} @ {fill.price}  {fill.kind.value}")
        orphans = broker_pkg.unrecorded_fills(fills, book)
        if orphans:
            print(f"\n  {len(orphans)} execution(s) for instruments the book has never opened. "
                  f"This does NOT say which approved action they settle - the venue carries an "
                  f"order id and `record-fill` needs a position and a sequence.")

    if not report_.agrees:
        print(f"\n{report_.code}: broker/journal mismatch. Appendix N's action for this code is "
              f"'pause new entries' until it is resolved.", file=sys.stderr)
        return 3
    return 0


def _record_fill(args: argparse.Namespace) -> int:
    """Record what the broker actually did, and report the slippage against what was planned.

    The planned price is taken from the ACTION, not from the owner - a reference the reporter
    supplies is a reference they can choose after seeing the fill, which would make slippage a
    number that always looks acceptable.

    For a stop exit the plan named a price and the stop is it. For a time exit it named none, and
    this says so rather than reporting 0.00: see `Fill.slippage_per_share`.
    """
    from datetime import date as date_cls

    clock = (
        FixedClock(datetime.fromisoformat(args.as_of).replace(tzinfo=UTC))
        if args.as_of
        else SystemClock()
    )
    now = clock.now()
    filled_on = date_cls.fromisoformat(args.filled_on) if args.filled_on else now.date()

    with PositionStore(args.data / "positions.duckdb") as positions:
        action = positions.proposal_at(args.position_id, args.sequence)
        if action is None:
            print(f"fill REFUSED  no action {args.position_id} #{args.sequence}", file=sys.stderr)
            return 2

        # `old_stop` is the plan's price for a stop exit and is carried on every proposal. A time
        # exit sets it too, but its reason code says the holding period ran out - it did not plan
        # to sell AT the stop, so that stop is not a reference this fill slipped against.
        planned = action.old_stop if (action.reason_code or "").lower().startswith("stop") else None

        try:
            positions.record_fill(Fill(
                position_id=args.position_id, sequence=args.sequence, filled_on=filled_on,
                shares=args.shares, price=args.price, commission=args.commission,
                planned_price=planned, recorded_at=now,
            ))
        except (ValueError, ValidationError) as refused:
            print(f"fill REFUSED  {refused}", file=sys.stderr)
            return 2

        recorded = positions.fills_for(args.position_id)[-1]
        print(f"recorded fill: {args.position_id} #{args.sequence}  "
              f"{recorded.shares} sh @ {recorded.price}, commission {recorded.commission}")

        history = positions.history(args.position_id)
        slip = recorded.slippage_per_share
        if slip is None:
            print("  slippage       UNAVAILABLE - the plan named no price to slip against")
            print("                 (a maximum-holding-period exit is at market, not at the stop)")
        else:
            in_r = recorded.slippage_r(history[0].initial_risk_per_share) if history else None
            print(f"  planned        {recorded.planned_price}")
            print(f"  slippage       {slip}/share"
                  + (f"  = {in_r:.4f}R against the ORIGINAL denominator" if in_r is not None
                     else ""))

        # US-011: recomputed across the whole book, never decremented.
        print(f"  open risk      {positions.open_risk_as_of(now)} across the book, recomputed")
    return 0


def _expiry(
    positions: PositionStore, action: ManagementAction, now: datetime
) -> bool | Refusal:
    """Is this proposal past `DR-013`'s window? A `Refusal` when the rule cannot be applied.

    The exchange comes from the POSITION, never from parsing `position_id`. That id defaults to
    `POS-<instrument id>-<opened-on>` but `--position-id` overrides it, so splitting the string
    would work until the first time somebody used the flag - and then it would pick the wrong
    calendar silently, which is the worst way for a date rule to be wrong.
    """
    try:
        days, _ = ParameterRegistry.load().int_value("management.proposal_expiry_days")
    except ParameterUnset as unset:
        return Refusal("RISK", "no expiry window is set, so staleness cannot be judged",
                       parameter_id=unset.parameter_id)
    history = positions.history(action.position_id)
    if not history:
        return Refusal("DATA", f"no position {action.position_id} to date this proposal against")
    exchange = cal.exchange_for(history[-1].instrument_id)
    return manage.is_expired(action, now, days, exchange)


def _pending(args: argparse.Namespace) -> int:
    """List proposals awaiting an answer, with what US-010 requires to answer them.

    Each entry states the observation the run acted on, the rule that produced the proposal, and
    the bounded set of choices - which is exactly two. Nothing here is a recommendation to trade:
    the system proposes managing a position it was told about, and the owner decides (D1, A-001).
    """

    now = (
        FixedClock(datetime.fromisoformat(args.as_of).replace(tzinfo=UTC)).now()
        if getattr(args, "as_of", None)
        else SystemClock().now()
    )

    with PositionStore(args.data / "positions.duckdb") as positions:
        everything = positions.pending()

        # Split at READ time (`DR-013` 6.4). Expired ones are SHOWN, not dropped: an owner who
        # cannot tell "nothing pending" from "something aged out while I was away" has been told
        # less than the truth, and the second is the case they most need to know about.
        waiting, expired, unjudgeable = [], [], []
        for item in everything:
            verdict = _expiry(positions, item.action, now)
            if isinstance(verdict, Refusal):
                unjudgeable.append((item, verdict))
            elif verdict:
                expired.append(item)
            else:
                waiting.append(item)

        if not everything:
            print("no proposals awaiting your answer.")
            return 0
        if not waiting:
            print("no proposals awaiting your answer.")
        else:
            print(f"{len(waiting)} proposal(s) awaiting your answer\n")
        for item in waiting:
            action = item.action
            print(f"  {action.position_id}  #{item.sequence}   {action.kind.value.upper()}")
            print(f"      proposed   {action.proposed_at:%Y-%m-%d %H:%M:%S %Z}")
            if action.reason_code:
                print(f"      code       {action.reason_code}")
            print(f"      because    {action.reason}")
            if action.old_stop is not None or action.new_stop is not None:
                print(f"      stop       {action.old_stop} -> {action.new_stop}")
            if action.shares_affected is not None:
                print(f"      shares     {action.shares_affected}")
            print(
                f"      answer     swingdesk respond {action.position_id} {item.sequence} "
                f"--approve|--reject --reason \"...\"\n"
            )

        if expired:
            print(f"{len(expired)} EXPIRED and can no longer be answered (DR-013):\n")
            for item in expired:
                a = item.action
                print(f"  {a.position_id}  #{item.sequence}   {a.kind.value.upper()}"
                      f"   proposed {a.proposed_at:%Y-%m-%d}")
                print("      the observation it acted on is stale; a later run will re-propose "
                      "if the rule still fires\n")

        # Never silently. A proposal whose age cannot be judged is not a proposal that is fine.
        for item, refusal in unjudgeable:
            print(f"  {item.action.position_id}  #{item.sequence}   AGE UNKNOWN  {refusal}",
                  file=sys.stderr)
    return 0


def _respond(args: argparse.Namespace) -> int:
    """Record the owner's answer, and apply it when it is an approval.

    This is the half of `US-010` that did not exist: `manage.apply_approved` was written, unit
    tested, and called from nowhere but tests, so no decision the owner made could ever reach the
    store. The order here is the requirement - the response is recorded FIRST, then acted on, so
    "no action is applied without a recorded response" holds even if applying then fails.
    """

    clock = (
        FixedClock(datetime.fromisoformat(args.as_of).replace(tzinfo=UTC))
        if args.as_of
        else SystemClock()
    )
    now = clock.now()
    verdict = ActionStatus.APPROVED if args.approve else ActionStatus.REJECTED

    with PositionStore(args.data / "positions.duckdb") as positions:
        # BEFORE the response is recorded, not after. `DR-013` 6.3 refuses an expired proposal
        # rather than applying it late, and the store's primary key means a recorded answer cannot
        # be taken back - so the check has to come first or the refusal arrives too late to matter.
        proposed = positions.proposal_at(args.position_id, args.sequence)
        if proposed is not None:
            # `stale`, not `verdict` - `verdict` above already holds the owner's APPROVED/REJECTED
            # choice, and shadowing it here passed a bool into `respond(choice=...)`. Caught
            # immediately by the store's own validator, which refused with "a response is APPROVED
            # or REJECTED, not False" - a validator earning its keep on the first shadowed name.
            stale = _expiry(positions, proposed, now)
            if isinstance(stale, Refusal):
                print(f"response REFUSED  {stale}", file=sys.stderr)
                return 2
            if stale:
                print(
                    f"response REFUSED  RISK: {args.position_id} #{args.sequence} expired - it was "
                    f"proposed {proposed.proposed_at:%Y-%m-%d} on an observation that is now stale "
                    f"(DR-013). A later run re-proposes if the rule still fires",
                    file=sys.stderr,
                )
                return 2

        try:
            positions.respond(
                args.position_id, args.sequence,
                choice=verdict, reason=args.reason, at=now,
            )
        except ValueError as refused:
            print(f"response REFUSED  {refused}", file=sys.stderr)
            return 2

        print(f"recorded: {args.position_id} #{args.sequence} {verdict.value} - {args.reason}")
        if verdict is ActionStatus.REJECTED:
            print("  nothing applied. The position is unchanged.")
            return 0

        history = positions.history(args.position_id)
        if not history:
            print(f"position REFUSED  no position {args.position_id} to apply this to",
                  file=sys.stderr)
            return 2
        current = history[-1]

        # Read by sequence, not by position in a list. `respond` above has already consumed this
        # proposal out of `pending()`, and indexing `actions_for` would assume sequences run
        # 1..n contiguously - they are monotonic, not contiguous, and being wrong there would
        # apply the owner's answer to a different proposal than the one they read.
        proposal = positions.proposal_at(args.position_id, args.sequence)
        if proposal is None:
            print(f"proposal REFUSED  {args.position_id} #{args.sequence} not found",
                  file=sys.stderr)
            return 2

        applied = manage.apply_approved(
            current, proposal.model_copy(update={"status": ActionStatus.APPROVED}), now
        )
        positions.record(applied)
        print(f"  applied: {args.position_id} is now version {applied.version}")
        if applied.current_stop != current.current_stop:
            print(f"           stop {current.current_stop} -> {applied.current_stop}")
        if applied.shares != current.shares:
            print(f"           shares {current.shares} -> {applied.shares}")
        if applied.closed_on is not None and current.closed_on is None:
            print(f"           closed {applied.closed_on}")
    return 0


def _capacity_for(
    positions: PositionStore, position: Position, registry: ParameterRegistry, now: datetime
) -> portfolio.Capacity | Refusal:
    """Is there room in the book for `position`? (`DR-006` §8.3.)

    Read BEFORE the position is recorded, so the book it is measured against is the book as it
    stood when the fill happened rather than one that already includes it.

    The R unit comes from `sizing.allowed_risk` and the conversion from `sizing.to_base_currency` -
    this command sizes nothing, so both would otherwise have to be re-derived here, which is how a
    second definition of 1R gets into the tree.
    """
    try:
        caps = portfolio.limits(registry)
    except ParameterUnset as unset:
        return Refusal(
            "RISK",
            "the book cannot be judged against a cap that has no value; set it, or acknowledge "
            "the breach explicitly",
            parameter_id=unset.parameter_id,
        )

    budget = allowed_risk(registry)
    if isinstance(budget, Refusal):
        # Reworded for the same reason the FX refusal below is: `allowed_risk` speaks about sizing,
        # and this command sizes nothing. Worth naming plainly because it WIDENS what can block the
        # recording of a fact that already happened at the broker - before the cap existed this
        # command needed only the DR-010 cost parameters, and it now also needs `account.equity`,
        # `risk.per_trade_pct`, both caps and (for a `.TO` name) the FX rate.
        return Refusal(
            budget.code,
            f"the cap is denominated in R and one R cannot be valued, so the book cannot be judged "
            f"at all: {budget.reason}",
            parameter_id=budget.parameter_id,
        )
    r_unit, _equity_use, _risk_use = budget

    def rate_for(currency: str) -> tuple[Decimal, tuple[ParameterUse, ...]] | Refusal:
        return to_base_currency(currency, registry)

    priced = portfolio.book(positions.open_as_of(now), rate_for, r_unit)
    if isinstance(priced, Refusal):
        return priced

    currency = cal.currency_for(position.instrument_id)
    rate = rate_for(currency)
    if isinstance(rate, Refusal):
        # Reworded rather than passed through: the underlying refusal is about SIZING across
        # currencies, and this command sizes nothing. What matters here is the consequence, which
        # is larger than this one command - a position whose risk cannot be expressed in R makes
        # the whole book untotallable, so every candidate in every later run refuses too. Owner
        # ruling 2026-08-22: refuse, and let --acknowledge-over-cap record it anyway.
        return Refusal(
            rate.code,
            f"this position is denominated in {currency} and its risk cannot be expressed in R, "
            f"so the cap cannot be applied to it - and once it is in the book, no later run can "
            f"total the book either, which would refuse every candidate: {rate.reason}",
            parameter_id=rate.parameter_id,
        )
    base_per_local, _uses = rate
    return portfolio.assess(priced, caps, position.open_risk * base_per_local / r_unit)


def _open_position(args: argparse.Namespace) -> int:
    """Record a manually-executed entry. `TODO.md` §6b item 1.

    Extracted into its own function on 2026-08-17, and it had to be: master's #14/#15 pulled
    the scan path out of `main()` into `_scan()`, which returns a 3-tuple so the notifier can
    run after the stores close. This block was written against the older inline `main()`, so
    the textual merge dropped it INSIDE `_scan()` - after that function's own `return`. It
    parsed, it type-checked, ruff and mypy were clean, and the command was unreachable: every
    `open-position` invocation fell through to `main()`'s final `return 1` and printed nothing
    at all. Six tests caught it; no gate would have.
    """
    from datetime import date as date_cls

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
        costs_result = costs_per_share(args.entry, instrument.currency, registry)
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

    acknowledged = (args.acknowledge_over_cap or "").strip()

    with PositionStore(args.data / "positions.duckdb") as store:
        # The portfolio cap, BEFORE the position is recorded (DR-006 8.3; owner ruling
        # 2026-08-22). This command records a fill that has already happened at the broker, so
        # refusing it makes the store disagree with reality - which is why the escape hatch
        # exists and why it demands a reason rather than a bare flag. What it must never do is
        # record a fifth position as though the limit had been met.
        capacity = _capacity_for(store, position, registry, now)
        breached = isinstance(capacity, Refusal) or not capacity.admitted
        # Parenthesised, because `a or b if c else d` parses as `(a or b) if c else d` and reads
        # to most people as `a or (b if c else d)`. This value labels a row in an append-only audit
        # table, so a later "clarification" in the wrong direction would mislabel which cap was
        # crossed in records nobody re-derives.
        binding = (
            (capacity.parameter_id or capacity.code) if isinstance(capacity, Refusal)
            else capacity.binding
        )
        detail = capacity.reason

        if breached and not acknowledged:
            print(f"position REFUSED  {detail}", file=sys.stderr)
            print(
                '                  If the position is real, re-run with '
                '--acknowledge-over-cap "<reason>". The reason is recorded, because a limit '
                'crossed without a stated reason is a decision nobody can review.',
                file=sys.stderr,
            )
            return 2

        try:
            store.record(position)
        except ValueError as duplicate:
            # Append-only: a second `open-position` for the same instrument on the same date
            # is refused rather than silently duplicated - the store's own guard, not a new one
            # written here (positions.py: "Rejects a version that already exists").
            print(f"position REFUSED  {duplicate}", file=sys.stderr)
            return 2

        if breached:
            book = None if isinstance(capacity, Refusal) else capacity.book
            store.record_cap_override(CapOverride(
                position_id=position.position_id, recorded_at=now,
                binding=binding or "RISK",
                positions_open=0 if book is None else book.count,
                open_risk_r=Decimal(0) if book is None else book.open_risk_r,
                requested_r=(
                    Decimal(0) if isinstance(capacity, Refusal) else capacity.requested_r
                ),
                reason=acknowledged,
            ))
            print(f"CAP BREACH ACKNOWLEDGED  {binding}", file=sys.stderr)
            print(f"                         {detail}", file=sys.stderr)
            print(f"                         your reason: {acknowledged}", file=sys.stderr)
        elif acknowledged:
            # A flag that excused nothing. Said out loud rather than swallowed, so nobody carries
            # it forward believing the cap was crossed and forgiven.
            print("note: --acknowledge-over-cap was passed and the position is INSIDE the cap; "
                  "nothing was overridden and no override was recorded", file=sys.stderr)

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


def _scan(args: argparse.Namespace) -> tuple[int, str | None, notify.Outcome]:
    """One `scan`, returning its exit code and what the owner should be told about it.

    Split out of `main()` so every store is closed before the notice is raised. The return carries
    the run id where one exists - a refusal can happen before any run is journalled, and there is
    then no manifest and no id to reference.
    """

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
        # Sector composition, for `DR-006` §2's sector cap. Opened here for the same reason the
        # position store is: an empty store makes the cap report `unavailable` on every candidate,
        # which is the truth, while not opening one at all would leave the cap unreachable from the
        # only command that runs it. `tools/refresh_classifications.py` is what fills it, and until
        # that has run every candidate is admitted UNCHECKED and the report says so.
        ClassificationStore(args.data / "classifications.duckdb") as classifications,
    ):
        if args.universe:
            built = universe_builder.rule_from_registry(registry)
            if isinstance(built, Refusal):
                # Fail closed and say which parameter. A universe that silently admitted
                # everything would be worse than no run at all. No run was journalled, so there
                # is no id to reference - the notice says so rather than inventing one.
                print(f"universe REFUSED  {built}", file=sys.stderr)
                return 2, None, notify.Outcome.REFUSED
            rule, parameters = built
            with DirectoryStore(args.data / "directory.duckdb") as directory:
                selection = universe_builder.select(
                    directory, store, rule, clock.now(),
                    parameters=parameters, limit=args.limit,
                )
            if not selection.members:
                print(report.render_empty_universe(selection), file=sys.stderr)
                return 3, None, notify.Outcome.REFUSED

        # The retry lives HERE, wrapped around the injected fetcher, and not inside `run()`
        # (DR-015 §3). `pipeline.py` is one of the frozen files and, more to the point, must stay
        # pure: a `time.sleep` in the decision path is a decision that takes an hour on a bad night.
        # One instance per run, because its 90-second budget is a property of the run - see
        # `market_data/retry.py` for why an unbounded per-instrument retry is not what DR-015 costed.
        fetcher = RetryingFetcher(vendor_yahoo.fetch)

        # `fetch_actions` is passed UNWRAPPED by the retry, deliberately. `DR-015` §3's 90-second
        # budget is spent on the bars a decision needs; a corporate-actions fetch that fails leaves
        # the stored actions standing and the split guard reports `unavailable`, which is a smaller
        # loss than spending the run's retry budget on it. At most
        # `risk.max_concurrent_positions` calls an evening (`DR-016` §7).
        result = run(instruments, clock, registry, store, journal,
                     mode=mode, lookback=args.lookback, universe=selection,
                     positions=positions, classifications=classifications, fetcher=fetcher,
                     actions_fetcher=vendor_yahoo.fetch_actions)

        # Only when something failed. DR-015 §6 asks for a measured distribution of fetch failures
        # and observes that nobody has counted one; this is the line that starts counting, into
        # `data/daily_run.log` where the other run facts already live.
        if retries := fetcher.summary():
            print(retries, file=sys.stderr)

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

        if args.submit:
            _submit(result, args.data, clock.now(), journal, registry, positions)

    # The outcome distinguishes "go and read it" from "there is nothing to read". Sending
    # COMPLETE unconditionally told the owner "Report on disk." after a failed write - a notice
    # asserting something the run already knew to be false.
    outcome = (
        notify.Outcome.COMPLETE if written is not None else notify.Outcome.COMPLETE_NO_REPORT
    )
    return 0, result.manifest.run_id, outcome



if __name__ == "__main__":
    raise SystemExit(main())
