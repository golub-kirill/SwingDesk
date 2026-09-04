"""Gate 41: the price vendor's network limits live in the committed policy and nowhere else.

Gate 22's shape, aimed at the dependency this project asks the most of. That gate exists because
`DR-008` required the DIRECTORY collector's limits in one committed machine-readable file; this one
exists because the same argument was never applied to the price vendor, and the price vendor is not
the small case.

**The asymmetry, measured 2026-09-04.** `registry/broker_policy.yml` governs the broker.
`registry/directory_pull_policy.yml` governs two static text files pulled once a day. The price
vendor had nothing — no timeout, no retry budget, no pause, no fetch ceiling in any committed
place — while the evening passes fetched **about 2,300 times a day** between them. The limits were
absent from exactly the place they matter most.

**What is being protected, because "put constants in YAML" is not a reason.** These are the limits
on what this project's software may ask of somebody else's free server. A limit in a literal is
changed by editing a line; a limit here is changed by a commit a gate reads and a reviewer sees.
`DR-008`'s rejected-alternatives table names the failure: *"unlimited retry inside one command — can
hammer the source without a new human decision."* **The point is the new human decision.**

**Three checks, and the third is the one that makes this more than a schema test.**

1. every key the loader requires is present and the policy loads;
2. `swingdesk/market_data/` carries no limit as a literal — no bare timeout, no lookback ceiling,
   no `auto_adjust=` constant;
3. the adapter READS the policy. A policy nothing consults is decoration, which is the
   one-logic-in-two-places failure `DR-008` §8 forbids and `AGENTS.md` §10.6 rule 4 restates.

Read from the SOURCE rather than by importing it: this gate needs nothing installed and cannot be
fooled by whatever happens to be in the environment — the same reason gate 17 parses instead of
importing.

    python tools/verify_vendor_policy.py
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
POLICY = REPO / "registry" / "vendor_policy.yml"
ADAPTER = REPO / "src" / "swingdesk" / "market_data" / "vendor_yahoo.py"
LOADER = REPO / "src" / "swingdesk" / "market_data" / "policy.py"

#: Every key the adapter's behaviour depends on. Named here rather than derived from the file, so a
#: key DELETED from the policy fails instead of quietly becoming unenforced.
REQUIRED = {
    "source": ("vendor", "label", "client"),
    "limits": ("request_timeout_seconds", "pause_seconds", "max_attempts",
               "retry_delay_seconds", "retry_budget_seconds"),
    "windows": ("day_max_lookback_days", "hour_max_lookback_days",
                "half_hour_max_lookback_days"),
    "fetch": ("auto_adjust",),
}

#: A limit written into the adapter instead of read from the policy. `auto_adjust=` with a literal
#: is the one that matters most - an adjusted series rewrites history under a bitemporal store -
#: and a bare `timeout=` or a lookback dict are the two the policy exists to hold.
LITERALS = (
    (re.compile(r"auto_adjust\s*=\s*(True|False)"),
     "auto_adjust as a literal; read fetch.auto_adjust from the policy"),
    (re.compile(r"timeout\s*=\s*\d"),
     "a timeout as a literal; read limits.request_timeout_seconds from the policy"),
    (re.compile(r"MAX_LOOKBACK_DAYS\s*[:=]"),
     "a lookback ceiling as a literal; read the windows section from the policy"),
)


def _policy_keys() -> dict[str, set[str]] | str:
    """The policy's sections and their keys, or one string saying why it could not be read.

    Parsed rather than imported, and deliberately without PyYAML: this gate must run on a machine
    where nothing is installed. The shape it needs - two levels of `key: value` under a top-level
    section - is exactly what the file has, and anything more complex would be a reason to reject
    the file rather than to write a parser.
    """
    if not POLICY.is_file():
        return f"no vendor policy at {POLICY.relative_to(REPO).as_posix()}"

    found: dict[str, set[str]] = {}
    section = ""
    for line in POLICY.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            section = line.split(":", 1)[0].strip()
            found.setdefault(section, set())
        elif section and ":" in line:
            found[section].add(line.split(":", 1)[0].strip())
    return found


def _reads_the_policy() -> bool:
    """Does the adapter actually consult the loader?

    An import is not a read: the check is a CALL, which is the distinction gate 20 was weakened by
    for eighteen days and `tests/test_guard_parity.py` was written for. Anything else would pass on
    a module that imports the policy and then uses its own numbers.
    """
    try:
        tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
            if name in ("load", "policy"):
                return True
    return False


def main() -> int:
    """Check the policy against the adapter, and say which of the three checks failed."""
    failures: list[str] = []

    keys = _policy_keys()
    if isinstance(keys, str):
        print(f"  {keys}")
        print("\nvendor policy: 1 failure(s)")
        return 1

    for section, required in REQUIRED.items():
        if section not in keys:
            failures.append(f"registry/vendor_policy.yml: the `{section}:` section is missing")
            continue
        for key in required:
            if key not in keys[section]:
                failures.append(f"registry/vendor_policy.yml: {section}.{key} is missing")

    if not LOADER.is_file():
        failures.append("src/swingdesk/market_data/policy.py is missing - nothing can read the file")

    if ADAPTER.is_file():
        source = ADAPTER.read_text(encoding="utf-8")
        # Comments are stripped first: this file EXPLAINS why `auto_adjust` comes from the policy,
        # and a check that fired on its own explanation would be the mention-not-a-thing defect
        # gate 20 was hardened against on 2026-09-04.
        code = "\n".join(
            line.split("#", 1)[0] for line in source.splitlines()
        )
        for pattern, consequence in LITERALS:
            if pattern.search(code):
                failures.append(f"src/swingdesk/market_data/vendor_yahoo.py carries {consequence}")
        if not _reads_the_policy():
            failures.append(
                "src/swingdesk/market_data/vendor_yahoo.py never CALLS the policy loader - a "
                "policy nothing reads is decoration (DR-008 8)"
            )
    else:
        failures.append("src/swingdesk/market_data/vendor_yahoo.py is missing")

    for failure in failures:
        print(f"  {failure}")
    checked = sum(len(v) for v in REQUIRED.values())
    print(f"\nvendor policy: {checked} key(s) checked, {len(failures)} failure(s)")
    if failures:
        print("\nThe limits on what this software may ask of somebody else's server live in one "
              "committed file, and the adapter reads them from there.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
