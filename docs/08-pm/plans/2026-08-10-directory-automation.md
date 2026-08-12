# Directory Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Status:** owner-pending · **Tier:** 8 (project management)

**Goal:** Collect one validated US symbol-directory snapshot per NYSE trading session without
changing the trading scan's result, while keeping network use bounded, local, explicit and auditable.

**Architecture:** Keep network and scheduler concerns in `tools/`: a thin CLI delegates to a
testable directory-pull service that reads one committed policy and one ignored local switch. Keep
point-in-time facts in `DirectoryStore`: successful snapshots, compact invocation audit rows,
append-only forced replacements and detected session gaps are committed transactionally; invalid
response bodies are never stored. `daily_run.cmd` invokes the pull after the scan and always exits
with the scan's saved return code.

**Tech Stack:** Python 3.12, stdlib `urllib`/`zoneinfo`/`hashlib`, PyYAML, DuckDB,
`pandas-market-calendars`, pytest, Windows batch, existing SwingDesk merge gates.

## Global Constraints

- This feature collects reference data only. It never places, proposes or changes an order.
- USA and Canada remain separate. This automation covers the two US NASDAQ Trader files only.
- The source allowlist is fixed in `registry/directory_pull_policy.yml`; the CLI cannot accept a URL.
- The committed policy is the single runtime source for every network and staleness limit. Code has
  no fallback literals for those values.
- The local switch is `.swingdesk-local.json`. Missing or `false` means disabled; malformed content
  refuses the pull visibly. The real file is ignored; the example is committed.
- Normal mode makes at most two attempts, separated by 60 seconds, and each attempt requests each of
  the two allowlisted files at most once.
- `FORCED` mode has no daily or lifetime invocation quota. Each explicit command makes one attempt,
  requires a non-empty reason and is recorded as `FORCED`; it has no internal retry loop.
- Every response body is capped at 2 MiB. `FORCED` cannot bypass the cap, local switch, calendar,
  allowlist, structural validation, lock or audit.
- A snapshot is committed only after both files pass byte, UTF-8, header, row, trailer, timestamp and
  non-empty checks. Large membership changes are displayed as counts, never rejected by an invented
  magnitude threshold.
- A forced replacement appends a new snapshot and a supersession record. It never deletes or updates
  the earlier snapshot. A failed forced replacement leaves the earlier snapshot canonical.
- Invalid response bodies are discarded. Every invocation that can open the local store writes one
  compact aggregate audit row containing only timestamps, mode/reason, enabled state, attempts,
  request count, received bytes, result code and the successful snapshot id. It does not write one
  row per retry. A lock/store failure is visible in the existing log because that failure cannot
  safely write into the store it failed to acquire.
- No backdating: the two embedded source dates must agree with the latest completed NYSE session.
  A missed session becomes a recorded gap, never a reconstructed `OBSERVED` snapshot.
- The first session-aware snapshot is a baseline. It produces no arrival/departure claim against the
  older legacy pulls whose embedded source dates were not stored.
- One missed NYSE session is `WARNING`; two or more consecutive missed sessions are `ERROR`. Neither
  changes the trading scan exit code.
- CI remains fully offline. Every vendor response is a fixture and every clock, sleeper, downloader
  and calendar decision is injected in tests.
- Production code, tests, messages and documentation are English. Measured live counts remain owned
  by `HANDOFF.md` section 2.

---

## File Map

### Existing design inputs

- `docs/decisions/DR-008-directory-automation.md` — accepted owner decision that supersedes the
  manual-only operating choice.
- `docs/decisions/measurements/directory-file-sizes-2026-08-10.json` — the HEAD measurement used to
  ratify the response cap; no response body.

### Create

- `registry/directory_pull_policy.yml` — single machine-readable source allowlist and limits.
- `.swingdesk-local.example.json` — safe local-switch example with automation off.
- `tools/directory_pull.py` — policy/config loading, bounded download, validation, locking,
  orchestration and one-line status formatting.
- `tools/verify_directory_policy.py` — offline gate for the policy, example and batch wiring.
- `tests/test_directory_pull.py` — offline tests for policy, validation, request budgets, calendar,
  retries, forced operation, locking and status output.

### Modify

- `.gitignore` — ignore `.swingdesk-local.json` but not its example.
- `tools/fetch_directory.py` — reduce to the CLI adapter over `directory_pull.run()`.
- `tools/daily_run.cmd` — call the directory CLI after the scan and preserve `%RC%`.
- `src/swingdesk/reference_data/directory.py` — immutable metadata, audit, supersession and gap APIs.
- `src/swingdesk/reference_data/universe.py` — expose exact expected headers and reject malformed
  data rows instead of silently skipping them.
- `tests/test_directory.py` — transaction, immutability, supersession, audit and gap tests.
- `tests/test_universe.py` — malformed-row and strict-parser tests.
- `tests/test_gates.py` — prove the policy gate goes red for unsafe drift.
- `tools/check_gates.py` — wire fast gate 19 before lint/type/test gates and before the summary.
- `docs/06-engineering/CI_POLICY.md` — add gate 19 and its failure class.
- `docs/03-data/POINT_IN_TIME_SPEC.md` — specify observed sessions, gaps and forced supersession.
- `docs/06-engineering/SYSTEM_MODES.md` — replace the stale unscheduled-directory statement.
- `docs/runbooks/README.md` — local enable/disable, normal status and forced recovery commands.
- `docs/decisions/README.md` — index accepted `DR-008`.
- `HANDOFF.md` — close the owner question, update measured state only after verification.

### Deliberately unchanged

- `src/swingdesk/application/universe.py` keeps its current latest-known `as_of` behavior so the
  post-scan directory job cannot alter Track A decisions. Exact session coverage is exposed
  separately through `DirectoryStore.gaps()` and must be checked by research claiming continuous
  survivorship coverage.
- The Windows scheduled-task definition is unchanged; it already invokes `tools/daily_run.cmd`.
- No report, dashboard, notification service, historical vendor or Canadian directory is added.

