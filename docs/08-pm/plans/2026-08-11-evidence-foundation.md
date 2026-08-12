# Evidence Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start collecting survivorship evidence again today, make that evidence trustworthy, and close the three holes that let a ratified decision ship unimplemented, uncommitted, and asserting a false fact about the repository.

**Architecture:** Four gates and one collector, in four phases. Phase A is a ~30-line change that restarts collection before the next session closes; everything else builds on data already accruing. Gates follow the existing pattern — a standalone script per gate, registered in `tools/check_gates.py`, proved able to fail in `tests/test_gates.py` against fixture trees via `SWINGDESK_ROOT`.

**Tech Stack:** Python 3.14, stdlib for gates (PyYAML where a registry is read), pytest, DuckDB via the existing `DirectoryStore`.

**Supersedes:** `2026-08-10-directory-automation.md` and the first draft of this file, both 2026-08-11. Neither was executed; none of the five files the older plan would create exists. Its genuinely load-bearing findings are carried forward and credited in Phase C — the older plan was right about strict parsing and about `gaps()`, and this plan verified both before adopting them.

## Global Constraints

- **The daily-run code path is FROZEN** until the Track A counter reaches 5 clean consecutive runs. Frozen: `tools/daily_run.cmd`, `application/pipeline.py`, `trade_management/sizing.py`. Task 2 is the one exception and carries its proof inline.
- **A gate that is wrong gets fixed or removed, never skipped.** No `--skip` flag.
- **Measured counts live in `HANDOFF.md` §2 and nowhere else** (`AGENTS.md` §10.5). Gate 14 matches digits only — a count spelled in words evades it, so do not write one.
- **Gate numbers are unique.** Three things once claimed "Gate 12" and it cost a day. This plan assigns **19 secrets, 20 decisions, 21 worktree, 22 directory policy**, in landing order. The superseded plan claimed 19 for its policy gate; that claim is released here.
- **Documents go in a tier, never a directory named after a tool** (`AGENTS.md` §4).
- **No network calls in `src/`.** Network tools live in `tools/` and never run in CI.
- Every new gate MUST have a test proving it goes red. A gate nobody has seen fail is untested.
- Branch from `master`; `master` is protected and requires the `gates` check.

---

## Phase A — stop the bleeding

**2026-08-10's departures are lost permanently.** 2026-08-11 was captured by hand. Phase A is deliberately the smallest change that makes collection automatic, because every further day is unrecoverable at any price and Phase C is days of work.

**This is why `DR-008` is NOT amended down.** The earlier draft of this plan proposed reducing the decision to what would ship quickly. That was the wrong trade: the irreversible asset is the snapshot, and Phase A secures it in one task without weakening a ratified record. Phase C then honours `DR-008` in full, over data that is already accruing.

### Task 1: Gate the collector on local config and the calendar

**Files:**
- Modify: `tools/fetch_directory.py`
- Create: `.swingdesk-local.example.json`
- Test: `tests/test_directory.py`

**Interfaces:**
- Consumes: `swingdesk.reference_data.calendar` (existing), `swingdesk.contracts.reference.Exchange` (existing).
- Produces: `collection_enabled(root: Path) -> bool`, `MAX_RESPONSE_BYTES = 2 * 1024 * 1024`, a `--scheduled` flag on the CLI.

**Touches the frozen path?** No. `tools/` only.

**What would make this wrong:** if `--scheduled` refuses silently, a fresh session cannot tell "collection is off" from "collection is broken". Every refusal path prints its reason to stdout, which the wrapper appends to `data/daily_run.log`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_directory.py

def test_collection_is_disabled_without_the_local_file(tmp_path: Path) -> None:
    from fetch_directory import collection_enabled
    assert collection_enabled(tmp_path) is False


def test_collection_is_disabled_when_the_flag_is_false(tmp_path: Path) -> None:
    from fetch_directory import collection_enabled
    (tmp_path / ".swingdesk-local.json").write_text(
        '{"directory_pull_enabled": false}', encoding="utf-8")
    assert collection_enabled(tmp_path) is False


def test_collection_is_enabled_only_by_an_explicit_true(tmp_path: Path) -> None:
    from fetch_directory import collection_enabled
    (tmp_path / ".swingdesk-local.json").write_text(
        '{"directory_pull_enabled": true}', encoding="utf-8")
    assert collection_enabled(tmp_path) is True


def test_malformed_json_refuses_rather_than_defaulting(tmp_path: Path) -> None:
    """Unset is not default (AGENTS.md 3). A broken switch refuses."""
    from fetch_directory import collection_enabled
    (tmp_path / ".swingdesk-local.json").write_text("{not json", encoding="utf-8")
    assert collection_enabled(tmp_path) is False


