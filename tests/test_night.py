"""`CARD-002` on the paper account (`DR-054`): the order shape, the ledger, the view, and both passes.

Offline like every other test here: the transport is injected, and the paper passes run against
a venue fake that keeps its own order book, so a pass that forgot what it sent is caught by the
venue it forgot it on.

**Most of the view's tests are written from the OTHER side's vocabulary** - a person's order that
looks like ours, a holding larger than ours, an answer that never arrived. `AGENTS.md` §12's first
trap is a fixture built from the same assumption as the code, and `DR-050` was that trap costing
every stop-out the book ever had.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from swingdesk.broker import night
from swingdesk.broker import policy as policy_module
from swingdesk.broker.alpaca import AlpacaClient, BrokerUnavailable, Credentials, SubmissionStopped
from swingdesk.broker.armed import STOPPED, Arming
from swingdesk.broker.policy import PolicyRefused
from swingdesk.contracts.broker import (
    BrokerAccount,
    BrokerFill,
    BrokerPosition,
    FillKind,
    NightOrder,
    PlacedOrder,
    PositionSide,
    Side,
)

REPO = Path(__file__).resolve().parents[1]
ARMED = Arming(True, "armed in a test")

#: Monday 2026-09-28, a regular session: the close is 16:00 ET, 20:00 UTC.
MONDAY = date(2026, 9, 28)
FRIDAY = date(2026, 9, 25)
AT_CLOSE_PASS = datetime(2026, 9, 28, 19, 40, tzinfo=UTC)      # 15:40 ET
AT_EXIT_PASS = datetime(2026, 9, 28, 23, 10, tzinfo=UTC)       # 19:10 ET
TUESDAY_CLOSE_PASS = datetime(2026, 9, 29, 19, 40, tzinfo=UTC)


@pytest.fixture(scope="module")
def paper():
    """The tool, imported by path - `tools/` is not a package and CI_POLICY 4 keeps it that way."""
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location("card002_paper", REPO / "tools" / "card002_paper.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# --- the policy: one shape, all or nothing ----------------------------------------------------


def _policy_with(tmp_path: Path, **write: object) -> policy_module.BrokerPolicy:
    raw = yaml.safe_load(policy_module.POLICY_PATH.read_text(encoding="utf-8"))
    for key, value in write.items():
        if value is None:
            raw["write"].pop(key, None)
        else:
            raw["write"][key] = value
    written = tmp_path / "broker_policy.yml"
    written.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return policy_module.load(written)


def test_the_committed_policy_permits_the_night_shape_for_two_funds_only() -> None:
    write = policy_module.load().write
    assert write is not None and write.night is not None
    assert write.night.symbols == frozenset({"IJR", "VB"})
    assert (write.night.entry_time_in_force, write.night.exit_time_in_force) == ("cls", "opg")
    assert write.night.order_type == "market"


def test_half_a_night_block_refuses_to_load(tmp_path: Path) -> None:
    """The half most likely to go missing is the symbol list - the boundary itself."""
    with pytest.raises(PolicyRefused, match="night_symbols"):
        _policy_with(tmp_path, night_symbols=None)


def test_an_entry_and_exit_in_the_same_auction_refuse(tmp_path: Path) -> None:
    with pytest.raises(PolicyRefused, match="both"):
        _policy_with(tmp_path, night_exit_time_in_force="cls")


def test_a_night_prefix_that_repeats_another_refuses(tmp_path: Path) -> None:
    with pytest.raises(PolicyRefused, match="duplicate id"):
        _policy_with(tmp_path, night_client_order_id_prefix="swingdesk-protect")


def test_a_policy_without_the_block_loads_and_carries_none(tmp_path: Path) -> None:
    keys = {key: None for key in policy_module.NIGHT_KEYS}
    loaded = _policy_with(tmp_path, **keys)
    assert loaded.write is not None and loaded.write.night is None


# --- the adapter: its own method, never a widened `submit` ------------------------------------


PLACED = {
    "id": "7a000000-0000-0000-0000-0000000000n1",
    "client_order_id": "swingdesk-night-2026-09-28-IJR-buy",
    "symbol": "IJR", "status": "accepted", "side": "buy", "type": "market",
    "time_in_force": "cls", "submitted_at": "2026-09-28T19:40:01.000Z", "filled_qty": "0",
    "filled_avg_price": None,
}


def _transport(payload: object, status: int = 200):
    sent: list[dict[str, object]] = []

    def _call(method, url, headers, timeout_seconds, max_bytes, body=None):
        sent.append({"method": method, "url": url,
                     "body": json.loads(body) if body else None})
        return status, json.dumps(payload).encode("utf-8")

    _call.sent = sent  # type: ignore[attr-defined]
    return _call


def _client(arming: Arming = ARMED, payload: object = PLACED, status: int = 200) -> AlpacaClient:
    return AlpacaClient(policy=policy_module.load(), credentials=Credentials(key_id="k", secret="s"),
                        transport=_transport(payload, status), arming=arming)


def _night_order(symbol: str = "IJR", side: Side = Side.BUY, shares: int = 361,
                 client_order_id: str | None = None) -> NightOrder:
    return NightOrder(
        client_order_id=client_order_id or f"swingdesk-night-2026-09-28-{symbol}-"
                                           f"{'buy' if side is Side.BUY else 'sell-1'}",
        session_date=MONDAY, symbol=symbol, side=side, shares=shares,
    )


def test_an_unarmed_client_sends_no_night_order() -> None:
    client = _client(arming=STOPPED)
    with pytest.raises(SubmissionStopped):
        client.submit_night(_night_order(), AT_CLOSE_PASS)
    assert client.transport.sent == []  # type: ignore[attr-defined]


def test_the_buy_is_a_market_on_close_with_no_legs_and_no_limit() -> None:
    client = _client()
    placed = client.submit_night(_night_order(), AT_CLOSE_PASS)
    [request] = client.transport.sent  # type: ignore[attr-defined]
    assert request["body"] == {
        "symbol": "IJR", "qty": "361", "side": "buy", "type": "market",
        "time_in_force": "cls", "client_order_id": "swingdesk-night-2026-09-28-IJR-buy",
    }
    assert placed.order_id == PLACED["id"] and placed.time_in_force == "cls"


def test_the_sell_is_a_market_on_open() -> None:
    order = _night_order(side=Side.SELL)
    client = _client(payload={**PLACED, "client_order_id": order.client_order_id, "side": "sell",
                              "time_in_force": "opg"})
    client.submit_night(order, AT_EXIT_PASS)
    [request] = client.transport.sent  # type: ignore[attr-defined]
    assert request["body"]["side"] == "sell" and request["body"]["time_in_force"] == "opg"


def test_a_symbol_outside_the_policy_never_reaches_the_wire() -> None:
    """An order with no stop is permitted for the two ratified funds and nothing else."""
    client = _client()
    with pytest.raises(SubmissionStopped, match="night_symbols"):
        client.submit_night(_night_order(symbol="QQQ"), AT_CLOSE_PASS)
    assert client.transport.sent == []  # type: ignore[attr-defined]


def test_an_id_without_the_night_prefix_never_reaches_the_wire() -> None:
    client = _client()
    with pytest.raises(SubmissionStopped, match="prefix"):
        client.submit_night(_night_order(client_order_id="swingdesk-2026-09-28-IJR"),
                            AT_CLOSE_PASS)
    assert client.transport.sent == []  # type: ignore[attr-defined]


def test_an_echo_that_names_another_order_is_not_accepted() -> None:
    client = _client(payload={**PLACED, "client_order_id": "somebody-else"})
    with pytest.raises(BrokerUnavailable, match="echoed"):
        client.submit_night(_night_order(), AT_CLOSE_PASS)


def test_a_lookup_by_our_id_that_the_venue_never_saw_is_none() -> None:
    client = _client(payload={"code": 40410000, "message": "order not found"}, status=404)
    assert client.order_by_client_id("swingdesk-night-2026-09-28-IJR-buy", AT_EXIT_PASS) is None


def test_a_lookup_by_our_id_reads_the_fill() -> None:
    filled = {**PLACED, "status": "filled", "filled_qty": "361", "filled_avg_price": "138.41"}
    client = _client(payload=filled)
    found = client.order_by_client_id("swingdesk-night-2026-09-28-IJR-buy", AT_EXIT_PASS)
    assert found is not None
    assert found.filled_shares == Decimal(361) and found.filled_average_price == Decimal("138.41")


def test_a_404_anywhere_else_is_still_the_venue_failing() -> None:
    """`absent_ok` is for one lookup. An order read by the VENUE's id that 404s is a fault."""
    client = _client(payload={"message": "not found"}, status=404)
    # The STATUS in the message, not merely a refusal: a 404 read as "absent" and then parsed
    # as an order also raises, for the wrong reason, and that was this test's first draft.
    with pytest.raises(BrokerUnavailable, match="HTTP 404"):
        client.order("7a000000-0000-0000-0000-0000000000n1", AT_EXIT_PASS)


