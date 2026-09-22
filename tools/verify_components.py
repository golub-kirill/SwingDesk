"""Enforce the component-registry contract — COMPONENT_REGISTRY_SPEC §7.

Six checks the registry unlocks, and the first is the one import analysis cannot see:

  1. `implements` is INJECTIVE. "Each component has one canonical definition" (§3.8). Two components
     mapping to the same function is the violation that looks perfectly legal to a linter, because
     both imports are fine.
  2. Every `active` component has `implements`, `verification` and `spec`. That is what `active`
     MEANS, and it is the drift that put two components into a reported study with no vectors.
  3. Every parameter id resolves in `registry/parameters.yml`. A dangling reference is a component
     that cannot be activated and does not know it.
  4. No `active` component has an `unset` parameter. Fail-closed: a component whose threshold is
     missing must refuse, not run.
  5. `implements` points at a module and symbol that actually exist.
  6. Every non-Definition topic has a row (full-catalogue coverage, owner decision D2).
  7. `spec` points at a document AND a heading that actually exist. Added 2026-08-18, because check
     2 verified only that the field was non-empty while check 5 resolved `implements` for real - so
     the code pointer was a fact and the spec pointer was a string length. All seven implemented
     components pointed at anchors that do not exist, in a document that contains no algorithm
     specifications and whose own section 7 has not decided whether it should.

Plus a consistency check the spec implies rather than lists: a component's `consumers` must name
components that exist, and must not name itself.

Usage:
    python tools/verify_components.py
"""

from __future__ import annotations

import argparse
import ast
import importlib
import re
import sys
from pathlib import Path
from typing import Any

import status_claims

REPO = Path(__file__).resolve().parents[1]
COMPONENTS = REPO / "registry" / "components.yml"
PARAMETERS = REPO / "registry" / "parameters.yml"
COURSE = REPO / "registry" / "course_index.yml"

ACTIVATIONS = ("registered", "specified", "active")
VERIFICATIONS = ("golden vectors", "property test", "review")


def _load(path: Path) -> Any:
    try:
        import yaml
    except ModuleNotFoundError:
        print("PyYAML required (pip install pyyaml)", file=sys.stderr)
        raise SystemExit(2) from None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _slug(heading: str) -> str:
    """GitHub's anchor slug for a Markdown heading: lowercase, non-alphanumerics to hyphens."""
    text = heading.lstrip("#").strip()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


#: The marker a module carries when its ALGORITHM_SPEC record lives in its own docstring. Checked
#: for CONTENT, not presence: a `.py` path that does not actually carry the record is the same
#: false pointer as a dangling anchor, one file type over.
SPEC_RECORD_MARKER = "ALGORITHM_SPEC record"


def spec_failure(component: str, spec: str) -> str | None:
    """`None` when `spec` resolves to a real specification. Two forms are legal.

    `path/to/doc.md#anchor` - the document must exist AND contain that heading.
    `path/to/module.py`     - the module must exist AND carry its ALGORITHM_SPEC record.

    Resolved the way `implements` is resolved, and for the same reason: a pointer only checked for
    length is not a pointer, it is a claim nobody has read. `spec` is what separates `registered`
    from `specified` on the activation ladder, so a dangling one leaves a component standing in a
    state it has not earned.

    The `.py` form is not a concession - it is where these specifications actually live.
    `ALGORITHM_SPEC.md` §7 asked whether specs belong in that document or beside the code, and five
    components had already answered by carrying the full eleven-field record in their module
    docstring while their `spec:` pointed at a heading that never existed.
    """
    path, _, fragment = spec.partition("#")
    target = REPO / path
    if not target.is_file():
        return f"{component}: `spec` names {path}, which does not exist"

    if path.endswith(".py"):
        if fragment:
            return f"{component}: `spec` {spec} - a module path takes no #fragment"
        if SPEC_RECORD_MARKER not in target.read_text(encoding="utf-8"):
            return (f"{component}: `spec` names {path}, which carries no "
                    f"{SPEC_RECORD_MARKER!r}. The file exists; the specification it promises "
                    f"does not")
        return None

    if not fragment:
        return None
    headings = {_slug(line) for line in target.read_text(encoding="utf-8").splitlines()
                if line.startswith("#")}
    if fragment.lower() not in headings:
        return (f"{component}: `spec` points at {path}#{fragment}, and {path} has no such heading. "
                f"The document exists; the section it promises does not")
    return None


