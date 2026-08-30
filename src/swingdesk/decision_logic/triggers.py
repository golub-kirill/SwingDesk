"""The entry trigger, in the one layer both the live path and the backtest may import.

**Why it lives here and not in the engine that uses it.** `REQ-VALIDATION-002` and master TZ section
8 forbid backtest and live from holding two independently written versions of one strategy, and
`REQUIREMENTS.md` section 3 records that the window in which that is cheap to prevent is open only
until the live path acquires a trigger.

**It was worse than a risk: the layer contract made the duplication mandatory.** `pyproject.toml`'s
layered contract orders `validation` ABOVE `application`, so `application/pipeline.py` cannot import
`validation.backtest.engine` at all - gate 6 would refuse it. With the trigger living there, the
live path's only legal options were to write a second implementation or to break the contract. That
is TradAlert's failure with a gate enforcing it: two paths, one strategy, and a measured edge
describing a program that could not have taken the trade.

`decision_logic` sits below both, which makes it the one home both may call. It is also where an
entry rule belongs by name.

**Moved unchanged, 2026-08-30.** Same comparisons, same windows, same `None` on a short window, so
every study pinned to one of these replays byte for byte. `validation.backtest.engine` re-exports
them, so no call site moved and there is still exactly one definition.

**Nothing here fetches a fact** - the contract that forbids `decision_logic` from importing
`market_data` is why a trigger takes a `BarSeries` it is handed rather than reading one.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from swingdesk.contracts.market import BarSeries


def breakout_high(series: BarSeries, index: int, lookback: int) -> Decimal | None:
    """Highest high of the `lookback` sessions BEFORE `index`.

    Excludes the current bar deliberately: a breakout compared against a window that includes the
    breaking bar can never fire, and one that includes it in the maximum is comparing a value to
    itself.
    """
    if index < lookback:
        return None
    return max(bar.high for bar in series.bars[index - lookback: index])


def lowest_low(series: BarSeries, index: int, lookback: int) -> Decimal | None:
    """Lowest low of the `lookback` sessions BEFORE `index`. The mirror of `breakout_high`.

    Excludes the current bar for the same reason and returns `None` on the same short window, so
    the two windows are the same window read two ways rather than two nearly-identical rules that
    could drift apart.
    """
    if index < lookback:
        return None
    return min(bar.low for bar in series.bars[index - lookback: index])


class EntryTrigger(Protocol):
    """Whether the entry condition fired at `index` - or that it could not be answered.

    **Three states, and the third is the one that makes this a protocol worth having.** `True` and
    `False` are a fired and an unfired signal; `None` is *the rule had nothing to answer with*,
    which every trigger with a lookback window returns for its first bars. `run_arm` counts those
    bars separately as `unevaluable_bars` rather than folding them into "did not trigger", because
    collapsing them removes bars from the denominator without saying so - the `UNKNOWN`-becomes-
    `FALSE` collapse `RULE_SPEC.md` section 4 forbids.

    A trigger reads `series.bars[:index + 1]` and nothing beyond it. The engine cannot enforce that
    - it hands over the whole series - so it is a contract a trigger keeps, and the reason every
    implementation here takes `index` rather than a pre-sliced window is that slicing per bar over
    26,000 trades costs more than the rule does.

    Triggers are dataclasses rather than closures so a study can RECORD what it ran: a `repr` naming
    the family and its parameters goes into the result, and a closure's does not.
    """

    def __call__(self, series: BarSeries, index: int) -> bool | None: ...


@dataclass(frozen=True, slots=True)
class BreakoutHigh:
    """Close above the highest high of the prior `lookback` sessions.

    **The family `PR-005` tested and refuted**, and until 2026-08-24 it was the only family this
    engine could express - `run_arm` called `breakout_high` directly and the `gate` argument was a
    per-bar filter over that call rather than the trigger itself. Extracted unchanged: the same
    comparison, the same window, the same `None` on a short window, so a study pinned to this
    trigger replays byte for byte.
    """

    lookback: int = 20

    def __call__(self, series: BarSeries, index: int) -> bool | None:
        threshold = breakout_high(series, index, self.lookback)
        if threshold is None:
            return None
        return series.bars[index].close > threshold


@dataclass(frozen=True, slots=True)
class CloseBelowLow:
    """Close below the lowest low of the prior `lookback` sessions. Long side, buying weakness.

    **This is not a proposed strategy and it has no pre-registration.** It exists so the injection
    point above has a second family running through it end to end, which is what makes
    `EntryTrigger` a seam rather than a rename. `AGENTS.md` section 8 governs proposing a rule, and
    nothing here proposes one: no card declares it, no study registers it, and running it as
    research needs both.

    Structurally the mirror of `BreakoutHigh` and deliberately so - same window, same `None` on a
    short one, opposite comparison - because a second family that shared no machinery would prove
    the seam works for a rule shaped exactly like the first.
    """

    lookback: int = 20

    def __call__(self, series: BarSeries, index: int) -> bool | None:
        floor = lowest_low(series, index, self.lookback)
        if floor is None:
            return None
        return series.bars[index].close < floor


@dataclass(frozen=True, slots=True)
class AlwaysEligible:
    """Every bar past `warmup` is a candidate. The trigger a CROSS-SECTIONAL family needs.

    **This is not "no trigger", it is a different shape of family.** A time-series rule asks *is this
    one ready yet*; a cross-sectional rule asks *which of these*, and the selection happens in the
    RANKING and the capacity cap rather than at a price level. `CARD-001` §1 says exactly that, and
    without this the only way to express it would be a trigger that lies about being a filter.

    `warmup` still returns `None` rather than `False`, because a name whose ranking score cannot be
    computed yet has nothing to answer with - the same distinction `run_arm` counts as
    `unevaluable_bars`. Set it to the ranking's lookback: a candidate the ranking would score
    `UNSCORED` is one this should never have offered.
    """

    warmup: int

    def __call__(self, series: BarSeries, index: int) -> bool | None:  # noqa: ARG002 - protocol
        # `series` is unused and must stay in the signature: EntryTrigger is a protocol and a
        # narrower one here would make this the only trigger a caller has to special-case.
        if index < self.warmup:
            return None
        return True
