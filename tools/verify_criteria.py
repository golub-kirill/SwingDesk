"""Gate 12: a committed criterion must be able to fire.

`REQ-VALIDATION-001` in its narrow form. The requirement's own rationale is not hypothetical - in
TradAlert an R:R gate was `if is_long: return True` and passed seven audits, because it is a valid
function with valid references. Prose review cannot catch that; only an executable check on the
gate's inputs can.

This tree contained one instance. `registry/criteria.yml` ratifies `k.drawdown_pause`, whose trigger
reads "Realised drawdown exceeds validation.max_allowable_drawdown" - and that parameter was `unset`,
along with every other `validation.*` value. A ratified kill criterion that cannot evaluate is a gate
whose verdict is invariant across all inputs. It was found by hand on 2026-08-03, which is exactly
the detection method the requirement says does not scale.

What this does NOT do: mutation testing. It checks that a criterion's inputs exist, not that its
logic discriminates. `REQUIREMENTS.md` §5 keeps `mutation_test` marked absent for that reason - this
closes the cheap half, and closing it should not be mistaken for closing the requirement.

Stdlib plus PyYAML, so it runs wherever the other registry gates do.

    python tools/verify_criteria.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

#: Root of the tree being checked. Overridable so a test can point the gate at a fixture and
#: assert it goes red - a gate nobody has seen fail is a gate nobody has tested. Never set in
#: normal use; `check_gates.py` does not set it.
REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: Statuses that represent a commitment rather than a draft. A `proposed` criterion may legitimately
#: reference a parameter nobody has set yet - that is what proposing it means. A ratified or
#: owner-set one may not, because it is already being relied on.
BINDING = frozenset({"ratified", "owner-set"})

#: Fields whose prose can name a parameter. Criteria cite them unquoted and mid-sentence, so this
#: reads the text rather than a structured reference.
TEXT_FIELDS = ("criterion", "trigger", "value", "measured_by", "action", "note")


def _load_yaml(path: Path) -> Any:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _namespaces(parameter_ids: set[str]) -> tuple[str, ...]:
    """Prefixes that mark a dotted token as a parameter reference.

    Derived from the registry, then unioned with the hand-kept list in `verify_docs.py`. Neither
    alone is enough: derivation cannot see a reference to a namespace that does not exist yet -
    which is precisely the dangling reference worth catching - and the hand-kept list goes stale the
    first time a namespace is added.
    """
    from verify_docs import PARAMETER_NAMESPACES

    derived = {f"{parameter_id.split('.', 1)[0]}." for parameter_id in parameter_ids}
    return tuple(sorted(derived | set(PARAMETER_NAMESPACES)))


def main() -> int:
    criteria = _load_yaml(REPO / "registry" / "criteria.yml")
    parameters = {
        entry["id"]: entry
        for entry in _load_yaml(REPO / "registry" / "parameters.yml")["parameters"]
    }

    namespaces = _namespaces(set(parameters))
    reference = re.compile(
        r"\b(?:" + "|".join(re.escape(prefix) for prefix in namespaces) + r")[a-z_0-9]+"
    )

    failures: list[str] = []
    checked = 0
    references = 0

    for section, items in criteria.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("status") not in BINDING:
                continue
            checked += 1

            text = " ".join(str(item.get(field, "")) for field in TEXT_FIELDS)
            label = f"{section}/{item.get('id')}"
            for name in sorted(set(reference.findall(text))):
                references += 1
                entry = parameters.get(name)
                if entry is None:
                    failures.append(f"{label}: references {name}, absent from the registry")
                elif entry.get("status") == "unset":
                    failures.append(
                        f"{label}: is {item['status']} and references {name}, which is unset - "
                        f"the criterion cannot fire"
                    )

    for failure in failures:
        print(f"  {failure}")
    print(
        f"\ncriteria: {checked} binding, {references} parameter reference(s), "
        f"{len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
