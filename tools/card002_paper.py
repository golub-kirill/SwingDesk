"""`CARD-002` on the paper account: the close pass, the exit pass, and what the nights earned. `DR-054`.

**What this is.** `DR-048` §3 specifies two passes that put the card on the paper account and
nothing had built them: a buy of each fund into the closing auction, and a sell of exactly what
filled into the next opening auction. The owner chose on 2026-09-26 to build them, so the paper
account carries the rule at the size ruled on 2026-09-20 - half the equity a fund, every night.

**What it is NOT.** The auction's cost. Alpaca's paper fills are simulated (`DR-048` §2), so a paper
night returns this project's own cost model to it. The twenty REAL sessions measure the cost, and
their fills live in `executions.jsonl`; paper nights live in `paper.jsonl` and never mix (`DR-054`
§6).

**The order of work inside each pass is the design:**

* `close` - heal any order the ledger sent without an answer, reconcile every earlier night (both
  sides filled, nothing still held), and only then size and buy. A night still held refuses BOTH
  funds tonight: buying on top of an exit that did not fill doubles the position nobody decided.
* `exit` - for each of the night's buys, ask the venue what filled, by our own id, and lodge a
  market-on-open sell for exactly that. That sell is the card's only protection (`DR-048` §5), so a
  filled buy left without one is an ALERT, never a log line.

Every order is written to the ledger BEFORE it is sent, under an id derived from the session and
the fund, so a retried pass cannot send one night twice - the venue rejects a repeated id.

**The day leg (`DR-056`).** The paper account carries `PR-035`'s whole book: the exit pass also
buys `SPY` in the next opening auction with what the night's sale frees, the morning pass lodges a
market-on-close sell for exactly what that buy filled, and the close pass checks the sell is
standing before it buys the night - so `SPY` is held from the opening cross to the closing cross
with its exit resting (`DR-055` §4).

    python tools/card002_paper.py close   [--data DIR] [--as-of ISO] [--dry-run]
    python tools/card002_paper.py exit    [--data DIR] [--as-of ISO] [--dry-run]
    python tools/card002_paper.py morning [--data DIR] [--as-of ISO] [--dry-run]
    python tools/card002_paper.py report  [--data DIR]

    exit 0  done, or nothing to do
    exit 2  REFUSED - outside its window, no session, a stale close, or the switch stopped
    exit 3  ALERT - the machinery is wrong: a night still held, or a filled buy with no exit lodged
    exit 4  UNAVAILABLE - the venue, the store or the ledger could not be read
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(REPO / "src"))

from swingdesk import broker as broker_pkg
from swingdesk.broker import night
from swingdesk.contracts.broker import NightOrder, PlacedOrder, Side
from swingdesk.contracts.market import Interval, Series
from swingdesk.contracts.reference import Exchange, ExchangeSession
from swingdesk.market_data import BarStore
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data import calendar as cal

FUNDS = ("IJR", "VB")
#: `DR-056`: the day leg, bought in the opening auction and sold in the closing one.
DAY_FUND = "SPY"

OK = 0
REFUSED = 2
ALERT = 3
UNAVAILABLE = 4

#: The exchange's own clock. Every window below is ET, whatever the machine keeps.
ET = ZoneInfo("America/New_York")

#: `DR-054` §2. The venue refuses `cls` from ten minutes before the close; the pass shuts two
#: minutes earlier so a slow request cannot land on the wrong side of it, and opens thirty minutes
#: before so a trigger a few seconds early is not a missed night. Both hang off the calendar's
#: close, so an early close moves the window with it.
CLOSE_WINDOW_OPENS = timedelta(minutes=30)
CLOSE_WINDOW_SHUTS = timedelta(minutes=12)

#: The venue accepts `opg` after 19:00 ET, or before 09:28 ET for that morning's open.
EXIT_AFTER = time(19, 0)
EXIT_BEFORE = time(9, 28)

#: `DR-056` §3. The morning pass lodges the day leg's closing sell once the opening buy can have
#: filled, and no later than the close pass's own cut-off - the venue refuses `cls` from ten minutes
#: before the close.
MORNING_OPENS_AFTER = timedelta(minutes=10)

#: Statuses after which an order fills nothing more. Anything else is still in the venue's hands.
FINISHED = frozenset({"filled", "canceled", "expired", "rejected", "done_for_day", "replaced"})

#: Statuses of an order that will never execute. A sell in one of these protects nothing.
DEAD = frozenset({"canceled", "expired", "rejected", "replaced", "absent"})


class Unavailable(Exception):
    """Something this pass must read could not be read - never a silent zero."""


def buy_id(prefix: str, session: date, fund: str) -> str:
    return f"{prefix}-{session.isoformat()}-{fund}-buy"


def sell_id(prefix: str, session: date, fund: str, attempt: int) -> str:
    return f"{prefix}-{session.isoformat()}-{fund}-sell-{attempt}"


def close_window(exchange: Exchange, now: datetime) -> ExchangeSession | str:
    """Today's session when `now` is inside the close pass's window, else why not."""
    today = cal.session(exchange, now.astimezone(ET).date())
    if today is None:
        return f"{now.astimezone(ET):%Y-%m-%d} is not a {exchange.value} session"
    opens = today.close_time - CLOSE_WINDOW_OPENS
    shuts = today.close_time - CLOSE_WINDOW_SHUTS
    if now < opens:
        return (f"too early: the close pass runs from {opens.astimezone(ET):%H:%M} ET, "
                f"{now.astimezone(ET):%H:%M} ET now")
    if now > shuts:
        return (f"too late: the venue refuses a market-on-close order from "
                f"{(today.close_time - timedelta(minutes=10)).astimezone(ET):%H:%M} ET and the "
                f"pass stops at {shuts.astimezone(ET):%H:%M}. A late cls is an order for another "
                f"session's close, which nobody decided")
    return today


def exit_night(exchange: Exchange, now: datetime) -> date | str:
    """The session whose night the exit pass sells, or why it may not run now.

    After 19:00 ET on a session day it is that session. Before 09:28 ET it is the last session
    that has closed - a Monday morning run sells Friday's night. Between the two the venue
    refuses an `opg` order, and the pass does not try.
    """
    local = now.astimezone(ET)
    today = cal.session(exchange, local.date())
    if today is not None and local.time() >= EXIT_AFTER:
        return today.session_date
    if local.time() < EXIT_BEFORE:
        try:
            return cal.last_completed_session(exchange, now).session_date
        except LookupError as none:
            return f"no completed session to sell: {none}"
    return (f"{local:%H:%M} ET is outside the venue's market-on-open window "
            f"(after {EXIT_AFTER:%H:%M}, or before {EXIT_BEFORE:%H:%M})")


def size(equity: Decimal, cash: Decimal, position_pct: Decimal, close: Decimal,
         funds: int) -> int:
    """Whole shares of one fund: `position_pct` of equity, capped at the fund's share of cash.

    `DR-054` §5. The cap is `CARD-002` §3's *account short of cash* applied proportionally: the
    card never borrows. Rounded DOWN, because a fund rounded up is larger than the ruled size.
    """
    if close <= 0 or funds <= 0:
        return 0
    notional = min(equity * position_pct / Decimal(100), cash / Decimal(funds))
    if notional <= 0:
        return 0
    return int((notional / close).to_integral_value(rounding=ROUND_DOWN))


def day_size(equity: Decimal, cash: Decimal, freed: Decimal, close: Decimal) -> int:
    """Whole shares of the day leg: the cash plus what the night's sale frees, never above equity.

    `DR-056` §2. The same dollar twice, as `PR-035` measured it - and never borrowed, even though the
    venue's buying power would lend it across the auction. Rounded down.
    """
    if close <= 0:
        return 0
    dollars = min(equity, cash + freed)
    if dollars <= 0:
        return 0
    return int((dollars / close).to_integral_value(rounding=ROUND_DOWN))


def next_session(exchange: Exchange, after: date) -> date | None:
    """The first session after `after`, from the calendar."""
    later = cal.sessions(exchange, after + timedelta(days=1), after + timedelta(days=14))
    return later[0].session_date if later else None


def whole(shares: Decimal) -> int:
    """A filled quantity as whole shares. A fraction is refused - this card never sends one."""
    if shares != shares.to_integral_value():
        raise Unavailable(f"the venue reports {shares} shares filled, which is not a whole number")
    return int(shares)


@dataclass
class Pass:
    """One run of one pass: the venue, the ledger's directory, the moment, and what it found."""

    client: Any
    data: Path
    now: datetime
    dry_run: bool = False

    def __post_init__(self) -> None:
        self.alerts: list[str] = []
        self.prefix = self._night_policy().client_order_id_prefix

    def _night_policy(self) -> Any:
        write = self.client.policy.write
        if write is None or write.night is None:
            raise Unavailable("the committed policy grants no night order shape (write.night_*)")
        return write.night

    def write(self, row: dict[str, Any]) -> None:
        if not self.dry_run:
            night.append(self.data, {**row, "at": self.now.isoformat()})

    def ledger(self) -> night.Ledger:
        try:
            return night.read(self.data)
        except night.LedgerUnreadable as unreadable:
            raise Unavailable(str(unreadable)) from unreadable

    def heal(self) -> night.Ledger:
        """Ask the venue about every order the ledger sent without an answer. `DR-054` §3.4."""
        ledger = self.ledger()
        for sent in ledger.unanswered():
            found = self.client.order_by_client_id(sent.client_order_id, self.now)
            print(f"  healed   {sent.client_order_id}: "
                  f"{'the venue never saw it' if found is None else found.status}")
            self.write({
                "kind": "answered", "client_order_id": sent.client_order_id,
                "order_id": "" if found is None else found.order_id,
                "status": "absent" if found is None else found.status,
            })
        return ledger if self.dry_run else self.ledger()

    def order_of(self, ledger: night.Ledger, sent: night.Sent) -> PlacedOrder | None:
        """The venue's current view of one of our orders, or `None` if it never landed."""
        answer = ledger.answered.get(sent.client_order_id)
        if answer is None:
            raise Unavailable(
                f"{sent.client_order_id} was sent and never answered, and the heal found no "
                f"answer either - its fills cannot be attributed")
        if not answer.order_id:
            return None
        found: PlacedOrder = self.client.order(answer.order_id, self.now)
        return found

    def send(self, order: NightOrder, extra: dict[str, Any] | None = None) -> PlacedOrder | None:
        """Write the order to the ledger, then send it. `None` on a dry run or a failed send.

        A send that raised leaves its `sent` row UNANSWERED on purpose: the request may have
        landed, and the next pass's heal asks the venue rather than guessing.
        """
        if self.dry_run:
            print(f"  WOULD SEND {order.side.value:<4} {order.shares:>6} {order.symbol:<4} "
                  f"{order.client_order_id}")
            return None
        self.write({"kind": "sent", "session": order.session_date.isoformat(),
                    "fund": order.symbol, "side": order.side.value, "shares": order.shares,
                    "client_order_id": order.client_order_id, **(extra or {})})
        try:
            placed: PlacedOrder = self.client.submit_night(order, self.now)
        except broker_pkg.BrokerUnavailable as unavailable:
            self.alerts.append(f"{order.client_order_id} may not have reached the venue: "
                               f"{unavailable}")
            return None
        self.write({"kind": "answered", "client_order_id": order.client_order_id,
                    "order_id": placed.order_id, "status": placed.status})
        print(f"  SENT     {order.side.value:<4} {order.shares:>6} {order.symbol:<4} "
              f"{placed.status}  {order.client_order_id}")
        return placed


