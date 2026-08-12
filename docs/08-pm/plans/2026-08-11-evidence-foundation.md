# Evidence Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop losing unrecoverable survivorship evidence, and close the three structural holes that let a ratified decision ship unimplemented, uncommitted, and asserting a false fact about the repository.

**Architecture:** Four gates and one collector. The gates extend `tools/check_gates.py`'s existing pattern — a standalone stdlib script per gate, registered in the runner's `results` mapping, tested for its ability to fail in `tests/test_gates.py` against fixture trees pointed at by `SWINGDESK_ROOT`. The collector is a `tools/` network script, never imported by `src/`, never run in CI.

**Tech Stack:** Python 3.14, stdlib only for gates (PyYAML permitted where a registry is read), pytest, DuckDB via the existing `DirectoryStore`.

## Global Constraints

- **The daily-run code path is FROZEN** until the Track A counter reaches 5 clean consecutive scheduled runs. Frozen files: `tools/daily_run.cmd`, `src/swingdesk/application/pipeline.py`, `src/swingdesk/trade_management/sizing.py`. Task 5 is the single validated exception and states its proof.
- **A gate that is wrong gets fixed or removed, never skipped.** There is no `--skip` flag.
- **Measured counts live in `HANDOFF.md` §2 and nowhere else** (AGENTS.md §10.5). Any task that changes a count updates §2 only.
- **English throughout** in docs, code and generated output.
- **No network calls in `src/`.** Network tools live in `tools/` and never run in CI.
- **Gates are stdlib-only where possible**; PyYAML is the single permitted non-stdlib dependency in `tools/`.
- Every new gate MUST have a test that proves it goes red, against a fixture tree, using `SWINGDESK_ROOT`. A gate nobody has seen fail is untested.
- Commit after each task. Branch from `master`; `master` is protected and requires the `gates` check.

---

## File Structure

| File | Responsibility |
|---|---|
| `tools/verify_decisions.py` | **Gate 19.** Every accepted decision record declares a verifiable implementation, or explicitly declares none. |
| `tools/verify_worktree_clean.py` | **Gate 20.** No finished work sits uncommitted or untracked in governed directories. |
| `tools/verify_secrets.py` | **Gate 21.** No tracked file looks like a secret; every documented "ignored" path really is ignored. |
| `tools/fetch_directory.py` | **Modified.** Local-config gating, NYSE eligibility, response cap, emergency repull. |
| `tools/check_gates.py` | **Modified.** Register gates 19, 20, 21. |
| `tests/test_gates.py` | **Modified.** Fail-proof tests for each new gate. |
| `docs/decisions/DR-008-directory-automation.md` | **Modified.** Amended down to what is actually built, or `implemented_by` added. |
| `.gitignore` | **Modified.** Secret patterns broadened. |

---

## Task 1: Gate 21 — secret hygiene and ignore-claim verification

Build this first. It is the only task whose absence is a *public* risk, and the repository is public.

**Files:**
- Create: `tools/verify_secrets.py`
- Modify: `.gitignore`
- Modify: `tools/check_gates.py`
- Test: `tests/test_gates.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `SECRET_PATTERNS: tuple[str, ...]`, `tracked_secrets(root: Path) -> list[str]`, `broken_ignore_claims(root: Path) -> list[str]`. Task 2 does not depend on these.

**Why this is right:** the defect was DR-008 calling `.swingdesk-local.json` "the ignored local file" when it was not ignored. GitHub push protection is enabled and catches known credential *formats*, but would not catch a local config carrying an account number. `.gitignore` is the only load-bearing configuration in this repo that is hand-maintained and unverified.

**What would make this wrong:** if the ignore-claim regex is so broad it matches prose like "this output is ignored by the parser", the gate becomes noisy and gets bypassed. Keep the pattern anchored to backticked paths.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gates.py

def _secrets_tree(tmp_path: Path, gitignore: str, doc: str = "") -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / ".gitignore").write_text(gitignore, encoding="utf-8")
    if doc:
        (tmp_path / "docs" / "NOTES.md").write_text(doc, encoding="utf-8")
    for args in (["init", "-b", "main"], ["add", "-A"],
                 ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "fixture"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True, check=True)
    return tmp_path


def test_secret_gate_catches_a_document_claiming_an_unignored_path_is_ignored(tmp_path: Path) -> None:
    root = _secrets_tree(tmp_path, "docs/build/\n",
                         "The collector reads the ignored local file `.swingdesk-local.json`.\n")
    code, out = run_gate("verify_secrets.py", root)
    assert code == 1
    assert ".swingdesk-local.json" in out
    assert "not ignored" in out


def test_secret_gate_accepts_a_true_ignore_claim(tmp_path: Path) -> None:
    root = _secrets_tree(tmp_path, ".swingdesk-local.json\n",
                         "The collector reads the ignored local file `.swingdesk-local.json`.\n")
    code, out = run_gate("verify_secrets.py", root)
    assert code == 0, out


def test_secret_gate_catches_a_tracked_file_that_looks_like_a_secret(tmp_path: Path) -> None:
    root = _secrets_tree(tmp_path, "docs/build/\n")
    (root / ".env").write_text("BROKER_TOKEN=abc123\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-f", ".env"], capture_output=True, check=True)
    code, out = run_gate("verify_secrets.py", root)
    assert code == 1
    assert ".env" in out


def test_secret_gate_does_not_flag_prose_without_a_backticked_path(tmp_path: Path) -> None:
    """A noisy gate gets bypassed. 'ignored' in ordinary prose must not trip it."""
    root = _secrets_tree(tmp_path, "docs/build/\n",
                         "Whitespace is ignored by the parser, and the header is ignored too.\n")
    code, out = run_gate("verify_secrets.py", root)
    assert code == 0, out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_gates.py -q -k secret_gate`
