"""Gate 15: the document index cannot drift from the tree or from the documents themselves.

Master TZ section 5. `docs/README.md` was a hand-maintained index and it had drifted in four
different ways at once, none of which a careful read had caught:

  * it claimed "57 documents in 8 tiers" while carrying 61 numbered rows across nine tiers;
  * it marked `REGIME_SPEC.md`, `EVENT_SPEC.md` and `CHART_SPEC.md` as `planned` when all three
    existed, ran to 118-161 lines, and declared `drafting` in their own headers;
  * it omitted `REQUIREMENTS.md` and `SPEC_GAP_ANALYSIS.md` entirely;
  * its Status column carried document progress, gate closure, ADR state and dates in one field.

`registry/project_manifest.yml` is now the machine source of truth and this checks three things
against each other: the manifest, the filesystem, and the index. A document's OWN status header wins
over the index, because the index is what was wrong.

Needs PyYAML, like the other registry gates.

    python tools/verify_project_manifest.py
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
MANIFEST = REPO / "registry" / "project_manifest.yml"
README = DOCS / "README.md"

#: This tree's status ladder, enforced by gate 3e on every document header. Deliberately NOT the
#: master TZ's richer set: two status vocabularies in one repository is the "one logic in two
#: places" violation that section 8 of the same specification forbids.
STATUSES = frozenset({"planned", "drafting", "owner-pending", "frozen", "generated"})

#: Directories whose documents are catalogued by their own index rather than by a numbered row.
#: Each is referenced from `docs/README.md` as a directory, so nothing here is unlisted - it is
#: listed collectively, which is a different thing from being missed.
UNNUMBERED = {
    "docs/decisions": "decision records, indexed by docs/decisions/README.md",
    "docs/prereg": "pre-registrations and results, indexed by docs/prereg/README.md",
    "docs/adr": "architecture decisions, referenced as `adr/` by rows 28 and 43",
    "docs/runbooks": "runbooks, referenced as `runbooks/` by row 45",
    "docs/contracts": "contract records, referenced as `contracts/` by row 25",
}

OWN_STATUS = re.compile(r"\*\*Status:\*\*\s*([a-z-]+)")
ROW = re.compile(r"^\|\s*(\d{1,2}[a-z]?)\s*\|")


def _load_yaml(path: Path):
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main() -> int:
    manifest = _load_yaml(MANIFEST)
    tiers = {t["id"] for t in manifest["tiers"]}
    documents = manifest["documents"]
    failures: list[str] = []

    # --- the manifest against itself -------------------------------------------------
    seen_ids: set[str] = set()
    seen_numbers: set[str] = set()
    for doc in documents:
        if doc["id"] in seen_ids:
            failures.append(f"duplicate document id {doc['id']}")
        seen_ids.add(doc["id"])
        if doc["display_number"] in seen_numbers:
            failures.append(f"duplicate display number {doc['display_number']!r}")
        seen_numbers.add(doc["display_number"])
        if doc["tier_ref"] not in tiers:
            failures.append(f"{doc['id']}: unknown tier {doc['tier_ref']}")
        if doc["document_status"] not in STATUSES:
            failures.append(
                f"{doc['id']}: status {doc['document_status']!r} outside {sorted(STATUSES)}"
            )

    # --- the manifest against the filesystem ------------------------------------------
    for doc in documents:
        path = doc.get("path")
        if not path or not doc.get("file_expected", True):
            continue
        if not (REPO / path).is_file():
            failures.append(f"{doc['id']}: path {path} does not exist")
            continue
        own = OWN_STATUS.search((REPO / path).read_text(encoding="utf-8"))
        if own and own.group(1).lower() != doc["document_status"]:
            failures.append(
                f"{doc['id']}: {path} declares {own.group(1)!r} but the manifest says "
                f"{doc['document_status']!r}"
            )

    # --- the index against the manifest -----------------------------------------------
    indexed: dict[str, str] = {}
    for line in README.read_text(encoding="utf-8").splitlines():
        if m := ROW.match(line):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            indexed[m.group(1)] = cells[-1] if cells else ""
    for number in sorted(set(indexed) - seen_numbers):
        failures.append(f"docs/README.md: row {number!r} has no manifest entry")
    for number in sorted(seen_numbers - set(indexed)):
        failures.append(f"manifest: document {number!r} has no row in docs/README.md")

    # The index's STATUS CELL against the manifest's copy of it. This gate's own docstring lists
    # `REGIME_SPEC` / `EVENT_SPEC` / `CHART_SPEC` reading `planned` while all three existed as one
    # of the four drifts it was written for - and it caught that only through each document's OWN
    # header, which the manifest tracks. The index cell itself went unchecked, so on 2026-08-24 all
    # three still read `planned` in `docs/README.md`, sixteen days after the manifest recorded
    # `drafting`. A gate that names a defect in its docstring and does not test for it is the same
    # shape as a hand-kept count (`AGENTS.md` §10.6): findable, and not true.
    for doc in documents:
        declared = doc.get("readme_status_text")
        row_status = indexed.get(doc["display_number"])
        if declared is None or row_status is None:
            continue
        if row_status != declared:
            failures.append(
                f"{doc['id']}: docs/README.md row {doc['display_number']!r} reads "
                f"{row_status!r} but the manifest says {declared!r}"
            )

    # --- every document is accounted for ----------------------------------------------
    catalogued = {doc["path"] for doc in documents if doc.get("path")}
    for doc in documents:
        catalogued.update(doc.get("additional_paths") or [])
    for path in sorted(p.relative_to(REPO).as_posix() for p in DOCS.rglob("*.md")):
        if path in catalogued or path == "docs/README.md":
            continue
        if any(path.startswith(f"{d}/") for d in UNNUMBERED):
            continue
        failures.append(f"{path}: in the tree, in no numbered row and in no catalogued directory")

    for failure in failures:
        print(f"  {failure}")
    print(
        f"\nmanifest: {len(tiers)} tiers, {len(documents)} documents, "
        f"{len(list(DOCS.rglob('*.md')))} files on disk, {len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