def lodge_exit(run: Pass, ledger: night.Ledger, session: date, fund: str, what: str) -> int:
    """Make sure a leg's filled buy has a resting sell for exactly what filled. Returns the filled.

    One rule for every leg: the night's market-on-open sell, and the day leg's market-on-close sell
    (`submit_night` chooses the auction by the symbol). A refused sell is re-sent under a new id,
    and a filled buy the switch will not let this protect is an ALERT, never a log line.
    """
    buys = ledger.orders(session, fund, Side.BUY)
    if not buys:
        print(f"  nothing  {fund}: no buy for {session}")
        return 0
    bought = run.order_of(ledger, buys[-1])
    if bought is None:
        print(f"  nothing  {fund}: the venue never saw the buy")
        return 0
    filled = whole(bought.filled_shares)
    if filled == 0:
        if bought.status not in FINISHED:
            run.alerts.append(f"{fund}: the buy for {session} is still {bought.status}")
        else:
            print(f"  nothing  {fund}: the buy did not fill ({bought.status})")
        return 0

    attempts = ledger.orders(session, fund, Side.SELL)
    lodged = 0
    for sent in attempts:
        sold = run.order_of(ledger, sent)
        if sold is None or sold.status in DEAD:
            continue
        lodged += sent.shares
    remaining = filled - lodged
    if remaining <= 0:
        print(f"  lodged   {fund}: the {what} sell for {filled} is already at the venue")
        return filled
    try:
        run.client.guards()
    except broker_pkg.SubmissionStopped as stopped:
        run.alerts.append(
            f"{fund}: {filled} held and no {what} sell lodged, and the switch refuses: {stopped}. "
            f"Re-arm and re-run the pass, or sell by hand")
        return filled
    run.send(NightOrder(
        client_order_id=sell_id(run.prefix, session, fund, len(attempts) + 1),
        session_date=session, symbol=fund, side=Side.SELL, shares=remaining,
    ))
    return filled