def check(
    rows: list[dict[str, Any]],
    parameters: dict[str, dict[str, Any]],
    course: list[dict[str, Any]],
) -> list[str]:
    failures: list[str] = []
    by_id = {row["component"]: row for row in rows}

    # 1. implements is injective
    seen: dict[str, str] = {}
    for row in rows:
        target = row.get("implements")
        if not target:
            continue
        if target in seen:
            failures.append(
                f"{row['component']}: `implements` {target} is already claimed by {seen[target]}. "
                f"Two components may not share one definition (Production Rules 3.8)."
            )
        seen[target] = row["component"]

    for row in rows:
        component = row["component"]
        activation = row.get("activation")

        if activation not in ACTIVATIONS:
            failures.append(f"{component}: activation {activation!r} not in {ACTIVATIONS}")
            continue

        verification = row.get("verification")
        if verification is not None and verification not in VERIFICATIONS:
            failures.append(
                f"{component}: verification {verification!r} not in {VERIFICATIONS}"
            )

        # 2. active requires the three
        if activation == "active":
            for field in ("implements", "verification", "spec"):
                if not row.get(field):
                    failures.append(
                        f"{component}: activation is 'active' with no {field}. That is what "
                        f"'active' means (COMPONENT_REGISTRY_SPEC 3)."
                    )

        # 2b. and the verification claim RESOLVES, rather than merely being non-empty.
        unresolved = unresolved_verification(row)
        if unresolved:
            failures.append(unresolved)

        # 3 and 4. parameters resolve, and an active component has none unset
        for parameter_id in row.get("parameters") or []:
            entry = parameters.get(parameter_id)
            if entry is None:
                failures.append(
                    f"{component}: parameter {parameter_id!r} is not in registry/parameters.yml"
                )
                continue
            if activation == "active" and entry.get("value") is None:
                failures.append(
                    f"{component}: activation is 'active' while {parameter_id} is unset. A "
                    f"component whose threshold is missing must refuse, not run."
                )

        # 7. spec resolves - document AND heading, not merely a non-empty string
        spec = row.get("spec")
        if spec:
            failure = spec_failure(component, str(spec))
            if failure:
                failures.append(failure)

        # 5. implements resolves
        target = row.get("implements")
        if target:
            module_path, _, symbol = target.partition(":")
            if not symbol:
                failures.append(f"{component}: `implements` must be 'module:symbol', got {target!r}")
            else:
                try:
                    module = importlib.import_module(module_path)
                except ImportError as error:
                    failures.append(f"{component}: cannot import {module_path} ({error})")
                else:
                    if not hasattr(module, symbol):
                        failures.append(f"{component}: {module_path} has no {symbol!r}")

        # consumers name real components, and not themselves
        for consumer in row.get("consumers") or []:
            if consumer == component:
                failures.append(f"{component}: lists itself as a consumer")
            elif consumer not in by_id:
                failures.append(f"{component}: consumer {consumer!r} has no registry row")

    # 6. coverage
    missing = [
        topic["component"]
        for topic in course
        if topic["claim_type"] != "Definition" and topic["component"] not in by_id
    ]
    if missing:
        failures.append(
            f"{len(missing)} non-Definition topic(s) have no registry row, first: {missing[:3]}"
        )

    return failures



#: What a `verification` claim may say, and it is the registry's own vocabulary: six rows say
#: `golden vectors` and one says `property test`. A value outside this set is a FAILURE rather than
#: a pass, so the check cannot be stepped around by inventing a third word.
GOLDEN, PROPERTY = "golden vectors", "property test"
VERIFICATION_CLAIMS = (GOLDEN, PROPERTY)

#: Where each claim has to resolve.
GOLDEN_ROOT = REPO / "golden" / "components"
TESTS_ROOT = REPO / "tests"


