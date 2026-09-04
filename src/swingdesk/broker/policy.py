"""Reading `registry/broker_policy.yml`, and refusing when it does not say what it must.

The adapter holds no URL, no timeout and no byte cap of its own. Everything it is permitted to ask
of the venue comes from here, for the reason `DR-008` gives about the directory collector and gate
22 enforces: a limit in a literal is changed by editing a line, a limit in a committed policy is
changed by a commit a reviewer sees.

**This module is where the paper/live boundary is actually enforced.** Alpaca's account object
carries no field saying which kind of account answered - measured against its API reference
2026-08-31 - so the host is the only thing that distinguishes play money from the owner's. A base
URL that is not on the allowlist is refused here, before a socket is opened.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

POLICY_PATH = Path(__file__).resolve().parents[3] / "registry" / "broker_policy.yml"

#: Verbs this package refuses to be given, whatever the policy says. **The only place in
#: `swingdesk/broker/` where an HTTP write verb is spelled at all**, and gate 39 permits it here by
#: name because a denylist is not a capability: nothing sends these, `load` refuses a policy that
#: names one, and the verb that IS used comes from `BrokerPolicy.write_method`, read from the file.
#:
#: `DR-027` 3.3 is why cancellation is on the list rather than merely unused: every order carries
#: `time_in_force: day`, so nothing this system placed outlives the session that decided it and
#: there is nothing to cancel.
REFUSED_METHODS = frozenset({"DELETE", "PATCH", "PUT"})


class PolicyRefused(Exception):
    """The policy is missing, malformed, or permits something it must not.

    Fail-closed, and deliberately not the same exception as `BrokerUnavailable`. A venue that did
    not answer is a fact about the world; a policy that would let this software reach a live
    brokerage is a fact about this repository, and the two must never be handled by one `except`.
    """


@dataclass(frozen=True, slots=True)
class Limits:
    max_response_bytes: int
    request_timeout_seconds: int
    max_retries_per_attempt: int
    retry_after_seconds: int
    page_size: int
    max_pages: int


@dataclass(frozen=True, slots=True)
class WritePolicy:
    """What a submission may look like, and the file that has to exist before one happens.

    Every field is a definition argued in `DR-027` rather than a threshold, which is why none of
    them is in `registry/parameters.yml`. The limit price is the one that looks like a number and
    is not: it is the sizing price itself, so no value is introduced.
    """

    kill_switch_file: str
    armed_marker: str
    client_order_id_prefix: str
    max_client_order_id_length: int
    order_type: str
    time_in_force: str
    order_class: str
    side: str

    tick_size: Decimal
    """The price increment the venue accepts at or above `sub_dollar_threshold`. Its own rule, not
    ours - SEC Rule 612, enforced by the venue and discovered by it rejecting four orders."""

    sub_dollar_tick: Decimal
    sub_dollar_threshold: Decimal

    protect_time_in_force: str
    """`gtc` (`DR-037`). The entry keeps `day` because an order outliving its session outlives the
    analysis that produced it; a PROTECTION has to outlive the session because the position does."""

    protect_order_class: str

    protect_order_type: str
    """`limit` (`DR-037`, amended 2026-09-03 after the venue refused the order without it).

    Not a threshold and not a price: `oco`'s take-profit leg IS a limit order, and this names the
    parent's shape. The prices are the book's own stop and the target `exit.target_r_multiple`
    implies, both carried in the legs below."""

    protect_side: str
    protect_client_order_id_prefix: str

    def tick_for(self, price: Decimal) -> Decimal:
        """The increment this price must be a multiple of."""
        return self.tick_size if price >= self.sub_dollar_threshold else self.sub_dollar_tick


@dataclass(frozen=True, slots=True)
class BrokerPolicy:
    """Everything the adapter is allowed to do, loaded from the committed file."""

    venue: str
    label: str
    user_agent: str
    market: str
    base_url: str
    forbidden_hosts: tuple[str, ...]
    allowed_methods: frozenset[str]
    write_enabled: bool
    key_env: str
    secret_env: str
    limits: Limits
    endpoints: dict[str, str]
    activity_type: str
    write: WritePolicy | None

    def url(self, endpoint: str, **path: str) -> str:
        """An absolute URL for a named endpoint, and the only way to build one.

        The host is never a parameter. A caller supplies the endpoint NAME, so a path that
        somebody edits into the policy still cannot reach a host the allowlist does not carry.
        """
        try:
            path_template = self.endpoints[endpoint]
        except KeyError:
            raise PolicyRefused(
                f"no endpoint {endpoint!r} in {POLICY_PATH.name}; "
                f"known: {', '.join(sorted(self.endpoints))}"
            ) from None
        return self.base_url + path_template.format(**path)

    @property
    def write_method(self) -> str:
        """The one verb this policy permits for a submission, read from the committed file.

        **Nothing in `swingdesk/broker/` spells a write verb, and that is the point.** Gate 39 can
        therefore keep an ABSOLUTE rule - no `POST`, `PUT`, `PATCH` or `DELETE` literal anywhere in
        the package - even though the package can now write. The verb exists in exactly one place,
        `registry/broker_policy.yml`, which is `DR-027` 4.3's guard; a policy narrowed back to
        `GET` leaves the code with no verb to use rather than with a literal to ignore.
        """
        verbs = sorted(self.allowed_methods - {"GET"})
        if len(verbs) != 1:
            raise PolicyRefused(
                f"{POLICY_PATH.name} permits {sorted(self.allowed_methods)}; a submission needs "
                f"exactly one non-GET verb and this policy names {len(verbs)}."
            )
        return verbs[0]

    def check_method(self, method: str) -> None:
        """Refuse anything the policy does not list. Today that is everything but `GET`."""
        if method not in self.allowed_methods:
            raise PolicyRefused(
                f"{method} is not permitted by {POLICY_PATH.name} "
                f"(allowed: {', '.join(sorted(self.allowed_methods))}). "
                f"Placing, amending or cancelling an order is D1/BR-1 and needs a decision record, "
                f"not an argument."
            )


def _decimal(section: dict[str, Any], key: str, where: str) -> Decimal:
    """A price increment, parsed exactly. Quoted in the YAML so no float ever touches it.

    A tick read through a float is a tick that is almost right, and `0.01` is famously not
    representable - the one place in this file where the parsing rule is load-bearing.
    """
    raw = section.get(key)
    if raw is None:
        raise PolicyRefused(f"{POLICY_PATH.name}: {where}.{key} is missing")
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise PolicyRefused(
            f"{POLICY_PATH.name}: {where}.{key} is {raw!r}, which is not a number"
        ) from None
    if value <= 0:
        raise PolicyRefused(f"{POLICY_PATH.name}: {where}.{key} is {value}; a tick is positive")
    return value


def _require(section: dict[str, Any], key: str, kind: type, where: str) -> Any:
    if key not in section:
        raise PolicyRefused(f"{POLICY_PATH.name}: {where}.{key} is missing")
    value = section[key]
    if not isinstance(value, kind) or (kind is not bool and isinstance(value, bool)):
        raise PolicyRefused(
            f"{POLICY_PATH.name}: {where}.{key} is {type(value).__name__}, expected {kind.__name__}"
        )
    return value


def load(path: Path | None = None) -> BrokerPolicy:
    """Load and validate the committed policy.

    Every refusal here names the key, because a policy that is wrong in a way nobody can locate is
    the same cost as no policy at all.
    """
    source = path or POLICY_PATH
    if not source.exists():
        raise PolicyRefused(f"{source} does not exist; the broker adapter has no permitted limits")

    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise PolicyRefused(f"{source.name} did not parse to a mapping")

    venue = raw.get("venue")
    access = raw.get("access")
    limits = raw.get("limits")
    endpoints = raw.get("endpoints")
    for name, section in (("venue", venue), ("access", access),
                          ("limits", limits), ("endpoints", endpoints)):
        if not isinstance(section, dict):
            raise PolicyRefused(f"{source.name}: section {name!r} is missing or not a mapping")
    assert isinstance(venue, dict) and isinstance(access, dict)
    assert isinstance(limits, dict) and isinstance(endpoints, dict)

    allowlist = venue.get("base_url_allowlist")
    if not isinstance(allowlist, list) or not allowlist:
        raise PolicyRefused(f"{source.name}: venue.base_url_allowlist is missing or empty")
    if len(allowlist) != 1:
        # Not pedantry. One entry means one host can be reached and a reviewer can see which;
        # a second entry is exactly the change this file exists to make visible, and it arrives
        # with a decision record or it does not arrive.
        raise PolicyRefused(
            f"{source.name}: venue.base_url_allowlist carries {len(allowlist)} entries. "
            f"Exactly one host may be reachable, and widening it is a decision record."
        )

    base_url = str(allowlist[0]).rstrip("/")
    if not base_url.startswith("https://"):
        raise PolicyRefused(f"{source.name}: {base_url} is not https")

    forbidden = tuple(str(host) for host in venue.get("forbidden_hosts") or ())
    # Compared as HOSTNAMES, never as substrings. `paper-api.alpaca.markets` CONTAINS
    # `api.alpaca.markets`, so a substring test refuses the paper host - and it would ADMIT
    # `paper-api.alpaca.markets.example.com`, which is somebody else's server. Gate 39's first run
    # found the first half; the second half is why the fix is an equality and not a `startswith`.
    reachable = (urlparse(base_url).hostname or "").lower()
    if not reachable:
        raise PolicyRefused(f"{source.name}: {base_url} names no host")
    for host in forbidden:
        if reachable == str(host).strip().lower():
            raise PolicyRefused(
                f"{source.name}: the allowlisted URL resolves to {reachable}, which is listed "
                f"under forbidden_hosts. That is the live venue, and DR-014 rules no owner capital "
                f"is involved."
            )

    write_enabled = _require(access, "write_enabled", bool, "access")
    methods = access.get("allowed_methods")
    if not isinstance(methods, list) or not methods:
        raise PolicyRefused(f"{source.name}: access.allowed_methods is missing or empty")
    allowed = frozenset(str(method).upper() for method in methods)
    if "GET" not in allowed:
        raise PolicyRefused(f"{source.name}: access.allowed_methods must permit GET")
    if not write_enabled and allowed != {"GET"}:
        raise PolicyRefused(
            f"{source.name}: access.write_enabled is false but allowed_methods is "
            f"{sorted(allowed)}. A read-only policy that permits a write verb is not read-only."
        )

    if write_enabled and allowed == {"GET"}:
        # The mirror of the check above, and it was missing until a test asked for it. A policy
        # that grants writing while naming no verb to write with loads happily and then refuses
        # every submission from inside `write_method` - a capability that exists in one half of the
        # file and not the other, which is the one-logic-in-two-places failure gate 39's own
        # message names.
        raise PolicyRefused(
            f"{source.name}: access.write_enabled is true but allowed_methods names no verb to "
            f"submit with. A permission that cannot be exercised is a claim, not a capability."
        )

    refused = sorted(allowed & REFUSED_METHODS)
    if refused:
        raise PolicyRefused(
            f"{source.name}: access.allowed_methods permits {', '.join(refused)}. DR-027 covers "
            f"submission only; amending or cancelling an order is a decision record of its own."
        )

    write_block = raw.get("write")
    write: WritePolicy | None = None
    if write_enabled:
        if not isinstance(write_block, dict):
            raise PolicyRefused(
                f"{source.name}: access.write_enabled is true and there is no `write` section. "
                f"A permission with no kill switch behind it is not a permission this project "
                f"grants (DR-027 4.2)."
            )
        write = WritePolicy(
            kill_switch_file=str(_require(write_block, "kill_switch_file", str, "write")),
            armed_marker=str(_require(write_block, "armed_marker", str, "write")),
            client_order_id_prefix=str(
                _require(write_block, "client_order_id_prefix", str, "write")
            ),
            max_client_order_id_length=int(
                _require(write_block, "max_client_order_id_length", int, "write")
            ),
            order_type=str(_require(write_block, "order_type", str, "write")),
            time_in_force=str(_require(write_block, "time_in_force", str, "write")),
            order_class=str(_require(write_block, "order_class", str, "write")),
            side=str(_require(write_block, "side", str, "write")),
            tick_size=_decimal(write_block, "tick_size", "write"),
            sub_dollar_tick=_decimal(write_block, "sub_dollar_tick", "write"),
            sub_dollar_threshold=_decimal(write_block, "sub_dollar_threshold", "write"),
            protect_time_in_force=str(
                _require(write_block, "protect_time_in_force", str, "write")
            ),
            protect_order_class=str(_require(write_block, "protect_order_class", str, "write")),
            protect_order_type=str(_require(write_block, "protect_order_type", str, "write")),
            protect_side=str(_require(write_block, "protect_side", str, "write")),
            protect_client_order_id_prefix=str(
                _require(write_block, "protect_client_order_id_prefix", str, "write")
            ),
        )
        if not write.armed_marker.strip():
            # An empty marker arms on any file at all, including one created by a stray redirect.
            raise PolicyRefused(f"{source.name}: write.armed_marker is blank, so anything arms it")
        if "/" in write.kill_switch_file or "\\" in write.kill_switch_file:
            # A name, resolved against the data directory by the caller. A path here could point
            # inside the repository, and a switch that ships in a commit is a release.
            raise PolicyRefused(
                f"{source.name}: write.kill_switch_file must be a bare filename, not a path"
            )

    return BrokerPolicy(
        venue=str(_require(venue, "name", str, "venue")),
        label=str(_require(venue, "label", str, "venue")),
        user_agent=str(_require(venue, "user_agent", str, "venue")),
        market=str(_require(venue, "market", str, "venue")),
        base_url=base_url,
        forbidden_hosts=forbidden,
        allowed_methods=allowed,
        write_enabled=write_enabled,
        key_env=str(_require(access, "key_env", str, "access")),
        secret_env=str(_require(access, "secret_env", str, "access")),
        limits=Limits(
            max_response_bytes=_positive(limits, "max_response_bytes"),
            request_timeout_seconds=_positive(limits, "request_timeout_seconds"),
            max_retries_per_attempt=_require(limits, "max_retries_per_attempt", int, "limits"),
            retry_after_seconds=_require(limits, "retry_after_seconds", int, "limits"),
            page_size=_positive(limits, "page_size"),
            max_pages=_positive(limits, "max_pages"),
        ),
        endpoints={
            str(key): str(value) for key, value in endpoints.items()
            if key != "activity_type"
        },
        activity_type=str(_require(endpoints, "activity_type", str, "endpoints")),
        write=write,
    )


def _positive(section: dict[str, Any], key: str) -> int:
    value = int(_require(section, key, int, "limits"))
    if value <= 0:
        raise PolicyRefused(
            f"{POLICY_PATH.name}: limits.{key} is {value}. A limit that is zero or negative is not "
            f"a limit - it is an unbounded request wearing one."
        )
    return value