def reconcile_nights(run: Pass, ledger: night.Ledger, before: date) -> None:
    """Close every earlier night whose sells matched its buy; alert on any that did not."""
    for session, fund in ledger.open_nights():
        if session >= before:
            continue
        buys = ledger.orders(session, fund, Side.BUY)
        bought = run.order_of(ledger, buys[-1])
        if bought is not None and bought.status not in FINISHED:
            run.alerts.append(f"{fund}, night of {session}: the buy is still {bought.status}")
            continue
        bought_n = 0 if bought is None else whole(bought.filled_shares)

        sold_n = 0
        sold_value = Decimal(0)
        pending = False
        for sent in ledger.orders(session, fund, Side.SELL):
            sold = run.order_of(ledger, sent)
            if sold is None:
                continue
            if sold.status not in FINISHED:
                pending = True
            filled = whole(sold.filled_shares)
            if filled:
                sold_n += filled
                sold_value += Decimal(filled) * (sold.filled_average_price or Decimal(0))

        if bought_n == 0:
            run.write({"kind": "night", "session": session.isoformat(), "fund": fund,
                       "shares": 0, "note": "the buy did not fill"})
            print(f"  night    {session} {fund}: the buy did not fill - nothing was held")
            continue
        if sold_n != bought_n or pending:
            run.alerts.append(
                f"CARD-002 still holds {bought_n - sold_n} {fund} from {session}: "
                f"{bought_n} bought, {sold_n} sold{', a sell still working' if pending else ''}. "
                f"The leg's exit did not complete, and the card buys nothing on top of it")
            continue
        assert bought is not None and bought.filled_average_price is not None
        entry = bought.filled_average_price
        exit_price = sold_value / Decimal(sold_n)
        pnl = (exit_price - entry) * Decimal(bought_n)
        run.write({"kind": "night", "session": session.isoformat(), "fund": fund,
                   "shares": bought_n, "entry": str(entry), "exit": str(exit_price),
                   "pnl": str(pnl.quantize(Decimal("0.01")))})
        print(f"  night    {session} {fund}: {bought_n} sh {entry} -> {exit_price:.4f}  "
              f"P&L {pnl:+.2f}")


