"""A generated checklist, and the four things an item can be.

The course's checklists are gated forms: every checklist stores date/time, version and owner,
and exactly one terminal state from the worksheet set (`DECISION_STATE_MACHINE.md` §5).

The four states matter more than the count. A machine item whose evidence does not exist yet is
**not** a human question and **not** a pass — it is `UNAVAILABLE`, and it says which evidence is
missing. Collapsing it into either of the others is how a checklist comes to claim more than the
system knows:

  PASS         machine-verified true from recorded run evidence
  FAIL         machine-verified false
  UNAVAILABLE  a machine item whose evidence this system does not yet produce
  HUMAN        only a person can answer it

`Complete` is unreachable while anything is unanswered. That is the gate part of "gated form".
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Worksheet terminal states, verbatim (DECISION_STATE_MACHINE 5). Not the decision set.
TERMINAL_STATES = ("Complete", "Research", "Pause", "Skip", "Error")


class ItemState(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"
    HUMAN = "human"


class ChecklistItem(BaseModel):
    """One line of a checklist, with its answer and where the answer came from."""

    model_config = ConfigDict(frozen=True)

    id: str
    text: str = Field(description="Verbatim from the appendix, via CHECKLIST_SPEC.")
    state: ItemState
    note: str | None = Field(
        default=None,
        description="For PASS/FAIL, the evidence. For UNAVAILABLE, what is missing. Required for "
                    "both, because an unexplained tick is not evidence and an unexplained gap is "
                    "not actionable.",
    )

    @model_validator(mode="after")
    def _explained(self) -> ChecklistItem:
        if self.state is not ItemState.HUMAN and not (self.note or "").strip():
            raise ValueError(
                f"{self.id}: state {self.state} must carry a note. A tick with no evidence behind "
                f"it is the thing this checklist exists to prevent."
            )
        return self


class Checklist(BaseModel):
    """One filled checklist for one candidate."""

    model_config = ConfigDict(frozen=True)

    appendix: str
    instrument_id: str
    run_id: str
    generated_at: datetime
    owner: str = "owner"
    version: int = Field(default=1, ge=1)
    items: tuple[ChecklistItem, ...]

    @property
    def counts(self) -> dict[str, int]:
        out = {state.value: 0 for state in ItemState}
        for item in self.items:
            out[item.state.value] += 1
        return out

    @property
    def unanswered(self) -> tuple[ChecklistItem, ...]:
        """Everything a human still has to answer, including the unavailable ones.

        An `UNAVAILABLE` item is unanswered by the system, so it lands on the person. Hiding it
        would make the checklist shorter and the decision worse.
        """
        return tuple(
            item for item in self.items
            if item.state in (ItemState.HUMAN, ItemState.UNAVAILABLE)
        )

    @property
    def failures(self) -> tuple[ChecklistItem, ...]:
        return tuple(item for item in self.items if item.state is ItemState.FAIL)

    def terminal_state(self) -> str:
        """The worksheet outcome this checklist has reached on its own.

        `Complete` requires every item answered and none failed — and since the system cannot answer
        a HUMAN item, a generated checklist never reaches `Complete` by itself. It reaches
        `Research`, and a person closes it. That is the correct shape: the system prepares the
        decision, the human makes it (`CHARTER.md` §2).
        """
        if self.failures:
            return "Skip"
        if self.unanswered:
            return "Research"
        return "Complete"