def test_a_non_boolean_value_refuses(tmp_path: Path) -> None:
    from fetch_directory import collection_enabled
    (tmp_path / ".swingdesk-local.json").write_text(
        '{"directory_pull_enabled": "yes"}', encoding="utf-8")
    assert collection_enabled(tmp_path) is False


def test_the_committed_example_has_automation_off(tmp_path: Path) -> None:
    """The example is committed; the real file is ignored. It must never enable anything."""
    import json
    from pathlib import Path as P
    example = P(__file__).resolve().parents[1] / ".swingdesk-local.example.json"
    assert json.loads(example.read_text(encoding="utf-8"))["directory_pull_enabled"] is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=$PWD/src:$PWD/tools python -m pytest tests/test_directory.py -q -k "collection or example"`
Expected: FAIL — `ImportError: cannot import name 'collection_enabled'`.

- [ ] **Step 3: Write the example file**

```json
{
  "directory_pull_enabled": false
}
```

Save as `.swingdesk-local.example.json`. It is committed on purpose: the real file is ignored, so the example is the only record of the switch's shape. Confirm `.gitignore` ignores `.swingdesk-local.json` **and not** the example:

```bash
git check-ignore -q .swingdesk-local.json && echo "real file ignored: correct"
git check-ignore -q .swingdesk-local.example.json && echo "WRONG - the example must be committed" || echo "example committed: correct"
```

- [ ] **Step 4: Implement gating and the cap**

Add to `tools/fetch_directory.py`:

```python
#: Response cap (DR-008). Applied to Content-Length AND to bytes actually read, so a server that
#: omits or misstates the header cannot bypass it.
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

#: Per-machine switch. Ignored by git, never committed, and absent means OFF - the same
#: fail-closed rule the parameter registry uses. There is deliberately no committed default.
LOCAL_CONFIG = ".swingdesk-local.json"


def collection_enabled(root: Path) -> bool:
    """True only for an explicit boolean true. Missing, false, malformed or non-boolean refuse."""
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

Enforce the cap in `_download`:

```python
def _download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        declared = response.headers.get("Content-Length")
        if declared is not None and int(declared) > MAX_RESPONSE_BYTES:
            raise ValueError(f"{url}: declared {declared} bytes exceeds the cap")
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(f"{url}: body exceeds the {MAX_RESPONSE_BYTES} byte cap")
    return body.decode("utf-8")
```

Add `--scheduled` to `main()`, before any network call:

