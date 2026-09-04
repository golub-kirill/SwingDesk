"""Reading `registry/vendor_policy.yml`, and refusing when it does not say what it must.

The price adapter holds no timeout, no retry budget and no fetch ceiling of its own. Everything it
is permitted to ask of the vendor comes from here, for the reason `DR-008` gives about the directory
collector and gate 22 enforces: **a limit in a literal is changed by editing a line, a limit in a
committed policy is changed by a commit a reviewer sees.**

**Why this module exists at all, measured 2026-09-04.** The broker had a policy. The symbol
directory had a policy. The price vendor — which this project asks for about 2,300 fetches a day
against the directory's two files — had none. The limits were absent from exactly the place they
matter most, and every one of them was a default inside somebody else's library.

**It authors no number.** Every value the policy carries was already in force: the fetch ceilings
were `MAX_LOOKBACK_DAYS` in `vendor_yahoo`, the retry budget was `DR-015` §3's ratified three
attempts, and the pause is the zero that has been running. `AGENTS.md` §8 governs a threshold this
project INVENTS; recording one already operating is not that.

Stdlib plus PyYAML, and no network — this reads a file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

POLICY_PATH = (
    Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[3])
    / "registry" / "vendor_policy.yml"
)


class VendorPolicyRefused(Exception):
    """The policy is missing, malformed, or does not carry a limit the adapter needs.

    Fail-closed, and deliberately its own exception rather than `VendorUnavailable`. A vendor that
    did not answer is a fact about the world; a policy this repository failed to write is a fact
    about this repository, and one `except` for both would let a configuration mistake read as an
    outage — which is the `unavailable`-admits-unchecked inversion `AGENTS.md` §12 names.
    """


@dataclass(frozen=True, slots=True)
class VendorPolicy:
    """What the price adapter may ask of the vendor, read from the committed file."""

    vendor: str
    label: str
    client: str

    request_timeout_seconds: int
    pause_seconds: float
    max_attempts: int
    retry_delay_seconds: float
    retry_budget_seconds: float

    day_max_lookback_days: int | None
    hour_max_lookback_days: int | None
    half_hour_max_lookback_days: int | None

    auto_adjust: bool


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    block = raw.get(name)
    if not isinstance(block, dict):
        raise VendorPolicyRefused(f"{POLICY_PATH.name}: the `{name}:` section is missing")
    return block


def _number(block: dict[str, Any], key: str, where: str, *, kind: type = int) -> Any:
    if key not in block:
        raise VendorPolicyRefused(f"{POLICY_PATH.name}: {where}.{key} is missing")
    value = block[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VendorPolicyRefused(
            f"{POLICY_PATH.name}: {where}.{key} is {value!r}, which is not a number"
        )
    if value < 0:
        raise VendorPolicyRefused(f"{POLICY_PATH.name}: {where}.{key} is {value}; it cannot be negative")
    return kind(value)


def _ceiling(block: dict[str, Any], key: str) -> int | None:
    """A lookback ceiling, or `None` for *as far as the vendor holds*.

    **`None` is a real answer and not a missing key**, which is why absence still refuses: a policy
    that forgot to state a ceiling and one that states there is none must not look the same.
    """
    if key not in block:
        raise VendorPolicyRefused(f"{POLICY_PATH.name}: windows.{key} is missing")
    value = block[key]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise VendorPolicyRefused(
            f"{POLICY_PATH.name}: windows.{key} is {value!r}; a ceiling is a positive whole number "
            f"of days, or `null` for no ceiling"
        )
    return value


def load(path: Path | None = None) -> VendorPolicy:
    """Read the committed policy, or refuse. Never returns a partially-populated policy."""
    target = path or POLICY_PATH
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise VendorPolicyRefused(f"no vendor policy at {target}") from None
    except yaml.YAMLError as broken:
        raise VendorPolicyRefused(f"{target.name} is not valid YAML: {broken}") from None
    if not isinstance(raw, dict):
        raise VendorPolicyRefused(f"{target.name} does not contain a mapping")

    source, limits = _section(raw, "source"), _section(raw, "limits")
    windows, fetch = _section(raw, "windows"), _section(raw, "fetch")

    for key in ("vendor", "label", "client"):
        if not isinstance(source.get(key), str) or not source[key].strip():
            raise VendorPolicyRefused(f"{target.name}: source.{key} is missing or blank")

    adjust = fetch.get("auto_adjust")
    if not isinstance(adjust, bool):
        raise VendorPolicyRefused(
            f"{target.name}: fetch.auto_adjust is {adjust!r}, which is not true or false. This one "
            f"is not a preference - an adjusted series rewrites history under a bitemporal store"
        )

    return VendorPolicy(
        vendor=source["vendor"], label=source["label"], client=source["client"],
        request_timeout_seconds=_number(limits, "request_timeout_seconds", "limits"),
        pause_seconds=_number(limits, "pause_seconds", "limits", kind=float),
        max_attempts=_number(limits, "max_attempts", "limits"),
        retry_delay_seconds=_number(limits, "retry_delay_seconds", "limits", kind=float),
        retry_budget_seconds=_number(limits, "retry_budget_seconds", "limits", kind=float),
        day_max_lookback_days=_ceiling(windows, "day_max_lookback_days"),
        hour_max_lookback_days=_ceiling(windows, "hour_max_lookback_days"),
        half_hour_max_lookback_days=_ceiling(windows, "half_hour_max_lookback_days"),
        auto_adjust=adjust,
    )