---

### Task 0: Freeze the Reviewed Plan

**Files:**

- Create: `docs/08-pm/plans/2026-08-10-directory-automation.md`
- Create: `docs/decisions/DR-008-directory-automation.md`
- Create: `docs/decisions/measurements/directory-file-sizes-2026-08-10.json`
- Modify: `docs/README.md`
- Modify: `docs/decisions/README.md`
- Modify: `registry/project_manifest.yml`
- Modify: `HANDOFF.md`

**Interfaces:**

- Consumes: the owner-approved decisions recorded in this plan.
- Produces: one indexed, reviewable implementation contract; no runtime behavior.

- [ ] **Step 1: Review this document before implementation**

Confirm that it contains no unapproved source, hidden default, automatic emergency loop, raw-body
retention, scan-exit coupling, backfill claim or Canadian scope.

- [ ] **Step 2: Run the document and count gates**

Run:

```powershell
$env:PYTHONPATH = "$PWD\src"
.venv\Scripts\python.exe tools\verify_project_manifest.py
.venv\Scripts\python.exe tools\verify_counts.py
```

Expected: both commands exit 0; the new plan is indexed and the document census is owned only by
`HANDOFF.md` section 2.

- [ ] **Step 3: Commit the approved plan as its own baseline**

```powershell
git add docs/08-pm/plans/2026-08-10-directory-automation.md docs/decisions/DR-008-directory-automation.md docs/decisions/measurements/directory-file-sizes-2026-08-10.json docs/decisions/README.md docs/README.md registry/project_manifest.yml HANDOFF.md
git commit -m "docs: plan guarded directory automation"
```

Expected: a documentation-only commit that can be reviewed or reverted independently of runtime
work.

---

### Task 1: Record the Owner Decision and Load One Policy

**Files:**

- Create: `registry/directory_pull_policy.yml`
- Create: `.swingdesk-local.example.json`
- Create: `tools/directory_pull.py`
- Create: `tests/test_directory_pull.py`
- Modify: `.gitignore`

**Interfaces:**

- Consumes: `registry/directory_pull_policy.yml`, `.swingdesk-local.json`.
- Produces:
  - `DirectoryPolicy` and `DirectorySource` frozen dataclasses.
  - `LocalSwitch(enabled: bool, state: str)`.
  - `load_policy(path: Path) -> DirectoryPolicy`.
  - `load_local_switch(path: Path) -> LocalSwitch`.

- [ ] **Step 1: Verify the accepted design inputs**

Read `DR-008` and its measurement before writing policy or code. The measurement is a historical
record rather than a live project census. Its exact content comes from the completed 2026-08-10 HEAD
check; do not issue another request merely to recreate it:

```json
{
  "schema_version": 1,
  "observed_on": "2026-08-10",
  "method": "HEAD",
  "sources": [
    {
      "url": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
      "content_length": 346612,
      "last_modified": "Tue, 11 Aug 2026 01:31:22 GMT"
    },
    {
      "url": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
      "content_length": 534704,
      "last_modified": "Tue, 11 Aug 2026 01:31:22 GMT"
    }
  ]
}
```

The DR cites that file without copying its measured byte values into another document. Confirm its
decision section freezes:

- daily post-scan execution on NYSE sessions;
- explicit ignored local enablement;
- normal retry budget and unlimited explicit `FORCED` invocations;
- 2 MiB per-file cap;
- atomic two-file validation;
- immutable replacement, compact audit and gap semantics;
- scan return-code independence.

The DR status is `accepted — ratified by the owner 2026-08-10` and its alternatives include manual
only, a separate scheduled task, unconditional enabling, automatic backfill and an unbounded retry
loop.

- [ ] **Step 2: Write the committed policy and safe local example**

Create exactly this policy shape:

```yaml
schema_version: 1
decision: DR-008
measurement: docs/decisions/measurements/directory-file-sizes-2026-08-10.json
source_timezone: America/New_York
request_timeout_seconds: 30
max_file_bytes: 2097152
normal:
  max_attempts: 2
  retry_delay_seconds: 60
forced:
  max_attempts_per_invocation: 1
  daily_invocation_limit: null
  reason_required: true
staleness:
  warning_after_missed_sessions: 1
  error_after_missed_sessions: 2
automatic_backfill: false
sources:
  - name: nasdaqlisted.txt
    url: https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt
    header: Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
  - name: otherlisted.txt
    url: https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt
    header: ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
```

Create `.swingdesk-local.example.json` as:

```json
{
  "directory_pull_enabled": false
}
```

Add only `.swingdesk-local.json` to `.gitignore`.

- [ ] **Step 3: Write failing policy/config tests**

```python
from pathlib import Path

import pytest

from tools.directory_pull import ConfigurationError, load_local_switch, load_policy


def test_policy_has_no_runtime_default() -> None:
    policy = load_policy(Path("registry/directory_pull_policy.yml"))
    assert policy.max_file_bytes == 2 * 1024 * 1024
    assert policy.normal_max_attempts == 2
    assert policy.forced_max_attempts == 1
    assert policy.forced_daily_invocation_limit is None
    assert tuple(source.name for source in policy.sources) == (
        "nasdaqlisted.txt", "otherlisted.txt"
    )


def test_missing_local_switch_is_explicitly_disabled(tmp_path: Path) -> None:
    switch = load_local_switch(tmp_path / ".swingdesk-local.json")
    assert switch.enabled is False
    assert switch.state == "MISSING"


def test_malformed_local_switch_refuses(tmp_path: Path) -> None:
    path = tmp_path / ".swingdesk-local.json"
    path.write_text('{"directory_pull_enabled": "yes"}', encoding="utf-8")
    with pytest.raises(ConfigurationError, match="must be boolean"):
        load_local_switch(path)
```

- [ ] **Step 4: Run the tests and verify the expected failure**