Expected: FAIL — `verify_secrets.py` does not exist, so `run_gate` returns a non-zero code with a "can't open file" message rather than the asserted text.

- [ ] **Step 3: Write the gate**

```python
# tools/verify_secrets.py
"""Gate 21: nothing secret is tracked, and every documented "ignored" path really is ignored.

The defect this exists for, 2026-08-11: `DR-008` called `.swingdesk-local.json` "the ignored local
file". It was not in `.gitignore`. The decision asserted a property of the repository instead of
creating it, and no gate reads `.gitignore` - so a document's claim about repository configuration
was the one class of claim this project never checked.

That matters more here than it would elsewhere: the repository is PUBLIC. GitHub push protection is
enabled and catches recognised credential formats, but it would not stop a local config file
carrying an account number, because that matches no provider pattern.

Two checks, deliberately narrow so the gate is never noisy enough to bypass:

  1. No TRACKED file matches a secret-shaped name. Tracked, not present - the filesystem is allowed
     to hold `.env`; the index is not.
  2. Any document asserting a backticked path is "ignored" or "local" must satisfy `git
     check-ignore`. Anchored to backticks so prose like "whitespace is ignored" cannot trip it.

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

#: Secret-shaped names. Matched against tracked paths, case-insensitively.
SECRET_PATTERNS: tuple[str, ...] = (
    r"(^|/)\.env($|\.)",
    r"\.pem$",
    r"\.key$",
    r"(^|/)credentials?($|[.-])",
    r"(^|/)secrets?($|[.-])",
    r"\.local\.json$",
    r"(^|/)\.swingdesk-local\.json$",
    r"_rsa$",
)

#: A document asserting a path is ignored or local. Backticked path required.
IGNORE_CLAIM = re.compile(r"\b(?:ignored|local)\b[^`\n]{0,40}`([^`\n]+)`", re.IGNORECASE)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, encoding="utf-8")


def tracked_secrets(root: Path) -> list[str]:
    """Tracked paths whose NAME looks like a secret."""
    listing = _git("ls-files")
    if listing.returncode != 0:
        return []
    found = []
    for path in listing.stdout.splitlines():
        if any(re.search(p, path, re.IGNORECASE) for p in SECRET_PATTERNS):
            found.append(path)
    return found


def broken_ignore_claims(root: Path) -> list[str]:
    """Documents claiming a path is ignored when `git check-ignore` disagrees."""
    failures: list[str] = []
    for doc in sorted(root.rglob("*.md")):
        if ".git" in doc.parts:
            continue
        for line_number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for match in IGNORE_CLAIM.finditer(line):
                candidate = match.group(1).strip()
                # Only paths, not prose in backticks. A path has no spaces and looks like a file.
                if " " in candidate or "/" not in candidate and "." not in candidate:
                    continue
                if _git("check-ignore", "-q", candidate).returncode != 0:
                    rel = doc.relative_to(root).as_posix()
                    failures.append(
                        f"{rel}:{line_number}: claims {candidate!r} is ignored/local, but "
                        f"`git check-ignore` says it is not ignored"
                    )
    return failures


def main() -> int:
    if _git("rev-parse", "--git-dir").returncode != 0:
        print(f"not a git repository: {REPO}", file=sys.stderr)
        return 1

    secrets = tracked_secrets(REPO)
    claims = broken_ignore_claims(REPO)

    for path in secrets:
        print(f"  TRACKED and secret-shaped: {path}")
    for failure in claims:
        print(f"  {failure}")

    print(f"\nsecrets: {len(secrets)} tracked secret-shaped file(s), "
          f"{len(claims)} false ignore-claim(s)")
    if secrets:
        print("\nRemove it from the index (`git rm --cached`), add the pattern to .gitignore, and "
              "rotate anything it contained. The repository is public.")
    if claims:
        print("\nAdd the path to .gitignore, or stop calling it ignored. A document asserting a "
              "repository property must be true (AGENTS.md 1).")
    return 1 if (secrets or claims) else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_gates.py -q -k secret_gate`
Expected: PASS.

- [ ] **Step 5: Broaden `.gitignore`**

Append to the existing `# secrets` section:

```
.env.*
*.pem
credentials*
secrets.*
*.local.json
*_rsa
```

