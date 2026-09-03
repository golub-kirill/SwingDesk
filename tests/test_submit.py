"""Submitting an order: the four guards, the idempotency key, and the shape that goes on the wire.

Offline like every other test here - the transport is injected and records what it was asked to
send (`CI_POLICY.md` 4).

**Most of this file asserts REFUSALS, and that is the right ratio.** `CHARTER` A-002 authorises the
machine to place an order nobody approved; `DR-027` 4 answers that with four independent guards.
A suite that mostly proved submission WORKS would be testing the easy half of a change whose whole
risk is in the other one.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from swingdesk.broker import armed, submit
from swingdesk.broker import policy as policy_module
from swingdesk.broker.alpaca import AlpacaClient, BrokerUnavailable, Credentials, SubmissionStopped
from swingdesk.broker.armed import STOPPED, Arming
from swingdesk.broker.policy import PolicyRefused
from swingdesk.contracts.broker import EntryOrder

OBSERVED_AT = datetime(2026, 9, 1, 21, 0, tzinfo=UTC)
SESSION = date(2026, 9, 1)

ACCEPTED = {
    "id": "6f0b0000-0000-0000-0000-00000000000a",
    "client_order_id": "swingdesk-2026-09-01-TEST.1",
    "symbol": "TEST.1",
    "status": "accepted",
    "submitted_at": "2026-09-01T13:31:00.123456Z",
    "filled_qty": "0",
}


def _write_policy():
    write = policy_module.load().write
    assert write is not None, "the committed policy must carry a write section"
    return write


#: The take-profit leg. `exit.target_r_multiple` is UNSET in the real registry, so these tests pass
#: a price directly rather than reading it - `test_the_target_comes_from_a_parameter` is what covers
#: the read, and it asserts the unset case, which is production's today.
TARGET = Decimal("55.50")


def _order(instrument_id: str = "TEST.1", shares: int = 10) -> EntryOrder:
    return submit.entry_order(
        instrument_id=instrument_id, shares=shares,
        limit_price=Decimal("50.25"), stop_price=Decimal("45.00"), target=TARGET,
        session_date=SESSION, write=_write_policy(), market="NYSE",
    )


def _transport(payload: object, status: int = 200):
    sent: list[dict[str, object]] = []

    def _call(method, url, headers, timeout_seconds, max_bytes, body=None):
        sent.append({"method": method, "url": url, "headers": headers, "body": body})
        return status, json.dumps(payload).encode("utf-8")

    _call.sent = sent  # type: ignore[attr-defined]
    return _call


def _client(arming: Arming = STOPPED, payload: object = ACCEPTED, status: int = 200):
    return AlpacaClient(
        policy=policy_module.load(),
        credentials=Credentials(key_id="k", secret="s"),
        transport=_transport(payload, status),
        arming=arming,
    )


# --- the kill switch: every path that is not an explicit yes is stopped ------------------------


def test_a_missing_switch_file_stops_submission(tmp_path: Path) -> None:
    decision = armed.read(tmp_path, _write_policy())
    assert decision.stopped
    assert "does not exist" in decision.reason


def test_an_empty_switch_file_stops_submission(tmp_path: Path) -> None:
    """An accidental file - a stray redirect, a touch - must not arm anything."""
    write = _write_policy()
    (tmp_path / write.kill_switch_file).write_text("", encoding="utf-8")
    assert armed.read(tmp_path, write).stopped


def test_a_switch_without_the_marker_stops_submission(tmp_path: Path) -> None:
    write = _write_policy()
    (tmp_path / write.kill_switch_file).write_text("yes please", encoding="utf-8")
    decision = armed.read(tmp_path, write)
    assert decision.stopped
    assert write.armed_marker in decision.reason


def test_no_write_permission_stops_submission(tmp_path: Path) -> None:
    assert armed.read(tmp_path, None).stopped


def test_an_unreadable_switch_stops_submission(tmp_path: Path, monkeypatch) -> None:
    """The branch where failing OPEN would be invisible.

    Nothing is wrong with the venue and nothing is wrong with the account - the machine would
    simply trade. `DR-025` 2.1 records this project reading a polarity backwards once already.
    """
    write = _write_policy()
    switch = tmp_path / write.kill_switch_file
    switch.write_text(write.armed_marker, encoding="utf-8")

    def _refuse(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "read_text", _refuse)
    decision = armed.read(tmp_path, write)
    assert decision.stopped
    assert "could not be read" in decision.reason


def test_the_marker_arms_it(tmp_path: Path) -> None:
    write = _write_policy()
    (tmp_path / write.kill_switch_file).write_text(
        f"{write.armed_marker}\npaper only\n", encoding="utf-8"
    )
    decision = armed.read(tmp_path, write)
    assert decision.armed
    assert write.kill_switch_file in decision.reason


def test_the_default_arming_is_stopped() -> None:
    """A client built without an arming decision cannot write. The safe state is the forgetful one."""
    assert STOPPED.stopped


# --- the idempotency key ------------------------------------------------------------------------


def test_the_key_is_derived_from_the_session_and_the_instrument() -> None:
    write = _write_policy()
    first = submit.client_order_id(SESSION, "TEST.1", write)
    again = submit.client_order_id(SESSION, "TEST.1", write)
    assert first == again == f"{write.client_order_id_prefix}-2026-09-01-TEST.1"


def test_a_different_session_is_a_different_key() -> None:
    write = _write_policy()
    assert submit.client_order_id(SESSION, "TEST.1", write) != submit.client_order_id(
        date(2026, 9, 2), "TEST.1", write
    )


def test_an_unsafe_instrument_id_refuses_rather_than_being_rewritten() -> None:
    """Rewriting would let two instruments derive one key, which is the collision it exists to stop."""
    with pytest.raises(PolicyRefused, match="two instruments derive one id"):
        submit.client_order_id(SESSION, "TEST 1/A", _write_policy())


def test_an_overlong_key_refuses_rather_than_truncating() -> None:
    with pytest.raises(PolicyRefused, match="Truncating"):
        submit.client_order_id(SESSION, "T" * 200, _write_policy())


# --- what may be built --------------------------------------------------------------------------


def test_a_canadian_instrument_is_refused_not_translated() -> None:
    with pytest.raises(PolicyRefused, match="never merged"):
        _order("TEST.2.TO")


def test_zero_shares_is_a_refusal_that_never_reaches_the_wire() -> None:
    with pytest.raises(PolicyRefused, match="nothing to submit"):
        _order(shares=0)


def test_a_stop_at_or_above_the_limit_is_refused() -> None:
    with pytest.raises(ValueError, match="not below the limit"):
        EntryOrder(
            client_order_id="x", session_date=SESSION, instrument_id="TEST.1", symbol="TEST.1",
            shares=1, limit_price=Decimal("50"), stop_price=Decimal("50"), target_price=TARGET,
        )


# --- the chokepoint -----------------------------------------------------------------------------


def test_a_client_that_was_never_armed_cannot_submit() -> None:
    client = _client()
    with pytest.raises(SubmissionStopped, match="stopped by default"):
        client.submit(_order(), OBSERVED_AT)
    assert client.transport.sent == [], "nothing may reach the wire"  # type: ignore[attr-defined]


def test_the_guard_runs_before_anything_that_could_fail_for_another_reason() -> None:
    """A stopped switch must not be reported as a venue problem.

    The two exceptions send a reader to different places at 18:31 - one to the network, one to the
    switch file - and only one of them is where the answer is.
    """
    client = _client()
    with pytest.raises(SubmissionStopped):
        client.submit(_order(), OBSERVED_AT)


def test_an_armed_client_sends_the_bracket_dr_027_specifies() -> None:
    client = _client(Arming(True, "armed in a test"))
    placed = client.submit(_order(), OBSERVED_AT)

    sent = client.transport.sent  # type: ignore[attr-defined]
    assert len(sent) == 1
    assert sent[0]["method"] == "POST"
    assert sent[0]["url"].endswith("/v2/orders")
    body = json.loads(sent[0]["body"])

    write = _write_policy()
    assert body["symbol"] == "TEST.1"
    assert body["qty"] == "10"
    assert body["side"] == write.side
    assert body["type"] == write.order_type
    assert body["time_in_force"] == write.time_in_force
    assert body["order_class"] == write.order_class
    # The limit is the SIZING price, not a price chosen for the order: every R the resulting
    # position reports is denominated in it (DR-027 3.1).
    assert body["limit_price"] == "50.25"
    assert body["stop_loss"] == {"stop_price": "45.00"}
    # A bracket is a chain of THREE and the venue refuses one with a leg missing - measured against
    # the real endpoint, not read: `bracket orders require take_profit.limit_price` (`DR-027` 9).
    assert body["take_profit"] == {"limit_price": "55.50"}
    assert body["client_order_id"] == "swingdesk-2026-09-01-TEST.1"

    assert placed.client_order_id == "swingdesk-2026-09-01-TEST.1"
    assert placed.status == "accepted"
    assert placed.filled_shares == Decimal(0)


def test_the_secret_travels_in_a_header_and_never_in_the_url() -> None:
    client = _client(Arming(True, "armed in a test"))
    client.submit(_order(), OBSERVED_AT)
    sent = client.transport.sent[0]  # type: ignore[attr-defined]
    assert "APCA-API-SECRET-KEY" in sent["headers"]
    assert "secret" not in sent["url"]


def test_a_duplicate_is_refused_by_the_venue_and_its_reason_travels() -> None:
    """Idempotency is enforced where the knowledge is - by the party that accepted the first one."""
    client = _client(
        Arming(True, "armed in a test"),
        payload={"code": 42210000, "message": "client_order_id must be unique"},
        status=422,
    )
    with pytest.raises(BrokerUnavailable, match="client_order_id must be unique"):
        client.submit(_order(), OBSERVED_AT)


def test_a_write_disabled_policy_stops_an_armed_client(tmp_path: Path) -> None:
    """The guards are independent: arming the switch does not overrule the committed policy."""
    import yaml

    raw = yaml.safe_load(policy_module.POLICY_PATH.read_text(encoding="utf-8"))
    raw["access"]["write_enabled"] = False
    raw["access"]["allowed_methods"] = ["GET"]
    written = tmp_path / "broker_policy.yml"
    written.write_text(yaml.safe_dump(raw), encoding="utf-8")

    client = AlpacaClient(
        policy=policy_module.load(written),
        credentials=Credentials(key_id="k", secret="s"),
        transport=_transport(ACCEPTED),
        arming=Arming(True, "armed in a test"),
    )
    with pytest.raises(SubmissionStopped, match="write_enabled"):
        client.submit(_order(), OBSERVED_AT)
    assert client.transport.sent == []  # type: ignore[attr-defined]


def test_write_enabled_without_a_write_section_will_not_load(tmp_path: Path) -> None:
    import yaml

    raw = yaml.safe_load(policy_module.POLICY_PATH.read_text(encoding="utf-8"))
    del raw["write"]
    written = tmp_path / "broker_policy.yml"
    written.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(PolicyRefused, match="no kill switch"):
        policy_module.load(written)


def test_a_policy_permitting_cancellation_will_not_load(tmp_path: Path) -> None:
    import yaml

    raw = yaml.safe_load(policy_module.POLICY_PATH.read_text(encoding="utf-8"))
    raw["access"]["allowed_methods"] = ["GET", "POST", "DELETE"]
    written = tmp_path / "broker_policy.yml"
    written.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(PolicyRefused, match="DR-027 covers submission only"):
        policy_module.load(written)


def test_the_write_verb_comes_from_the_policy_and_not_from_the_code() -> None:
    """Which is why gate 39 can keep an absolute rule about verb literals in the package."""
    assert policy_module.load().write_method == "POST"


# --- the target, which is mandatory and unset -------------------------------------------------


def test_a_target_at_or_below_the_entry_is_refused() -> None:
    """An instruction to sell at a loss on the way up."""
    with pytest.raises(ValueError, match="not above the limit"):
        EntryOrder(
            client_order_id="x", session_date=SESSION, instrument_id="TEST.1", symbol="TEST.1",
            shares=1, limit_price=Decimal("50"), stop_price=Decimal("45"),
            target_price=Decimal("50"),
        )


def test_the_target_comes_from_the_real_registry_and_is_one_r() -> None:
    """`DR-029`, ruled by the owner 2026-09-01. The REAL registry, not a fixture.

    Pinned deliberately: a fixture would pass whatever it was shown, and this value is what every
    order this system places will carry. `test_an_unset_target_refuses` covers the other side.
    """
    from swingdesk.platform.parameters import ParameterRegistry

    assert submit.target_price(
        Decimal("100.00"), Decimal("5.27"), ParameterRegistry.load()
    ) == Decimal("105.27")


def test_an_unset_target_refuses_rather_than_inventing_one() -> None:
    """The venue requires both legs of a bracket, so an unset target is no order at all.

    Inventing one to satisfy a wire format would be authoring a threshold (`AGENTS.md` 8), and the
    branch has to keep working for the day somebody clears the value.
    """
    from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset

    empty = ParameterRegistry({
        "exit.target_r_multiple": {
            "id": "exit.target_r_multiple", "value": None, "provenance": None,
            "status": "unset", "unit": "R", "named_in": ["M53-T0807"],
        },
    })
    with pytest.raises(ParameterUnset, match=re.escape("exit.target_r_multiple")):
        submit.target_price(Decimal("100"), Decimal("5"), empty)


def test_a_nonpositive_target_multiple_refuses() -> None:
    from swingdesk.platform.parameters import ParameterRegistry

    zero = ParameterRegistry({
        "exit.target_r_multiple": {
            "id": "exit.target_r_multiple", "value": "0", "provenance": "owner",
            "status": "owner", "unit": "R", "named_in": ["M53-T0807"],
        },
    })
    with pytest.raises(ValueError, match="sell at a loss on the way up"):
        submit.target_price(Decimal("100"), Decimal("5"), zero)


def test_the_target_is_r_above_the_entry_once_a_value_exists() -> None:
    """R is `entry - stop + costs`, so the target is volatility-normalised by construction."""
    from swingdesk.platform.parameters import ParameterRegistry

    registry = ParameterRegistry({
        "exit.target_r_multiple": {
            "id": "exit.target_r_multiple", "value": "2.0", "provenance": "owner",
            "status": "owner", "unit": "R", "named_in": ["M53-T0808"],
        },
    })
    assert submit.target_price(Decimal("100"), Decimal("5.27"), registry) == Decimal("110.54")


def test_the_trading_session_is_the_exchange_s_and_not_the_clock_s() -> None:
    """`DR-027` 9, and a real order is what found it.

    At 19:57 New York on 1 September the UTC date is already the 2nd, so the 18:30 pass and the
    19:30 retry `DR-015` provides for would key on different days and resubmit every entry.
    """
    from datetime import timedelta

    after_the_close = datetime(2026, 9, 2, 0, 57, tzinfo=UTC)
    before_midnight = after_the_close - timedelta(hours=2)
    assert after_the_close.date() != before_midnight.date(), "the fixture must straddle midnight"
    assert (submit.trading_session("NYSE", after_the_close)
            == submit.trading_session("NYSE", before_midnight))


# --------------------------------------------------------------------------------------------
# `DR-033`: the venue prices in pennies, and rounding is never allowed to flatter.
#
# THE REGRESSION. The first four real orders this system ever sent were ALL rejected:
#   invalid limit_price 66.949997. sub-penny increment does not fulfill minimum pricing criteria
# The whole pipeline was right - caps, guards, allocation - and the wire format was wrong. Only a
# real order could find it, which is the third time that has been true (`DR-027` §9).


def _write_policy():
    from swingdesk.broker import policy as policy_module

    write = policy_module.load().write
    assert write is not None
    return write


def test_the_four_prices_the_venue_actually_rejected_are_now_valid() -> None:
    """Named literally, because a regression test whose inputs are invented is testing a guess."""
    from swingdesk.broker.submit import to_tick

    write = _write_policy()
    rejected = {
        Decimal("66.949997"): Decimal("66.94"),
        Decimal("106.059998"): Decimal("106.05"),
        Decimal("106.480003"): Decimal("106.48"),
        Decimal("65.72569193187650639356166246"): Decimal("65.72"),
    }
    for raw, expected in rejected.items():
        assert to_tick(raw, write, favouring="cheaper") == expected
        assert to_tick(raw, write, favouring="cheaper") % write.tick_size == 0


def test_every_leg_rounds_the_way_that_cannot_hurt() -> None:
    """The tick is the venue's rule; the DIRECTION is ours, and it is the half that matters.

    An entry rounded UP could fill above the price its R was computed against - permanently, on the
    one statistic the validation programme is measured in. A stop rounded DOWN would risk more per
    share than the sizing planned.
    """
    from swingdesk.broker.submit import to_tick

    write = _write_policy()
    price = Decimal("50.005")

    assert to_tick(price, write, favouring="cheaper") == Decimal("50.00"), "entry never rounds up"
    assert to_tick(price, write, favouring="safer") == Decimal("50.01"), "stop never rounds down"


def test_a_price_already_on_the_tick_is_untouched() -> None:
    from swingdesk.broker.submit import to_tick

    write = _write_policy()
    for direction in ("cheaper", "safer"):
        assert to_tick(Decimal("50.00"), write, favouring=direction) == Decimal("50.00")


def test_below_a_dollar_the_venue_allows_four_decimals() -> None:
    """`universe.min_price` admits nothing under $5, so this is unreachable today.

    Asserted anyway: a rounding rule that silently did the wrong thing below a dollar would be
    waiting for the day that floor moves, and the policy declares the increment for exactly that.
    """
    from swingdesk.broker.submit import to_tick

    write = _write_policy()
    assert to_tick(Decimal("0.123456"), write, favouring="cheaper") == Decimal("0.1234")
    assert to_tick(Decimal("0.123456"), write, favouring="safer") == Decimal("0.1235")


def test_an_order_whose_legs_collapse_once_rounded_is_refused() -> None:
    """Rounding must not be allowed to produce an order with no R denominator.

    A stop a fraction below the entry rounds UP onto it; sending that would put a position in the
    book whose reported R is zero, and finding out from a 422 is the expensive place to find out.
    """
    from swingdesk.broker.policy import PolicyRefused
    from swingdesk.broker.submit import entry_order

    write = _write_policy()
    with pytest.raises(PolicyRefused, match="no longer below the entry"):
        entry_order(
            instrument_id="AAPL", shares=10,
            limit_price=Decimal("50.004"), stop_price=Decimal("49.999"),
            target=Decimal("60.00"), session_date=date(2026, 9, 2), write=write, market="NYSE",
        )


def test_a_target_that_rounds_onto_the_entry_is_refused() -> None:
    from swingdesk.broker.policy import PolicyRefused
    from swingdesk.broker.submit import entry_order

    write = _write_policy()
    with pytest.raises(PolicyRefused, match="sell at a loss on the way up"):
        entry_order(
            instrument_id="AAPL", shares=10,
            limit_price=Decimal("50.00"), stop_price=Decimal("45.00"),
            target=Decimal("50.009"), session_date=date(2026, 9, 2), write=write, market="NYSE",
        )


def test_a_built_order_carries_only_tick_aligned_prices() -> None:
    """End to end: the three legs the venue sees are all multiples of its increment."""
    from swingdesk.broker.submit import entry_order

    write = _write_policy()
    order = entry_order(
        instrument_id="AIS", shares=17,
        limit_price=Decimal("66.949997"),
        stop_price=Decimal("61.69966995546901155580079372"),
        target=Decimal("72.20033004453098844419920628"),
        session_date=date(2026, 9, 2), write=write, market="NYSE",
    )
    assert order.limit_price == Decimal("66.94")
    assert order.stop_price == Decimal("61.70"), "the stop rounds UP, nearer the entry"
    assert order.target_price == Decimal("72.20")
    for price in (order.limit_price, order.stop_price, order.target_price):
        assert price % write.tick_size == 0
    assert order.stop_price < order.limit_price < order.target_price