Run:

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.venv\Scripts\python.exe -m pytest tests\test_directory_pull.py -v
```

Expected: collection fails because `tools.directory_pull` does not exist.

- [ ] **Step 5: Implement strict loaders without fallback values**

`DirectoryPolicy` contains typed fields for every YAML key; `load_policy()` rejects missing,
additional or wrongly typed keys and parses sources in file order. `load_local_switch()` implements
three states: `MISSING`, `DISABLED`, `ENABLED`; invalid JSON, extra keys or a non-boolean value raises
`ConfigurationError`. It never converts strings or numbers to booleans.

```python
@dataclass(frozen=True, slots=True)
class DirectorySource:
    name: str
    url: str
    header: str


@dataclass(frozen=True, slots=True)
class LocalSwitch:
    enabled: bool
    state: str


@dataclass(frozen=True, slots=True)
class DirectoryPolicy:
    schema_version: int
    decision: str
    measurement: Path
    source_timezone: str
    request_timeout_seconds: int
    max_file_bytes: int
    normal_max_attempts: int
    retry_delay_seconds: int
    forced_max_attempts: int
    forced_daily_invocation_limit: int | None
    forced_reason_required: bool
    warning_after_missed_sessions: int
    error_after_missed_sessions: int
    automatic_backfill: bool
    sources: tuple[DirectorySource, ...]
```

- [ ] **Step 6: Run the focused tests and commit**

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.venv\Scripts\python.exe -m pytest tests\test_directory_pull.py -v
.venv\Scripts\python.exe -m ruff check tools\directory_pull.py tests\test_directory_pull.py
git add .gitignore .swingdesk-local.example.json registry/directory_pull_policy.yml tools/directory_pull.py tests/test_directory_pull.py
git commit -m "feat: load bounded directory policy"
```

Expected: tests and ruff pass; no real local config or network response is committed.

---

### Task 2: Make the Feed Boundary Strict and Bounded

**Files:**

- Modify: `tools/directory_pull.py`
- Modify: `src/swingdesk/reference_data/universe.py`
- Modify: `tests/test_directory_pull.py`
- Modify: `tests/test_universe.py`

**Interfaces:**

- Consumes: `DirectorySource`, `DirectoryPolicy`, injectable `UrlOpen`.
- Produces:
  - `FetchedFile(name: str, body: bytes, bytes_received: int, sha256: str)`.
  - `ValidatedFile(name: str, created_at: datetime, entries: tuple[DirectoryEntry, ...],
    bytes_received: int, sha256: str)`.
  - `download(source, policy, *, urlopen) -> FetchedFile`.
  - `validate_file(source, fetched, timezone) -> ValidatedFile`.
  - `FeedError(code: str, message: str, bytes_received: int = 0)`.

- [ ] **Step 1: Write failing bounded-download tests**

Use a small fake response implementing `headers`, `read(size)`, `__enter__` and `__exit__`. Assert:

```python
def test_content_length_over_cap_is_refused_before_body_read(policy, fake_response) -> None:
    fake_response.headers["Content-Length"] = str(policy.max_file_bytes + 1)
    with pytest.raises(FeedError, match="CONTENT_LENGTH_LIMIT"):
        download(policy.sources[0], policy, urlopen=fake_response.open)
    assert fake_response.read_calls == []


def test_stream_over_cap_is_refused_without_content_length(policy, fake_response) -> None:
    fake_response.headers.clear()
    fake_response.body = b"x" * (policy.max_file_bytes + 1)
    with pytest.raises(FeedError, match="BODY_LIMIT"):
        download(policy.sources[0], policy, urlopen=fake_response.open)
    assert fake_response.read_calls == [policy.max_file_bytes + 1]
```

Also assert that the request uses the fixed URL, the configured 30-second timeout and the existing
`swingdesk/0.0` user agent.

- [ ] **Step 2: Write failing structural-validation tests**

Cover exact header, strict UTF-8, exactly eight fields per data row, non-empty symbol, exactly one
final creation-time trailer, a parseable exchange-local timestamp and at least one parsed row.

```python
def test_invalid_utf8_is_not_replaced(policy) -> None:
    fetched = FetchedFile("nasdaqlisted.txt", b"\xff", 1, "probe")
    with pytest.raises(FeedError, match="UTF8"):
        validate_file(policy.sources[0], fetched, policy.source_timezone)


def test_short_data_row_is_not_silently_skipped(policy, nasdaq_body) -> None:
    body = nasdaq_body.replace(b"TEST1|Synthetic|Q|N|N|100|N|N", b"TEST1|Synthetic|Q")
    fetched = fetched_file("nasdaqlisted.txt", body)
    with pytest.raises(FeedError, match="ROW_SHAPE"):
        validate_file(policy.sources[0], fetched, policy.source_timezone)
```

In `tests/test_universe.py`, add direct parser cases proving a malformed row raises `ValueError`
instead of disappearing from the snapshot.

- [ ] **Step 3: Run the tests and verify they fail on current behavior**

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.venv\Scripts\python.exe -m pytest tests\test_directory_pull.py tests\test_universe.py -v
```

Expected: size/validation symbols are absent and the current parser silently skips short rows.

- [ ] **Step 4: Implement bounded reading and exact validation**

The production reader performs these operations in order:

1. Build `urllib.request.Request` from the committed `DirectorySource.url`.
2. Open with `policy.request_timeout_seconds`.
3. Reject a missing-numeric or over-limit `Content-Length` when the header is present.
4. Read at most `policy.max_file_bytes + 1` bytes and reject an oversized body.
5. Compute SHA-256 only for an in-limit body.
6. Decode UTF-8 with `errors="strict"`.
7. Require exact header and trailer positions, exact row width and non-empty parsed entries.
8. Parse `File Creation Time: MMDDYYYYHH:MM` in `America/New_York`.

`parse_nasdaq_listed()` and `parse_other_listed()` raise on every non-trailer row with the wrong
shape. Validation remains in `tools` because source transport is operational; the pure parsers stay
in `reference_data`.

- [ ] **Step 5: Run focused tests and commit**

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.venv\Scripts\python.exe -m pytest tests\test_directory_pull.py tests\test_universe.py -v
.venv\Scripts\python.exe -m ruff check tools\directory_pull.py src\swingdesk\reference_data\universe.py tests\test_directory_pull.py tests\test_universe.py
git add tools/directory_pull.py src/swingdesk/reference_data/universe.py tests/test_directory_pull.py tests/test_universe.py
git commit -m "feat: validate bounded directory responses"
```