```python
    parser.add_argument("--scheduled", action="store_true",
                        help="honour the local switch and the exchange calendar; the manual form "
                             "ignores both, because a human asked for it")
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

- [ ] **Step 6: Commit**

```bash
git add tools/fetch_directory.py .swingdesk-local.example.json tests/test_directory.py
git commit -m "the directory collector refuses unless the machine says yes and the exchange was open"
```

---

### Task 2: Wire the sidecar — the one validated exception to the freeze

**Files:**
- Modify: `tools/daily_run.cmd` (the commented block near the end)
- Create: `.swingdesk-local.json` (untracked)

**Touches the frozen path? YES — and here is the proof it is safe:**

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

**What would make this wrong:** a batch-syntax error would break the whole wrapper, scan included.
Step 2 exists for that and must not be skipped.

- [ ] **Step 1: Uncomment, adding `--scheduled`**

```bat
REM Sidecar (DR-008). Placed AFTER `set RC=%ERRORLEVEL%` and before `exit /b %RC%`, so no outcome
REM here can change the run's exit code or the Track A counter. --scheduled honours the local
REM switch and the NYSE calendar; both refuse loudly into this same log.
"%PY%" -X utf8 "%REPO%\tools\fetch_directory.py" --scheduled --data "%REPO%\data" >> "%LOG%" 2>&1
```

- [ ] **Step 2: Prove the wrapper still exits correctly, BEFORE the next 18:30**

```bash
cmd /c "tools\daily_run.cmd" & echo "exit was %ERRORLEVEL%"
```

Expected: the same code the scan produces alone. On any batch-syntax error, revert immediately —
the scheduled run matters more than the sidecar.

- [ ] **Step 3: Create the local switch**

```bash
printf '{\n  "directory_pull_enabled": true\n}\n' > .swingdesk-local.json
git status --short   # must NOT list it
```

- [ ] **Step 4: Confirm collection happens on the next session**

```bash
tail -20 data/daily_run.log
```

Expected: a `recorded N rows` line, or a stated refusal. Silence is a failure.

- [ ] **Step 5: Commit**

```bash
git add tools/daily_run.cmd
git commit -m "the directory sidecar runs, and cannot touch the run's exit code"
```

---

## Phase B — the gates that would have caught it

### Task 3: Gate 19 — secret hygiene and ignore-claim verification

**Files:**
- Create: `tools/verify_secrets.py`
- Modify: `.gitignore`, `tools/check_gates.py`
- Test: `tests/test_gates.py`

**Interfaces:**
- Produces: `SECRET_PATTERNS: tuple[str, ...]`, `tracked_secrets(root) -> list[str]`, `broken_ignore_claims(root) -> list[str]`.

**Touches the frozen path?** No.

**Why:** `DR-008` called `.swingdesk-local.json` "the ignored local file" when it was not ignored — a document asserting a repository property instead of creating it. The repository is public. GitHub push protection is enabled and catches known credential *formats*, but not a local config carrying an account number.

**What would make this wrong:** a broad regex matching prose like "whitespace is ignored" makes the gate noisy, and a noisy gate gets bypassed. The pattern is anchored to backticked paths for exactly that reason.

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


def test_secret_gate_catches_a_false_ignore_claim(tmp_path: Path) -> None:
    root = _secrets_tree(tmp_path, "docs/build/\n",
                         "The collector reads the ignored local file `.swingdesk-local.json`.\n")
    code, out = run_gate("verify_secrets.py", root)
    assert code == 1
    assert ".swingdesk-local.json" in out


def test_secret_gate_accepts_a_true_ignore_claim(tmp_path: Path) -> None:
    root = _secrets_tree(tmp_path, ".swingdesk-local.json\n",
                         "The collector reads the ignored local file `.swingdesk-local.json`.\n")
    code, out = run_gate("verify_secrets.py", root)
    assert code == 0, out


def test_secret_gate_catches_a_tracked_secret_shaped_file(tmp_path: Path) -> None:
    root = _secrets_tree(tmp_path, "docs/build/\n")
    (root / ".env").write_text("BROKER_TOKEN=abc\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-f", ".env"], capture_output=True, check=True)
    code, out = run_gate("verify_secrets.py", root)
    assert code == 1
    assert ".env" in out


def test_secret_gate_does_not_flag_ordinary_prose(tmp_path: Path) -> None:
    """A noisy gate gets bypassed. 'ignored' in prose must not trip it."""
    root = _secrets_tree(tmp_path, "docs/build/\n",
                         "Whitespace is ignored by the parser, and the header is ignored too.\n")
    code, out = run_gate("verify_secrets.py", root)
    assert code == 0, out
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_gates.py -q -k secret_gate`
Expected: FAIL — the script does not exist.

- [ ] **Step 3: Write the gate**

```python
# tools/verify_secrets.py
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


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, encoding="utf-8")


def tracked_secrets(root: Path) -> list[str]:
    listing = _git("ls-files")
    if listing.returncode != 0:
        return []
    return [p for p in listing.stdout.splitlines()
            if any(re.search(pat, p, re.IGNORECASE) for pat in SECRET_PATTERNS)]


def broken_ignore_claims(root: Path) -> list[str]:
    failures: list[str] = []
    for doc in sorted(root.rglob("*.md")):
        if ".git" in doc.parts:
            continue
        for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for match in IGNORE_CLAIM.finditer(line):
                candidate = match.group(1).strip()
                if " " in candidate or ("/" not in candidate and "." not in candidate):
                    continue  # backticked prose, not a path
                if _git("check-ignore", "-q", candidate).returncode != 0:
                    failures.append(
                        f"{doc.relative_to(root).as_posix()}:{number}: claims {candidate!r} is "
                        f"ignored, but `git check-ignore` says it is not"
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

    print(f"\nsecrets: {len(secrets)} tracked secret-shaped, {len(claims)} false ignore-claim(s)")
    if secrets:
        print("\n`git rm --cached` it, add the pattern to .gitignore, and rotate whatever it held. "
              "The repository is public.")
    if claims:
        print("\nAdd the path to .gitignore, or stop calling it ignored (AGENTS.md 1).")
    return 1 if (secrets or claims) else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_gates.py -q -k secret_gate`
Expected: PASS.

- [ ] **Step 5: Broaden `.gitignore`**

Append to the `# secrets` section. **Do not add `*.local.json`** — it would ignore
`.swingdesk-local.example.json`, which must stay committed:

```
.env.*
*.pem
credentials*
secrets.*
*_rsa
```

- [ ] **Step 6: Register and verify**

```python
        "19 secret hygiene": _run("no tracked secrets, no false ignore claims",
                               [python, "tools/verify_secrets.py"]),
```