def close_pass(run: Pass, position_pct: Decimal,
               closes: Callable[[str, date], tuple[Decimal, date] | str]) -> int:
    """Reconcile, then buy each fund into the closing auction. `DR-054` §2 and §5."""
    exchange = Exchange(run.client.policy.market)
    window = close_window(exchange, run.now)
    if isinstance(window, str):
        print(f"CARD-002 close REFUSED  {window}")
        return REFUSED
    session = window.session_date
    print(f"CARD-002 close   session {session}   {run.now.astimezone(ET):%H:%M} ET")

    ledger = run.heal()
    # `DR-056` §3: the day leg's closing sell must be standing before anything else is sized - a
    # SPY position held past this auction would be a night leg nobody decided.
    day_held = lodge_exit(run, ledger, session, DAY_FUND, "market-on-close") \
        if ledger.orders(session, DAY_FUND, Side.BUY) else 0
    ledger = ledger if run.dry_run else run.ledger()
    reconcile_nights(run, ledger, before=session)
    if run.alerts:
        for alert in run.alerts:
            print(f"  ALERT    {alert}")
        return ALERT

    try:
        run.client.guards()
    except broker_pkg.SubmissionStopped as stopped:
        print(f"  STOPPED  {stopped}")
        if not run.dry_run:
            return REFUSED

    account = run.client.account(run.now)
    prior = cal.last_completed_session(exchange, run.now).session_date
    # What the day leg's sale frees in the same auction: the night is bought with it.
    freed = Decimal(0)
    if day_held:
        spy = closes(DAY_FUND, prior)
        if isinstance(spy, str):
            print(f"  REFUSED  the day leg's value is unknown: {spy}")
            return REFUSED
        freed = Decimal(day_held) * spy[0]
    print(f"  account  equity {account.equity}  cash {account.cash}  freed by the day leg "
          f"{freed:.2f}   sized from the close of {prior}")
    refused = 0
    for fund in FUNDS:
        if ledger.orders(session, fund, Side.BUY):
            print(f"  already  {fund}: tonight's buy is in the ledger - not sent twice")
            continue
        priced = closes(fund, prior)
        if isinstance(priced, str):
            print(f"  REFUSED  {fund}: {priced}")
            refused += 1
            continue
        close, _ = priced
        shares = size(account.equity, account.cash + freed, position_pct, close, len(FUNDS))
        if shares <= 0:
            print(f"  REFUSED  {fund}: no whole share fits at {close}")
            refused += 1
            continue
        run.send(
            NightOrder(client_order_id=buy_id(run.prefix, session, fund), session_date=session,
                       symbol=fund, side=Side.BUY, shares=shares),
            extra={"close": str(close), "equity": str(account.equity), "cash": str(account.cash)},
        )
    if run.alerts:
        for alert in run.alerts:
            print(f"  ALERT    {alert}")
        return ALERT
    return REFUSED if refused else OK


