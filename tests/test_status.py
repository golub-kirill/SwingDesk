"""`swingdesk status`, the pure half: every branch of the screen, with no venue and no scheduler.

Exit codes follow `broker`'s because a script reads both for the same answer: 0 in order, 2 the
venue could not be read (NOT agreement), 3 a TECH finding."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_UP, Decimal

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


def _stop(price: str, status: str = "new") -> PlacedOrder:
    return PlacedOrder(order_id="leg-VGT", client_order_id="", symbol="VGT", status=status,
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


def test_a_proposal_the_book_has_overtaken_is_marked_obsolete():
    """Found live 2026-09-13: BTSG's newest proposal asked for 55.76 under a 57.61 book stop."""
    stale = Pending(sequence=7, action=ManagementAction(
        position_id="POS-VGT-2026-09-09", proposed_at=AT, kind=ActionKind.MOVE_STOP,
        reason="x", old_stop=Decimal(115), new_stop=Decimal("116.10")))
    view = _view(split=PendingSplit(waiting=[stale]))
    assert view.positions[0].proposal == (
        "#7 MOVE_STOP -> 116.10 (obsolete - at or below the book stop)")


# ------------------------------------------------------- what to type at the venue, 2026-09-14


HANDOVER = status.Handover(
    orders_url="https://paper-api.alpaca.markets/v2/orders", key_env="APCA_API_KEY_ID",
    secret_env="APCA_API_SECRET_KEY",
    stop_at_tick=lambda p: (p / Decimal("0.01")).quantize(Decimal(1), rounding=ROUND_UP)
    * Decimal("0.01"))


def test_no_stop_prints_the_book_stop_rounded_up_for_the_books_shares():
    """The 2026-09-14 case: VGT's book stop 117.044982, nothing resting."""
    view = _view(live_orders=[], handover=HANDOVER)
    [command] = view.commands
    assert command.startswith("curl -s -X POST https://paper-api.alpaca.markets/v2/orders ")
    assert '\\"stop_price\\":\\"117.05\\"' in command
    assert '\\"qty\\":\\"20\\"' in command and '\\"side\\":\\"sell\\"' in command
    assert '\\"type\\":\\"stop\\"' in command and '\\"time_in_force\\":\\"gtc\\"' in command


def test_a_command_carries_the_names_of_the_keys_and_never_a_value():
    [command] = _view(live_orders=[], handover=HANDOVER).commands
    assert '-H "APCA-API-KEY-ID: %APCA_API_KEY_ID%"' in command
    assert '-H "APCA-API-SECRET-KEY: %APCA_API_SECRET_KEY%"' in command


def test_a_looser_venue_stop_is_cancelled_before_the_books_is_placed():
    """A move approved in the book and never sent: VGT's 115.62 under a 117.044982 book."""
    view = _view(live_orders=[_stop("115.62")], handover=HANDOVER)
    cancel, place = view.commands
    assert cancel.startswith("curl -s -X DELETE https://paper-api.alpaca.markets/v2/orders/leg-VGT ")
    assert '\\"stop_price\\":\\"117.05\\"' in place
    lines = "\n".join(status.render(view))
    assert lines.index("-X DELETE") < lines.index("-X POST")
    assert "before its stop is placed" in lines


def test_a_tighter_venue_stop_is_left_for_dr041_to_adopt():
    view = _view(live_orders=[_stop("118.00")], handover=HANDOVER)
    assert view.commands == ()
    [note] = view.venue_notes
    assert "tighter" in note and "DR-041" in note
    assert view.exit_code == 3, "still a finding until sync-fills adopts it"


def test_a_take_profit_is_named_as_holding_the_shares_and_never_cancelled():
    """A resting sell limit reserves the shares, so the stop would be refused - said, not decided."""
    target = PlacedOrder(order_id="tp-VGT", client_order_id="", symbol="VGT", status="new",
                         submitted_at=AT, order_type="limit", stop_price=None, side="sell",
                         observed_at=AT)
    view = _view(live_orders=[_stop("115.62"), target], handover=HANDOVER)
    assert not any("tp-VGT" in command for command in view.commands)
    assert [c for c in view.commands if "-X DELETE" in c] == [view.commands[0]]
    [note] = view.venue_notes
    assert "tp-VGT" in note and "insufficient qty" in note


def test_a_stop_being_withdrawn_gets_a_note_and_no_command():
    """`DR-044`, measured 2026-09-15: three cancels sent after the close were queued, and the
    shares stay held until they land - so a place command printed now is refused."""
    view = _view(live_orders=[_stop("117.05", status="pending_cancel")], handover=HANDOVER)

    assert view.commands == (), "the venue would refuse it for insufficient qty"
    [note] = view.venue_notes
    assert "withdrawn" in note and "insufficient qty" in note and "DR-044" in note
    assert "117.05" in note and "20 shares" in note
    assert view.exit_code == 3, "the position reads unprotected, and it is"


def test_a_position_in_order_prints_nothing_to_type():
    view = _view(handover=HANDOVER)
    assert view.commands == () and view.venue_notes == ()
    assert "at the venue" not in "\n".join(status.render(view))


def test_nothing_is_printed_without_a_handover_or_with_an_unread_venue():
    assert _view(live_orders=[]).commands == ()
    unread = _view(venue_error="down", held=[], live_orders=[], handover=HANDOVER)
    assert unread.commands == ()
