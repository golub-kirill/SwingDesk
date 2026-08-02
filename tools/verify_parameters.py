"""Enforce the parameter-registry contract.

The course supplies no numeric thresholds, so every threshold in this system is authored. The risk
is not that a value is wrong - it is that a value silently acquires the authority of a measurement.
These checks make that impossible: a parameter cannot carry a value without saying where it came
from, and an unset parameter cannot be mistaken for a default.

Checks:
  1. Every entry has id, unit, value, status, provenance, named_in, ui_editable.
  2. Ids are unique and namespaced (`group.name`).
  3. status is one of unset | assumed | owner | validated, and agrees with value/provenance:
       - value null            <=> status unset  and provenance null
       - status assumed        =>  provenance starts with 'assumed:' and cites a source
       - status owner          =>  provenance is 'owner'
       - status validated      =>  provenance starts with 'validated:' and cites an evidence id
  4. named_in is non-empty - a parameter with no course reference is either invented scope or a
     missing citation, and both need a human to look.

Usage:
    python tools/verify_parameters.py [--registry PATH]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO / "registry" / "parameters.yml"

REQUIRED_FIELDS = ("id", "unit", "value", "status", "provenance", "named_in", "ui_editable")
VALID_STATUS = ("unset", "assumed", "owner", "validated")
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


def load_entries(path: Path) -> list[dict]:
    try:
        import yaml
    except ModuleNotFoundError:
        print(
            "PyYAML is required for this check. It is the only non-stdlib dependency in tools/;\n"
            "install it into the project environment (pip install pyyaml).",
            file=sys.stderr,
        )
        raise SystemExit(2)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data.get("parameters") or []


def check(entries: list[dict]) -> list[str]:
    failures: list[str] = []
    seen: set[str] = set()

    for index, entry in enumerate(entries):
        label = entry.get("id") or f"<entry {index}>"

        missing = [f for f in REQUIRED_FIELDS if f not in entry]
        if missing:
            failures.append(f"{label}: missing required field(s) {missing}")
            continue

        if not ID_PATTERN.match(entry["id"]):
            failures.append(f"{label}: id must be lowercase 'group.name'")
        if entry["id"] in seen:
            failures.append(f"{label}: duplicate id")
        seen.add(entry["id"])

        status = entry["status"]
        value = entry["value"]
        provenance = entry["provenance"]

        if status not in VALID_STATUS:
            failures.append(f"{label}: status {status!r} not in {VALID_STATUS}")
            continue

        if value is None:
            if status != "unset":
                failures.append(f"{label}: value is null but status is {status!r}, expected 'unset'")
            if provenance is not None:
                failures.append(f"{label}: value is null but provenance is set")
        else:
            if status == "unset":
                failures.append(f"{label}: has a value but status is 'unset'")
            if not provenance:
                failures.append(f"{label}: has a value but no provenance")
            elif status == "assumed" and not re.match(r"^assumed:\s*\S+", str(provenance)):
                failures.append(
                    f"{label}: status 'assumed' requires provenance 'assumed:<citation>', "
                    f"got {provenance!r}"
                )
            elif status == "owner" and str(provenance).strip() != "owner":
                failures.append(f"{label}: status 'owner' requires provenance 'owner'")
            elif status == "validated" and not re.match(r"^validated:\s*\S+", str(provenance)):
                failures.append(
                    f"{label}: status 'validated' requires provenance 'validated:<evidence-id>'"
                )

        if not entry["named_in"]:
            failures.append(f"{label}: named_in is empty - cite the course topic or mark as authored")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args()

    entries = load_entries(args.registry)
    failures = check(entries)

    by_status: dict[str, int] = {}
    for entry in entries:
        by_status[entry.get("status", "?")] = by_status.get(entry.get("status", "?"), 0) + 1

    print(f"parameters: {len(entries)}")
    for status in VALID_STATUS:
        if status in by_status:
            print(f"  {status:<10} {by_status[status]}")

    unset = by_status.get("unset", 0)
    if unset:
        print(
            f"\n{unset} parameter(s) unset. Components owning them return a coded refusal "
            f"rather than a default - see docs/02-domain/FAIL_CLOSED_POLICY.md."
        )

    if failures:
        print(f"\n{len(failures)} FAILURES", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("\nparameter registry contract satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
