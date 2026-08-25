"""Gate 16: the study record, and every count quoted from it.

Written after a defect of the standard shape - a claim that reads as correct and is not. Five
documents stated `4 studies, 3 refuted`. The tree holds three pre-registrations with three reports,
two of them REJECT; the fourth "study" is the survivorship bound, which is labelled post-hoc in its
own report and carries no verdict. Nothing was wrong in the evidence - only in the summaries of it,
and a summary is what everyone reads.

Gate 3e cannot see this: every reference resolved. Only recomputing the counts from the reports
catches it.

  * a report whose verdict is not one of the three permitted values
  * a report with no pre-registration behind it
  * the prereg index disagreeing with the report it points at
  * a parameter carrying `validated:PR-NNN` from a study that did not ACCEPT
  * a `| Studies |` table row whose numbers do not match the reports on disk

Stdlib only, like gates 2 and 3, so it runs on system Python.

    python tools/verify_studies.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

#: `SWINGDESK_ROOT` so this gate can be pointed at a fixture tree, the way gates 3e and 3g already
#: can. It was the last of the four registry gates whose root was fixed at import, which is why it
#: had never been proven able to go red: there was nowhere to plant a defect except the real tree.
REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
PREREG = REPO / "docs" / "prereg"
RESULTS = PREREG / "results"

#: A study either fails to refute its hypothesis, refutes it, cannot say, or could not look.
#: `inconclusive` is first-class here (PREREG_TEMPLATE) - a study that cannot reach a verdict is a
#: result, not a failed run, and collapsing it into either of the others is how a null gets
#: reported as a win.
#:
#: `REFUSED` was added 2026-08-24, when PR-012's sample rule fired and the vocabulary had no word
#: for it. PREREG_TEMPLATE section 8 has always required it - "the study reports the measurement and
#: REFUSES a verdict" when the minimum sample is not met - and this gate could not represent the
#: outcome its own template mandates, so the first study to hit it failed the gate for being honest.
#:
#: It is NOT a synonym for `inconclusive`, and the difference is the one AGENTS.md section 12 calls
#: the most damaging error this product can make. `inconclusive` is a fact about the TRADE: the
#: study looked and the statistic did not discriminate. `REFUSED` is a gap in the DATA: there was
#: not enough to look with, so no statistic was computed. Folding the second into the first reports
#: an unmeasured question as a measured one.
VERDICTS = ("ACCEPT", "REJECT", "INCONCLUSIVE", "REFUSED")

HEADER_FIELD = re.compile(r"^\s*(prereg|status|verdict|id):\s*(.+?)\s*$", re.MULTILINE)
INDEX_ROW = re.compile(r"^\|\s*`(PR-\d+[a-z]?)`\s*\|([^|]*)\|([^|]*)\|", re.MULTILINE)
VALIDATED = re.compile(r"validated:(PR-\d+[a-z]?)")
STUDIES_ROW = re.compile(r"^\|\s*Studies[^|]*\|(.+?)\|\s*$", re.MULTILINE)
ROOT_DOCS = ("README.md", "AGENTS.md", "HANDOFF.md")


def _header(body: str) -> dict[str, str]:
    """The fenced key/value block every prereg and report opens with."""
    return {key: value for key, value in HEADER_FIELD.findall(body)}


def _reports() -> dict[str, str]:
    """Study id -> verdict token, read from the reports themselves."""
    found: dict[str, str] = {}
    for path in sorted(RESULTS.glob("PR-*-report.md")):
        header = _header(path.read_text(encoding="utf-8"))
        study = (header.get("prereg") or "").split()[0] if header.get("prereg") else ""
        # An ABSENT `verdict:` field gives `None or "" -> "".split() -> []`, and indexing that
        # raised `IndexError` rather than reporting a malformed header. Found 2026-08-24 by a report
        # whose header used markdown bold instead of the fenced key/value block every other one
        # uses, so the field was missing entirely: the gate crashed with a traceback where its whole
        # job was to name the defect. The `prereg` line one above already guarded for this; the
        # verdict line did not. A gate that cannot read its subject says so.
        tokens = (header.get("verdict") or "").split()
        verdict = tokens[0].rstrip(",.") if tokens else ""
        if not study:
            print(f"  {path.name}: header has no `prereg:` field naming the study")
            continue
        if verdict not in VERDICTS:
            print(f"  {path.name}: verdict {verdict!r} is not one of {VERDICTS}")
            continue
        found[study] = verdict
    return found


def main() -> int:
    failures: list[str] = []
    reports = _reports()

    registered = {
        match.group(1)
        for path in PREREG.glob("PR-*.md")
        if (match := re.match(r"(PR-\d+[a-z]?)-", path.name))
    }

    # 1. A report with no pre-registration is a result without a protocol - the one thing
    #    VALIDATION_PROGRAM 5 says is not evidence.
    for study in sorted(reports):
        if study not in registered:
            failures.append(f"{study}: reported with no pre-registration file in docs/prereg/")

    # 2. The index and the reports must agree. The index is what a reader sees first.
    index = PREREG / "README.md"
    for study, _question, status in INDEX_ROW.findall(index.read_text(encoding="utf-8")):
        state = status.strip().replace("*", "").lower()
        if "reported" in state:
            verdict = reports.get(study)
            if verdict is None:
                failures.append(f"docs/prereg/README.md: {study} is indexed reported, no report file")
            elif verdict.lower() not in state:
                failures.append(
                    f"docs/prereg/README.md: {study} indexed as {state!r}, report says {verdict}"
                )
        elif "not written" in state and study in registered:
            failures.append(f"docs/prereg/README.md: {study} indexed 'not written' and it exists")

    # 3. A `validated` parameter may only cite a study that failed to refute its hypothesis.
    parameters = (REPO / "registry" / "parameters.yml").read_text(encoding="utf-8")
    for study in sorted(set(VALIDATED.findall(parameters))):
        verdict = reports.get(study)
        if verdict is None:
            failures.append(f"registry/parameters.yml: validated:{study} has no report")
        elif verdict != "ACCEPT":
            failures.append(
                f"registry/parameters.yml: validated:{study}, whose verdict is {verdict}. "
                f"A refuted study cannot validate a parameter."
            )

    # 4. Every count quoted in a `| Studies |` row, recomputed.
    counts = {
        "reported": len(reports),
        "refuted": sum(1 for v in reports.values() if v == "REJECT"),
        "accepted": sum(1 for v in reports.values() if v == "ACCEPT"),
    }
    markdown = sorted((REPO / "docs").rglob("*.md")) + [REPO / name for name in ROOT_DOCS]
    rows = 0
    for path in markdown:
        body = path.read_text(encoding="utf-8")
        for cell in STUDIES_ROW.findall(body):
            rows += 1
            plain = cell.replace("*", "")
            for word, expected in counts.items():
                for quoted in re.findall(rf"(\d+)\s+{word}", plain):
                    if int(quoted) != expected:
                        failures.append(
                            f"{path.relative_to(REPO)}: says {quoted} {word}, "
                            f"the reports say {expected}"
                        )

    for failure in failures:
        print(f"  {failure}")
    print(
        f"\nstudies: {len(registered)} pre-registered, {counts['reported']} reported "
        f"({counts['refuted']} refuted, {counts['accepted']} accepted), {rows} summary row(s) "
        f"checked, {len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
