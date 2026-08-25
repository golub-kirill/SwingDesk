"""Gate 28: a document may not state a parameter status the registry contradicts.

Gate 1 checks the registry against itself and against the code that reads it. Nothing checked the
**prose**, and prose is where this repository's most persistent failure lives: a cited fact moves
and the citation stays. Six live instances on 2026-08-24, every one the same shape - a parameter
was given a value by an owner ruling and a document still called it `unset`.

`UX_TASK_FLOWS.md` said the risk budget needs `risk.max_open_risk` "and friends, all `unset`" two
days after `DR-006` ratified four of them. `GO_LIVE_GATES.md` listed
`validation.max_allowable_drawdown` as `unset` sixteen days after `DR-007` gave it a value - and
that parameter is the one `RULE_SPEC.md` §7 calls this project's own inert gate, so the stale line
was the exact claim someone would have acted on.

**What it does NOT check, deliberately.** An `assumed` value read as `owner`, or any other pair,
fails the same way - but the common and dangerous direction is a document under-stating what the
registry holds, and the rule is symmetric only because asymmetry would need a reason.

**Three exclusions, and each is a rule rather than a convenience:**

* `docs/decisions/`, `docs/prereg/` and `docs/adr/` are **append-only** (`AGENTS.md` §11 rule 2).
  A decision record states what was true when it was accepted, and correcting it forward means
  superseding it, never editing it. A gate that demanded they track today's registry would be
  demanding the one thing those stores forbid.
* A line that reads as **history** - struck through, or carrying a ruling word - is a statement
  about a date and is left alone, the same convention `AGENTS.md` §10.5 uses for counts.
* A line that reads as a **transition or a negation** - "moves from `unset` to `owner`", "this does
  not make it `validated`" - mentions the status without claiming it.

A gate with false positives gets bypassed and teaches that red is normal (`CI_POLICY` §3), so the
match is narrow: a backticked parameter id, then a backticked status word within 80 characters on
the same line, with none of the above in the way.

    python tools/verify_parameter_claims.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

#: Root of the tree being checked. Overridable so a test can point the gate at a fixture and assert
#: it goes red - a gate nobody has seen fail is a gate nobody has tested.
REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: The registry's own vocabulary. `unset` is not a provenance - it is the absence of a value - and
#: it is the one this gate exists for.
STATUSES = ("unset", "assumed", "owner", "validated")

#: Append-only stores. See the module docstring: tracking today's registry is precisely what these
#: may not do.
APPEND_ONLY = ("docs/decisions/", "docs/prereg/", "docs/adr/")

#: `risk.max_open_risk` ... `unset`, on one line and close together. Widening the gap or crossing
#: lines buys hits that are mostly coincidence.
CLAIM = re.compile(
    r"`(?P<pid>[a-z_]+\.[a-z0-9_]+)`(?P<gap>[^`\n]{0,80}?)`(?P<status>" + "|".join(STATUSES) + r")`"
)

#: A line recording what was true on a date, or a decision being taken. Same convention as
#: `verify_counts.py`: history is not drift and rewriting it would falsify the record.
HISTORICAL = re.compile(r"~~|\b(DONE|CLOSED|REACHED|RULED|RATIFIED|CORRECTED|SUPERSEDED)\b")

#: A status named as one end of a move rather than as the current state.
TRANSITION = re.compile(
    r"\b(was|were|had been|until|since|stays?|remains?|used to|no longer|moves?|moved|went|"
    r"becomes?|became|from)\b|->|→"
)

#: A status named in order to deny it - "this does not make it `validated`".
NEGATION = re.compile(r"\b(not|never|nothing|cannot|isn't|doesn't)\b", re.IGNORECASE)

#: How far BEFORE the claim a negation still governs it. Scoped rather than applied to the whole
#: line, because a sentence can deny something else in the same breath: "`validation.execution_delay`
#: is `unset` and read by nothing. It is not unclaimed" is a live claim followed by two negations
#: that have nothing to do with it, and a line-wide rule swallowed it.
NEGATION_LOOKBEHIND = 40


def _registry_status() -> dict[str, str]:
    """Every parameter's current status: its provenance, or `unset` when it has no value."""
    import yaml

    raw = yaml.safe_load(
        (REPO / "registry" / "parameters.yml").read_text(encoding="utf-8")
    )["parameters"]
    entries = raw.items() if isinstance(raw, dict) else [(p["id"], p) for p in raw]
    status: dict[str, str] = {}
    for pid, entry in entries:
        provenance = entry.get("provenance")
        if entry.get("value") is None:
            status[pid] = "unset"
        elif isinstance(provenance, str):
            # `assumed:DR-012` is `assumed`; the citation after the colon is the evidence, not the
            # status, and a document quoting either form means the same thing.
            status[pid] = provenance.split(":")[0]
    return status


def _documents() -> list[Path]:
    paths = sorted(REPO.glob("docs/**/*.md")) + sorted(REPO.glob("*.md"))
    return [
        path for path in paths
        if not path.relative_to(REPO).as_posix().startswith(APPEND_ONLY)
    ]


def main() -> int:
    status = _registry_status()
    failures: list[str] = []
    scanned = checked = 0

    for path in _documents():
        scanned += 1
        relative = path.relative_to(REPO).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in CLAIM.finditer(line):
                pid, claimed = match.group("pid"), match.group("status")
                actual = status.get(pid)
                if actual is None:
                    continue  # not a parameter this registry knows; not this gate's business
                checked += 1
                if actual == claimed:
                    continue
                governing = line[max(0, match.start() - NEGATION_LOOKBEHIND):match.end()]
                if (HISTORICAL.search(line) or TRANSITION.search(match.group("gap"))
                        or NEGATION.search(governing)):
                    continue
                failures.append(
                    f"{relative}:{number}: says `{pid}` is `{claimed}`; the registry has "
                    f"`{actual}`"
                )

    for failure in failures:
        print(f"  {failure}")
    if failures:
        print(
            "\n  A parameter that gained a value and a document that still calls it `unset` is the "
            "\n  drift this gate exists for. Correct the sentence, or mark it as history the way "
            "\n  AGENTS.md 10.5 does - strike it through, or say when it was true."
        )
    print(f"\nparameter claims: {scanned} document(s), {checked} claim(s), {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
