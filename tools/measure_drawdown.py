"""Report the drawdown `k.drawdown_pause` triggers on, so the criterion can be evaluated at all.

`k.drawdown_pause` is ratified with scope `live` and until 2026-08-30 **nothing computed its input**
- `validation.max_allowable_drawdown` is owner-set at 20 percent and its `read_by` was `none`. This
is what makes the criterion evaluable. `criteria.yml` amendment v1.1.2 fixes what the trigger's word
means: peak-to-trough drawdown of account equity **including open positions marked to market**,
peak-relative, baseline `account.equity`.

**It reports and it does nothing.** The prescribed action names the risk-off ladder,
`risk.risk_off_ladder` is `unset`, and writing it is the owner's. Nothing in the decision path calls
this: a measurable kill switch is not an automatic one, and wiring both in one change would have
moved decision output for a number whose first honest answer is 0.00%.

**Position store only.** Not the journal - the journal holds runs and decisions, and equity is a
fact about positions and fills. Marks come from the bar store, because "marked to market" needs a
price and a position record does not carry one.

Read-only over `data/`.

    python tools/measure_drawdown.py --data C:/PycharmProjects/SwingDesk/data
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.market import Interval, Series
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.market_data import BarStore
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset
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
        positions = positions_store.open_as_of(as_of)

        fills_by_position = {p.position_id: positions_store.fills_for(p.position_id)
                             for p in positions}
        # Resolved fill by fill through `proposal_at`, not by zipping `actions_for` against a range.
        # A fill names the SEQUENCE of the action it settles, and `actions_for` returns actions
        # without their sequence numbers - so position in that list is not the sequence, and
        # assuming it were would attribute a fill to the wrong action the first time a proposal was
        # withdrawn.
        actions_by_position: dict[str, dict[int, str]] = {}
        for position in positions:
            kinds: dict[int, str] = {}
            for fill in fills_by_position[position.position_id]:
                action = positions_store.proposal_at(position.position_id, fill.sequence)
                if action is not None:
                    kinds[fill.sequence] = str(action.kind)
            actions_by_position[position.position_id] = kinds
        sessions = sorted({
            session
            for p in positions
            for session in _sessions_for(bars, p.instrument_id, as_of)
        })

        def mark_for(instrument_id: str, session: object) -> Decimal | None:
            series = bars.as_of(instrument_id, Interval.DAY, Series.RAW, as_of)
            for bar in reversed(series.bars):
                if bar.session_date == session:
                    return bar.close
            return None

        result = measurement.measure(
            positions=positions,
            fills_by_position=fills_by_position,
            actions_by_position=actions_by_position,
            baseline=baseline,
            sessions=sessions,
            mark_for=mark_for,
        )

    print(f"positions open      {len(positions)}")
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
        print("                    reporting only; risk.risk_off_ladder is unset and the "
              "prescribed action is the owner's")
    return 0


def _sessions_for(bars: BarStore, instrument_id: str, as_of: datetime) -> list:
    series = bars.as_of(instrument_id, Interval.DAY, Series.RAW, as_of)
    return [bar.session_date for bar in series.bars]


if __name__ == "__main__":
    raise SystemExit(main())