- [ ] **Step 6: Register the gate**

In `tools/check_gates.py`, add to the `results` mapping after `"18 lock current"`:

```python
        "21 secret hygiene": _run("no tracked secrets, no false ignore claims",
                               [python, "tools/verify_secrets.py"]),
```

- [ ] **Step 7: Run the gate against the real tree, then the full suite**

Run: `python tools/verify_secrets.py`
Expected: PASS — verified 2026-08-11 that nothing secret is tracked and nothing secret appears in history.

Run: `python tools/check_gates.py`
Expected: all pass. If gate 14 reports a stale gate count, update **`HANDOFF.md` §2 only**.

- [ ] **Step 8: Commit**

```bash
git add tools/verify_secrets.py tools/check_gates.py tests/test_gates.py .gitignore HANDOFF.md
git commit -m "gate 21: a document claiming a path is ignored must be telling the truth"
```

---

## Task 2: Gate 19 — a decision record declares its implementation

**Files:**
- Create: `tools/verify_decisions.py`
- Modify: `docs/decisions/*.md` (add one header field to each)
- Modify: `tools/check_gates.py`
- Test: `tests/test_gates.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `HEADER_FIELD = "implemented_by"`, `parse_header(text: str) -> dict[str, str]`.

**Why this is right — the 5-whys root cause:** the only decisions this project verifies are those that set parameters, because a parameter carries provenance `assumed:DR-nnn` and gate 1 checks it. `DR-008` declares `parameters: none`, so it had no hook at all: it was ratified, unimplemented, and not even committed to git until 2026-08-11.

**What would make this wrong:** if `implementation: none` becomes the default anyone writes to get green, the gate is theatre. Mitigation: the field is required to be one of two explicit values, and the marker form must name a path that exists *and* a token found in it — a claim that can fail.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gates.py

def _decisions_tree(tmp_path: Path, header: str, *, marker_file: str = "",
                    marker_body: str = "") -> Path:
    (tmp_path / "docs" / "decisions").mkdir(parents=True)
    (tmp_path / "docs" / "decisions" / "DR-001-fixture.md").write_text(
        f"# DR-001: fixture\n\n```\n{header}\n```\n\nBody.\n", encoding="utf-8")
    if marker_file:
        target = tmp_path / marker_file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(marker_body, encoding="utf-8")
    return tmp_path


def test_decision_gate_catches_an_accepted_record_with_no_implementation_field(tmp_path: Path) -> None:
    """DR-008 in miniature: ratified, and nothing says what would prove it was done."""
    root = _decisions_tree(tmp_path, "date: 2026-08-01\nstatus: accepted\nparameters: none")
    code, out = run_gate("verify_decisions.py", root)
    assert code == 1
    assert "implemented_by" in out


def test_decision_gate_catches_a_marker_that_is_not_present(tmp_path: Path) -> None:
    root = _decisions_tree(
        tmp_path,
        "date: 2026-08-01\nstatus: accepted\nimplemented_by: tools/run.cmd :: fetch_directory.py",
        marker_file="tools/run.cmd", marker_body="echo nothing here\n")
    code, out = run_gate("verify_decisions.py", root)
    assert code == 1
    assert "fetch_directory.py" in out


def test_decision_gate_accepts_a_marker_that_is_present(tmp_path: Path) -> None:
    root = _decisions_tree(
        tmp_path,
        "date: 2026-08-01\nstatus: accepted\nimplemented_by: tools/run.cmd :: fetch_directory.py",
        marker_file="tools/run.cmd", marker_body="python tools/fetch_directory.py --data data\n")
    code, out = run_gate("verify_decisions.py", root)
    assert code == 0, out


def test_decision_gate_accepts_an_explicit_none(tmp_path: Path) -> None:
    """A convention decision changes no code. Saying so explicitly is the point."""
    root = _decisions_tree(tmp_path,
                           "date: 2026-08-01\nstatus: accepted\nimplementation: none")
    code, out = run_gate("verify_decisions.py", root)
    assert code == 0, out


def test_decision_gate_ignores_a_proposed_record(tmp_path: Path) -> None:
    """Only ACCEPTED records make a promise. A proposal is still a question."""
    root = _decisions_tree(tmp_path, "date: 2026-08-01\nstatus: proposed\nparameters: none")
    code, out = run_gate("verify_decisions.py", root)
    assert code == 0, out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_gates.py -q -k decision_gate`
Expected: FAIL — `verify_decisions.py` does not exist.

- [ ] **Step 3: Write the gate**

