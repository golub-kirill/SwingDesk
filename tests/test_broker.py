"""The broker adapter: read-only, one host, and a reconciliation that refuses to guess.

**Offline by construction.** Every response here is a recorded fixture served through the injected
transport, so the suite exercises the production parsing path without a socket (`CI_POLICY.md` 4).

**The two tests that matter most are the ones about what this cannot do**: `test_policy_refuses_a_
write_verb` and `test_paper_host_is_not_the_forbidden_live_host`. The first is `D1`/`BR-1` made
executable; the second is a regression for the bug gate 39 found on its first run, where a
substring test called the paper host forbidden - and would have admitted a lookalike host.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from swingdesk.broker import policy as policy_module
from swingdesk.broker.alpaca import (
    AlpacaClient,
    BrokerUnavailable,
    Credentials,
    CredentialsMissing,
    credentials_from_env,
)
from swingdesk.broker.policy import PolicyRefused

# Imported from the MODULE and not from the package: `swingdesk.broker` re-exports a FUNCTION
# called `reconcile`, which shadows the module of the same name on an `import ... as`.
from swingdesk.broker.reconcile import (
    Unprotected,
    own_stop,
    reconcile,
    resting_stops,
    restorable,
    unprotected,
    unrecorded_fills,
    withdrawn_stops,
)
from swingdesk.contracts.broker import BrokerPosition, FillKind, PositionSide, Side
from swingdesk.contracts.position import Position

OBSERVED_AT = datetime(2026, 8, 31, 21, 0, tzinfo=UTC)
OPENED_ON = date(2026, 8, 20)

ACCOUNT = {
    "id": "9f1a0000-0000-0000-0000-000000000001",
    "account_number": "PA3XYZTEST01",
    "status": "ACTIVE",
    "currency": "USD",
    "cash": "100000.00",
    "equity": "100123.45",
    "buying_power": "200246.90",
    "trading_blocked": False,
    "account_blocked": False,
}

HELD = [
    {
        "asset_id": "b0", "symbol": "TEST.1", "exchange": "NYSE", "asset_class": "us_equity",
        "qty": "100", "side": "long", "avg_entry_price": "50.25", "current_price": "52.00",
        "market_value": "5200.00", "cost_basis": "5025.00", "unrealized_pl": "175.00",
    },
]

FILLS = [
    {
        "id": "20260820000000000::a", "activity_type": "FILL", "order_id": "o-1",
        "symbol": "TEST.1", "side": "buy", "type": "fill",
        "transaction_time": "2026-08-20T13:31:04.123Z",
        "price": "50.25", "qty": "100", "cum_qty": "100", "leaves_qty": "0",
        "order_status": "filled",
    },
]


def _policy(tmp_path: Path, **overrides: object) -> policy_module.BrokerPolicy:
    """The committed policy, optionally with one section replaced, written to a temp file.

    The real file is loaded and then edited, rather than a fixture policy being invented here: a
    test policy that drifts from the committed one tests a system nobody runs, and the committed
    one is the thing gate 39 protects.
    """
    import yaml

    raw = yaml.safe_load(policy_module.POLICY_PATH.read_text(encoding="utf-8"))
    for dotted, value in overrides.items():
        section, _, key = dotted.partition("__")
        raw[section][key] = value
    written = tmp_path / "broker_policy.yml"
    written.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return policy_module.load(written)


def _transport(responses: dict[str, object], status: int = 200):
    """A transport that answers by endpoint substring. Records the calls it was asked to make."""
    calls: list[tuple[str, str]] = []

    def _call(method, url, headers, timeout_seconds, max_bytes):
        calls.append((method, url))
        for fragment, payload in responses.items():
            if fragment in url:
                return status, json.dumps(payload).encode("utf-8")
        raise AssertionError(f"no fixture for {url}")

    _call.calls = calls  # type: ignore[attr-defined]
    return _call


def _client(tmp_path: Path, responses: dict[str, object], status: int = 200) -> AlpacaClient:
    return AlpacaClient(
        policy=_policy(tmp_path),
        credentials=Credentials(key_id="k", secret="s"),
        transport=_transport(responses, status),
    )


def _position(instrument_id: str, shares: int = 100, entry: str = "50.25") -> Position:
    return Position(
        position_id=f"POS-{instrument_id}-2026-08-20", version=1, instrument_id=instrument_id,
        opened_on=OPENED_ON, entry_price=Decimal(entry), shares=shares,
        initial_stop=Decimal("45.00"), current_stop=Decimal("45.00"),
        initial_costs_per_share=Decimal("0.02"), knowledge_time=OBSERVED_AT,
    )


def _holding(symbol: str = "TEST.1", **overrides: object) -> BrokerPosition:
    fields: dict[str, object] = {
        "symbol": symbol, "asset_class": "us_equity", "exchange": "NYSE",
        "side": PositionSide.LONG, "shares": Decimal(100),
        "average_entry_price": Decimal("50.25"), "observed_at": OBSERVED_AT,
    }
    fields.update(overrides)
    return BrokerPosition(**fields)  # type: ignore[arg-type]


# --- the policy, which is the whole paper/live boundary --------------------------------------


def test_the_committed_policy_loads() -> None:
    """Reading is always permitted; writing is whatever the committed file currently says.

    This assertion deliberately does NOT pin `write_enabled`. It was `False` until `CHARTER` A-002
    (2026-09-01) and is `True` now, and a test that pinned it would have to be edited by the same
    commit that changes the policy - which is a test agreeing with whatever it is shown rather than
    checking anything. What is pinned is the invariant: GET is always there, the host is https, and
    a policy permitting writes carries a kill switch. `test_submit.py` owns the write contract.
    """
    loaded = policy_module.load()
    assert "GET" in loaded.allowed_methods
    assert loaded.base_url.startswith("https://")
    assert (loaded.write is not None) == loaded.write_enabled


def test_paper_host_is_not_the_forbidden_live_host() -> None:
    """Regression for gate 39's first run: hosts are compared as hostnames, not substrings.

    `paper-api.alpaca.markets` CONTAINS `api.alpaca.markets`, so a substring test refused the paper
    host - and the same test would have ADMITTED `paper-api.alpaca.markets.example.com`, which is
    somebody else's server. Both directions are wrong and both are closed by an equality.
    """
    loaded = policy_module.load()
    assert loaded.forbidden_hosts, "the live venue must be named, not merely omitted"
    for forbidden in loaded.forbidden_hosts:
        assert forbidden in loaded.base_url, "the substring test this replaced would have fired"


def test_a_write_verb_without_the_permission_does_not_load(tmp_path: Path) -> None:
    """The two halves must agree. A policy that lists a write verb while claiming to be read-only
    is describing two different systems, and the loader refuses rather than picking one."""
    with pytest.raises(PolicyRefused, match="read-only"):
        _policy(tmp_path, access__write_enabled=False)


def test_the_permission_without_a_verb_does_not_load(tmp_path: Path) -> None:
    """And the other way round: a permission nothing can use is a claim, not a capability."""
    with pytest.raises(PolicyRefused, match="cannot be exercised"):
        _policy(tmp_path, access__allowed_methods=["GET"], access__write_enabled=True)


def test_policy_refuses_a_second_host(tmp_path: Path) -> None:
    with pytest.raises(PolicyRefused, match="Exactly one host"):
        _policy(tmp_path, venue__base_url_allowlist=[
            "https://paper-api.alpaca.markets", "https://api.alpaca.markets",
        ])


def test_policy_refuses_the_live_host(tmp_path: Path) -> None:
    with pytest.raises(PolicyRefused, match="forbidden_hosts"):
        _policy(tmp_path, venue__base_url_allowlist=["https://api.alpaca.markets"])


def test_policy_refuses_plain_http(tmp_path: Path) -> None:
    with pytest.raises(PolicyRefused, match="not https"):
        _policy(tmp_path, venue__base_url_allowlist=["http://paper-api.alpaca.markets"])


def test_policy_refuses_a_zero_limit(tmp_path: Path) -> None:
    with pytest.raises(PolicyRefused, match="not a limit"):
        _policy(tmp_path, limits__request_timeout_seconds=0)


def test_check_method_refuses_every_verb_the_policy_does_not_name() -> None:
    """Reading, submitting and `DR-043`'s replace are permitted; cancelling and overwriting are not.

    A cancel always leaves a moment with no stop, which is why `DR-043` chose the replace and
    nothing has ruled on a cancel.
    """
    loaded = policy_module.load()
    loaded.check_method("GET")
    loaded.check_method(loaded.write_method)
    loaded.check_method(loaded.replace_method)
    for verb in ("PUT", "DELETE"):
        with pytest.raises(PolicyRefused, match="D1/BR-1"):
            loaded.check_method(verb)


def test_url_comes_from_the_policy_and_never_from_a_caller() -> None:
    loaded = policy_module.load()
    assert loaded.url("account") == loaded.base_url + "/v2/account"
    with pytest.raises(PolicyRefused, match="no endpoint"):
        loaded.url("orders/place")


# --- credentials -------------------------------------------------------------------------------


def test_credentials_never_print_themselves() -> None:
    rendered = repr(Credentials(key_id="AKREAL", secret="supersecret"))
    assert "AKREAL" not in rendered
    assert "supersecret" not in rendered


def test_missing_credentials_are_not_the_venue_being_down(monkeypatch) -> None:
    loaded = policy_module.load()
    monkeypatch.delenv(loaded.key_env, raising=False)
    monkeypatch.delenv(loaded.secret_env, raising=False)
    with pytest.raises(CredentialsMissing, match=loaded.key_env):
        credentials_from_env(loaded)


def test_the_secret_never_reaches_a_url(tmp_path: Path) -> None:
    """The key pair travels in headers. A URL is logged and a header is not."""
    client = _client(tmp_path, {"/v2/account": ACCOUNT})
    client.account(OBSERVED_AT)
    for _, url in client.transport.calls:  # type: ignore[attr-defined]
        assert "k" not in url.replace("markets", "").replace("alpaca", "")


# --- reading the venue -------------------------------------------------------------------------


def test_account_is_parsed_exactly_and_carries_no_account_number(tmp_path: Path) -> None:
    account = _client(tmp_path, {"/v2/account": ACCOUNT}).account(OBSERVED_AT)
    assert account.equity == Decimal("100123.45")
    assert account.cash == Decimal("100000.00")
    assert account.status == "ACTIVE"
    # SECURITY 2.4: the number is digested and discarded, so nothing downstream can print it.
    assert ACCOUNT["account_number"] not in repr(account)
    assert ACCOUNT["id"] not in repr(account)
    assert len(account.fingerprint) == 12


def test_positions_are_parsed_and_sorted(tmp_path: Path) -> None:
    payload = [dict(HELD[0]), {**HELD[0], "symbol": "TEST.0", "qty": "5"}]
    held = _client(tmp_path, {"/v2/positions": payload}).positions(OBSERVED_AT)
    assert [holding.symbol for holding in held] == ["TEST.0", "TEST.1"]
    assert held[1].average_entry_price == Decimal("50.25")
    assert held[1].whole_shares == 100


def test_a_fractional_holding_reports_none_rather_than_rounding(tmp_path: Path) -> None:
    payload = [{**HELD[0], "qty": "1.5"}]
    held = _client(tmp_path, {"/v2/positions": payload}).positions(OBSERVED_AT)
    assert held[0].shares == Decimal("1.5")
    assert held[0].whole_shares is None


def test_fills_are_parsed(tmp_path: Path) -> None:
    fills = _client(tmp_path, {"/activities/": FILLS}).fills(OBSERVED_AT)
    assert len(fills) == 1
    assert fills[0].side is Side.BUY
    assert fills[0].kind is FillKind.FILL
    assert fills[0].price == Decimal("50.25")
    assert fills[0].transaction_time.tzinfo is not None


def test_a_missing_money_field_refuses_rather_than_defaulting_to_zero(tmp_path: Path) -> None:
    broken = {key: value for key, value in ACCOUNT.items() if key != "equity"}
    with pytest.raises(BrokerUnavailable, match="equity is missing"):
        _client(tmp_path, {"/v2/account": broken}).account(OBSERVED_AT)


def test_an_unparseable_number_refuses(tmp_path: Path) -> None:
    with pytest.raises(BrokerUnavailable, match="not a number"):
        _client(tmp_path, {"/v2/account": {**ACCOUNT, "cash": "n/a"}}).account(OBSERVED_AT)


def test_a_naive_timestamp_refuses(tmp_path: Path) -> None:
    naive = [{**FILLS[0], "transaction_time": "2026-08-20T13:31:04"}]
    with pytest.raises(BrokerUnavailable, match="no timezone"):
        _client(tmp_path, {"/activities/": naive}).fills(OBSERVED_AT)


def test_an_unknown_side_refuses(tmp_path: Path) -> None:
    with pytest.raises(BrokerUnavailable, match="side is"):
        _client(tmp_path, {"/activities/": [{**FILLS[0], "side": "sideways"}]}).fills(OBSERVED_AT)


def test_rejected_credentials_are_reported_as_such(tmp_path: Path) -> None:
    with pytest.raises(BrokerUnavailable, match="refused the credentials"):
        _client(tmp_path, {"/v2/account": {}}, status=401).account(OBSERVED_AT)


def test_page_walking_stops_at_the_policy_ceiling(tmp_path: Path) -> None:
    """A paged endpoint followed until the server stops is unbounded. It raises instead."""
    policy = _policy(tmp_path, limits__page_size=1, limits__max_pages=2)
    client = AlpacaClient(
        policy=policy,
        credentials=Credentials(key_id="k", secret="s"),
        transport=_transport({"/activities/": FILLS}),
    )
    with pytest.raises(BrokerUnavailable, match="still paging"):
        client.fills(OBSERVED_AT)


# --- the reconciliation ------------------------------------------------------------------------


def _reconcile(book, held):
    return reconcile(book, held, venue="test venue", market="NYSE")


def test_two_books_that_agree() -> None:
    report = _reconcile([_position("TEST.1")], [_holding()])
    assert report.agrees
    assert report.code is None
    assert report.agreed[0].shares == 100


def test_a_position_the_venue_does_not_hold_is_tech() -> None:
    report = _reconcile([_position("TEST.1")], [])
    assert not report.agrees
    assert report.code == "TECH"
    assert report.divergences[0].reason == "book_only"


def test_a_holding_the_book_never_opened_is_tech() -> None:
    report = _reconcile([], [_holding()])
    assert report.divergences[0].reason == "venue_only"
    assert report.unrecorded_symbols == ("TEST.1",)


def test_a_share_count_disagreement_is_tech() -> None:
    report = _reconcile([_position("TEST.1", shares=50)], [_holding()])
    assert report.divergences[0].reason == "shares"


def test_an_entry_price_disagreement_is_tech() -> None:
    report = _reconcile([_position("TEST.1", entry="49.00")], [_holding()])
    assert report.divergences[0].reason == "entry_price"


def test_a_fractional_holding_is_reported_not_rounded() -> None:
    report = _reconcile([_position("TEST.1")], [_holding(shares=Decimal("100.5"))])
    assert report.divergences[0].reason == "fractional"


def test_a_short_is_a_position_this_system_cannot_describe() -> None:
    report = _reconcile([_position("TEST.1")], [_holding(side=PositionSide.SHORT)])
    assert report.divergences[0].reason == "short"


def test_a_canadian_position_is_out_of_scope_and_not_a_divergence() -> None:
    """AGENTS 3: USA and Canada are never merged.

    This venue does not trade the TSX, so its silence about a `.TO` holding is not evidence of an
    unrecorded exit. Counting it as one would break the rule by omission - the reconciliation would
    report a mismatch that cannot exist, and the course's action for `TECH` is to pause entries.
    """
    report = _reconcile([_position("TEST.2.TO")], [])
    assert report.agrees
    assert report.out_of_scope == ("TEST.2.TO",)


def test_unrecorded_fills_names_executions_with_no_position(tmp_path: Path) -> None:
    fills = _client(tmp_path, {"/activities/": FILLS}).fills(OBSERVED_AT)
    assert unrecorded_fills(fills, []) == fills
    assert unrecorded_fills(fills, [_position("TEST.1")]) == ()


# ------------------------------------------------------------ which unprotected positions get one
#
# `DR-037` §3's line, and it has to stay narrow. The predicate was written twice - inline in
# `cli._submit` and again in `tools/verify_submission_guards.py` - which is the drift
# `tests/test_guard_parity.py` exists to catch. It is one function now, and these are its tests.


def _finding(instrument_id: str, venue_stop: Decimal | None) -> Unprotected:
    return Unprotected(
        instrument_id=instrument_id, book_stop=Decimal("45.00"), shares=100,
        venue_stop=venue_stop, reason="fixture",
    )


def test_a_position_with_nothing_resting_is_restored() -> None:
    """The case `DR-037` was ruled for: the protection was decided, sent, and expired with the
    session. Placing it again restores; it moves nothing."""
    keep, leave = restorable([_finding("AIS", None)])
    assert [f.instrument_id for f in keep] == ["AIS"]
    assert leave == ()
    # `DR-041`'s adoption in `sync-fills` reads only `leave` and dereferences `venue_stop` without
    # a guard that could ever fire. THIS is the assertion that makes that safe: a finding with
    # nothing resting must never appear there, or the adoption would try to write a stop of `None`
    # over a real one.


def test_a_stop_resting_at_the_wrong_price_is_left_alone() -> None:
    """THE ONE THAT MATTERS, because getting it wrong applies a move nobody approved.

    A stop standing at a price the book does not record is a stop somebody MOVED. `D6` governs a
    move. Placing a second one would leave two triggers on one position, and `unprotected` reads
    the HIGHEST as the one in force - so restoring here would silently enact the move.
    """
    keep, leave = restorable([_finding("BTSG", Decimal("52.00"))])
    assert keep == ()
    assert [f.instrument_id for f in leave] == ["BTSG"]


def test_the_two_kinds_are_split_and_nothing_is_dropped() -> None:
    """Every finding lands in exactly one side. A position quietly in neither is one nobody acts on."""
    findings = [
        _finding("AIS", None), _finding("BTSG", Decimal("52.00")),
        _finding("DINO", None), _finding("CM", Decimal("110.00")),
    ]
    keep, leave = restorable(findings)
    assert [f.instrument_id for f in keep] == ["AIS", "DINO"]
    assert [f.instrument_id for f in leave] == ["BTSG", "CM"]
    assert len(keep) + len(leave) == len(findings)


def test_no_findings_is_not_an_error() -> None:
    assert restorable([]) == ((), ())


# ------------------------------------------------------------------ an OCO's stop rests as a LEG
#
# Measured 2026-09-04 against the live venue. `status=open` returns the `oco` PARENT and not its
# stop, because the stop's status is `held` and `held` is not `open`. `nested=true` is the only
# shape of this request that returns it at all:
#
#     status=open                 -> 3 rows, all `limit`, 0 legs
#     status=open&nested=false    -> 3 rows, all `limit`, 0 legs
#     status=open&nested=true     -> 3 rows, all `limit`, 3 legs
#
# Three positions were protected, `unprotected` could not see any of it, and the pass stopped with
# 101 candidates behind protection the venue was holding.

OCO_WITH_LEG = [{
    "id": "1e5b565a-0000-0000-0000-000000000001",
    "client_order_id": "swingdesk-protect-2026-09-03-TEST.1",
    "symbol": "TEST.1", "status": "accepted", "side": "sell", "type": "limit",
    "order_class": "oco", "limit_price": "70.03", "stop_price": None, "filled_qty": "0",
    "submitted_at": "2026-09-03T21:49:08.975524Z",
    "legs": [{
        "id": "1e5b565a-0000-0000-0000-000000000002",
        "client_order_id": "venue-generated-leg-id",
        "symbol": "TEST.1", "status": "held", "side": "sell", "type": "stop",
        "limit_price": None, "stop_price": "61.70", "filled_qty": "0",
        "submitted_at": "2026-09-03T21:49:08.975524Z",
    }],
}]


def test_open_orders_asks_for_the_legs(tmp_path: Path) -> None:
    """THE REGRESSION. Without `nested=true` the venue never mentions the stop that is standing."""
    client = _client(tmp_path, {"/orders": OCO_WITH_LEG})
    client.open_orders(OBSERVED_AT)
    urls = [url for _method, url in client.transport.calls]
    assert any("nested=true" in url for url in urls), (
        f"open_orders asked {urls}; an OCO's stop leg rests as `held`, which `status=open` "
        f"excludes, so without `nested=true` a protected position reads as naked"
    )


def test_a_leg_keeps_its_parents_id(tmp_path: Path) -> None:
    """`DR-043`: an `oco`'s stop carries an id the venue generated, so only the parent says whose.

    Flattened without it, this system's own stop reads exactly like one a person typed, and the
    replace would leave every stop it placed alone.
    """
    client = _client(tmp_path, {"/orders": OCO_WITH_LEG})
    by_type = {order.order_type: order for order in client.open_orders(OBSERVED_AT)}
    assert by_type["stop"].parent_client_order_id == OCO_WITH_LEG[0]["client_order_id"]
    assert by_type["limit"].parent_client_order_id == "", "a parent has no parent"


# --- own_stop: which resting stop is this system's to raise (DR-043) --------------------------

OUR_PARENT = "swingdesk-protect-2026-09-01-TEST.1"
SENT = frozenset({OUR_PARENT})


def _stop(symbol: str = "TEST.1", **overrides: object):
    from swingdesk.contracts.broker import PlacedOrder

    fields: dict[str, object] = dict(
        order_id="leg-1", client_order_id="venue-generated-leg-id", symbol=symbol, status="held",
        submitted_at=OBSERVED_AT, order_type="stop", stop_price=Decimal("45.00"), side="sell",
        parent_client_order_id=OUR_PARENT, observed_at=OBSERVED_AT,
    )
    fields.update(overrides)
    return PlacedOrder(**fields)  # type: ignore[arg-type]


def test_own_stop_is_found_through_its_parent() -> None:
    leg = _stop()
    assert own_stop("TEST.1", [leg], SENT) is leg


def test_a_stop_this_system_already_replaced_is_still_its_own() -> None:
    """The venue answers a replace with a new order; the journal records it under that id."""
    replacement = _stop(client_order_id="venue-generated-replacement", parent_client_order_id="")
    assert own_stop("TEST.1", [replacement], SENT | {"venue-generated-replacement"}) is replacement


def test_a_stop_a_person_placed_is_left_alone() -> None:
    """`DR-043` 3.3. Its owner is a person, and the book cannot know what they meant by it."""
    by_hand = _stop(client_order_id="dashboard-uuid", parent_client_order_id="")
    found = own_stop("TEST.1", [by_hand], SENT)
    assert isinstance(found, str) and "not placed by this system" in found
    assert "45.00" in found and "leg-1" in found, "the operator is told which stop, and where"


def test_an_id_that_looks_ours_is_not_ours() -> None:
    """`ours`' rule: the journal decides, never the first word of an id."""
    lookalike = _stop(client_order_id=OUR_PARENT + "-typed", parent_client_order_id="")
    assert isinstance(own_stop("TEST.1", [lookalike], SENT), str)