Expected: all tests pass without touching the network.

---

### Task 3: Make Directory Records Immutable and Session-Aware

**Files:**

- Modify: `src/swingdesk/reference_data/directory.py`
- Modify: `tests/test_directory.py`

**Interfaces:**

- Consumes: validated entries and source metadata from Task 2.
- Produces:
  - `PullMode.NORMAL` and `PullMode.FORCED`.
  - `SnapshotMetadata` and `PullAudit` frozen dataclasses.
  - `DirectoryStore.record_snapshot(entries, metadata, audit, *, supersedes=None,
    gaps=()) -> int`.
  - `DirectoryStore.record_audit(audit) -> None`.
  - `DirectoryStore.snapshot_for_session(session_date) -> datetime | None`.
  - `DirectoryStore.latest_session() -> date | None`.
  - `DirectoryStore.gaps(start, end) -> tuple[date, ...]`.
  - Existing `latest_pull()` and `as_of()` ignore superseded snapshots.

Use these exact records at the store boundary:

```python
class PullMode(StrEnum):
    NORMAL = "NORMAL"
    FORCED = "FORCED"


@dataclass(frozen=True, slots=True)
class SnapshotMetadata:
    knowledge_time: datetime
    session_date: date
    source: str
    nasdaq_created_at: datetime
    other_created_at: datetime
    nasdaq_sha256: str
    other_sha256: str
    mode: PullMode
    forced_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PullAudit:
    run_id: str
    started_at: datetime
    finished_at: datetime
    session_date: date | None
    enabled: bool
    mode: PullMode
    reason: str | None
    attempts: int
    http_requests: int
    bytes_received: int
    result_code: str
    snapshot_time: datetime | None
```

- [ ] **Step 1: Write failing immutability and metadata tests**

Replace the existing same-instant replacement expectation with refusal:

```python
def test_recording_the_same_instant_twice_refuses_without_mutating(store) -> None:
    store.record([_entry("TEST1")], MONDAY, "fixture")
    with pytest.raises(ValueError, match="already exists"):
        store.record([_entry("TEST2")], MONDAY, "fixture")
    assert [entry.symbol for entry in store.as_of(MONDAY)] == ["TEST1"]
```

Add tests proving a session-aware snapshot exposes its exact session and that legacy rows remain
readable but do not masquerade as exact-session observations.

- [ ] **Step 2: Write failing transaction, audit and supersession tests**

```python
def test_forced_replacement_keeps_both_snapshots_and_reads_the_replacement(store) -> None:
    first = _snapshot(MONDAY, session_date=MONDAY.date(), mode=PullMode.NORMAL)
    second = _snapshot(FRIDAY, session_date=MONDAY.date(), mode=PullMode.FORCED,
                       reason="validated parser defect")
    store.record_snapshot([_entry("TEST1")], first, _audit(first))
    store.record_snapshot([_entry("TEST2")], second, _audit(second), supersedes=MONDAY)
    assert [entry.symbol for entry in store.as_of(FRIDAY)] == ["TEST2"]
    assert store.pulls() == ((MONDAY, "fixture", 1), (FRIDAY, "fixture", 1))


def test_failed_replacement_cannot_supersede_the_last_valid_snapshot(store) -> None:
    first = _snapshot(MONDAY, session_date=MONDAY.date(), mode=PullMode.NORMAL)
    store.record_snapshot([_entry("TEST1")], first, _audit(first))
    with pytest.raises(ValueError, match="empty directory pull"):
        store.record_snapshot([], _snapshot(FRIDAY, session_date=MONDAY.date(),
                              mode=PullMode.FORCED, reason="bad source"),
                              _audit_result("EMPTY"), supersedes=MONDAY)
    assert [entry.symbol for entry in store.as_of(FRIDAY)] == ["TEST1"]
```

Add one test that forces a database exception after directory-row insertion and verifies the
transaction leaves no partial pull, audit or supersession row.

- [ ] **Step 3: Write failing gap tests**

Record missed session dates as individual immutable rows. Duplicate detection uses insert-if-absent,
not update.

```python
def test_detected_gaps_are_exact_dates_and_idempotent(store) -> None:
    missed = (date(2026, 1, 13), date(2026, 1, 14))
    snapshot = _snapshot(FRIDAY)
    store.record_snapshot([_entry("TEST1")], snapshot, _audit(snapshot), gaps=missed)
    assert store.gaps(date(2026, 1, 1), date(2026, 1, 31)) == missed
```

- [ ] **Step 4: Run the focused store tests and verify failure**

```powershell
$env:PYTHONPATH = "$PWD\src"
.venv\Scripts\python.exe -m pytest tests\test_directory.py -v
```

Expected: the existing store replaces rows and has no metadata, audit, supersession or gap APIs.

- [ ] **Step 5: Implement additive schema migration and transactional writes**

Keep existing tables and rows. Add nullable metadata columns to `directory_pulls` so legacy pulls
survive unchanged, plus append-only tables:

