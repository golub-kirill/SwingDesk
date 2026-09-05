"""Gate 13: every stated study count matches the studies on disk.

Found the hard way. Six documents claimed the project had run **four** studies of which **three**
were refuted. The record holds three studies with a verdict - PR-001 `reject`, PR-002 `accept`,
PR-005 `reject` - so the true census is two refuted and one accepted. The likely cause is
`PR-002-survivorship-bound.json`, which sits in `results/` and carries neither a `prereg` id nor a
`verdict`: it is a supporting analysis of PR-002, and counting it as a study inflated every summary
that quoted it, including `RISK_REGISTER.md`'s statement of the project's central risk.

The error direction is worth noting, because it is the one people assume cannot happen: it claimed
MORE refuted evidence than exists. An honest-sounding number is not a checked one.

This derives the census from the result files and fails on any document asserting a different one.
Two count phrasings are legitimate and are allowlisted below rather than silently tolerated.

Stdlib only, so it runs wherever gates 2 and 3 do.

    python tools/verify_study_summary.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

#: Root of the tree being checked. Overridable so a test can point the gate at a fixture and
#: assert it goes red - a gate nobody has seen fail is a gate nobody has tested. Never set in
#: normal use; `check_gates.py` does not set it.
REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
DOCS = REPO / "docs"
PREREG = DOCS / "prereg"
RESULTS = PREREG / "results"

#: Root-level documents that state project-wide summaries and must be checked like any other.
#: `TODO.md` joined on 2026-09-05. It had been outside this gate since the gate was written, so
#: the open-work list - the file a fresh session reads first - was never checked. The first run
#: found two dead citations and two sentences claiming a number of reported studies the record
#: contradicted.
ROOT_DOCS = ("README.md", "AGENTS.md", "HANDOFF.md", "TODO.md")

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

#: Counted phrasings that are NOT about the executed-study census. Listed explicitly so that adding
#: one is a decision someone made, rather than a hole that quietly widens.
ALLOWED = {
    # An open item about the order the first four PLANNED studies should run in - a forward-looking
    # statement about intent, not a claim about what has been executed.
    ("docs/05-validation/VALIDATION_PROGRAM.md", "four studies"),
    # "two studies that pick differently are not comparable" - a hypothetical illustrating why a
    # convention needs a decision record. No census is being asserted.
    ("docs/decisions/README.md", "two studies"),
}

#: Result reports are immutable (`PREREG_TEMPLATE.md` §3.2: never edited in place). A report states
#: what was true when it ran, and a gate that demanded they be updated would be asking for frozen
#: evidence to be rewritten - the exact failure the immutability rule prevents.
IMMUTABLE = ("docs/prereg/results/",)

#: A number, in digits or words, followed by a study noun. The lookbehind keeps identifiers out:
#: without it, "PR-002 reported" parses as the number 002.
COUNT_PHRASE = re.compile(
    r"(?<![-\w.])(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(reported\s+|executed\s+|registered\s+|pre-?registered\s+)?"
    r"(studies|study|pre-registrations|pre-registration)\b",
    re.IGNORECASE,
)

#: A number bound directly to a census term. Only consulted on a line that is already talking about
#: studies - "465 registered" is a component count, and a gate that flagged it would be noise.
LABELLED = re.compile(
    r"(?<![-\w.])(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(registered|reported|refuted|accepted)\b",
    re.IGNORECASE,
)

#: What makes a line a study claim at all. `hypothes` is included because "three refuted hypotheses"
#: is a census statement that never uses the word study - and it was one of the six places the
#: original defect hid.
STUDY_NOUN = re.compile(r"\b(stud(y|ies)|pre-?registration|hypothes[ie]s)", re.IGNORECASE)


class Census:
    """What the record actually holds."""

    __slots__ = ("accepted", "refuted", "registered", "reported")

    def __init__(self, registered: int, reported: int, refuted: int, accepted: int) -> None:
        self.registered = registered
        self.reported = reported
        self.refuted = refuted
        self.accepted = accepted

    def get(self, label: str) -> int:
        return {
            "registered": self.registered,
            "reported": self.reported,
            "refuted": self.refuted,
            "accepted": self.accepted,
        }[label]

    def __repr__(self) -> str:
        return (f"registered={self.registered} reported={self.reported} "
                f"refuted={self.refuted} accepted={self.accepted}")


def measure() -> Census:
    """Derive the census from the files, never from a summary.

    A result file without a `prereg` id and a `verdict` is a supporting analysis, not a study. That
    distinction is the whole reason this gate exists.
    """
    registered = sorted(PREREG.glob("PR-*.md"))

    verdicts: list[str] = []
    for path in sorted(RESULTS.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("prereg") and record.get("verdict"):
            verdicts.append(str(record["verdict"]).lower())

    return Census(
        registered=len(registered),
        reported=len(verdicts),
        refuted=sum(1 for v in verdicts if v == "reject"),
        accepted=sum(1 for v in verdicts if v == "accept"),
    )


def _value(token: str) -> int:
    return int(token) if token.isdigit() else NUMBER_WORDS[token.lower()]


def main() -> int:
    census = measure()
    markdown = sorted(DOCS.rglob("*.md")) + [REPO / name for name in ROOT_DOCS]
    # A ROOT_DOCS entry that is absent is skipped rather than raising. Every one of them is
    # present in a real checkout; a FIXTURE builds only what its case needs, and a gate that
    # dies on a missing root file reports a traceback instead of a verdict - which is what
    # adding TODO.md to the tuple did to ten existing tests on 2026-09-05.
    markdown = [path for path in markdown if path.is_file()]

    failures: list[str] = []
    for path in markdown:
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith(IMMUTABLE):
            continue
        body = path.read_text(encoding="utf-8")

        for match in COUNT_PHRASE.finditer(body):
            noun = match.group(3).lower()
            phrase = f"{match.group(1).lower()} {noun}"
            if (rel, phrase) in ALLOWED:
                continue
            modifier = (match.group(2) or "").strip().lower()
            # The modifier decides, when there is one: "executed pre-registrations" is a count of
            # what ran, not of what was registered. Without a modifier the noun decides.
            if modifier in {"reported", "executed"}:
                expected, label = census.reported, "reported"
            elif modifier in {"registered", "pre-registered", "preregistered"}:
                expected, label = census.registered, "registered"
            elif noun.startswith("pre-registration"):
                expected, label = census.registered, "registered"
            else:
                expected, label = census.reported, "reported"
            if _value(match.group(1)) != expected:
                failures.append(
                    f"{rel}: says {match.group(0).strip()!r}, but the record holds "
                    f"{expected} {label} ({census})"
                )

        for line in body.splitlines():
            if not STUDY_NOUN.search(line):
                continue
            for match in LABELLED.finditer(line):
                label = match.group(2).lower()
                if _value(match.group(1)) != census.get(label):
                    failures.append(
                        f"{rel}: says {match.group(0)!r}, but the record holds "
                        f"{census.get(label)} {label} ({census})"
                    )

    for failure in failures:
        print(f"  {failure}")
    print(f"\nstudies: {census}, {len(markdown)} documents checked, {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
