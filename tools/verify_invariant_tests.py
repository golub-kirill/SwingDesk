"""Gate 34: the tests `INVARIANTS.md` names must be able to fail.

`INVARIANTS.md` §1 states *"Seven of nine are enforced by a test that would fail if the invariant
broke."* **That sentence was false when it was written, and stayed false for three weeks.** The test
it names for invariant 1 asserted `r_multiple(net, sized) * sized.planned_risk == net` - which is
`(net / x) * x == net`, an identity true for every non-zero `x`. Replacing `planned_risk` with the
constant `Decimal("42")` left it green, measured 2026-08-17.

A document naming a test that cannot fail is the non-negotiable *nothing looks more validated than
it is*, aimed at the test suite rather than at a number. `tests/test_gates.py` already applies this
standard to the gates - *"a gate that has never been seen red proves nothing"* - and the invariants,
which are the properties the whole system rests on, had no equivalent.

**What it does.** For each covered invariant it copies `src/` to a scratch directory, applies one
committed source mutation that breaks that invariant, and runs the named test against the copy. The
test must FAIL. A mutant that survives is reported with the invariant it disproves.

**The real tree is never touched**, which matters more here than usual: `trade_management/sizing.py`
is a frozen file (`HANDOFF.md` §5) and two of the mutations land in it.

**Two of the nine are not covered and the gate says which, every run.** Invariant 4 is carried by a
function signature rather than by a test and `INVARIANTS.md` §2 argues why that is stronger; nothing
can mutate it. Invariant 7 is *"identical inputs yield an identical classification"*, and a mutation
that made a pure function non-deterministic would be testing Python rather than this code.

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
    """One break of one invariant, and the test that must notice."""

    invariant: int
    breaks: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]


#: One mutant per covered invariant, each the plainest way that invariant could break in this code.
#: They are committed rather than generated because a generated mutation is usually equivalent or
#: absurd, and neither teaches anything - `TODO.md` §6 records an equivalent mutant that cost a
#: session's attention.
MUTANTS: tuple[Mutant, ...] = (
    Mutant(
        invariant=1,
        breaks="the sizing denominator stops being the planned risk",
        path="swingdesk/trade_management/sizing.py",
        old='planned_risk=(Decimal(shares) * risk_per_share).quantize(Decimal("0.01")),',
        new='planned_risk=Decimal("42"),',
        tests=("tests/test_invariants.py::test_r_denominator_is_the_planned_risk",),
    ),
    Mutant(
        invariant=1,
        breaks="a position's denominator follows the stop instead of staying at entry",
        path="swingdesk/contracts/position.py",
        old="return self.entry_price - self.initial_stop + self.initial_costs_per_share",
        new="return self.entry_price - self.current_stop + self.initial_costs_per_share",
        tests=("tests/test_positions.py::test_r_denominator_survives_a_stop_move",),
    ),
    Mutant(
        invariant=2,
        breaks="open risk is clamped at zero instead of recomputed",
        path="swingdesk/contracts/position.py",
        old="return (self.entry_price - self.current_stop) * self.shares",
        new='return max(Decimal("0"), (self.entry_price - self.current_stop) * self.shares)',
        tests=("tests/test_positions.py::test_open_risk_is_recomputed_and_may_go_negative",),
    ),
    Mutant(
        invariant=3,
        breaks="shares round up, so the position risks more than the budget allows",
        path="swingdesk/trade_management/sizing.py",
        old="shares = int((allowed_risk_local / risk_per_share)"
            ".to_integral_value(rounding=ROUND_DOWN))",
        new="shares = int((allowed_risk_local / risk_per_share)"
            '.to_integral_value(rounding="ROUND_UP"))',
        tests=("tests/test_invariants.py::test_shares_never_round_up",),
    ),
    Mutant(
        invariant=5,
        breaks="a stop may be widened below the initial one after the fact",
        path="swingdesk/contracts/position.py",
        old="        if self.current_stop < self.initial_stop:",
        new="        if False and self.current_stop < self.initial_stop:",
        tests=("tests/test_positions.py::test_a_stop_below_the_initial_one_is_refused",),
    ),
    Mutant(
        invariant=5,
        breaks="a downward stop move may be proposed",
        path="swingdesk/contracts/position.py",
        old="            if self.new_stop < self.old_stop:",
        new="            if False and self.new_stop < self.old_stop:",
        tests=("tests/test_positions.py::test_a_proposed_stop_move_downward_is_refused",),
    ),
    Mutant(
        invariant=6,
        breaks="the only read path stops filtering on knowledge_time",
        path="swingdesk/market_data/store.py",
        old='"instrument_id = ?", "interval = ?", "series = ?", "knowledge_time <= ?",',
        new='"instrument_id = ?", "interval = ?", "series = ?", "? IS NOT NULL",',
        tests=("tests/test_pipeline.py::test_as_of_ignores_later_knowledge",),
    ),
    Mutant(
        invariant=8,
        breaks="breadth becomes dependent on the order its members arrive in",
        path="swingdesk/derived_observations/breadth.py",
        old="            if series.bars[index].close > average:\n                above += 1",
        new="            if series.bars[index].close > average and counted % 2:\n"
            "                above += 1",
        tests=("tests/test_component_oracles.py::test_breadth_is_invariant_to_member_order",),
    ),
    Mutant(
        invariant=9,
        breaks="an unset parameter yields a value instead of a coded refusal",
        path="swingdesk/platform/parameters.py",
        old='        if entry.get("value") is None:\n            raise ParameterUnset(parameter_id)',
        new='        if entry.get("value") is None:\n            entry = {**entry, "value": 1, '
            '"provenance": "assumed:mutant"}',
        tests=("tests/test_invariants.py::test_unset_parameter_refuses_and_names_itself",),
    ),
    Mutant(
        invariant=9,
        breaks="an unfitted classifier invents a threshold instead of refusing",
        path="swingdesk/derived_observations/regime.py",
        old="        if not self.fitted_on:",
        new="        if False and not self.fitted_on:",
        tests=("tests/test_regime.py::"
               "test_an_unfitted_classifier_refuses_rather_than_inventing_a_threshold",),
    ),
)

#: Invariant -> why no mutant exists for it. Printed every run: a gate that cannot see part of its
#: subject says so rather than reporting a pass over it (`AGENTS.md` §12).
UNCOVERED = {
    4: "carried by the signature of `size_long`, not by a test - `INVARIANTS.md` section 2 argues "
       "that is stronger, and there is nothing to mutate",
    7: "determinism of a pure function. A mutation that made it non-deterministic would be testing "
       "Python rather than this code",
}


def _run_mutant(mutant: Mutant, scratch: Path, index: int) -> str | None:
    """None when the named test caught the mutation; a description of the miss otherwise."""
    workspace = scratch / f"inv{mutant.invariant}_{index}"
    shutil.copytree(REPO / "src", workspace / "src")

    target = workspace / "src" / mutant.path
    if not target.is_file():
        return f"{mutant.path} does not exist; the mutation site has moved"
    source = target.read_text(encoding="utf-8")
    if mutant.old not in source:
        return (f"the mutation site in {mutant.path} no longer matches. Re-point it at the line "
                f"that now carries this invariant; a mutant that cannot be applied proves nothing")
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
        return (f"SURVIVED. {', '.join(mutant.tests)} passed with the invariant broken, so it does "
                f"not enforce what `INVARIANTS.md` section 1 says it enforces")
    return None


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="swingdesk-mutants-") as raw:
        scratch = Path(raw)
        for index, mutant in enumerate(MUTANTS):
            problem = _run_mutant(mutant, scratch, index)
            print(f"  {'killed ' if problem is None else 'MISSED '} "
                  f"invariant {mutant.invariant}: {mutant.breaks}")
            if problem is not None:
                failures.append(f"invariant {mutant.invariant}: {problem}")

    print("\n  not covered by a mutant, and each for a stated reason:")
    for invariant, reason in sorted(UNCOVERED.items()):
        print(f"    invariant {invariant}: {reason}")

    for failure in failures:
        print(f"\n  {failure}")
    if failures:
        print(
            "\n  `INVARIANTS.md` section 1 claims these tests would fail if the invariant broke."
            "\n  Make the test able to fail, or correct the claim - a document naming a test that"
            "\n  cannot fail is the non-negotiable *nothing looks more validated than it is*,"
            "\n  applied to the suite."
        )
    covered = sorted({mutant.invariant for mutant in MUTANTS})
    print(
        f"\ninvariant tests: {len(MUTANTS)} mutant(s) over invariant(s) "
        f"{', '.join(str(number) for number in covered)}, {len(UNCOVERED)} uncovered, "
        f"{len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
