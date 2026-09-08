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

Side records in `results/` - a file with no `prereg`, such as a re-price at an earlier knowledge
instant - are declared to spend nothing rather than silently skipped.

Stdlib only. Reads `docs/prereg/results/` AND `docs/decisions/measurements/` - a configuration a
tool swept is a shot at the same data, and until 2026-09-06 only the first directory was counted.

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
MEASUREMENTS = REPO / "docs" / "decisions" / "measurements"

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

    # A study that DECLARED its spend is counted from its own declaration. `PREREG_TEMPLATE`
    # section 6 now requires that declaration - "state how many configurations it will evaluate,
    # before it runs" - so a rule inferred here would be a second opinion about a number the study
    # already committed to. The per-study rules below are for the studies that predate the
    # convention, and they exist because those results cannot be re-declared retroactively.
    declared = data.get("trials")
    if isinstance(declared, int):
        return declared, f"declared by the study: {declared} configuration(s)"

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

#: The rule each counted study's number comes from, printed beside it. A study carrying its own
#: `trials` field needs no row here - it declared, and the declaration is the rule.
RULES = {
    "PR-001": "one per trend definition tested (`definitions`); the 6 pairwise comparisons are "
              "readings of those 4, not 6 further shots",
    "PR-002": "one per regime-classifier variant fitted (`thresholds`); one was selected and the "
              "other three were still tried",
    "PR-005": "one per gate arm (`regimes[*].arms`); 1x/3x is a cost stress on the same arm and "
              "primary/holdout is a data split, so neither multiplies the search",
}


#: **The counter was blind to every configuration a TOOL tried — found 2026-09-06.**
#:
#: `b.deflated_sharpe` reads *"the CUMULATIVE trial count across the whole programme"*, and until
#: this table existed the programme meant `docs/prereg/results/` alone. An exploratory measurement
#: that sweeps a grid is still a grid of shots at the same data: `measure_exit_surface.py` evaluated
#: twenty-five stop/target cells against one null and spent nothing by that accounting - more
#: configurations than any single pre-registration has ever declared.
#:
#: **An earlier version of that sentence said "more than every pre-registration put together".**
#: True when written at 20 registered trials, false hours later when `PR-014` declared 12. The test
#: that asserted it failed and caught it, which is the only reason it is not still standing here.
#:
#: The rule is declared HERE rather than added to the evidence files, for the same reason `RULES`
#: is: a committed measurement records what was run, and editing one to satisfy a later counter
#: would rewrite the record. Same shape, same file, one more source.
#:
#: A measurement file with no row here is reported **UNDECLARED**, never counted as zero - those
#: are the same number and different claims, which is the sentence `NO_SPEND` already carries.
EXPLORATORY = {
    "exit-surface-2026-09-06": (
        26, "5 stop multiples x 5 targets, plus the buy-and-hold null each cell is marked against; "
            "the null is a configuration evaluated, not a free reference"),
    "long-only-horizon-2026-09-06": (
        8, "4 horizons x 2 formation skips; the gross/net pair is one cost restatement of each, "
           "not a second shot"),
    "execution-time-2026-09-06": (
        3, "3 execution times on one holding period; paired on the same entries, which sharpens "
           "the estimate and does not reduce the number of configurations tried"),
    "banding-2026-09-06": (
        4, "4 hold bands against one buy fraction; the narrowest IS the fixed control, so it is a "
           "configuration and not a separate baseline"),
    # The two spends the 2026-09-07 audit found. See the note above NO_SPEND_MEASUREMENTS.
    "pivots-2026-08-24": (
        7, "7 left/right pivot-width pairs (`grid`), each scored on forward confirmation drift in "
           "ATR and on breakout rate. `pivot.left` and `pivot.right` are registry parameters, so "
           "the best cell was a cell somebody would have kept"),
    "correlation-cap-calibration-2026-08-23": (
        2, "the ADMITTED and REFUSED books, each evaluated on mean net R over PR-005's trades "
           "(`cost`). The `premise` block compares event RATES rather than returns and is not a "
           "third shot; the 0.70 threshold was fixed by DR before this ran rather than swept"),
    "short-leg-2026-09-06": (
        8, "4 arms x 2 horizons. The unrestricted spread and the long-only excess are REPRODUCTIONS "
           "of already-counted results rather than new shots - but they are re-evaluated here on a "
           "population this tool rebuilt, so counting them is the conservative reading and the "
           "flattering one would be to net them out"),
}

