"""The guard-verification tool must consult every guard `_submit` consults. `DR-036` proved it can drift.

**What paid for it, 2026-09-03.** `tools/verify_submission_guards.py` was written the same day
`DR-036` added the protection guard, and in the wrong order: the tool landed first and its docstring
claimed *"every guard in `_submit`'s order"* while the newest guard was not in it.

That is not a documentation slip. On the evening of 2026-09-03 the scheduled pass **stopped** —
`TECH: 3 open position(s) have no stop standing` — and the tool, run on the same book at the same
hour, would have printed *"WOULD SUBMIT 1 order(s), and every guard passes."* A safety tool that
disagrees with the thing it verifies, in the permissive direction, is worse than no tool.

**Why a test and not a gate.** A gate needs an inventory row and a number
(`CI_POLICY.md` §1, gates 36 and 38), and this is a property of two files rather than of the repo.
The suite already runs in CI, which is where a drift has to be caught.

**Why the exclusions are named individually.** The alternative is a rule that guesses which calls
are guards, and a guessing check is one that goes quiet in exactly the case it exists for. When a
new name appears in `_submit`, this test fails and somebody decides which list it belongs in —
the failure is the point.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SUBMIT = REPO / "src" / "swingdesk" / "presentation" / "cli.py"
TOOL = REPO / "tools" / "verify_submission_guards.py"

#: Calls `_submit` makes that BUILD or SEND rather than decide, and which the tool therefore has no
#: obligation to make. Each is here for a stated reason, never because it was inconvenient.
NOT_GUARDS = {
    "load_policy",          # configuration, checked by gate 39 rather than by a run
    "open_client",          # the connection itself
    "trading_session",      # derives the idempotency key; the tool calls it for the same reason
    "entry_order",          # builds a payload - the tool DOES call it, to check the prices
    "target_price",         # part of building one
    "protective_order",     # builds a protective payload (`DR-037`)
    "client_order_id",      # names an attempt for the journal
    "MISMATCH_CODE",        # a constant
}

#: A CALL, and either spelling of it. `_submit` calls its own helpers bare (`_allocate(...)`) and
#: the tool reaches them through the module (`cli._allocate(...)`) - the same guard, and a pattern
#: that admitted only one spelling would report a tool that consults everything as missing three.
GUARD_CALL = re.compile(
    r"broker_pkg\.([a-z_]+)\(|(?:cli\.)?\b(_drawdown_now|_committed_by_live_orders|_allocate)\("
)


def _submit_body() -> str:
    text = SUBMIT.read_text(encoding="utf-8")
    return text[text.index("def _submit("):text.index("def _broker(")]


def _guards_in(text: str) -> set[str]:
    found = {match.group(1) or match.group(2) for match in GUARD_CALL.finditer(text)}
    return {name for name in found if name not in NOT_GUARDS}


def test_the_tool_consults_every_guard_the_submission_path_consults() -> None:
    """THE REGRESSION. `unprotected` was in `_submit` and not in the tool for a whole day.

    **A CALL, never a mention.** The first version of this test asked whether the guard's NAME
    appeared anywhere in the tool - and a mutation that replaced the call with `naked = []` left
    the name in the section heading beside it, so the test passed with the fix removed. It was
    decoration for as long as it took to mutate it.
    """
    required = _guards_in(_submit_body())
    called = _guards_in(TOOL.read_text(encoding="utf-8"))

    missing = sorted(name for name in required if name not in called)
    assert not missing, (
        f"tools/verify_submission_guards.py does not consult {missing}, which `_submit` does. "
        f"Its docstring claims every guard in `_submit`'s order; a tool that misses one reports "
        f"a submission as safe that the real pass would refuse - which is what happened on "
        f"2026-09-03. Add the check, or move the name into NOT_GUARDS with a reason."
    )


def test_the_submission_path_still_has_guards_to_find() -> None:
    """The positive control, and `AGENTS.md` §9 is why it is here.

    A regex that stopped matching would make the test above pass by finding nothing to require -
    green, and evidence about nothing. This fails the day the extraction breaks.
    """
    required = _guards_in(_submit_body())
    assert len(required) >= 4, (
        f"only {sorted(required)} extracted from `_submit`. The guard extraction has broken, so "
        f"the parity test above is passing vacuously."
    )
    assert "reconcile" in required and "uncommitted_exposure" in required
