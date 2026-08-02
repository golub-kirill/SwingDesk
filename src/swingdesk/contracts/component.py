"""What a module declares about the component it implements.

The course's own fields - id, name, layer, stage, claim type, validation status - are generated into
`registry/course_index.yml` and must not be hand-edited (COMPONENT_REGISTRY_SPEC 2). The pure
packages cannot read that file, because they have no I/O, so each module mirrors the row it
implements and a test pins the mirror to the source.

One module may implement more than one component: swing highs and swing lows are the same algorithm
mirrored, and the course gives them separate ids. What may NOT happen is two implementations of one
component - "one canonical definition" (§3.8), the rule import analysis cannot see.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from swingdesk.contracts.observation import VALIDATION_STATUSES


class ComponentSpec(BaseModel):
    """A component's identity, as the implementing module declares it."""

    model_config = ConfigDict(frozen=True)

    component: str = Field(description="Course component id, e.g. 'M25-T0382-v5.0'.")
    name: str
    version: int = Field(ge=1, description="Our version. Independent of the course's.")
    validation: str = Field(
        description="Mirrored from the course index. Advancing above it is the job of evidence "
                    "(VALIDATION_PROGRAM 1), never of a module constant."
    )
    units: str
    layer: str = Field(default="Derived Observations")

    def model_post_init(self, _context: object) -> None:
        if self.validation not in VALIDATION_STATUSES:
            raise ValueError(f"{self.validation!r} is not one of the nine validation statuses")
