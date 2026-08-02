"""The evidence record: what a validation claim is allowed to assert, and what it must disclose.

Owner decision, 2026-08-02: a component MAY advance above `Untested` on survivorship-incomplete
data, provided the record carries the coverage and every display of that component shows it. The
alternative - blocking advancement - would have meant nothing ever advances on free data
(BACKTEST_PROTOCOL 6).

That decision only holds if the flag cannot be omitted, so it is a required field with no default.
A record constructed without it does not exist rather than existing as complete, and the three
disclosures (survivorship, window ceiling, point-in-time coverage) are the three EVIDENCE_RECORD_SPEC
adds beyond the course's own list.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from swingdesk.contracts.observation import MEASURED_STATUSES, VALIDATION_STATUSES

__all__ = [
    "MEASURED_STATUSES",
    "VALIDATION_STATUSES",
    "EvidenceRecord",
    "SurvivorshipCoverage",
]


class SurvivorshipCoverage(StrEnum):
    """Whether delisted instruments were present in the study's universe.

    `absent` is the expected value on free data and is not a defect - it is a disclosure. What is a
    defect is a record that does not say.
    """

    COMPLETE = "complete"
    PARTIAL = "partial"
    ABSENT = "absent"

    @property
    def biases_result_upward(self) -> bool:
        """True when instruments that failed are missing from the sample."""
        return self is not SurvivorshipCoverage.COMPLETE


class EvidenceRecord(BaseModel):
    """One validation claim, with everything that qualifies it.

    Frozen: a claim that can be edited after the fact is not evidence, and error HINDSIGHT's
    required control is an immutable snapshot (AUDIT_AND_IMMUTABILITY).
    """

    model_config = ConfigDict(frozen=True)

    evidence_id: str = Field(description="Stable id referenced by parameter provenance.")
    component: str
    component_version: int
    claimed_status: str = Field(description="The validation status this evidence supports.")

    prereg_id: str | None = Field(
        default=None,
        description="The pre-registration this study was run under. None means the study was "
                    "exploratory - which is a legitimate kind of work and is not evidence "
                    "(PREREG_TEMPLATE 3).",
    )
    run_id: str = Field(description="The run whose manifest pins code, config and snapshot.")
    recorded_at: datetime

    window_start: date
    window_end: date
    sample_size: int = Field(ge=0, description="Trades, or observations for a descriptive study.")

    # --- the three disclosures EVIDENCE_RECORD_SPEC adds beyond the course's list ---
    survivorship: SurvivorshipCoverage = Field(
        description="REQUIRED, no default. Every historical result on free data is optimistic by "
                    "an unknown amount, and the owner decision permitting advancement anyway "
                    "depends entirely on this being impossible to leave out."
    )
    window_ceiling_days: int | None = Field(
        default=None,
        description="History available for the tightest-bound interval the study used. A claim "
                    "touching 30m data is bounded by ~60 trading days no matter how it is phrased.",
    )
    point_in_time_from: date | None = Field(
        default=None,
        description="First date with a real revision record. Data before it is backfilled, and "
                    "backfilled history is not point-in-time history (POINT_IN_TIME_SPEC 7).",
    )

    @model_validator(mode="after")
    def _claim_is_supportable(self) -> EvidenceRecord:
        if self.claimed_status not in VALIDATION_STATUSES:
            raise ValueError(
                f"{self.claimed_status!r} is not one of the nine validation statuses"
            )
        if self.window_end < self.window_start:
            raise ValueError(f"window ends {self.window_end} before it starts {self.window_start}")
        if self.claimed_status in MEASURED_STATUSES and self.sample_size == 0:
            raise ValueError(
                f"{self.claimed_status!r} asserts a measurement; sample_size is 0"
            )
        return self

    @property
    def is_qualified(self) -> bool:
        """True when a disclosure limits what this record may be read as claiming.

        Drives display: a qualified record shows its qualification wherever its component's output
        appears. The owner decision permitting advancement on incomplete survivorship is what makes
        this property load-bearing rather than informational.
        """
        return (
            self.survivorship.biases_result_upward
            or self.point_in_time_from is not None
            or self.window_ceiling_days is not None
        )

    @property
    def qualifications(self) -> tuple[str, ...]:
        """Human-readable disclosures, for display next to the number - not in a footnote."""
        notes: list[str] = []
        if self.survivorship.biases_result_upward:
            notes.append(
                f"survivorship {self.survivorship.value}: result is optimistic by an unmeasured "
                f"amount"
            )
        if self.window_ceiling_days is not None:
            notes.append(f"bounded by {self.window_ceiling_days} trading days of history")
        if self.point_in_time_from is not None:
            notes.append(f"point-in-time record begins {self.point_in_time_from}")
        if self.prereg_id is None:
            notes.append("exploratory: no pre-registration")
        return tuple(notes)
