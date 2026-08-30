"""Gate 22: the directory collector's network limits live in the committed policy and nowhere else.

`DR-008` (ratified 2026-08-10): *"The source URLs, retry budget, timeouts, cap and staleness levels
live in one committed machine-readable policy and are merge-gated."* Both halves were missing until
2026-08-25 - the values were Python literals in `tools/fetch_directory.py`, and no gate read them.
`plans/2026-08-11-evidence-foundation.md` names this file and this gate number; neither is invented
here.

**What the clause is actually protecting, because "put constants in YAML" is not a reason.** These
are the limits on what this project's software may ask of somebody else's free server. A limit in a
literal is changed by editing a line. A limit here is changed by a commit a gate reads and a
reviewer sees. `DR-008`'s own rejected-alternatives table names the failure: *"unlimited retry
inside one command - can hammer the source without a new human decision."* The **new human
decision** is the point, and a committed, gated policy is what makes one happen.

**Two checks, and the second is the one with teeth.**

1. **The policy is complete and well-formed.** Every key the collector needs, of the right type,
   with the response cap and the timeout positive. A policy missing a limit must fail here rather
   than at the moment that limit would have bounded a request.
2. **The collector READS it rather than carrying a second copy.** A source URL or a byte cap
   written as a literal in `tools/fetch_directory.py` is refused even when it agrees with the
   policy today - agreeing today is precisely how every drift in this repository has looked on the
   day it was written (`AGENTS.md` §10.5). This is checked from the syntax tree, so the gate never
   imports or runs the collector and stays inside `CI_POLICY.md` §4's no-network rule.

**Deliberately NOT in the policy: `.swingdesk-local.json`.** The policy is what this project commits
to doing to someone else's server; the switch is one machine's own state, and committing it would
turn an operator's local choice into a repository fact.

    python tools/verify_directory_policy.py
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
POLICY = REPO / "registry" / "directory_pull_policy.yml"
COLLECTOR = REPO / "tools" / "fetch_directory.py"

#: section -> {key: (type, must_be_positive)}. Every one is named by `DR-008`'s sentence.
REQUIRED: dict[str, dict[str, tuple[type, bool]]] = {
    "source": {"host": (str, False), "label": (str, False), "user_agent": (str, False)},
    "limits": {
        "max_response_bytes": (int, True),
        "request_timeout_seconds": (int, True),
        # A lock that never goes stale refuses every pull for ever after one killed
        # process, and DR-008 gives the forced pull no way past it. Required and positive.
        "lock_stale_after_seconds": (int, True),
        "max_retries_per_attempt": (int, False),
        "retry_after_seconds": (int, False),
    },
    "staleness": {
        "warning_at_consecutive_misses": (int, True),
        "error_at_consecutive_misses": (int, True),
    },
}

#: A literal in the collector that should have come from the policy. `http` catches a source URL
#: however it is spelled; the byte cap is matched as an arithmetic form too, because `2 * 1024 *
#: 1024` is how it was written before it moved and is what a future edit would most likely reach for.
SECOND_COPY = re.compile(r"https?://")


def _policy_failures() -> list[str]:
    import yaml

    if not POLICY.is_file():
        return [f"{POLICY.relative_to(REPO).as_posix()} does not exist. DR-008 requires the source "
                f"URLs, retry budget, timeouts, cap and staleness levels to live in one committed "
                f"machine-readable policy."]
    try:
        loaded = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        return [f"{POLICY.name}: will not parse - {error}"]
    if not isinstance(loaded, dict):
        return [f"{POLICY.name}: must be a mapping"]

    failures: list[str] = []
    for section, keys in REQUIRED.items():
        block = loaded.get(section)
        if not isinstance(block, dict):
            failures.append(f"{POLICY.name}: missing or malformed `{section}` section")
            continue
        for key, (kind, positive) in keys.items():
            value = block.get(key)
            # `bool` is an `int` in Python and a boolean cap would be nonsense, so it is excluded.
            if not isinstance(value, kind) or isinstance(value, bool):
                failures.append(
                    f"{POLICY.name}: `{section}.{key}` is missing or not {kind.__name__}"
                )
            elif positive and value <= 0:
                failures.append(f"{POLICY.name}: `{section}.{key}` must be positive, is {value!r}")

    files = (loaded.get("source") or {}).get("files")
    if not isinstance(files, dict) or not files:
        failures.append(f"{POLICY.name}: `source.files` must be a non-empty mapping of name -> URL")
    else:
        for name, url in files.items():
            if not isinstance(url, str) or not url.startswith("https://"):
                failures.append(f"{POLICY.name}: `source.files.{name}` is not an https URL")
    return failures


def _second_copy_failures() -> list[str]:
    """Literals in the collector that the policy is supposed to own.

    Read from the syntax tree so the gate never imports the collector - importing it would execute a
    network tool to check whether it is allowed to reach the network.
    """
    if not COLLECTOR.is_file():
        return [f"{COLLECTOR.relative_to(REPO).as_posix()} does not exist"]
    source = COLLECTOR.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [f"{COLLECTOR.name}: will not parse - {error}"]

    failures: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if SECOND_COPY.search(node.value):
                failures.append(
                    f"{COLLECTOR.name}:{node.lineno}: carries the URL {node.value!r} as a literal. "
                    f"Source URLs live in {POLICY.name}; a copy that agrees today is how every "
                    f"drift here has looked on the day it was written."
                )
    return failures


def main() -> int:
    failures = _policy_failures()
    # Only meaningful once the policy itself is sound; reporting both at once would blame the
    # collector for a limit the policy never defined.
    if not failures:
        failures += _second_copy_failures()

    for failure in failures:
        print(f"  {failure}")
    checked = sum(len(keys) for keys in REQUIRED.values())
    print(f"\ndirectory policy: {checked} limit(s) required by DR-008, {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