def unresolved_verification(row: dict[str, object]) -> str | None:
    """`None` when a component's `verification` claim resolves to something that exists.

    **A field checked only for PRESENCE is the defect this project keeps finding under other
    names.** `verify_parameters.py` says that about `read_by` in its own docstring, and it was true
    here too: until 2026-09-21 check 2 asked only `if not row.get("verification")`, so `active` -
    the strongest claim a component can make, the one `COMPONENT_REGISTRY_SPEC` 3 says needs
    parameters with VALUES and verification that EXISTS - rested on a two-word string nobody
    resolved. Both claims were true when this was written; nothing would have said so if they
    were not, and the moment a third component is activated is exactly when a false one slips in.

    Deliberately not a test-name match. `property test` resolves when some file under `tests/`
    imports the module `implements` names - a module import is the one thing a text search reads
    reliably, unlike an f-string-built id or a bare identifier, both of which fooled the `read_by`
    check earlier the same day.
    """
    claim = str(row.get("verification") or "").strip()
    if not claim:
        return None                                   # check 2 above already fails an active row
    component = str(row.get("component", "?"))
    if claim not in VERIFICATION_CLAIMS:
        return (f"{component}: verification {claim!r} is not one of {VERIFICATION_CLAIMS}. "
                f"A claim nobody can resolve is not verification")
    if claim == GOLDEN:
        directory = GOLDEN_ROOT / component
        if not directory.is_dir() or not any(directory.glob("*.json")):
            return (f"{component}: verification says {GOLDEN!r} and "
                    f"golden/components/{component}/ holds none")
        return None
    implements = str(row.get("implements") or "")
    module = implements.partition(":")[0]
    if not module:
        return (f"{component}: verification says {PROPERTY!r} but there is no `implements` to say "
                f"what the test would be exercising")
    if not TESTS_ROOT.is_dir():
        return None                                   # unavailable is not fail (AGENTS.md 12)
    if not any(module in _imported_modules(f) for f in TESTS_ROOT.glob("test_*.py")):
        return (f"{component}: verification says {PROPERTY!r} and no file in tests/ imports "
                f"{module}")
    return None


def _imported_modules(path: Path) -> set[str]:
    """Every module a test file imports, as a dotted name, read from the AST.

    NOT a substring search over the source. `tests/test_relative_strength.py` spells its import
    `from swingdesk.derived_observations import relative_strength`, which does not contain the
    dotted path at all - the first cut of this check passed only because a SECOND file happens to
    use the dotted form, which is a check passing for a reason other than the one it states. The
    same lesson the `read_by` audit produced hours earlier, in the same direction.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:                               # a file that cannot parse imports nothing
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def misstated_activations(components: list[dict[str, object]]) -> list[str]:
    """Every file that states a component activation the registry contradicts.

    **Measured 2026-09-21.** An OPEN `TODO.md` item headlined "`M31-T0464` IS `specified`" and said
    so again in its body - `DR-024` activated it on 2026-08-30, 22 days earlier, and the registry had
    read `active` ever since. The same item said ATR and SMA "are held"; `M18-T0280` (ATR) reads
    `active` too, so the sentence was half true when written.

    An id whose registry rows disagree with each other is skipped rather than guessed at: two rows
    for one bare id means a version bump, and which one a sentence meant is not decidable here.
    """
    by_bare: dict[str, set[str]] = {}
    for entry in components:
        full = str(entry.get("component", ""))
        bare = re.match(r"(M\d+-T\d+)", full)
        if bare:
            by_bare.setdefault(bare.group(1), set()).add(str(entry.get("activation", "")).lower())
    unambiguous = {name: next(iter(v)) for name, v in by_bare.items() if len(v) == 1}
    return status_claims.misstated(
        REPO, unambiguous, id_pattern=r"M\d+-T\d+", words=ACTIVATIONS, caller=Path(__file__))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    sys.path.insert(0, str(REPO / "src"))
    rows = (_load(COMPONENTS) or {}).get("components") or []
    parameters = {e["id"]: e for e in (_load(PARAMETERS) or {}).get("parameters") or []}
    course_data = _load(COURSE)
    course = course_data["topics"] if isinstance(course_data, dict) else course_data

    failures = check(rows, parameters, course)
    # A claim ABOUT the registry rather than one of its rows, and counted with the rest
    # because the repair is the same: correct the sentence. See `status_claims.py`.
    failures += misstated_activations(rows)

    by_activation: dict[str, int] = {}
    for row in rows:
        by_activation[row.get("activation", "?")] = by_activation.get(row.get("activation", "?"), 0) + 1

    print(f"components: {len(rows)}")
    for activation in ACTIVATIONS:
        if activation in by_activation:
            print(f"  {activation:<12} {by_activation[activation]}")

    implemented = [r for r in rows if r.get("implements")]
    blocked = [
        r for r in implemented
        if r.get("activation") != "active"
        and any(parameters.get(p, {}).get("value") is None for p in (r.get("parameters") or []))
    ]
    if blocked:
        print(
            f"\n{len(blocked)} implemented component(s) cannot activate because a parameter is "
            f"unset — the fail-closed design working, not a defect:"
        )
        for row in blocked:
            unset = [p for p in row["parameters"] if parameters.get(p, {}).get("value") is None]
            print(f"  {row['component']:<18} blocked by {unset}")

    if failures:
        print(f"\n{len(failures)} FAILURES", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("\ncomponent registry contract satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