Run: `python tools/verify_secrets.py` — expected PASS; verified 2026-08-11 that nothing secret is
tracked and none is in history.
Run: `python tools/check_gates.py`. Update **`HANDOFF.md` §2 only** if the gate count moved.

- [ ] **Step 7: Commit**

```bash
git add tools/verify_secrets.py tools/check_gates.py tests/test_gates.py .gitignore HANDOFF.md
git commit -m "gate 19: a document claiming a path is ignored must be telling the truth"
```

---

### Task 4: Gate 20 — an accepted decision names what proves it

**Files:**
- Create: `tools/verify_decisions.py`
- Modify: `docs/decisions/*.md`, `tools/check_gates.py`
- Test: `tests/test_gates.py`

**Interfaces:**
- Produces: `parse_header(text: str) -> dict[str, str]`.

**Touches the frozen path?** No.

**Why — the 5-whys root cause:** the only decisions this project verifies are those that set parameters, because a parameter carries provenance `assumed:DR-nnn` and gate 1 checks it. `DR-008` declares `parameters: none`, so it had no hook at all: ratified, unimplemented, and uncommitted until 2026-08-11.

**What would make this wrong:** if `implementation: none` becomes what everyone writes to go green, the gate is theatre. Mitigation: the marker form names a path that must exist *and* a token that must appear in it — a claim that can fail.

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
    root = _decisions_tree(tmp_path, "date: 2026-08-01\nstatus: accepted\nparameters: none")
    code, out = run_gate("verify_decisions.py", root)
    assert code == 1
    assert "implemented_by" in out


def test_decision_gate_catches_an_absent_marker(tmp_path: Path) -> None:
    root = _decisions_tree(
        tmp_path,
        "date: 2026-08-01\nstatus: accepted\nimplemented_by: tools/run.cmd :: fetch_directory.py",
        marker_file="tools/run.cmd", marker_body="echo nothing\n")
    code, out = run_gate("verify_decisions.py", root)
    assert code == 1
    assert "fetch_directory.py" in out


def test_decision_gate_accepts_a_present_marker(tmp_path: Path) -> None:
    root = _decisions_tree(
        tmp_path,
        "date: 2026-08-01\nstatus: accepted\nimplemented_by: tools/run.cmd :: fetch_directory.py",
        marker_file="tools/run.cmd", marker_body="python tools/fetch_directory.py --scheduled\n")
    code, out = run_gate("verify_decisions.py", root)
    assert code == 0, out


def test_decision_gate_accepts_an_explicit_none(tmp_path: Path) -> None:
    """A convention decision changes no code. Saying so out loud is the point."""
    root = _decisions_tree(tmp_path, "date: 2026-08-01\nstatus: accepted\nimplementation: none")
    code, out = run_gate("verify_decisions.py", root)
    assert code == 0, out