```python
# tools/verify_decisions.py
"""Gate 19: an accepted decision record says what would prove it was carried out.

The defect this exists for, 2026-08-11. `DR-008` was ratified 2026-08-10, declared
`parameters: none`, and specified a collector with local-config gating, NYSE eligibility, a
response cap, validation and audit rows. None of it was built. The file was not even committed.
A ratified decision sat unimplemented and invisible, and one trading day of unrecoverable
survivorship evidence was lost because of it.

The root cause is narrow and worth stating exactly: **the only decisions this project verifies are
the ones that set parameters.** A parameter carries provenance `assumed:DR-nnn` and gate 1 checks
it, so a parameter-setting decision is automatically bound to its effect. A decision that changes
operational behaviour instead has no hook, and falls through by construction.

So an `accepted` record must carry one of:

    implemented_by: <path> :: <token>     the token must appear in that file
    implementation: none                  the decision changes no code, said out loud

`proposed` records are exempt - a proposal has promised nothing yet.

`implementation: none` is the obvious escape hatch, and it is deliberately narrow: it is a claim a
reader can challenge, sitting in the record's own header, rather than an absence nobody notices.

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
    """The fenced `key: value` block at the top of a decision record."""
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
    if not DECISIONS.is_dir():
        print(f"no docs/decisions under {REPO}", file=sys.stderr)
        return 1

    failures: list[str] = []
    checked = 0
    for record in sorted(DECISIONS.glob("DR-*.md")):
        fields = parse_header(record.read_text(encoding="utf-8"))
        status = fields.get("status", "")
        if not status.startswith("accepted"):
            continue
        checked += 1
        rel = record.relative_to(REPO).as_posix()

        if fields.get("implementation") == "none":
            continue

        marker = fields.get("implemented_by")
        if not marker:
            failures.append(
                f"{rel}: status is {status!r} but the header declares neither "
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
    if failures:
        print("\nAn accepted decision promises something. Name the file and token that prove it, "
              "or declare `implementation: none`.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_gates.py -q -k decision_gate`
Expected: PASS.

- [ ] **Step 5: Run against the real tree and read what it says**

Run: `python tools/verify_decisions.py`
Expected: FAIL, naming every accepted record. `DR-007` and `DR-008` are accepted today. This failure is the gate working — do not weaken it.

- [ ] **Step 6: Add the field to each accepted record**

For records that set parameters, the honest marker is the registry and the provenance token:

```
implemented_by: registry/parameters.yml :: assumed:DR-007
```

For `DR-001` (Sharpe convention) and similar convention decisions that change no code, add:

```
implementation: none
```

Leave `DR-008` failing. Task 4 resolves it, and a red gate is the correct record of its state until then. If the suite must be green to commit, mark `DR-008` `status: accepted — implementation outstanding` and add `implementation: none` only if Task 4 concludes the collector will not be built.

- [ ] **Step 7: Register the gate and run the suite**

```python
        "19 decisions implemented": _run("accepted decisions declare what proves them",
                                      [python, "tools/verify_decisions.py"]),
```

Run: `python tools/check_gates.py`

- [ ] **Step 8: Commit**

```bash
git add tools/verify_decisions.py tools/check_gates.py tests/test_gates.py docs/decisions/ HANDOFF.md
git commit -m "gate 19: a ratified decision names what would prove it happened"
```

---

## Task 3: Gate 20 — no finished work sitting uncommitted

**Files:**
- Create: `tools/verify_worktree_clean.py`
- Modify: `tools/check_gates.py`
- Test: `tests/test_gates.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `GOVERNED = ("docs/", "registry/", "src/", "tools/")`, `stray_paths(root: Path) -> list[str]`.

**Why this is right:** three separate incidents on 2026-08-11 trace to finished work sitting uncommitted in the main checkout — the lost directory day, and twice a `git add -A` sweeping another effort's files into an unrelated commit. This is also the condition `AGENTS.md` §10.1 warns about from the other direction.

**What would make this wrong:** this gate is red during normal editing, which is exactly when someone reaches for a bypass. It must therefore be **advisory in the runner** — printed loudly, never failing the build. The value is the visibility, not the veto. A gate that blocks ordinary work is one that gets disabled and takes the others' credibility with it.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gates.py

def test_worktree_gate_reports_untracked_governed_files(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "orphan.md").write_text("finished work nobody committed\n", encoding="utf-8")
    for args in (["init", "-b", "main"],
                 ["-c", "user.email=t@t", "-c", "user.name=t", "commit",
                  "--allow-empty", "-m", "base"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True, check=True)
    code, out = run_gate("verify_worktree_clean.py", tmp_path)
    assert code == 0, "advisory only - it must never fail the build"
    assert "docs/orphan.md" in out


def test_worktree_gate_is_silent_on_a_clean_tree(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "kept.md").write_text("committed\n", encoding="utf-8")
    for args in (["init", "-b", "main"], ["add", "-A"],
                 ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "base"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True, check=True)
    code, out = run_gate("verify_worktree_clean.py", tmp_path)
    assert code == 0
    assert "0 stray" in out


def test_worktree_gate_ignores_paths_outside_governed_directories(tmp_path: Path) -> None:
    (tmp_path / "scratch.txt").write_text("not governed\n", encoding="utf-8")
    for args in (["init", "-b", "main"],
                 ["-c", "user.email=t@t", "-c", "user.name=t", "commit",
                  "--allow-empty", "-m", "base"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True, check=True)
    code, out = run_gate("verify_worktree_clean.py", tmp_path)
    assert "0 stray" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_gates.py -q -k worktree_gate`
