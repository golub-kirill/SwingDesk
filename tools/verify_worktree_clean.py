"""Gate 21 (advisory): finished work is not left sitting uncommitted.

Three incidents on 2026-08-11 trace to one condition - completed work uncommitted in the main
checkout:

  * `DR-008` was ratified but existed only as an untracked file, so no gate, no CI and no sibling
    worktree could see it. One trading day of survivorship evidence was lost permanently.
  * Twice, a `git add -A` in an unrelated change swept another effort's files into a commit that
    had nothing to do with them.

ADVISORY BY DESIGN: it prints and returns 0. This gate is red during ordinary editing, which is
exactly when someone reaches for a bypass - and a gate that blocks normal work gets disabled,
taking the credibility of the others with it. Visibility, not veto.

Stdlib only.

    python tools/verify_worktree_clean.py
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: Directories governed by a gate, a registry or a review rule. Uncommitted work here is work the
#: project's own machinery cannot see.
GOVERNED = ("docs/", "registry/", "src/", "tools/")


def stray_paths(root: Path) -> list[str]:
    """Return uncommitted paths that the project's controls govern."""
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        return []
    strays = []
    for line in result.stdout.splitlines():
        path = line[3:].strip().strip('"')
        if any(path.startswith(prefix) for prefix in GOVERNED):
            strays.append(f"{line[:2].strip() or '??'}  {path}")
    return strays


def main() -> int:
    """Print governed uncommitted paths without vetoing ordinary editing."""
    strays = stray_paths(REPO)
    for path in strays:
        print(f"  {path}")
    print(f"\nworktree: {len(strays)} stray path(s) under {', '.join(GOVERNED)}")
    if strays:
        print("Advisory. Commit them on their own branch, or know why they are staying. "
              "A `git add -A` will sweep them into whatever you commit next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
