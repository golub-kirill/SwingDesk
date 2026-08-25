"""Gate 35: a document naming a test must name one that exists.

`INVARIANTS.md` section 1 names the test enforcing each of nine invariants. `REQUIREMENTS.md`
section 7 names the test or gate that would go red for each of nine requirements. `CI_POLICY.md`,
`TODO.md` and `HANDOFF.md` all cite tests as evidence that something is enforced. **Those citations
are the whole argument** - a reader takes "enforced by `test_x`" as proof, and nothing checked that
`test_x` was still called `test_x`.

This is gate 28's shape aimed at a different subject. Gate 28 catches prose stating a parameter
status the registry contradicts; this catches prose naming a test the suite does not define. Both
are the failure `AGENTS.md` section 12 records as this repository's most persistent: *"a citation
that was CORRECT when written, still standing after the fact it cites moved."*

**Zero unresolved today, across 23 cited names.** That is the weaker case for a gate and it is made
deliberately: renaming a test is ordinary, safe work that no other gate would notice, and the
documents it silently falsifies are the ones a reader trusts to know what is enforced. It costs
nothing while the answer stays zero.

**Two exclusions, each a rule rather than a convenience.**

* `docs/decisions/`, `docs/prereg/` and `docs/adr/` are append-only (`AGENTS.md` section 11 rule 2).
  A record states what was true when it was accepted; demanding that it track a later rename would
  demand the one thing those stores forbid. Gate 20 already covers a decision record's
  `implemented_by` marker, so this is not a gap.
* A line that reads as **history** - struck through, or carrying a ruling word - is a statement
  about a date. Same convention as gate 28 and `AGENTS.md` section 10.5.

    python tools/verify_cited_tests.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: A backticked pytest function name. Anything else in backticks is not this gate's business.
CITED = re.compile(r"`(test_[a-z0-9_]+)`")

#: A test as pytest defines one.
DEFINED = re.compile(r"^(?:async )?def (test_[a-z0-9_]+)", re.MULTILINE)

#: A line recording what was true on a date, or a removal being announced. Same set as gate 28.
HISTORICAL = re.compile(r"~~|\b(DONE|CLOSED|REMOVED|DELETED|RENAMED|SUPERSEDED|WAS|REPLACED)\b")

APPEND_ONLY = ("docs/decisions/", "docs/prereg/", "docs/adr/")


def _defined() -> set[str]:
    names: set[str] = set()
    tests = REPO / "tests"
    if not tests.is_dir():
        return names
    for path in sorted(tests.rglob("*.py")):
        names.update(DEFINED.findall(path.read_text(encoding="utf-8")))
    return names


def _documents() -> list[Path]:
    paths = sorted(REPO.glob("docs/**/*.md")) + sorted(REPO.glob("*.md"))
    return [
        path for path in paths
        if not path.relative_to(REPO).as_posix().startswith(APPEND_ONLY)
    ]


def main() -> int:
    defined = _defined()
    failures: list[str] = []
    cited: set[str] = set()
    scanned = 0

    for path in _documents():
        scanned += 1
        relative = path.relative_to(REPO).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in CITED.finditer(line):
                name = match.group(1)
                cited.add(name)
                if name in defined or HISTORICAL.search(line):
                    continue
                failures.append(
                    f"{relative}:{number}: names `{name}`, which tests/ does not define"
                )

    for failure in failures:
        print(f"  {failure}")
    if failures:
        print(
            "\n  A document naming a test is claiming something is enforced, and a reader takes"
            "\n  that as proof. Point it at the test that carries the property now, or mark the"
            "\n  line as history the way AGENTS.md 10.5 does - strike it through, or say when it"
            "\n  was true."
        )
    print(
        f"\ncited tests: {scanned} document(s), {len(cited)} name(s) cited, "
        f"{len(defined)} defined, {len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