```sql
CREATE TABLE IF NOT EXISTS directory_pull_audit (
    run_id          VARCHAR PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ NOT NULL,
    session_date    DATE,
    enabled         BOOLEAN NOT NULL,
    mode            VARCHAR NOT NULL,
    reason          VARCHAR,
    attempts        INTEGER NOT NULL,
    http_requests   INTEGER NOT NULL,
    bytes_received  BIGINT NOT NULL,
    result_code     VARCHAR NOT NULL,
    snapshot_time   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS directory_snapshot_supersessions (
    superseded_at       TIMESTAMPTZ NOT NULL,
    superseded_snapshot TIMESTAMPTZ PRIMARY KEY,
    replacement_snapshot TIMESTAMPTZ UNIQUE NOT NULL,
    reason              VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS directory_gaps (
    session_date        DATE PRIMARY KEY,
    detected_at         TIMESTAMPTZ NOT NULL,
    previous_session    DATE NOT NULL,
    next_session        DATE NOT NULL
);
```

Add `session_date`, both source timestamps, both SHA-256 values, `mode` and `forced_reason` to
`directory_pulls`. Use explicit `BEGIN`/`COMMIT`/`ROLLBACK`; remove both `DELETE` and
`INSERT OR REPLACE` from snapshot writes. `latest_pull()` excludes every snapshot appearing in the
superseded column, while `pulls()` remains the complete immutable census.

- [ ] **Step 6: Run store and downstream tests**

```powershell
$env:PYTHONPATH = "$PWD\src"
.venv\Scripts\python.exe -m pytest tests\test_directory.py tests\test_universe_selection.py tests\test_pipeline.py -v
.venv\Scripts\python.exe -m mypy
```

Expected: all pass; existing database files migrate when opened and old pulls remain readable.

- [ ] **Step 7: Commit the store boundary**

```powershell
git add src/swingdesk/reference_data/directory.py tests/test_directory.py
git commit -m "feat: preserve immutable directory sessions"
```

---

### Task 4: Implement the Normal Daily Pull

**Files:**

- Modify: `tools/directory_pull.py`
- Modify: `tests/test_directory_pull.py`

**Interfaces:**

- Consumes: Task 1 policy/switch, Task 2 validated files, Task 3 store API,
  `calendar.last_completed_session(Exchange.NYSE, now)` and injected collaborators.
- Produces:
  - `PullRequest(data: Path, config: Path, forced: bool, reason: str | None)`.
  - `PullOutcome(code: str, severity: str, message: str, session_date: date | None,
    last_valid_session: date | None, snapshot_time: datetime | None, attempts: int,
    http_requests: int, bytes_received: int, gaps: tuple[date, ...], arrivals: int,
    departures: int, mode: PullMode, reason: str | None)`.
  - `run(request, *, now, downloader, sleeper, session_lookup) -> PullOutcome`.

- [ ] **Step 1: Write failing zero-request tests**

Use a downloader fake that raises if called. Cover missing switch, explicit false, malformed config,
Saturday, an NYSE holiday and a second normal invocation after a successful snapshot.

```python
def test_disabled_mode_makes_zero_requests(harness) -> None:
    outcome = harness.run(config_enabled=False)
    assert outcome.code == "DISABLED"
    assert outcome.http_requests == 0
    assert harness.download_calls == []


def test_second_normal_run_after_success_makes_zero_requests(harness) -> None:
    first = harness.run(config_enabled=True)
    second = harness.run(config_enabled=True)
    assert first.http_requests == 2
    assert second.code == "ALREADY_CURRENT"
    assert second.http_requests == 0
```

- [ ] **Step 2: Write failing source-date and atomicity tests**

Require both embedded dates to equal the latest completed NYSE session. A mismatch, malformed second
file or empty second parse records a failed audit but no snapshot. A pre-close invocation resolves
to the prior completed session and cannot label intraday current data as completed.

- [ ] **Step 3: Write failing retry-budget tests**

```python
def test_normal_failure_retries_once_after_sixty_seconds(harness) -> None:
    harness.fail_first_attempt("NETWORK")
    outcome = harness.run(config_enabled=True)
    assert outcome.attempts == 2
    assert outcome.http_requests <= 4
    assert harness.sleep_calls == [60]


def test_success_never_uses_the_retry_budget(harness) -> None:
    outcome = harness.run(config_enabled=True)
    assert outcome.attempts == 1
    assert outcome.http_requests == 2
    assert harness.sleep_calls == []
```

Also fail if an injected downloader reports more requests than the policy permits; the runtime guard
must not rely only on tests.

- [ ] **Step 4: Write failing baseline, gap and staleness tests**

The first session-aware snapshot returns zero arrivals/departures. Later snapshots compare only to
the previous valid session-aware snapshot. Missing intermediate NYSE sessions are inserted into
`directory_gaps`. A failed pull reports `WARNING` after one missed session and `ERROR` after two,
without changing or deleting the last valid snapshot.

- [ ] **Step 5: Run the orchestration tests and verify failure**

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.venv\Scripts\python.exe -m pytest tests\test_directory_pull.py -v
```

Expected: the orchestration API is absent.

- [ ] **Step 6: Implement the normal state machine**

The exact order is:

1. Load policy and local switch.
2. Determine the current date in the policy timezone without touching the network.
3. Acquire the process lock and open `DirectoryStore`.
4. For invalid/disabled config, a closed date or `ALREADY_CURRENT`, append one zero-request audit and
   return. If the policy, lock or store itself is unavailable, return a visible failure without
   pretending an audit row was written.
5. Download and validate both allowlisted files sequentially.
6. On failure with an attempt remaining, retain aggregate metrics, sleep once and repeat only in
   normal mode. Append one audit only when the whole invocation finishes.
7. On success, require matching source/completed-session dates; compute arrivals, departures and
   intervening gaps; commit snapshot, gaps and audit in one transaction.
8. Return one structured outcome. No branch prints directly.

Use `datetime.now(UTC)`, `time.sleep`, downloader and session lookup only through defaults supplied
at the outer `run()` boundary so tests inject every nondeterministic dependency.

- [ ] **Step 7: Run tests and commit**

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.venv\Scripts\python.exe -m pytest tests\test_directory_pull.py tests\test_directory.py -v
.venv\Scripts\python.exe -m ruff check tools\directory_pull.py tests\test_directory_pull.py
git add tools/directory_pull.py tests/test_directory_pull.py
git commit -m "feat: collect one directory session daily"
```

