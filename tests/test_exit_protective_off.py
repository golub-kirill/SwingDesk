"""The protective slot switched OFF — `PR-018`'s null arm, and the one policy that must never ship.

A position with no standing stop is what `DR-036`, `DR-037` and every cap in `risk.*` exist to
prevent. This policy expresses exactly that, deliberately, for one purpose: `PR-018` asks whether
the ratified exit earns its keep against holding to the clock, and the comparison needs a null in
the SAME units.

Three things carry it and none raises when wrong:

* **the stop is still COMPUTED.** R is `entry − stop` (`RISK_SPEC` 2) and every figure this project
  reports is denominated in it. A null arm priced in different units is not a comparison — it is
  two numbers that cannot be subtracted.
* **nothing else may stop the position out.** The check comes first, so no later branch can.
* **it can never be the live path's policy.** `application/pipeline.py` builds from registry values
  and there is no registry value for this. A test asserts the constructed policy is protective.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from swingdesk.contracts.market import Bar, Interval, Series
from swingdesk.contracts.trade import ExitReason
from swingdesk.trade_management.exits import ExitPolicy

KNOWN = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
ENTRY, RISK, STOP, ONE_R = Decimal(100), Decimal(10), Decimal(90), Decimal(110)

HOLD_ONLY = ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20, protective=False)
RATIFIED = ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20,
                      target_r_multiple=Decimal(1))


def bar(open_: str, high: str, low: str, close: str) -> Bar:
    return Bar(
        instrument_id="TEST.1", interval=Interval.DAY, series=Series.RAW,
        event_time=datetime(2026, 1, 15, tzinfo=UTC), session_date=date(2026, 1, 15),
        open=Decimal(open_), high=Decimal(high), low=Decimal(low), close=Decimal(close),
        volume=1_000_000, knowledge_time=KNOWN,
    )


# --- the stop is computed and never acted on -----------------------------------------------------

def test_the_stop_is_still_computed_because_R_is_denominated_in_it() -> None:
    """The null arm must be priced in the SAME R as the arm it is compared against, or the
    difference is two numbers that cannot be subtracted."""
    assert HOLD_ONLY.stop_for(ENTRY, Decimal(5)) == STOP
    assert HOLD_ONLY.stop_for(ENTRY, Decimal(5)) == RATIFIED.stop_for(ENTRY, Decimal(5))


def test_a_bar_deep_below_the_stop_does_not_exit() -> None:
    decision = HOLD_ONLY.evaluate(bar("50", "55", "40", "45"), STOP, 5)
    assert not decision.exited


def test_a_bar_that_OPENS_below_the_stop_does_not_exit_either() -> None:
    """The gap branch is the one that fires first in the protective policy, so it is the one most
    likely to survive a switch that only guarded the intraday check."""
    decision = HOLD_ONLY.evaluate(bar("50", "51", "49", "50"), STOP, 5)
    assert not decision.exited


def test_the_same_bar_DOES_exit_under_the_ratified_policy() -> None:
    """The control on the two tests above: the fixture really would stop out, so their passing is
    the switch working rather than the fixture being harmless."""
    assert RATIFIED.evaluate(bar("50", "55", "40", "45"), STOP, 5).exited
    assert RATIFIED.evaluate(bar("50", "51", "49", "50"), STOP, 5).reason is ExitReason.STOP_GAP


def test_the_clock_still_ends_it_at_the_close() -> None:
    decision = HOLD_ONLY.evaluate(bar("50", "55", "40", "45"), STOP, 20)
    assert decision.exited
    assert decision.reason is ExitReason.TIME
    assert decision.price == Decimal(45)


def test_the_position_survives_a_ruinous_bar_before_its_time() -> None:
    """−9R on one session and the position is still open. That is the whole point of the arm and
    the whole reason `PR-018` must read the MAE distribution and not only the mean."""
    assert not HOLD_ONLY.evaluate(bar("100", "100", "10", "10"), STOP, 3).exited


# --- what it refuses -----------------------------------------------------------------------------

def test_no_stop_with_a_take_profit_is_refused() -> None:
    """Neither the null arm nor a strategy anyone registered. The null holds to the clock."""
    with pytest.raises(ValueError, match="neither the null arm nor a strategy"):
        ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20,
                   target_r_multiple=Decimal(1), protective=False)


def test_a_partial_still_fires_without_a_protective_stop() -> None:
    """A partial is the PROFIT slot and is not what was switched off. Silently dropping it would
    make a diagnostic arm run a policy its own record does not describe."""
    policy = ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20, protective=False,
                        partial_trigger=Decimal(1), partial_fraction=Decimal("0.5"))
    decision = policy.evaluate(bar("100", "111", "40", "108"), STOP, 5, None, ONE_R)
    assert decision.partial
    assert not decision.exited


# --- it must never ship --------------------------------------------------------------------------

def test_the_default_is_protective() -> None:
    """Every policy anything else in this repository constructs is protective, because none of them
    passes the argument."""
    assert ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20).protective


def test_the_live_pipeline_cannot_build_an_unprotected_policy() -> None:
    """`_exit_policy` reads `exit.atr_stop_multiple` and `exit.max_holding_period` from the
    registry and passes nothing else. There is no registry value that could switch the protective
    slot off, and this asserts the constructed policy rather than trusting that reading."""
    from swingdesk.application.pipeline import _exit_policy
    from swingdesk.platform.parameters import ParameterRegistry

    registry = ParameterRegistry({
        "exit.atr_stop_multiple": {"id": "exit.atr_stop_multiple", "value": "2.0",
                                   "provenance": "assumed:DR-012", "unit": "multiple of ATR",
                                   "named_in": ["M48-T0738"]},
        "exit.max_holding_period": {"id": "exit.max_holding_period", "value": 20,
                                    "provenance": "assumed:DR-012", "unit": "trading days",
                                    "named_in": ["M57-T0866"]},
    })
    policy = _exit_policy(registry)
    assert isinstance(policy, ExitPolicy), policy
    assert policy.protective, "the live path built a position with no stop"
