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

**A gate that passes because the tree is silent is not a gate.** The first cut of this file failed
only on an affirmative verdict, and no study reports one - so two of its three conditions were
unreachable and it was green for the same reason gate 23 used to be: it could not see its subject.
The fix was not to soften or harden it but to make the tree declarable and then require the
declaration. All five studies now carry a `perturbations` block, read from their pre-registrations
and their runners' source, so condition 4 gates rather than reports.

That backfill immediately surfaced a SECOND undetected instance. `PR-001` registered "SMA periods
moved +/- 20% (parameter stability)" and `run_pr001.py` fixes `SMA_SHORT = 50` and `SMA_LONG = 200`
with no sensitivity loop; its report never mentions the check. Its `reject` therefore rests on one
parameterisation. Nothing had noticed in two weeks.

Four failures and one report:

  1. A reported study must state its SCOPE. `country` is the one every prereg here constrains
     (`AGENTS.md` 3: "USA and Canada are never merged"). A study whose scope is unstated cannot be
     checked against a rule that constrains scope, and PR-002 is what that costs. Caught `PR-010`,
     which stated none.

  2. `accept` is REFUSED where the record declares a scope shortfall - `single_market: true`, or a
     non-empty `scope_unmet`. This is exactly PR-002's shape and would have caught it on the day.

  3. `accept` is REFUSED where `run` does not cover `registered`. A robustness claim resting on a
     subset of the checks registered for it is not the claim the prereg authorised.

  4. A reported study must DECLARE `perturbations` - `registered` and `run`, both explicit. An empty
     `registered` is a legitimate declaration (`PR-008` and `PR-010` register none); an ABSENT block
     is not, because it is indistinguishable from nobody having looked. This is the condition that
     makes the gate bite on the present tree rather than on a hypothetical future study.

  5. REPORTED, not failed: registered perturbations left unrun under a NON-affirmative verdict.
     `PR-001` and `PR-002` are both in this state. It is not a failure - concluding LESS than you
     registered is always permitted, and failing here would push a study toward claiming more - but
     it is printed on every run, because a `reject` resting on one parameterisation is a weaker
     result than its report implies.

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
    unrun: list[tuple[str, str, list[str]]] = []
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

        # 3 and 4. Robustness checks: the declaration is mandatory, and an affirmative verdict may
        # not rest on a subset of what was registered.
        perturbations = record.get("perturbations")
        if not isinstance(perturbations, dict) or "registered" not in perturbations \
                or "run" not in perturbations:
            failures.append(
                f"{name}: declares no `perturbations` block with both `registered` and `run`. An "
                f"empty `registered` is a legitimate declaration; an absent one is indistinguishable "
                f"from nobody having looked."
            )
            continue

        registered = set(map(str, perturbations.get("registered") or []))
        ran = set(map(str, perturbations.get("run") or []))
        missing = sorted(registered - ran)
        if not missing:
            continue
        if affirmative:
            failures.append(
                f"{name}: verdict {verdict!r} with registered perturbation(s) not run "
                f"({', '.join(missing)}). A robustness claim may not rest on a subset of the "
                f"checks registered for it."
            )
        else:
            unrun.append((name, verdict, missing))

    for failure in failures:
        print(f"  {failure}")

    if unrun:
        # Reported, never failed - concluding LESS than you registered is always permitted, and
        # failing here would push a study toward claiming more. Printed because a verdict resting
        # on a subset of its registered checks is weaker than its report implies.
        print(f"\n  {len(unrun)} study(ies) left registered perturbation(s) unrun under a "
              f"non-affirmative verdict:")
        for name, verdict, missing in unrun:
            print(f"      {name:16} {verdict:14} unrun: {', '.join(missing)}")
        print("  Permitted - a study may always conclude less than it registered - but the verdict")
        print("  rests on fewer checks than the pre-registration asked for.")

    print(f"\nprereg conformance: {checked} study(ies) checked, {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