def test_decision_gate_ignores_a_proposal(tmp_path: Path) -> None:
    """Only ACCEPTED records promise anything. A proposal is still a question."""
    root = _decisions_tree(tmp_path, "date: 2026-08-01\nstatus: proposed\nparameters: none")
    code, out = run_gate("verify_decisions.py", root)
    assert code == 0, out
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_gates.py -q -k decision_gate`
Expected: FAIL — the script does not exist.

- [ ] **Step 3: Write the gate**

```python
# tools/verify_decisions.py
"""Gate 20: an accepted decision record says what would prove it was carried out.

The defect this exists for, 2026-08-11. `DR-008` was ratified 2026-08-10, declared
`parameters: none`, and specified a collector with config gating, calendar eligibility, a response
cap, validation and audit rows. None of it was built, and the file was not even committed. One
trading day of unrecoverable survivorship evidence was lost because of it.

The root cause is narrow and worth stating exactly: **the only decisions this project verifies are
the ones that set parameters.** A parameter carries provenance `assumed:DR-nnn` and gate 1 checks
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
                f"{rel}: status {status!r} but the header declares neither "
                f"`implemented_by: <path> :: <token>` nor `implementation: none`")
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
                f"ratified but its implementation is absent")

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

- [ ] **Step 5: Add the field to every accepted record**

`DR-008` — now true, because Task 2 uncommented the line:

```
implemented_by: tools/daily_run.cmd :: fetch_directory.py
```

`DR-007` and other parameter-setting records — the registry and provenance token are the honest marker:

```
implemented_by: registry/parameters.yml :: assumed:DR-007
```

Convention records that change no code (`DR-001`, the Sharpe convention):

```
implementation: none
```

- [ ] **Step 6: Register, verify, commit**

```python
        "20 decisions implemented": _run("accepted decisions declare what proves them",
                                      [python, "tools/verify_decisions.py"]),
```

```bash
python tools/check_gates.py
git add tools/verify_decisions.py tools/check_gates.py tests/test_gates.py docs/decisions/ HANDOFF.md
git commit -m "gate 20: a ratified decision names what would prove it happened"
```

---

### Task 5: Gate 21 — finished work left uncommitted (advisory)

**Files:**
- Create: `tools/verify_worktree_clean.py`
- Modify: `tools/check_gates.py`
- Test: `tests/test_gates.py`

**Interfaces:**
- Produces: `GOVERNED = ("docs/", "registry/", "src/", "tools/")`, `stray_paths(root) -> list[str]`.

**Touches the frozen path?** No.

**Why:** three incidents on 2026-08-11 trace to one condition — finished work sitting uncommitted in the main checkout. `DR-008` was invisible to every gate; twice a `git add -A` swept another effort's files into an unrelated commit.

**What would make this wrong — and it decides the design:** this gate is red during ordinary editing, which is exactly when someone reaches for a bypass. It is therefore **advisory: it prints and returns 0.** The value is visibility, not veto. A gate that blocks normal work gets disabled and takes the others' credibility with it.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gates.py

def _git_init(root: Path) -> None:
    for args in (["init", "-b", "main"],
                 ["-c", "user.email=t@t", "-c", "user.name=t", "commit",
                  "--allow-empty", "-m", "base"]):
        subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True)


def test_worktree_gate_reports_untracked_governed_files(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "orphan.md").write_text("finished, uncommitted\n", encoding="utf-8")
    _git_init(tmp_path)
    code, out = run_gate("verify_worktree_clean.py", tmp_path)
    assert code == 0, "advisory only - it must never fail the build"
    assert "docs/orphan.md" in out


def test_worktree_gate_is_quiet_on_a_clean_tree(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "kept.md").write_text("committed\n", encoding="utf-8")
    for args in (["init", "-b", "main"], ["add", "-A"],
                 ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "base"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True, check=True)
    code, out = run_gate("verify_worktree_clean.py", tmp_path)
    assert code == 0
    assert "0 stray" in out


def test_worktree_gate_ignores_ungoverned_paths(tmp_path: Path) -> None:
    (tmp_path / "scratch.txt").write_text("not governed\n", encoding="utf-8")
    _git_init(tmp_path)
    code, out = run_gate("verify_worktree_clean.py", tmp_path)
    assert "0 stray" in out
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_gates.py -q -k worktree_gate`
Expected: FAIL — the script does not exist.

- [ ] **Step 3: Write the gate**

```python
# tools/verify_worktree_clean.py
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
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        return []
    strays = []
    for line in result.stdout.splitlines():
        path = line[3:].strip().strip('"')
        if any(path.startswith(prefix) for prefix in GOVERNED):
            strays.append(f"{line[:2].strip() or '??'}  {path}")
    return strays


def main() -> int:
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
```

- [ ] **Step 4: Run the tests, register, commit**

```python
        "21 worktree clean": _run("no finished work left uncommitted (advisory)",
                               [python, "tools/verify_worktree_clean.py"]),
```

```bash
python -m pytest tests/test_gates.py -q -k worktree_gate
python tools/check_gates.py
git add tools/verify_worktree_clean.py tools/check_gates.py tests/test_gates.py HANDOFF.md
git commit -m "gate 21: finished work left uncommitted is work no gate can see"
```

---

## Phase C — make the evidence trustworthy

**Carried forward from the superseded plan, and verified before adoption.** Its author was right about both of these, and both were confirmed against the tree on 2026-08-11.

### Task 6: Stop silently dropping malformed directory rows

**Files:**
- Modify: `src/swingdesk/reference_data/universe.py:68`, `:92`
- Test: `tests/test_universe.py`

**Touches the frozen path?** No — `reference_data/universe.py` is not in the frozen set, but it *is* `src/`. Land it on a branch and let CI confirm before merging.

**Why this is more serious than hygiene:** `if len(parts) < 8: continue` drops a malformed row without a trace. A symbol that vanishes because its row was corrupt **looks exactly like a departure** — and departures are the entire survivorship evidence base, which the council's hinge assumption now rests on. A parse defect currently manufactures false evidence.

**What would make this wrong:** if the vendor legitimately emits a short trailer row and the strict parser rejects the whole file, collection stops. Hence: reject the *row*, count it, and refuse the file only when the reject count is non-zero — loudly, not silently.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_universe.py

def test_a_malformed_row_is_reported_rather_than_skipped() -> None:
    """A dropped row is indistinguishable from a delisting, and delistings are the evidence."""
    from swingdesk.reference_data import universe
    body = (
        "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
        "AAPL|Apple Inc.|Q|N|N|100|N|N\n"
        "BROKEN|only|three\n"
        "File Creation Time: 0811202618:30|||||||\n"
    )
    with pytest.raises(ValueError, match="1 malformed row"):
        universe.parse_nasdaq_listed(body)


def test_a_clean_file_still_parses() -> None:
    from swingdesk.reference_data import universe
    body = (
        "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
        "AAPL|Apple Inc.|Q|N|N|100|N|N\n"
        "File Creation Time: 0811202618:30|||||||\n"
    )
    assert [e.symbol for e in universe.parse_nasdaq_listed(body)] == ["AAPL"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=$PWD/src python -m pytest tests/test_universe.py -q -k malformed`
Expected: FAIL — no exception is raised; the row is skipped.

- [ ] **Step 3: Replace the silent skip**

In both parsers, replace `continue` on the short-row branch with a counter, and after the loop:

```python
    if malformed:
        raise ValueError(
            f"{malformed} malformed row(s) in the directory feed. Refusing the file rather than "
            f"skipping them: a dropped row is indistinguishable from a departure, and departures "
            f"are this project's only survivorship evidence."
        )
```

Keep the `File Creation Time` trailer exempt — it is a known, valid short row.

- [ ] **Step 4: Run the tests and the full suite**

```bash
PYTHONPATH=$PWD/src python -m pytest tests/test_universe.py -q
python tools/check_gates.py
```

- [ ] **Step 5: Commit**

```bash
git add src/swingdesk/reference_data/universe.py tests/test_universe.py
git commit -m "a malformed directory row looks exactly like a delisting, so stop dropping them"
```

---

### Task 7: `DirectoryStore.gaps()` — say which sessions were actually observed

**Files:**
- Modify: `src/swingdesk/reference_data/directory.py`
- Test: `tests/test_directory.py`

**Interfaces:**
- Consumes: `swingdesk.reference_data.calendar.sessions`.
- Produces: `DirectoryStore.gaps(self, start: date, end: date) -> tuple[date, ...]`.

**Touches the frozen path?** No.

**Why:** the store has `record`, `latest_pull` and `as_of` — nothing reports which sessions were observed. Coverage today is 08-03, 08-05, 08-08 and 08-11, with 08-10 permanently missing. Any research claiming continuous survivorship coverage would be unfounded **and undetectable**. This makes the hole a first-class, queryable fact.

**What would make this wrong:** if `gaps()` counts non-session days as gaps it reports noise. It must intersect with the NYSE calendar.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_directory.py

def test_gaps_reports_unobserved_trading_sessions(tmp_path: Path) -> None:
    """08-10 is a real hole in this project's evidence. gaps() is how anyone finds out."""
    from datetime import UTC, date, datetime
    from swingdesk.reference_data.directory import DirectoryStore

    with DirectoryStore(tmp_path / "d.duckdb") as store:
        store.record((), datetime(2026, 8, 11, 3, 0, tzinfo=UTC), "fixture")
        holes = store.gaps(date(2026, 8, 10), date(2026, 8, 11))

    assert date(2026, 8, 10) in holes
    assert date(2026, 8, 11) not in holes


