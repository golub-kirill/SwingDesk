"""The drawdown `k.drawdown_pause` triggers on (`criteria.yml` amendment v1.1.2).

The criterion has been ratified with scope `live` since v1.0.0 and nothing computed its input, so
these are the first tests that can say what the number means. The cases that matter are the ones
where the answer is NOT zero - today's store holds no positions, and a measurement that is only ever
exercised at zero is a measurement nobody has checked.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from swingdesk.contracts.position import ActionKind, Fill, ManagementAction, Position
from swingdesk.trade_management import drawdown

BASELINE = Decimal(10_000)
KNOWN = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)


def _position(
    position_id: str = "p1",
    *,
    shares: int = 100,
    entry: str = "50.00",
    opened: date = date(2026, 1, 5),
    closed: date | None = None,
    costs: str = "0.00",
) -> Position:
    return Position(
        position_id=position_id, version=1, instrument_id="TEST.US",
        opened_on=opened, entry_price=Decimal(entry), shares=shares,
        initial_stop=Decimal("40.00"), current_stop=Decimal("40.00"),
        initial_costs_per_share=Decimal(costs), strategy="test", strategy_version=1,
        knowledge_time=KNOWN, closed_on=closed,
    )


def _marks(prices: dict[date, str]) -> drawdown.MarkFor:
    def mark_for(_instrument_id: str, session: date) -> Decimal | None:
        value = prices.get(session)
        return Decimal(value) if value is not None else None

    return mark_for


# ------------------------------------------------------------------ the case that runs today

def test_no_positions_reports_zero_rather_than_refusing() -> None:
    """The point of building this: the criterion stops being unevaluable.

    An empty book is not a missing measurement. Before this existed `k.drawdown_pause` could not
    fire at all, which is the inert-gate failure `REQ-VALIDATION-001` names - and "no answer" and
    "0.00%" are very different things to show an owner beside a ratified kill switch.
    """
    result = drawdown.measure(
        positions=[], fills_by_position={}, actions_by_position={},
        baseline=BASELINE, sessions=[], mark_for=_marks({}),
    )
    assert isinstance(result, drawdown.Drawdown)
    assert result.percent == Decimal("0.00")
    assert not result.breaches(Decimal(20))


# ------------------------------------------------------------------ open positions are marked

def test_an_open_position_that_has_fallen_counts_before_anything_is_realised() -> None:
    """The whole reason the owner ruled against the closed-trades reading.

    100 shares bought at 50.00 - 5,000 of a 10,000 account - falling to 30.00 is an unrealised loss
    of 2,000, a 20% drawdown, with nothing sold. Under "realised means closed trades only" this
    account reports 0.00% and the kill switch never fires, which inverts M69.
    """
    sessions = [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)]
    result = drawdown.measure(
        positions=[_position()], fills_by_position={}, actions_by_position={},
        baseline=BASELINE, sessions=sessions,
        mark_for=_marks({
            sessions[0]: "50.00",   # equity 10,000
            sessions[1]: "40.00",   # equity  9,000
            sessions[2]: "30.00",   # equity  8,000
        }),
    )
    assert isinstance(result, drawdown.Drawdown)
    assert result.peak == Decimal(10_000)
    assert result.trough == Decimal(8_000)
    assert result.percent == Decimal("20.00")
    assert result.breaches(Decimal("19.99"))
    assert not result.breaches(Decimal("20.00")), "the trigger is `exceeds`, not `reaches`"


def test_the_drawdown_is_peak_to_trough_not_first_to_last() -> None:
    """`GLOSSARY.md` defines drawdown as a decline from the PREVIOUS PEAK.

    An account that climbed to 12,000, fell to 9,000 and recovered to 12,000 has been through a 25%
    drawdown. First-to-last would report 0% and peak-to-final would too - both would tell the owner
    nothing happened on the day their equity fell by a quarter.
    """
    sessions = [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7), date(2026, 1, 8)]
    result = drawdown.measure(
        positions=[_position()], fills_by_position={}, actions_by_position={},
        baseline=BASELINE, sessions=sessions,
        mark_for=_marks({
            sessions[0]: "50.00",   # equity 10,000
            sessions[1]: "70.00",   # equity 12,000  <- peak
            sessions[2]: "40.00",   # equity  9,000  <- trough
            sessions[3]: "70.00",   # equity 12,000  recovered
        }),
    )
    assert isinstance(result, drawdown.Drawdown)
    assert result.peak == Decimal(12_000)
    assert result.trough == Decimal(9_000)
    assert result.percent == Decimal("25.00")


# ------------------------------------------------------------------ realised P&L

def test_a_closed_loss_stays_in_the_curve_after_the_position_is_gone() -> None:
    """Realised losses do not stop counting when the position closes.

    Sold 100 at 30.00 against a 50.00 entry: 2,000 gone, and the account is at 8,000 from then on.
    A curve that dropped the position and its loss together would show the account recovering to
    its baseline the moment the owner took the loss.
    """
    sessions = [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)]
    position = _position(closed=date(2026, 1, 6))
    exit_fill = Fill(
        position_id="p1", sequence=1, filled_on=date(2026, 1, 6), shares=100,
        price=Decimal("30.00"), commission=Decimal(0), recorded_at=KNOWN,
    )
    result = drawdown.measure(
        positions=[position],
        fills_by_position={"p1": [exit_fill]},
        actions_by_position={"p1": {1: str(ActionKind.EXIT_NOW)}},
        baseline=BASELINE, sessions=sessions,
        mark_for=_marks({sessions[0]: "50.00"}),
    )
    assert isinstance(result, drawdown.Drawdown)
    assert [point.equity for point in result.curve] == [
        Decimal(10_000), Decimal(8_000), Decimal(8_000)
    ]
    assert result.percent == Decimal("20.00")


def test_a_fill_against_a_stop_move_realises_nothing() -> None:
    """A fill settles an approved ACTION, and a `move_stop` transacts no shares.

    Counting every fill as realising would book a P&L for an action that moved a price and not a
    share - and it would do it in whichever direction the mark happened to sit.
    """
    sessions = [date(2026, 1, 5)]
    stop_move = Fill(
        position_id="p1", sequence=1, filled_on=date(2026, 1, 5), shares=100,
        price=Decimal("30.00"), commission=Decimal(0), recorded_at=KNOWN,
    )
    result = drawdown.measure(
        positions=[_position()],
        fills_by_position={"p1": [stop_move]},
        actions_by_position={"p1": {1: str(ActionKind.MOVE_STOP)}},
        baseline=BASELINE, sessions=sessions,
        mark_for=_marks({sessions[0]: "50.00"}),
    )
    assert isinstance(result, drawdown.Drawdown)
    assert result.percent == Decimal("0.00"), "nothing was sold, so nothing was realised"


def test_costs_are_taken_out_of_both_halves() -> None:
    """`initial_costs_per_share` is what entry cost, and it is a real reduction in equity.

    `criteria.yml`'s own rules say all measurements are net of costs. A drawdown computed gross
    understates how far the account actually fell.
    """
    sessions = [date(2026, 1, 5)]
    result = drawdown.measure(
        positions=[_position(costs="0.10")], fills_by_position={}, actions_by_position={},
        baseline=BASELINE, sessions=sessions,
        mark_for=_marks({sessions[0]: "50.00"}),
    )
    assert isinstance(result, drawdown.Drawdown)
    # Flat price, but 100 shares cost 0.10 each to get into: equity is 9,990, not 10,000.
    assert result.curve[0].equity == Decimal("9990.00")


# ------------------------------------------------------------------ fail-closed

def test_an_unpriceable_position_is_unavailable_and_never_zero() -> None:
    """The one direction a kill switch must not be wrong in.

    Treating a missing mark as no unrealised loss makes the drawdown look SMALLER than it is, so a
    breach could pass silently. `AGENTS.md` §12: unavailable is not fail and it is not pass.
    """
    sessions = [date(2026, 1, 5), date(2026, 1, 6)]
    result = drawdown.measure(
        positions=[_position()], fills_by_position={}, actions_by_position={},
        baseline=BASELINE, sessions=sessions,
        mark_for=_marks({sessions[0]: "50.00"}),  # nothing for 01-06
    )
    assert isinstance(result, drawdown.Unavailable)
    assert result.unpriced == (("p1", date(2026, 1, 6)),)
    assert "smaller than the real one" in result.reason


def test_a_wiped_out_peak_refuses_rather_than_dividing() -> None:
    """A peak of zero has no percentage, and swallowing that would report a number for nothing."""
    points = [drawdown.EquityPoint(date(2026, 1, 5), Decimal(0), Decimal(0), Decimal(0))]
    result = drawdown.peak_to_trough(points)
    assert isinstance(result, drawdown.Unavailable)
    assert "no equity to draw down from" in result.reason


def test_the_measurement_prescribes_nothing() -> None:
    """`breaches` answers the trigger and stops there.

    `k.drawdown_pause`'s action names the risk-off ladder; `risk.risk_off_ladder` is `unset` and
    writing it is the owner's. A module that returned an ACTION would be inventing that ladder.
    """
    assert not hasattr(drawdown, "act")
    assert not hasattr(drawdown.Drawdown, "action")
    names = set(drawdown.__all__)
    assert names == {
        "Drawdown", "EquityPoint", "MarkFor", "Unavailable", "curve", "measure", "peak_to_trough"
    }


def test_management_action_kinds_used_here_still_exist() -> None:
    """The realising set is matched by STRING, so a renamed enum member would silently stop matching
    and every exit would quietly realise nothing."""
    assert str(ActionKind.EXIT_NOW) == "exit_now"
    assert str(ActionKind.PARTIAL_EXIT) == "partial_exit"
    assert ManagementAction(
        position_id="p1", proposed_at=KNOWN, kind=ActionKind.EXIT_NOW, reason="test"
    ).kind is ActionKind.EXIT_NOW
