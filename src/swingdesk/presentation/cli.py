"""Command-line entry point. The complete surface (PRODUCT_SURFACES 3.1)."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from swingdesk.application import universe as universe_builder
from swingdesk.application.pipeline import run
from swingdesk.contracts.observation import ParameterUse
from swingdesk.contracts.position import ActionStatus, Fill, ManagementAction, Position
from swingdesk.contracts.reference import Instrument
from swingdesk.contracts.run import RunMode
from swingdesk.journal_evidence.journal import Journal
from swingdesk.journal_evidence.positions import CapOverride, PositionStore
from swingdesk.market_data import BarStore, vendor_yahoo
from swingdesk.market_data.retry import RetryingFetcher
from swingdesk.platform.clock import FixedClock, SystemClock
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset
from swingdesk.presentation import notify, report
from swingdesk.reference_data import calendar as cal
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
    allowed_risk,
    costs_per_share,
    to_base_currency,
)

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

    args = parser.parse_args(argv)

    if args.command == "record-fill":
        return _record_fill(args)

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

    # The outcome distinguishes "go and read it" from "there is nothing to read". Sending
    # COMPLETE unconditionally told the owner "Report on disk." after a failed write - a notice
    # asserting something the run already knew to be false.
    outcome = (
        notify.Outcome.COMPLETE if written is not None else notify.Outcome.COMPLETE_NO_REPORT
    )
    return 0, result.manifest.run_id, outcome



if __name__ == "__main__":
    raise SystemExit(main())
