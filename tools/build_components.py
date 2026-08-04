"""Generate registry/components.yml from registry/course_index.yml, preserving authored fields.

Six of a component's fields are the course's — component, name, layer, stage, claim_type,
validation — and are generated. The rest are authored as a component advances, and this script must
never lose them: it reads the existing file, regenerates the course-derived fields, and writes the
authored ones back untouched.

**Which topics get a row.** `COMPONENT_REGISTRY_SPEC` §8 left this open. Resolved here:

  - every **non-Definition** topic (463) — these are the computable catalogue, and §7's coverage
    check is stated over exactly them
  - plus any **Definition** topic that has an implementation

The second clause is not a technicality. Two implemented components are Definitions in the course —
`M31-T0459` breadth and `M30-T0450` regime — so a rule that excluded Definitions would have left the
project's only `validated` parameter attached to a component with no registry row.

The remaining ~914 Definitions stay out. They compute nothing and seed the glossary; carrying them
would triple the file to make a coverage check trivially true.

Usage:
    python tools/build_components.py [--check-only]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COURSE = REPO / "registry" / "course_index.yml"
OUT = REPO / "registry" / "components.yml"

#: Regenerated from the course every run. Hand-editing one is a defect the check-only mode catches.
GENERATED = ("component", "name", "layer", "stage", "claim_type", "validation")

#: Authored as a component advances. Carried forward verbatim.
AUTHORED = ("activation", "implements", "parameters", "consumers", "owner", "verification", "spec")

DEFAULTS = {
    "activation": "registered",
    "implements": None,
    "parameters": [],
    "consumers": [],
    "owner": None,
    "verification": None,
    "spec": None,
}

HEADER = """# Component registry.
#
# GENERATED for the course-derived fields; AUTHORED for the rest. Regenerate with
# tools/build_components.py, which preserves every authored field.
#
#   generated : component, name, layer, stage, claim_type, validation
#   authored  : activation, implements, parameters, consumers, owner, verification, spec
#
# Hand-editing a generated field is a defect - `--check-only` catches it.
#
# Rows exist for every non-Definition topic, plus any Definition topic with an implementation.
# See tools/build_components.py for why the second clause is not a technicality.
#
# Activation (COMPONENT_REGISTRY_SPEC 3):
#   registered - the course row exists. Free.
#   specified  - algorithm spec written, parameters declared with provenance, consumers listed.
#   active     - parameters have values, verification exists, `implements` points at real code.
#
# Enforced by tools/verify_components.py.

"""


def _load_yaml(path: Path):
    try:
        import yaml
    except ModuleNotFoundError:
        print("PyYAML required (pip install pyyaml)", file=sys.stderr)
        raise SystemExit(2) from None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def course_rows() -> list[dict]:
    data = _load_yaml(COURSE)
    return data["topics"] if isinstance(data, dict) and "topics" in data else data


def existing_authored() -> dict[str, dict]:
    if not OUT.exists():
        return {}
    data = _load_yaml(OUT) or {}
    rows = data.get("components") or []
    return {
        row["component"]: {field: row.get(field, DEFAULTS[field]) for field in AUTHORED}
        for row in rows
    }


def build() -> list[dict]:
    authored = existing_authored()
    implemented = set(authored)

    rows: list[dict] = []
    for topic in course_rows():
        component = topic["component"]
        is_computable = topic["claim_type"] != "Definition"
        has_implementation = (
            component in implemented
            and authored[component].get("implements") is not None
        )
        if not (is_computable or has_implementation):
            continue

        row = {
            "component": topic["component"],
            "name": topic["title"],          # the course index calls it `title`
            "layer": topic["layer"],
            "stage": topic["stage"],
            "claim_type": topic["claim_type"],
            "validation": topic["validation"],
        }
        row.update(authored.get(component, dict(DEFAULTS)))
        rows.append(row)
    return rows


def render(rows: list[dict]) -> str:
    lines = [HEADER, "components:\n"]
    for row in rows:
        lines.append(f"\n  - component: {row['component']}\n")
        lines.append(f"    name: {_scalar(row['name'])}\n")
        lines.append(f"    layer: {_scalar(row['layer'])}\n")
        lines.append(f"    stage: {_scalar(row['stage'])}\n")
        lines.append(f"    claim_type: {_scalar(row['claim_type'])}\n")
        lines.append(f"    validation: {_scalar(row['validation'])}\n")
        lines.append(f"    activation: {row['activation']}\n")
        lines.append(f"    implements: {_scalar(row['implements'])}\n")
        lines.append(f"    parameters: {_list(row['parameters'])}\n")
        lines.append(f"    consumers: {_list(row['consumers'])}\n")
        lines.append(f"    owner: {_scalar(row['owner'])}\n")
        lines.append(f"    verification: {_scalar(row['verification'])}\n")
        lines.append(f"    spec: {_scalar(row['spec'])}\n")
    return "".join(lines)


def _scalar(value) -> str:
    if value is None:
        return "null"
    text = str(value)
    return f'"{text}"' if any(c in text for c in ':#"\'') else text


def _list(values) -> str:
    return "[]" if not values else "[" + ", ".join(str(v) for v in values) + "]"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    rows = build()
    rendered = render(rows)

    computable = sum(1 for r in rows if r["claim_type"] != "Definition")
    implemented = sum(1 for r in rows if r["implements"])
    active = sum(1 for r in rows if r["activation"] == "active")
    print(f"components: {len(rows)} rows ({computable} computable, "
          f"{len(rows) - computable} implemented Definitions)")
    print(f"  implemented {implemented} · active {active}")

    if args.check_only:
        if not OUT.exists():
            print(f"{OUT} does not exist; run without --check-only", file=sys.stderr)
            return 1
        if OUT.read_text(encoding="utf-8") != rendered:
            print(
                "components.yml is stale or a generated field was hand-edited. "
                "Run: python tools/build_components.py",
                file=sys.stderr,
            )
            return 1
        print("components.yml current")
        return 0

    OUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
