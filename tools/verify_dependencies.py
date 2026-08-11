"""Gate 17: every third-party module `src/` imports is a declared dependency.

The defect this exists for, 2026-08-10: `yfinance` was imported by
`market_data/vendor_yahoo.py` and declared in no dependency list. It survived 22 green gates, 302
tests and a published commit, because nothing compared what the code imports against what the
package says it needs.

**Why a plain import smoke test would not have caught it.** `vendor_yahoo.fetch` imports yfinance
inside the function body, deliberately, so the package imports and the gate suite runs with no
network and no vendor installed. Importing every module under `swingdesk` therefore succeeds with
yfinance absent. Only reading the source finds it, so this gate parses rather than imports - which
also means it needs nothing installed and cannot be fooled by whatever happens to be in the
developer's environment.

Nesting is the whole point: imports are collected at any depth - module level, inside a function,
inside a class, inside a `try`. A module-level-only scan reproduces the blind spot.

`TYPE_CHECKING` blocks are excluded. Those imports never execute, so a missing distribution behind
one cannot break a run, and requiring them would push type-only packages into runtime dependencies.

Stdlib only.

    python tools/verify_dependencies.py
"""

from __future__ import annotations

import ast
import os
import sys
import tomllib
from collections import defaultdict
from importlib import metadata
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
SRC = REPO / "src"
PYPROJECT = REPO / "pyproject.toml"

#: First-party. Not a dependency of itself.
FIRST_PARTY = {"swingdesk"}

_NAME_END = "<>=!~[ ;("


def requirement_name(requirement: str) -> str:
    for index, character in enumerate(requirement):
        if character in _NAME_END:
            return requirement[:index].strip()
    return requirement.strip()


def declared() -> set[str]:
    """Runtime dependency names from `pyproject.toml`, normalised the way packaging compares them."""
    with PYPROJECT.open("rb") as handle:
        config = tomllib.load(handle)
    names = config.get("project", {}).get("dependencies", [])
    return {requirement_name(item).lower().replace("_", "-") for item in names}


def _is_type_checking(node: ast.If) -> bool:
    """`if TYPE_CHECKING:` / `if typing.TYPE_CHECKING:`."""
    test = node.test
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def imported_modules(tree: ast.AST) -> list[tuple[str, int]]:
    """(top-level module, line) for every import at any nesting depth, minus TYPE_CHECKING blocks."""
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _is_type_checking(node):
            for inner in ast.walk(node):
                skip.add(id(inner))

    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Import):
            found.extend((alias.name.split(".")[0], node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # `level` > 0 is a relative import: first-party by construction.
            if node.level == 0 and node.module:
                found.append((node.module.split(".")[0], node.lineno))
    return found


def provided_by(names: set[str]) -> set[str]:
    """Top-level module names supplied by the given distributions, as installed.

    Needed because a distribution's name and its import name routinely differ - `pyyaml` provides
    `yaml`, `pandas-market-calendars` provides `pandas_market_calendars`. Falls back to the
    distribution name itself when the mapping is unavailable, which keeps the gate usable on a
    machine where a declared dependency is not installed.
    """
    modules: set[str] = set(names)
    mapping: dict[str, list[str]] = defaultdict(list)
    for module, dists in metadata.packages_distributions().items():
        for dist in dists:
            mapping[dist.lower().replace("_", "-")].append(module)
    for name in names:
        modules.update(mapping.get(name, []))
    return {module.lower().replace("-", "_") for module in modules}


def main() -> int:
    if not SRC.is_dir():
        print(f"no src/ under {REPO}", file=sys.stderr)
        return 1

    names = declared()
    available = provided_by(names)
    stdlib = sys.stdlib_module_names

    failures: list[str] = []
    scanned = 0
    for path in sorted(SRC.rglob("*.py")):
        scanned += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module, line in imported_modules(tree):
            key = module.lower().replace("-", "_")
            if module in stdlib or key in FIRST_PARTY or key in available:
                continue
            failures.append(
                f"{path.relative_to(REPO)}:{line}: imports {module!r}, which no declared "
                f"dependency provides"
            )

    for failure in sorted(set(failures)):
        print(f"  {failure}")
    print(f"\ndependencies: {len(names)} declared, {scanned} modules scanned, "
          f"{len(set(failures))} undeclared import(s)")
    if failures:
        print("\nAdd it to [project.dependencies] in pyproject.toml, or stop importing it. An "
              "import the package does not declare works on the developer's machine and nowhere "
              "else.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
