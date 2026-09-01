"""Gate 39: the broker adapter is read-only, reaches one host, and holds no limits of its own.

Same instrument as gate 22 and the same argument, applied to a target where it matters more. Gate
22 governs what this project may ask of a free text-file server; this governs what it may do to a
BROKERAGE ACCOUNT.

**The check that has teeth is the third one, and it is here because of a measured fact.** Alpaca's
account object carries no field saying whether an account is paper or live - checked against its
own API reference on 2026-08-31, and its `id`, `status`, `currency`, `equity` and `trading_blocked`
are identical in both. **Which host was called is the only difference there is.** So the allowlist
in `registry/broker_policy.yml` is not configuration, it is the entire boundary that `DR-014` ("no
owner capital in the observable state of the project") rests on, and a URL written as a literal in
the adapter would route around it silently.

Four checks:

1. **The policy is complete and well-formed.** Every key the adapter needs, of the right type, with
   the caps positive. A policy missing a limit fails here rather than at the moment that limit
   would have bounded a request.
2. **The allowlist names exactly one https host, and the live venue is not it.** One entry means a
   reviewer can see which host is reachable; a second is the change this file exists to make
   visible. The live host must also be listed under `forbidden_hosts` - a host protected by an
   omission is protected by nobody noticing.
3. **`swingdesk/broker/` carries no URL and no HTTP write verb.** `D1`/`BR-1` forbid this system
   placing, amending or cancelling an order, and `DR-026` records where the owner put that boundary
   on 2026-08-31 and what stayed closed. Until a write path arrives with its own decision record,
   *there is no write verb in the package* - which is a fact a gate can check, unlike an intention.
4. **`access.write_enabled` is false while check 3 holds.** A policy claiming a capability the code
   does not have is the one-logic-in-two-places failure, pointed the other way.

Read from the syntax tree, so the gate never imports or runs the adapter and stays inside
`CI_POLICY.md` 4's no-network rule. It is a structural check and not a proof: a verb assembled at
runtime from fragments would pass it, which is why `policy.check_method` refuses at the call as
well. Two mechanisms, because either one alone is a promise.

    python tools/verify_broker_policy.py
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
POLICY = REPO / "registry" / "broker_policy.yml"
PACKAGE = REPO / "src" / "swingdesk" / "broker"

#: section -> {key: (type, must_be_positive)}.
REQUIRED: dict[str, dict[str, tuple[type, bool]]] = {
    "venue": {
        "name": (str, False),
        "label": (str, False),
        "user_agent": (str, False),
        # Which market the venue serves, so the reconciliation can tell "the venue does not hold
        # this" from "the venue cannot hold this". AGENTS 3: USA and Canada are never merged.
        "market": (str, False),
    },
    "access": {
        "write_enabled": (bool, False),
        "key_env": (str, False),
        "secret_env": (str, False),
    },
    "limits": {
        "max_response_bytes": (int, True),
        "request_timeout_seconds": (int, True),
        "max_retries_per_attempt": (int, False),
        "retry_after_seconds": (int, False),
        "page_size": (int, True),
        # A paged endpoint with no ceiling is DR-008's "unlimited retry inside one command" wearing
        # a different hat: the loop ends when the server stops issuing tokens, which is never.
        "max_pages": (int, True),
    },
    "endpoints": {
        "account": (str, False),
        "positions": (str, False),
        "activities": (str, False),
        "activity_type": (str, False),
    },
}

#: A URL with a HOST written into the package, however spelled. Gate 22 matches a bare scheme;
#: this requires a character after the slashes, because `policy.py` legitimately checks that the
#: allowlisted URL `startswith("https://")` and a scheme-only pattern reports that as a second
#: copy of the host. Caught on this gate's second run.
URL_LITERAL = re.compile(r"https?://\S")

#: HTTP verbs that change something at the venue. `GET` and `HEAD` are absent deliberately.
WRITE_VERBS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _docstrings(tree: ast.AST) -> set[int]:
    """Line numbers of docstring constants, which are prose and cannot issue a request.

    Skipped for the verb check only: this file's own subject has to be describable in the package's
    documentation, and `"no POST, no DELETE"` in a module docstring is the sentence a reader needs.
    """
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                lines.add(body[0].value.lineno)
    return lines


def _policy_failures() -> tuple[list[str], dict[str, object]]:
    import yaml

    if not POLICY.is_file():
        return ([f"{POLICY.relative_to(REPO).as_posix()} does not exist. The broker adapter has no "
                 f"committed limits, which means it has no paper/live boundary either."], {})
    try:
        loaded = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        return ([f"{POLICY.name}: will not parse - {error}"], {})
    if not isinstance(loaded, dict):
        return ([f"{POLICY.name}: must be a mapping"], {})

    failures: list[str] = []
    for section, keys in REQUIRED.items():
        block = loaded.get(section)
        if not isinstance(block, dict):
            failures.append(f"{POLICY.name}: missing or malformed `{section}` section")
            continue
        for key, (kind, positive) in keys.items():
            value = block.get(key)
            # `bool` is an `int` in Python and a boolean cap would be nonsense, so it is excluded
            # everywhere the expected type is not `bool` itself.
            if not isinstance(value, kind) or (kind is not bool and isinstance(value, bool)):
                failures.append(
                    f"{POLICY.name}: `{section}.{key}` is missing or not {kind.__name__}"
                )
            elif positive and cast(int, value) <= 0:
                failures.append(f"{POLICY.name}: `{section}.{key}` must be positive, is {value!r}")

    venue = loaded.get("venue")
    venue_block = venue if isinstance(venue, dict) else {}
    allowlist = venue_block.get("base_url_allowlist")
    forbidden = venue_block.get("forbidden_hosts")

    if not isinstance(allowlist, list) or len(allowlist) != 1:
        failures.append(
            f"{POLICY.name}: `venue.base_url_allowlist` must carry EXACTLY ONE https host. "
            f"Alpaca's account object names no paper/live flag, so the host is the whole boundary "
            f"and widening it is a decision record, not an edit."
        )
    else:
        host = str(allowlist[0])
        if not host.startswith("https://"):
            failures.append(f"{POLICY.name}: `venue.base_url_allowlist[0]` {host!r} is not https")
        if not isinstance(forbidden, list) or not forbidden:
            failures.append(
                f"{POLICY.name}: `venue.forbidden_hosts` is missing. The live venue named there is "
                f"protected by a check; one merely absent from the allowlist is protected by "
                f"nobody noticing."
            )
        else:
            # Compared as HOSTNAMES and not as substrings, and the first run of this gate is why.
            # `paper-api.alpaca.markets` CONTAINS `api.alpaca.markets`, so a substring test called
            # the paper host forbidden. The same test fails the other way round too: it would pass
            # `paper-api.alpaca.markets.example.com`, which is a different server entirely.
            reachable = (urlparse(host).hostname or "").lower()
            for entry in forbidden:
                if reachable and reachable == str(entry).strip().lower():
                    failures.append(
                        f"{POLICY.name}: the allowlisted host resolves to {reachable}, which is "
                        f"listed under `forbidden_hosts`. DR-014 rules no owner capital is in "
                        f"scope."
                    )

    access = loaded.get("access")
    access_block = access if isinstance(access, dict) else {}
    methods = access_block.get("allowed_methods")
    if not isinstance(methods, list) or not methods:
        failures.append(f"{POLICY.name}: `access.allowed_methods` is missing or empty")
    else:
        writes = sorted({str(m).upper() for m in methods} & WRITE_VERBS)
        if writes and not access_block.get("write_enabled"):
            failures.append(
                f"{POLICY.name}: `access.allowed_methods` permits {', '.join(writes)} while "
                f"`write_enabled` is false. A read-only policy that lists a write verb is not one."
            )
        if writes and access_block.get("write_enabled"):
            failures.append(
                f"{POLICY.name}: `access.write_enabled` is true. Placing, amending or cancelling "
                f"an order is D1/BR-1; DR-026 records what a write path needs before one exists, "
                f"and nothing in swingdesk/broker/ can write today."
            )

    return failures, venue_block


def _package_failures() -> list[str]:
    """URLs and write verbs written into the package that the policy is supposed to own."""
    if not PACKAGE.is_dir():
        return [f"{PACKAGE.relative_to(REPO).as_posix()} does not exist"]

    failures: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as error:
            failures.append(f"{path.name}: will not parse - {error}")
            continue

        prose = _docstrings(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if URL_LITERAL.search(node.value):
                failures.append(
                    f"{path.name}:{node.lineno}: carries the URL {node.value!r} as a literal. "
                    f"The host lives in {POLICY.name} because it is the only thing separating a "
                    f"paper account from the owner's money."
                )
            if node.lineno in prose:
                continue
            if node.value.strip().upper() in WRITE_VERBS:
                failures.append(
                    f"{path.name}:{node.lineno}: carries the HTTP write verb {node.value!r}. "
                    f"D1/BR-1: this system prepares and records, it never acts. A write path "
                    f"arrives with a decision record or it does not arrive."
                )
    return failures


def main() -> int:
    failures, _ = _policy_failures()
    # Only meaningful once the policy itself is sound - otherwise the package is blamed for a limit
    # that was never defined.
    if not failures:
        failures += _package_failures()

    for failure in failures:
        print(f"  {failure}")
    checked = sum(len(keys) for keys in REQUIRED.values())
    print(f"\nbroker policy: {checked} key(s) required, "
          f"{len(list(PACKAGE.rglob('*.py'))) if PACKAGE.is_dir() else 0} module(s) read for URLs "
          f"and write verbs, {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
