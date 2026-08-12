"""Gate 19: nothing secret is tracked, and every documented "ignored" path really is ignored.

The defect this exists for, 2026-08-11. `DR-008` called `.swingdesk-local.json` "the ignored local
file". It was not in `.gitignore`. The decision asserted a property of the repository instead of
creating it, and no gate reads `.gitignore` - a document's claim about repository CONFIGURATION was
the one class of claim this project never checked.

It matters here more than it would elsewhere: the repository is PUBLIC. GitHub push protection is
enabled and catches recognised credential formats, but would not stop a local config carrying an
account number, because that matches no provider pattern.

Two checks, deliberately narrow so the gate is never noisy enough to bypass:

  1. No TRACKED file has a secret-shaped name. Tracked, not present - the filesystem may hold
     `.env`; the index may not.
  2. Any document asserting a backticked path is "ignored" or "local" must satisfy
     `git check-ignore`. Anchored to backticks so "whitespace is ignored" cannot trip it.

Stdlib only.

    python tools/verify_secrets.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

SECRET_PATTERNS: tuple[str, ...] = (
    r"(^|/)\.env($|\.)",
    r"\.pem$",
    r"\.key$",
    r"(^|/)credentials?($|[.-])",
    r"(^|/)secrets?($|[.-])",
    r"(^|/)\.swingdesk-local\.json$",
    r"_rsa$",
)

#: A document asserting a path is ignored or local. A backticked path is required.
IGNORE_CLAIM = re.compile(r"\b(?:ignored|local)\b[^`\n]{0,40}`([^`\n]+)`", re.IGNORECASE)
IGNORE_CLAIM_NOUN = re.compile(r"\b(?:file|path|config(?:uration)?|switch)\b", re.IGNORECASE)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True, encoding="utf-8")


def tracked_secrets(root: Path) -> list[str]:
    listing = _git(root, "ls-files")
    if listing.returncode != 0:
        return []
    return [path for path in listing.stdout.splitlines()
            if any(re.search(pattern, path, re.IGNORECASE) for pattern in SECRET_PATTERNS)]


def broken_ignore_claims(root: Path) -> list[str]:
    failures: list[str] = []
    for doc in sorted(root.rglob("*.md")):
        relative = doc.relative_to(root)
        if any(part.startswith(".") for part in relative.parts):
            continue
        for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for match in IGNORE_CLAIM.finditer(line):
                candidate = match.group(1).strip()
                claim = match.group(0)
                if (not IGNORE_CLAIM_NOUN.search(claim)
                        or any(mark in claim for mark in ",;:()")):
                    continue  # A nearby word, not an assertion that this path is local or ignored.
                if " " in candidate or ("/" not in candidate and "." not in candidate):
                    continue  # Backticked prose, not a path.
                if _git(root, "check-ignore", "-q", candidate).returncode != 0:
                    failures.append(
                        f"{doc.relative_to(root).as_posix()}:{number}: claims {candidate!r} is "
                        "ignored, but `git check-ignore` says it is not"
                    )
    return failures


def main() -> int:
    if _git(REPO, "rev-parse", "--git-dir").returncode != 0:
        print(f"not a git repository: {REPO}", file=sys.stderr)
        return 1

    secrets = tracked_secrets(REPO)
    claims = broken_ignore_claims(REPO)
    for path in secrets:
        print(f"  TRACKED and secret-shaped: {path}")
    for failure in claims:
        print(f"  {failure}")

    print(f"\nsecrets: {len(secrets)} tracked secret-shaped, {len(claims)} false ignore-claim(s)")
    if secrets:
        print("\n`git rm --cached` it, add the pattern to .gitignore, and rotate whatever it held. "
              "The repository is public.")
    if claims:
        print("\nAdd the path to .gitignore, or stop calling it ignored (AGENTS.md 1).")
    return 1 if (secrets or claims) else 0


if __name__ == "__main__":
    raise SystemExit(main())