# --- the ledger ------------------------------------------------------------------------------


def _sent(data: Path, fund: str = "IJR", side: str = "buy", shares: int = 300,
          session: str = "2026-09-28", attempt: int = 1) -> str:
    client_id = (f"swingdesk-night-{session}-{fund}-buy" if side == "buy"
                 else f"swingdesk-night-{session}-{fund}-sell-{attempt}")
    night.append(data, {"kind": "sent", "session": session, "fund": fund, "side": side,
                        "shares": shares, "client_order_id": client_id})
    return client_id


def _answered(data: Path, client_id: str, order_id: str, status: str = "accepted") -> None:
    night.append(data, {"kind": "answered", "client_order_id": client_id,
                        "order_id": order_id, "status": status})


def test_an_absent_ledger_is_a_card_that_never_ran(tmp_path: Path) -> None:
    ledger = night.read(tmp_path)
    assert not ledger.started and ledger.open_nights() == ()


def test_an_unparseable_ledger_refuses_rather_than_reading_empty(tmp_path: Path) -> None:
    """Empty would set nothing aside AND let `CARD-001` resume entries. Only the first is safe."""
    path = night.ledger_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text('{"kind": "sent", "session": "not a date"}\n', encoding="utf-8")
    with pytest.raises(night.LedgerUnreadable):
        night.read(tmp_path)


def test_the_last_answer_wins(tmp_path: Path) -> None:
    """A heal that finds the order later overrides an earlier 'the venue never saw it'."""
    client_id = _sent(tmp_path)
    _answered(tmp_path, client_id, "", status="absent")
    _answered(tmp_path, client_id, "v-1")
    assert night.read(tmp_path).answered[client_id].order_id == "v-1"