def test_gaps_does_not_count_weekends(tmp_path: Path) -> None:
    from datetime import UTC, date, datetime
    from swingdesk.reference_data.directory import DirectoryStore

    with DirectoryStore(tmp_path / "d.duckdb") as store:
        store.record((), datetime(2026, 8, 11, 3, 0, tzinfo=UTC), "fixture")
        holes = store.gaps(date(2026, 8, 8), date(2026, 8, 11))

    assert date(2026, 8, 8) not in holes   # Saturday
    assert date(2026, 8, 9) not in holes   # Sunday
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=$PWD/src python -m pytest tests/test_directory.py -q -k gaps`
Expected: FAIL — `AttributeError: 'DirectoryStore' object has no attribute 'gaps'`.

- [ ] **Step 3: Implement**

```python
    def gaps(self, start: date, end: date) -> tuple[date, ...]:
        """NYSE sessions in [start, end] with no recorded pull.

        A gap is permanent: the vendor publishes a current snapshot and no history, so a session
        missed is departure evidence lost at any price. Exposed as data rather than left implicit,
        because research claiming continuous coverage would otherwise be unfounded AND
        undetectable.
        """
        observed = {
            pull.astimezone(UTC).date()
            for (pull,) in self._connection.execute(
                "SELECT DISTINCT knowledge_time FROM directory_pulls"
            ).fetchall()
        }
        sessions = {s.session_date for s in cal.sessions(Exchange.NYSE, start, end)}
        return tuple(sorted(sessions - observed))
