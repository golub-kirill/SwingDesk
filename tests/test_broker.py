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
from swingdesk.broker.reconcile import reconcile, unrecorded_fills
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
    loaded = policy_module.load()
    assert loaded.allowed_methods == {"GET"}
    assert loaded.write_enabled is False
    assert loaded.base_url.startswith("https://")


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


def test_policy_refuses_a_write_verb(tmp_path: Path) -> None:
    """D1/BR-1 as an executable rule: a policy listing a write verb does not load."""
    with pytest.raises(PolicyRefused, match="read-only"):
        _policy(tmp_path, access__allowed_methods=["GET", "POST"])


def test_policy_refuses_write_enabled(tmp_path: Path) -> None:
    with pytest.raises(PolicyRefused, match="DR-026"):
        _policy(tmp_path, access__write_enabled=True)


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


def test_check_method_refuses_anything_but_get() -> None:
    loaded = policy_module.load()
    loaded.check_method("GET")
    for verb in ("POST", "PUT", "PATCH", "DELETE"):
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
