"""Environment preflight for the scheduled daily run.

The defect this exists for, 2026-08-10: `yfinance` was imported by `market_data/vendor_yahoo.py`
and declared nowhere. `fetch()` imports it inside the function body - deliberately, so the package
imports and the gate suite runs with no network and no vendor installed - which meant a clean
install SUCCEEDED and the environment was only wrong at the first fetch. That fetch happens inside
the 18:30 scheduled run, and `a.run_completes` counts CONSECUTIVE trading days: a dependency fault
discovered there does not cost a minute, it costs a day of the Track A clock and resets the
counter.

So the check runs BEFORE the pipeline, and its exit code is 3 - the wrapper's code for "the
environment is wrong", distinct from 2, a coded refusal, which is a real outcome and not a failure
(FAIL_CLOSED_POLICY).

Declared dependencies are read from `pyproject.toml`, never listed here. A preflight carrying its
own copy of the dependency list is one more hand-maintained count to drift, and this repository has
lost five of those already (HANDOFF section 8).

**What this proves and what it does not.** It proves every declared distribution is present in this
interpreter's environment. It does not import them, so a distribution that is installed but broken
- a compiled extension against the wrong Python, a partial upgrade - still passes. That is the
weaker of the two checks and it is the one that cannot itself fail on an unrelated import error,
which is what a preflight needs to be.

Stdlib only, and imports nothing from `swingdesk`: it has to run correctly in exactly the broken
environment it exists to report on.

    python tools/preflight.py
"""

from __future__ import annotations

import os
import sys
import tomllib
from importlib import metadata
from pathlib import Path

#: Root of the tree being checked. Overridable so a test can point it at a fixture and assert it
#: goes red - a check nobody has seen fail is a check nobody has tested. Never set in normal use;
#: `tools/daily_run.cmd` does not set it.
REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
PYPROJECT = REPO / "pyproject.toml"

#: Exit code for "the environment is wrong". Matches `tools/daily_run.cmd`, where 0 is a completed
#: run, 2 is a coded refusal, and 3 is a crash or a bad environment.
ENVIRONMENT_FAULT = 3

#: Characters that end a distribution name in a PEP 508 requirement string.
_NAME_END = "<>=!~[ ;("


def requirement_name(requirement: str) -> str:
    """The distribution name from a PEP 508 requirement, e.g. `yfinance>=1` -> `yfinance`."""
    for index, character in enumerate(requirement):
        if character in _NAME_END:
            return requirement[:index].strip()
    return requirement.strip()


def declared_dependencies() -> list[str]:
    """Runtime dependency names from `pyproject.toml`. Extras are excluded on purpose.

    `dev` holds the gate tooling; the scheduled run does not need ruff or mypy, and demanding them
    would make the preflight fail on a correct production environment.
    """
    with PYPROJECT.open("rb") as handle:
        config = tomllib.load(handle)
    declared = config.get("project", {}).get("dependencies", [])
    return [requirement_name(item) for item in declared]


def missing(names: list[str]) -> list[str]:
    """Those not installed in the running interpreter's environment."""
    absent = []
    for name in names:
        try:
            metadata.distribution(name)
        except metadata.PackageNotFoundError:
            absent.append(name)
    return absent


def main() -> int:
    if not PYPROJECT.exists():
        print(f"preflight: no pyproject.toml at {PYPROJECT}", file=sys.stderr)
        return ENVIRONMENT_FAULT

    names = declared_dependencies()
    if not names:
        print("preflight: pyproject.toml declares no runtime dependencies", file=sys.stderr)
        return ENVIRONMENT_FAULT

    absent = missing(names)
    if absent:
        print(f"preflight: FAIL - {len(absent)} of {len(names)} declared dependencies missing",
              file=sys.stderr)
        for name in absent:
            print(f"  missing: {name}", file=sys.stderr)
        print(f"  interpreter: {sys.executable}", file=sys.stderr)
        print("  fix: pip install -e . (from the repository root)", file=sys.stderr)
        print("  the run was NOT attempted; today does not count toward a.run_completes",
              file=sys.stderr)
        return ENVIRONMENT_FAULT

    print(f"preflight: ok - {len(names)} declared dependencies present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
