"""Gate 3e: documentation cross-references resolve, and status values are from the ladder.

Every defect this gate catches has the same shape - a claim that reads as correct and is stale. Two
surfaced by hand on 2026-08-03: `DR-003` described the share-class exclusion accurately and framed
it as 2.5% of a random sample, which made it sound peripheral while it was silently removing
Berkshire; and `UX_COPY` claimed Appendix A was untranscribed when `GLOSSARY.md` had held all 35
terms since 2026-08-01. Neither was a code defect and neither would fail a test.

A careful read does not catch the next one. This does:

  * a `FOO_SPEC.md` cited by a document that does not exist
  * a `parameter.id` cited by a document and absent from the registry
  * an `M##-T####` component id absent from the course index
  * a Status line outside the declared ladder
  * the gap analysis's coverage summary disagreeing with a recount of its own table

**Known limit: it cannot tell a historical name from a live citation.** A renamed, superseded or
merged-away document mentioned in backticks reads exactly like a reference to a missing file, and
that has now happened three times in one day - a struck-through filename, a renamed study, and a
merged specification. The fix each time was to write the dead name in plain text, which is correct:
it is no longer a reference. Adding an exemption list instead would be a list of names nobody may
ever cite again, which is worse than a false positive that takes one edit to clear.

Stdlib plus PyYAML, so it runs wherever the other registry gates do.

    python tools/verify_docs.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

#: Root of the tree being checked. Overridable so a test can point the gate at a fixture and
#: assert it goes red - a gate nobody has seen fail is a gate nobody has tested. Never set in
#: normal use; `check_gates.py` does not set it.
REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
DOCS = REPO / "docs"

#: The status ladder, from docs/README.md. A value outside it is a defect rather than a nuance.
STATUSES = {"planned", "drafting", "owner-pending", "frozen", "generated"}

#: Documents named in the plan but deliberately not written yet. Listed explicitly so that adding
#: one is a decision someone made, not a reference that quietly stopped resolving.
PLANNED = {
    # Tier 7, deferred to G7 - they specify a visual surface that does not exist (docs/README.md).
    "DESIGN_SYSTEM.md",
    "CHART_VISUAL_STANDARD.md",
    "ACCESSIBILITY.md",
    "DESIGN_HANDOFF.md",
    # Per-package developer context, planned alongside AGENTS.md.
    "CONTEXT.md",
    # RULE_SPEC, SYSTEM_MODES, EXECUTION_MODEL and COVERAGE_AUDIT were all listed here and are all
    # now written, so they resolve on their own. The remaining absent sections have no agreed
    # filename yet; naming one here would invent it.
    # Broker reconciliation. `UX_TASK_FLOWS.md` §4 argues the hole is real under D1 - the broker is
    # authoritative for positions and the journal must yield - but a spec cannot be written before
    # there is a position source to reconcile against. Named here rather than deleted from
    # FAIL_CLOSED_POLICY, because the requirement outlives the missing document.
    "RECONCILIATION_SPEC.md",
}

#: Documents that EXIST on another branch, unmerged. A third state this gate did not model:
#: `PLANNED` means nobody has written it, and these are written and waiting.
#:
#: **EMPTY as of 2026-08-09, and that is the mechanism finishing.** Both branches landed, so every
#: entry resolved on its own and was removed. The set stays because the situation recurs - this
#: repository normally runs several worktrees - and because a non-empty set is the honest way to say
#: "written, not here yet" without reporting finished work as outstanding.
#:
#: An entry still listed after its branch merges means the merge dropped a file.
ON_OTHER_BRANCHES: set[str] = set()


#: Prefixes that identify a registry parameter rather than an ordinary dotted phrase in prose.
PARAMETER_NAMESPACES = (
    "account.", "atr.", "costs.", "data.", "exit.", "pivot.", "regime.", "risk.",
    "screen.", "sma.", "universe.", "validation.",
)

#: A document reference, bare (`FOO_SPEC.md`) or path-qualified (`docs/08-pm/FOO_SPEC.md`). The
#: path form was invisible to an earlier version of this pattern, which anchored on the opening
#: backtick and so skipped anything starting with a lowercase directory name - the citation style
#: used across most of the tree.
DOC_REF = re.compile(r"`(?:[A-Za-z0-9_./-]*/)?([A-Z][A-Za-z_0-9-]*\.md)`")
PARAM_REF = re.compile(r"`([a-z_]+\.[a-z_0-9]+)`")
TOPIC_REF = re.compile(r"\bM\d{1,3}-T\d{4}\b")
STATUS_LINE = re.compile(r"\*\*Status:\*\*\s*([a-z-]+)")

#: The gap analysis keeps a coverage table and a summary of it in the same document, and the summary
#: was maintained by hand until it drifted to 31/22 against a table saying 30/24. That is the third
#: hand-kept count in this repository to drift - after the study verdicts (gate 3f) and the gate
#: total - so it is recounted here rather than corrected again.
GAP = REPO / "docs" / "08-pm" / "SPEC_GAP_ANALYSIS.md"
GAP_ROW = re.compile(r"^\|\s*(\d+)\s*\|[^|]*\|\s*\*{0,2}(FULL|PARTIAL|ABSENT|DEFERRED)\*{0,2}\s*\|",
                     re.MULTILINE)
GAP_SUMMARY = re.compile(r"^\|\s*(FULL|PARTIAL|ABSENT|DEFERRED)\s*\|\s*\*{0,2}(\d+)\*{0,2}\s*\|",
                         re.MULTILINE)


def check_gap_summary() -> list[str]:
    """The gap analysis's summary must equal a recount of its own table."""
    if not GAP.is_file():
        return [f"{GAP.name} is missing"]
    body = GAP.read_text(encoding="utf-8")

    rows = GAP_ROW.findall(body)
    counted: dict[str, int] = {}
    for _section, coverage in rows:
        counted[coverage] = counted.get(coverage, 0) + 1

    claimed = {key: int(value) for key, value in GAP_SUMMARY.findall(body)}
    if not claimed:
        return [f"{GAP.name}: no summary table found to check"]

    failures = [
        f"{GAP.name}: summary says {key} {claimed.get(key, 0)}, the table has {counted.get(key, 0)}"
        for key in sorted(set(counted) | set(claimed))
        if counted.get(key, 0) != claimed.get(key, 0)
    ]
    sections = {int(section) for section, _ in rows}
    missing = sorted(set(range(min(sections), max(sections) + 1)) - sections) if sections else []
    if missing:
        failures.append(f"{GAP.name}: sections {missing} have no row")
    return failures