def exit_pass(run: Pass,
              closes: Callable[[str, date], tuple[Decimal, date] | str] | None = None) -> int:
    """Lodge the night's market-on-open sells, then buy the day leg in the same auction.

    `DR-054` §2 for the night, `DR-056` §1-§2 for the day leg. The day leg is bought only when every
    filled night leg has its sell standing, and with no more than that sale frees.
    """
    exchange = Exchange(run.client.policy.market)
    session = exit_night(exchange, run.now)
    if isinstance(session, str):
        print(f"CARD-002 exit REFUSED  {session}")
        return REFUSED
    print(f"CARD-002 exit    the night of {session}   {run.now.astimezone(ET):%H:%M} ET")

    ledger = run.heal()
    held: dict[str, int] = {}
    for fund in FUNDS:
        held[fund] = lodge_exit(run, ledger, session, fund, "market-on-open")
    if run.alerts:
        for alert in run.alerts:
            print(f"  ALERT    {alert}")
        return ALERT
    if closes is None:
        return OK

    day = next_session(exchange, session)
    if day is None:
        print("  day leg  no next session in the calendar")
        return OK
    ledger = ledger if run.dry_run else run.ledger()
    if ledger.orders(day, DAY_FUND, Side.BUY):
        print(f"  already  {DAY_FUND}: the day leg for {day} is in the ledger - not sent twice")
        return OK
    freed = Decimal(0)
    for fund, shares in held.items():
        if shares:
            priced = closes(fund, session)
            if isinstance(priced, str):
                print(f"  REFUSED  day leg: {fund}'s close is unknown ({priced})")
                return REFUSED
            freed += Decimal(shares) * priced[0]
    spy = closes(DAY_FUND, session)
    if isinstance(spy, str):
        print(f"  REFUSED  day leg: {spy}")
        return REFUSED
    try:
        run.client.guards()
    except broker_pkg.SubmissionStopped as stopped:
        print(f"  STOPPED  day leg: {stopped}")
        return REFUSED if not run.dry_run else OK
    account = run.client.account(run.now)
    shares = day_size(account.equity, account.cash, freed, spy[0])
    if shares <= 0:
        print(f"  REFUSED  day leg: no whole share of {DAY_FUND} fits")
        return REFUSED
    run.send(
        NightOrder(client_order_id=buy_id(run.prefix, day, DAY_FUND), session_date=day,
                   symbol=DAY_FUND, side=Side.BUY, shares=shares),
        extra={"close": str(spy[0]), "equity": str(account.equity), "cash": str(account.cash),
               "freed": str(freed)},
    )
    if run.alerts:
        for alert in run.alerts:
            print(f"  ALERT    {alert}")
        return ALERT
    return OK