def test_a_reconciled_night_is_no_longer_open(tmp_path: Path) -> None:
    _sent(tmp_path)
    _sent(tmp_path, fund="VB")
    night.append(tmp_path, {"kind": "night", "session": "2026-09-28", "fund": "IJR", "shares": 0})
    assert night.read(tmp_path).open_nights() == ((MONDAY, "VB"),)


# --- the view: CARD-001's account, less exactly what the ledger accounts for ------------------


def _order(order_id: str, client_id: str, symbol: str = "IJR", filled: int = 0,
           status: str = "accepted", price: str | None = None) -> PlacedOrder:
    return PlacedOrder(order_id=order_id, client_order_id=client_id, symbol=symbol, status=status,
                       submitted_at=AT_CLOSE_PASS, filled_shares=Decimal(filled),
                       filled_average_price=Decimal(price) if price else None,
                       observed_at=AT_CLOSE_PASS)


def _holding(symbol: str, shares: int) -> BrokerPosition:
    return BrokerPosition(symbol=symbol, asset_class="us_equity", exchange="ARCA",
                          side=PositionSide.LONG, shares=Decimal(shares),
                          average_entry_price=Decimal("138.00"), market_value=Decimal(1),
                          observed_at=AT_EXIT_PASS)


def _fill(order_id: str, symbol: str = "IJR") -> BrokerFill:
    return BrokerFill(activity_id=f"a-{order_id}", order_id=order_id, symbol=symbol,
                      side=Side.BUY, kind=FillKind.FILL, transaction_time=AT_EXIT_PASS,
                      price=Decimal("138.00"), shares=Decimal(1), observed_at=AT_EXIT_PASS)


class _Account:
    """What the venue holds and the orders it can be asked about by id."""

    def __init__(self, held=(), live=(), fills=(), orders=None) -> None:
        self.held, self.live, self._fills = tuple(held), tuple(live), tuple(fills)
        self.orders = orders or {}

    def positions(self, now):
        return self.held

    def open_orders(self, now):
        return self.live

    def fills(self, now, after=None):
        return self._fills

    def order(self, order_id, now):
        return self.orders[order_id]

    def submit(self, order, now):
        return "passed through"


def test_the_view_sets_aside_exactly_what_the_ledgers_buy_filled(tmp_path: Path) -> None:
    client_id = _sent(tmp_path, shares=300)
    _answered(tmp_path, client_id, "v-1")
    venue = _Account(held=[_holding("IJR", 300), _holding("GUARDED", 100)],
                     orders={"v-1": _order("v-1", client_id, filled=300, status="filled")})
    seen = night.view(venue, tmp_path).positions(AT_EXIT_PASS)
    assert [h.symbol for h in seen] == ["GUARDED"]


def test_a_holding_beyond_the_ledger_stays_in_view_and_claims_no_money_it_cannot_measure(
    tmp_path: Path
) -> None:
    """A person's 100 `IJR` beside the card's 300: the 100 is still a divergence."""
    client_id = _sent(tmp_path, shares=300)
    _answered(tmp_path, client_id, "v-1")
    venue = _Account(held=[_holding("IJR", 400)],
                     orders={"v-1": _order("v-1", client_id, filled=300, status="filled")})
    [rest] = night.view(venue, tmp_path).positions(AT_EXIT_PASS)
    assert rest.shares == Decimal(100) and rest.market_value is None


def test_a_sell_that_filled_releases_what_it_sold(tmp_path: Path) -> None:
    buy = _sent(tmp_path, shares=300)
    _answered(tmp_path, buy, "v-1")
    sell = _sent(tmp_path, side="sell", shares=300)
    _answered(tmp_path, sell, "v-2")
    venue = _Account(held=[_holding("IJR", 300)], orders={
        "v-1": _order("v-1", buy, filled=300, status="filled"),
        "v-2": _order("v-2", sell, filled=200, status="partially_filled"),
    })
    [rest] = night.view(venue, tmp_path).positions(AT_EXIT_PASS)
    assert rest.shares == Decimal(200), "only the 100 still held are the card's"


def test_a_buy_never_answered_cannot_be_set_aside(tmp_path: Path) -> None:
    """Its fills cannot be attributed, so they stay visible - the loud outcome."""
    _sent(tmp_path, shares=300)
    venue = _Account(held=[_holding("IJR", 300)])
    assert [h.symbol for h in night.view(venue, tmp_path).positions(AT_EXIT_PASS)] == ["IJR"]


def test_a_person_s_order_that_looks_like_ours_is_not_ours(tmp_path: Path) -> None:
    """Ownership is membership in the ledger, never the shape of the id."""
    ours = _sent(tmp_path)
    _answered(tmp_path, ours, "v-1")
    lookalike = _order("v-9", "swingdesk-night-2026-09-28-IJR-sell-7")
    venue = _Account(live=[_order("v-1", ours), lookalike])
    assert night.view(venue, tmp_path).open_orders(AT_EXIT_PASS) == (lookalike,)


def test_fills_are_filtered_by_the_venue_id_the_ledger_recorded(tmp_path: Path) -> None:
    ours = _sent(tmp_path)
    _answered(tmp_path, ours, "v-1")
    venue = _Account(fills=[_fill("v-1"), _fill("v-2", symbol="GUARDED")])
    assert [f.order_id for f in night.view(venue, tmp_path).fills(AT_EXIT_PASS)] == ["v-2"]


def test_the_view_passes_every_write_through_untouched(tmp_path: Path) -> None:
    assert night.view(_Account(), tmp_path).submit(object(), AT_EXIT_PASS) == "passed through"