#: **Fourteen measurements sat here UNDECLARED until 2026-09-07 and the total was wrong by nine.**
#:
#: The `UNDECLARED` line below has printed since this table was built on 2026-09-06, and it printed
#: for every measurement committed before that date - which was all of them. A gap that is reported
#: honestly is still a gap, and reading fourteen files is the only thing that closes it.
#:
#: **The rule used to classify them, stated once here rather than fourteen times below:** a trial is
#: a configuration you would have KEPT had it come out well. A grid scored on a forward RETURN is a
#: search - somebody would have adopted the best cell. A grid scored on how many names a floor
#: admits, how often a guard refuses, or how two rankings correlate is a POPULATION statistic: there
#: is no Sharpe in it to deflate, and no cell of it could have become a bet.
#:
#: **Two of the fourteen were spends and twelve were not.** `pivots-2026-08-24` swept seven
#: left/right widths and scored each on forward drift in ATR, and `pivot.left` / `pivot.right` are
#: real parameters in `registry/parameters.yml` - somebody would have kept the best of the seven.
#: `correlation-cap-calibration-2026-08-23` evaluated the admitted and refused books on NET R over
#: `PR-005`'s trades, which is two configurations scored on a return. The total moves 81 -> 90 and
#: the hurdle 2.46 -> 2.50, both in the conservative direction, which is the direction an
#: undeclared gap always hides.
#: Exploratory measurements that spend nothing, and why. Same distinction `NO_SPEND` draws for
#: pre-registrations: a cost or execution input has no Sharpe to deflate.
NO_SPEND_MEASUREMENTS = {
    "quoted-spread-2026-09-06": "the venue's quoted spread - a cost input, not a return",
    "fill-convention-2026-09-06": "which fills happen - an execution input, not a search over "
                                  "configurations; the two columns are one convention each and "
                                  "neither was chosen for its return",
    "gap-cost-2026-09-06": "the R cost of a stop-out - a cost input",
    "gap-population-2026-09-06": "a population comparison, no strategy return",
    "short-leg-2026-09-07": "no new trials: the same 8 configurations short-leg-2026-09-06 "
                            "declared, re-priced on measured turnover and re-run on the widened "
                            "sample. Counted once, in that measurement. A re-price of counted "
                            "shots is not a new shot",
    "decile-persistence-2026-09-07": "one-sided TURNOVER of the selected book - a cost input. It "
                                     "compares no return and selects nothing; the seven horizons "
                                     "are one book measured at seven spacings, not seven "
                                     "strategies",
    "benchmark-2026-08-24": "SPEARMAN CORRELATIONS between two rankings. It measures whether the "
                            "path form and a raw return order names differently, never what "
                            "either earns - there is no return in the file to deflate",
    "benchmark-fit-2026-09-06": "TRACKING ERROR against the admitted universe. The record states "
                                "its own selection criterion - `card excess is reported and is "
                                "NOT an input` - so no cell was ever scored on a return",
    "directory-file-sizes-2026-08-10": "HTTP HEAD content lengths on two vendor files. "
                                       "Infrastructure, not a strategy",
    "liquidity-floor-2026-08-23": "ten ADTV floors scored on how many names each ADMITS and what "
                                  "coverage each costs. A population census: the floor was chosen "
                                  "on the plateau in coverage, not on any return",
    "liquidity-sample": "a 120-name ADTV sample used to size the floor. A measurement of the "
                        "universe, not of a strategy",
    "revisions-2026-08-23": "a data-quality census of restated bars. No book, no return",
    "sector-cap-calibration-2026-08-23": "three caps scored on how often the GUARD REFUSES and on "
                                         "R concentration in the heaviest sector. A guard is not a "
                                         "bet: no cell of this could have been kept for what it "
                                         "earned, because it earns nothing",
    "sector-classifications-2026-08-23": "a per-name classification dump. Reference data",
    "sector-relative-2026-08-24": "the record refuses the claim itself - `not_measured: whether "
                                  "the sector signal PREDICTS anything. This measures that the "
                                  "denominator changes the order, not that the order is better`",
    "spread-sample": "two spread estimators on one sample - a cost input, and PR-008 and PR-010 "
                     "are where its verdict lives",
    "venue-fees-2026-09-05": "the venue's regulatory fee schedule, checked against one observed "
                             "round trip. A cost input, and a deterministic one",
}


