"""Gate 12: documentation cross-references resolve, and status values are from the ladder.

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

Stdlib plus PyYAML, so it runs wherever the other registry gates do.

    python tools/verify_docs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
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
    # Broker reconciliation. `UX_TASK_FLOWS.md` §4 argues the hole is real under D1 - the broker is
    # authoritative for positions and the journal must yield - but a spec cannot be written before
    # there is a position source to reconcile against. Named here rather than deleted from
    # FAIL_CLOSED_POLICY, because the requirement outlives the missing document.
    "RECONCILIATION_SPEC.md",
}

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


def _load_yaml(path: Path):
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


#: Root-level documents that are permanent entry points and must be checked like any other.
#: The numbered ТЗ-track files at root are deliberately NOT here: 31 of their 32 unresolved
#: references are forward entries in `46_Build_Plan`'s own plan table, and all of them disappear
#: when that material is folded into docs/. Allowlisting them would be 32 throwaway entries.
ROOT_DOCS = ("README.md", "AGENTS.md")


def main() -> int:
    markdown = sorted(DOCS.rglob("*.md")) + [REPO / name for name in ROOT_DOCS]
    # Documents that exist anywhere in the tree, plus the repo-root ones docs legitimately cite.
    known_docs = {p.name for p in markdown} | {p.name for p in REPO.glob("*.md")} | PLANNED

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

    for failure in failures:
        print(f"  {failure}")
    print(
        f"\ndocs: {len(markdown)} checked, {len(parameters)} parameters, {len(topics)} topics, "
        f"{len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
