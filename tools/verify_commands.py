"""Gate 31: a command a document tells you to run is a command that runs.

**What paid for it, 2026-08-25.** `HANDOFF.md` §2's generated census carries the row
*"Classifications ... derive it with `python tools/measure_sector_cap.py --wide`"*. That command
exits **2**: `--classifications` is `required=True` and there is no default. So the one promise §2
makes - that a reader derives the number instead of trusting the row - was unkeepable for whoever
tried, and the row had been generated that way by `tools/build_state.py` since the block was built.

Three of the five mentions of that tool in the tree were unrunnable, and the third is the finding:
`docs/07-ux/UX_TASK_FLOWS.md` got its copy by a session reading `HANDOFF.md` §2 and quoting it.
**A broken command propagates exactly like a stale count**, and `AGENTS.md` §10.5 already has the
answer for counts - one owner, and a gate. This is that gate for commands.

**Why nothing caught it.** Gate 3e resolves document *references*, gate 24 regenerates the block's
*numbers*. Neither reads the command line, and a command is neither a citation nor a count. It
looked checked from three directions and was checked from none - `AGENTS.md` §12's shape.

**Static only. It never imports and never executes a tool.** The tool's `add_argument` calls are
read out of its syntax tree, so a gate about running commands does not run any, and `CI_POLICY.md`
§4's no-network rule cannot be breached by it. That is also the honest limitation: this proves the
ARGUMENTS are accepted, never that the command succeeds. A tool whose data file is missing still
exits non-zero and this gate still passes - it is a spelling check on the invocation, not a smoke
test, and calling it more would be the `unavailable`-as-`pass` failure §12 names.

**What it checks, in the order a reader meets them:**

1. The tool named exists. A rename that misses a citation is otherwise silent across 90 mentions.
2. Every flag the document passes is a flag the tool declares. Catches a flag removed or renamed
   under a document that still names it.
3. Every `required=True` flag the tool declares appears in the command.

**The escape hatch, and why it must be written rather than inferred.** A document sometimes names a
command shape rather than an invocation. Marking the line `<!-- partial-command -->` says so, and it
is a claim the author makes on the record. Inferring "they probably meant a shape" is how a gate
learns to pass things.

    python tools/verify_commands.py
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: A `python tools/<name>.py` invocation and the arguments belonging to IT. Anchored on `python` so
#: prose naming a tool as a FILE (`tools/foo.py` in a sentence) is not read as an instruction to run
#: it - those are references and gate 3e's business.
#:
#: **Argument capture stops at a shell operator, and that is not a detail.** The first version ran
#: to end of line and read `verify_transcription.py && build_course_index.py --check-only` as
#: `verify_transcription.py --check-only` - reporting a flag against a tool that never received it,
#: in `AGENTS.md` §2 and `docs/README.md`, both of which were correct. A gate whose first run
#: produces two false positives teaches a reader to skim its output, which is how a real finding
#: gets skipped; `CI_POLICY.md` §3 records that cost. A trailing backslash still continues onto the
#: next line, because a wrapped command is one command.
#: **The interpreter is matched, not assumed to be the word `python`.** `docs/runbooks/README.md` is
#: read by an operator on this machine, where a bare `python` resolves to the Windows Store stub and
#: exits without running anything - so its commands name `.\.venv\Scripts\python.exe`, the same
#: interpreter `tools/daily_run.cmd` uses. Measured 2026-09-04: normalising the runbook onto that
#: form took this gate from 145 invocations to 134 **while it still reported zero failures**, which
#: is `AGENTS.md` §10.6 rule 2 exactly - a check that stopped seeing eleven of its subjects and said
#: nothing. Path separator too: a Windows line writes `tools\x.py`.
PYTHON = r"(?:python|[.\w\\/:-]*python(?:\.exe)?)(?:\s+-X\s+\w+)?"
INVOCATION = re.compile(
    PYTHON + r"\s+(tools[/\\][A-Za-z0-9_]+\.py)((?:\\\n|[^\n`&|;>])*)"
)

#: Flags a document may pass to any tool without the tool declaring them. `--help` is argparse's,
#: not the author's, and every parser has it.
UNIVERSAL = frozenset({"-h", "--help"})

#: The author's written claim that a line shows a command SHAPE and not an invocation.
PARTIAL = "<!-- partial-command -->"


def _tracked_markdown() -> list[Path]:
    """Tracked `.md` files. Untracked scratch is not the repository's problem."""
    result = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "*.md"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return sorted(REPO.rglob("*.md"))
    return [REPO / line for line in result.stdout.split() if line]


def declared_flags(tool: Path) -> tuple[frozenset[str], frozenset[str]]:
    """Every flag a tool declares, and the subset it declares `required`.

    Read from the syntax tree. Importing the module to inspect its parser would execute it, and a
    gate that executes the thing it is checking is a different gate with different risks.
    """
    try:
        tree = ast.parse(tool.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return frozenset(), frozenset()

    every: set[str] = set()
    required: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "add_argument":
            continue
        flags = [
            argument.value for argument in node.args
            if isinstance(argument, ast.Constant)
            and isinstance(argument.value, str)
            and argument.value.startswith("-")
        ]
        if not flags:
            # A positional. Named here rather than silently ignored: this gate does not check
            # positionals, and a tool that grows a required one is a hole in it.
            continue
        every.update(flags)
        is_required = any(
            keyword.arg == "required"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        )
        if is_required:
            # Any spelling satisfies it, so the whole alias group is one obligation.
            required.add("|".join(flags))
    return frozenset(every), frozenset(required)


def _flags_passed(arguments: str) -> list[str]:
    """The flags a document's command line passes, ignoring their values."""
    return re.findall(r"(?<!\S)(--?[A-Za-z][A-Za-z0-9-]*)", arguments)


def check(paths: list[Path]) -> tuple[list[str], int]:
    """Failures, and how many invocations were read in total."""
    failures: list[str] = []
    seen = 0
    for path in paths:
        try:
            body = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(REPO).as_posix()
        lines = body.splitlines()
        for match in INVOCATION.finditer(body):
            tool_name, arguments = match.group(1), match.group(2)
            number = body[:match.start()].count("\n") + 1
            # The claim must sit on the invocation's own line or the one above it, so it cannot be
            # made once at the top of a document and inherited by everything below.
            window = "\n".join(lines[max(0, number - 2):number])
            if PARTIAL in window:
                continue
            seen += 1

            tool = REPO / tool_name
            if not tool.is_file():
                failures.append(
                    f"{relative}:{number}: names `python {tool_name}`, which does not exist. "
                    f"A renamed tool leaves its citations pointing at nothing."
                )
                continue

            every, required = declared_flags(tool)
            passed = _flags_passed(arguments)
            for flag in passed:
                if flag in UNIVERSAL or flag in every:
                    continue
                failures.append(
                    f"{relative}:{number}: passes `{flag}` to `{tool_name}`, which does not "
                    f"declare it. The command exits 2 for whoever runs it."
                )
            for group in sorted(required):
                if not any(flag in passed for flag in group.split("|")):
                    failures.append(
                        f"{relative}:{number}: `python {tool_name}` is named without "
                        f"`{group}`, which the tool declares required. The command exits 2, so "
                        f"this document tells a reader to derive something they cannot."
                    )
    return failures, seen


def main() -> int:
    paths = _tracked_markdown()
    failures, seen = check(paths)
    for failure in failures:
        print(f"  {failure}")
    print(f"\ncommands: {seen} invocation(s) across {len(paths)} document(s), "
          f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