def _load_yaml(path: Path):
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


#: Root-level documents that are permanent entry points and must be checked like any other.
#: The numbered specification-track files at root are deliberately NOT here: 31 of their 32
#: references are forward entries in `46_Build_Plan`'s own plan table, and all of them disappear
#: when that material is folded into docs/. Allowlisting them would be 32 throwaway entries.
ROOT_DOCS = ("README.md", "AGENTS.md", "HANDOFF.md")


def _unindexed_decisions() -> list[str]:
    """Every decision record must appear in the decisions index.

    Found the hard way: `DR-004` had existed for three days and the index in §5 listed DR-001 to
    DR-003, so the one record that set the cost model underneath every R in the system was invisible
    to anyone reading the index. Same defect shape as the others this gate catches - a claim that
    reads as correct because what is missing leaves no trace.
    """
    index = DOCS / "decisions" / "README.md"
    if not index.is_file():
        return []

    listed = set(re.findall(r"`(DR-\d{3})`", index.read_text(encoding="utf-8")))
    failures = []
    for path in sorted((DOCS / "decisions").glob("DR-*.md")):
        identifier = "-".join(path.name.split("-")[:2])
        if identifier not in listed:
            failures.append(
                f"docs/decisions/README.md: {identifier} exists and is not in the index"
            )
    return failures


def main() -> int:
    markdown = sorted(DOCS.rglob("*.md")) + [REPO / name for name in ROOT_DOCS]
    # Documents that exist anywhere in the tree, plus the repo-root ones docs legitimately cite.
    known_docs = (
        {p.name for p in markdown}
        | {p.name for p in REPO.glob("*.md")}
        | PLANNED
        | ON_OTHER_BRANCHES
    )

    parameters = {e["id"] for e in _load_yaml(REPO / "registry" / "parameters.yml")["parameters"]}
    topics = {
        row["component"].rsplit("-v", 1)[0]
        for row in _load_yaml(REPO / "registry" / "course_index.yml")["topics"]
    }

    failures: list[str] = []
    for path in markdown:
        rel = path.relative_to(REPO)
        body = path.read_text(encoding="utf-8")

        for name in sorted(set(DOC_REF.findall(body))):
            if name not in known_docs:
                failures.append(f"{rel}: cites {name}, which does not exist and is not planned")

        for name in sorted(set(PARAM_REF.findall(body))):
            if name.startswith(PARAMETER_NAMESPACES) and name not in parameters:
                failures.append(f"{rel}: cites parameter {name!r}, absent from the registry")

        for name in sorted(set(TOPIC_REF.findall(body))):
            if name not in topics:
                failures.append(f"{rel}: cites component {name}, absent from the course index")

        status = STATUS_LINE.search(body)
        if status and status.group(1) not in STATUSES:
            failures.append(
                f"{rel}: status {status.group(1)!r} is outside the ladder {sorted(STATUSES)}"
            )

    failures.extend(_unindexed_decisions())
    failures.extend(check_gap_summary())

    for failure in failures:
        print(f"  {failure}")
    print(
        f"\ndocs: {len(markdown)} checked, {len(parameters)} parameters, {len(topics)} topics, "
        f"{len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
