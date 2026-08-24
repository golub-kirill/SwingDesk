"""The backtest harness: BACKTEST_PROTOCOL's nine stages, executed.

Sits in `validation` because it drives the same components the live path drives and must not become
a second implementation of them. What it adds is the simulation: an entry that happens after the
signal, an exit that follows a rule, and a cost that is charged.

Two properties are structural rather than tested-for:

  - **No look-ahead.** The engine walks bars in order and a decision at index i may read
    `bars[:i+1]` and nothing else. Entry happens at `i+1`'s open. This is enforced by the shape of
    the loop, not by discipline.
  - **Every exit has a reason.** `ExitReason` is an enum, so a position cannot be closed for a
    reason nobody defined, and a run cannot end with positions quietly dropped.
"""

from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.validation.backtest.book import (
    BookResult,
    Candidate,
    Capacity,
    Ranking,
    by_instrument_id,
    run_book,
)
from swingdesk.validation.backtest.costs import CostModel
from swingdesk.validation.backtest.engine import (
    AlwaysEligible,
    ArmResult,
    BacktestConfig,
    BreakoutHigh,
    CloseBelowLow,
    EntryTrigger,
    Skipped,
    run_arm,
)
from swingdesk.validation.backtest.ranking import (
    ByMarketPathStrength,
    ByRawReturn,
    BySectorRelativeStrength,
)

__all__ = [
    "AlwaysEligible",
    "ArmResult",
    "BacktestConfig",
    "BookResult",
    "BreakoutHigh",
    "ByMarketPathStrength",
    "ByRawReturn",
    "BySectorRelativeStrength",
    "Candidate",
    "Capacity",
    "CloseBelowLow",
    "CostModel",
    "EntryTrigger",
    "ExitPolicy",
    "Ranking",
    "Skipped",
    "by_instrument_id",
    "run_arm",
    "run_book",
]
