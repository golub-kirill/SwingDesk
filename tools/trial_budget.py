"""What the programme has spent against `b.deflated_sharpe`, and what the next trial costs.

**The criterion is ratified and nothing computes it.** `registry/criteria.yml` `b.deflated_sharpe`
reads *"Deflated Sharpe computed on the CUMULATIVE trial count across the whole programme"*, status
`ratified`. Measured 2026-08-24: no module computes a deflated Sharpe, and - the part that matters
more - **nothing counts the trials**. A criterion whose only input does not exist anywhere is a
criterion that cannot fire, and `AGENTS.md` section 7 has a name for the shape.

This tool supplies the input. It does not compute the deflated Sharpe: that needs each trial's
Sharpe and their dispersion, and Track B evaluates on JOURNALLED trades only (`criteria.yml` v1.1.0),
of which there are none. What it computes is the half that is knowable today - **how many
configurations the programme has already tried, and what the null's expected maximum Sharpe is at
that count.**

**A trial is a CONFIGURATION EVALUATED, not a pre-registration filed.** That distinction is the
whole point and it is why the number here is not the study census. `PR-005` registered one study and
tried five gate arms; each arm is a separate shot at the same data and the deflated Sharpe counts
shots. Counting pre-registrations instead would understate the search by roughly a factor of three,
in the flattering direction.

**The counting rule is per study and it is printed, not hidden.** Each entry below names the field
it reads and why that field is the configuration count, so a reader can disagree with the rule
rather than having to trust the total. Studies measuring a COST INPUT rather than a strategy's
return spend no trials - they cannot produce a Sharpe to be deflated.

The hurdle formula is an **authored import** (`AGENTS.md` section 10.3), marked as one:
Bailey & Lopez de Prado, *The Deflated Sharpe Ratio* (2014), the expected-maximum-Sharpe term.

Stdlib only. Reads `docs/prereg/results/`.

    python tools/trial_budget.py
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "docs" / "prereg" / "results"

#: Euler-Mascheroni. Bailey & Lopez de Prado (2014) equation for E[max SR] over N independent
#: trials; the constant weights the two order-statistic terms.
EULER_MASCHERONI = 0.5772156649015329


@dataclass(frozen=True, slots=True)
class Spend:
    """One study's trial spend, and the rule that produced the number."""

    study: str
    trials: int
    what: str
    rule: str


def _configurations(path: Path) -> tuple[int, str] | None:
    """Configurations a result records, or None when the study spends no trials.

    Derived from each result's own structure rather than from a hand-kept number, so a study that
    adds an arm cannot leave this tool describing the old shape.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    study = data.get("prereg")

    if study == "PR-001":
        names = data["definitions"]
        return len(names), ", ".join(names)
    if study == "PR-002":
        names = list(data["thresholds"])
        return len(names), ", ".join(names)
    if study == "PR-005":
        regime = next(iter(data["regimes"].values()))
        names = sorted(next(iter(regime["arms"].values())))
        return len(names), ", ".join(names)
    return None


#: Why a reported study spends no trials against this criterion. Listed rather than silently
#: skipped: "not counted" and "counted as zero" are the same number and different claims.
NO_SPEND = {
    "PR-008": "measures an effective-spread ESTIMATOR, not a strategy's return - no Sharpe to deflate",
    "PR-010": "same - EDGE against its own zero-spread floor, a cost input rather than an edge",
}

#: The rule each counted study's number comes from, printed beside it.
RULES = {
    "PR-001": "one per trend definition tested (`definitions`); the 6 pairwise comparisons are "
              "readings of those 4, not 6 further shots",
    "PR-002": "one per regime-classifier variant fitted (`thresholds`); one was selected and the "
              "other three were still tried",
    "PR-005": "one per gate arm (`regimes[*].arms`); 1x/3x is a cost stress on the same arm and "
              "primary/holdout is a data split, so neither multiplies the search",
}


def expected_max_sharpe(trials: int) -> float:
    """E[max Sharpe] under the null over `trials` independent shots, in units of sd(SR) across them.

    Bailey & Lopez de Prado (2014). An AUTHORED IMPORT and marked as one - the course supplies no
    multiple-testing correction and this project did not derive this. Reported in units of sd(SR)
    rather than absolute Sharpe deliberately: the absolute figure needs the dispersion of the
    trials' own Sharpes, which needs journalled trades, of which there are none. The ratio is the
    part that is knowable today and it is the part a budget decision turns on.
    """
    if trials < 2:
        return 0.0
    normal = NormalDist()
    return (
        (1 - EULER_MASCHERONI) * normal.inv_cdf(1 - 1 / trials)
        + EULER_MASCHERONI * normal.inv_cdf(1 - 1 / (trials * math.e))
    )


def spends() -> list[Spend]:
    found: list[Spend] = []
    for path in sorted(RESULTS.glob("PR-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        study = data.get("prereg")
        if not study:
            continue  # a provenance or side-record file, not a study result
        counted = _configurations(path)
        if counted is None:
            reason = NO_SPEND.get(study, "no counting rule declared for this study")
            found.append(Spend(study, 0, "-", reason))
            continue
        trials, what = counted
        found.append(Spend(study, trials, what, RULES.get(study, "no rule declared")))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(prog="trial_budget")
    parser.add_argument("--budget", type=int, default=None,
                        help="a candidate total, to price against what is already spent")
    args = parser.parse_args()

    found = spends()
    if not found:
        print("no reported studies found - nothing to count")
        return 1

    print("SPENT - configurations evaluated, per reported study\n")
    for spend in sorted(found, key=lambda s: s.study):
        print(f"  {spend.study}  {spend.trials:>2} trial(s)   {spend.what}")
        print(f"           rule: {spend.rule}")
    total = sum(spend.trials for spend in found)
    counted = [s for s in found if s.trials]
    print(f"\n  TOTAL {total} trial(s) across {len(counted)} of {len(found)} reported studies")
    print(f"  (the study census is {len(found)} - a trial is a configuration, not a filing)")

    print("\nTHE HURDLE - E[max Sharpe] under the null, in units of sd(SR) across trials")
    print(f"{'N':>5} {'hurdle':>9} {'marginal':>10}   ")
    previous = None
    for n in (1, 5, 10, total, 15, 20, 30, 50, 100):
        if n < 1:
            continue
        value = expected_max_sharpe(n)
        marginal = "-" if previous is None else f"+{value - previous[1]:.4f}"
        mark = "  <- spent" if n == total else ""
        print(f"{n:>5} {value:>9.4f} {marginal:>10}{mark}")
        previous = (n, value)

    at_now = expected_max_sharpe(total)
    print(f"\n  at {total} trials the null's expected best already sits {at_now:.2f} sd(SR) above zero")
    if args.budget:
        at_budget = expected_max_sharpe(args.budget)
        print(f"  at a budget of {args.budget} it would sit {at_budget:.2f} sd(SR), "
              f"a further +{at_budget - at_now:.2f}")

    first_five = expected_max_sharpe(5)
    next_forty_five = expected_max_sharpe(50) - first_five
    print("\n  The shape is logarithmic, and it is the finding a budget turns on: going from 1 to")
    print(f"  5 trials costs {first_five:.2f} sd(SR), and going from 5 all the way to 50 costs only")
    print(f"  {next_forty_five:.2f} more. The expensive trials are the FIRST ones. Rationing trials late")
    print("  buys very little; declaring and counting them buys the whole control.")
    print("\n  NOT computed here: the deflated Sharpe itself. It needs each trial's Sharpe and their"
          "\n  dispersion, and Track B evaluates on journalled trades only - there are none.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
