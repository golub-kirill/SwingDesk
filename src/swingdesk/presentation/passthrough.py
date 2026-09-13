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
#: line in `cli.main` that `tools/build_commands.py` reads; `tests/test_passthrough.py` fails if a
#: name here has no such line.
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