def morning_window(exchange: Exchange, now: datetime) -> ExchangeSession | str:
    """Today's session when the day leg's buy can have filled and a `cls` sell can still be sent."""
    today = cal.session(exchange, now.astimezone(ET).date())
    if today is None:
        return f"{now.astimezone(ET):%Y-%m-%d} is not a {exchange.value} session"
    if now < today.open_time + MORNING_OPENS_AFTER:
        return f"too early: the opening auction is at {today.open_time.astimezone(ET):%H:%M} ET"
    if now > today.close_time - CLOSE_WINDOW_SHUTS:
        return "too late: the venue refuses a market-on-close order this close to the close"
    return today


def morning_pass(run: Pass) -> int:
    """Lodge the day leg's market-on-close sell for exactly what its opening buy filled. `DR-056`."""
    exchange = Exchange(run.client.policy.market)
    window = morning_window(exchange, run.now)
    if isinstance(window, str):
        print(f"CARD-002 morning REFUSED  {window}")
        return REFUSED
    session = window.session_date
    print(f"CARD-002 morning session {session}   {run.now.astimezone(ET):%H:%M} ET")
    ledger = run.heal()
    lodge_exit(run, ledger, session, DAY_FUND, "market-on-close")
    if run.alerts:
        for alert in run.alerts:
            print(f"  ALERT    {alert}")
        return ALERT
    return OK


#: `DR-055` §1.3's proof (2): sixty sessions of the whole book with no machinery defect.
PROOF_SESSIONS = 60


def previous_session(exchange: Exchange, day: date) -> date | None:
    """The last session before `day`, from the calendar."""
    for back in range(1, 15):
        earlier = day - timedelta(days=back)
        if cal.session(exchange, earlier) is not None:
            return earlier
    return None


def book_sessions(rows: Sequence[dict[str, Any]], exchange: Exchange) -> list[date]:
    """Sessions the paper account carried the WHOLE book cleanly - what `DR-055`'s proof (2) counts.

    Session D counts when `SPY` was held from D's opening auction to its closing one AND both small-
    cap funds were held from the previous session's close into D's open, each leg journalled as a
    priced row. A leg that did not fill, or whose exit did not match its buy, leaves no priced row
    (`reconcile_nights`), so its session does not count. The day leg's row is keyed by the session
    it was held in; a night leg's by the session it was bought in.
    """
    priced = {(date.fromisoformat(row["session"]), row["fund"]) for row in rows
              if row.get("kind") == "night" and row.get("shares")}
    out: list[date] = []
    for day, fund in sorted(priced):
        if fund != DAY_FUND:
            continue
        prior = previous_session(exchange, day)
        if prior is not None and all((prior, leg) in priced for leg in FUNDS):
            out.append(day)
    return out


