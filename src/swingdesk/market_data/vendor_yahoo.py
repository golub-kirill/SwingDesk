"""Yahoo bar adapter (ADR-0001).

The primary bar source: the only free source verified to cover Canada and provide intraday. It is
also an unofficial scrape of a consumer site, so its output is treated as untrusted input - shapes
and ranges are validated at the boundary rather than assumed (SECURITY 6).

Fetching is fail-open: a failure returns nothing and the caller raises DATA. Deciding is
fail-closed. Those are different layers and conflating them is how "fail-open everywhere" quietly
becomes "traded on stale data".
"""

from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from functools import cache
from typing import SupportsFloat

from swingdesk.contracts.market import (
    Bar,
    BarSeries,
    CorporateAction,
    CorporateActionKind,
    Interval,
    Series,
)
from swingdesk.contracts.reference import Classification, Instrument, SectorWeight
from swingdesk.market_data import policy as vendor_policy
from swingdesk.market_data.policy import VendorPolicy
from swingdesk.reference_data.classification import FUND_KINDS


@cache
def policy() -> VendorPolicy:
    """The committed vendor policy, read once per process.

    **Cached because `fetch` is called once per universe member** - 1,142 times in an evening pass,
    and re-parsing the same YAML that often is work nobody asked for. `cache_clear()` is the seam a
    test uses to point this at a different file; nothing in `src/` calls it.
    """
    return vendor_policy.load()


def max_lookback_days(interval: Interval) -> int | None:
    """What the vendor will serve for this interval, or `None` for as far back as it holds.

    **Read from `registry/vendor_policy.yml`, not from a literal here** - `DR-008`'s argument
    applied to the dependency this project asks the most of. Requesting more than the ceiling
    silently returns less, which is why it is stated rather than discovered: a request for five
    years of half-hourly bars comes back as sixty days and looks like a short history rather than
    like a refusal.
    """
    current = policy()
    return {
        Interval.DAY: current.day_max_lookback_days,
        Interval.HOUR: current.hour_max_lookback_days,
        Interval.HALF_HOUR: current.half_hour_max_lookback_days,
    }[interval]

_INTERVAL_ARG = {Interval.DAY: "1d", Interval.HOUR: "1h", Interval.HALF_HOUR: "30m"}