Expected: FAIL — the script does not exist.

- [ ] **Step 3: Write the gate**

```python
# tools/verify_worktree_clean.py
"""Gate 20 (advisory): finished work is not left sitting uncommitted.

Three separate incidents on 2026-08-11 trace to one condition - completed work sitting uncommitted
in the main checkout:

  * `DR-008` was ratified but existed only as an untracked file, so no gate, no CI and no sibling
    worktree could see it. One trading day of unrecoverable survivorship evidence was lost.
  * Twice, a `git add -A` in an unrelated change swept another effort's files into a commit that
    had nothing to do with them.

ADVISORY BY DESIGN. It prints and returns 0. This gate is red during ordinary editing, which is
precisely when someone reaches for a bypass - and a gate that blocks normal work gets disabled,
taking the credibility of the other gates with it. The value here is visibility, not veto.

Stdlib only.

    python tools/verify_worktree_clean.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: Directories whose contents are governed by a gate, a registry or a review rule. Work left
#: uncommitted here is work the project's own machinery cannot see.
GOVERNED = ("docs/", "registry/", "src/", "tools/")


def stray_paths(root: Path) -> list[str]:
    """Modified-but-uncommitted and untracked paths under governed directories."""
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        return []
    paths = []
    for line in result.stdout.splitlines():
        path = line[3:].strip().strip('"')
        if any(path.startswith(prefix) for prefix in GOVERNED):
            paths.append(f"{line[:2].strip() or '??'}  {path}")
    return paths


def main() -> int:
    strays = stray_paths(REPO)
    for path in strays:
        print(f"  {path}")
    print(f"\nworktree: {len(strays)} stray path(s) under {', '.join(GOVERNED)}")
    if strays:
        print("Advisory. Commit them on their own branch, or know why they are staying. "
              "A `git add -A` here will sweep them into whatever you commit next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_gates.py -q -k worktree_gate`
Expected: PASS.

- [ ] **Step 5: Register the gate**

```python
        "20 worktree clean": _run("no finished work left uncommitted (advisory)",
                               [python, "tools/verify_worktree_clean.py"]),
```

- [ ] **Step 6: Run the full suite and commit**

```bash
python tools/check_gates.py
git add tools/verify_worktree_clean.py tools/check_gates.py tests/test_gates.py HANDOFF.md
git commit -m "gate 20: finished work left uncommitted is work no gate can see"
```

---

## Task 4: Decide DR-008's real scope, then build it

**Files:**
- Modify: `docs/decisions/DR-008-directory-automation.md`
- Modify: `tools/fetch_directory.py`
- Test: `tests/test_directory.py`

**Interfaces:**
- Consumes: `DirectoryStore` from `swingdesk.reference_data.directory` (existing), `swingdesk.reference_data.calendar` (existing).
- Produces: `collection_enabled(root: Path) -> bool`, `eligible_today(now: datetime) -> bool`, `MAX_RESPONSE_BYTES = 2 * 1024 * 1024`.

**The decision this task opens with — do not skip it.** `DR-008` specifies a collector that does not exist. `tools/fetch_directory.py` is 76 lines: it downloads two files and records a snapshot. It has no local-config gating, no `--emergency-repull`, no NYSE-calendar eligibility, no 2 MiB response cap, no validation/checksum/audit rows and no supersession records.

Two honest routes, and the wrong move is to build all of it because a ratified document says so:

- **(A) Amend `DR-008` down** to what the existing collector does plus config gating and the response cap, and record the amendment with its reason. Smaller, honest, and the evidence keeps accruing tomorrow.
- **(B) Build the full specification.** Correct if the audit trail is genuinely needed; it is several days of work, and each day costs one unrecoverable trading day of departures.

**Recommended: (A).** The irreversible thing is the *snapshot*, not the audit row. A day of departures cannot be re-fetched at any price; an audit trail can be added later over data already collected. `AGENTS.md` §11 governs amending a ratified record — amend visibly, never edit silently.

**What would make this wrong:** if the collector runs unattended and its failures are silent, an amended-down version loses the one property the full spec was protecting. Mitigation: the sidecar writes its result to the same `data/daily_run.log` the scan writes to, so a failure is visible in the file the owner already reads.

- [ ] **Step 1: Amend DR-008 visibly**

Add to the record, above `## Decision`:

