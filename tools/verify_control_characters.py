"""Gate 42: a control character in a tracked text file, which is what a mangled edit leaves behind.

**This gate exists because a RULE was not enough.** `AGENTS.md` §12 already says never to write a
backslash escape inside a heredoc, and records what it cost: gate 14's widened pattern was written
as `(\\d+)\\s+specified\\b`, reached Python as `specified\\x08` - a BACKSPACE, not a word boundary -
and the gate then ran, printed **0 failures**, and could never have matched anything. The rule was
read and broken again on 2026-09-04, by a session that had read it that morning: a patch script
piped through a heredoc turned `tools\\verify_...` into a VERTICAL TAB and truncated five commands in
`docs/runbooks/README.md`. An honour rule catches nothing on the day somebody is concentrating on
something else.

**So this gate checks the RESIDUE rather than the habit.** Every one of those accidents leaves the
same evidence: a C0 control byte in a file that should hold none. That is an exact token, which is
`AGENTS.md` §12's own standard for a gate over text - no prose is parsed and no judgement is made.

**What it does not do.** It has no opinion about how a file was edited, and it cannot see a mangled
edit that produced valid characters - a `\\n` that became a real newline is legal text and stays this
gate's blind spot. It catches the class that is silent, not the class that is loud.

Measured before shipping (`AGENTS.md` §12): **438 tracked text files, zero control bytes**, so the
gate ships with no exemption list and every future hit is a real one.

    python tools/verify_control_characters.py

Stdlib only.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: The C0 bytes a text file in this repository has no legitimate use for, by name so a failure says
#: what was found. TAB, LF and CR are absent deliberately: they are ordinary text here, and CRLF is
#: this repository's line ending on Windows.
FORBIDDEN = {
    0x00: "NUL", 0x01: "SOH", 0x02: "STX", 0x03: "ETX", 0x04: "EOT", 0x05: "ENQ", 0x06: "ACK",
    0x07: "BEL", 0x08: "BS (a `\\b` that reached the file as a backspace)", 0x0B: "VT",
    0x0C: "FF", 0x0E: "SO", 0x0F: "SI", 0x1A: "SUB", 0x1B: "ESC",
}

#: Suffixes whose bytes are not text and are never read as text by anything here.
BINARY = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".duckdb", ".gz", ".zip", ".xlsx", ".woff",
    ".woff2", ".ttf",
})


def tracked_text_files() -> list[Path] | None:
    """Every tracked file git knows about, less the ones that are not text.

    Read from git rather than walked, so an ignored artefact - a stray store, a `__pycache__` - can
    never fail a gate about the repository's own content. Returns `None` when git cannot answer,
    which the caller reports rather than treating as a clean tree.
    """
    try:
        done = subprocess.run(
            ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace",
        )
    except OSError:
        return None
    if done.returncode != 0:
        return None
    found = []
    for name in done.stdout.split("\n"):
        name = name.strip()
        if not name:
            continue
        path = REPO / name
        if path.suffix.lower() in BINARY or not path.is_file():
            continue
        found.append(path)
    return found


def offences(path: Path) -> list[tuple[int, str, int]]:
    """Every forbidden byte in one file, as (line number, name, byte)."""
    data = path.read_bytes()
    if not any(bytes([code]) in data for code in FORBIDDEN):
        return []
    found: list[tuple[int, str, int]] = []
    line = 1
    for byte in data:
        if byte == 0x0A:
            line += 1
        elif byte in FORBIDDEN:
            found.append((line, FORBIDDEN[byte], byte))
    return found


def main() -> int:
    files = tracked_text_files()
    if files is None:
        print("  control characters: DID NOT RUN - git could not list tracked files. This is not "
              "a clean result.")
        print("\ncontrol characters: not run")
        return 0

    failures: list[str] = []
    for path in files:
        for line, name, byte in offences(path):
            rel = path.relative_to(REPO).as_posix()
            failures.append(f"{rel}:{line}: {name}, byte 0x{byte:02x}")

    for failure in failures:
        print(f"  {failure}")
    if failures:
        print(
            "\n  A control byte in a text file is almost always a mangled EDIT rather than "
            "\n  something anybody typed - `AGENTS.md` §12: a heredoc eats one level of backslash, "
            "\n  so `\\b` arrives as a backspace and `\\v` as a vertical tab. Rewrite the file with "
            "\n  an editor tool, or write the patch script to disk and run it. Never pipe one "
            "\n  through a heredoc."
        )
    print(f"\ncontrol characters: {len(files)} tracked text file(s), {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
