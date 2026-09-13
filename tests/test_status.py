"""`swingdesk status`, the pure half: every branch of the screen, with no venue and no scheduler.

Exit codes follow `broker`'s because a script reads both for the same answer: 0 in order, 2 the
venue could not be read (NOT agreement), 3 a TECH finding."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from swingdesk.broker.armed import Arming
from swingdesk.contracts.broker import BrokerPosition, PlacedOrder, PositionSide
from swingdesk.contracts.position import ActionKind, ManagementAction, Position
from swingdesk.journal_evidence.positions import Pending
from swingdesk.platform.schedule import TaskReading
from swingdesk.presentation import status
from swingdesk.presentation.pending_view import PendingSplit

AT = datetime(2026, 9, 12, 23, 0, tzinfo=UTC)
ARMED = Arming(armed=True, reason="the switch file is present")
DAILY = TaskReading("SwingDesk daily run", "Ready", "9/14/2026 6:30:00 PM",
                    "9/11/2026 6:30:00 PM", "clean", "exit 0")


def _book(stop: str = "117.044982") -> Position:
    return Position(
        position_id="POS-VGT-2026-09-09", version=1, instrument_id="VGT",
        opened_on=date(2026, 9, 9), entry_price=Decimal("119.658"), shares=20,
        initial_stop=Decimal(115), current_stop=Decimal(stop),
        initial_costs_per_share=Decimal("0.25"),
        knowledge_time=datetime(2026, 9, 9, 20, 0, tzinfo=UTC))


def _held() -> BrokerPosition:
    return BrokerPosition(symbol="VGT", asset_class="us_equity", exchange="ARCA",
                          side=PositionSide("long"), shares=Decimal(20),
                          average_entry_price=Decimal("119.658"), observed_at=AT)


def _stop(price: str) -> PlacedOrder:
    return PlacedOrder(order_id="leg-VGT", client_order_id="", symbol="VGT", status="new",
                       submitted_at=AT, order_type="stop", stop_price=Decimal(price),
                       observed_at=AT)


def _view(**overrides):
    fields = dict(at=AT, switch=ARMED, schedule=(DAILY,), account=None, venue_error=None,
                  book=[_book()], held=[_held()], live_orders=[_stop("117.05")],
                  split=PendingSplit(), market="NYSE", label="Alpaca paper trading",
                  tick_for=lambda _: Decimal("0.01"))
    fields.update(overrides)
    return status.build(**fields)


def test_a_stop_within_a_tick_is_in_order():
    view = _view()
    assert view.positions[0].protection == status.OK
    assert view.positions[0].venue_stop == Decimal("117.05")
    assert view.exit_code == 0


def test_a_stop_a_full_atr_away_is_the_wrong_price():
    view = _view(live_orders=[_stop("115.62")])
    assert view.positions[0].protection == status.WRONG_PRICE
    assert view.exit_code == 3


def test_no_stop_standing_is_tech():
    view = _view(live_orders=[])
    assert view.positions[0].protection == status.NO_STOP
    assert view.exit_code == 3


def test_a_venue_that_could_not_be_read_is_unavailable_not_agreement():
    view = _view(venue_error="the venue did not answer", held=[], live_orders=[])
    assert view.positions[0].protection == status.UNKNOWN
    assert view.exit_code == 2
    assert any("UNAVAILABLE" in line for line in status.render(view))


def test_a_book_the_venue_does_not_hold_is_a_divergence():
    view = _view(held=[])
    assert view.divergences
    assert view.exit_code == 3


def test_the_newest_proposal_is_shown_beside_its_position():
    older = Pending(sequence=4, action=ManagementAction(
        position_id="POS-VGT-2026-09-09", proposed_at=AT, kind=ActionKind.MOVE_STOP,
        reason="x", old_stop=Decimal(115), new_stop=Decimal("116.10")))
    newer = Pending(sequence=5, action=ManagementAction(
        position_id="POS-VGT-2026-09-09", proposed_at=AT, kind=ActionKind.MOVE_STOP,
        reason="x", old_stop=Decimal(115), new_stop=Decimal("117.05")))
    view = _view(split=PendingSplit(waiting=[newer, older]))
    assert view.positions[0].proposal == "#5 MOVE_STOP -> 117.05"
    assert view.waiting == 2


def test_the_screen_carries_every_section():
    lines = "\n".join(status.render(_view()))
    for needle in ("switch     ARMED", "SwingDesk daily run", "VGT", "venue 117.05",
                   "pending    0 awaiting", "verdict    OK"):
        assert needle in lines


def test_a_stopped_switch_is_said_as_stopped():
    lines = "\n".join(status.render(_view(switch=Arming(armed=False, reason="no switch file"))))
    assert "switch     STOPPED - no switch file" in lines


def test_no_registered_task_is_said_rather_than_left_blank():
    lines = "\n".join(status.render(_view(schedule=())))
    assert "no task registered on this machine" in lines
