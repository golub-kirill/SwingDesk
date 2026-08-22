"""Yahoo bar adapter (ADR-0001).

The primary bar source: the only free source verified to cover Canada and provide intraday. It is
also an unofficial scrape of a consumer site, so its output is treated as untrusted input - shapes
and ranges are validated at the boundary rather than assumed (SECURITY 6).

Fetching is fail-open: a failure returns nothing and the caller raises DATA. Deciding is
fail-closed. Those are different layers and conflating them is how "fail-open everywhere" quietly
becomes "traded on stale data".
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import SupportsFloat

from swingdesk.contracts.market import (
    Bar,
    BarSeries,
    CorporateAction,
    CorporateActionKind,
    Interval,
    Series,
)
from swingdesk.contracts.reference import Instrument

#: What Yahoo will serve, measured 2026-08-01 (ADR-0001). Requesting more silently returns less,
#: so the ceiling is stated here rather than discovered.
MAX_LOOKBACK_DAYS: dict[Interval, int | None] = {
    Interval.DAY: None,      # full history: AAPL to 1980-12-12, CNQ.TO to 1995-01-12
    Interval.HOUR: 730,      # ~725 trading days
    Interval.HALF_HOUR: 60,  # 60 trading days; Yahoo's own error states the limit
}

_INTERVAL_ARG = {Interval.DAY: "1d", Interval.HOUR: "1h", Interval.HALF_HOUR: "30m"}


class VendorUnavailable(Exception):
    """The vendor could not be reached, or returned nothing usable.

    Fail-open at this layer: the caller degrades to the last valid snapshot and refuses to decide
    (FAIL_CLOSED_POLICY row 1).
    """


def fetch(
    instrument: Instrument,
    interval: Interval,
    knowledge_time: datetime,
    period: str | None = None,
) -> BarSeries:
    """Fetch bars for one instrument.

    `knowledge_time` is supplied by the caller rather than read from the clock, so a fetch is
    reproducible in a test and the store records when we *say* we learned this.
    """
    import yfinance as yf

    if period is None:
        ceiling = MAX_LOOKBACK_DAYS[interval]
        period = "max" if ceiling is None else f"{ceiling}d"

    try:
        frame = yf.Ticker(instrument.vendor_symbol).history(
            period=period, interval=_INTERVAL_ARG[interval], auto_adjust=False
        )
    except Exception as error:
        raise VendorUnavailable(f"{instrument.vendor_symbol} {interval.value}: {error}") from error

    if frame is None or frame.empty:
        raise VendorUnavailable(f"{instrument.vendor_symbol} {interval.value}: no data returned")

    # The session a bar belongs to is computed HERE, while the timestamp is still in the
    # exchange's own timezone. yfinance returns a tz-aware index in exchange-local time; once the
    # value is stored and read back it may come out in any timezone, and its .date() would then be
    # wrong (CALENDAR_SPEC 6).
    bars: list[Bar] = []
    for stamp, row in frame.iterrows():
        local = stamp.to_pydatetime()
        session_date = local.date()
        event_time = local if local.tzinfo is not None else local.replace(tzinfo=UTC)
        try:
            bar = Bar(
                instrument_id=instrument.id,
                interval=interval,
                series=Series.RAW,
                event_time=event_time,
                session_date=session_date,
                open=_decimal(row["Open"]),
                high=_decimal(row["High"]),
                low=_decimal(row["Low"]),
                close=_decimal(row["Close"]),
                volume=int(row["Volume"]),
                knowledge_time=knowledge_time,
            )
        except (ValueError, InvalidOperation, TypeError):
            # A malformed row is dropped and the session then fails the completeness check, which
            # is the correct place for it to surface - as a coded DATA finding, not an exception
            # three layers up.
            continue
        bars.append(bar)

    if not bars:
        raise VendorUnavailable(
            f"{instrument.vendor_symbol} {interval.value}: no usable rows after validation"
        )

    return BarSeries(
        instrument_id=instrument.id,
        interval=interval,
        series=Series.RAW,
        knowledge_time=knowledge_time,
        bars=tuple(bars),
    )


def _decimal(value: SupportsFloat) -> Decimal:
    """Vendor floats to Decimal, quantised.

    Prices arrive as float64. Converting the repr rather than the float avoids carrying binary
    noise into a Decimal that is then compared for revisions.
    """
    return Decimal(repr(float(value))).quantize(Decimal("0.000001"))


def fetch_actions(
    instrument: Instrument,
    knowledge_time: datetime,
    period: str = "max",
) -> tuple[CorporateAction, ...]:
    """Splits and cash dividends for one instrument, oldest first.

    The precondition `DR-016` names. `POINT_IN_TIME_SPEC` §4 calls actions the third series and
    nothing implemented it, so the corporate-actions gate that `DATA_QUALITY_SPEC` §4 specifies in
    full had no input to run on - the same "specified, wired to nothing" shape as the staleness gate
    one door over.

    Separate from `fetch` rather than folded into it, and this is a boundary rather than a
    preference: `fetch` returns a `BarSeries` and an action is not a bar. yfinance also serves these
    from a different endpoint, so a caller that wants bars should not pay for actions it will not
    read.

    **A zero or negative ratio is dropped, not stored.** The same rule the bar path uses for a
    malformed row: this is a scrape of a consumer site and its output is untrusted input
    (SECURITY 6). A split ratio of 0 would make `price_factor` divide by zero at exactly the moment
    someone is comparing a held stop against a new price level.
    """
    import yfinance as yf

    try:
        ticker = yf.Ticker(instrument.vendor_symbol)
        splits = ticker.get_splits(period=period)
        dividends = ticker.get_dividends(period=period)
    except Exception as error:
        raise VendorUnavailable(f"{instrument.vendor_symbol} actions: {error}") from error

    actions: list[CorporateAction] = []
    for kind, series in (
        (CorporateActionKind.SPLIT, splits),
        (CorporateActionKind.DIVIDEND, dividends),
    ):
        if series is None:
            continue
        for stamp, raw in series.items():
            local = stamp.to_pydatetime()
            try:
                value = _decimal(raw)
            except (ValueError, InvalidOperation, TypeError):
                continue
            if value <= 0:
                continue
            actions.append(
                CorporateAction(
                    instrument_id=instrument.id,
                    kind=kind,
                    # Exchange-local, computed here while the timestamp still carries the
                    # exchange's own timezone - the same rule and the same reason as a bar's
                    # session_date (CALENDAR_SPEC 6).
                    effective_date=local.date(),
                    value=value,
                    knowledge_time=knowledge_time,
                )
            )

    return tuple(sorted(actions, key=lambda a: (a.effective_date, a.kind.value)))