```

- [ ] **Step 4: Run the tests, then report the real gaps**

```bash
PYTHONPATH=$PWD/src python -m pytest tests/test_directory.py -q
PYTHONPATH=$PWD/src python -c "
from datetime import date
from swingdesk.reference_data.directory import DirectoryStore
with DirectoryStore('data/directory.duckdb') as s:
    print('unobserved sessions:', s.gaps(date(2026,8,3), date.today()))
"
```

Expected: `2026-08-04, 2026-08-06, 2026-08-07, 2026-08-10` and any since. Record the result in
`HANDOFF.md` §2's Directory row — the count belongs there and nowhere else.

- [ ] **Step 5: Commit**

```bash
git add src/swingdesk/reference_data/directory.py tests/test_directory.py HANDOFF.md
git commit -m "gaps(): the sessions nobody observed, as data rather than an assumption"
```

---

## Phase D — the trade log

### Task 8: Reproduce PR-005 and persist one row per trade

**Files:**
- Create: `tools/run_pr005_replay.py`, `docs/prereg/results/PR-005-trades.csv`
- Test: `tests/test_trade_log.py`

**Interfaces:**
- Consumes: the recorded seed in `docs/prereg/results/PR-005.json`; the entry rule from `tools/run_pr005.py`, **imported, never re-derived**.
- Produces: a CSV with header `entry_date,instrument,entry_price,atr14,stop_distance,exit_date,exit_reason,net_r`.

**Touches the frozen path?** No.

**Why this is the council's number one:** no reported study in this project has a trade log. `PR-009` is registered and blocked on exactly this. `BACKTEST_PROTOCOL.md` §3 lists it among the five artefacts a strategy claim requires. Every surviving strategy card needs it before it can be measured.

**What would make this wrong — and it is the most valuable possible outcome:** if the reproduced aggregates do not match `PR-005`'s published figures, **stop and report the mismatch**. A published result in this project would be wrong, and that finding outranks every strategy card. Do not adjust the replay until it matches — that is fitting the instrument to the answer.

- [ ] **Step 1: Read the recorded constants**

```bash
python -c "import json; d=json.load(open('docs/prereg/results/PR-005.json',encoding='utf-8')); print(json.dumps({k:v for k,v in d.items() if k!='rows'}, indent=1)[:1500])"
```

Record the seed, universe definition, entry rule and published aggregates. All are inputs to Step 3
and none may be invented.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_trade_log.py
"""The trade log must reproduce PR-005's published aggregates, or say plainly that it cannot."""

from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LOG = REPO / "docs" / "prereg" / "results" / "PR-005-trades.csv"
COLUMNS = ["entry_date", "instrument", "entry_price", "atr14",
           "stop_distance", "exit_date", "exit_reason", "net_r"]


@pytest.mark.skipif(not LOG.exists(), reason="trade log not generated yet")
def test_the_log_has_the_artefact_columns() -> None:
    with LOG.open(encoding="utf-8", newline="") as handle:
        assert next(csv.reader(handle)) == COLUMNS


@pytest.mark.skipif(not LOG.exists(), reason="trade log not generated yet")
def test_every_row_carries_a_coded_exit_reason() -> None:
    with LOG.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows, "an empty trade log reproduces nothing"
    for row in rows:
        assert row["exit_reason"] in {"STOP", "TIME", "TARGET"}, row


@pytest.mark.skipif(not LOG.exists(), reason="trade log not generated yet")
def test_mean_r_matches_the_published_aggregate() -> None:
    """If this fails, a published result is wrong. That outranks every strategy card."""
    published = json.loads((REPO / "docs" / "prereg" / "results" / "PR-005.json")
                           .read_text(encoding="utf-8"))
    with LOG.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mean_r = sum(Decimal(r["net_r"]) for r in rows) / len(rows)
    target = Decimal(str(published["mean_r"]))
    assert abs(mean_r - target) < Decimal("0.005"), (
        f"reproduced {mean_r}, published {target} - do NOT adjust the replay to match")
```

- [ ] **Step 3: Confirm they skip, then write the runner**

Run: `python -m pytest tests/test_trade_log.py -q` — expected: all skipped.

Write `tools/run_pr005_replay.py`. **Import** the entry rule and universe selection from
`tools/run_pr005.py` rather than restating them; a re-derived rule reproduces nothing. Emit one row
per closed trade with the columns above, under the seed from Step 1.

- [ ] **Step 4: Generate and verify**

```bash
PYTHONPATH=$PWD/src python tools/run_pr005_replay.py --out docs/prereg/results/PR-005-trades.csv
python -m pytest tests/test_trade_log.py -q
```