def test_an_empty_parent_id_matches_nothing() -> None:
    lone = _stop(client_order_id="dashboard-uuid", parent_client_order_id="")
    assert isinstance(own_stop("TEST.1", [lone], frozenset({""})), str)


def test_nothing_resting_is_said_plainly() -> None:
    found = own_stop("TEST.1", [], SENT)
    assert isinstance(found, str) and "no stop is resting" in found


def test_other_symbols_targets_and_buy_stops_are_not_the_stop() -> None:
    orders = [
        _stop(symbol="OTHER"),
        _stop(order_id="tp-1", order_type="limit", stop_price=None),
        _stop(order_id="buy-1", side="buy"),
        _stop(order_id="untriggered", stop_price=None),
    ]
    found = own_stop("TEST.1", orders, SENT)
    assert isinstance(found, str) and "no stop is resting" in found


def test_a_stop_limit_counts_and_an_unsided_stop_counts() -> None:
    assert own_stop("TEST.1", [_stop(order_type="stop_limit")], SENT) is not None
    assert not isinstance(own_stop("TEST.1", [_stop(order_type="stop_limit")], SENT), str)
    assert not isinstance(own_stop("TEST.1", [_stop(side="")], SENT), str)


def test_two_resting_stops_are_refused_rather_than_resolved() -> None:
    """Raising one would leave the other standing, and the higher is the one in force."""
    found = own_stop("TEST.1", [_stop(), _stop(order_id="leg-2", stop_price=Decimal("44.00"))],
                     SENT)
    assert isinstance(found, str) and "2 stops" in found and "44.00" in found


