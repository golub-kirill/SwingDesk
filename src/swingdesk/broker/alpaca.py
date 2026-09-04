"""Alpaca paper-trading adapter. READ ONLY, and the read-only part is structural.

`ADR-0005` chose the venue; `DR-026` records where the owner put the order-placing boundary on
2026-08-31 and what is still closed. What matters in this file is what it does NOT contain:

  - **No write verb.** There is no POST, no DELETE, no PATCH and no PUT anywhere in this package,
    and gate 39 reads the syntax tree to keep it that way. `policy.check_method` refuses anything
    the committed policy does not list, which today is everything but `GET`.
  - **No host.** Every URL comes from `registry/broker_policy.yml`, whose allowlist carries exactly
    one entry. `APCA_API_BASE_URL` - Alpaca's own environment override - is deliberately not read.

**Why the host is the whole safety boundary.** Measured against Alpaca's API reference 2026-08-31:
the account object has no field saying whether the account is paper or live. `id`, `status`,
`currency`, `equity`, `trading_blocked` and the rest are identical in both, so there is nothing in
a response this software could check. The only difference between play money and the owner's is
which host was called, which is why that value lives in a gated file and not in this one.

**The venue's output is untrusted input** (`SECURITY.md` 6), the same treatment `vendor_yahoo`
gives Yahoo. Every number arrives as a JSON string and is parsed to `Decimal` at the boundary;
a field that is missing, empty or unparseable raises rather than defaulting to zero.

**Fetching is fail-open, deciding is fail-closed.** A venue that cannot be reached raises
`BrokerUnavailable` and the caller reports it; nothing here degrades to a guess. Those are
different layers and conflating them is how "fail-open everywhere" quietly becomes "reconciled
against a book we could not read".
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
from typing import Any, Protocol

from swingdesk.broker.armed import STOPPED, Arming
from swingdesk.broker.policy import BrokerPolicy
from swingdesk.contracts.broker import (
    BrokerAccount,
    BrokerFill,
    BrokerPosition,
    EntryOrder,
    FillKind,
    PlacedOrder,
    PositionSide,
    ProtectiveOrder,
    Side,
)

#: How many characters of the account-number digest identify the account. Twelve hex characters is
#: 48 bits - far beyond collision for one owner's handful of accounts, and not reversible.
FINGERPRINT_LENGTH = 12


class BrokerUnavailable(Exception):
    """The venue could not be reached, or answered with something unusable.

    Fail-open at this layer: the caller reports the gap and refuses to reconcile, exactly as
    `market_data.VendorUnavailable` works for bars. It is NOT `PolicyRefused` - a venue that is
    down is a fact about the world, a policy that would permit a live host is a fact about this
    repository, and one `except` catching both would hide the second behind the first.
    """


class CredentialsMissing(Exception):
    """The environment does not carry the keys the policy names.

    Distinct from `BrokerUnavailable` because the remedy is different and belongs to the owner:
    `SECURITY.md` 2.1 puts secrets in environment variables or an OS keyring and never in this
    repository, so this software cannot fix it and must not pretend the venue is at fault.
    """


class SubmissionStopped(Exception):
    """A guard refused to submit. NOT a venue problem, and never handled with `BrokerUnavailable`.

    `DR-027` 4's four guards all raise this. The distinction matters at the point somebody reads a
    log at 18:31: `BrokerUnavailable` sends them to the network, and this sends them to the switch
    file or to the policy, which is where the answer actually is.
    """


class Transport(Protocol):
    """One HTTP round trip. Injected so every test runs against a recorded response.

    `CI_POLICY.md` 4 forbids the suite touching the network. A transport parameter is how that is
    obeyed without the tests exercising a different code path than production does.
    """

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        timeout_seconds: int,
        max_bytes: int,
        body: bytes | None = None,
    ) -> tuple[int, bytes]:
        ...


@dataclass(frozen=True, slots=True)
class Credentials:
    """The venue's key pair, read from the environment and never written anywhere.

    `__repr__` is overridden rather than trusted: a dataclass prints its fields, and this object
    will eventually end up inside an exception, a log line or a debugger frame.
    """

    key_id: str
    secret: str

    def __repr__(self) -> str:
        return "Credentials(key_id=<redacted>, secret=<redacted>)"

    def headers(self, user_agent: str) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.key_id,
            "APCA-API-SECRET-KEY": self.secret,
            "User-Agent": user_agent,
            "Accept": "application/json",
        }


def credentials_from_env(policy: BrokerPolicy) -> Credentials:
    """Read the key pair the policy names, or refuse.

    The variable NAMES come from the committed policy; the values never touch the repository.
    """
    key_id = os.environ.get(policy.key_env, "").strip()
    secret = os.environ.get(policy.secret_env, "").strip()
    missing = [name for name, value in ((policy.key_env, key_id), (policy.secret_env, secret))
               if not value]
    if missing:
        raise CredentialsMissing(
            f"{', '.join(missing)} not set. {policy.label} keys are issued per account and paper "
            f"keys are distinct from live ones; set them in the environment, never in a file in "
            f"this repository (SECURITY 2.1 - this repository is public)."
        )
    return Credentials(key_id=key_id, secret=secret)


def urllib_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
    max_bytes: int,
    body: bytes | None = None,
) -> tuple[int, bytes]:
    """The real round trip. The only place in this package that opens a socket.

    The byte cap is applied to what is actually READ and not only to `Content-Length`, so a server
    that omits or misstates the header cannot bypass it - the same rule `fetch_directory.py`
    follows under `DR-008`.
    """
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            declared = response.headers.get("Content-Length")
            if declared is not None and declared.isdigit() and int(declared) > max_bytes:
                raise BrokerUnavailable(
                    f"response declares {declared} bytes, over the policy cap of {max_bytes}"
                )
            received = response.read(max_bytes + 1)
            if len(received) > max_bytes:
                raise BrokerUnavailable(f"response exceeded the policy cap of {max_bytes} bytes")
            status = int(response.status)
    except urllib.error.HTTPError as error:
        # The body of an error response can carry the venue's own explanation and is worth having;
        # the REQUEST headers carry the secret and are never touched here.
        received = error.read(max_bytes + 1)[:max_bytes]
        status = int(error.code)
    except urllib.error.URLError as error:
        raise BrokerUnavailable(f"{url}: {error.reason}") from error
    except TimeoutError as error:
        raise BrokerUnavailable(f"{url}: timed out after {timeout_seconds}s") from error
    return status, received


@dataclass(frozen=True, slots=True)
class AlpacaClient:
    """A read-only view of one paper account.

    `observed_at` is supplied by the caller on every method rather than read from a clock, the way
    `vendor_yahoo.fetch` takes `knowledge_time`: a fetch is then reproducible in a test, and the
    record says when we CLAIM we learned something rather than when a machine happened to run.
    """

    policy: BrokerPolicy
    credentials: Credentials
    transport: Transport = urllib_transport

    arming: Arming = STOPPED
    """Whether submission is armed. **Defaults to stopped, and that default is the guard.**

    A client constructed without an explicit arming decision cannot write. That makes the safe
    state the one you get by forgetting, which is the only kind of safe default worth having -
    `DR-027` 4.2, and `DR-025` 2.1 for what the opposite polarity costs here.
    """

    def _get(self, endpoint: str, query: dict[str, str] | None = None, **path: str) -> Any:
        self.policy.check_method("GET")
        url = self.policy.url(endpoint, **path)
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"

        limits = self.policy.limits
        status, body = self.transport(
            "GET",
            url,
            self.credentials.headers(self.policy.user_agent),
            limits.request_timeout_seconds,
            limits.max_response_bytes,
        )

        return self._decode(endpoint, status, body)

    def _decode(self, endpoint: str, status: int, body: bytes) -> Any:
        """One status and decoding rule for reads and writes alike.

        Shared deliberately: a write path with its own idea of what `401` means is a second rule
        that agrees today, which is how every drift in this repository has looked on the day it was
        written.
        """
        if status in (401, 403):
            raise BrokerUnavailable(
                f"{self.policy.label} refused the credentials in {self.policy.key_env} / "
                f"{self.policy.secret_env} (HTTP {status}). Paper keys are distinct from live keys."
            )
        # 200 for a read, 200 on a submission accepted by Alpaca. A 422 carries the venue's reason
        # for rejecting an order - a duplicate `client_order_id` among them - and that text is the
        # most useful thing in the whole exchange, so it travels rather than being flattened.
        if status not in (200, 201):
            raise BrokerUnavailable(
                f"{endpoint}: HTTP {status} from {self.policy.label}: "
                f"{body[:400].decode('utf-8', errors='replace')}"
            )

        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise BrokerUnavailable(f"{endpoint}: response was not JSON: {error}") from error

    def guards(self) -> None:
        """`DR-027` 4's guards, in order, and BEFORE anything an order is built out of.

        Called from `submit` as well as from `_write` so that a refusal happens before a payload
        exists. A guard that runs after the work is a guard whose failure mode is "we nearly did
        it", and the ordering is asserted by `test_submit.py` rather than left to reading.

        The arming check is first on purpose. A refusal that reported *the venue is unreachable*
        when the truth is *the owner never armed it* sends somebody to debug a network at 18:31.
        """
        if self.arming.stopped:
            raise SubmissionStopped(self.arming.reason)

        if not self.policy.write_enabled or self.policy.write is None:
            raise SubmissionStopped(
                "the committed policy sets access.write_enabled false, so it carries no write "
                "section and nothing may be submitted"
            )

    def _write(self, endpoint: str, payload: dict[str, Any]) -> Any:
        """The ONLY place in this package that sends anything but a GET.

        `DR-027` 4 lists four guards and three of them are consulted here, in order, before a socket
        is opened. The fourth is this function's own existence: gate 39 asserts that
        `self.transport` is called from exactly two places, so a second write path cannot be added
        without the build noticing.

        **No verb is spelled here.** `policy.write_method` reads it from the committed file, so a
        policy narrowed back to `GET` leaves this function with nothing to send rather than with a
        literal it ignores - and gate 39's rule about write verbs stays absolute.
        """
        self.guards()
        method = self.policy.write_method
        self.policy.check_method(method)
        url = self.policy.url(endpoint)

        limits = self.policy.limits
        headers = self.credentials.headers(self.policy.user_agent)
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, sort_keys=True).encode("utf-8")

        status, received = self.transport(
            method, url, headers, limits.request_timeout_seconds, limits.max_response_bytes, body,
        )
        return self._decode(endpoint, status, received)

    def submit(self, order: EntryOrder, observed_at: datetime) -> PlacedOrder:
        """Send one entry as a bracket, and return what the venue said about it.

        The shape is `DR-027` 3: a limit at the sizing price, a stop-loss leg at the sized stop,
        `day`, whole shares. Every one of those values comes from the order or from the policy;
        nothing about the order is decided here.
        """
        self.guards()
        write = self.policy.write
        assert write is not None  # `guards` refuses when it is, and mypy cannot see that

        payload: dict[str, Any] = {
            "symbol": order.symbol,
            "qty": str(order.shares),
            "side": write.side,
            "type": write.order_type,
            "time_in_force": write.time_in_force,
            "limit_price": str(order.limit_price),
            "order_class": write.order_class,
            "stop_loss": {"stop_price": str(order.stop_price)},
            # A bracket is a chain of THREE and the venue refuses one with a leg missing -
            # measured, not read: the first real order came back "bracket orders require
            # take_profit.limit_price". `DR-027` 9.
            "take_profit": {"limit_price": str(order.target_price)},
            "client_order_id": order.client_order_id,
        }
        answered = self._write("orders", payload)
        if not isinstance(answered, dict):
            raise BrokerUnavailable("orders: expected an object")

        return PlacedOrder(
            order_id=_text(answered, "id", "orders"),
            client_order_id=_text(answered, "client_order_id", "orders"),
            symbol=_text(answered, "symbol", "orders"),
            status=str(answered.get("status", "")),
            submitted_at=_instant(answered, "submitted_at", "orders"),
            filled_shares=_optional_decimal(answered, "filled_qty", "orders") or Decimal(0),
            observed_at=observed_at,
        )

    def protect(self, order: ProtectiveOrder, observed_at: datetime) -> PlacedOrder:
        """Place one `oco` against a position already held, and return what the venue said.

        **The same chokepoint, deliberately.** This goes through `_write` like every other write in
        this package, so `DR-027` §4's three guards are consulted before a socket opens and gate 39
        still sees exactly two call sites reaching the transport. A second write METHOD is not a
        second write PATH.

        **It is an order shape `DR-027` §2 did not permit**, and `DR-037` is the record that adds
        it. The distinction that made it addable: §2 excludes *management actions on open
        positions* because `D6` governs stop MOVES and partial exits. This moves nothing. It
        restores the protection this system already decided on and already sent, which the venue
        retired for a mechanical reason - `DR-036` measured all three of them gone at the first
        close.
        """
        self.guards()
        write = self.policy.write
        assert write is not None  # `guards` refuses when it is, and mypy cannot see that

        payload: dict[str, Any] = {
            "symbol": order.symbol,
            "qty": str(order.shares),
            "side": write.protect_side,
            # **The venue settled this by refusing, on 2026-09-03.** The first three protective
            # orders went out without a `type` at all - the comment here reasoned that an `oco` IS
            # its two legs and therefore needs no type of its own - and all three came back
            # `422 {"code":40010001,"message":"invalid order type"}`. AIS, BTSG and DINO spent that
            # night unprotected because of it.
            #
            # The evidence that settles it is this system's own accepted order, not a document:
            # `submit` above sends `type` ALONGSIDE `order_class: bracket` and the same nested
            # `stop_loss`/`take_profit` legs, and the venue takes it. `order_class` says how the
            # legs relate; `type` is still the parent order's own shape. `DR-027` 9 records the
            # entry's class being settled the same way, by a refusal.
            "type": write.protect_order_type,
            "order_class": write.protect_order_class,
            "time_in_force": write.protect_time_in_force,
            "stop_loss": {"stop_price": str(order.stop_price)},
            "take_profit": {"limit_price": str(order.target_price)},
            "client_order_id": order.client_order_id,
        }
        answered = self._write("orders", payload)
        if not isinstance(answered, dict):
            raise BrokerUnavailable("orders: expected an object")

        return PlacedOrder(
            order_id=_text(answered, "id", "orders"),
            client_order_id=_text(answered, "client_order_id", "orders"),
            symbol=_text(answered, "symbol", "orders"),
            status=str(answered.get("status", "")),
            submitted_at=_instant(answered, "submitted_at", "orders"),
            filled_shares=_optional_decimal(answered, "filled_qty", "orders") or Decimal(0),
            order_type=str(answered.get("order_type") or answered.get("type") or ""),
            stop_price=_optional_decimal(answered, "stop_price", "orders"),
            observed_at=observed_at,
        )

    def account(self, observed_at: datetime) -> BrokerAccount:
        """The account as the venue describes it.

        The account NUMBER is digested here and discarded; nothing downstream ever sees it
        (`SECURITY.md` 2.4, and `contracts.broker.BrokerAccount` explains the choice).
        """
        payload = self._get("account")
        if not isinstance(payload, dict):
            raise BrokerUnavailable("account: expected an object")

        number = str(payload.get("account_number") or payload.get("id") or "")
        if not number:
            raise BrokerUnavailable("account: the venue named no account")

        return BrokerAccount(
            venue=self.policy.venue,
            base_url=self.policy.base_url,
            fingerprint=sha256(number.encode("utf-8")).hexdigest()[:FINGERPRINT_LENGTH],
            status=str(payload.get("status", "")),
            currency=str(payload.get("currency", "")),
            cash=_decimal(payload, "cash", "account"),
            equity=_decimal(payload, "equity", "account"),
            buying_power=_decimal(payload, "buying_power", "account"),
            trading_blocked=bool(payload.get("trading_blocked", False)),
            account_blocked=bool(payload.get("account_blocked", False)),
            observed_at=observed_at,
        )

    def open_orders(self, observed_at: datetime) -> tuple[PlacedOrder, ...]:
        """Every order the venue still considers live, in symbol order. A GET, and only a GET.

        **An unfilled order is committed exposure and a position is not the whole story.** A
        bracket resting overnight will fill or will not, and until the venue says which, the name
        is spoken for - so a cap that counted only filled positions would let the same name be
        entered twice on consecutive evenings. `DR-027` §11.

        `status=open` is the venue's own filter, applied at the server rather than here: asking for
        every order this account ever had and discarding most of them locally would walk the page
        bound for an answer the endpoint can give directly.
        """
        payload = self._get("orders", query={"status": "open", "direction": "asc"})
        if not isinstance(payload, list):
            raise BrokerUnavailable("orders: expected an array")

        live = [self._order(row, observed_at) for row in payload]
        # Sorted here rather than trusted from the wire, exactly as `positions` is: a vendor is
        # free to change its ordering between calls and `DETERMINISM_SPEC` is not.
        return tuple(sorted(live, key=lambda order: (order.symbol, order.order_id)))

    def _order(self, row: Any, observed_at: datetime) -> PlacedOrder:
        if not isinstance(row, dict):
            raise BrokerUnavailable("orders: expected an array of objects")
        return PlacedOrder(
            order_id=_text(row, "id", "orders"),
            # An order this system did not place carries whatever id the venue assigned, and an
            # order placed by hand in the dashboard may carry none at all. Both are still exposure,
            # so this reads rather than requires - unlike `submit`, where a missing echo would mean
            # our own id did not land.
            client_order_id=str(row.get("client_order_id") or ""),
            symbol=_text(row, "symbol", "orders"),
            status=str(row.get("status", "")),
            submitted_at=_instant(row, "submitted_at", "orders"),
            filled_shares=_optional_decimal(row, "filled_qty", "orders") or Decimal(0),
            # `DR-036`. A resting order's TYPE and trigger are what say whether it protects
            # anything, and until this was read nothing in this system could tell a live stop from
            # a live target - or from no protection at all.
            order_type=str(row.get("order_type") or row.get("type") or ""),
            stop_price=_optional_decimal(row, "stop_price", "orders"),
            observed_at=observed_at,
        )

    def positions(self, observed_at: datetime) -> tuple[BrokerPosition, ...]:
        """Every position the venue says is open, in symbol order.

        Sorted here rather than trusted from the wire: `DETERMINISM_SPEC` requires a run to be
        reproducible, and a vendor is free to change its ordering between calls.
        """
        payload = self._get("positions")
        if not isinstance(payload, list):
            raise BrokerUnavailable("positions: expected an array")

        held = [self._position(row, observed_at) for row in payload]
        return tuple(sorted(held, key=lambda position: position.symbol))

    def _position(self, row: Any, observed_at: datetime) -> BrokerPosition:
        if not isinstance(row, dict):
            raise BrokerUnavailable("positions: expected an array of objects")
        return BrokerPosition(
            symbol=_text(row, "symbol", "positions"),
            asset_class=str(row.get("asset_class", "")),
            exchange=str(row.get("exchange", "")),
            side=_enum(PositionSide, row, "side", "positions"),
            shares=_decimal(row, "qty", "positions"),
            average_entry_price=_decimal(row, "avg_entry_price", "positions"),
            current_price=_optional_decimal(row, "current_price", "positions"),
            market_value=_optional_decimal(row, "market_value", "positions"),
            cost_basis=_optional_decimal(row, "cost_basis", "positions"),
            unrealized_pl=_optional_decimal(row, "unrealized_pl", "positions"),
            observed_at=observed_at,
        )

    def fills(self, observed_at: datetime, after: datetime | None = None) -> tuple[BrokerFill, ...]:
        """Every execution the venue reports, oldest first, walking its pages.

        The page walk is bounded by `limits.max_pages`. A paged endpoint followed until the server
        stops issuing tokens is the "unlimited retry inside one command" failure `DR-008` names
        wearing a different hat, so exhausting the bound raises rather than returning a partial
        answer that looks complete.
        """
        limits = self.policy.limits
        collected: list[BrokerFill] = []
        page_token: str | None = None

        for _ in range(limits.max_pages):
            query = {
                "page_size": str(limits.page_size),
                "direction": "asc",
            }
            if after is not None:
                query["after"] = after.isoformat()
            if page_token is not None:
                query["page_token"] = page_token

            payload = self._get(
                "activities", query=query, activity_type=self.policy.activity_type
            )
            if not isinstance(payload, list):
                raise BrokerUnavailable("activities: expected an array")
            if not payload:
                return tuple(collected)

            for row in payload:
                collected.append(self._fill(row, observed_at))
            page_token = collected[-1].activity_id

            if len(payload) < limits.page_size:
                return tuple(collected)

        raise BrokerUnavailable(
            f"activities: still paging after {limits.max_pages} pages. Narrow the window with "
            f"--since rather than raising the bound, or the ceiling stops meaning anything."
        )

    def _fill(self, row: Any, observed_at: datetime) -> BrokerFill:
        if not isinstance(row, dict):
            raise BrokerUnavailable("activities: expected an array of objects")
        return BrokerFill(
            activity_id=_text(row, "id", "activities"),
            order_id=_text(row, "order_id", "activities"),
            symbol=_text(row, "symbol", "activities"),
            side=_enum(Side, row, "side", "activities"),
            kind=_enum(FillKind, row, "type", "activities"),
            transaction_time=_instant(row, "transaction_time", "activities"),
            price=_decimal(row, "price", "activities"),
            shares=_decimal(row, "qty", "activities"),
            cumulative_shares=_optional_decimal(row, "cum_qty", "activities"),
            remaining_shares=_optional_decimal(row, "leaves_qty", "activities"),
            order_status=str(row["order_status"]) if row.get("order_status") else None,
            observed_at=observed_at,
        )


def open_client(
    policy: BrokerPolicy | None = None,
    transport: Transport = urllib_transport,
    arming: Arming = STOPPED,
) -> AlpacaClient:
    """The one construction path: load the committed policy, then read the environment.

    In that order deliberately. A malformed policy must refuse before this process reads a secret,
    so a `PolicyRefused` never arrives with credentials already in memory.

    `arming` defaults to STOPPED. A caller that wants to submit has to have gone and read the
    switch, which is the point: the reading is an act, not an assumption.
    """
    from swingdesk.broker import policy as policy_module

    resolved = policy or policy_module.load()
    return AlpacaClient(
        policy=resolved,
        credentials=credentials_from_env(resolved),
        transport=transport,
        arming=arming,
    )


def _text(row: dict[str, Any], key: str, where: str) -> str:
    value = row.get(key)
    if value is None or str(value) == "":
        raise BrokerUnavailable(f"{where}: {key} is missing")
    return str(value)


def _decimal(row: dict[str, Any], key: str, where: str) -> Decimal:
    """Parse a venue string to `Decimal`, or refuse. Never a default, never a float.

    A missing money field that defaulted to zero would read downstream as a real balance of zero,
    which is a number this system would then reconcile against.
    """
    raw = row.get(key)
    if raw is None or str(raw).strip() == "":
        raise BrokerUnavailable(f"{where}: {key} is missing")
    try:
        return Decimal(str(raw))
    except InvalidOperation as error:
        raise BrokerUnavailable(f"{where}: {key} is {raw!r}, not a number") from error


def _optional_decimal(row: dict[str, Any], key: str, where: str) -> Decimal | None:
    """As `_decimal`, but a field the venue may legitimately omit. Absent is `None`, never zero."""
    if row.get(key) is None or str(row.get(key)).strip() == "":
        return None
    return _decimal(row, key, where)


def _enum[E: StrEnum](kind: type[E], row: dict[str, Any], key: str, where: str) -> E:
    raw = _text(row, key, where)
    try:
        return kind(raw)
    except ValueError as error:
        raise BrokerUnavailable(
            f"{where}: {key} is {raw!r}, which is not one of "
            f"{', '.join(member.value for member in kind)}"
        ) from error


def _instant(row: dict[str, Any], key: str, where: str) -> datetime:
    """Parse an ISO instant and refuse a naive one.

    A naive timestamp from a venue is not a small problem: every store in this system is
    `TIMESTAMPTZ` and a naive value would be read back in whatever zone the reader happened to
    have, which is the `CALENDAR_SPEC` 6 failure that puts a bar in the wrong session.
    """
    raw = _text(row, key, where)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise BrokerUnavailable(f"{where}: {key} is {raw!r}, not an ISO instant") from error
    if parsed.tzinfo is None:
        raise BrokerUnavailable(f"{where}: {key} is {raw!r}, which carries no timezone")
    return parsed