def report(data: Path) -> int:
    """What the paper nights earned. Simulated fills - the curve, not the auction's cost."""
    path = night.ledger_path(data)
    if not path.exists():
        print("CARD-002 paper: no night journalled yet")
        return OK
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    except (OSError, ValueError) as unreadable:
        print(f"CARD-002 paper UNAVAILABLE: {unreadable}")
        return UNAVAILABLE

    priced = [row for row in rows if row.get("kind") == "night" and row.get("shares")]
    nights = [row for row in priced if row["fund"] != DAY_FUND]
    days = [row for row in priced if row["fund"] == DAY_FUND]
    first_equity = next((Decimal(row["equity"]) for row in rows
                         if row.get("kind") == "sent" and row.get("equity")), None)
    whole = book_sessions(rows, Exchange.NYSE)
    print(f"CARD-002 on the paper account - {len(nights)} fund-night(s) priced, "
          f"{len(days)} {DAY_FUND} day leg(s) priced")
    print(f"  whole-book sessions {len(whole)} of the {PROOF_SESSIONS} DR-055's proof (2) needs"
          + (f"   first {whole[0]}   last {whole[-1]}" if whole else ""))
    if priced:
        pnls = [Decimal(row["pnl"]) for row in priced]
        total = sum(pnls, Decimal(0))
        worst = min(priced, key=lambda row: Decimal(row["pnl"]))
        up = sum(1 for pnl in pnls if pnl > 0)
        print(f"  first {priced[0]['session']}   last {priced[-1]['session']}")
        print(f"  realised P&L  {total:+,.2f} USD   mean {total / len(pnls):+,.2f} a leg")
        if first_equity:
            print(f"  on the first night's equity ({first_equity:,.2f})  "
                  f"{total / first_equity * 100:+.2f}%")
        print(f"  up {up} / down {len(pnls) - up}   worst {Decimal(worst['pnl']):+,.2f} "
              f"({worst['fund']}, {'the day' if worst['fund'] == DAY_FUND else 'the night'} of "
              f"{worst['session']})")
    ledger = night.read(data)
    for session, fund in ledger.open_nights():
        print(f"  open     {fund}, night of {session}")
    print("  Paper fills are simulated: this is the rule's curve at full size, not what the "
          "auctions cost (DR-054 section 6). Dividends are credited by the venue apart from this.")
    return OK


def store_closes(path: Path, now: datetime) -> Callable[[str, date], tuple[Decimal, date] | str]:
    """Each fund's close on an expected session, as the store knew it at `now`, or why none.

    As of the pass's own clock rather than the store's latest instant, so a rehearsal with
    `--as-of` reads what the pass would have read then. The store refuses an unclosed bar on
    write, so a fetch during the session never makes today's partial print the prior close.
    """
    def closes(fund: str, expected: date) -> tuple[Decimal, date] | str:
        if not path.exists():
            return f"no bar store at {path}"
        store = BarStore(path)
        try:
            bars = store.as_of(fund, Interval.DAY, Series.RAW, now).bars
        finally:
            store.close()
        if not bars:
            return f"no bar stored as of {now:%Y-%m-%d %H:%M} UTC"
        last = bars[-1]
        if last.session_date != expected:
            return (f"the last stored close is {last.session_date} and the prior session is "
                    f"{expected}. Fetch the two funds first (runbook section 11.1)")
        return Decimal(str(last.close)), last.session_date
    return closes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("mode", choices=("close", "exit", "morning", "report"))
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--as-of", help="an ISO instant; pins the clock (tests and rehearsals)")
    parser.add_argument("--dry-run", action="store_true",
                        help="read the venue and print what would be sent; write and send nothing")
    args = parser.parse_args(argv)

    if args.mode == "report":
        return report(args.data)

    now = (datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(UTC))
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    try:
        policy = broker_pkg.load_policy()
        if policy.write is None:
            print("CARD-002 REFUSED  the committed policy grants no write section")
            return REFUSED
        arming = broker_pkg.read_arming(args.data, policy.write)
        client = broker_pkg.open_client(policy, arming=arming)
        run = Pass(client, args.data, now, dry_run=args.dry_run)
        closes = store_closes(args.data / "bars.duckdb", now)
        if args.mode == "close":
            registry = ParameterRegistry.load(REPO / "registry" / "parameters.yml")
            position_pct, _use = registry.decimal_value("overnight.position_pct")
            return close_pass(run, position_pct, closes)
        if args.mode == "morning":
            return morning_pass(run)
        return exit_pass(run, closes)
    except (broker_pkg.PolicyRefused, broker_pkg.CredentialsMissing) as refused:
        print(f"CARD-002 {args.mode} REFUSED  {refused}")
        return REFUSED
    except (broker_pkg.BrokerUnavailable, Unavailable) as unavailable:
        print(f"CARD-002 {args.mode} UNAVAILABLE  {unavailable}")
        return UNAVAILABLE


if __name__ == "__main__":  # pragma: no cover - the entry point
    raise SystemExit(main())
