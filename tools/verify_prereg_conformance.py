"""Gate 25: a reported verdict conforms to the pre-registration it claims.

Gates 3f and 13 check that DOCUMENTS agree with the result files. Nothing checked that a RESULT
agrees with its own pre-registration - that the verdict came out of the branches the prereg
registered, over the scope it required, with the robustness checks it listed.

WHAT PAID FOR THIS, 2026-08-16. `PR-002` §6 permits `accept` only where the effect holds "in BOTH
countries independently", and its third amendment - written before any data was seen - assigned a
single-market result to the inconclusive branch. `tools/run_pr002.py` implemented §6's percentile
thresholds and nothing else. It recorded `single_market: true` beside the verdict, where no reader
and no gate treated it as part of the verdict, and emitted `accept` on a US-only sample. That
verdict was the sole support for the project's only `validated` parameter. Every gate stayed green
for two weeks.

It also ran ONE of §5's three registered perturbations. Nothing noticed that either.

**This gate does not parse prose.** A prereg is Markdown written for a human, and a gate that
guesses at English produces false positives, gets bypassed, and teaches that red is normal
(`CI_POLICY` 3). So the obligation is inverted: a result must DECLARE the things a prereg
constrains, and the gate checks the declaration against the verdict. What a study will not say about
itself cannot be checked, and this gate says so out loud rather than passing quietly.

Three failures and one report:

  1. A reported study must state its SCOPE. `country` is the one every prereg here constrains
     (`AGENTS.md` 3: "USA and Canada are never merged"). A study whose scope is unstated cannot be
     checked against a rule that constrains scope, and PR-002 is what that costs.

  2. `accept` is REFUSED where the record declares a scope shortfall - `single_market: true`, or a
     non-empty `scope_unmet`. This is exactly PR-002's shape and would have caught it on the day.

  3. `accept` is REFUSED where `perturbations` is declared and `run` does not cover `registered`.
     A robustness claim resting on a subset of the checks that were registered for it is not the
     claim the prereg authorised.

  4. REPORTED, not failed: a study carrying no `perturbations` block at all. Every current study is
     in this state, so failing would make the gate red on arrival and immediately bypassed. Printing
     it on every run is what keeps the gap from being forgotten - the same reason gate 16 prints its
     census when green.

Stdlib only, so it runs wherever gates 2 and 3 do.

    python tools/verify_prereg_conformance.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
RESULTS = REPO / "docs" / "prereg" / "results"

#: Verdicts that assert the hypothesis survived. Only these carry an obligation to have met the
#: prereg's conditions - `reject` and `inconclusive` claim less than the study registered, and a
#: study is always free to conclude less than it hoped.
AFFIRMATIVE = frozenset({"accept"})

#: Fields whose truthiness declares the run fell short of the registered scope. `single_market` is
#: PR-002's own field, kept as the name it already had rather than renamed underneath the record it
#: describes.
SHORTFALL_FLAGS = ("single_market",)


def _results() -> list[tuple[Path, dict]]:
    """Result files that are studies. A file without a `prereg` id and a `verdict` is a supporting
    analysis - `PR-002-survivorship-bound.json` is one - and carries no verdict to check."""
    studies = []
    for path in sorted(RESULTS.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            studies.append((path, {"__unreadable__": str(error)}))
            continue
        if isinstance(record, dict) and record.get("prereg") and record.get("verdict"):
            studies.append((path, record))
    return studies


def _shortfalls(record: dict) -> list[str]:
    found = [flag for flag in SHORTFALL_FLAGS if record.get(flag)]
    unmet = record.get("scope_unmet")
    if isinstance(unmet, list) and unmet:
        found.extend(str(item) for item in unmet)
    return found


def main() -> int:
    failures: list[str] = []
    undeclared: list[str] = []
    checked = 0

    for path, record in _results():
        name = path.name
        if "__unreadable__" in record:
            failures.append(f"{name}: not valid JSON - {record['__unreadable__']}")
            continue

        checked += 1
        verdict = str(record["verdict"]).lower()
        affirmative = verdict in AFFIRMATIVE

        # 1. Scope must be stated, whatever the verdict.
        if not record.get("country"):
            failures.append(
                f"{name}: states no `country`. Scope is what every prereg here constrains, and a "
                f"verdict over an unstated scope cannot be checked against it."
            )

        # 2. An affirmative verdict over a declared shortfall.
        shortfalls = _shortfalls(record)
        if affirmative and shortfalls:
            failures.append(
                f"{name}: verdict {verdict!r} while the record declares a scope shortfall "
                f"({', '.join(shortfalls)}). The prereg's affirmative branch requires the scope it "
                f"registered; a shortfall belongs in the inconclusive branch."
            )

        # 3. An affirmative verdict on a subset of the registered robustness checks.
        perturbations = record.get("perturbations")
        if isinstance(perturbations, dict):
            registered = set(map(str, perturbations.get("registered") or []))
            ran = set(map(str, perturbations.get("run") or []))
            missing = sorted(registered - ran)
            if affirmative and missing:
                failures.append(
                    f"{name}: verdict {verdict!r} with registered perturbation(s) not run "
                    f"({', '.join(missing)}). A robustness claim may not rest on a subset of the "
                    f"checks registered for it."
                )
        else:
            undeclared.append(name)

    for failure in failures:
        print(f"  {failure}")

    if undeclared:
        # Reported, never failed - see the module docstring. The point is that it stays visible.
        print(f"\n  {len(undeclared)} study(ies) declare no `perturbations` block, so condition 3 "
              f"cannot be checked for them:")
        for name in undeclared:
            print(f"      {name}")
        print("  A study that does not say which registered checks it ran cannot be held to them.")

    print(f"\nprereg conformance: {checked} study(ies) checked, {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
