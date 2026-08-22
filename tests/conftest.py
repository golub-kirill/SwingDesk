"""Shared fixtures. Offline by construction - no test may reach the network (CI_POLICY 4).

The bar fixture deliberately contains the three pathologies measured in the real data: a US
half-day, a session where one exchange is closed and the other is not, and a truncated session
standing in for a confirmed vendor gap. Those are the cases that break things, so they belong in
the fixture rather than in a known-issues list (TEST_STRATEGY 4).
"""

from __future__ import annotations

import math
import random
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.contracts.reference import Exchange, Instrument
from swingdesk.platform.parameters import ParameterRegistry

#: Synthetic instruments. Never real tickers - a fixture naming a real name invites someone to
#: "fix" it against current market data.
TEST_US = Instrument(id="TEST.1", ticker="TEST1", exchange=Exchange.NYSE, currency="USD")
TEST_CA = Instrument(id="TEST.2.TO", ticker="TEST2", exchange=Exchange.TSX, currency="CAD")

KNOWLEDGE_TIME = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)


@pytest.fixture
def registry() -> ParameterRegistry:
    """A registry with everything the slice needs, so tests never read the real one."""
    values = {
        "atr.period": 14,
        "account.equity": 10000,
        # Sizing reads the account's currency and refuses to size an instrument denominated in
        # another one without a rate (2026-08-16). The slice trades US instruments, so the rate is
        # never reached; the base currency is, on every call.
        "account.base_currency": "USD",
        "risk.per_trade_pct": "1.0",
        "risk.costs_bp_usd": "50",
        "risk.costs_floor_usd": "0.02",
        "risk.costs_bp_cad": "50",
        "risk.costs_floor_cad": "0.02",
        "risk.max_position_value": 1_000_000,
        # The run's exit semantics, and the SAME policy the candidate path sizes against
        # (2026-08-16). Both are UNSET in the real registry, where the pipeline therefore refuses;
        # the fixture sets them so the slice can exercise the working path, and
        # test_pipeline covers the unset case explicitly.
        "exit.atr_stop_multiple": "2.0",
        "exit.max_holding_period": 20,
        # How stale is too stale (DR-015). Set here for the same reason the exit pair is: the slice
        # needs the working path, and `test_pipeline` covers the unset case explicitly.
        #
        # Note what this made visible the moment it was wired. Every fixture in the suite ran a
        # series ending the day BEFORE its as-of, which the gate correctly reads as one session
        # behind - the Monday-against-Friday case DR-015 §2.1 is written about. The fixtures now
        # run through the as-of session, which is what the scheduled 18:30 run actually sees: the
        # session that closed at 16:00 has a bar by then.
        "data.freshness_window": 2,
    }
    return ParameterRegistry(
        {
            key: {"id": key, "value": value, "provenance": "assumed:test fixture",
                  "status": "assumed", "unit": "", "named_in": ["test"]}
            for key, value in values.items()
        }
    )


def make_bars(
    instrument: Instrument,
    sessions: list[date],
    first_close: Decimal = Decimal("100.00"),
) -> tuple[Bar, ...]:
    """Deterministic synthetic bars: one per session, walking upward by a fixed step.

    No randomness anywhere - a fixture that varies between runs cannot support a determinism test.
    """
    bars: list[Bar] = []
    close = first_close
    for offset, session in enumerate(sessions):
        close = first_close + Decimal(offset) * Decimal("0.50")
        bars.append(
            Bar(
                instrument_id=instrument.id,
                interval=Interval.DAY,
                series=Series.RAW,
                event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
                session_date=session,
                open=close - Decimal("0.25"),
                high=close + Decimal("1.00"),
                low=close - Decimal("1.00"),
                close=close,
                volume=1_000_000 + offset,
                knowledge_time=KNOWLEDGE_TIME,
            )
        )
    return tuple(bars)


def series_for(instrument: Instrument, sessions: list[date]) -> BarSeries:
    return BarSeries(
        instrument_id=instrument.id,
        interval=Interval.DAY,
        series=Series.RAW,
        knowledge_time=KNOWLEDGE_TIME,
        bars=make_bars(instrument, sessions),
    )