---

### Task 5: Add Explicit Unlimited `FORCED` Recovery and Concurrency Control

**Files:**

- Modify: `tools/directory_pull.py`
- Modify: `tests/test_directory_pull.py`

**Interfaces:**

- Consumes: `PullRequest(forced=True, reason="operator supplied recovery reason")` and Task 3
  supersession API.
- Produces: an OS-released non-blocking `directory.pull.lock`; repeated manual forced invocations,
  each limited to one two-file attempt and independently audited.

- [ ] **Step 1: Write failing forced-mode tests**

```python
def test_forced_requires_a_reason_before_any_request(harness) -> None:
    outcome = harness.run(config_enabled=True, forced=True, reason="")
    assert outcome.code == "FORCED_REASON_REQUIRED"
    assert outcome.http_requests == 0


def test_forced_has_no_daily_invocation_quota(harness) -> None:
    first = harness.run(config_enabled=True, forced=True, reason="parser repaired")
    second = harness.run(config_enabled=True, forced=True, reason="source repaired")
    assert first.http_requests == 2
    assert second.http_requests == 2
    assert first.mode is PullMode.FORCED
    assert second.mode is PullMode.FORCED


def test_forced_failure_never_retries_automatically(harness) -> None:
    harness.fail_first_attempt("NETWORK")
    outcome = harness.run(config_enabled=True, forced=True, reason="source check")
    assert outcome.attempts == 1
    assert harness.sleep_calls == []
```

Also prove `FORCED` cannot run when disabled or closed, cannot change URLs, cannot exceed 2 MiB and
cannot replace a canonical snapshot unless both new files validate.

- [ ] **Step 2: Write failing supersession-chain tests**

When a same-session canonical snapshot exists, each successful forced pull supersedes only the
current canonical snapshot. Two forced pulls therefore form an immutable chain; `as_of()` reads the
last member while `pulls()` and audit expose all members and reasons.

- [ ] **Step 3: Write failing overlap tests**

Hold the lock in one context, start a second run with a downloader that raises if called, and assert
`LOCKED`, zero requests and no snapshot mutation. The lock must be released by file-handle closure,
including exception paths; no stale-lock deletion heuristic is allowed.

- [ ] **Step 4: Implement the portable non-blocking file lock**

Open `data/directory.pull.lock` as `a+b`; if it is empty, write and flush one zero byte, then seek to
offset zero. Lock that byte with
`msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)` on Windows and
`fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)` on POSIX. The file may remain; the
operating-system lock is the authority and is released on close. `FORCED` does not bypass it.

- [ ] **Step 5: Run focused and cross-platform-safe tests**

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.venv\Scripts\python.exe -m pytest tests\test_directory_pull.py tests\test_directory.py -v
.venv\Scripts\python.exe -m ruff check tools\directory_pull.py tests\test_directory_pull.py
```

Expected: all pass; the tests use temporary files and no real process or network state.

- [ ] **Step 6: Commit forced recovery**

```powershell
git add tools/directory_pull.py tests/test_directory_pull.py
git commit -m "feat: add audited forced directory recovery"
```

---

### Task 6: Expose the CLI and Wire It After the Scan

**Files:**

- Modify: `tools/fetch_directory.py`
- Modify: `tools/daily_run.cmd`
- Modify: `tests/test_directory_pull.py`

**Interfaces:**

- Consumes: `directory_pull.run()` and `PullOutcome`.
- Produces:
  - normal command: `python tools/fetch_directory.py --data <path> --config <path>`;
  - forced command: `python tools/fetch_directory.py --emergency-repull --reason <text>`;
  - exactly one status line prefixed `[DIRECTORY]` per invocation;
  - exit 0 for recorded/current/disabled/closed expected states, exit 1 for config, lock, network,
    validation, cap or audit failures; argparse exit 2 for invalid CLI shape.

- [ ] **Step 1: Write failing CLI tests**

Patch `directory_pull.run`, call `fetch_directory.main(argv)` and assert exact output. Required
formats are:

```text
[DIRECTORY] OK — snapshot 2026-08-10; mode=NORMAL; requests=2; arrivals=0; departures=0; gaps=0
[DIRECTORY] OK — snapshot 2026-08-10; mode=FORCED; requests=2; reason=parser repaired
[DIRECTORY] DISABLED — local switch is missing; requests=0; last valid=2026-08-08
[DIRECTORY] WARNING — pull failed; missed sessions=1; last valid=2026-08-08
[DIRECTORY] ERROR — pull failed; missed sessions=2; last valid=2026-08-07
```

Do not assert locale-specific batch timestamps. Assert one line, uppercase mode and no response body,
symbol list or traceback in normal failures.

- [ ] **Step 2: Reduce `fetch_directory.py` to an adapter**

The parser keeps `--data`, adds `--config`, `--emergency-repull` and `--reason`, rejects `--reason`
without emergency mode and supplies no URL, retry, cap or enable override. `--data` defaults to the
repository's `data/`; `--config` defaults to the repository's `.swingdesk-local.json`.
`main(argv: Sequence[str] | None = None) -> int` builds `PullRequest`, calls `run()`, prints
`format_status()` once and maps the outcome to the documented process code.

- [ ] **Step 3: Write a failing batch-order test**

Read `tools/daily_run.cmd` as text and assert this strict ordering:

1. scan command;
2. `set RC=%ERRORLEVEL%`;
3. directory command;
4. final `daily run finished` line;
5. `exit /b %RC%`.

Also assert the directory command redirects both streams to `%LOG%` and contains no `set RC=` after
it.

- [ ] **Step 4: Wire the batch file without coupling results**

Replace the commented manual line with:

```bat
"%PY%" -X utf8 "%REPO%\tools\fetch_directory.py" --data "%REPO%\data" --config "%REPO%\.swingdesk-local.json" >> "%LOG%" 2>&1
```

Keep the saved scan code in `%RC%`; directory exit status is intentionally not assigned to it. Move
the `daily run finished` marker after the directory line so the log represents the whole scheduled
wrapper, then exit with `%RC%`.

- [ ] **Step 5: Run CLI/batch tests and commit**

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.venv\Scripts\python.exe -m pytest tests\test_directory_pull.py -v
.venv\Scripts\python.exe -m ruff check tools\fetch_directory.py tools\directory_pull.py tests\test_directory_pull.py
git add tools/fetch_directory.py tools/daily_run.cmd tests/test_directory_pull.py
git commit -m "feat: run directory collection after daily scan"
```

