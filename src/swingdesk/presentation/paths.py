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
