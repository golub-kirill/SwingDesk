"""Gate 3g: a ratified criterion cannot reference a parameter nobody has set.

The narrow half of `REQ-VALIDATION-001` (`REQUIREMENTS.md` §2). The requirement's own rationale is
TradAlert's R:R gate, `if is_long: return True`, which passed seven audits because it is a valid
function with valid references. This tree had its own instance and it was quieter: `k.drawdown_pause`
is ratified, its trigger reads *"realised drawdown exceeds validation.max_allowable_drawdown"*, and
that parameter was `unset`. A ratified kill criterion whose verdict is invariant across every input
the system can produce is not a safeguard - it is the appearance of one, which is worse, because
nobody looks for a second.

It was found by hand on 2026-08-03. This is the check that finds the next one.

  * a ratified criterion referencing a parameter with no value
  * a criterion referencing a parameter id that is not in the registry at all
  * a criterion referencing another criterion that does not exist
  * a criterion whose status is outside the declared ladder - which matters more than it looks,
    because a typo there would silently exempt the criterion from the first check

Not covered, and named so the gap is deliberate: the mutation half of the requirement - forcing a
gate's inverse must change at least one verdict in a test corpus. That needs a corpus of evaluated
criteria, and nothing evaluates these yet.

    python tools/verify_criteria.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CRITERIA = REPO / "registry" / "criteria.yml"
PARAMETERS = REPO / "registry" / "parameters.yml"

SECTIONS = ("track_a", "track_b", "kill")

#: The ladder declared at the top of criteria.yml. A value outside it is a defect, not a nuance.
STATUSES = ("proposed", "owner-set", "ratified", "met", "failed")

#: Statuses that put a criterion in force. These are the ones whose references must resolve to a
#: value; a `proposed` criterion may legitimately name a threshold nobody has set yet.
BINDING = ("ratified", "owner-set", "met")

#: Free-text fields a reference can hide in. `note` included deliberately - a criterion explaining
#: itself in terms of a parameter is still depending on it.
FIELDS = ("criterion", "value", "trigger", "action", "measured_by", "note")

#: A dotted lowercase token. Filtered against the registry's own namespaces below rather than a
#: hardcoded list, so a new parameter family is covered the day it is added.
DOTTED = re.compile(r"\b([a-z_]+\.[a-z_0-9]+)\b")


def _load(path: Path):
    try:
        import yaml
    except ModuleNotFoundError:
        print("PyYAML required (pip install pyyaml)", file=sys.stderr)
        raise SystemExit(2) from None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def check(criteria: dict, parameters: dict[str, dict]) -> list[str]:
    failures: list[str] = []

    rows = [(section, row) for section in SECTIONS for row in criteria.get(section) or []]
    ids = {row["id"] for _, row in rows}
    namespaces = {pid.split(".", 1)[0] for pid in parameters}
    criterion_namespaces = {cid.split(".", 1)[0] for cid in ids}

    for section, row in rows:
        cid = row.get("id", "<no id>")
        status = row.get("status")

        # Checked first: a status outside the ladder would exempt this row from everything below,
        # so a typo would disable the check rather than fail it.
        if status not in STATUSES:
            failures.append(f"{section}/{cid}: status {status!r} is outside {list(STATUSES)}")

        text = " ".join(str(row.get(field, "")) for field in FIELDS)
        for token in sorted(set(DOTTED.findall(text))):
            head = token.split(".", 1)[0]

            if head in namespaces:
                entry = parameters.get(token)
                if entry is None:
                    failures.append(
                        f"{section}/{cid}: references {token!r}, which is not in "
                        f"registry/parameters.yml"
                    )
                elif entry.get("value") is None and status in BINDING:
                    failures.append(
                        f"{section}/{cid} is {status} and references {token}, which is unset. "
                        f"A criterion in force whose parameter has no value cannot fail "
                        f"(REQ-VALIDATION-001)."
                    )
            elif head in criterion_namespaces and token not in ids:
                failures.append(f"{section}/{cid}: references criterion {token!r}, which does not exist")

    return failures


def main() -> int:
    criteria = _load(CRITERIA) or {}
    parameters = {e["id"]: e for e in (_load(PARAMETERS) or {}).get("parameters") or []}

    failures = check(criteria, parameters)
    counted = sum(len(criteria.get(section) or []) for section in SECTIONS)
    binding = sum(
        1
        for section in SECTIONS
        for row in criteria.get(section) or []
        if row.get("status") in BINDING
    )

    for failure in failures:
        print(f"  {failure}")
    print(
        f"\ncriteria: v{criteria.get('version', '?')}, {counted} criteria, {binding} in force, "
        f"{len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
