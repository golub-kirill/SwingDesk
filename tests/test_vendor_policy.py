"""The price vendor's limits live in the committed policy, and the adapter reads them there.

**The asymmetry that paid for this, measured 2026-09-04.** The broker had `broker_policy.yml`. The
symbol directory had `directory_pull_policy.yml`, required by `DR-008` and gated by gate 22. The
price vendor — fetched about 2,300 times a day against the directory's two files — had no committed
limit at all: no timeout, no retry budget, no pause, no fetch ceiling. Every one was a default
inside somebody else's library.

**These tests are about REFUSAL more than about loading**, and that is the right ratio. A policy
that loads is worth little; a policy that cannot be half-loaded is the whole point, because a
partially-populated limit set is how a limit silently becomes a default again.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from swingdesk.contracts.market import Interval
from swingdesk.market_data import policy as vendor_policy
from swingdesk.market_data import vendor_yahoo

GOOD = """
version: 1
source:
  vendor: yahoo
  label: A Vendor
  client: someclient
limits:
  request_timeout_seconds: 30
  pause_seconds: 0.0
  max_attempts: 3
  retry_delay_seconds: 30.0
  retry_budget_seconds: 90.0
windows:
  day_max_lookback_days: null
  hour_max_lookback_days: 730
  half_hour_max_lookback_days: 60
fetch:
  auto_adjust: false
"""


def _written(tmp_path: Path, text: str) -> Path:
    target = tmp_path / "vendor_policy.yml"
    target.write_text(text, encoding="utf-8")
    return target


def test_the_committed_policy_loads_and_says_what_is_in_force() -> None:
    """The real file, not a fixture. It must load, and it must carry the values already running."""
    loaded = vendor_policy.load()

    assert loaded.max_attempts == 3, "`DR-015` 3: three attempts"
    assert loaded.retry_delay_seconds == 30.0, "thirty seconds apart"
    assert loaded.retry_budget_seconds == 90.0, "and a ninety-second ceiling on the sleeping"
    assert loaded.auto_adjust is False, "RAW bars - an adjusted series rewrites a bitemporal store"
    assert loaded.day_max_lookback_days is None, "daily history has no ceiling at this vendor"


def test_a_missing_section_REFUSES_rather_than_defaulting(tmp_path: Path) -> None:
    """The whole argument. A limit that quietly falls back to a default is a limit nobody set."""
    text = GOOD.replace("limits:", "notlimits:")
    with pytest.raises(vendor_policy.VendorPolicyRefused) as refusal:
        vendor_policy.load(_written(tmp_path, text))

    # THE SECTION, named as a section. A mutation that returned an empty mapping instead of raising
    # still refused - the first missing KEY inside it raised a moment later - so an assertion on the
    # word "limits" alone passed either way. The diagnostic is the difference between "somebody
    # deleted a section" and "somebody deleted a line", and only one of those is a five-second fix.
    assert "`limits:` section is missing" in str(refusal.value)


def test_a_missing_KEY_refuses_too(tmp_path: Path) -> None:
    """A section that exists is not a section that is complete."""
    text = GOOD.replace("  max_attempts: 3\n", "")
    with pytest.raises(vendor_policy.VendorPolicyRefused, match="max_attempts"):
        vendor_policy.load(_written(tmp_path, text))


def test_a_negative_limit_refuses(tmp_path: Path) -> None:
    """A negative pause is not a faster fetch; it is a policy nobody read before committing."""
    text = GOOD.replace("pause_seconds: 0.0", "pause_seconds: -1.0")
    with pytest.raises(vendor_policy.VendorPolicyRefused, match="negative"):
        vendor_policy.load(_written(tmp_path, text))


def test_a_MISSING_ceiling_and_a_null_one_are_different(tmp_path: Path) -> None:
    """`null` means *as far as the vendor holds*. Absence means somebody forgot.

    Collapsing the two would let a forgotten ceiling read as an unlimited one, which is the
    `unavailable`-admits-unchecked shape aimed at a fetch window.
    """
    assert vendor_policy.load(_written(tmp_path, GOOD)).day_max_lookback_days is None

    text = GOOD.replace("  day_max_lookback_days: null\n", "")
    with pytest.raises(vendor_policy.VendorPolicyRefused, match="day_max_lookback_days"):
        vendor_policy.load(_written(tmp_path, text))


def test_auto_adjust_must_be_a_BOOLEAN_and_the_refusal_says_why(tmp_path: Path) -> None:
    """The one value where a wrong type is not a typo but a rewritten history."""
    text = GOOD.replace("auto_adjust: false", "auto_adjust: maybe")
    with pytest.raises(vendor_policy.VendorPolicyRefused, match="bitemporal"):
        vendor_policy.load(_written(tmp_path, text))


def test_the_adapter_takes_its_lookback_from_the_policy(tmp_path: Path) -> None:
    """THE POINT. A policy nothing reads is decoration - `DR-008` 8, and gate 41's third check.

    The cache is cleared around this deliberately: it exists so an evening pass parses one YAML
    instead of 1,142, and a test that left it warm would be asserting about the committed file
    while claiming to assert about this one.
    """
    text = GOOD.replace("hour_max_lookback_days: 730", "hour_max_lookback_days: 111")
    target = _written(tmp_path, text)
    vendor_yahoo.policy.cache_clear()
    try:
        original = vendor_policy.POLICY_PATH
        vendor_policy.POLICY_PATH = target
        vendor_yahoo.policy.cache_clear()
        assert vendor_yahoo.max_lookback_days(Interval.HOUR) == 111
    finally:
        vendor_policy.POLICY_PATH = original
        vendor_yahoo.policy.cache_clear()

    assert vendor_yahoo.max_lookback_days(Interval.HOUR) == 730, "and the real file is back"