#: A refusal that ARITHMETIC forbids, as opposed to one the vendor will fix by tomorrow.
#:
#: `contracts.market.Bar` raises `open <price> outside [<low>, <high>]` when a session's opening
#: trade sits beyond the range of the session that contains it. That cannot happen in real market
#: data at any publication time, which is exactly what separates it from a `close` that is still
#: `NaN` because the vendor's end-of-day process has not run.
#:
#: Matched on the message rather than on an exception type because the two arrive as the SAME type
#: - pydantic raises `ValidationError` for both - and a check on the type would put every refusal
#: in one bucket, which is the defect this exists to end.
_IMPOSSIBLE = re.compile(r"outside \[")


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
        ceiling = max_lookback_days(interval)
        period = "max" if ceiling is None else f"{ceiling}d"

    try:
        frame = yf.Ticker(instrument.vendor_symbol).history(
            period=period, interval=_INTERVAL_ARG[interval],
            # From the committed policy, never a literal: this system stores RAW bars and
            # applies its own corporate-action handling (`DR-016`). An adjusted series would
            # rewrite history under a bitemporal store, which it cannot recover from - so the
            # value sits where a change to it is a commit a reviewer sees.
            auto_adjust=policy().auto_adjust,
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
    dropped: list[str] = []
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
        except (ValueError, InvalidOperation, TypeError) as invalid:
            # A malformed row is dropped rather than raised three layers up - but it is NAMED.
            #
            # This comment used to say the session "then fails the completeness check, which is the
            # correct place for it to surface". That was false, and `DR-015` §2.2 had already
            # recorded why: completeness looks for a hole INSIDE the stored window, and a series
            # whose newest row was dropped simply ends early, which is not a hole. So the drop was
            # invisible - the report said `completeness clean` over a series one bar short.
            #
            # Reported on stderr because that is where the rest of a scheduled run's vendor facts
            # go: `daily_run.cmd` redirects it into `data/daily_run.log`. Naming the field costs a
            # line and is the difference between "the vendor is late" and "the vendor sent
            # something we refused", which are different problems with different fixes.
            # Collapsed to one line: a pydantic `ValidationError` renders over several, and a log
            # that spends six lines per refused row per instrument is one nobody reads.
            reason = " ".join(str(invalid).split())
            dropped.append(f"{session_date} ({type(invalid).__name__}: {reason[:120]})")

            # AN IMPOSSIBLE BAR IS NOT A LATE ONE, AND ONE LINE PER REFUSAL HID THAT FOR 52 RUNS.
            #
            # Measured 2026-09-04 over the whole of `data/daily_run.log`: 1,120 refusals in one
            # evening, of which 1,113 were the same routine condition - the vendor's own close for
            # the current session, not yet published, arriving as `NaN`. Buried among them was
            # `DFNM`, whose OPEN sat outside its own `[low, high]`. It was found by grouping the
            # lines with an ad-hoc script, which is not a mechanism anybody can rely on running.
            #
            # The two are different problems with different fixes, and the difference is not a
            # severity I invented - it is the shape of the failure. *Not yet published* is a
            # TIMING fact that resolves itself by tomorrow. *Open outside `[low, high]`* is an
            # ARITHMETIC impossibility: the high is the highest price of the session and the open
            # happened inside it, so no vendor timing can produce this and no later fetch repairs
            # it. Verified against the raw feed - `auto_adjust=False`, `back_adjust=False`,
            # `repair=False` - so it is the vendor's own number and not our adjustment rounding.
            #
            # Given its own prefix rather than its own severity, because a prefix is greppable and
            # a severity is a number somebody has to agree on. `tools/vendor_integrity.py` reads
            # these lines and answers "has this happened before" as a tool call rather than a
            # memory - `AGENTS.md` §10.6.
            if _IMPOSSIBLE.search(reason):
                print(
                    f"VENDOR INTEGRITY  {instrument.vendor_symbol} {interval.value} "
                    f"{session_date}  {reason[:120]}",
                    file=sys.stderr,
                )
            continue
        bars.append(bar)

    if dropped:
        # Bounded, because a vendor-wide malformation would otherwise write one line per session per
        # instrument into the evening's log. The count is the fact; the first few carry the reason.
        shown = ", ".join(dropped[:3])
        more = f", and {len(dropped) - 3} more" if len(dropped) > 3 else ""
        print(
            f"vendor row(s) refused  {instrument.vendor_symbol} {interval.value}: "
            f"{len(dropped)} of {len(frame)} rows failed validation - {shown}{more}",
            file=sys.stderr,
        )

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


def fetch_classification(instrument: Instrument, knowledge_time: datetime) -> Classification:
    """What the vendor says this instrument is made of: kind, industry, and sector composition.

    The precondition `DR-006` §8.4 named. `Instrument.sector` has been `None` since the contract was
    written and §3 recorded the sector cap as unevaluable for want of a source; this is the source.
    An ordinary share carries its own sector as a single weight of 1, an equity fund carries its
    look-through, and both come back in the same shape - which is what lets the sector budget add a
    share to an ETF without a special case.

    **Recorded as answered. Judged elsewhere.** This function does not apply `DR-006` §8.7's
    degeneracy guard, and that is deliberate rather than an omission: refusing here would store
    nothing, and "we asked and the answer was unusable" would become indistinguishable from "we
    never asked". `reference_data.classification.look_through` judges it, on the way out of the
    store rather than on the way in.

    What IS enforced here is the boundary this vendor needs, because it is an unofficial scrape of a
    consumer site and its output is untrusted input (`SECURITY` §6): a weight that is not a number,
    is negative, or exceeds 1 is dropped rather than stored. Same rule the bar path uses for a
    malformed row, and the same reason - a bad value surfaces as a coded gap rather than as an
    exception three layers up.
    """
    import yfinance as yf

    ticker = yf.Ticker(instrument.vendor_symbol)
    try:
        info = ticker.info or {}
    except Exception as error:
        raise VendorUnavailable(f"{instrument.vendor_symbol} info: {error}") from error

    quote_type = str(info.get("quoteType") or "").strip()
    if not quote_type:
        # Without the kind there is no way to tell a direct sector from a look-through, and
        # guessing which one an answer is would be the substitution this project refuses by name.
        raise VendorUnavailable(
            f"{instrument.vendor_symbol} info: no quoteType, so a sector cannot be classified"
        )

    weights: list[SectorWeight] = []
    equity_share: Decimal | None = None
    if quote_type.upper() in FUND_KINDS:
        try:
            reported = ticker.funds_data.sector_weightings or {}
        except Exception:  # noqa: BLE001 - a fund with no look-through is a gap, not a failure
            # NOT a VendorUnavailable. The kind is known and the composition is not, which is a
            # classification with no weights - `look_through` reports that as `unavailable` and the
            # candidate is admitted unchecked. Raising here would lose the quoteType as well.
            reported = {}
        for sector, share in reported.items():
            weight = _weight(share)
            if weight is not None:
                weights.append(SectorWeight(sector=str(sector), weight=weight))

        # `DR-021`: the fact the degeneracy guard was inferring, asked for directly. It arrives in
        # the SAME response as the sector weights, which is what made the inference avoidable all
        # along - `AGENTS.md` §12's named trap, a proxy standing in for a measurement that was
        # sitting in the same payload.
        #
        # Its own `except`, not folded into the one above: a vendor that serves sector weights and
        # no asset classes must keep the weights. Sharing a handler would discard both over the
        # half that is optional.
        try:
            classes = ticker.funds_data.asset_classes or {}
            equity_share = _weight(classes.get("stockPosition"))
        except Exception:  # noqa: BLE001 - an unanswered field is a fact, not a failure
            equity_share = None
    else:
        sector = str(info.get("sector") or "").strip()
        if sector:
            weights.append(SectorWeight(sector=sector, weight=Decimal(1)))

    industry = str(info.get("industry") or "").strip() or None
    return Classification(
        instrument_id=instrument.id,
        quote_type=quote_type,
        industry=industry,
        weights=tuple(weights),
        equity_share=equity_share,
        knowledge_time=knowledge_time,
    )


def _weight(value: object) -> Decimal | None:
    """A vendor sector share as a Decimal fraction, or `None` when it is not one.

    Quantised at six places, the same as a price: the vendor serves float64 and converting the repr
    rather than the float keeps binary noise out of a number that is later summed and compared.
    """
    try:
        weight = Decimal(repr(float(value))).quantize(Decimal("0.000001"))  # type: ignore[arg-type]
    except (ValueError, InvalidOperation, TypeError):
        return None
    if weight < 0 or weight > 1:
        return None
    return weight


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
