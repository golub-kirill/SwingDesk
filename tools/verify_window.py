"""Gate 46: a study reaching further back than forty-eight months says why.

`AGENTS.md` §19, owner instruction 2026-09-08:

> *"I want you to make a rule to not measure back more than 48 month from now if its no real reason
> to measure old market instead of current."*

**Why a gate and not a habit.** Every study on the branch that raised this used nine to eleven
years, and not one of them argued for it — the window was the store's extent, which is an inventory
rather than a reason. A default nobody chose is exactly what a gate is for; §19.2 has the measured
case, of which the sharpest is that the admitted universe grew **from 38 names to 3,999** across
the span those studies averaged over.

**What this checks, and what it deliberately does not.** It reads each reported study's own
`measured_span` — the window it OBTAINED, not the one its arguments asked for, because `PR-016`
asked for 10.67 years and got 8.91 — and requires a `window rationale:` line in the
pre-registration whenever that span exceeds forty-eight months. **It cannot check whether a reason
is a good one.** §19.4 lists what holds and what does not, and that is a reviewer's job; this gate
checks that a reason was given, dated, and attached to the study that spent the trials.

**Studies registered before the rule are exempt BY NAME.** Same shape gate 44 uses for the
pre-registrations that predate the minimum-effect rule, and for the same reason: an exemption
somebody listed is one a reader can argue with, and a silent one is a rule nobody applies.

    PYTHONPATH=$PWD/src python tools/verify_window.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "docs" / "prereg" / "results"
PREREGS = REPO / "docs" / "prereg"

#: The owner's number. Months, from the run's own `as_of` backwards.
MAX_MONTHS = 48
MAX_YEARS = MAX_MONTHS / 12

#: Registered before `AGENTS.md` §19 existed. Listed rather than skipped: each of these took a
#: window nobody argued for, and saying so by name is the point.
EXEMPT = {
    "PR-014": "registered 2026-09-06, before the rule. Its subject IS the holding period, so a "
              "long span was arguable - and it never argued it",
    "PR-015": "registered 2026-09-07, before the rule",
    "PR-016": "registered 2026-09-07, before the rule. Measured 8.91 years and reported the span "
              "beside the window it asked for, which is the habit this rule generalises",
    "PR-017": "registered 2026-09-08, hours before the rule. 9.39 years",
    "PR-018": "registered 2026-09-08, hours before the rule. Inherits PR-016's window by design, "
              "because its §9 reproduction check requires the same entries",
}

RATIONALE = re.compile(r"^\s*(?:\*\*)?window rationale(?:\*\*)?\s*[:\-]\s*(\S.*)$",
                       re.IGNORECASE | re.MULTILINE)


def prereg_for(study: str) -> Path | None:
    matches = sorted(PREREGS.glob(f"{study}-*.md"))
    return matches[0] if matches else None


def span_years(result: dict[str, object]) -> float | None:
    """The span the study OBTAINED. `None` when it does not report one.

    A study that does not declare its measured span is not failed here - `verify_studies` owns
    what a result must contain - but it cannot be checked either, and the report says so.
    """
    measured = result.get("measured_span")
    if isinstance(measured, dict) and isinstance(measured.get("years"), (int, float)):
        return float(measured["years"])
    return None


def main() -> int:
    failures: list[str] = []
    undeclared: list[str] = []
    exempt_seen: list[str] = []
    checked = 0

    for path in sorted(RESULTS.glob("PR-*.json")):
        study = path.stem.split("-as-")[0]
        study = "-".join(study.split("-")[:2])
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(result, dict) or "verdict" not in result:
            continue
        years = span_years(result)
        if years is None:
            undeclared.append(f"{path.name}: no measured_span, so the window cannot be checked")
            continue
        checked += 1
        if years <= MAX_YEARS:
            continue
        if study in EXEMPT:
            exempt_seen.append(f"{study} ({years:.2f}y) - {EXEMPT[study]}")
            continue
        prereg = prereg_for(study)
        if prereg is None:
            failures.append(f"{study}: {years:.2f} years measured and no pre-registration found")
            continue
        if not RATIONALE.search(prereg.read_text(encoding="utf-8")):
            failures.append(
                f"{study}: measured {years:.2f} years, more than the {MAX_MONTHS}-month default, "
                f"and {prereg.name} carries no `window rationale:` line. AGENTS.md §19.4 lists "
                f"what counts - 'more data' and 'the store goes back that far' do not"
            )

    if undeclared:
        # One class, not N problems: `measured_span` was added with `PR-016` on 2026-09-08, so
        # every study before it is unmeasurable here by construction. Printing ten identical lines
        # would make a known gap look like ten findings.
        print(f"  {len(undeclared)} study(ies) predate the `measured_span` field and cannot be "
              f"checked: {', '.join(sorted(x.split(':')[0].replace('.json', '') for x in undeclared))}")
        print("    Retrofitting it would mean re-running them; they are reported and closed.")
    if exempt_seen:
        print(f"  {len(exempt_seen)} study(ies) exempt, registered before AGENTS.md §19:")
        for line in exempt_seen:
            print(f"    {line}")
    for line in failures:
        print(f"  {line}")
    print(f"\nwindow: {checked} reported study(ies) checked against {MAX_MONTHS} months, "
          f"{len(exempt_seen)} exempt, {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
