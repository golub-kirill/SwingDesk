"""Gate 32: a checklist item's stated blocker must still be blocking.

Five of Appendix E's eighteen pre-trade items are answerable today. The other thirteen are `HUMAN`
or `UNAVAILABLE`, and each `UNAVAILABLE` one carries a sentence saying what the system is waiting
on. Those sentences are the map a session reads before deciding what to build next -
`plans/2026-08-24-the-trade-flow.md` §3 stage 4 is literally *"re-checking each `_unavailable`
reason first, since two were suspected stale and a third may be by the time this is worked"*.

**That re-check was a manual chore with no mechanism, and the chore is the defect.** `AGENTS.md`
§12 names the shape: *"a citation that was CORRECT when written, still standing after the fact it
cites moved"*. Here it costs more than usual in one direction - a reason that outlives its blocker
keeps an item `UNAVAILABLE` after the thing blocking it was supplied, so the checklist goes on
returning `Research` and `Trade` goes on being unreachable for a cause that no longer exists.

The imminent instance is `entry.maximum_entry_atr`. `DR-020` created it `unset` and two items wait
on it - `E08` (trigger measurable and not yet `Late`) and `E09` (entry zone and maximum entry
recorded). The moment it is ruled or measured, both reasons become false, and before this gate
nothing connected the registry row to the two sentences that cite it.

**What it checks.** Every `Unavailable` evaluator in `application/checklist.py` declares
`blocked_by`: parameter id -> the status that parameter must still have for the reason to hold.
The gate reads `registry/parameters.yml` and fails on any disagreement, and on any id the registry
does not know - a typo pins nothing and would pass forever.

**What it does not check, and says so every run.** Two of the eight reasons rest on a missing
*capability* with no registry row to pin: `E03` (corporate actions are fetched for held names only)
and `E05` (no sector-to-index mapping exists). The gate names those as unpinned rather than passing
over them silently - `AGENTS.md` §12: a gate that cannot see its subject must say so rather than
report a pass. Two more are pinned on their value half only - `E11` and `E14` each also wait on the
same absent event calendar - so a green pin means one blocker is still standing, never that the
item is otherwise ready.

    python tools/verify_checklist_blockers.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: Root of the tree whose REGISTRY is read. Overridable so a test can vary the registry alone and
#: watch the gate go red - the pins live in code and the statuses live in the registry, so varying
#: the registry is exactly the move this gate exists to catch.
REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: The code under inspection. A fixture tree that carries its own `src/` is read from; one that
#: carries only a registry falls back to this checkout, which is the tree the tool shipped in.
_SRC = REPO / "src"
sys.path.insert(0, str(_SRC if _SRC.is_dir() else Path(__file__).resolve().parents[1] / "src"))


def _registry_status() -> dict[str, str]:
    """Every parameter's current status: its provenance, or `unset` when it has no value.

    The same derivation as gate 28, and deliberately so - two gates disagreeing about what
    `assumed:DR-012` means would be worse than either being absent.
    """
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
            status[pid] = provenance.split(":")[0]
    return status


def main() -> int:
    from swingdesk.application.checklist import EVALUATORS, Unavailable, _load_items

    status = _registry_status()
    item_id = {
        row["evidence"]: row["id"]
        for row in _load_items("E") if row.get("evidence")
    }

    failures: list[str] = []
    unpinned: list[str] = []
    checked = 0

    for key, evaluator in EVALUATORS.items():
        if not isinstance(evaluator, Unavailable):
            continue
        label = f"{item_id.get(key, '?')} {key}"
        if not evaluator.blocked_by:
            unpinned.append(label)
            continue
        for pid, pinned in sorted(evaluator.blocked_by.items()):
            checked += 1
            actual = status.get(pid)
            if actual is None:
                failures.append(
                    f"{label}: pinned to `{pid}`, which registry/parameters.yml does not define. "
                    f"A pin the registry cannot resolve constrains nothing."
                )
            elif actual != pinned:
                failures.append(
                    f"{label}: its reason rests on `{pid}` being `{pinned}`; the registry has "
                    f"`{actual}`. Re-read the reason - the item may now be answerable."
                )

    for failure in failures:
        print(f"  {failure}")
    if failures:
        print(
            "\n  A pre-trade item that stays UNAVAILABLE after its blocker was supplied keeps"
            "\n  `Trade` unreachable for a cause that no longer exists. Correct the reason in"
            "\n  src/swingdesk/application/checklist.py, and wire the item if it can now be"
            "\n  answered (plans/2026-08-24-the-trade-flow.md section 3, stage 4)."
        )

    if unpinned:
        print("\n  blocked by a missing capability rather than a value, so nothing to pin:")
        for label in unpinned:
            print(f"    {label}")

    print(
        f"\nchecklist blockers: {checked} pin(s) checked, {len(unpinned)} unpinned, "
        f"{len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
