"""Gate 27: a strategy card's references resolve, and it does not claim more than it has.

`STRATEGY_CARD_SPEC` section 5 binds two rules and neither was checkable until `registry/cards.yml`
existed:

  1. **A card references components; it does not restate their formulas.** So every id under
     `components` must resolve in `components.yml`, and every id under `parameters`, `selection`,
     `exits`, `sizing` and `universe` must resolve in `parameters.yml`. A citation nobody can follow
     is not a citation - the same rule gate 1 applies to `read_by` and gate 20 to `implemented_by`.
  2. **A card is versioned as a whole**, and editing a field resets any validation claim resting on
     the earlier definition. This gate cannot see an edit, so it enforces the half it can: a card
     is `Validated` only with an evidence id, and carries one only if it is `Validated`.

**And one rule this project learned the expensive way.** A card with an `unset` input must say so in
`blocked_by`. An `unset` parameter makes its component refuse - that is the design working
(`AGENTS.md` section 12) - but a card that depends on one while claiming to be runnable is the
"specified, sometimes implemented, wired to nothing" shape section 7 was written for, one layer up.

**What this gate does NOT do.** It does not judge the strategy, and it cannot: `criteria.yml` v1.1.0
evaluates Track B on journalled trades only, and there are none. It checks that a card's claims are
internally consistent and its references real.

It also PRINTS the card's component activation, because `ROADMAP` G6 reads *"every component a live
strategy card needs is active"* and that criterion had no denominator before a card existed. The
figure is printed rather than failed on: `registered` is the correct state for a component no card
has demanded yet, and G6 is a project gate rather than a merge gate.

Stdlib plus PyYAML, like the other registry gates.

    python tools/verify_cards.py
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])
CARDS = REPO / "registry" / "cards.yml"
COMPONENTS = REPO / "registry" / "components.yml"
PARAMETERS = REPO / "registry" / "parameters.yml"

VALID_STATUS = ("Untested", "Testing", "Validated", "Retired")

#: Fields whose values are parameter ids, by the shape they take in the card.
PARAMETER_FIELDS = (
    ("universe", "parameters"),
    ("selection", "benchmark"),
    ("selection", "form"),
    ("selection", "lookback"),
    ("selection", "method"),
    ("selection", "cutoff"),
    ("sizing", "portfolio_constraints"),
    ("exits", None),
    ("invalidation", "initial_stop"),
    ("scope", "holding_horizon"),
)

#: A value meaning "this card deliberately does not set it". Not a parameter id, and not a defect.
NOT_A_REFERENCE = frozenset({"unset", None, ""})


def _load(path: Path) -> Any:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _referenced_parameters(card: dict[str, Any]) -> set[str]:
    """Every parameter id the card cites, from wherever it cites one."""
    found: set[str] = set()
    for section, key in PARAMETER_FIELDS:
        block = card.get(section)
        if not isinstance(block, dict):
            continue
        values = list(block.values()) if key is None else [block.get(key)]
        for value in values:
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, str) and item not in NOT_A_REFERENCE and "." in item \
                        and " " not in item:
                    found.add(item)
    return found


def check(cards: list[dict[str, Any]], components: set[str],
          parameters: dict[str, str]) -> tuple[list[str], list[str]]:
    """Failures, and the informational lines worth printing beside them."""
    failures: list[str] = []
    notes: list[str] = []
    seen: set[str] = set()

    for card in cards:
        label = card.get("card") or "<no id>"
        if label in seen:
            failures.append(f"{label}: duplicate card id")
        seen.add(label)

        status = card.get("status")
        if status not in VALID_STATUS:
            failures.append(f"{label}: status {status!r} is not one of {VALID_STATUS}")

        evidence = card.get("evidence")
        if status == "Validated" and not evidence:
            failures.append(f"{label}: status 'Validated' requires an evidence id")
        if evidence and status != "Validated":
            failures.append(
                f"{label}: carries evidence {evidence!r} but status is {status!r}. A card carries "
                f"evidence only when a study cleared it"
            )

        document = card.get("document")
        if not document or not (REPO / str(document)).is_file():
            failures.append(f"{label}: `document` names {document!r}, which is not a file")

        declared = card.get("components") or []
        for component in declared:
            if component not in components:
                failures.append(
                    f"{label}: component {component!r} does not resolve in components.yml"
                )

        cited = _referenced_parameters(card)
        for parameter in sorted(cited):
            if parameter not in parameters:
                failures.append(
                    f"{label}: parameter {parameter!r} does not resolve in parameters.yml"
                )

        # The rule that matters most: an unset input must be declared as a blocker.
        unset = sorted(p for p in cited if parameters.get(p) == "unset")
        if unset and not card.get("blocked_by"):
            failures.append(
                f"{label}: cites unset parameter(s) {unset} and declares no `blocked_by`. A card "
                f"depending on a value nobody has set is not runnable, and saying so is the point"
            )
        elif unset:
            notes.append(f"{label}: {len(unset)} unset input(s) - {', '.join(unset)}")

    return failures, notes


def main() -> int:
    if not CARDS.is_file():
        print(f"cards: no {CARDS.relative_to(REPO)} - nothing to check")
        return 0

    cards = (_load(CARDS) or {}).get("cards") or []
    components = {c["component"] for c in (_load(COMPONENTS) or {}).get("components") or []}
    activation = {
        c["component"]: c.get("activation")
        for c in (_load(COMPONENTS) or {}).get("components") or []
    }
    parameters = {
        p["id"]: p.get("status")
        for p in (_load(PARAMETERS) or {}).get("parameters") or []
    }

    failures, notes = check(cards, components, parameters)

    for card in cards:
        declared = card.get("components") or []
        active = sum(1 for c in declared if activation.get(c) == "active")
        print(f"  {card.get('card')}  status {card.get('status')}  "
              f"components {active}/{len(declared)} active  "
              f"blockers {len(card.get('blocked_by') or [])}")
    for note in notes:
        print(f"  {note}")

    if failures:
        print()
        for failure in failures:
            print(f"FAIL: {failure}")
        print(f"\ncards: {len(cards)} card(s), {len(failures)} failure(s)")
        return 1

    print(f"\ncards: {len(cards)} card(s), references resolve, no card claims more than it has")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
