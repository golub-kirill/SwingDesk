"""Reading registry/parameters.yml, and refusing when a value is absent.

The course supplies no numeric thresholds, so every threshold here is authored and carries its
provenance. An unset parameter makes its component refuse - it does not fall back to a default,
because there is no default field, deliberately (PARAMETER_REGISTRY 4).

The module gate states it plainly: missing or incomplete required data means
Research/Watch/Skip/Pause, "а не догадку" - not a guess.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from swingdesk.contracts.observation import ParameterUse

REGISTRY_PATH = Path(__file__).resolve().parents[3] / "registry" / "parameters.yml"


class ParameterUnset(Exception):
    """Raised when a component asks for a parameter that has no value.

    Carries the parameter id so the refusal can name it - a refusal that does not say which input
    was missing is not actionable (USER_STORIES US-020).
    """

    def __init__(self, parameter_id: str) -> None:
        self.parameter_id = parameter_id
        super().__init__(
            f"parameter {parameter_id!r} is unset; the component refuses rather than assuming a "
            f"default. Set it in registry/parameters.yml with a provenance."
        )


class UnknownParameter(Exception):
    """Raised when a component asks for a parameter that is not in the registry at all.

    Distinct from unset: unset is an expected, shippable state; unknown means the code and the
    registry disagree, which is a defect.
    """


class ParameterRegistry:
    """The parameter registry, loaded once.

    Lookups return the value *and* its provenance together, because a value whose origin can be
    dropped on the way to a report is a value that can be presented as a measurement
    (PARAMETER_REGISTRY 5).
    """

    def __init__(self, entries: dict[str, dict[str, Any]]) -> None:
        self._entries = entries

    @classmethod
    def load(cls, path: Path | None = None) -> ParameterRegistry:
        import yaml

        source = path or REGISTRY_PATH
        data = yaml.safe_load(source.read_text(encoding="utf-8"))
        entries = {entry["id"]: entry for entry in (data.get("parameters") or [])}
        return cls(entries)

    def __contains__(self, parameter_id: str) -> bool:
        return parameter_id in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def is_set(self, parameter_id: str) -> bool:
        entry = self._entries.get(parameter_id)
        if entry is None:
            raise UnknownParameter(parameter_id)
        return entry.get("value") is not None

    def use(self, parameter_id: str) -> ParameterUse:
        """Fetch a parameter for use, or refuse.

        Returns the record that travels with any number computed from it.
        """
        entry = self._entries.get(parameter_id)
        if entry is None:
            raise UnknownParameter(
                f"{parameter_id!r} is not in registry/parameters.yml. Code and registry disagree."
            )
        if entry.get("value") is None:
            raise ParameterUnset(parameter_id)
        provenance = entry.get("provenance")
        if not provenance:
            # verify_parameters.py rejects this, so reaching it means the linter was bypassed.
            raise UnknownParameter(f"{parameter_id!r} has a value but no provenance")
        return ParameterUse(id=parameter_id, value=str(entry["value"]), provenance=str(provenance))

    def int_value(self, parameter_id: str) -> tuple[int, ParameterUse]:
        use = self.use(parameter_id)
        return int(use.value), use

    def decimal_value(self, parameter_id: str) -> tuple[Decimal, ParameterUse]:
        use = self.use(parameter_id)
        return Decimal(use.value), use

    def unset_ids(self) -> tuple[str, ...]:
        """Every parameter still awaiting a value. Reported daily (OBSERVABILITY_SPEC 5)."""
        return tuple(
            sorted(pid for pid, entry in self._entries.items() if entry.get("value") is None)
        )

    def assumed_ids(self) -> tuple[str, ...]:
        """Every parameter whose value is an assumption rather than evidence."""
        return tuple(
            sorted(
                pid
                for pid, entry in self._entries.items()
                if str(entry.get("provenance") or "").startswith("assumed:")
            )
        )
