"""Gate 3g: a committed criterion must be able to fire.

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


#: Where a criterion may be named, and `registry/` is deliberately NOT here. A criterion mentioned
#: only inside another registry file is discharged by nothing: no gate reads it, no document owes
#: anything against it and no `TODO` line tracks it, which is exactly what the failure below says.
#: It is also what makes the check answerable - the gate tests build a registry-only root, and with
#: `registry` searched the check read those two files, decided the tree was present, and accused a
#: fixture of not documenting itself.
SEARCHED = ("tools", "src", "docs", "tests", "AGENTS.md", "HANDOFF.md", "TODO.md", "README.md")


def unreferenced(ids: list[str]) -> set[str] | None:
    """Which criterion ids appear nowhere but `registry/criteria.yml`, or `None` to say it cannot tell.

    A plain text search over the tracked tree rather than an import graph, because a criterion is
    discharged as often by a document or a `TODO` line as by code, and both count as being tracked.

    **`None` when there is no tree to read**, which is `AGENTS.md` 12's rule rather than a
    convenience: the gate tests build a one-criterion registry in a temporary root with no `tools`,
    no `docs` and no `TODO.md`, and a check that called every criterion unreferenced there would be
    accusing on absence. Unavailable is not fail - and the caller says so out loud rather than
    passing quietly, so a search that silently stops working cannot look like a clean run.
    """
    # THIS FILE CANNOT VOUCH FOR A CRITERION, and the first cut let it. Naming the ids in the
    # comment below made `verify_criteria.py` itself a "reference", so every one of them passed -
    # the check went green because of its own text. Excluded like the registry that defines them,
    # and the comment now describes the finding without spelling an id.
    excluded = {(REPO / "registry" / "criteria.yml").resolve(), Path(__file__).resolve()}
    seen: set[str] = set()
    read = 0
    for root in SEARCHED:
        base = REPO / root
        if base.is_file():
            paths = [base]
        elif base.is_dir():
            paths = [q for q in base.rglob("*")
                     if q.is_file() and q.suffix in {".py", ".md", ".yml", ".yaml", ".cmd", ".txt"}]
        else:
            paths = []
        for path in paths:
            if path.resolve() in excluded:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            seen.update(cid for cid in ids if cid in text)
            read += 1
    return None if read == 0 else set(ids) - seen


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
    criterion_ids: list[str] = []

    for section, items in criteria.items():
        if not isinstance(items, list):
            continue
        if section == "amendments":
            # An amendment is a CHANGE RECORD, not a criterion, and it carries `status: ratified`
            # for the change rather than for anything that fires. Its prose legitimately discusses
            # parameters that are unset - v1.1.2's note says in as many words that
            # `risk.risk_off_ladder` stays unset and the prescribed action remains the owner's,
            # which is the honest thing to write and was read here as a criterion that cannot fire.
            #
            # Latent until 2026-08-30: the first two amendments happened to name no unset parameter.
            # The tell was in the gate's own output - it printed `amendments/None`, and a criterion
            # always has an id.
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("status") not in BINDING:
                continue
            if item.get("id") is None:
                # Same subject from the other side: this gate is about identified criteria, and an
                # unidentified dict in a criteria list is not one.
                continue
            checked += 1
            criterion_ids.append(str(item["id"]))

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

    # ------------------------------------------------------------- a criterion nothing names
    #
    # ADDED 2026-09-21, and it is a defect CLASS rather than a tidiness rule. One Track A
    # criterion was ratified asking for something the system does not and should not produce - a
    # reason CODE on every decision row, where `contracts/position.py` defines a code as applying
    # to a skip or an exit only - and it survived because nothing referenced it: outside the
    # registry it appeared once, in a test comment. The same audit found three more with ZERO
    # references anywhere in the tree, one of which its own note calls the only hard numeric gate
    # the course states. **The ids are deliberately not written here**: this file would then be
    # their reference, which is how the first cut of this check passed every one of them.
    #
    # **This checks VISIBILITY, not measurement, and the difference is stated rather than glossed.**
    # A line in `TODO.md` satisfies it. That is deliberate: a criterion whose debt is written down
    # is being tracked, and one nothing names at all cannot be. Making "is it MEASURED" a gate
    # needs a definition of measurement this project does not have, and a gate that claimed to
    # check it would be the green-for-the-wrong-reason failure `AGENTS.md` 12 collects.
    orphans = unreferenced(criterion_ids)
    if orphans is None:
        print("  reference check UNAVAILABLE - no tracked tree at this root, so whether a "
              "criterion is named anywhere could not be read")
    else:
        for criterion in sorted(orphans):
            failures.append(
                f"{criterion}: ratified and named NOWHERE outside registry/criteria.yml - no gate, "
                f"no tool, no document, no TODO item. Write down what it owes, or retire it."
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