Expected: offline tests pass and the batch test proves directory failures cannot replace the scan
exit code.

---

### Task 7: Gate the Limits and Wiring Explicitly

**Files:**

- Create: `tools/verify_directory_policy.py`
- Modify: `tests/test_gates.py`
- Modify: `tools/check_gates.py`
- Modify: `docs/06-engineering/CI_POLICY.md`

**Interfaces:**

- Consumes: policy YAML, measurement JSON, local example, `.gitignore`, `fetch_directory.py` and
  `daily_run.cmd`.
- Produces: offline gate 19 with exit 0/1 and actionable failures.

- [ ] **Step 1: Build a minimal fixture helper and red tests**

`_directory_policy_tree()` writes the smallest policy/example/batch/tool tree. Add independent tests
that mutate one fact at a time:

```python
def test_directory_gate_rejects_an_unbounded_body(tmp_path: Path) -> None:
    root = _directory_policy_tree(tmp_path)
    policy = root / "registry" / "directory_pull_policy.yml"
    policy.write_text(policy.read_text(encoding="utf-8").replace(
        "max_file_bytes: 2097152", "max_file_bytes: 0"
    ), encoding="utf-8")
    code, out = run_gate("verify_directory_policy.py", root)
    assert code == 1
    assert "max_file_bytes" in out


def test_directory_gate_rejects_a_forced_daily_limit(tmp_path: Path) -> None:
    root = _directory_policy_tree(tmp_path)
    policy = root / "registry" / "directory_pull_policy.yml"
    policy.write_text(policy.read_text(encoding="utf-8").replace(
        "daily_invocation_limit: null", "daily_invocation_limit: 1"
    ), encoding="utf-8")
    code, out = run_gate("verify_directory_policy.py", root)
    assert code == 1
    assert "daily_invocation_limit" in out
```

Add red cases for automatic attempts above two, forced attempts other than one, retry delay drift,
staleness drift, non-HTTPS/non-allowlisted URL, local example enabled, local config not ignored,
directory call before scan, and final exit not using `%RC%`. Add one green consistent-tree test.

- [ ] **Step 2: Run the new tests and verify missing-gate failure**

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.venv\Scripts\python.exe -m pytest tests\test_gates.py -k directory -v
```

Expected: failures because `verify_directory_policy.py` is absent.

- [ ] **Step 3: Implement the verifier**

Use `SWINGDESK_ROOT` like the other gates. Parse YAML/JSON; validate exact keys, types, owner decision
and measurement paths, fixed host/path allowlist, limits, safe local example and batch ordering. Print
every failure and a final factual summary. It never imports `tools.directory_pull`, touches the
network, reads the real local config or writes a file.

- [ ] **Step 4: Wire and document gate 19**

Add to `tools/check_gates.py`:

```python
"19 directory policy": _run(
    "directory automation policy and wiring",
    [python, "tools/verify_directory_policy.py"],
),
```

Place it with the other fast structural verifiers, before ruff. Add gate 19 to the CI inventory and
failure mapping without stating a second live gate count outside `HANDOFF.md` section 2.

- [ ] **Step 5: Run gate tests, the gate itself and commit**

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.venv\Scripts\python.exe -m pytest tests\test_gates.py -k directory -v
.venv\Scripts\python.exe tools\verify_directory_policy.py
.venv\Scripts\python.exe -m ruff check tools\verify_directory_policy.py tests\test_gates.py tools\check_gates.py
git add tools/verify_directory_policy.py tests/test_gates.py tools/check_gates.py docs/06-engineering/CI_POLICY.md
git commit -m "test: gate directory request limits"
```

Expected: the gate has been observed red through mutations and is green on the real tree.

---

### Task 8: Update Canonical Operations and Point-in-Time Documentation

**Files:**

- Modify: `docs/03-data/POINT_IN_TIME_SPEC.md`
- Modify: `docs/06-engineering/SYSTEM_MODES.md`
- Modify: `docs/runbooks/README.md`
- Modify: `HANDOFF.md`

**Interfaces:**

- Consumes: implemented CLI, store schema, policy and gate.
- Produces: one canonical explanation of observation versus gap, one operational recovery procedure,
  and current measured state in its single allowed owner section.

- [ ] **Step 1: Update point-in-time semantics**

Append a dated section that distinguishes:

- `OBSERVED`: both files validated and committed for their embedded completed NYSE session;
- `GAP`: a NYSE session between observed snapshots with no recoverable source snapshot;
- `FORCED`: a new observed version superseding a prior same-session version for a recorded reason;
- a departure: an observation between valid snapshots, never proof of delisting.

State that `as_of()` remains latest-known for the operational universe, while research claiming
continuous survivorship coverage must query `gaps()` and disclose any result.

- [ ] **Step 2: Update runbook commands**

Document local enablement:

```powershell
Copy-Item .swingdesk-local.example.json .swingdesk-local.json
```

Then edit the ignored file to `true`. Document normal inspection and forced recovery:

```powershell
.venv\Scripts\python.exe tools\fetch_directory.py
.venv\Scripts\python.exe tools\fetch_directory.py --emergency-repull --reason "source recovered after malformed first response"
Select-String -Path data\daily_run.log -Pattern "\[DIRECTORY\]" | Select-Object -Last 5
```

State that `FORCED` is repeated by issuing another explicit command; there is no persistent emergency
toggle. Invalid bodies are not retained.