def test_an_unreadable_ledger_sets_nothing_aside_and_counts_as_started(tmp_path: Path) -> None:
    path = night.ledger_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("not json\n", encoding="utf-8")
    view = night.view(_Account(held=[_holding("IJR", 300)]), tmp_path)
    assert [h.symbol for h in view.positions(AT_EXIT_PASS)] == ["IJR"]
    reason = night.retirement(view)
    assert reason is not None and "could not be read" in reason


def test_retirement_answers_none_until_the_card_has_sent_anything(tmp_path: Path) -> None:
    assert night.retirement(night.view(_Account(), tmp_path)) is None
    _sent(tmp_path)
    assert night.retirement(night.view(_Account(), tmp_path)) == night.RETIRED


def test_a_client_not_read_through_the_view_is_retired(tmp_path: Path) -> None:
    """Nothing then says whether the other card holds the account - so nothing is added."""
    reason = night.retirement(_Account())
    assert reason is not None and "not read through" in reason


# --- the paper passes -------------------------------------------------------------------------


class _Venue:
    """A paper venue that keeps its own order book, answers by either id, and can be filled."""

    def __init__(self, armed: bool = True, equity: str = "100000", cash: str = "100000") -> None:
        self.policy = policy_module.load()
        self.armed = armed
        self.equity, self.cash = Decimal(equity), Decimal(cash)
        self.orders: dict[str, PlacedOrder] = {}
        self.by_client: dict[str, str] = {}
        self.sent: list[NightOrder] = []
        self.raise_after_landing: Exception | None = None

    def guards(self) -> None:
        if not self.armed:
            raise SubmissionStopped("stopped in a test")

    def account(self, now):
        return BrokerAccount(venue="paper", base_url="https://paper", fingerprint="f",
                             status="ACTIVE", currency="USD", cash=self.cash, equity=self.equity,
                             buying_power=self.cash, trading_blocked=False, account_blocked=False,
                             observed_at=now)

    def submit_night(self, order: NightOrder, now):
        self.guards()
        if order.client_order_id in self.by_client:
            raise BrokerUnavailable("orders: HTTP 422: client_order_id must be unique")
        order_id = f"v-{len(self.orders) + 1}"
        placed = PlacedOrder(order_id=order_id, client_order_id=order.client_order_id,
                             symbol=order.symbol, status="accepted", submitted_at=now,
                             side=order.side.value, observed_at=now)
        self.orders[order_id] = placed
        self.by_client[order.client_order_id] = order_id
        self.sent.append(order)
        if self.raise_after_landing is not None:
            raised, self.raise_after_landing = self.raise_after_landing, None
            raise raised
        return placed

    def order(self, order_id, now):
        return self.orders[order_id]

    def order_by_client_id(self, client_id, now):
        order_id = self.by_client.get(client_id)
        return None if order_id is None else self.orders[order_id]

    def fill(self, client_id: str, shares: int, price: str, status: str = "filled") -> None:
        order_id = self.by_client[client_id]
        self.orders[order_id] = self.orders[order_id].model_copy(update={
            "filled_shares": Decimal(shares), "filled_average_price": Decimal(price),
            "status": status})

    def end(self, client_id: str, status: str) -> None:
        order_id = self.by_client[client_id]
        self.orders[order_id] = self.orders[order_id].model_copy(update={"status": status})


def _closes(prices: dict[str, str] | None = None, stale: tuple[str, ...] = ()):
    table = prices or {"IJR": "100.00", "VB": "200.00", "SPY": "400.00"}

    def closes(fund: str, expected: date):
        if fund in stale:
            return f"the last stored close is behind {expected}"
        return Decimal(table[fund]), expected
    return closes


def _close(paper, venue, data, now=AT_CLOSE_PASS, dry_run=False, closes=None):
    return paper.close_pass(paper.Pass(venue, data, now, dry_run=dry_run), Decimal(50),
                            closes or _closes())


def _exit(paper, venue, data, now=AT_EXIT_PASS, dry_run=False):
    return paper.exit_pass(paper.Pass(venue, data, now, dry_run=dry_run))


def _rows(data: Path) -> list[dict]:
    path = night.ledger_path(data)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize(("equity", "cash", "close", "expected"), [
    ("100000", "100000", "100.00", 500),    # half the equity binds
    ("100000", "95777", "100.00", 478),     # the other card's positions leave less cash
    ("100000", "100000", "333.00", 150),    # rounded down, never up
    ("100000", "100000", "0", 0),
    ("100000", "0", "100.00", 0),
])
def test_size_is_half_the_equity_capped_at_the_fund_s_share_of_cash(
    paper, equity, cash, close, expected
) -> None:
    assert paper.size(Decimal(equity), Decimal(cash), Decimal(50), Decimal(close), 2) == expected


@pytest.mark.parametrize(("now", "answer"), [
    (AT_CLOSE_PASS, MONDAY),
    (datetime(2026, 9, 28, 19, 20, tzinfo=UTC), "too early"),
    (datetime(2026, 9, 28, 19, 49, tzinfo=UTC), "too late"),
    (datetime(2026, 9, 26, 19, 40, tzinfo=UTC), "not a"),
    # 2026-11-27 closes at 13:00 ET (18:00 UTC): the window moves with the calendar's close.
    (datetime(2026, 11, 27, 17, 40, tzinfo=UTC), date(2026, 11, 27)),
    (datetime(2026, 11, 27, 20, 40, tzinfo=UTC), "too late"),
])
def test_the_close_window_hangs_off_the_calendar_s_close(paper, now, answer) -> None:
    from swingdesk.contracts.reference import Exchange

    found = paper.close_window(Exchange("NYSE"), now)
    if isinstance(answer, date):
        assert found.session_date == answer
    else:
        assert isinstance(found, str) and answer in found