```markdown
## Amendment 2026-08-11 — scope reduced to what will actually run

Ratified 2026-08-10 and NOT implemented. The collector described below did not exist: on
2026-08-11 `tools/fetch_directory.py` was 76 lines with no config gating, no emergency repull, no
calendar eligibility, no response cap and no audit rows. The 2026-08-10 trading day was lost as a
result, permanently.

This amendment reduces the decision to what will run this week, because the irreversible asset is
the SNAPSHOT and not the audit trail. A missed day of departures cannot be re-fetched at any
price; an audit row can be added later over data already collected.

**Retained:** local-config gating, NYSE eligibility, the 2 MiB response cap, the sidecar exit-code
guarantee.
**Deferred, with no date:** `--emergency-repull`, supersession records, checksum storage and the
compact audit row. They return when something needs them, per demand-driven coverage.
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_directory.py

def test_collection_is_disabled_without_the_local_file(tmp_path: Path) -> None:
    from fetch_directory import collection_enabled
    assert collection_enabled(tmp_path) is False


def test_collection_is_disabled_when_the_flag_is_false(tmp_path: Path) -> None:
    from fetch_directory import collection_enabled
    (tmp_path / ".swingdesk-local.json").write_text('{"directory_pull_enabled": false}',
                                                    encoding="utf-8")
    assert collection_enabled(tmp_path) is False


def test_collection_is_enabled_only_by_an_explicit_true(tmp_path: Path) -> None:
    from fetch_directory import collection_enabled
    (tmp_path / ".swingdesk-local.json").write_text('{"directory_pull_enabled": true}',
                                                    encoding="utf-8")
    assert collection_enabled(tmp_path) is True


def test_invalid_json_refuses_rather_than_defaulting(tmp_path: Path) -> None:
    """Unset is not default (AGENTS.md 3). A malformed switch refuses."""
    from fetch_directory import collection_enabled
    (tmp_path / ".swingdesk-local.json").write_text("{not json", encoding="utf-8")
    assert collection_enabled(tmp_path) is False


def test_a_non_boolean_value_refuses(tmp_path: Path) -> None:
    from fetch_directory import collection_enabled
    (tmp_path / ".swingdesk-local.json").write_text('{"directory_pull_enabled": "yes"}',
                                                    encoding="utf-8")
    assert collection_enabled(tmp_path) is False
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `PYTHONPATH=$PWD/src:$PWD/tools python -m pytest tests/test_directory.py -q -k collection`
Expected: FAIL — `ImportError: cannot import name 'collection_enabled'`.

- [ ] **Step 4: Implement gating and the response cap**

Add to `tools/fetch_directory.py`:

```python
#: Response cap (DR-008). Applies to Content-Length AND to bytes actually read, so a server that
#: omits or lies about the header cannot bypass it.
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

#: Per-machine switch. Ignored by git (.gitignore), never committed, and absent means OFF - the
#: same fail-closed rule the parameter registry uses. There is deliberately no committed default.
LOCAL_CONFIG = ".swingdesk-local.json"


