"""Report the drawdown `k.drawdown_pause` triggers on, so the criterion can be evaluated at all.

`k.drawdown_pause` is ratified with scope `live` and until 2026-08-30 **nothing computed its input**
- `validation.max_allowable_drawdown` is owner-set at 20 percent and its `read_by` was `none`. This
is what makes the criterion evaluable. `criteria.yml` amendment v1.1.2 fixes what the trigger's word
means: peak-to-trough drawdown of account equity **including open positions marked to market**,
peak-relative, baseline `account.equity`.

~~**It reports and it does nothing.** ... Nothing in the decision path calls this~~ - true
until `DR-034` on 2026-09-03, which made a breach halt every submission. **This reports the number
the kill switch acts on**, and since 2026-09-26 it is computed by the SAME function:
`cli._drawdown_now`. It used to assemble the curve itself - its own sessions, its own marks, its own
action lookup - and when the kill switch was found reading the open book only, this had the identical
defect in its own copy. One measurement in two places had become two measurements that agreed by
coincidence; now there is one, and the report cannot disagree with what stops the run.

The prescribed action still names the risk-off ladder, `risk.risk_off_ladder` is `unset`, and that
half - reducing size - is the owner's. What is automated is the pause.

**Position store only.** Not the journal - the journal holds runs and decisions, and equity is a
fact about positions and fills. Marks come from the bar store, because "marked to market" needs a
price and a position record does not carry one.

~~Read-only over `data/`.~~ Not quite, and a tool run against live stores should say so:
`PositionStore` and `BarStore` open read-write and run `schema.reconcile`, which alters a
table only when a column is missing. It writes no position, fill or bar.

    python tools/measure_drawdown.py --data C:/PycharmProjects/SwingDesk/data
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.market_data import BarStore
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset
from swingdesk.presentation.cli import _drawdown_now
from swingdesk.trade_management import drawdown as measurement


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data", help="the data directory")
    args = parser.parse_args()

    root = Path(args.data)
    registry = ParameterRegistry.load()

    try:
        baseline, equity_use = registry.decimal_value("account.equity")
    except ParameterUnset as unset:
        # Fail-closed, like every other threshold read: a drawdown against a guessed account size
        # is a percentage of nothing.
        print(f"UNAVAILABLE: {unset.parameter_id} is unset, so there is no baseline to draw down "
              f"from. The measurement refuses rather than inventing one.")
        return 1

    try:
        limit, limit_use = registry.decimal_value("validation.max_allowable_drawdown")
    except ParameterUnset:
        limit, limit_use = None, None

    as_of = datetime.now(UTC)
    with (
        PositionStore(root / "positions.duckdb") as positions_store,
        BarStore(root / "bars.duckdb") as bars,
    ):
        held = positions_store.latest_as_of(as_of)
        result = _drawdown_now(positions_store, bars, registry, as_of)

    print(f"positions           {sum(p.is_open for p in held)} open, "
          f"{sum(not p.is_open for p in held)} closed - realised results count, not only what is "
          f"held")
    print(f"baseline equity     {baseline}  ({equity_use.provenance})")
    if isinstance(result, measurement.Unavailable):
        print(f"drawdown            UNAVAILABLE - {result.reason}")
        for position_id, session in result.unpriced[:10]:
            print(f"  unpriced          {position_id} on {session}")
        return 0

    print(f"peak                {result.peak}")
    print(f"trough              {result.trough}")
    print(f"drawdown            {result.percent}%  (peak-relative, GLOSSARY.md)")
    if limit is not None and limit_use is not None:
        verdict = "BREACHED" if result.breaches(limit) else "within"
        print(f"k.drawdown_pause    {verdict} - limit {limit}% ({limit_use.provenance})")
        # Not "reporting only", which this printed until 2026-09-26: since `DR-034` a breach halts
        # every submission. What stays the owner's is the other half of the action.
        print("                    a breach PAUSES new entries at submission (DR-034); reducing "
              "size per risk.risk_off_ladder is the owner's, and it is unset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