def test_open_orders_returns_the_stop_leg_as_a_resting_order(tmp_path: Path) -> None:
    """A leg IS a resting order. `DR-036` asks what is standing, not what has a parent."""
    live = _client(tmp_path, {"/orders": OCO_WITH_LEG}).open_orders(OBSERVED_AT)

    assert len(live) == 2, f"parent and leg, got {[(o.order_type, o.status) for o in live]}"
    stops = [o for o in live if o.order_type == "stop"]
    assert len(stops) == 1
    assert stops[0].stop_price == Decimal("61.70")
    assert stops[0].side == "sell"


def test_the_flattened_leg_protects_the_position_it_belongs_to(tmp_path: Path) -> None:
    """The whole point, end to end: with the leg visible, the position is no longer unprotected."""
    live = _client(tmp_path, {"/orders": OCO_WITH_LEG}).open_orders(OBSERVED_AT)
    held = _position("TEST.1", shares=100, entry="65.70")
    held = held.model_copy(update={
        "initial_stop": Decimal("61.70"), "current_stop": Decimal("61.70")})

    assert unprotected([held], live, "NYSE", tick_for=lambda _: None) == (), (
        "the venue is holding a stop at exactly the book's price and the position still read as "
        "naked - which is the 2026-09-04 defect"
    )
    assert unprotected([held], [o for o in live if o.order_type != "stop"], "NYSE",
                       tick_for=lambda _: None), (
        "the positive control: drop the leg and it must go back to reading naked, or this test "
        "would pass for a reason that has nothing to do with the leg"
    )


