"""Gate 44: a pre-registration says the smallest effect it could detect, before it spends a trial.

**Owner instruction, 2026-09-07.** The programme has spent 95 trials and validated nothing, and the
first study to state its own resolving power was `PR-015` - the ninety-first through ninety-fifth.
Everything before it was run without anyone asking whether it could see the thing it was looking
for, and the answer for several of them was no:

* `PR-012` measured a four-position book and **refused a verdict for want of sample** - after
  spending its trials.
* `PR-013`'s six **gross** intervals all include zero.
* `PR-014`'s long-only intervals ran about ±8 percentage points, so an edge of 3% a year - a good
  long-only strategy - was invisible to it. It reported `inconclusive` and the reader could not
  tell that apart from "there is nothing there".

**A null from an instrument that could not have seen the effect is not evidence of absence, and it
is not free.** `b.deflated_sharpe` counts every configuration evaluated, so each such study raises
the hurdle for every study after it and can never pay the hurdle back. That is the compounding
error this gate exists to stop: the deflated-Sharpe machinery counts shots meticulously and had no
way to ask whether a shot could hit.

**What it checks, and it is a token check.** Every pre-registration dated after 2026-09-07 carries a
line naming its minimum detectable effect. A gate cannot read whether the NUMBER is right - that is
prose against arithmetic - and it does not try. What it closes is the case where nobody wrote one
down, which is what actually happened ninety times.

**Studies dated on or before 2026-09-07 are exempt and are LISTED, never passed over in silence.**
Retro-fitting the line to a registered document would be either an edit in place, which `AGENTS.md`
§11 forbids, or a post-hoc amendment, which `PREREG_TEMPLATE` rule 3 downgrades to exploratory -
so the honest treatment of a document written before the rule is to name it as exempt and count it.
`PR-015` is the boundary: it prompted the rule and already satisfies its substance in §3 and §8,
under the name "power floor".

**`PREREG_TEMPLATE` rule 9 is the rule; §3's form carries the field.** The new rule was appended as
9 rather than inserted at 8 on purpose: four documents and two test files cite rule 8 as the
both-negative branch, and renumbering it would have made every one of them quietly wrong.

    python tools/verify_minimum_effect.py
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
PREREG = REPO / "docs" / "prereg"

#: The rule binds studies registered AFTER the day it was ruled. Not `>=`: `PR-015` is dated
#: 2026-09-07, is already reported, and states its resolving power under another name.
RULED_ON = date(2026, 9, 7)

#: The header field every pre-registration carries. A file without one is not dated and cannot be
#: judged either way, which is itself a failure.
DATE_LINE = re.compile(r"^date:\s*(\d{4})-(\d{2})-(\d{2})\s*$", re.MULTILINE)

#: What the rule requires. Accepted in either wording, because "power floor" is what `PR-015` called
#: it and renaming a thing does not make it a different obligation.
REQUIRED = re.compile(
    r"^\s*(?:\*\*)?(minimum detectable effect|power floor)(?:\*\*)?\s*[:\-]\s*(\S.*)$",
    re.MULTILINE | re.IGNORECASE,
)


def studies() -> list[Path]:
    return sorted(p for p in PREREG.glob("PR-*.md") if p.name != "README.md")


def main() -> int:
    failures: list[str] = []
    exempt: list[str] = []
    checked = 0

    for path in studies():
        text = path.read_text(encoding="utf-8")
        stamp = DATE_LINE.search(text)
        if stamp is None:
            failures.append(f"{path.name}: carries no `date:` line, so the rule cannot be applied "
                            f"to it either way")
            continue
        registered = date(int(stamp[1]), int(stamp[2]), int(stamp[3]))
        if registered <= RULED_ON:
            exempt.append(f"{path.name} ({registered})")
            continue
        checked += 1
        if REQUIRED.search(text) is None:
            failures.append(
                f"{path.name}: dated {registered} and states no minimum detectable effect. "
                f"Add a line `minimum detectable effect: <number, and where it came from>` to §3. "
                f"A study that cannot resolve the effect it is looking for cannot inform, and its "
                f"null costs the programme hurdle it can never repay."
            )

    if exempt:
        print(f"  {len(exempt)} pre-registration(s) predate the rule (ruled {RULED_ON}) and are "
              f"exempt:")
        for name in exempt:
            print(f"      {name}")
        print("  Exempt, not silent: retro-fitting the line would edit a registered document or "
              "amend it after the run.")

    for line in failures:
        print(f"  {line}")
    print(f"\nminimum effect: {checked} study(ies) bound by the rule, {len(exempt)} exempt, "
          f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
