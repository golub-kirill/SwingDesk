"""The evidence record's disclosures, and that they cannot be skipped.

The owner decision of 2026-08-02 permits a component to advance above `Untested` on
survivorship-incomplete data *provided the record says so*. That proviso is the entire safeguard, so
these tests exist to prove it is not optional.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from swingdesk.contracts.evidence import (
    MEASURED_STATUSES,
    VALIDATION_STATUSES,
    EvidenceRecord,
    SurvivorshipCoverage,
)

UTC = UTC

BASE = {
    "evidence_id": "EV-001",
    "component": "M18-T0280-v5.0",
    "component_version": 1,
    "claimed_status": "Historically Tested",
    "run_id": "run-20260115T210000Z-abcd1234",
    "recorded_at": datetime(2026, 1, 15, 21, 0, tzinfo=UTC),
    "window_start": date(2016, 1, 4),
    "window_end": date(2026, 1, 14),
    "sample_size": 412,
}


def test_survivorship_cannot_be_omitted() -> None:
    """No default. A record that does not disclose coverage does not exist."""
    with pytest.raises(ValidationError):
        EvidenceRecord(**BASE)


def test_absent_survivorship_qualifies_the_claim() -> None:
    """The expected state on free data: advancement permitted, disclosure mandatory."""
    record = EvidenceRecord(**BASE, survivorship=SurvivorshipCoverage.ABSENT, prereg_id="PR-001")
    assert record.is_qualified
    assert any("survivorship absent" in note for note in record.qualifications)
    assert record.claimed_status in MEASURED_STATUSES


def test_complete_survivorship_alone_does_not_qualify() -> None:
    """Nothing to disclose means nothing displayed - the flag must not become decoration."""
    record = EvidenceRecord(**BASE, survivorship=SurvivorshipCoverage.COMPLETE, prereg_id="PR-001")
    assert not record.is_qualified
    assert record.qualifications == ()


def test_missing_prereg_is_disclosed_as_exploratory() -> None:
    """A study with no pre-registration is reportable and is not evidence."""
    record = EvidenceRecord(**BASE, survivorship=SurvivorshipCoverage.COMPLETE)
    assert any("exploratory" in note for note in record.qualifications)


def test_window_ceiling_and_pit_are_disclosures_too() -> None:
    record = EvidenceRecord(
        **BASE,
        survivorship=SurvivorshipCoverage.COMPLETE,
        prereg_id="PR-001",
        window_ceiling_days=60,
        point_in_time_from=date(2026, 8, 1),
    )
    assert len(record.qualifications) == 2
    assert any("60 trading days" in note for note in record.qualifications)


def test_a_measured_status_needs_a_sample() -> None:
    """"Historically Tested" on zero trades asserts a measurement that was not made."""
    with pytest.raises(ValidationError):
        EvidenceRecord(
            **{**BASE, "sample_size": 0}, survivorship=SurvivorshipCoverage.COMPLETE
        )


def test_untested_may_have_no_sample() -> None:
    """`Untested` claims nothing, so it needs nothing. The ladder starts here."""
    record = EvidenceRecord(
        **{**BASE, "claimed_status": "Untested", "sample_size": 0},
        survivorship=SurvivorshipCoverage.ABSENT,
    )
    assert record.claimed_status not in MEASURED_STATUSES


def test_status_must_be_one_of_the_nine() -> None:
    """The enum is the course's. Extending it needs a dated amendment, not a string."""
    with pytest.raises(ValidationError):
        EvidenceRecord(
            **{**BASE, "claimed_status": "Historically Tested (survivorship-limited)"},
            survivorship=SurvivorshipCoverage.ABSENT,
        )
    assert len(VALIDATION_STATUSES) == 9


def test_window_must_not_run_backwards() -> None:
    with pytest.raises(ValidationError):
        EvidenceRecord(
            **{**BASE, "window_start": date(2026, 1, 14), "window_end": date(2016, 1, 4)},
            survivorship=SurvivorshipCoverage.ABSENT,
        )