def test_a_placed_order_carries_its_side(tmp_path: Path) -> None:
    """`side` is what says an order can commit exposure at all. A buy opens; a sell closes."""
    live = _client(tmp_path, {"/orders": OCO_WITH_LEG}).open_orders(OBSERVED_AT)
    assert {o.side for o in live} == {"sell"}


# --- DR-044: a stop whose cancel is queued is not protection -----------------------------------


def test_a_queued_cancel_is_not_protection_in_force() -> None:
    """THE REGRESSION, measured 2026-09-15. Three cancels sent after the close were queued, the
    evening pass read the doomed stops as protection, and restored nothing."""
    going = _stop(status="pending_cancel")

    assert resting_stops([going]) == {}, "it is on its way out"
    assert withdrawn_stops([going]) == {"TEST.1": Decimal("45.00")}


def test_a_standing_stop_is_in_force_even_when_a_higher_one_is_being_withdrawn() -> None:
    """The withdrawn one must not win the `highest` comparison it is no longer part of."""
    orders = [_stop(order_id="going", stop_price=Decimal("46.00"), status="pending_cancel"),
              _stop(order_id="standing", stop_price=Decimal("44.00"))]
    assert resting_stops(orders) == {"TEST.1": Decimal("44.00")}


def test_withdrawn_stops_reports_the_highest_of_them() -> None:
    orders = [_stop(order_id="a", stop_price=Decimal("44.00"), status="pending_cancel"),
              _stop(order_id="b", stop_price=Decimal("46.00"), status="pending_cancel")]
    assert withdrawn_stops(orders) == {"TEST.1": Decimal("46.00")}


