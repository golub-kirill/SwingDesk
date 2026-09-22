"""One rule, used by two gates: a status asserted about an id must match the registry that owns it.

A status is the one fact about a decision or a component that changes what somebody may do next. A
`proposed` that is really `accepted` reads as *the owner has not answered yet*; a `specified` that is
really `active` reads as *nothing calls this*. Both were found stated wrongly on 2026-09-21, in files
a person reads to decide what to work on.

**This is a gate over PROSE, which `CI_POLICY.md` §3 permits only with an exact token.** It has one:
an id, a copula, and a word from a CLOSED set that the registry itself defines. `blocked_claims.py`
is the counter-example and says so in its own docstring - *"it finds sentences, not truth"* - because
"blocked" has no closed vocabulary and no field to compare against. Here both exist, so the check can
be wrong in only one direction: it can miss a paraphrase, and it cannot invent a disagreement.

**Shared rather than copied.** `verify_decisions.py` (gate 20) and `verify_components.py` (gate 11)
each hold their own registry to their own ids, and the matching, the exemptions and the line
arithmetic are identical. This project's own rule against one logic in two places applies to its
gates first: a second copy is a second place for the `~~struck~~` handling to be forgotten.

Three exemptions, each paid for on the day this was written:

  1. **The gate's own file.** A check that names the defect it looks for reports itself.
     `verify_criteria.py` did it this morning and reported ZERO, because the criterion ids it was
     searching for lived in its own comment.
  2. **`~~struck~~` text.** This tree corrects in place - `TODO.md` and `SPEC_GAP_ANALYSIS.md` both
     keep a wrong claim beside its repair - so a check that cannot see the strikethrough accuses the
     correction written to satisfy it.
  3. **A per-LINE marker.** The tests that prove this fires must CONTAIN a false status. Excluding
     `tests/` would be the wrong repair: a test docstring is prose like any other and is exactly
     where a stale claim would sit unread. The marker is visible in the diff and challengeable by a
     reader - the same shape as `implementation: none`.
"""

from __future__ import annotations

import re
from pathlib import Path

#: A line carrying this is an EXAMPLE of the defect rather than an instance of it.
EXAMPLE_MARKER = "status-claim-example"

#: `~~...~~` is this tree's notation for *this was true and is not*.
STRUCK = re.compile(r"~~.*?~~", re.DOTALL)


def without_struck(text: str) -> str:
    """The text with every struck span blanked IN PLACE, so offsets and line numbers survive.

    Deleting the spans was the first version and it misreported line numbers by however many
    newlines it had removed: `tests/test_gates.py` carries a struck fixture, and the claim 5 lines
    below it was reported at the line of an `import`. Same technique as `verify_decisions.py`'s
    `code_of`, which blanks comments and docstrings column by column for the same reason - a check
    that names the wrong line sends a reader to innocent code and gets disbelieved.
    """
    out = list(text)
    for match in STRUCK.finditer(text):
        for index in range(match.start(), match.end()):
            if out[index] != chr(10):
                out[index] = " "
    return "".join(out)

#: Where a status claim can hide. `docs/decisions/` is excluded by the callers: a record narrating
#: its own or another's history at the time it was written is the one place the past tense is right.
CLAIM_ROOTS = ("src", "tools", "tests", "registry", "docs", "AGENTS.md", "HANDOFF.md", "TODO.md")

#: File kinds that carry prose in this repository.
SUFFIXES = frozenset({".py", ".md", ".yml"})


def claim_pattern(id_pattern: str, words: tuple[str, ...]) -> re.Pattern[str]:
    """`<id> is|was|remains|stays <word>`, and deliberately nothing looser.

    Only the copula forms, so a sentence NARRATING what a record did ("`DR-018` left the form for a
    study") is not read as a status claim. The id may carry a version suffix or backticks.
    """
    return re.compile(
        r"(" + id_pattern + r")(?:-v[\d.]+)?`?\s+(?:is|was|remains|stays)\s+`?("
        + "|".join(words) + r")\b",
        re.I,
    )


def files_to_read(repo: Path) -> list[Path]:
    """Every prose-carrying file under `CLAIM_ROOTS`, sorted so output is stable."""
    found: list[Path] = []
    for name in CLAIM_ROOTS:
        root = repo / name
        if root.is_file():
            found.append(root)
        elif root.is_dir():
            found += [f for f in root.rglob("*") if f.suffix in SUFFIXES]
    return sorted(found)


def line_of(text: str, start: int, end: int) -> tuple[int, str]:
    """The 1-based line number of a match, and the whole physical line it sits on."""
    number = text[:start].count(chr(10)) + 1
    body = text[:start].rsplit(chr(10), 1)[-1] + text[end:].split(chr(10), 1)[0]
    return number, body


def misstated(
    repo: Path,
    actual: dict[str, str],
    *,
    id_pattern: str,
    words: tuple[str, ...],
    caller: Path,
    skip_parts: tuple[str, ...] = ("docs", "decisions"),
) -> list[str]:
    """Every place outside the exemptions that states a status `actual` contradicts.

    `actual` maps id to the registry's own word. A claim about an id the registry does not know is
    not this check's business - it is either a typo another gate catches or a reference to something
    outside the registry, and guessing between those would be inventing a failure.
    """
    pattern = claim_pattern(id_pattern, words)
    failures: list[str] = []
    for path in files_to_read(repo):
        relative = path.relative_to(repo)
        if relative.parts[: len(skip_parts)] == skip_parts:
            continue
        if path.resolve() in {caller.resolve(), Path(__file__).resolve()}:
            continue
        text = without_struck(path.read_text(encoding="utf-8", errors="replace"))
        for match in pattern.finditer(text):
            found, said = match.group(1), match.group(2).lower()
            truth = actual.get(found)
            if truth is None or said == truth:
                continue
            number, body = line_of(text, match.start(), match.end())
            if EXAMPLE_MARKER in body:
                continue
            failures.append(
                f"{relative.as_posix()}:{number} says {found} is {said!r}; the registry says "
                f"{truth!r}. A status is what tells a reader whether anything is waiting on them."
            )
    return failures