#: Intraday steps per session in `synthetic_ohlc`. The spread estimators assume a continuously
#: observed diffusion, so a coarse path under-samples the one-day range more than the two-day range
#: and biases them. At 1,000 the artefact is small. Real sessions carry far more prints.
INTRADAY_STEPS = 1000
DAILY_VOLATILITY = 0.02


def synthetic_ohlc(
    days: int,
    proportional_spread: float,
    seed: int = 20260809,
    steps: int = INTRADAY_STEPS,
) -> tuple[list[float], list[float], list[float]]:
    """Daily bars carrying a KNOWN bid-ask spread, as (highs, lows, closes).

    An efficient price walks intraday; the observed high and low are the true extremes widened by
    the half-spread; the close lands on the bid or the ask. That is the microstructure the spread
    estimators model, and this generator is deliberately not written in terms of any of their
    formulas - so an estimator recovering `proportional_spread` is evidence rather than circularity.

    `proportional_spread=0.0` produces a market with no spread at all.

    **One draw from this generator is not a property.** On a spreadless series Abdi-Ranaldo clamps to
    zero about half the time and scatters up to ~0.004 the rest of the time, so a single seed can be
    quoted to support almost anything - which is exactly the error PR-008's report and DR-005's test
    each made, independently, on the same estimator. Every assertion built on this generator sweeps
    seeds and asserts on the distribution.

    Seeded, so it supports a determinism test.
    """
    rng = random.Random(seed)
    half = proportional_spread / 2
    step_volatility = DAILY_VOLATILITY / math.sqrt(steps)

    price = 100.0
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []

    for _ in range(days):
        high = low = price
        for _ in range(steps):
            price *= math.exp(rng.gauss(0.0, step_volatility))
            high = max(high, price)
            low = min(low, price)
        highs.append(high * (1 + half))
        lows.append(low * (1 - half))
        closes.append(price * (1 + half if rng.random() < 0.5 else 1 - half))

    return highs, lows, closes


def fixture_fetcher(sessions_by_instrument: dict[str, list[date]]):
    """A fetcher that serves recorded sessions instead of calling a vendor."""

    def _fetch(instrument, interval, knowledge_time, period=None):
        sessions = sessions_by_instrument.get(instrument.id, [])
        if not sessions:
            from swingdesk.market_data import VendorUnavailable

            raise VendorUnavailable(f"no fixture for {instrument.id}")
        return series_for(instrument, sessions)

    return _fetch


def synthetic_ohlcv(
    days: int,
    proportional_spread: float,
    seed: int = 20260809,
    steps: int = INTRADAY_STEPS,
) -> tuple[list[float], list[float], list[float], list[float]]:
    """As `synthetic_ohlc`, but emitting a genuine OPEN as well: (opens, highs, lows, closes).

    EDGE reads the open, and it is the one field the 2012 and 2017 estimators ignore. That makes a
    faked open silently fatal rather than merely inaccurate: setting it to the previous close makes
    `o - c1` identically zero, which zeroes one of EDGE's two estimating equations and returns a
    spread of zero for every input. That is what happened on the first attempt here, and it looked
    exactly like a broken estimator rather than a broken fixture.

    So the open is what it is in a real session: the first trade of the day, at the bid or the ask,
    on an efficient price that has moved overnight.
    """
    rng = random.Random(seed)
    half = proportional_spread / 2
    step_volatility = DAILY_VOLATILITY / math.sqrt(steps)

    price = 100.0
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []

    def on_a_side(efficient: float) -> float:
        return efficient * (1 + half if rng.random() < 0.5 else 1 - half)

    for _ in range(days):
        price *= math.exp(rng.gauss(0.0, step_volatility * math.sqrt(steps) / 3))  # overnight
        opens.append(on_a_side(price))
        high = low = price
        for _ in range(steps):
            price *= math.exp(rng.gauss(0.0, step_volatility))
            high = max(high, price)
            low = min(low, price)
        highs.append(high * (1 + half))
        lows.append(low * (1 - half))
        closes.append(on_a_side(price))

    return opens, highs, lows, closes
