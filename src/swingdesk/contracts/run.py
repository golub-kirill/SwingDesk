"""The run manifest: a run's identity and everything it was pinned to.

Written before any work. A replay takes a manifest and must reproduce its output_hash; a mismatch
means either something is non-deterministic or something was not pinned, and the manifest narrows
which (DETERMINISM_SPEC 5).

Config is recorded as a hash, never as values - config can contain credentials (SECURITY 2.5).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from swingdesk.contracts.observation import ParameterUse


class RunManifest(BaseModel):
    """The ten fields of DETERMINISM_SPEC 5, plus the run's own outcome."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    started_at: datetime = Field(description="Identity, not an input. Never read by domain code.")

    code_hash: str
    code_dirty: bool = Field(
        default=False,
        description="True when the working tree had uncommitted changes. A dirty run is "
                    "reproducible only by accident.",
    )
    config_hash: str = Field(description="Hash of the resolved config. Never the values.")
    snapshot_id: str = Field(description="The pinned knowledge_time this run read.")

    component_versions: dict[str, int] = Field(default_factory=dict)
    parameters: tuple[ParameterUse, ...] = ()
    universe_hash: str | None = Field(
        default=None,
        description="Hash of the rule and the member ids it selected. The universe is a run INPUT: "
                    "without it pinned, a changed universe moves output_hash with nothing in the "
                    "manifest explaining why - the same defect gate 9 caught in config_hash. None "
                    "means the run took an explicit instrument list.",
    )
    seed: int | None = None
    calendar_version: str = Field(description="pandas-market-calendars version (ADR-0002).")
    platform: str = Field(description="OS, Python and key library versions.")

    output_hash: str | None = Field(
        default=None,
        description="Set when the run completes. None means the run did not finish, and its "
                    "output is not a decision input.",
    )
    completed_at: datetime | None = None

    @property
    def is_complete(self) -> bool:
        return self.output_hash is not None and self.completed_at is not None

    @property
    def is_reproducible(self) -> bool:
        """A dirty tree means the code cannot be recovered from the hash alone."""
        return self.is_complete and not self.code_dirty

    @property
    def assumed_parameter_count(self) -> int:
        """How many assumed values influenced this run.

        Reported daily (OBSERVABILITY_SPEC 5) and tracked as a project-health signal: if it never
        falls, the validation programme is not progressing.
        """
        return sum(1 for parameter in self.parameters if parameter.is_assumed)