@pytest.mark.parametrize(("now", "answer"), [
    (AT_EXIT_PASS, MONDAY),
    (datetime(2026, 9, 29, 12, 15, tzinfo=UTC), MONDAY),     # Tuesday 08:15 ET
    (datetime(2026, 9, 28, 12, 15, tzinfo=UTC), FRIDAY),     # Monday 08:15 ET sells Friday's
    (datetime(2026, 9, 28, 16, 0, tzinfo=UTC), "outside"),   # noon ET: the venue refuses opg
])
def test_the_exit_pass_sells_the_right_night(paper, now, answer) -> None:
    from swingdesk.contracts.reference import Exchange

    found = paper.exit_night(Exchange("NYSE"), now)
    if isinstance(answer, date):
        assert found == answer
    else:
        assert isinstance(found, str) and answer in found


def test_the_close_pass_buys_both_funds_and_writes_each_before_sending(paper, tmp_path) -> None:
    venue = _Venue()
    assert _close(paper, venue, tmp_path) == paper.OK
    assert [(o.symbol, o.side, o.shares) for o in venue.sent] == [
        ("IJR", Side.BUY, 500), ("VB", Side.BUY, 250)]
    assert venue.sent[0].client_order_id == "swingdesk-night-2026-09-28-IJR-buy"
    kinds = [(row["kind"], row["client_order_id"][-7:]) for row in _rows(tmp_path)]
    assert kinds == [("sent", "IJR-buy"), ("answered", "IJR-buy"),
                     ("sent", "-VB-buy"), ("answered", "-VB-buy")]


def test_a_second_close_pass_sends_nothing_twice(paper, tmp_path) -> None:
    venue = _Venue()
    _close(paper, venue, tmp_path)
    assert _close(paper, venue, tmp_path) == paper.OK
    assert len(venue.sent) == 2


def test_the_close_pass_refuses_outside_its_window_and_touches_nothing(paper, tmp_path) -> None:
    venue = _Venue()
    late = datetime(2026, 9, 28, 20, 5, tzinfo=UTC)
    assert _close(paper, venue, tmp_path, now=late) == paper.REFUSED
    assert venue.sent == [] and not night.ledger_path(tmp_path).exists()


def test_a_stale_close_refuses_that_fund_and_not_the_other(paper, tmp_path) -> None:
    venue = _Venue()
    assert _close(paper, venue, tmp_path, closes=_closes(stale=("VB",))) == paper.REFUSED
    assert [o.symbol for o in venue.sent] == ["IJR"]


def test_a_stopped_switch_refuses_the_close_pass_and_writes_nothing(paper, tmp_path) -> None:
    venue = _Venue(armed=False)
    assert _close(paper, venue, tmp_path) == paper.REFUSED
    assert venue.sent == [] and not night.ledger_path(tmp_path).exists()


def test_a_dry_run_sends_nothing_and_writes_nothing(paper, tmp_path) -> None:
    venue = _Venue()
    assert _close(paper, venue, tmp_path, dry_run=True) == paper.OK
    assert venue.sent == [] and not night.ledger_path(tmp_path).exists()


def test_the_exit_pass_sells_exactly_what_filled(paper, tmp_path) -> None:
    venue = _Venue()
    _close(paper, venue, tmp_path)
    venue.fill("swingdesk-night-2026-09-28-IJR-buy", 500, "100.10")
    venue.end("swingdesk-night-2026-09-28-VB-buy", "canceled")
    assert _exit(paper, venue, tmp_path) == paper.OK
    sells = [o for o in venue.sent if o.side is Side.SELL]
    assert [(o.symbol, o.shares, o.client_order_id) for o in sells] == [
        ("IJR", 500, "swingdesk-night-2026-09-28-IJR-sell-1")]


def test_a_second_exit_pass_does_not_sell_twice(paper, tmp_path) -> None:
    venue = _Venue()
    _close(paper, venue, tmp_path)
    venue.fill("swingdesk-night-2026-09-28-IJR-buy", 500, "100.10")
    venue.end("swingdesk-night-2026-09-28-VB-buy", "canceled")
    _exit(paper, venue, tmp_path)
    assert _exit(paper, venue, tmp_path) == paper.OK
    assert sum(1 for o in venue.sent if o.side is Side.SELL) == 1


def test_a_refused_sell_is_sent_again_under_a_new_id(paper, tmp_path) -> None:
    """The sell is the night's only protection, and the venue rejects a repeated id."""
    venue = _Venue()
    _close(paper, venue, tmp_path)
    venue.fill("swingdesk-night-2026-09-28-IJR-buy", 500, "100.10")
    venue.end("swingdesk-night-2026-09-28-VB-buy", "canceled")
    _exit(paper, venue, tmp_path)
    venue.end("swingdesk-night-2026-09-28-IJR-sell-1", "rejected")
    assert _exit(paper, venue, tmp_path) == paper.OK
    assert venue.sent[-1].client_order_id == "swingdesk-night-2026-09-28-IJR-sell-2"
    assert venue.sent[-1].shares == 500


