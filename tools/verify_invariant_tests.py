"""Gate 34: an enforcement this repository claims must be able to fail.

Gate 8 says the tests pass. Nothing said they could **fail**, and two documents claim enforcement
that only a mutation can check.

**`INVARIANTS.md` §1** states *"Seven of nine are enforced by a test that would fail if the
invariant broke."* That sentence was false when written and stayed false for three weeks: the test
it names for invariant 1 asserted `r_multiple(net, sized) * sized.planned_risk == net` - which is
`(net / x) * x == net`, an identity true for every non-zero `x`. Replacing `planned_risk` with the
constant `Decimal("42")` left it green, measured 2026-08-17.

**`REQUIREMENTS.md` `REQ-VALIDATION-001`** is the other, and it is scar tissue rather than good
practice: in TradAlert an R:R gate was `if is_long: return True` and **passed seven audits**, because
it is a valid function with valid references. The requirement therefore demands that every gate,
veto or eligibility filter have *"a pair of inputs producing different verdicts"*. §2 records that
half of it landed as gate 3g and that the mutation half *"still does not exist, and it needs a
corpus of evaluated criteria before it can"*. **That corpus now exists** - `DR-006` wired the book,
correlation and sector caps into the live path and `DR-015` wired the staleness gate - so the five
live vetoes below are mutated to admit everything, and a named test must notice.

A document naming an enforcement that cannot fail is the non-negotiable *nothing looks more
validated than it is*, aimed at the suite rather than at a number. `tests/test_gates.py` already
applies this standard to the gates - *"a gate that has never been seen red proves nothing"*.

**What it does.** For each claim it copies `src/` to a scratch directory, applies one committed
source mutation that breaks it, and runs the named test against the copy. The test must FAIL.

**The real tree is never touched**, which matters more here than usual: `trade_management/sizing.py`
is a frozen file (`HANDOFF.md` §5) and two of the mutations land in it.

**What is NOT covered is named on every run.** Invariant 4 is carried by a function signature and
`INVARIANTS.md` §2 argues why that is stronger; invariant 7 is the determinism of a pure function,
where a mutation would be testing Python rather than this code. `REQ-VALIDATION-001` also covers
ratified CRITERIA, and `k.drawdown_pause` still cannot fire at all - a criterion with nothing to
evaluate has no verdict to flip, which is gate 3g's subject and not this one's.

**A mutation site that no longer matches is a FAILURE, not a skip.** Refactoring the line a mutant
targets is exactly when the check must speak up, and a silent skip would turn this gate into
decoration the first time someone renamed a variable.

    python tools/verify_invariant_tests.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])


@dataclass(frozen=True)
class Mutant:
    """One break of one claimed enforcement, and the test that must notice."""

    claim: str
    """What the tree claims - an `INVARIANTS.md` §1 row, or a veto `REQ-VALIDATION-001` covers."""

    breaks: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]


#: One mutant per claimed enforcement, each the plainest way it could break in this code.
#: They are committed rather than generated because a generated mutation is usually equivalent or
#: absurd, and neither teaches anything - `TODO.md` §6 records an equivalent mutant that cost a
#: session's attention.
#:
#: The veto mutants all take the same shape - force the gate to admit everything - because that is
#: the shape the requirement was written against: TradAlert's `if is_long: return True`.
MUTANTS: tuple[Mutant, ...] = (
    Mutant(
        claim="invariant 1",
        breaks="the sizing denominator stops being the planned risk",
        path="swingdesk/trade_management/sizing.py",
        old='planned_risk=(Decimal(shares) * risk_per_share).quantize(Decimal("0.01")),',
        new='planned_risk=Decimal("42"),',
        tests=("tests/test_invariants.py::test_r_denominator_is_the_planned_risk",),
    ),
    Mutant(
        claim="invariant 1",
        breaks="a position's denominator follows the stop instead of staying at entry",
        path="swingdesk/contracts/position.py",
        old="return self.entry_price - self.initial_stop + self.initial_costs_per_share",
        new="return self.entry_price - self.current_stop + self.initial_costs_per_share",
        tests=("tests/test_positions.py::test_r_denominator_survives_a_stop_move",),
    ),
    Mutant(
        claim="invariant 1",
        breaks="the denominator stops carrying round-trip costs, so 1R understates the loss",
        path="swingdesk/trade_management/sizing.py",
        old="    risk_per_share = entry - stop + costs\n",
        new="    risk_per_share = entry - stop\n",
        tests=("tests/test_invariants.py::test_sizing_and_position_agree_on_the_denominator",),
    ),
    Mutant(
        claim="invariant 2",
        breaks="open risk is clamped at zero instead of recomputed",
        path="swingdesk/contracts/position.py",
        old="return (self.entry_price - self.current_stop) * self.shares",
        new='return max(Decimal("0"), (self.entry_price - self.current_stop) * self.shares)',
        tests=("tests/test_positions.py::test_open_risk_is_recomputed_and_may_go_negative",),
    ),
    Mutant(
        claim="invariant 3",
        breaks="shares round up, so the position risks more than the budget allows",
        path="swingdesk/trade_management/sizing.py",
        old="shares = int((allowed_risk_local / risk_per_share)"
            ".to_integral_value(rounding=ROUND_DOWN))",
        new="shares = int((allowed_risk_local / risk_per_share)"
            '.to_integral_value(rounding="ROUND_UP"))',
        tests=("tests/test_invariants.py::test_shares_never_round_up",),
    ),
    Mutant(
        claim="invariant 5",
        breaks="a stop may be widened below the initial one after the fact",
        path="swingdesk/contracts/position.py",
        old="        if self.current_stop < self.initial_stop:",
        new="        if False and self.current_stop < self.initial_stop:",
        tests=("tests/test_positions.py::test_a_stop_below_the_initial_one_is_refused",),
    ),
    Mutant(
        claim="invariant 5",
        breaks="a downward stop move may be proposed",
        path="swingdesk/contracts/position.py",
        old="            if self.new_stop < self.old_stop:",
        new="            if False and self.new_stop < self.old_stop:",
        tests=("tests/test_positions.py::test_a_proposed_stop_move_downward_is_refused",),
    ),
    Mutant(
        claim="invariant 6",
        breaks="the only read path stops filtering on knowledge_time",
        path="swingdesk/market_data/store.py",
        old='"instrument_id = ?", "interval = ?", "series = ?", "knowledge_time <= ?",',
        new='"instrument_id = ?", "interval = ?", "series = ?", "? IS NOT NULL",',
        tests=("tests/test_pipeline.py::test_as_of_ignores_later_knowledge",),
    ),
    Mutant(
        claim="invariant 8",
        breaks="breadth becomes dependent on the order its members arrive in",
        path="swingdesk/derived_observations/breadth.py",
        old="            if series.bars[index].close > average:\n                above += 1",
        new="            if series.bars[index].close > average and counted % 2:\n"
            "                above += 1",
        tests=("tests/test_component_oracles.py::test_breadth_is_invariant_to_member_order",),
    ),
    Mutant(
        claim="invariant 9",
        breaks="an unset parameter yields a value instead of a coded refusal",
        path="swingdesk/platform/parameters.py",
        old='        if entry.get("value") is None:\n            raise ParameterUnset(parameter_id)',
        new='        if entry.get("value") is None:\n            entry = {**entry, "value": 1, '
            '"provenance": "assumed:mutant"}',
        tests=("tests/test_invariants.py::test_unset_parameter_refuses_and_names_itself",),
    ),
    Mutant(
        claim="invariant 9",
        breaks="an unfitted classifier invents a threshold instead of refusing",
        path="swingdesk/derived_observations/regime.py",
        old="        if not self.fitted_on:",
        new="        if False and not self.fitted_on:",
        tests=("tests/test_regime.py::"
               "test_an_unfitted_classifier_refuses_rather_than_inventing_a_threshold",),
    ),

    # ---- REQ-VALIDATION-001: every veto must have a pair of inputs producing different verdicts.
    # Each of these five evaluates on the live path today, which is what `REQUIREMENTS.md` §2 said
    # did not exist yet. `DR-006` wired three of them and `DR-015` the fourth and fifth.
    Mutant(
        claim="REQ-VALIDATION-001 veto",
        breaks="the concurrent-position cap admits a fifth position",
        path="swingdesk/trade_management/portfolio.py",
        old="    if book.count + 1 > caps.max_concurrent:",
        new="    if False and book.count + 1 > caps.max_concurrent:",
        tests=("tests/test_portfolio.py::test_the_fifth_position_is_refused_on_the_count",),
    ),
    Mutant(
        claim="REQ-VALIDATION-001 veto",
        breaks="the open-risk cap admits a candidate past the book's R budget",
        path="swingdesk/trade_management/portfolio.py",
        old="    elif book.open_risk_r + requested_r > caps.max_open_risk:",
        new="    elif False and book.open_risk_r + requested_r > caps.max_open_risk:",
        tests=("tests/test_portfolio.py::test_open_risk_refuses_before_the_count_does",),
    ),
    Mutant(
        claim="REQ-VALIDATION-001 veto",
        breaks="the sector cap admits a candidate that would breach one sector",
        path="swingdesk/trade_management/portfolio.py",
        old="        if over:",
        new="        if False and over:",
        tests=("tests/test_sector.py::"
               "test_a_candidate_that_would_pass_the_cap_in_one_sector_is_refused",),
    ),
    Mutant(
        claim="REQ-VALIDATION-001 veto",
        breaks="the correlation cap admits a duplicate of an open position",
        path="swingdesk/trade_management/portfolio.py",
        old="        if r is None or r < limit.threshold:",
        new="        if True or r is None or r < limit.threshold:",
        tests=("tests/test_correlation.py::"
               "test_a_duplicate_refuses_and_names_the_position_it_duplicates",),
    ),
    Mutant(
        claim="REQ-VALIDATION-001 veto",
        breaks="the staleness gate stops dropping an instrument past the window",
        path="swingdesk/market_data/freshness.py",
        old="    elif behind >= allowed:",
        new="    elif False and behind >= allowed:",
        tests=("tests/test_freshness.py::"
               "test_the_window_is_reached_at_two_and_drops_the_instrument",),
    ),
    Mutant(
        claim="REQ-VALIDATION-001 veto",
        breaks="the session count the staleness gate compares is off by one",
        path="swingdesk/reference_data/calendar.py",
        old="    return max(0, len(window) - 1)\n",
        new="    return max(0, len(window))\n",
        tests=("tests/test_freshness.py::test_friday_to_monday_is_one_session_not_three_days",),
    ),
)

#: Claim -> why no mutant exists for it. Printed every run: a gate that cannot see part of its
#: subject says so rather than reporting a pass over it (`AGENTS.md` §12).
UNCOVERED = {
    "invariant 4": "carried by the signature of `size_long`, not by a test - `INVARIANTS.md` "
                   "section 2 argues that is stronger, and there is nothing to mutate",
    "invariant 7": "determinism of a pure function. A mutation that made it non-deterministic "
                   "would be testing Python rather than this code",
    "REQ-VALIDATION-001 criteria": "the requirement also covers ratified CRITERIA, and "
                                   "`k.drawdown_pause` cannot fire at all - nothing computes "
                                   "realised drawdown, so there is no verdict to flip. That is "
                                   "gate 3g's subject and `TODO.md` section 1's open item",
}


def _run_mutant(mutant: Mutant, scratch: Path, index: int) -> str | None:
    """None when the named test caught the mutation; a description of the miss otherwise."""
    workspace = scratch / f"mutant{index}"
    shutil.copytree(REPO / "src", workspace / "src")

    target = workspace / "src" / mutant.path
    if not target.is_file():
        return f"{mutant.path} does not exist; the mutation site has moved"
    source = target.read_text(encoding="utf-8")
    if mutant.old not in source:
        return (f"the mutation site in {mutant.path} no longer matches. Re-point it at the line "
                f"that now carries this claim; a mutant that cannot be applied proves nothing")
    target.write_text(source.replace(mutant.old, mutant.new, 1), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", *mutant.tests, "-q", "-x"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONPATH": str(workspace / "src")},
    )
    if "no tests ran" in result.stdout or "ERROR" in result.stdout:
        return (f"the named test did not run: {', '.join(mutant.tests)}. A missing test is not a "
                f"passing one")
    if result.returncode == 0:
        return (f"SURVIVED. {', '.join(mutant.tests)} passed with the enforcement broken, so it "
                f"does not enforce what the tree says it enforces")
    return None


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="swingdesk-mutants-") as raw:
        scratch = Path(raw)
        for index, mutant in enumerate(MUTANTS):
            problem = _run_mutant(mutant, scratch, index)
            print(f"  {'killed ' if problem is None else 'MISSED '} "
                  f"{mutant.claim}: {mutant.breaks}")
            if problem is not None:
                failures.append(f"{mutant.claim}: {problem}")

    print("\n  not covered by a mutant, and each for a stated reason:")
    for claim, reason in sorted(UNCOVERED.items()):
        print(f"    {claim}: {reason}")

    for failure in failures:
        print(f"\n  {failure}")
    if failures:
        print(
            "\n  `INVARIANTS.md` section 1 and `REQ-VALIDATION-001` both claim an enforcement that"
            "\n  only a mutation can check. Make the test able to fail, or correct the claim - a"
            "\n  document naming an enforcement that cannot fail is the non-negotiable *nothing"
            "\n  looks more validated than it is*, applied to the suite."
        )
    claims = sorted({mutant.claim for mutant in MUTANTS})
    print(
        f"\nenforcement mutants: {len(MUTANTS)} over {len(claims)} claim(s) "
        f"({', '.join(claims)}), {len(UNCOVERED)} uncovered, {len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
