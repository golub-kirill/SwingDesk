"""Derived observations: the output of a versioned calculation.

Every observation carries the component id and version that produced it, plus the parameters used.
That is what makes "every displayed number traces to a registered component with a recorded
parameter provenance" (USER_STORIES US-018) buildable rather than aspirational - the trace is
carried by the value, not reconstructed later from logs.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: The nine validation statuses, verbatim from Production Rules 3.7 (COMPONENT_REGISTRY_SPEC 4).
#: Order is the course's. Lives here rather than in evidence.py because an observation carries one
#: and observations are the more fundamental record.
VALIDATION_STATUSES = (
    "Not Applicable",
    "Untested",
    "Historically Tested",
    "Out-of-Sample Tested",
    "Walk-Forward Tested",
    "Forward Test Running",
    "Forward Tested",
    "Rejected",
    "Retired",
)

#: Statuses that assert a measurement was made. These are the ones a disclosure qualifies.
MEASURED_STATUSES = frozenset(VALIDATION_STATUSES[2:7])


class ParameterUse(BaseModel):
    """A parameter value as it was used, with where it came from.

    Provenance travels with the number. A report showing a value computed from `assumed` inputs
    must say so adjacent to it (PARAMETER_REGISTRY 5), which is only possible if the value
    remembers.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Id in registry/parameters.yml, e.g. 'atr.period'.")
    value: str = Field(description="Rendered value. String so the record is uniform across types.")
    provenance: str = Field(description="assumed:<citation> | owner | validated:<evidence-id>")

    @property
    def is_assumed(self) -> bool:
        return self.provenance.startswith("assumed:")


class Observation(BaseModel):
    """One computed value for one instrument at one bar."""

    model_config = ConfigDict(frozen=True)

    component: str = Field(description="Course component id, e.g. 'M18-T0280-v5.0'.")
    component_version: int = Field(ge=1, description="Our version, independent of the course's.")
    instrument_id: str
    event_time: datetime
    value: Decimal | None = Field(
        description="None means the component declined to emit - warm-up incomplete or missing "
                    "data. A partially-warmed value is never emitted (ALGORITHM_SPEC 3)."
    )
    units: str
    knowledge_time: datetime


class ObservationSeries(BaseModel):
    """The boundary record: one component's output over a window.

    Mirrors BarSeries. The component identity, version and parameter set live on the container
    rather than on every point, because they are constant across the series by construction - a
    series computed with two different parameter sets is two series.
    """

    model_config = ConfigDict(frozen=True)

    component: str
    component_version: int = Field(ge=1)
    instrument_id: str
    units: str
    parameters: tuple[ParameterUse, ...]
    validation_status: str = Field(
        default="Untested",
        description="From the 9-value enum. Travels with the output so no surface can display the "
                    "number without it (BR-8).",
    )
    knowledge_time: datetime
    observations: tuple[Observation, ...]

    @model_validator(mode="after")
    def _consistent(self) -> ObservationSeries:
        if self.validation_status not in VALIDATION_STATUSES:
            raise ValueError(
                f"{self.validation_status!r} is not one of the nine validation statuses. "
                f"Extending the enum needs a dated amendment (COMPONENT_REGISTRY_SPEC 4), "
                f"not a new string."
            )
        previous: datetime | None = None
        for observation in self.observations:
            if observation.component != self.component:
                raise ValueError("observation component does not match the container")
            if observation.component_version != self.component_version:
                raise ValueError("observation version does not match the container")
            if observation.instrument_id != self.instrument_id:
                raise ValueError("observation instrument does not match the container")
            if previous is not None and observation.event_time <= previous:
                raise ValueError(f"observations not strictly ascending at {observation.event_time}")
            previous = observation.event_time
        return self

    @property
    def uses_assumed_parameters(self) -> bool:
        """True when any input carried `assumed` provenance.

        Drives the display obligation: a number computed from assumptions is marked as such
        wherever it appears.
        """
        return any(parameter.is_assumed for parameter in self.parameters)

    def __len__(self) -> int:
        return len(self.observations)