def test_unprotected_names_a_stop_being_withdrawn_apart_from_nothing_at_all() -> None:
    """Two different facts and two different next moves: one waits for a cancel, one places."""
    position = _position("TEST.1")
    [finding] = unprotected([position], [_stop(status="pending_cancel")], "NYSE",
                            tick_for=lambda _: None)

    assert finding.venue_stop is None, "nothing is protecting it, which is the point"
    assert "being withdrawn" in finding.reason and "cancel is queued" in finding.reason
    assert "100 shares" in finding.reason, "the shares it still holds"

    [bare] = unprotected([position], [], "NYSE", tick_for=lambda _: None)
    assert "nothing is resting" in bare.reason and "withdrawn" not in bare.reason


def test_own_stop_will_not_raise_a_stop_that_is_going_away() -> None:
    """`DR-043` amends an order; an order the venue is already retiring is not one to amend."""
    found = own_stop("TEST.1", [_stop(status="pending_cancel")], SENT)
    assert isinstance(found, str)
    assert "cancel queued" in found and "DR-037" in found


def test_the_highest_standing_trigger_is_the_one_in_force() -> None:
    """The higher stop fires first, so a lower one behind it changes nothing about the loss - and
    the answer must not depend on which order the venue happened to list first."""
    orders = [_stop(order_id="low", stop_price=Decimal("44.00")),
              _stop(order_id="high", stop_price=Decimal("46.00"))]

    assert resting_stops(orders) == {"TEST.1": Decimal("46.00")}
    assert resting_stops(list(reversed(orders))) == {"TEST.1": Decimal("46.00")}