def test_a_filled_buy_left_without_its_exit_is_an_alert(paper, tmp_path) -> None:
    venue = _Venue()
    _close(paper, venue, tmp_path)
    venue.fill("swingdesk-night-2026-09-28-IJR-buy", 500, "100.10")
    venue.fill("swingdesk-night-2026-09-28-VB-buy", 250, "200.20")
    venue.armed = False
    assert _exit(paper, venue, tmp_path) == paper.ALERT
    assert not any(o.side is Side.SELL for o in venue.sent)


def test_the_next_close_pass_prices_last_night_and_buys_again(paper, tmp_path) -> None:
    venue = _Venue()
    _close(paper, venue, tmp_path)
    venue.fill("swingdesk-night-2026-09-28-IJR-buy", 500, "100.10")
    venue.end("swingdesk-night-2026-09-28-VB-buy", "canceled")
    _exit(paper, venue, tmp_path)
    venue.fill("swingdesk-night-2026-09-28-IJR-sell-1", 500, "100.50")
    assert _close(paper, venue, tmp_path, now=TUESDAY_CLOSE_PASS) == paper.OK
    nights = {row["fund"]: row for row in _rows(tmp_path) if row["kind"] == "night"}
    assert nights["IJR"]["pnl"] == "200.00" and nights["IJR"]["shares"] == 500
    assert nights["VB"]["shares"] == 0
    assert [o.client_order_id[-18:] for o in venue.sent[-2:]] == [
        "2026-09-29-IJR-buy", "-2026-09-29-VB-buy"]


def test_a_night_still_held_refuses_both_funds_tonight(paper, tmp_path) -> None:
    """Buying on top of an exit that did not fill doubles a position nobody decided."""
    venue = _Venue()
    _close(paper, venue, tmp_path)
    venue.fill("swingdesk-night-2026-09-28-IJR-buy", 500, "100.10")
    venue.end("swingdesk-night-2026-09-28-VB-buy", "canceled")
    _exit(paper, venue, tmp_path)
    before = len(venue.sent)
    assert _close(paper, venue, tmp_path, now=TUESDAY_CLOSE_PASS) == paper.ALERT
    assert len(venue.sent) == before


def test_a_send_that_raised_is_healed_from_the_venue_not_guessed(paper, tmp_path) -> None:
    """The request landed and the answer did not: the next pass asks the venue by our id."""
    venue = _Venue()
    venue.raise_after_landing = BrokerUnavailable("orders: read timed out")
    assert _close(paper, venue, tmp_path) == paper.ALERT
    ledger = night.read(tmp_path)
    assert [row.client_order_id for row in ledger.unanswered()] == [
        "swingdesk-night-2026-09-28-IJR-buy"]

    venue.fill("swingdesk-night-2026-09-28-IJR-buy", 500, "100.10")
    venue.fill("swingdesk-night-2026-09-28-VB-buy", 250, "200.20")
    assert _exit(paper, venue, tmp_path) == paper.OK
    assert night.read(tmp_path).unanswered() == ()
    assert sorted(o.symbol for o in venue.sent if o.side is Side.SELL) == ["IJR", "VB"]


def test_the_report_counts_priced_nights(paper, tmp_path, capsys) -> None:
    venue = _Venue()
    _close(paper, venue, tmp_path)
    venue.fill("swingdesk-night-2026-09-28-IJR-buy", 500, "100.10")
    venue.end("swingdesk-night-2026-09-28-VB-buy", "canceled")
    _exit(paper, venue, tmp_path)
    venue.fill("swingdesk-night-2026-09-28-IJR-sell-1", 500, "100.50")
    _close(paper, venue, tmp_path, now=TUESDAY_CLOSE_PASS)
    capsys.readouterr()
    assert paper.report(tmp_path) == paper.OK
    printed = capsys.readouterr().out
    assert "1 fund-night(s) priced" in printed and "+200.00" in printed


def test_the_scheduled_wrapper_fetches_the_three_funds_before_the_passes_that_price() -> None:
    """Runbook 11.1's precondition, made a mechanism: the close pass sizes from the prior close,
    and on 2026-09-20 the store held VB a session behind. The exit pass values the night and sizes
    the day leg from THIS session's closes, which the evening run has not fetched by 19:10 ET
    (`DR-056` §2). The morning pass reads no bar at all."""
    lines = (REPO / "tools" / "card002_paper.cmd").read_text(encoding="ascii").splitlines()
    fetches = [(i, line) for i, line in enumerate(lines) if "fetch_history.py" in line]
    passes = next(i for i, line in enumerate(lines) if "card002_paper.py" in line
                  and not line.startswith("REM"))
    modes = {re.match(r'if "%MODE%"=="(\w+)"', line).group(1) for _, line in fetches}  # type: ignore[union-attr]
    assert modes == {"close", "exit"}, "the morning pass fetches nothing"
    assert all(i < passes and "IJR VB SPY" in line for i, line in fetches)


# --- DR-056: the day leg - SPY from the opening auction to the closing one ----------------------

TUESDAY_MORNING = datetime(2026, 9, 29, 13, 45, tzinfo=UTC)   # 09:45 ET
TUESDAY = date(2026, 9, 29)


def test_the_committed_policy_carries_the_day_leg_at_the_reversed_auctions() -> None:
    night_policy = policy_module.load().write.night
    assert night_policy.day_symbols == frozenset({"SPY"})
    assert (night_policy.day_entry_time_in_force, night_policy.day_exit_time_in_force) == \
        ("opg", "cls")


