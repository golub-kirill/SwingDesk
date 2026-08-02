"""The trend filter: does this instrument qualify as being in an uptrend, on this bar.

Course grounding: M33-T0485 `Фильтр по тренду`, Operational Course Rule, layer **Decision Logic**.
The course places it here and not in Derived Observations, which is the right split - measuring the
structure is an observation, *selecting on it* is a decision.

The course supplies no definition. `screen.trend_definition` is `unset` and PR-001 is the registered
study that would justify choosing one, so this module implements the five candidates the
pre-registration names and picks none of them. A caller must say which it wants; there is no default,
because a default here would silently become the answer PR-001 exists to find.

Pure: takes observations in, returns a verdict. No I/O, no clock, and no access to market_data -
`decision_logic` may not fetch its own facts (DEPENDENCY_LAW).

Look-ahead: every input is read at the decision bar's index only. `structure` uses confirmed pivots,
which are already dated at their confirmation bar rather than their pivot bar (`pivots` module), so
the guard holds through composition rather than being re-imposed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from swingdesk.contracts.component import ComponentSpec
from swingdesk.contracts.observation import ObservationSeries
from swingdesk.derived_observations.pivots import Pivot

class UnsetThreshold(Exception):
    """A definition asked for a threshold nobody has set.

    A coded refusal rather than a substituted default: the component declines and names the
    parameter (PARAMETER_REGISTRY 4, USER_STORIES US-020).
    """


#: `Untested`, not `Not Applicable` - and the difference is the point. A calculation the course
#: treats as a definition (SMA, ATR) is not subject to validation; a rule that SELECTS instruments
#: is, and the course marks it so. PR-001 is the study that would move it.
TREND_FILTER = ComponentSpec(
    component="M33-T0485-v5.0", name="Trend filter", version=1,
    validation="Untested", units="boolean", layer="Decision Logic",
)


class TrendDefinition(StrEnum):
    """The five candidates registered in PR-001. Four are course-sourced; one is not.

    `ADX_DI` appears nowhere in the course as a rule - only as a chart-panel label on Module 30
    figures - so it is an authored candidate and PR-001's amendment of 2026-08-02 records it as
    such. It stays in the study because it is the only candidate not built from moving averages,
    which makes it the most informative comparison; if it wins, adopting it is a decision with no
    course backing and that has to be visible when the choice is made.
    """

    ABOVE_LONG_MA = "A"      # close > SMA(long)
    MA_STACK = "B"           # SMA(short) > SMA(long)
    PRICE_AND_STACK = "C"    # close > SMA(short) > SMA(long)
    STRUCTURE = "D"          # higher highs and higher lows over the last N confirmed pivots
    ADX_DI = "E"             # authored: ADX above a threshold with +DI > -DI


@dataclass(frozen=True, slots=True)
class TrendInputs:
    """Everything the five definitions can read, at one bar.

    A single record rather than five signatures, so adding a definition cannot quietly widen what
    the filter is allowed to see. `None` means the input was not computed or has not warmed up, and
    every definition treats that as "cannot answer" rather than as "no".
    """

    close: Decimal | None = None
    sma_short: Decimal | None = None
    sma_long: Decimal | None = None
    swing_highs: tuple[Decimal, ...] = ()
    swing_lows: tuple[Decimal, ...] = ()
    adx: Decimal | None = None
    plus_di: Decimal | None = None
    minus_di: Decimal | None = None


def is_uptrend(definition: TrendDefinition, inputs: TrendInputs, *, pivot_count: int = 2) -> bool | None:
    """True, False, or None when the inputs cannot answer.

    Three-valued deliberately. Collapsing "not warmed up" into False would make an instrument look
    like it failed the filter when it was never tested, and the difference matters for PR-001: a
    definition that answers on fewer bars selects a smaller set for a reason that has nothing to do
    with trend.
    """
    match definition:
        case TrendDefinition.ABOVE_LONG_MA:
            if inputs.close is None or inputs.sma_long is None:
                return None
            return inputs.close > inputs.sma_long

        case TrendDefinition.MA_STACK:
            if inputs.sma_short is None or inputs.sma_long is None:
                return None
            return inputs.sma_short > inputs.sma_long

        case TrendDefinition.PRICE_AND_STACK:
            if inputs.close is None or inputs.sma_short is None or inputs.sma_long is None:
                return None
            return inputs.close > inputs.sma_short > inputs.sma_long

        case TrendDefinition.STRUCTURE:
            if len(inputs.swing_highs) < pivot_count or len(inputs.swing_lows) < pivot_count:
                return None
            highs = inputs.swing_highs[-pivot_count:]
            lows = inputs.swing_lows[-pivot_count:]
            rising_highs = all(b > a for a, b in zip(highs, highs[1:]))
            rising_lows = all(b > a for a, b in zip(lows, lows[1:]))
            return rising_highs and rising_lows

        case TrendDefinition.ADX_DI:
            if inputs.adx is None or inputs.plus_di is None or inputs.minus_di is None:
                return None
            # Threshold is a parameter, and regime.adx_threshold is unset. Rather than invent one,
            # this definition answers only the directional half it can answer without a threshold,
            # and PR-001 must set the threshold before running it (see below).
            raise UnsetThreshold(
                "TrendDefinition.ADX_DI needs regime.adx_threshold, which is unset. The parameter "
                "carries a WEAK CITATION - ADX appears in the course only as a chart-panel label - "
                "so setting it is a decision record, not a transcription."
            )

    raise ValueError(f"unhandled trend definition {definition!r}")


def inputs_from_series(
    index: int,
    close: Decimal,
    sma_short: ObservationSeries | None = None,
    sma_long: ObservationSeries | None = None,
    highs: tuple[Pivot, ...] = (),
    lows: tuple[Pivot, ...] = (),
) -> TrendInputs:
    """Assemble one bar's inputs, reading nothing dated after `index`.

    The pivot filter is the load-bearing line: `confirmed_index <= index`, never `index <= index`.
    A pivot that happened before this bar but was confirmed after it is not knowable here.
    """
    return TrendInputs(
        close=close,
        sma_short=sma_short.observations[index].value if sma_short is not None else None,
        sma_long=sma_long.observations[index].value if sma_long is not None else None,
        swing_highs=tuple(p.price for p in highs if p.confirmed_index <= index),
        swing_lows=tuple(p.price for p in lows if p.confirmed_index <= index),
    )
