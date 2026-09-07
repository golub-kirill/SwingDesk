"""Which of the two changes flipped `PR-014`'s verdict - the cost correction or the backfill.

**`PR-014` was published ACCEPT and is now INCONCLUSIVE, and two things changed between the runs.**
The cost model was corrected from GROSS turnover to MEASURED NET turnover, and the admitted universe
was backfilled from about two years of bars to a decade. A re-run changed both at once, which
attributes nothing: "the verdict moved" is not a finding about either change.

**This tool separates them, and it can do so without a third thirty-five-minute run.** Cost enters
`run_pr014.py` as a CONSTANT annualised subtraction from a bootstrapped GROSS interval - `net_low =
low * 12 - cost` - so re-pricing a committed cell under the other cost model is exact arithmetic on
numbers already in the file, not a re-estimate. Each result carries both costs per row:
`annual_cost` (measured net turnover) and `annual_cost_as_first_published` (`252 / horizon` full
turns). The sample is separated by the store's bitemporal `as_of`: the pre-backfill run is committed
beside the result as a side record.

So the 2x2 is two files by two cost models, and every cell is decided by `run_pr014.decide` - the
same function the study runs - rather than by a rule restated here.

    PYTHONPATH=$PWD/src python tools/attribute_pr014_flip.py

Reads only committed JSON. Touches no store, spends no trials: re-pricing a configuration already
counted evaluates no new one.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from run_pr014 import STRESS_MULTIPLE, decide

RESULTS = REPO / "docs" / "prereg" / "results"

#: `run_pr014.py` rounds every figure it writes to six decimal places, independently. So `gross`,
#: `net` and `cost` each carry up to half a unit of rounding and their identity holds only to
#: within one whole unit at that place. Not a tolerance chosen to make a check pass - it is the
#: precision of the file being read.
ULP = Decimal("0.000001")

#: The two cost models, and the field each reads. Named rather than passed as booleans so the
#: printed table says which is which without a legend.
COSTS = {
    "as first published (gross)": "annual_cost_as_first_published",
    "corrected (measured net)": "annual_cost",
}


def reprice(row: dict[str, Any], field: str) -> dict[str, Any]:
    """One cell, re-priced under the cost in `field`.

    The bootstrap is not re-run and does not need to be: the interval is estimated on the GROSS
    per-period series and the cost is subtracted afterwards, so recovering the gross bound is
    `net_low + annual_cost` and re-pricing it is a second subtraction. The qualification flag is
    then RE-DERIVED from the new bounds rather than copied - copying it is the whole error this
    tool exists to measure.
    """
    cost = Decimal(str(row[field]))
    priced: dict[str, Any] = {k: v for k, v in row.items() if k not in ("primary", "holdout")}
    priced["annual_cost"] = float(cost)
    for window in ("primary", "holdout"):
        cell = dict(row[window])
        if "net_annual" not in cell:  # a window the sample rule refused
            priced[window] = cell
            continue
        was = Decimal(str(row["annual_cost"]))
        for key in ("net_annual", "net_low", "net_high"):
            cell[key] = float(Decimal(str(cell[key])) + was - cost)
        cell["net_excludes_zero"] = bool(
            cell["sample_rule_met"] and (cell["net_low"] > 0 or cell["net_high"] < 0)
        )
        cell["both_negative"] = bool(
            cell["net_annual"] < 0 and cell["control_universe_annual"] < 0
        )
        priced[window] = cell
    return priced


def check_reproduction(published: dict[str, Any], control: dict[str, Any]) -> list[str]:
    """Every line on which the control run FAILS to reproduce the published one.

    The attribution rests on the control being the published run with one thing changed, and that
    is a claim about bytes rather than a description of intent. `net + cost` recovers the gross
    figure the bootstrap actually produced, and gross is what must be identical: same `as_of`, same
    series, same block, same seed. A control that drifted would still print a well-formed 2x2 and
    would attribute the flip to whatever it happened to compare.
    """
    was = {(r["horizon"], r["arm"]): r for r in published["rows"]}
    drift: list[str] = []
    if published["as_of"] != control["as_of"]:
        drift.append(f"as_of {published['as_of']} != {control['as_of']}")
    for row in control["rows"]:
        before = was.get((row["horizon"], row["arm"]))
        if before is None:
            drift.append(f"{row['horizon']} {row['arm']}: absent from the published run")
            continue
        for window in ("primary", "holdout"):
            a, b = before[window], row[window]
            if "gross_annual" not in a or "gross_annual" not in b:
                continue
            # `gross_annual` is the comparison and it is compared EXACTLY. It is what the bootstrap
            # produced, before any cost touched it, and both files round it once from the same
            # quantity.
            if Decimal(str(a["gross_annual"])) != Decimal(str(b["gross_annual"])):
                drift.append(f"{row['horizon']} {row['arm']} {window}: gross "
                             f"{a['gross_annual']} != {b['gross_annual']}")
            # `net + cost` is a SECOND route to the same number, and the first version of this
            # check used it alone. That was wrong and reported six false differences: net and cost
            # are each rounded to six places independently, so their sum can miss gross by one unit
            # in the last place without anything having drifted. Kept as a consistency check with
            # exactly that tolerance, rather than dropped, because an internally inconsistent file
            # is worth catching and is a different fault from a drifted one.
            for name, cell, cost in ((". published", a, before), (". control", b, row)):
                slack = abs(Decimal(str(cell["gross_annual"]))
                            - Decimal(str(cell["net_annual"]))
                            - Decimal(str(cost["annual_cost"])))
                if slack > ULP:
                    drift.append(f"{row['horizon']} {row['arm']} {window}{name}: "
                                 f"gross - net - cost = {slack}, above one unit in the last place")
            if a["rebalances"] != b["rebalances"]:
                drift.append(f"{row['horizon']} {row['arm']} {window}: "
                             f"{a['rebalances']} rebalances != {b['rebalances']}")
    return drift


def main() -> int:
    parser = argparse.ArgumentParser(prog="attribute_pr014_flip")
    parser.add_argument("--result", type=Path, default=RESULTS / "PR-014.json",
                        help="the current, post-backfill result")
    parser.add_argument("--control", type=Path,
                        default=RESULTS / "PR-014-cost-attribution.json",
                        help="the same twelve configurations at the pre-backfill knowledge instant")
    parser.add_argument("--published", type=Path, default=RESULTS / "PR-014-as-published.json",
                        help="the bytes PR-014 published, preserved when the result was regenerated")
    args = parser.parse_args()

    published = json.loads(args.published.read_text(encoding="utf-8"))
    control = json.loads(args.control.read_text(encoding="utf-8"))
    drift = check_reproduction(published, control)
    print("REPRODUCTION: does the control run recover the published run's gross figures?")
    if drift:
        print(f"  NO - {len(drift)} difference(s). The attribution below is NOT trustworthy:")
        for line in drift:
            print(f"      {line}")
    else:
        print(f"  YES - all {len(published['rows'])} cells, both windows, identical gross to the "
              f"last committed digit,")
        print(f"  at as_of {published['as_of']}. Only the cost model differs.")
    print()

    samples = {
        "pre-backfill  (as published)": control,
        "post-backfill (current)": json.loads(args.result.read_text(encoding="utf-8")),
    }

    print("TURNOVER: what a book actually trades, against what PR-014 charged it for")
    print(f"  {'horizon':>8}{'K':>4}  {'measured net/reb':>17}{'charged (252/h)':>17}"
          f"{'long-only cost/yr':>19}{'as published':>14}")
    for row in samples["post-backfill (current)"]["rows"]:
        if row["arm"] != "long_only":
            continue
        charged = 252 / int(row["horizon"])
        print(f"  {row['horizon']:>8}{row['K']:>4}  {row['turnover_per_rebalance'] * 100:>16.1f}%"
              f"{charged:>16.2f}x{row['annual_cost'] * 100:>18.2f}%"
              f"{row['annual_cost_as_first_published'] * 100:>13.2f}%")

    print()
    print("THE VERDICT, over sample x cost model - each decided by run_pr014.decide")
    print(f"  {'sample':<30}{'cost model':<28}{'shortest qualifying':>20}  {'verdict':<14}")
    grid: dict[tuple[str, str], dict[str, Any]] = {}
    for sample, data in samples.items():
        for label, field in COSTS.items():
            rows = [reprice(r, field) for r in data["rows"]]
            outcome = decide(rows, STRESS_MULTIPLE)
            grid[(sample, label)] = outcome
            where = (f"{outcome['horizon']} {outcome.get('arm', '-')}"
                     if "horizon" in outcome else "none")
            verdict = str(outcome["verdict"]).upper()
            print(f"  {sample:<30}{label:<28}{where:>20}  {verdict:<14}")

    published = grid[("pre-backfill  (as published)", "as first published (gross)")]
    cost_only = grid[("pre-backfill  (as published)", "corrected (measured net)")]
    both = grid[("post-backfill (current)", "corrected (measured net)")]
    sample_only = grid[("post-backfill (current)", "as first published (gross)")]

    print()
    print("ATTRIBUTION")
    print(f"  the cost correction alone   {published['verdict']} -> {cost_only['verdict']}"
          f"   (sample held fixed)")
    print(f"  the backfill alone          {published['verdict']} -> {sample_only['verdict']}"
          f"   (cost model held fixed)")
    print(f"  both, as reported now       {published['verdict']} -> {both['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