def test_a_symbol_in_both_legs_refuses_to_load(tmp_path: Path) -> None:
    """Which auction buys it would be a guess - and it decides whether it is held open or shut."""
    with pytest.raises(PolicyRefused, match="both"):
        _policy_with(tmp_path, day_symbols=["IJR"])


def test_half_a_day_block_refuses_to_load(tmp_path: Path) -> None:
    with pytest.raises(PolicyRefused, match="day leg is one shape"):
        _policy_with(tmp_path, day_exit_time_in_force=None)


def test_the_day_leg_buys_at_the_open_and_sells_at_the_close() -> None:
    buy = _night_order(symbol="SPY", client_order_id="swingdesk-night-2026-09-29-SPY-buy")
    client = _client(payload={**PLACED, "client_order_id": buy.client_order_id, "symbol": "SPY"})
    client.submit_night(buy, AT_EXIT_PASS)
    sell = _night_order(symbol="SPY", side=Side.SELL,
                        client_order_id="swingdesk-night-2026-09-29-SPY-sell-1")
    client_sell = _client(payload={**PLACED, "client_order_id": sell.client_order_id,
                                   "symbol": "SPY", "side": "sell"})
    client_sell.submit_night(sell, TUESDAY_MORNING)
    [bought] = client.transport.sent  # type: ignore[attr-defined]
    [sold] = client_sell.transport.sent  # type: ignore[attr-defined]
    assert (bought["body"]["side"], bought["body"]["time_in_force"]) == ("buy", "opg")
    assert (sold["body"]["side"], sold["body"]["time_in_force"]) == ("sell", "cls")


@pytest.mark.parametrize(("equity", "cash", "freed", "close", "expected"), [
    ("100000", "0", "99000", "400", 247),     # the night's sale funds it
    ("100000", "95000", "99000", "400", 250),  # never more than the equity
    ("100000", "0", "0", "400", 0),            # nothing freed, nothing bought
    ("100000", "0", "99000", "0", 0),
])
def test_the_day_leg_is_what_the_night_frees_and_never_above_equity(
    paper, equity, cash, freed, close, expected
) -> None:
    assert paper.day_size(Decimal(equity), Decimal(cash), Decimal(freed), Decimal(close)) == expected


def _exit_with_day(paper, venue, data, now=AT_EXIT_PASS, closes=None):
    return paper.exit_pass(paper.Pass(venue, data, now), closes or _closes())


def _night_filled(paper, venue, data) -> None:
    _close(paper, venue, data)
    venue.fill("swingdesk-night-2026-09-28-IJR-buy", 500, "100.10")
    venue.fill("swingdesk-night-2026-09-28-VB-buy", 250, "200.20")
    venue.cash = Decimal("0")


def test_the_exit_pass_buys_the_day_leg_with_what_the_night_frees(paper, tmp_path) -> None:
    venue = _Venue()
    _night_filled(paper, venue, tmp_path)
    assert _exit_with_day(paper, venue, tmp_path) == paper.OK
    [spy] = [o for o in venue.sent if o.symbol == "SPY"]
    # 500 x 100 + 250 x 200 = 100,000 freed; at a 400 close, 250 shares.
    assert (spy.side, spy.shares, spy.session_date) == (Side.BUY, 250, TUESDAY)
    assert spy.client_order_id == "swingdesk-night-2026-09-29-SPY-buy"
    assert [o.symbol for o in venue.sent[-3:]] == ["IJR", "VB", "SPY"], \
        "the night legs are protected before the day leg is bought"


def test_no_day_leg_while_a_night_leg_is_unprotected(paper, tmp_path) -> None:
    venue = _Venue()
    _night_filled(paper, venue, tmp_path)
    venue.raise_after_landing = BrokerUnavailable("orders: read timed out")
    assert _exit_with_day(paper, venue, tmp_path) == paper.ALERT
    assert not [o for o in venue.sent if o.symbol == "SPY"]


def test_the_day_leg_is_bought_once(paper, tmp_path) -> None:
    venue = _Venue()
    _night_filled(paper, venue, tmp_path)
    _exit_with_day(paper, venue, tmp_path)
    assert _exit_with_day(paper, venue, tmp_path) == paper.OK, \
        "the ledger, not the venue's duplicate-id refusal, is what stops a second buy"
    assert len([o for o in venue.sent if o.symbol == "SPY"]) == 1
    sent_rows = [r for r in _rows(tmp_path) if r["kind"] == "sent" and r["fund"] == "SPY"]
    assert len(sent_rows) == 1


@pytest.mark.parametrize(("now", "answer"), [
    (TUESDAY_MORNING, TUESDAY),
    (datetime(2026, 9, 29, 13, 35, tzinfo=UTC), "too early"),    # 09:35 ET
    (datetime(2026, 9, 29, 19, 49, tzinfo=UTC), "too late"),     # 15:49 ET
    (datetime(2026, 10, 3, 14, 0, tzinfo=UTC), "not a"),         # a Saturday
])
def test_the_morning_window(paper, now, answer) -> None:
    from swingdesk.contracts.reference import Exchange

    found = paper.morning_window(Exchange("NYSE"), now)
    if isinstance(answer, date):
        assert found.session_date == answer
    else:
        assert isinstance(found, str) and answer in found


