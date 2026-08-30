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

Stdlib only.

    python tools/verify_decisions.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
DECISIONS = REPO / "docs" / "decisions"
HEADER = re.compile(r"^```\n(.*?)^```", re.MULTILINE | re.DOTALL)


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
    for record in sorted(DECISIONS.glob("DR-*.md")):
        fields = parse_header(record.read_text(encoding="utf-8"))
        status = fields.get("status", "")
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
        elif token not in target.read_text(encoding="utf-8", errors="replace"):
            failures.append(
                f"{rel}: {token!r} does not appear in {path_part.strip()} - the decision is "
                f"ratified but its implementation is absent"
            )

    for failure in failures:
        print(f"  {failure}")
    print(f"\ndecisions: {checked} accepted, {len(failures)} unverifiable")
    if awaiting:
        print(f"\n{len(awaiting)} record(s) still `proposed` - awaiting the owner, and not a "
              f"failure. Ratifying is the owner's act:")
        for name, status in awaiting:
            print(f"  {name:<44} {status}")
    if failures:
        print("\nAn accepted decision promises something. Name the file and token that prove it, "
              "or declare `implementation: none`.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