- [ ] **Step 3: Close stale scheduling claims**

Update `SYSTEM_MODES.md` and `HANDOFF.md` to say the scan is scheduled and the directory pull is now
locally gated inside the same wrapper after the scan. Preserve the historical 2026-08-09 manual
decision as history and name `DR-008` as its accepted reversal.

- [ ] **Step 4: Recompute only the counts owned by HANDOFF**

Run:

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.venv\Scripts\python.exe -m pytest --collect-only -q
.venv\Scripts\python.exe tools\verify_counts.py
```

Update only `HANDOFF.md` section 2 with the resulting test and gate censuses. Do not copy those live
counts into this plan, CI policy, runbook or decision record.

- [ ] **Step 5: Run documentation gates and commit**

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.venv\Scripts\python.exe tools\verify_docs.py
.venv\Scripts\python.exe tools\verify_project_manifest.py
.venv\Scripts\python.exe tools\verify_counts.py
git add docs/03-data/POINT_IN_TIME_SPEC.md docs/06-engineering/SYSTEM_MODES.md docs/runbooks/README.md HANDOFF.md
git commit -m "docs: operate directory collection safely"
```

Expected: documentation, manifest and count gates pass; no manual-only statement remains live.

---

### Task 9: Full Verification and Controlled Local Rollout

**Files:**

- Local only: `.swingdesk-local.json`
- Runtime data only: `data/directory.duckdb`, `data/daily_run.log`
- No committed source file changes unless verification exposes a defect.

**Interfaces:**

- Consumes: the complete implementation.
- Produces: a green offline tree, one supervised local status check and an enabled daily switch.

- [ ] **Step 1: Re-check parallel work before final verification**

```powershell
git -c safe.directory=C:/PycharmProjects/SwingDesk worktree list
git -c safe.directory=C:/PycharmProjects/SwingDesk branch -a
git -c safe.directory=C:/PycharmProjects/SwingDesk status --short
```

Expected: every sibling is represented in `HANDOFF.md`; `skills-lock.json` and other owner files are
not staged by this work.

- [ ] **Step 2: Run focused suites**

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.venv\Scripts\python.exe -m pytest tests\test_directory_pull.py tests\test_directory.py tests\test_universe.py tests\test_universe_selection.py tests\test_pipeline.py tests\test_gates.py -v
```

Expected: all pass offline.

- [ ] **Step 3: Run the complete merge-gate command**

```powershell
$env:PYTHONPATH = "$PWD\src"
.venv\Scripts\python.exe tools\check_gates.py
```

Expected: every locally available gate passes; no gate is skipped. A wrong gate is fixed or removed,
never bypassed.

- [ ] **Step 4: Enable locally only after the tree is green**

```powershell
Copy-Item .swingdesk-local.example.json .swingdesk-local.json
```

Change only the ignored local file to:

```json
{
  "directory_pull_enabled": true
}
```

Verify it is ignored:

```powershell
git check-ignore -v .swingdesk-local.json
git status --short
```

Expected: the local file is ignored and no unrelated owner file is staged.

- [ ] **Step 5: Run one supervised normal invocation**

```powershell
.venv\Scripts\python.exe -X utf8 tools\fetch_directory.py --data data --config .swingdesk-local.json
```

Expected: exactly one `[DIRECTORY]` line. On a closed NYSE date or an already-recorded session it
makes zero requests. On an eligible completed session it makes two successful requests and appends
one snapshot. Do not use live `FORCED` merely to test it; forced behavior is covered offline.

- [ ] **Step 6: Inspect the audit without changing it**

Run a read-only DuckDB query through the project interpreter and verify the newest audit row has the
expected mode, request/attempt counts, result code and snapshot reference. Verify no response-body
table or file exists.

- [ ] **Step 7: Run the wrapper once only if the owner wants an end-to-end scheduler rehearsal**

```powershell
cmd /c tools\daily_run.cmd
Get-Content data\daily_run.log -Tail 20
```

Expected: the scan's normal completion/refusal code remains the wrapper result; one directory line
appears after scan output. This step performs the real daily scan and therefore is not run silently
as part of unit verification.

- [ ] **Step 8: Final status and optional publication**

```powershell
git status --short
git log --oneline -10
```

Expected: only the owner's pre-existing untracked files remain. Publishing or opening a pull request
is a separate explicit action after the owner reviews the green implementation.

---

## Acceptance Matrix

| Approved requirement | Enforced by |
|---|---|
| Daily, US sessions only | calendar tests + `run()` ordering |
| Local on/off | ignored JSON switch + config tests |
| Normal request budget | policy, runtime meter, offline tests, gate 19 |
| Unlimited explicit emergency use | `null` daily quota + repeated forced test |
| Every emergency marked `FORCED` | audit schema + CLI/status tests |
| Reason required | CLI and service tests before network access |
| 2 MiB per file | bounded reader + policy gate |
| No automatic backfill | source-date validation + policy gate |
| Atomic two-file snapshot | transaction rollback tests |
| No corrupted/raw-body retention | schema review + failure tests |
| Immutable corrections | append-only supersession chain tests |
| First pull is baseline | baseline test |
| Missed days are gaps | calendar gap tests + `DirectoryStore.gaps()` |
| One-session warning, two-session error | policy + staleness tests + gate 19 |
| One log line, no dashboard | exact formatter/CLI tests |
| Directory failure does not fail scan | batch-order/exit-code gate |
| CI never fetches | injected downloader fixtures + CI policy |

## Rollback Boundary

- Before local enablement, rollback is an ordinary code/config revert.
- After the first automated snapshot, never delete the snapshot, audit or gap rows. Disable the local
  switch, then supersede faulty behavior with a new code/decision version.
- A wrong integrity gate is fixed or removed; `FORCED` never bypasses it.
- A wrong accepted snapshot is replaced by a successful forced snapshot and append-only supersession
  reason. The original remains inspectable and non-canonical.
