# Operator Console, Level 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** one command — `swingdesk status` — answers *"is anything wrong tonight?"* on one screen,
every `swingdesk` command works from any folder, and the handful of operational scripts become
`swingdesk` subcommands — without a new dependency and without a second copy of any logic.

**Architecture:** new behaviour lives in four small modules under `src/swingdesk/presentation/` and
one under `src/swingdesk/platform/`; `cli.py` only registers and dispatches. `status` is split into
a pure `build`/`render` pair (no I/O, fully testable) and a thin `_status` command that reads the
venue, the book and the Task Scheduler. Operational scripts are **run**, not imported: `tools/` is
not a package, and copying their logic into `src/` is the one-logic-in-two-places defect this
repository has paid for repeatedly.

**Tech Stack:** Python ≥ 3.12, argparse (existing), duckdb via `PositionStore` (existing), the
existing `swingdesk.broker` read path. Nothing new is installed.

**Why this, requested by the owner 2026-09-12:** the operations review's medium #4 (no `status`
command) and medium #5 (CLI friction), and the observation that `DEFAULT_DATA = Path("data")` is
relative to wherever the command is typed — so `swingdesk pending` from another folder reads an
empty directory and answers *"no proposals"* about the wrong book.

## Global Constraints

- Interpreter: `C:/PycharmProjects/SwingDesk/.venv/Scripts/python.exe` with `PYTHONPATH=$PWD/src`. Bare `python` fails in this shell. Below, `PY` means that interpreter.
- `mypy --strict` over `src/swingdesk`, `ruff`, and the import-linter layers in `pyproject.toml` must stay clean. `presentation` may import every layer below it; `platform` is the bottom layer and imports nothing from `swingdesk`.
- **No new third-party dependency** (gates 17 and 18). Output stays plain aligned text, like every existing command.
- **Nothing here writes to the venue or the book.** `status` issues GETs only (gate 39's boundary); the passthrough subcommands run scripts that already exist.
- Exit codes follow `swingdesk broker`: `0` in order · `2` unavailable or refused (not agreement) · `3` a `TECH` finding.
- `README.md`'s command block is generated: after any parser change run `PY tools/build_commands.py`. Before any gate run, `PY tools/build_state.py`.
- Every commit: `PY tools/check_gates.py` → **50 of 52** in a worktree (23 and 24 cannot run there) or **52 of 52** on the main checkout.
- Artifacts in English. Comments say why, in this repository's register.

## File Structure

| file | status | responsibility |
|---|---|---|
| `src/swingdesk/presentation/paths.py` | create | where `--data` points when it was not given; `REPO_ROOT` |
| `src/swingdesk/platform/schedule.py` | create | the ONE `schtasks` reader: `query_task`, `verdict`, `read` → `TaskReading` |
| `tools/verify_schedule.py` | modify | gate 26 imports its parser from `platform.schedule` instead of owning it |
| `src/swingdesk/broker/reconcile.py` | modify | `resting_stops()` — the one definition of "the stop in force", used by `unprotected` |
| `src/swingdesk/broker/__init__.py` | modify | export `resting_stops` |
| `src/swingdesk/presentation/pending_view.py` | create | `pending`'s read-time split (`expiry`, `split_pending`), shared by `pending` and `status` |
| `src/swingdesk/presentation/status.py` | create | pure `build()` → `StatusView`, `render()` → lines |
| `src/swingdesk/presentation/passthrough.py` | create | `TOOL_COMMANDS`, `run_tool()` |
| `src/swingdesk/presentation/cli.py` | modify | `--data` default, `status` subcommand, tool dispatch, `_pending` uses `split_pending` |
| `src/swingdesk/validation/backtest/fees.py` | modify | fee schedule path resolved from the package, not the cwd |
| `tests/test_paths.py`, `tests/test_platform_schedule.py`, `tests/test_pending_view.py`, `tests/test_status.py`, `tests/test_passthrough.py` | create | one per module |
| `tests/test_cli.py`, `tests/test_operations_review.py` | modify | integration tests |

`cli.py` (2,295 lines) is **not** split here. That is worth doing and it is a separate risk;
this plan adds only registration and dispatch to it.

---

### Task 1: `--data` resolves from any folder

**Files:**
- Create: `src/swingdesk/presentation/paths.py`
- Modify: `src/swingdesk/presentation/cli.py` (the `DEFAULT_DATA` line near :56, the eight `default=DEFAULT_DATA,` arguments, `main`)
- Modify: `src/swingdesk/validation/backtest/fees.py:69`
- Modify: `registry/project_manifest.yml`, `docs/README.md` (register this plan)
- Test: `tests/test_paths.py`, `tests/test_cli.py`

**Interfaces:**
- Produces: `paths.ENV: str`, `paths.REPO_ROOT: Path`, `paths.default_data(cwd: Path | None = None, environ: Mapping[str, str] | None = None, repo_root: Path | None = None) -> Path`

- [ ] **Step 1: Write the failing tests**

`tests/test_paths.py`:

```python
"""Where `--data` points when nobody said.

`DEFAULT_DATA = Path("data")` was relative to the folder the command was typed in, so `pending` run
from anywhere else read an empty directory and answered "nothing pending" - a confident answer about
the wrong book. Four rules, first match wins, and each is pinned here.
"""

from __future__ import annotations

from pathlib import Path

from swingdesk.presentation import paths
from swingdesk.presentation.paths import ENV, default_data


def test_the_environment_wins(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    chosen = tmp_path / "elsewhere"
    assert default_data(cwd=tmp_path, environ={ENV: str(chosen)}, repo_root=tmp_path) == chosen


def test_an_empty_environment_value_is_ignored(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    assert default_data(cwd=tmp_path, environ={ENV: ""}, repo_root=repo) == repo / "data"


def test_a_data_directory_here_wins_over_the_checkout(tmp_path: Path) -> None:
    here, repo = tmp_path / "here", tmp_path / "repo"
    (here / "data").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    assert default_data(cwd=here, environ={}, repo_root=repo) == here / "data"


def test_from_anywhere_else_the_checkouts_data_is_found(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    assert default_data(cwd=tmp_path, environ={}, repo_root=repo) == repo / "data"


def test_with_no_data_anywhere_the_old_relative_default_stands(tmp_path: Path) -> None:
    """A missing directory still fails where it always failed, not somewhere new."""
    assert default_data(cwd=tmp_path, environ={}, repo_root=tmp_path / "repo") == Path("data")


def test_repo_root_is_the_checkout() -> None:
    assert (paths.REPO_ROOT / "pyproject.toml").is_file()


def test_the_fee_schedule_does_not_depend_on_the_folder_the_command_ran_in() -> None:
    from swingdesk.validation.backtest.fees import DEFAULT_SCHEDULE_PATH

    assert DEFAULT_SCHEDULE_PATH.is_absolute()
    assert DEFAULT_SCHEDULE_PATH.is_file()
```

Append to `tests/test_cli.py`, after `test_pending_lists_only_the_latest_stop_move_and_counts_the_ones_it_replaced`:

```python
def test_data_is_found_from_any_folder_when_not_given(tmp_path, monkeypatch, capsys) -> None:
    """The review's medium #5, measured: `pending` typed outside the checkout read an empty `data`."""
    from swingdesk.presentation import paths

    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    _seeded(repo / "data")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.delenv(paths.ENV, raising=False)
    monkeypatch.setattr(paths, "REPO_ROOT", repo)
    capsys.readouterr()

    assert cli.main(["pending", "--as-of", "2026-08-18T22:00:00"]) == 0
    assert "1 proposal(s) awaiting your answer" in capsys.readouterr().out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_paths.py tests/test_cli.py::test_data_is_found_from_any_folder_when_not_given -q`
Expected: FAIL — `ModuleNotFoundError: swingdesk.presentation.paths`.

- [ ] **Step 3: Implement `paths.py`**

```python
"""Where the data directory is when `--data` was not given.

`DEFAULT_DATA = Path("data")` was relative to wherever the command was typed, so `swingdesk
pending` from any other folder read an empty directory and answered "nothing pending" - a
confident answer about the wrong book (the owner's operations review, 2026-09-12, medium #5).

Resolution, first match wins:

1. `$SWINGDESK_DATA`, when set and non-empty - the owner said so;
2. `./data`, when it exists - exactly what every command did before;
3. `<checkout>/data`, when it exists - an editable install knows where its checkout is;
4. `Path("data")` - the old default, so a missing directory fails where it always failed.

`registry/parameters.yml` and `registry/broker_policy.yml` were already resolved from the package
(`parents[3]`), which is why only the data directory needed this.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

ENV = "SWINGDESK_DATA"

#: `src/swingdesk/presentation/paths.py`, three levels below the checkout - the same arithmetic
#: `platform/parameters.py` uses for `REGISTRY_PATH`.
REPO_ROOT = Path(__file__).resolve().parents[3]


def default_data(
    cwd: Path | None = None,
    environ: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
) -> Path:
    env = os.environ if environ is None else environ
    chosen = env.get(ENV, "")
    if chosen:
        return Path(chosen)
    here = (Path.cwd() if cwd is None else cwd) / "data"
    if here.is_dir():
        return here
    rooted = (REPO_ROOT if repo_root is None else repo_root) / "data"
    if rooted.is_dir():
        return rooted
    return Path("data")
```

- [ ] **Step 4: Wire it into `cli.py`**

1. Add to the imports block, beside `from swingdesk.presentation import notify, report`:
   `from swingdesk.presentation.paths import default_data`
2. Replace every `default=DEFAULT_DATA,` with `default=None,` (eight occurrences; replace-all), and delete the line `DEFAULT_DATA = Path("data")`.
3. In `main`, immediately after the line that assigns `args = parser.parse_args(...)`, add:

```python
    # Resolved HERE rather than in `default=`: a computed default would be evaluated at import time,
    # and `tools/build_commands.py`, which reads the tree, would render a machine-specific absolute
    # path into README.md. `paths.default_data` says where it looks and in what order.
    if getattr(args, "data", "") is None:
        args.data = default_data()
```

- [ ] **Step 5: Fix the fee schedule path**

In `src/swingdesk/validation/backtest/fees.py`, replace
`DEFAULT_SCHEDULE_PATH = Path("registry/fee_schedule.yml")` with:

```python
#: Resolved from the package, like `REGISTRY_PATH` and `POLICY_PATH`: a relative path read the
#: folder the command was typed in (found 2026-09-12 while making `--data` work from anywhere).
#: `backtest/fees.py` is four levels below the checkout.
DEFAULT_SCHEDULE_PATH = Path(__file__).resolve().parents[4] / "registry" / "fee_schedule.yml"
```

- [ ] **Step 6: Register this plan document**

Append to `registry/project_manifest.yml`:

```yaml
- id: DOC-71
  display_number: '71'
  tier_ref: TIER-8
  artifact_class: PRIMARY_DELIVERABLE
  path: docs/08-pm/plans/2026-09-12-operator-console.md
  document_status: drafting
  status_source: document
  readme_status_text: drafting
  generated: false
  file_expected: true
```

Add to `docs/README.md`, directly after the row for `02-domain/STRATEGY_CONTRACT.md`:

```markdown
| 71 | `08-pm/plans/2026-09-12-operator-console.md` | Level 1 of the operator console: `swingdesk status` on one screen, `--data` that works from any folder, and the operational scripts as subcommands - no new dependency, no second copy of any logic | drafting |
```

If gate 14 names a different `tier_ref` or count, use what it names.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_paths.py tests/test_cli.py -q`
Expected: PASS, including every existing `test_cli.py` test.

- [ ] **Step 8: Regenerate, gate, commit**

```bash
PYTHONPATH=$PWD/src PY tools/build_commands.py && PYTHONPATH=$PWD/src PY tools/build_state.py && PYTHONPATH=$PWD/src PY tools/check_gates.py
```

```bash
git add -A && git commit -m "--data resolves from any folder, and the fee schedule stops reading the cwd"
```

---

### Task 2: one `schtasks` reader

**Files:**
- Create: `src/swingdesk/platform/schedule.py`
- Modify: `tools/verify_schedule.py`
- Test: `tests/test_platform_schedule.py` (existing `tests/test_gates.py` schedule tests must pass unchanged)

**Interfaces:**
- Produces: `schedule.RUN_TASKS: tuple[str, ...]`, `schedule.TASKS`, `schedule.CLEAN_RESULTS`, `schedule.NO_RESULT_YET`, `schedule.DIAGNOSED`, `schedule.HAZARDS`, `schedule.query_task(task: str) -> dict[str, str] | None`, `schedule.verdict(last_result: str) -> tuple[str, str]`, `schedule.TaskReading` (frozen dataclass: `task, state, next_run, last_run, judgement, phrase`), `schedule.read(task: str) -> TaskReading | None`

- [ ] **Step 1: Write the failing test**

`tests/test_platform_schedule.py`:

```python
"""The Task Scheduler, read once. Gate 26 and `swingdesk status` must agree on what a result means,
so they share one parser - a second copy is how `267009` (still running) was once called a crash."""

from __future__ import annotations

import pytest

from swingdesk.platform import schedule

RECORD = {
    "Scheduled Task State": "Enabled",
    "Next Run Time": "9/14/2026 6:30:00 PM",
    "Last Run Time": "9/11/2026 6:30:00 PM",
    "Last Result": "0",
}


def test_off_windows_nothing_is_read(monkeypatch) -> None:
    monkeypatch.setattr(schedule.sys, "platform", "linux")
    assert schedule.read("SwingDesk daily run") is None


def test_a_task_that_is_not_registered_reads_none(monkeypatch) -> None:
    monkeypatch.setattr(schedule.sys, "platform", "win32")
    monkeypatch.setattr(schedule, "query_task", lambda task: None)
    assert schedule.read("SwingDesk daily run") is None


def test_one_task_is_summarised(monkeypatch) -> None:
    monkeypatch.setattr(schedule.sys, "platform", "win32")
    monkeypatch.setattr(schedule, "query_task", lambda task: dict(RECORD))
    assert schedule.read("SwingDesk daily run") == schedule.TaskReading(
        task="SwingDesk daily run", state="Enabled", next_run="9/14/2026 6:30:00 PM",
        last_run="9/11/2026 6:30:00 PM", judgement="clean", phrase="exit 0")


@pytest.mark.parametrize(("code", "judgement"), [("267009", "pending"), ("-1", "crash"), ("2", "clean")])
def test_the_result_is_judged_by_the_shared_verdict(monkeypatch, code, judgement) -> None:
    monkeypatch.setattr(schedule.sys, "platform", "win32")
    monkeypatch.setattr(schedule, "query_task", lambda task: {**RECORD, "Last Result": code})
    reading = schedule.read("SwingDesk daily run")
    assert reading is not None and reading.judgement == judgement


def test_the_run_tasks_lead_the_task_list() -> None:
    assert schedule.TASKS[: len(schedule.RUN_TASKS)] == schedule.RUN_TASKS
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_platform_schedule.py -q`
Expected: FAIL — `ImportError: cannot import name 'schedule'`.

- [ ] **Step 3: Create `src/swingdesk/platform/schedule.py`**

Move these from `tools/verify_schedule.py` **verbatim, comments included**: `TASKS`, `CLEAN_RESULTS`, `NO_RESULT_YET`, `DIAGNOSED`, `HAZARDS`, the function `_query` (renamed `query_task`) and `verdict`. `UNAVAILABLE_EXIT` and `main` stay in the tool. Then split `TASKS` and add the reading:

```python
"""The Windows Task Scheduler, read - one parser, shared by gate 26 and `swingdesk status`.

Moved out of `tools/verify_schedule.py` on 2026-09-12 so that the status screen does not grow a
second opinion about what `267009` means. Stdlib only; `platform` imports nothing above it.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from dataclasses import dataclass

#: The two passes that produce a run. `status` shows these; gate 26 checks every task in `TASKS`.
RUN_TASKS = ("SwingDesk daily run", "SwingDesk second pass")

# ... TASKS, CLEAN_RESULTS, NO_RESULT_YET, DIAGNOSED, HAZARDS moved verbatim, with TASKS rewritten
# as `TASKS = (*RUN_TASKS, "SwingDesk coverage pass", "SwingDesk classification pass")` and its
# existing comments kept above the lines they describe ...

# ... `def query_task(task: str) -> dict[str, str] | None:` - the body of `_query`, verbatim ...

# ... `def verdict(last_result: str) -> tuple[str, str]:` - verbatim ...


@dataclass(frozen=True)
class TaskReading:
    task: str
    state: str
    next_run: str
    last_run: str
    judgement: str
    phrase: str


def read(task: str) -> TaskReading | None:
    """One task, summarised; None off Windows or when the task is not registered."""
    if sys.platform != "win32":
        return None
    record = query_task(task)
    if record is None:
        return None
    judgement, phrase = verdict((record.get("Last Result") or "").strip())
    return TaskReading(
        task=task,
        state=(record.get("Scheduled Task State") or "").strip(),
        next_run=(record.get("Next Run Time") or "?").strip(),
        last_run=(record.get("Last Run Time") or "").strip(),
        judgement=judgement,
        phrase=phrase,
    )
```

The three `# ...` lines above stand for code that already exists and is moved without edits.

- [ ] **Step 4: Point `tools/verify_schedule.py` at it**

Delete the moved definitions and add, after the stdlib imports:

```python
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from swingdesk.platform.schedule import (
    CLEAN_RESULTS,
    DIAGNOSED,
    HAZARDS,
    NO_RESULT_YET,
    TASKS,
    verdict,
)
from swingdesk.platform.schedule import query_task as _query
```

`tests/test_gates.py` reads `verify_schedule.verdict`, `DIAGNOSED` and `CLEAN_RESULTS`; these
names keep resolving through the imports.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_platform_schedule.py tests/test_gates.py -q -k "schedule or verdict or 267"`
Expected: PASS.
Run: `PYTHONPATH=$PWD/src PY tools/verify_schedule.py` — on the scheduling machine it prints the four tasks as before.

- [ ] **Step 6: Gate and commit**

```bash
PYTHONPATH=$PWD/src PY tools/build_state.py && PYTHONPATH=$PWD/src PY tools/check_gates.py
```

```bash
git add -A && git commit -m "One schtasks reader: gate 26 and the status screen share platform.schedule"
```

---

### Task 3: one definition of "the stop in force"

**Files:**
- Modify: `src/swingdesk/broker/reconcile.py` (`unprotected`), `src/swingdesk/broker/__init__.py`
- Test: `tests/test_operations_review.py`

**Interfaces:**
- Produces: `reconcile.resting_stops(live_orders: Sequence[PlacedOrder]) -> dict[str, Decimal]`, exported as `swingdesk.broker.resting_stops`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_operations_review.py`:

```python
# --- the stop in force ---------------------------------------------------------------------------


def _order(symbol: str, kind: str, stop: str | None) -> PlacedOrder:
    return PlacedOrder(
        order_id=f"{kind}-{symbol}-{stop}", client_order_id="", symbol=symbol, status="new",
        submitted_at=datetime(2026, 9, 1, 21, 0, tzinfo=UTC), order_type=kind,
        stop_price=None if stop is None else Decimal(stop),
        observed_at=datetime(2026, 9, 1, 21, 0, tzinfo=UTC),
    )


def test_the_highest_protective_trigger_per_symbol_is_the_one_in_force():
    from swingdesk.broker import resting_stops

    orders = [_order("T", "stop", "100.00"), _order("T", "stop", "101.50"),
              _order("U", "stop_limit", "50.00")]
    assert resting_stops(orders) == {"T": Decimal("101.50"), "U": Decimal("50.00")}


def test_a_take_profit_or_a_triggerless_order_protects_nothing():
    from swingdesk.broker import resting_stops

    assert resting_stops([_order("T", "limit", None), _order("T", "stop", None)]) == {}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_operations_review.py -q -k "in_force or protects_nothing"`
Expected: FAIL — `ImportError: cannot import name 'resting_stops'`.

- [ ] **Step 3: Implement, and make `unprotected` use it**

In `reconcile.py`, after `PROTECTIVE_TYPES`:

```python
def resting_stops(live_orders: Sequence[PlacedOrder]) -> dict[str, Decimal]:
    """The protection actually in force for each symbol: the HIGHEST resting protective trigger.

    The higher trigger fires first, so a lower one behind it changes nothing about the loss. One
    definition, used by `unprotected` and by `swingdesk status`, so the screen cannot show a venue
    stop the check did not compare.
    """
    in_force: dict[str, Decimal] = {}
    for order in live_orders:
        if order.order_type in PROTECTIVE_TYPES and order.stop_price is not None:
            current = in_force.get(order.symbol)
            if current is None or order.stop_price > current:
                in_force[order.symbol] = order.stop_price
    return in_force
```

In `unprotected`, replace the `resting` dict built before the loop, the `stops = resting.get(...)`
lookup and the `highest = max(...)` line with:

```python
    in_force = resting_stops(live_orders)
    ...
        venue = in_force.get(position.instrument_id)
        if venue is None:
            findings.append(Unprotected(
                position.instrument_id, position.current_stop, position.shares, None,
                f"the book records a stop at {position.current_stop} and nothing is resting at "
                f"the venue for {position.shares} shares. A stop the market cannot see is not a "
                f"stop (DR-027 3.2).",
            ))
            continue
        if not same_trigger(venue, position.current_stop, tick_for(position.current_stop)):
            findings.append(Unprotected(
                position.instrument_id, position.current_stop, position.shares, venue,
                f"the book records a stop at {position.current_stop} and the venue is holding one "
                f"at {venue}. Every R this position reports is denominated in the book's number "
                f"(RISK_SPEC 2), and the loss would be taken at the venue's.",
            ))
```

The messages are the existing ones (`venue_word` always rendered `nothing` on that branch). Add
`resting_stops` to both the import line and `__all__` in `src/swingdesk/broker/__init__.py`.

- [ ] **Step 4: Run every protection test**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_operations_review.py tests/test_broker.py tests/test_cli.py tests/test_guard_parity.py -q`
Expected: PASS — the existing `unprotected` tests are the proof the refactor changed nothing.

- [ ] **Step 5: Gate and commit**

```bash
PYTHONPATH=$PWD/src PY tools/build_state.py && PYTHONPATH=$PWD/src PY tools/check_gates.py
```

```bash
git add -A && git commit -m "resting_stops: one definition of the stop in force, used by unprotected"
```

---

### Task 4: `pending`'s split, shared

**Files:**
- Create: `src/swingdesk/presentation/pending_view.py`
- Modify: `src/swingdesk/presentation/cli.py` (`_expiry`, `_pending`)
- Test: `tests/test_pending_view.py` (existing `pending`/`respond`/`_expiry` tests in `tests/test_cli.py` must pass unchanged)

**Interfaces:**
- Produces: `pending_view.expiry(positions: PositionStore, action: ManagementAction, now: datetime) -> bool | Refusal`; `pending_view.PendingSplit` (dataclass: `waiting: list[Pending]`, `expired: list[Pending]`, `superseded: list[Pending]`, `unjudgeable: list[tuple[Pending, Refusal]]`, property `total: int`); `pending_view.split_pending(positions: PositionStore, now: datetime) -> PendingSplit`

- [ ] **Step 1: Write the failing test**

`tests/test_pending_view.py`:

```python
"""`pending`'s read-time split, now shared with `status` - so the two screens cannot disagree
about what is waiting."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from swingdesk.contracts.position import ActionKind, ManagementAction, Position
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.presentation.pending_view import split_pending

NOW = datetime(2026, 8, 18, 22, 0, tzinfo=UTC)


def _store(tmp_path, kinds):
    store = PositionStore(tmp_path / "positions.duckdb")
    store.record(Position(
        position_id="POS-1", version=1, instrument_id="AAPL", opened_on=date(2026, 8, 10),
        entry_price=Decimal(300), shares=8, initial_stop=Decimal(290), current_stop=Decimal(290),
        initial_costs_per_share=Decimal("1.50"), knowledge_time=datetime(2026, 8, 10, tzinfo=UTC)))
    for day, kind in kinds:
        store.propose(ManagementAction(
            position_id="POS-1", proposed_at=datetime(2026, 8, day, 21, 0, tzinfo=UTC), kind=kind,
            reason="fixture", reason_code="STOP" if kind is ActionKind.EXIT_NOW else None,
            old_stop=Decimal(290),
            new_stop=Decimal(290 + day) if kind is ActionKind.MOVE_STOP else None))
    return store


def test_older_stop_moves_are_superseded_and_the_latest_waits(tmp_path) -> None:
    with _store(tmp_path, [(16, ActionKind.MOVE_STOP), (17, ActionKind.MOVE_STOP),
                           (18, ActionKind.MOVE_STOP)]) as store:
        split = split_pending(store, NOW)
    assert [p.sequence for p in split.waiting] == [3]
    assert sorted(p.sequence for p in split.superseded) == [1, 2]
    assert split.total == 3


def test_a_critical_proposal_is_never_superseded(tmp_path) -> None:
    with _store(tmp_path, [(16, ActionKind.EXIT_NOW), (17, ActionKind.MOVE_STOP)]) as store:
        split = split_pending(store, NOW)
    assert {p.action.kind for p in split.waiting} == {ActionKind.EXIT_NOW, ActionKind.MOVE_STOP}
    assert split.superseded == []


def test_nothing_pending_is_an_empty_split(tmp_path) -> None:
    with _store(tmp_path, []) as store:
        split = split_pending(store, NOW)
    assert split.total == 0
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_pending_view.py -q`
Expected: FAIL — `ModuleNotFoundError: swingdesk.presentation.pending_view`.

- [ ] **Step 3: Create `pending_view.py`**

```python
"""`pending`'s read-time split, shared by `swingdesk pending` and `swingdesk status`.

Moved out of `cli.py` on 2026-09-12 so the status screen counts what `pending` lists, by the same
rules, rather than a second reading of `DR-013`. Nothing here writes: expiry and supersession are
both read-time, and `PositionStore.pending` says why a stored status would be wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from swingdesk.contracts.position import ManagementAction
from swingdesk.journal_evidence.positions import Pending, PositionStore
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset
from swingdesk.reference_data import calendar as cal
from swingdesk.trade_management import manage
from swingdesk.trade_management.sizing import Refusal


def expiry(positions: PositionStore, action: ManagementAction, now: datetime) -> bool | Refusal:
    # ... the body and docstring of `cli._expiry`, moved verbatim ...


@dataclass
class PendingSplit:
    waiting: list[Pending] = field(default_factory=list)
    expired: list[Pending] = field(default_factory=list)
    superseded: list[Pending] = field(default_factory=list)
    unjudgeable: list[tuple[Pending, Refusal]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (len(self.waiting) + len(self.expired) + len(self.superseded)
                + len(self.unjudgeable))


def split_pending(positions: PositionStore, now: datetime) -> PendingSplit:
    """Superseded BEFORE expiry: an older stop move a newer one replaced is the same question asked
    on staler data, whether or not it has also aged out (`manage.superseded`)."""
    everything = positions.pending()
    replaced = manage.superseded(
        [(item.action.position_id, item.sequence, item.action.kind) for item in everything])
    out = PendingSplit()
    for item in everything:
        if (item.action.position_id, item.sequence) in replaced:
            out.superseded.append(item)
            continue
        verdict = expiry(positions, item.action, now)
        if isinstance(verdict, Refusal):
            out.unjudgeable.append((item, verdict))
        elif verdict:
            out.expired.append(item)
        else:
            out.waiting.append(item)
    return out
```

The `# ...` line stands for the existing `_expiry` body, moved without edits.

- [ ] **Step 4: Point `cli.py` at it**

1. Add to the imports: `from swingdesk.presentation.pending_view import expiry as _expiry` and `from swingdesk.presentation.pending_view import split_pending`. The alias keeps `_respond` and the two `cli._expiry` tests working.
2. Delete `def _expiry(...)` from `cli.py`.
3. In `_pending`, replace everything from `everything = positions.pending()` through the end of the `for item in everything:` loop with:

```python
        split = split_pending(positions, now)
        waiting, expired, unjudgeable, older = (
            split.waiting, split.expired, split.unjudgeable, split.superseded)
        everything = split.total
```

   The rest of `_pending` reads `waiting`, `expired`, `unjudgeable`, `older` and `if not everything:`, and needs no other change.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_pending_view.py tests/test_cli.py tests/test_positions.py -q`
Expected: PASS.

- [ ] **Step 6: Gate and commit**

```bash
PYTHONPATH=$PWD/src PY tools/build_state.py && PYTHONPATH=$PWD/src PY tools/check_gates.py
```

```bash
git add -A && git commit -m "pending's read-time split, shared: pending_view.split_pending"
```

---

### Task 5: the status view — pure

**Files:**
- Create: `src/swingdesk/presentation/status.py`
- Test: `tests/test_status.py`

**Interfaces:**
- Consumes: `resting_stops` (Task 3), `TaskReading` (Task 2), `PendingSplit` (Task 4), `swingdesk.broker.{reconcile, unprotected, MISMATCH_CODE}`, `swingdesk.broker.armed.Arming`
- Produces: `status.OK`, `NO_STOP`, `WRONG_PRICE`, `UNKNOWN`, `OUT_OF_SCOPE`; `status.PositionLine`; `status.StatusView` with properties `findings: int` and `exit_code: int`; `status.build(*, at, switch, schedule, account, venue_error, book, held, live_orders, split, market, label, tick_for) -> StatusView`; `status.render(view: StatusView) -> list[str]`

- [ ] **Step 1: Write the failing tests**

`tests/test_status.py`:

```python
"""`swingdesk status`, the pure half: every branch of the screen, with no venue and no scheduler.

Exit codes follow `broker`'s because a script reads both for the same answer: 0 in order, 2 the
venue could not be read (NOT agreement), 3 a TECH finding."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from swingdesk.broker.armed import Arming
from swingdesk.contracts.broker import BrokerPosition, PlacedOrder, PositionSide
from swingdesk.contracts.position import ActionKind, ManagementAction, Position
from swingdesk.journal_evidence.positions import Pending
from swingdesk.platform.schedule import TaskReading
from swingdesk.presentation import status
from swingdesk.presentation.pending_view import PendingSplit

AT = datetime(2026, 9, 12, 23, 0, tzinfo=UTC)
ARMED = Arming(armed=True, reason="the switch file is present")
DAILY = TaskReading("SwingDesk daily run", "Ready", "9/14/2026 6:30:00 PM",
                    "9/11/2026 6:30:00 PM", "clean", "exit 0")


def _book(stop: str = "117.044982") -> Position:
    return Position(
        position_id="POS-VGT-2026-09-09", version=1, instrument_id="VGT",
        opened_on=date(2026, 9, 9), entry_price=Decimal("119.658"), shares=20,
        initial_stop=Decimal(115), current_stop=Decimal(stop),
        initial_costs_per_share=Decimal("0.25"),
        knowledge_time=datetime(2026, 9, 9, 20, 0, tzinfo=UTC))


def _held() -> BrokerPosition:
    return BrokerPosition(symbol="VGT", asset_class="us_equity", exchange="ARCA",
                          side=PositionSide("long"), shares=Decimal(20),
                          average_entry_price=Decimal("119.658"), observed_at=AT)


def _stop(price: str) -> PlacedOrder:
    return PlacedOrder(order_id="leg-VGT", client_order_id="", symbol="VGT", status="new",
                       submitted_at=AT, order_type="stop", stop_price=Decimal(price),
                       observed_at=AT)


def _view(**overrides):
    fields = dict(at=AT, switch=ARMED, schedule=(DAILY,), account=None, venue_error=None,
                  book=[_book()], held=[_held()], live_orders=[_stop("117.05")],
                  split=PendingSplit(), market="NYSE", label="Alpaca paper trading",
                  tick_for=lambda _: Decimal("0.01"))
    fields.update(overrides)
    return status.build(**fields)


def test_a_stop_within_a_tick_is_in_order():
    view = _view()
    assert view.positions[0].protection == status.OK
    assert view.positions[0].venue_stop == Decimal("117.05")
    assert view.exit_code == 0


def test_a_stop_a_full_atr_away_is_the_wrong_price():
    view = _view(live_orders=[_stop("115.62")])
    assert view.positions[0].protection == status.WRONG_PRICE
    assert view.exit_code == 3


def test_no_stop_standing_is_tech():
    view = _view(live_orders=[])
    assert view.positions[0].protection == status.NO_STOP
    assert view.exit_code == 3


def test_a_venue_that_could_not_be_read_is_unavailable_not_agreement():
    view = _view(venue_error="the venue did not answer", held=[], live_orders=[])
    assert view.positions[0].protection == status.UNKNOWN
    assert view.exit_code == 2
    assert any("UNAVAILABLE" in line for line in status.render(view))


def test_a_book_the_venue_does_not_hold_is_a_divergence():
    view = _view(held=[])
    assert view.divergences
    assert view.exit_code == 3


def test_the_newest_proposal_is_shown_beside_its_position():
    older = Pending(sequence=4, action=ManagementAction(
        position_id="POS-VGT-2026-09-09", proposed_at=AT, kind=ActionKind.MOVE_STOP,
        reason="x", old_stop=Decimal(115), new_stop=Decimal("116.10")))
    newer = Pending(sequence=5, action=ManagementAction(
        position_id="POS-VGT-2026-09-09", proposed_at=AT, kind=ActionKind.MOVE_STOP,
        reason="x", old_stop=Decimal(115), new_stop=Decimal("117.05")))
    view = _view(split=PendingSplit(waiting=[older, newer]))
    assert view.positions[0].proposal == "#5 MOVE_STOP -> 117.05"
    assert view.waiting == 2


def test_the_screen_carries_every_section():
    lines = "\n".join(status.render(_view()))
    for needle in ("switch     ARMED", "SwingDesk daily run", "VGT", "venue 117.05",
                   "pending    0 awaiting", "verdict    OK"):
        assert needle in lines


def test_no_registered_task_is_said_rather_than_left_blank():
    lines = "\n".join(status.render(_view(schedule=())))
    assert "no task registered on this machine" in lines
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_status.py -q`
Expected: FAIL — `ImportError: cannot import name 'status'`.

- [ ] **Step 3: Implement `status.py`**

```python
"""`swingdesk status` - one screen for the operator. It reads only.

The owner's operations review of 2026-09-12, medium #4: the state of the system was spread over
`broker`, `pending` and the Task Scheduler, and nothing answered the one question - *is anything
wrong tonight?* - on one screen. This module turns values the command has already read into that
screen. It performs no I/O, so every branch is testable without a venue or a scheduler.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from swingdesk.broker import MISMATCH_CODE, reconcile, resting_stops, unprotected
from swingdesk.broker.armed import Arming
from swingdesk.contracts.broker import BrokerAccount, BrokerPosition, PlacedOrder
from swingdesk.contracts.position import Position
from swingdesk.platform.schedule import TaskReading
from swingdesk.presentation.pending_view import PendingSplit

OK = "ok"
NO_STOP = "NO STOP"
WRONG_PRICE = "WRONG PRICE"
UNKNOWN = "UNKNOWN"
OUT_OF_SCOPE = "OUT OF SCOPE"


@dataclass(frozen=True)
class PositionLine:
    instrument_id: str
    shares: int
    entry: Decimal
    book_stop: Decimal
    venue_stop: Decimal | None
    protection: str
    proposal: str | None


@dataclass(frozen=True)
class StatusView:
    at: datetime
    switch: Arming
    schedule: tuple[TaskReading, ...]
    account: BrokerAccount | None
    venue_error: str | None
    positions: tuple[PositionLine, ...]
    divergences: tuple[str, ...]
    waiting: int
    superseded: int
    expired: int
    unjudgeable: int

    @property
    def findings(self) -> int:
        return len(self.divergences) + sum(
            1 for line in self.positions if line.protection in (NO_STOP, WRONG_PRICE))

    @property
    def exit_code(self) -> int:
        """`broker`'s three answers. Unavailable is checked FIRST: a book that could not be compared
        is not in order, and a script reading 0 would be told it was."""
        if self.venue_error is not None:
            return 2
        return 3 if self.findings else 0


def _newest_proposals(split: PendingSplit) -> dict[str, str]:
    newest: dict[str, tuple[int, str]] = {}
    for item in (*split.waiting, *split.expired):
        action = item.action
        phrase = f"#{item.sequence} {action.kind.value.upper()}"
        if action.new_stop is not None:
            phrase += f" -> {action.new_stop}"
        seen = newest.get(action.position_id)
        if seen is None or item.sequence > seen[0]:
            newest[action.position_id] = (item.sequence, phrase)
    return {position_id: phrase for position_id, (_, phrase) in newest.items()}


def build(
    *,
    at: datetime,
    switch: Arming,
    schedule: Sequence[TaskReading],
    account: BrokerAccount | None,
    venue_error: str | None,
    book: Sequence[Position],
    held: Sequence[BrokerPosition],
    live_orders: Sequence[PlacedOrder],
    split: PendingSplit,
    market: str,
    label: str,
    tick_for: Callable[[Decimal], Decimal | None],
) -> StatusView:
    proposals = _newest_proposals(split)
    in_force = resting_stops(live_orders)
    naked: dict[str, bool] = {}
    divergences: tuple[str, ...] = ()
    out_of_scope: set[str] = set()
    if venue_error is None:
        naked = {finding.instrument_id: finding.venue_stop is None
                 for finding in unprotected(book, live_orders, market, tick_for=tick_for)}
        report = reconcile(book, held, venue=label, market=market)
        divergences = tuple(f"{d.reason} {d.instrument_id}" for d in report.divergences)
        out_of_scope = set(report.out_of_scope)

    lines: list[PositionLine] = []
    for position in book:
        if venue_error is not None:
            protection = UNKNOWN
        elif position.instrument_id in out_of_scope:
            protection = OUT_OF_SCOPE
        elif position.instrument_id in naked:
            protection = NO_STOP if naked[position.instrument_id] else WRONG_PRICE
        else:
            protection = OK
        lines.append(PositionLine(
            instrument_id=position.instrument_id, shares=position.shares,
            entry=position.entry_price, book_stop=position.current_stop,
            venue_stop=in_force.get(position.instrument_id), protection=protection,
            proposal=proposals.get(position.position_id)))

    return StatusView(
        at=at, switch=switch, schedule=tuple(schedule), account=account,
        venue_error=venue_error, positions=tuple(lines), divergences=divergences,
        waiting=len(split.waiting), superseded=len(split.superseded),
        expired=len(split.expired), unjudgeable=len(split.unjudgeable))


def render(view: StatusView) -> list[str]:
    out = [f"SwingDesk status   {view.at:%Y-%m-%d %H:%M %Z}", ""]
    word = "ARMED" if view.switch.armed else "STOPPED"
    out.append(f"  switch     {word} - {view.switch.reason}")
    if not view.schedule:
        out.append("  schedule   UNAVAILABLE - no task registered on this machine")
    for index, task in enumerate(view.schedule):
        lead = "  schedule   " if index == 0 else "             "
        out.append(f"{lead}{task.task:<22} next {task.next_run} · last {task.last_run} "
                   f"{task.judgement} ({task.phrase})")
    if view.account is not None:
        out.append(f"  account    equity {view.account.equity} · cash {view.account.cash} · "
                   f"{view.account.status}")
    else:
        out.append(f"  account    UNAVAILABLE - {view.venue_error}")

    out += ["", f"positions ({len(view.positions)} open)"]
    if not view.positions:
        out.append("  (none)")
    for line in view.positions:
        venue = "-" if line.venue_stop is None else str(line.venue_stop)
        row = (f"  {line.instrument_id:<8} {line.shares:>6} sh  entry {line.entry}  "
               f"stop {line.book_stop}  venue {venue:<10} {line.protection}")
        if line.proposal:
            row += f"   {line.proposal}"
        out.append(row)
    for divergence in view.divergences:
        out.append(f"  {MISMATCH_CODE}  {divergence}")

    unknown = f" · {view.unjudgeable} AGE UNKNOWN" if view.unjudgeable else ""
    out += ["", f"pending    {view.waiting} awaiting · {view.superseded} superseded · "
                f"{view.expired} expired{unknown}   -> swingdesk pending"]
    if view.exit_code == 2:
        out.append("verdict    UNAVAILABLE - the venue could not be read; that is not agreement")
    elif view.exit_code == 3:
        out.append(f"verdict    {MISMATCH_CODE} - {view.findings} finding(s); new entries pause "
                   f"until resolved (DR-035, DR-036) - swingdesk broker has the detail")
    else:
        out.append("verdict    OK - the venue and the book agree and every stop is standing")
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_status.py -q`
Expected: PASS.

- [ ] **Step 5: Gate and commit**

```bash
PYTHONPATH=$PWD/src PY tools/build_state.py && PYTHONPATH=$PWD/src PY tools/check_gates.py
```

```bash
git add -A && git commit -m "The status view, pure: build and render with no venue and no scheduler"
```

---

### Task 6: `swingdesk status`

**Files:**
- Modify: `src/swingdesk/presentation/cli.py` (parser, dispatch, new `_status`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `status.build`, `status.render`, `StatusView.exit_code` (Task 5), `split_pending` (Task 4), `schedule.read`, `schedule.RUN_TASKS` (Task 2)

- [ ] **Step 1: Write the failing tests** — append to `tests/test_cli.py`:

```python
def test_status_reads_the_book_and_the_venue_and_exits_like_broker(tmp_path, monkeypatch,
                                                                   capsys) -> None:
    """One screen; and a position with no stop standing is TECH here exactly as in `broker`."""
    from swingdesk.contracts.broker import BrokerPosition, PositionSide
    from swingdesk.platform import schedule

    root = _seeded(tmp_path)
    held = [BrokerPosition(symbol="AAPL", asset_class="us_equity", exchange="NASDAQ",
                           side=PositionSide("long"), shares=Decimal(8),
                           average_entry_price=Decimal(300),
                           observed_at=datetime(2026, 8, 18, 21, 0, tzinfo=UTC))]
    _stub_broker(monkeypatch, held)
    monkeypatch.setattr(schedule, "read", lambda task: None)
    capsys.readouterr()

    code = cli.main(["status", "--data", str(root), "--as-of", "2026-08-18T22:00:00"])

    out = capsys.readouterr().out
    assert code == 3
    assert "AAPL" in out and "NO STOP" in out
    assert "1 awaiting" in out
    assert "no task registered on this machine" in out
    assert "switch     STOPPED" in out


def test_status_says_unavailable_and_still_shows_the_book(tmp_path, monkeypatch, capsys) -> None:
    from swingdesk import broker as broker_pkg
    from swingdesk.platform import schedule

    root = _seeded(tmp_path)
    _stub_broker(monkeypatch, [], raises=broker_pkg.BrokerUnavailable("the venue did not answer"))
    monkeypatch.setattr(schedule, "read", lambda task: None)
    capsys.readouterr()

    code = cli.main(["status", "--data", str(root), "--as-of", "2026-08-18T22:00:00"])

    out = capsys.readouterr().out
    assert code == 2, "unavailable is not agreement"
    assert "AAPL" in out and "UNKNOWN" in out
    assert "UNAVAILABLE" in out
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_cli.py -q -k status_`
Expected: FAIL — `argparse` exits 2 with *invalid choice: 'status'*.

- [ ] **Step 3: Register the parser** — in `main`, beside the other `sub.add_parser` calls:

```python
    status_cmd = sub.add_parser(
        "status",
        help="one screen: the switch, the schedule, the account, every stop, what is pending. "
             "Reads only")
    status_cmd.add_argument("--data", type=Path, default=None,
                            help="data directory: $SWINGDESK_DATA, then ./data, then the checkout's")
    status_cmd.add_argument("--as-of", default=None,
                            help="ISO instant to read the book at; defaults to now")
```

and in the dispatch block: `if args.command == "status": return _status(args)`.

- [ ] **Step 4: Implement `_status`** — after `_broker` in `cli.py`:

```python
def _status(args: argparse.Namespace) -> int:
    """One screen, and it reads only. Exit codes are `broker`'s: 0 · 2 unavailable · 3 TECH.

    A venue that cannot be read does not stop the screen: the switch, the schedule, the book and
    the queue are all local, and an operator at 18:35 needs them most on exactly the evening the
    venue is down.
    """
    from swingdesk import broker as broker_pkg
    from swingdesk.platform import schedule as schedule_pkg
    from swingdesk.presentation import status as status_view

    now = (
        FixedClock(datetime.fromisoformat(args.as_of).replace(tzinfo=UTC)).now()
        if args.as_of
        else SystemClock().now()
    )
    try:
        policy = broker_pkg.load_policy()
    except broker_pkg.PolicyRefused as refused:
        print(f"status REFUSED  {refused}", file=sys.stderr)
        return 2
    switch = broker_pkg.read_arming(args.data, policy.write)
    readings = tuple(reading for task in schedule_pkg.RUN_TASKS
                     if (reading := schedule_pkg.read(task)) is not None)

    account = None
    held: Sequence[BrokerPosition] = ()
    live: Sequence[PlacedOrder] = ()
    venue_error: str | None = None
    try:
        client = broker_pkg.open_client(policy)
        account = client.account(now)
        held = client.positions(now)
        live = client.open_orders(now)
    except (broker_pkg.CredentialsMissing, broker_pkg.BrokerUnavailable) as unavailable:
        venue_error = str(unavailable)

    with PositionStore(args.data / "positions.duckdb") as positions:
        book = positions.open_as_of(now)
        split = split_pending(positions, now)

    view = status_view.build(
        at=now, switch=switch, schedule=readings, account=account, venue_error=venue_error,
        book=book, held=held, live_orders=live, split=split, market=policy.market,
        label=policy.label, tick_for=policy.tick_for)
    for line in status_view.render(view):
        print(line)
    return view.exit_code
```

Add `from swingdesk.contracts.broker import BrokerPosition, PlacedOrder` to the `TYPE_CHECKING`
block at the top of `cli.py` (it exists at :11) so the annotations cost nothing at runtime.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_cli.py tests/test_status.py -q`
Expected: PASS.

- [ ] **Step 6: See it on the real account (read-only)**

Run from the main checkout: `.venv/Scripts/python.exe -X utf8 -m swingdesk.presentation.cli status`
Expected: the four positions, VGT's and BTSG's findings until the owner resolves them, exit 3.

- [ ] **Step 7: Regenerate, gate, commit**

```bash
PYTHONPATH=$PWD/src PY tools/build_commands.py && PYTHONPATH=$PWD/src PY tools/build_state.py && PYTHONPATH=$PWD/src PY tools/check_gates.py
```

```bash
git add -A && git commit -m "swingdesk status: the switch, the schedule, the account, every stop and the queue on one screen"
```

---

### Task 7: operational scripts as subcommands

**Files:**
- Create: `src/swingdesk/presentation/passthrough.py`
- Modify: `src/swingdesk/presentation/cli.py` (`main`: early dispatch, six literal parsers)
- Test: `tests/test_passthrough.py`

**Interfaces:**
- Produces: `passthrough.TOOL_COMMANDS: dict[str, str]` (subcommand → script in `tools/`), `passthrough.run_tool(name: str, rest: Sequence[str], repo_root: Path | None = None, runner: Callable[..., Any] = subprocess.run) -> int`

- [ ] **Step 1: Write the failing tests**

`tests/test_passthrough.py`:

```python
"""Operational scripts as `swingdesk` subcommands: the same script, the same interpreter, the
arguments untouched. Two lists must never drift - the mapping and the parsers README can see."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

from swingdesk.presentation import cli, passthrough


def test_every_tool_command_reaches_its_script_with_arguments_untouched(monkeypatch) -> None:
    seen: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(cli, "run_tool", lambda name, rest: seen.append((name, list(rest))) or 0)
    for name in passthrough.TOOL_COMMANDS:
        assert cli.main([name, "--help", "--budget", "5"]) == 0
    assert seen == [(name, ["--help", "--budget", "5"]) for name in passthrough.TOOL_COMMANDS]


def test_every_tool_command_is_a_literal_subcommand_the_readme_can_list() -> None:
    """`tools/build_commands.py` reads the tree and cannot see a parser built in a loop."""
    source = Path(cli.__file__).read_text(encoding="utf-8")
    for name in passthrough.TOOL_COMMANDS:
        assert re.search(rf'add_parser\(\s*"{name}"', source), name


def test_every_mapped_script_exists_in_the_checkout() -> None:
    for script in passthrough.TOOL_COMMANDS.values():
        assert (passthrough.REPO_ROOT / "tools" / script).is_file(), script


def test_a_missing_script_is_unavailable_not_a_crash(tmp_path, capsys) -> None:
    assert passthrough.run_tool("budget", [], repo_root=tmp_path) == 2
    assert "UNAVAILABLE" in capsys.readouterr().err


def test_the_script_runs_with_this_interpreter_from_the_checkout(tmp_path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "trial_budget.py").write_text("", encoding="utf-8")
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=7)

    assert passthrough.run_tool("budget", ["--budget", "5"], repo_root=tmp_path,
                                runner=runner) == 7
    command, kwargs = calls[0]
    assert command == [sys.executable, "-X", "utf8",
                       str(tmp_path / "tools" / "trial_budget.py"), "--budget", "5"]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["env"]["PYTHONPATH"] == str(tmp_path / "src")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_passthrough.py -q`
Expected: FAIL — `ImportError: cannot import name 'passthrough'`.

- [ ] **Step 3: Create `passthrough.py`**

```python
"""Operational scripts as `swingdesk` subcommands - the same script, run by the same interpreter.

`tools/` is not a package: `src/` cannot import it, and should not. A second copy of
`forward_record` inside the CLI is the one-logic-in-two-places defect this repository has paid for
more than once. So a subcommand here RUNS the script, from the checkout, with this interpreter and
`src/` on the path, and returns its exit code unchanged. Arguments pass through untouched, `--help`
included, which is why `cli.main` dispatches these BEFORE argparse sees them.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from swingdesk.presentation.paths import REPO_ROOT

#: subcommand -> script in `tools/`. The help text lives in ONE place, the literal `add_parser`
#: line in `cli.main` that `tools/build_commands.py` reads; `tests/test_passthrough.py` fails if
#: a name here has no such line.
TOOL_COMMANDS: dict[str, str] = {
    "record": "forward_record.py",
    "budget": "trial_budget.py",
    "streak": "track_a_streak.py",
    "preflight": "preflight.py",
    "gates": "check_gates.py",
    "schedule": "verify_schedule.py",
}


def run_tool(
    name: str,
    rest: Sequence[str],
    repo_root: Path | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> int:
    root = REPO_ROOT if repo_root is None else repo_root
    script = root / "tools" / TOOL_COMMANDS[name]
    if not script.is_file():
        print(f"{name} UNAVAILABLE  {script} is not here - tools ship with the checkout, not "
              f"with the package", file=sys.stderr)
        return 2
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    completed = runner([sys.executable, "-X", "utf8", str(script), *rest],
                       cwd=root, env=env, check=False)
    return int(completed.returncode)
```

- [ ] **Step 4: Wire it into `cli.main`**

1. Import: `from swingdesk.presentation.passthrough import TOOL_COMMANDS, run_tool`.
2. At the top of `main`, before the parser is built:

```python
    raw = sys.argv[1:] if argv is None else argv
    if raw and raw[0] in TOOL_COMMANDS:
        # BEFORE argparse on purpose: the script owns its arguments, `--help` included, and an
        # `argparse.REMAINDER` positional refuses a first argument that starts with `-`.
        return run_tool(raw[0], raw[1:])
```

3. Beside the other subparsers, six literal lines — never reached for parsing; they exist so
   `swingdesk --help` and README.md's generated reference list the commands:

```python
    # Operational scripts (`presentation/passthrough.py`), dispatched before argparse runs. Literal
    # calls, one each, because `tools/build_commands.py` reads the tree.
    sub.add_parser("record", help="the live paper record: switch, book, what was refused")
    sub.add_parser("budget", help="what the search has cost and what the next trial costs")
    sub.add_parser("streak", help="the a.run_completes streak, computed not hand-kept")
    sub.add_parser("preflight", help="is every declared dependency installed")
    sub.add_parser("gates", help="the whole gate suite - this is the contract")
    sub.add_parser("schedule", help="the scheduled tasks and how each last ended")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=$PWD/src PY -m pytest tests/test_passthrough.py tests/test_cli.py -q`
Expected: PASS.
Run: `PYTHONPATH=$PWD/src PY -m swingdesk.presentation.cli budget` — prints the trial budget.

- [ ] **Step 6: Regenerate, gate, commit**

```bash
PYTHONPATH=$PWD/src PY tools/build_commands.py && PYTHONPATH=$PWD/src PY tools/build_state.py && PYTHONPATH=$PWD/src PY tools/check_gates.py
```

```bash
git add -A && git commit -m "Operational scripts as swingdesk subcommands, run rather than copied"
```

---

### Task 8: prove it, record it, hand it over

**Files:**
- Modify: `TODO.md` §6b (the operations review entry), `README.md` (Quick start)
- Scratch: a mutation script in the session scratchpad

- [ ] **Step 1: Mutation check** — each mutant must be KILLED by the tests in the named file.
  The column names the file and the behaviour rather than the function: a plan written before
  its tests exist should not cite test names it cannot vouch for (gate 35), and the mutation
  script in the scratchpad records the exact names when it runs.

| file | mutation | killed by |
|---|---|---|
| `paths.py` | `if chosen:` → `if False:` | `tests/test_paths.py` — the environment wins |
| `paths.py` | `if here.is_dir():` → `if False:` | `tests/test_paths.py` — `./data` wins over the checkout |
| `schedule.py` | `if sys.platform != "win32":` → `if False:` | `tests/test_platform_schedule.py` — off Windows nothing is read |
| `reconcile.py` | `order.stop_price > current` → `order.stop_price < current` | `tests/test_operations_review.py` — the highest trigger is the one in force |
| `pending_view.py` | drop the `continue` after `out.superseded.append(item)` | `tests/test_pending_view.py` — older moves are superseded, the latest waits |
| `status.py` | `if self.venue_error is not None:` → `if False:` | `tests/test_status.py` — unavailable is not agreement |
| `status.py` | `NO_STOP if naked[...] else WRONG_PRICE` → swapped | `tests/test_status.py` — a stop an ATR away is the wrong price |
| `status.py` | `item.sequence > seen[0]` → `<` | `tests/test_status.py` — the newest proposal is shown |
| `passthrough.py` | `if not script.is_file():` → `if False:` | `tests/test_passthrough.py` — a missing script is unavailable |
| `cli.py` | `if raw and raw[0] in TOOL_COMMANDS:` → `if False:` | `tests/test_passthrough.py` — every tool command reaches its script |

Any survivor gets the test it was missing before this step is done.

- [ ] **Step 2: Record it** — in `TODO.md` §6b, under the review's "Still open", strike `status`
  and the CLI-defaults item and add a dated `BUILT` line naming `swingdesk status`, `$SWINGDESK_DATA`
  and the six subcommands. In `README.md` Quick start, add under "Reading the state of things":

```bash
swingdesk status                              # one screen: switch, schedule, account, every stop, queue
```

- [ ] **Step 3: Final gate, commit, push, PR**

```bash
PYTHONPATH=$PWD/src PY tools/build_commands.py && PYTHONPATH=$PWD/src PY tools/build_state.py && PYTHONPATH=$PWD/src PY tools/check_gates.py
```

```bash
git add -A && git commit -m "Operator console level 1: recorded, mutation-checked" && git push -u origin HEAD
```

Open the PR against `master`; merge only with `gates` = SUCCESS on the PR's own head SHA.

- [ ] **Step 4: Owner handover** — after `git pull --ff-only` on the main checkout, the owner's
  `swingdesk.cmd` shim is unnecessary: `.venv\Scripts\swingdesk.exe status` works from any folder.

---

## What this plan deliberately does not do

- **Split `cli.py`.** Worth doing, and a separate risk from adding features; it gets its own plan.
- **Colour, `rich`, or a TUI.** Level 2, decided after a week of using `status`.
- **Anything that writes to the venue.** Moving a venue stop on approval is the review's #2 and the owner's ruling.
- **Round book stops at write time or add `align-stops`.** The review's #1 and medium #3, next after this.
- **Move research runners or gates into the CLI.** Each is bound to a pre-registration or a gate.