Expected: PASS. **If the mean-R test fails, stop this plan and write the mismatch up as a finding.**

- [ ] **Step 5: Commit**

```bash
git add tools/run_pr005_replay.py docs/prereg/results/PR-005-trades.csv tests/test_trade_log.py
git commit -m "the first trade log this project has ever had, and it reproduces PR-005"
```

---

## Deferred, with entry criteria

| Item | Entry criterion |
|---|---|
| **`DR-008`'s remaining machinery** — `registry/directory_pull_policy.yml` + its gate 22, `--emergency-repull`, supersession records, checksum storage, the audit row | After Phase C. Carried from the superseded plan, which specified all of it. Deferred not dismissed: it is real work, and Phase A already secured the irreversible part. |
| **EDGAR delisting backfill** | After Task 8. Needs the trade log to attribute delistings to breadth regimes. Decides the council's hinge: concentrated (kill threshold 2.31%) vs proportional (34.9%) against an observed 1.6–2.3% missing rate. Free API, User-Agent with name and email, 10 req/sec. |
| **Exit card (the one funded card)** | After Task 8 and the EDGAR result. `PR-007` fixes the stop at entry − 2.0 × ATR(14), no trailing, 20-session time exit — exits have never been varied. One literature-sourced multiple per D5, pre-registered, **no sweep**. |
| **Breadth card (written, parked)** | Write any time; fund only after EDGAR reports. `PR-002` sits on its own survivorship kill line at the observed rate. If revived, only as a portfolio participation gate — never a per-signal entry filter, which is closed by evidence. |
| **Vector memory** | After Task 8 — nothing to index before it. Permitted over the course PDFs as an authoring aid and over the trade log for post-hoc human review marked not-evidence. **Forbidden in the decision path** without a charter amendment: it breaks gate 9 determinism and `a.reproducible`, and `CHARTER.md` A-001 with `AI_AUTHORITY_MODEL.md` §3 close "an AI that decides, sizes, or ranks by desirability". |
| **`sizing.py` cost model** | After 5 clean scheduled runs. `risk.costs_allowance` is a flat constant charging ten times the true cost at $5, and one number spanning two currencies while `sizing.py` has no currency handling at all (`DR-009` §3). |
| **`tools/` under mypy** | Any time. 100 errors in 21 of 28 files. Two suspicious sites first: `run_pr002.py:209` (`min(key=...)` over a key that can return `None`), `run_pr005.py:267` (`Decimal` from an `object`). |
| **Structured logging** | Any time. `OBSERVABILITY_SPEC.md` §2 specifies a `run_id`/`event`/`code`/`as_of` schema; `platform/` has no logging module. |
| **Backup and restore** | Any time. `BACKUP_AND_DR.md` is spec-only, no tooling, no proven restore. |
| **Chaos scenarios** | Screener-crash any time. **Cross-source conflict should be formally deferred**, not left looking like an oversight — it is structurally untestable with one vendor. |
| **Gate 10 (traceability)** | Unblocked: the first `active` component exists, so "every `active` component has a test" no longer passes vacuously. |
| **Gate 14 word-number hole** | Any time. It matches digits, so a count spelled in words evades the ownership rule — `HANDOFF.md`'s own header said "Twenty-two gates" while the count was 24. |

---

## Self-Review

**Spec coverage.** Phase A covers the urgent collector; Phase B the three gates from the 5-whys; Phase C the two findings carried from the superseded plan, both verified against the tree before adoption; Phase D the trade log. Everything else is in *Deferred* with an entry criterion.

**Superseded-plan audit.** Its five would-be files all confirmed absent — nothing was executed. Adopted: strict parsing (Task 6), `gaps()` (Task 7), the `.swingdesk-local.example.json` pattern (Task 1), the policy YAML and forced-repull machinery (deferred, credited). Dropped: "Task 0: Freeze the Reviewed Plan" as ceremony, and its gate-19 claim, released here to avoid the number collision that once cost this repository a day.

**Placeholder scan.** Every code step carries real code. Task 8 Step 3 says "import the entry rule" rather than reproducing it — deliberate, because re-deriving it is the one thing that would invalidate the reproduction.

**Type consistency.** `collection_enabled(root: Path) -> bool` identical in Task 1 Steps 1 and 4. `parse_header` used only in Task 4. `gaps(start, end) -> tuple[date, ...]` matches its test. `run_gate(tool, root)` matches the existing helper. The CSV header in Task 8's test matches its Produces block.

**Length.** 2,249 lines across two plans became one. The reduction is ceremony and duplication, not substance: every task retained carries its own tests, its own code, and a stated reason it could be wrong.