#: **A file in `results/` with no `prereg` key is a SIDE RECORD, and silence about it is a claim.**
#:
#: `spends()` skips such a file, and it has to - a provenance dump is not a study. But "skipped" and
#: "spent nothing" print identically as an absence, which is the exact confusion `NO_SPEND` exists to
#: prevent one line above. So every side record is named here with the reason it costs nothing, and
#: one that is not named is reported UNDECLARED rather than passed over.
#:
#: The rule for a RE-PRICE, which is what the first entry is: correcting a cost model re-evaluates
#: configurations the programme has already counted and searches nothing. `b.deflated_sharpe` counts
#: shots at the data. Re-pricing twelve cells is not a thirteenth shot, and counting it as twelve
#: more would inflate the hurdle for arithmetic that could not have found an edge.
#: **Two of these were already sitting in `results/` and nothing had ever said what they cost.**
#: They were found by adding this table, not before it - which is the argument for the table.
#:
#: The rule that covers all three: a re-evaluation spends nothing when **no selection is made on
#: its output.** `PR-005`'s replay re-ran five counted arms to test whether the store reproduces
#: the study's inputs, and chose no arm on the answer. `PR-014`'s control re-prices twelve counted
#: cells to attribute a verdict change, and chooses no horizon on the answer. A shot at the data is
#: a configuration you would have KEPT had it come out well; neither of these could have been kept.
SIDE_RECORDS = {
    "PR-002-survivorship-bound": "no trials: a POST-HOC bound computed from PR-002.json, reading a "
                                 "committed result rather than evaluating a configuration",
    "PR-005-trades-provenance": "no new trials: a replay of PR-005's five counted gate arms at the "
                                "local store's vintage, run to test whether the inputs reproduce. "
                                "No arm was selected on its output",
    "PR-014-as-published": "no new trials: the PRESERVED BYTES of PR-014's 2026-09-06 result, kept "
                           "because the cost correction regenerated the result file in place. It "
                           "is the same twelve, counted once in PR-014.json, not a second run",
    "PR-014-cost-attribution": "no new trials: PR-014's OWN twelve configurations, re-run at an "
                               "earlier knowledge instant to separate the cost correction from the "
                               "2026-09-06 backfill. A re-price of counted shots is not a new shot",
}


def side_records() -> list[Spend]:
    """Result files that carry no `prereg`, and the declared reason each spends nothing."""
    found: list[Spend] = []
    for path in sorted(RESULTS.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("prereg"):
            continue
        name = path.stem
        if name in SIDE_RECORDS:
            found.append(Spend(name, 0, "-", SIDE_RECORDS[name]))
        else:
            found.append(Spend(name, 0, "UNDECLARED", "no counting rule declared for this side "
                                                      "record - this is a GAP, not a zero"))
    return found


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


def exploratory_spends() -> list[Spend]:
    """What the TOOLS tried. Every committed measurement, declared or reported undeclared."""
    found: list[Spend] = []
    for path in sorted(MEASUREMENTS.glob("*.json")):
        study = path.stem
        if study in NO_SPEND_MEASUREMENTS:
            found.append(Spend(study, 0, "-", NO_SPEND_MEASUREMENTS[study]))
        elif study in EXPLORATORY:
            trials, rule = EXPLORATORY[study]
            found.append(Spend(study, trials, f"{trials} configuration(s)", rule))
        else:
            found.append(Spend(study, 0, "UNDECLARED", "no counting rule declared - this is a "
                                                       "GAP, not a zero"))
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
    registered = sum(spend.trials for spend in found)
    counted = [s for s in found if s.trials]
    print(f"\n  {registered} trial(s) across {len(counted)} of {len(found)} reported studies")
    print(f"  (the study census is {len(found)} - a trial is a configuration, not a filing)")

    aside = side_records()
    if aside:
        print()
        print("  SIDE RECORDS in the same directory, each declared to spend nothing:")
        for spend in aside:
            marker = "  UNDECLARED" if spend.what == "UNDECLARED" else ""
            print(f"      {spend.study}{marker}")
            print(f"           rule: {spend.rule}")

    explored = exploratory_spends()
    print("\nSPENT - configurations evaluated by a TOOL, outside any pre-registration\n")
    for spend in explored:
        marker = "  UNDECLARED" if spend.what == "UNDECLARED" else ""
        print(f"  {spend.study}  {spend.trials:>2} trial(s)   {spend.what}{marker}")
        print(f"           rule: {spend.rule}")
    exploratory_total = sum(spend.trials for spend in explored)
    undeclared = [s for s in explored if s.what == "UNDECLARED"]
    print(f"\n  {exploratory_total} trial(s) across {len([s for s in explored if s.trials])} "
          f"of {len(explored)} committed measurements")
    if undeclared:
        print(f"  {len(undeclared)} measurement(s) carry NO counting rule and are reported as a "
              f"GAP, not as zero:")
        for spend in undeclared:
            print(f"      {spend.study}")

    total = registered + exploratory_total
    print(f"\n  TOTAL {total} trial(s) - {registered} registered, {exploratory_total} exploratory.")
    print(f"  Counting only the pre-registrations would report {registered}, understating the "
          f"search")
    print(f"  by {total - registered} configurations in the flattering direction.")

    print("\nTHE HURDLE - E[max Sharpe] under the null, in units of sd(SR) across trials")
    print(f"{'N':>5} {'hurdle':>9} {'marginal':>10}   ")
    previous = None
    # Sorted, and the spent total merged into the ladder rather than appended: an unsorted rung
    # makes the marginal column read as a DECREASE, which is the opposite of what the curve does.
    for n in sorted({1, 5, 10, 15, 20, 30, 50, 100, total}):
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