def collection_enabled(root: Path) -> bool:
    """True only for an explicit boolean true. Missing, false, malformed or non-boolean all refuse."""
    config = root / LOCAL_CONFIG
    if not config.is_file():
        return False
    try:
        loaded = json.loads(config.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    value = loaded.get("directory_pull_enabled") if isinstance(loaded, dict) else None
    return value is True
```

Modify `_download` to enforce the cap:

```python
def _download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        declared = response.headers.get("Content-Length")
        if declared is not None and int(declared) > MAX_RESPONSE_BYTES:
            raise ValueError(f"{url}: declared {declared} bytes exceeds the {MAX_RESPONSE_BYTES} cap")
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(f"{url}: body exceeds the {MAX_RESPONSE_BYTES} byte cap")
    return body.decode("utf-8")
```

Add `--scheduled` to `main()`, which is what the wrapper passes:

```python
    parser.add_argument("--scheduled", action="store_true",
                        help="honour the local enable switch and the exchange calendar; the "
                             "manual form ignores both because a human asked for it")
    ...
    if args.scheduled:
        if not collection_enabled(REPO):
            print(f"directory pull disabled - no {LOCAL_CONFIG} with directory_pull_enabled: true")
            return 0
        if not cal.is_session(Exchange.NYSE, datetime.now(UTC).date()):
            print("not an NYSE session - nothing to collect")
            return 0
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=$PWD/src:$PWD/tools python -m pytest tests/test_directory.py -q`
Expected: PASS.

- [ ] **Step 6: Add the `implemented_by` marker to DR-008**

```
implemented_by: tools/daily_run.cmd :: fetch_directory.py
```

This is still red until Task 5 uncomments the line. That is correct: the gate should say the decision is unimplemented, because it is.

- [ ] **Step 7: Commit**

```bash
git add docs/decisions/DR-008-directory-automation.md tools/fetch_directory.py tests/test_directory.py
git commit -m "DR-008 amended to what will run, and the collector gated to match"
```

---

## Task 5: Wire the sidecar — the one validated exception to the freeze

**Files:**
- Modify: `tools/daily_run.cmd` (lines 57-62)
- Create: `.swingdesk-local.json` (untracked; ignored as of 2026-08-11)

**This touches the frozen daily-run path. Here is the proof it is safe:**

```
"%PY%" ... scan --universe ...      <- the run
set RC=%ERRORLEVEL%                 <- exit code captured HERE
popd
echo ===== ... finished, exit %RC%
REM "%PY%" ... fetch_directory.py   <- the line to uncomment, AFTER capture
exit /b %RC%                        <- returns the SAVED value
```

The collector sits after `set RC=%ERRORLEVEL%` and before `exit /b %RC%`, which returns the saved
variable. No outcome of the collector can reach the wrapper's exit code, so it cannot break the
Track A counter. `DR-008` designed it this way deliberately.

**What would make this wrong:** a batch-syntax error in the edited file would break the whole
wrapper, including the scan. Step 2 exists for exactly that and must not be skipped.

- [ ] **Step 1: Uncomment the collector, add `--scheduled`**

Replace the commented line with:

```bat
REM Sidecar (DR-008, amended 2026-08-11). Placed AFTER `set RC=%ERRORLEVEL%` and before
REM `exit /b %RC%`, so no outcome here can change the run's exit code or the Track A counter.
REM --scheduled honours the local enable switch and the NYSE calendar; both refuse quietly.
"%PY%" -X utf8 "%REPO%\tools\fetch_directory.py" --scheduled --data "%REPO%\data" >> "%LOG%" 2>&1
```

- [ ] **Step 2: Prove the wrapper still exits correctly BEFORE the next scheduled run**

```bash
cmd /c "tools\daily_run.cmd" & echo "exit was %ERRORLEVEL%"
```

Expected: the same exit code the scan produces on its own (0 today). If this errors on batch
syntax, revert immediately — the 18:30 run matters more than the sidecar.

- [ ] **Step 3: Create the local switch**

```bash
printf '{\n  "directory_pull_enabled": true\n}\n' > .swingdesk-local.json
git status --short   # must NOT list it - it is ignored as of 2026-08-11
```

- [ ] **Step 4: Verify gates 19 and 21 now agree**

Run: `python tools/verify_decisions.py`
Expected: PASS — `fetch_directory.py` now appears in `tools/daily_run.cmd`.

Run: `python tools/verify_secrets.py`
Expected: PASS — the ignore claim in DR-008 is now true.

- [ ] **Step 5: Commit**

```bash
git add tools/daily_run.cmd
git commit -m "the directory sidecar runs, and gate 19 goes green because the decision is now true"
```

---

## Task 6: The trade log

**Files:**
- Create: `tools/run_pr005_replay.py`
- Create: `docs/prereg/results/PR-005-trades.csv`
- Test: `tests/test_trade_log.py`

**Interfaces:**
- Consumes: the recorded seed in `docs/prereg/results/PR-005.json`.
- Produces: a CSV with header `entry_date,instrument,entry_price,atr14,stop_distance,exit_date,exit_reason,net_r`.

**Why this is the council's number one:** no reported study in this project has a trade log. `PR-009` is registered and blocked on exactly this. `BACKTEST_PROTOCOL.md` §3 lists it among the five artefacts a strategy claim requires. Every candidate strategy card needs it before it can be measured.

**Does it touch the frozen path?** No. It is a new `tools/` script reading stored bars.

**What would make this wrong — and it is the most valuable outcome here:** if the reproduced aggregates do not match `PR-005`'s published figures, **stop and report that**. A mismatch means a published result in this project is wrong, and that finding outranks every strategy card. Do not adjust the replay until it matches; that would be fitting the instrument to the answer.

- [ ] **Step 1: Read the recorded constants**

```bash
python -c "import json; d=json.load(open('docs/prereg/results/PR-005.json',encoding='utf-8')); print(json.dumps({k:v for k,v in d.items() if k!='rows'}, indent=1)[:1500])"
```

Record the seed, the universe definition, the entry rule and the reported aggregates. Every one of
them is an input to Step 3, and none may be invented.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_trade_log.py
"""The trade log must reproduce PR-005's published aggregates, or say it cannot."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LOG = REPO / "docs" / "prereg" / "results" / "PR-005-trades.csv"

EXPECTED_COLUMNS = ["entry_date", "instrument", "entry_price", "atr14",
                    "stop_distance", "exit_date", "exit_reason", "net_r"]


@pytest.mark.skipif(not LOG.exists(), reason="trade log not generated yet")
def test_the_trade_log_has_the_five_artefact_columns() -> None:
    with LOG.open(encoding="utf-8", newline="") as handle:
        assert next(csv.reader(handle)) == EXPECTED_COLUMNS


@pytest.mark.skipif(not LOG.exists(), reason="trade log not generated yet")
def test_every_row_carries_a_coded_exit_reason() -> None:
    with LOG.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows, "an empty trade log reproduces nothing"
    for row in rows:
        assert row["exit_reason"] in {"STOP", "TIME", "TARGET"}, row


@pytest.mark.skipif(not LOG.exists(), reason="trade log not generated yet")
def test_mean_r_matches_the_published_aggregate() -> None:
    """If this fails, a published result is wrong. That finding outranks every strategy card."""
    import json
    published = json.load((REPO / "docs" / "prereg" / "results" / "PR-005.json")
                          .open(encoding="utf-8"))
    with LOG.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mean_r = sum(Decimal(r["net_r"]) for r in rows) / len(rows)
    target = Decimal(str(published["mean_r"]))
    assert abs(mean_r - target) < Decimal("0.005"), (
        f"reproduced {mean_r}, published {target} - do NOT adjust the replay to match"
    )
```

- [ ] **Step 3: Run the tests to confirm they skip, then write the runner**

Run: `python -m pytest tests/test_trade_log.py -q`
Expected: every case skipped — the log does not exist yet.

Write `tools/run_pr005_replay.py` following the shape of the existing `tools/run_pr005.py`,
reusing its entry rule and universe selection unchanged, and emitting one CSV row per closed trade
with the columns above. Use the seed read in Step 1. Do not re-derive the entry logic — import it.

- [ ] **Step 4: Generate the log and run the tests**

```bash
PYTHONPATH=$PWD/src python tools/run_pr005_replay.py --out docs/prereg/results/PR-005-trades.csv
python -m pytest tests/test_trade_log.py -q
```

Expected: PASS. **If `test_mean_r_matches_the_published_aggregate` fails, stop this plan and write
the mismatch up as a finding.**

- [ ] **Step 5: Commit**

```bash
git add tools/run_pr005_replay.py docs/prereg/results/PR-005-trades.csv tests/test_trade_log.py
git commit -m "the first trade log this project has ever had, and it reproduces PR-005"
```

---

## Deferred to their own plans

Per the scope check, these are independent subsystems. Each states its entry criterion.

| Item | Entry criterion |
|---|---|
| **EDGAR delisting backfill** | After Task 6. It needs the trade log to attribute delistings to breadth regimes. Decides the council's hinge: concentrated (kill threshold 2.31%) versus proportional (34.9%) against an observed 1.6-2.3% missing rate. Free API, User-Agent with name and email, 10 req/sec. |
| **Exit card (funded)** | After Task 6 and the EDGAR result. `PR-007` fixes the stop at entry − 2.0 × ATR(14), no trailing, 20-session time exit — so exits have never been varied. One literature-sourced trailing multiple per D5, pre-registered, **no sweep**. |
| **Breadth card (written, parked)** | Write now, fund never until EDGAR reports. `PR-002` sits on its own survivorship kill line at the observed rate. If revived, only as a portfolio participation gate — never a per-signal entry filter, which is on the closed-by-evidence list. |
| **Vector memory** | After Task 6 — nothing to index before it. Permitted: over the 116 course PDFs as an authoring aid, and over the trade log for post-hoc human review marked not-evidence. **Forbidden in the decision path** without a charter amendment: it breaks gate 9 determinism and ratified criterion `a.reproducible`, and `CHARTER.md` A-001 with `AI_AUTHORITY_MODEL.md` §3 close "an AI that decides, sizes, or ranks by desirability". |
| **`sizing.py` cost model** | After 5 clean scheduled runs. `risk.costs_allowance` is a flat constant charging ten times the true cost at $5, and one number spanning two currencies while `sizing.py` has no currency handling at all. Both fixes are the same edit to a frozen file (`DR-009` §3). |
| **`tools/` under mypy** | Any time. 100 errors in 21 of 28 files. Two named suspicious sites first: `run_pr002.py:209` (`min(key=...)` over a key that can return `None`) and `run_pr005.py:267` (`Decimal` from an `object`). |
| **Structured logging** | Any time. `OBSERVABILITY_SPEC.md` §2 specifies a `run_id`/`event`/`code`/`as_of` schema; `platform/` has no logging module at all. |
| **Backup and restore** | Any time. `BACKUP_AND_DR.md` is spec-only, with no tooling and no proven restore. |
| **Chaos scenarios** | Screener-crash any time. **Cross-source conflict should be formally deferred**, not left looking like an oversight — it is structurally untestable with one vendor. |
| **Gate 10 (traceability)** | Now unblocked: the first `active` component exists, so its check "every `active` component has a test" would no longer pass vacuously. |

---

## Self-Review

**Spec coverage.** Items 1-4 of the brief map to Tasks 4+5, 2, 3 and 6. Item 1's honest-scope decision is Task 4 Step 1. The secrets concern raised mid-session is Task 1. Items 5-8 and the nine smaller debts are in *Deferred*, each with an entry criterion rather than a vague "later".

**Placeholder scan.** Every code step carries real code. Task 6 Step 3 is the one place that says "follow the shape of the existing runner" rather than reproducing it — deliberate, because inventing the entry rule instead of importing it is precisely the failure that would invalidate the reproduction.

**Type consistency.** `collection_enabled(root: Path) -> bool` is used identically in Task 4 Steps 2 and 4. `run_gate(tool, root)` matches the existing helper in `tests/test_gates.py`. The CSV header in Task 6's test matches the one in its Produces block.

**Ordering.** Task 1 is first because it is the only public risk. Task 5 is the sole exception to the freeze and carries its proof inline. Task 2 deliberately leaves `DR-008` red until Task 5 makes it true — a red gate that accurately describes reality is the correct state, not a problem to route around.
