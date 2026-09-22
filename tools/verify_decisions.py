"""Gate 20: an accepted decision record says what would prove it was carried out.

The defect this exists for, 2026-08-11: `DR-008` was ratified 2026-08-10, declared
`parameters: none`, and specified a collector with config gating, calendar eligibility, a response
cap, validation and audit rows. None of it was built, and the file was not even committed. One
trading day of unrecoverable survivorship evidence was lost because of it.

The root cause is narrow and worth stating exactly: the only decisions this project verifies are
the ones that set parameters. A parameter carries provenance `assumed:DR-nnn` and gate 1 checks
it, so a parameter-setting decision is bound to its effect automatically. A decision that changes
operational behaviour instead has no hook, and falls through by construction.

So an `accepted` record must carry one of:

    implemented_by: <path> :: <token>     the token must appear in that file
    implementation: none                  the decision changes no code, said out loud

`proposed` records are exempt. `implementation: none` is the obvious escape hatch and is
deliberately a claim a reader can challenge, sitting in the record's own header, rather than an
absence nobody notices.

**The token must appear in CODE, 2026-09-03.** Until today the check was `token not in
target.read_text()` - a plain substring test over the whole file, which a token in a **comment or a
docstring** satisfies. That is the difference between a decision that was implemented and one that
was merely written about, and this gate exists to tell those apart.

It was not hypothetical. `DR-011` declared `notify.py :: DR-011`, and `DR-011` appeared in that
file exactly twice, both times in prose. This gate reads only ACCEPTED records, and that
record was ratified on 2026-08-30 - so it passed on a citation of itself for the four days it
was subject to the check, having been exempt as a proposal for the fourteen before.

Found while auditing a test of mine that had the same defect: it asked whether a guard's NAME
appeared in a file, and a mutation that deleted the guard left the name in a heading beside it.

**Ordinary string literals still count**, and that is not laziness. `DR-006`'s token is
`MAX_OPEN_RISK = "risk.max_open_risk"` - a parameter key is real code, and a rule that stripped
every string would call the most precisely-cited record in the store unimplemented. Only comments
and **bare string statements** (a string that is an entire statement, which is what a docstring is)
are prose.

**Only `.py` targets are redacted.** A `#` in YAML is a comment and a `#` in a `.cmd` file is not;
guessing per format would put a guess inside a gate. Non-Python targets keep the whole-file test
they have always had.

Stdlib only.

    python tools/verify_decisions.py
"""

from __future__ import annotations

import io
import os
import re
import sys
import tokenize
from pathlib import Path

import status_claims

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
DECISIONS = REPO / "docs" / "decisions"
HEADER = re.compile(r"^```\n(.*?)^```", re.MULTILINE | re.DOTALL)


#: A string token is a DOCSTRING when it is an entire statement: nothing but a statement boundary
#: before it, nothing but the end of a statement after it. That covers module, class and function
#: docstrings and every bare string used as prose, and excludes `x = "text"` and `f("text")`, whose
#: neighbours are an operator and a bracket.
_STATEMENT_START = {tokenize.ENCODING, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT}
_STATEMENT_END = {tokenize.NEWLINE, tokenize.ENDMARKER}
_LAYOUT = {tokenize.COMMENT, tokenize.NL}


