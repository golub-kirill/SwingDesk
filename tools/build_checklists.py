"""Generate registry/checklists.yml by parsing the verbatim blocks in CHECKLIST_SPEC.md.

The item text is never hand-copied. It comes from the document, which gate 2 checks against freshly
extracted PDF text — so the chain is:

    Appendix PDF  ->  CHECKLIST_SPEC.md  (gate 2)  ->  registry/checklists.yml  (this gate)

A third transcription by hand would be a third place to drift. What IS authored here is the
classification — machine or human, and for a machine item, which piece of run evidence answers it —
and that is carried forward across regenerations like every other authored field.

Usage:
    python tools/build_checklists.py [--check-only]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = REPO / "docs" / "04-journal" / "CHECKLIST_SPEC.md"
OUT = REPO / "registry" / "checklists.yml"

FENCE = re.compile(r"^```verbatim[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)

#: Which fenced block belongs to which appendix, in document order, with its expected item count.
#: The counts are the spec's own (E 18 · H 13 · P 19 · T 34) and a mismatch fails rather than
#: silently reshaping the checklist.
BLOCKS = [("E", 18), ("H", 13), ("P", 19), ("T", 34)]

#: Authored: how each pre-trade item is answered. `evidence` names the run fact that decides it;
#: `null` means only a human can answer.
#:
#: CHECKLIST_SPEC §1 says twelve of E's eighteen are machine-checkable "given the data the system
#: already holds". The system does not hold all of it yet, so several are marked machine and will
#: report UNAVAILABLE until their evidence exists. That is deliberate: an item whose evidence is
#: missing must say so, not quietly become a human question.
EVIDENCE = {
    "E01": "instrument_identity",
    "E02": "universe_membership",
    "E03": "data_freshness",
    "E04": "regime_recorded",
    "E05": "sector_benchmark",
    "E06": None,
    "E07": None,
    "E08": "trigger_not_late",
    "E09": "entry_zone_recorded",
    "E10": None,
    "E11": "event_proximity",
    "E12": "liquidity_acceptable",
    "E13": "risk_recomputed",
    "E14": "exposure_within_limits",
    "E15": None,
    "E16": "time_stop_recorded",
    "E17": "no_skip_condition",
    "E18": None,
}

HEADER = """# Checklist registry.
#
# GENERATED item text, parsed from docs/04-journal/CHECKLIST_SPEC.md, which gate 2 checks against
# the appendix PDFs. Never hand-copied - a third transcription is a third place to drift.
#
# AUTHORED: `evidence`. It names the run fact that answers a machine item; null means only a human
# can answer it. Carried forward across regenerations.
#
# Terminal states are the worksheet set (DECISION_STATE_MACHINE 5):
#   Complete - Research - Pause - Skip - Error
#
# Enforced by tools/build_checklists.py --check-only.

"""


def parse() -> list[dict]:
    text = SPEC.read_text(encoding="utf-8")
    blocks = FENCE.findall(text)
    if len(blocks) < len(BLOCKS):
        raise SystemExit(
            f"expected at least {len(BLOCKS)} verbatim blocks in CHECKLIST_SPEC.md, found "
            f"{len(blocks)}"
        )

    items: list[dict] = []
    for index, (appendix, expected) in enumerate(BLOCKS):
        lines = [line.strip() for line in blocks[index].splitlines() if line.strip()]
        if len(lines) != expected:
            raise SystemExit(
                f"Appendix {appendix}: expected {expected} items, parsed {len(lines)}. The spec "
                f"and this script disagree; fix whichever is wrong rather than adjusting the count."
            )
        for number, line in enumerate(lines, start=1):
            item_id = f"{appendix}{number:02d}"
            items.append({
                "id": item_id,
                "appendix": appendix,
                "position": number,
                "text": line,
                "evidence": EVIDENCE.get(item_id),
            })
    return items


def render(items: list[dict]) -> str:
    out = [HEADER, "items:\n"]
    for item in items:
        out.append(f"\n  - id: {item['id']}\n")
        out.append(f"    appendix: {item['appendix']}\n")
        out.append(f"    position: {item['position']}\n")
        out.append(f"    text: {_quote(item['text'])}\n")
        out.append(f"    evidence: {item['evidence'] or 'null'}\n")
    return "".join(out)


def _quote(text: str) -> str:
    escaped = text.replace('"', '\\"')
    return f'"{escaped}"'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    items = parse()
    rendered = render(items)

    machine = sum(1 for i in items if i["evidence"])
    pre_trade = [i for i in items if i["appendix"] == "E"]
    print(f"checklists: {len(items)} items "
          f"(E {len(pre_trade)} · H 13 · P 19 · T 34), {machine} with evidence keys")

    if args.check_only:
        if not OUT.exists():
            print(f"{OUT} does not exist; run without --check-only", file=sys.stderr)
            return 1
        if OUT.read_text(encoding="utf-8") != rendered:
            print("checklists.yml is stale. Run: python tools/build_checklists.py", file=sys.stderr)
            return 1
        print("checklists.yml current")
        return 0

    OUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
