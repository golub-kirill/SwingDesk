"""Shared fixtures. Offline by construction - no test may reach the network (CI_POLICY 4).

The bar fixture deliberately contains the three pathologies measured in the real data: a US
half-day, a session where one exchange is closed and the other is not, and a truncated session
standing in for a confirmed vendor gap. Those are the cases that break things, so they belong in
the fixture rather than in a known-issues list (TEST_STRATEGY 4).
"""

from __future__ import annotations

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
        "risk.per_trade_pct": "1.0",
        "risk.costs_allowance": "0.02",
        "risk.max_position_value": 1_000_000,
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


def fixture_fetcher(sessions_by_instrument: dict[str, list[date]]):
    """A fetcher that serves recorded sessions instead of calling a vendor."""

    def _fetch(instrument, interval, knowledge_time, period=None):
        sessions = sessions_by_instrument.get(instrument.id, [])
        if not sessions:
            from swingdesk.market_data import VendorUnavailable

            raise VendorUnavailable(f"no fixture for {instrument.id}")
        return series_for(instrument, sessions)

    return _fetch