def _day_bought(paper, venue, data) -> None:
    _night_filled(paper, venue, data)
    _exit_with_day(paper, venue, data)
    venue.fill("swingdesk-night-2026-09-29-SPY-buy", 250, "401.00")


def test_the_morning_pass_lodges_a_closing_sell_for_exactly_what_filled(paper, tmp_path) -> None:
    venue = _Venue()
    _day_bought(paper, venue, tmp_path)
    assert paper.morning_pass(paper.Pass(venue, tmp_path, TUESDAY_MORNING)) == paper.OK
    last = venue.sent[-1]
    assert (last.symbol, last.side, last.shares) == ("SPY", Side.SELL, 250)
    assert last.client_order_id == "swingdesk-night-2026-09-29-SPY-sell-1"


def test_a_filled_day_leg_the_switch_will_not_protect_is_an_alert(paper, tmp_path) -> None:
    venue = _Venue()
    _day_bought(paper, venue, tmp_path)
    venue.armed = False
    assert paper.morning_pass(paper.Pass(venue, tmp_path, TUESDAY_MORNING)) == paper.ALERT


def test_the_close_pass_lodges_a_missing_day_sell_and_sizes_the_night_with_what_it_frees(
    paper, tmp_path
) -> None:
    """The morning pass never ran: the close pass must lodge the day leg's sell BEFORE buying the
    night, and count the SPY it sells as the money the night is bought with."""
    venue = _Venue()
    _day_bought(paper, venue, tmp_path)
    venue.fill("swingdesk-night-2026-09-28-IJR-sell-1", 500, "100.50")
    venue.fill("swingdesk-night-2026-09-28-VB-sell-1", 250, "200.40")
    assert _close(paper, venue, tmp_path, now=TUESDAY_CLOSE_PASS) == paper.OK
    tuesday = [o for o in venue.sent if o.session_date == TUESDAY]
    assert [(o.symbol, o.side) for o in tuesday] == [
        ("SPY", Side.BUY), ("SPY", Side.SELL), ("IJR", Side.BUY), ("VB", Side.BUY)]
    ijr = next(o for o in tuesday if o.symbol == "IJR" and o.side is Side.BUY)
    # cash 0 + 250 SPY x 400 = 100,000 freed; half each, at 100: 500 shares.
    assert ijr.shares == 500


def test_the_day_leg_is_priced_at_the_next_close_pass(paper, tmp_path) -> None:
    venue = _Venue()
    _day_bought(paper, venue, tmp_path)
    paper.morning_pass(paper.Pass(venue, tmp_path, TUESDAY_MORNING))
    venue.fill("swingdesk-night-2026-09-28-IJR-sell-1", 500, "100.50")
    venue.fill("swingdesk-night-2026-09-28-VB-sell-1", 250, "200.40")
    _close(paper, venue, tmp_path, now=TUESDAY_CLOSE_PASS)
    venue.fill("swingdesk-night-2026-09-29-SPY-sell-1", 250, "403.00")
    venue.fill("swingdesk-night-2026-09-29-IJR-buy", 500, "100.00")
    venue.fill("swingdesk-night-2026-09-29-VB-buy", 250, "200.00")
    paper.exit_pass(paper.Pass(venue, tmp_path, datetime(2026, 9, 29, 23, 10, tzinfo=UTC)),
                    _closes())
    venue.fill("swingdesk-night-2026-09-29-IJR-sell-1", 500, "100.20")
    venue.fill("swingdesk-night-2026-09-29-VB-sell-1", 250, "200.30")
    _close(paper, venue, tmp_path, now=datetime(2026, 9, 30, 19, 40, tzinfo=UTC))
    legs = {(row["session"], row["fund"]): row for row in _rows(tmp_path) if row["kind"] == "night"}
    assert legs[("2026-09-29", "SPY")]["pnl"] == "500.00"   # 250 x (403 - 401)


# --- DR-055 proof (2): what counts as a session of the whole book ---------------------------------


def _priced(session: str, fund: str, shares: int = 100) -> dict:
    return {"kind": "night", "session": session, "fund": fund, "shares": shares, "pnl": "1.00"}


def test_a_whole_book_session_is_the_night_into_it_and_its_own_day_leg(paper) -> None:
    """Tuesday counts: IJR and VB bought at Monday's close and sold at Tuesday's open, SPY held
    through Tuesday. Monday does not - nothing was held the night before it."""
    rows = [_priced("2026-09-28", "IJR"), _priced("2026-09-28", "VB"),
            _priced("2026-09-29", "SPY"), _priced("2026-09-28", "SPY")]
    assert paper.book_sessions(rows, paper.Exchange.NYSE) == [TUESDAY]


def test_a_session_missing_any_leg_does_not_count(paper) -> None:
    whole = [_priced("2026-09-28", "IJR"), _priced("2026-09-28", "VB"), _priced("2026-09-29", "SPY")]
    for missing in range(3):
        rows = whole[:missing] + whole[missing + 1:]
        assert paper.book_sessions(rows, paper.Exchange.NYSE) == []
    unfilled = [*whole[:2], {**whole[2], "shares": 0}]
    assert paper.book_sessions(unfilled, paper.Exchange.NYSE) == [], "a day leg that never filled"


def test_the_night_before_a_monday_is_fridays(paper) -> None:
    rows = [_priced("2026-09-25", "IJR"), _priced("2026-09-25", "VB"), _priced("2026-09-28", "SPY")]
    assert paper.book_sessions(rows, paper.Exchange.NYSE) == [MONDAY]