def code_of(source: str) -> str:
    """`source` with comments and docstrings blanked out, every other character left in place.

    **Blanked, not removed, and never rebuilt from the token stream** - the first version of this
    joined the surviving tokens and reported nineteen records unimplemented, including `DR-015`'s
    `def assess`, because `def` and `assess` were no longer adjacent. A gate whose failure list is
    an artefact of its own parser is worse than the weakness it replaced. Blanking preserves every
    offset, so a multi-word token matches exactly as it did before, and a caller can compare lengths
    to prove the redaction ran at all.

    Returns the source unchanged if it will not tokenize. This gate reports on decision records; a
    syntax error in a target is another gate's failure, and swallowing it here would be a second.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    # Measured, rather than guessed at: an unclosed bracket and an unterminated string give
    # `TokenError`, a dedent to no matching level gives `IndentationError`, and a stray
    # bracket or a bad indent tokenizes cleanly - `tokenize` is a lexer and does not parse.
    # `IndentationError` is a `SyntaxError`, so two names cover every case there is, and
    # each has a fixture below it in `tests/test_gates.py`.
    except (tokenize.TokenError, SyntaxError):
        return source

    following: dict[int, int | None] = {}
    later: int | None = None
    for index in range(len(tokens) - 1, -1, -1):
        following[index] = later
        if tokens[index].type not in _LAYOUT:
            later = tokens[index].type

    spans: list[tuple[tuple[int, int], tuple[int, int]]] = []
    previous = tokenize.ENCODING
    for index, token in enumerate(tokens):
        if token.type == tokenize.COMMENT:
            spans.append((token.start, token.end))
            continue
        if (token.type == tokenize.STRING and previous in _STATEMENT_START
                and following[index] in _STATEMENT_END):
            spans.append((token.start, token.end))
        if token.type not in _LAYOUT:
            previous = token.type

    lines = [list(line) for line in source.splitlines(keepends=True)]
    for (start_row, start_col), (end_row, end_col) in spans:
        for row in range(start_row, end_row + 1):
            if row > len(lines):
                break
            characters = lines[row - 1]
            last = end_col if row == end_row else len(characters)
            for column in range(start_col if row == start_row else 0,
                                min(last, len(characters))):
                # Whitespace is left alone: blanking a newline would JOIN two lines and could
                # manufacture a match that the file does not contain.
                if not characters[column].isspace():
                    characters[column] = " "
    return "".join("".join(line) for line in lines)


#: The index `docs/decisions/README.md` section 5 carries, one row per record.
INDEX = DECISIONS / "README.md"
INDEX_ROW = re.compile(r"^\| `(DR-\d+)` \|")

#: The words a status may begin with. A row states its verdict in prose, so this looks for the word
#: rather than for an exact string - the prose beside it is the point of the row.
STATUSES = ("accepted", "superseded", "proposed")


def index_statuses(text: str) -> dict[str, str]:
    """The status word each index row claims, by record id."""
    rows: dict[str, str] = {}
    for line in text.splitlines():
        match = INDEX_ROW.match(line)
        if not match:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        claimed = cells[-1].lower() if cells else ""
        rows[match.group(1)] = next((word for word in STATUSES if word in claimed), claimed[:40])
    return rows


def disagreements(records: dict[str, str], rows: dict[str, str]) -> list[str]:
    """Where the index and the records would tell an owner different things.

    **Measured 2026-09-15, and it cost a wrong answer to the owner.** `DR-003` and `DR-006` had read
    `accepted` in their own headers since August; the index still said `proposed`, one of them
    `proposed - binds a real account`. Asked what was waiting on them, this project answered from
    the index and named two decisions they had already made. Gate 20 read every record header and
    never the table a person actually reads.
    """
    failures: list[str] = []
    for record, status in sorted(records.items()):
        word = next((candidate for candidate in STATUSES if status.startswith(candidate)), status)
        claimed = rows.get(record)
        if claimed is None:
            failures.append(
                f"{record} has no row in {INDEX.name} section 5. A record the index does not carry "
                f"is a record nobody finds."
            )
        elif claimed != word:
            failures.append(
                f"{record}: the record says {word!r} and {INDEX.name} says {claimed!r}. The table "
                f"is what an owner is shown when they ask what is still waiting on them."
            )
    for record in sorted(set(rows) - set(records)):
        failures.append(f"{INDEX.name} carries a row for {record}, which has no record file")
    return failures


def misstated_elsewhere(records: dict[str, str]) -> list[str]:
    """Every file outside `docs/decisions/` that states a status the record contradicts.

    **Measured 2026-09-21, three places, all of them live.**
    `validation/backtest/fees.py` said `DR-039` carried the status `proposed` and used it as the
    REASON nothing charges the venue's regulatory fees - sixteen days after the owner ratified it, so
    a reader deciding whether to wire them was told the rates were still unsettled when only the
    wiring decision was. `TODO.md` said the same of `DR-040` and `DR-009`, both ratified 2026-09-14.

    `disagreements` above already holds the INDEX to each record; this holds the rest of the tree to
    it, and for the same reason. The rule, the exemptions and the line arithmetic live in
    `status_claims.py` because `verify_components.py` needs the identical check over component
    activation, and a second copy is a second place for the `~~struck~~` handling to be forgotten.
    """
    words = tuple(STATUSES)
    return status_claims.misstated(
        REPO,
        {record: next((c for c in STATUSES if status.startswith(c)), status)
         for record, status in records.items()},
        id_pattern=r"DR-\d+",
        words=words,
        caller=Path(__file__),
    )


def parse_header(text: str) -> dict[str, str]:
    """Return the fenced `key: value` block at the top of a decision record."""
    match = HEADER.search(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip().lower()] = value.strip()
    return fields


def main() -> int:
    """Verify every accepted record names its implementation evidence."""
    if not DECISIONS.is_dir():
        print(f"no docs/decisions under {REPO}", file=sys.stderr)
        return 1

    failures: list[str] = []
    checked = 0
    awaiting: list[tuple[str, str]] = []
    statuses: dict[str, str] = {}
    for record in sorted(DECISIONS.glob("DR-*.md")):
        fields = parse_header(record.read_text(encoding="utf-8"))
        status = fields.get("status", "")
        statuses[record.name[:6]] = status
        if status.startswith("proposed"):
            # A standing measurement, never a failure: ratifying is the owner's act and this gate
            # has no opinion about when. It is printed because nothing derived it, and `HANDOFF.md`
            # section 5 carried a hand-typed list saying "these five are the whole of what is
            # blocked on a human" while `docs/decisions/` held twelve. `AGENTS.md` 10.5 gives a
            # measured COUNT one owner; a STATUS had none, and this is that answer for this one.
            awaiting.append((record.stem, status))
        if not status.startswith("accepted"):
            continue
        checked += 1
        rel = record.relative_to(REPO).as_posix()

        if fields.get("implementation") == "none":
            continue

        marker = fields.get("implemented_by")
        if not marker:
            failures.append(
                f"{rel}: status {status!r} but the header declares neither "
                f"`implemented_by: <path> :: <token>` nor `implementation: none`"
            )
            continue

        path_part, _, token = marker.partition("::")
        target = REPO / path_part.strip()
        token = token.strip()
        if not token:
            failures.append(f"{rel}: implemented_by has no `:: <token>` to look for")
        elif not target.is_file():
            failures.append(f"{rel}: implemented_by names {path_part.strip()!r}, which does not exist")
        else:
            source = target.read_text(encoding="utf-8", errors="replace")
            code = code_of(source) if target.suffix == ".py" else source
            if token not in source:
                failures.append(
                    f"{rel}: {token!r} does not appear in {path_part.strip()} - the decision is "
                    f"ratified but its implementation is absent"
                )
            elif token not in code:
                failures.append(
                    f"{rel}: {token!r} appears in {path_part.strip()} only inside a COMMENT or a "
                    f"DOCSTRING - the file talks about the decision rather than carrying it out. "
                    f"Point the marker at code, or declare `implementation: none`"
                )

    # The index last, and counted apart: it is a claim ABOUT the records rather than one of them,
    # and the two failures ask for different repairs.
    stale = disagreements(
        statuses, index_statuses(INDEX.read_text(encoding="utf-8")) if INDEX.is_file() else {})
    stale += misstated_elsewhere(statuses)

    for failure in failures + stale:
        print(f"  {failure}")
    print(f"\ndecisions: {checked} accepted, {len(failures)} unverifiable, "
          f"{len(stale)} index row(s) disagreeing")
    if awaiting:
        print(f"\n{len(awaiting)} record(s) still `proposed` - awaiting the owner, and not a "
              f"failure. Ratifying is the owner's act:")
        for name, status in awaiting:
            print(f"  {name:<44} {status}")
    if failures:
        print("\nAn accepted decision promises something. Name the file and token that prove it, "
              "or declare `implementation: none`.")
    if stale:
        print("\nThe index is the answer an owner gets when they ask what is waiting on them. "
              "Correct the row; the record itself is immutable once accepted.")
    failures += stale
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
