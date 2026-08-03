"""Universe construction: which instruments are eligible, decided by a rule rather than a list.

Owner decision (2026-08-01): "A-tier" is a **liquidity rule computed from our own bars**, not index
membership. That was chosen because no free source serves index constituents point-in-time, and
using today's membership to filter yesterday's data stacks a second survivorship bias on top of the
delisting one this project already cannot escape (`DATA_QUALITY_SPEC.md`).

Two stages, deliberately separate:

  1. **eligibility** - static facts from a symbol directory: is it a test issue, is it an ETF, what
     venue lists it. Cheap, no bars needed, no look-ahead possible.
  2. **liquidity** - computed from bars, as-of a date. This is where point-in-time correctness
     matters, because dollar volume changes and yesterday's universe is not today's.

Parsing is pure: it takes the directory text, not a URL. Fetching lives in a tool, so nothing in the
layer graph reaches the network to answer a question about eligibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from swingdesk.contracts.market import BarSeries
from swingdesk.contracts.reference import Exchange, Instrument

#: Venue codes in the NASDAQ Trader `otherlisted.txt` file, mapped to the session calendar that
#: governs them. NASDAQ and NYSE were MEASURED identical over 2016-2026: 2523 sessions each, no
#: one-sided session, and no differing open or close time. So the calendar is shared and the listing
#: venue is recorded separately rather than being flattened into it.
US_VENUE_CALENDAR = {
    "A": Exchange.NYSE,   # NYSE American
    "N": Exchange.NYSE,   # NYSE
    "P": Exchange.NYSE,   # NYSE Arca
    "Q": Exchange.NYSE,   # NASDAQ
    "Z": Exchange.NYSE,   # Cboe BZX
    "V": Exchange.NYSE,   # IEX
}

VENUE_NAME = {
    "A": "NYSE American", "N": "NYSE", "P": "NYSE Arca",
    "Q": "NASDAQ", "Z": "Cboe BZX", "V": "IEX",
}


@dataclass(frozen=True, slots=True)
class DirectoryEntry:
    """One row of a symbol directory, before any liquidity test."""

    symbol: str
    name: str
    venue: str
    is_etf: bool
    is_test_issue: bool

    @property
    def is_eligible(self) -> bool:
        """Test issues are excluded; ETFs are in scope (CHARTER: equities *and* ETFs)."""
        return not self.is_test_issue and self.venue in US_VENUE_CALENDAR


def parse_nasdaq_listed(text: str) -> tuple[DirectoryEntry, ...]:
    """Parse `nasdaqlisted.txt`: pipe-delimited, with a trailing file-creation line."""
    entries: list[DirectoryEntry] = []
    for line in text.splitlines()[1:]:
        parts = line.split("|")
        if len(parts) < 8 or parts[0].startswith("File Creation Time"):
            continue
        entries.append(
            DirectoryEntry(
                symbol=parts[0].strip(),
                name=parts[1].strip(),
                venue="Q",
                is_etf=parts[6].strip() == "Y",
                is_test_issue=parts[3].strip() == "Y",
            )
        )
    return tuple(entries)


def parse_other_listed(text: str) -> tuple[DirectoryEntry, ...]:
    """Parse `otherlisted.txt`: NYSE, NYSE American, Arca, Cboe, IEX.

    Uses the ACT symbol rather than the NASDAQ symbol - it is the one that matches the vendor's
    ticker for these venues, and picking the wrong column silently produces a universe of symbols
    that fetch empty.
    """
    entries: list[DirectoryEntry] = []
    for line in text.splitlines()[1:]:
        parts = line.split("|")
        if len(parts) < 8 or parts[0].startswith("File Creation Time"):
            continue
        entries.append(
            DirectoryEntry(
                symbol=parts[0].strip(),
                name=parts[1].strip(),
                venue=parts[2].strip(),
                is_etf=parts[4].strip() == "Y",
                is_test_issue=parts[6].strip() == "Y",
            )
        )
    return tuple(entries)


def to_instrument(entry: DirectoryEntry) -> Instrument:
    """A directory row as an Instrument. Identity is the symbol *plus* the venue's market.

    Tickers get reused after a delisting and we cannot detect reuse from price continuity, because
    no free source serves delisted history. The id is a label we control, not a fact we inferred.
    """
    return Instrument(
        id=entry.symbol,
        ticker=entry.symbol,
        exchange=US_VENUE_CALENDAR[entry.venue],
        currency="USD",
        listing_venue=VENUE_NAME.get(entry.venue, entry.venue),
    )


# ------------------------------------------------------------------ liquidity

def average_dollar_volume(series: BarSeries, window: int, as_of_index: int | None = None) -> Decimal | None:
    """Mean close x volume over the last `window` bars ending at `as_of_index`.

    Returns None when the window is not full. A partial window understates or overstates liquidity
    depending on where it lands, and a universe rule that silently accepts a 3-bar average admits
    instruments that have barely traded (ALGORITHM_SPEC 3).
    """
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")

    end = len(series.bars) - 1 if as_of_index is None else as_of_index
    if end < 0 or end >= len(series.bars) or end + 1 < window:
        return None

    total = Decimal(0)
    for bar in series.bars[end - window + 1: end + 1]:
        total += bar.close * bar.volume
    return total / window


@dataclass(frozen=True, slots=True)
class LiquidityRule:
    """The A-tier membership test, as of a date.

    Both thresholds are `unset` in the registry until DR-003 sets them. This record takes them as
    values rather than reading the registry, so a study can pin the rule it ran under into its own
    evidence record instead of inheriting whatever the registry says later.
    """

    min_price: Decimal
    min_adtv: Decimal
    adtv_window: int
    min_history: int

    def admits(self, series: BarSeries, as_of_index: int | None = None) -> bool:
        end = len(series.bars) - 1 if as_of_index is None else as_of_index
        if end + 1 < self.min_history:
            return False
        adtv = average_dollar_volume(series, self.adtv_window, end)
        if adtv is None:
            return False
        return series.bars[end].close >= self.min_price and adtv >= self.min_adtv


def members(
    rule: LiquidityRule,
    series_by_instrument: dict[str, BarSeries],
    as_of: date | None = None,
) -> tuple[str, ...]:
    """Instrument ids admitted by the rule, sorted.

    Sorted because an unordered collection feeding output is the most common source of silent
    non-determinism (DETERMINISM_SPEC 3.2), and universe membership feeds everything downstream.
    """
    admitted: list[str] = []
    for instrument_id, series in series_by_instrument.items():
        index = None
        if as_of is not None:
            eligible = [i for i, bar in enumerate(series.bars) if bar.session_date <= as_of]
            if not eligible:
                continue
            index = eligible[-1]
        if rule.admits(series, index):
            admitted.append(instrument_id)
    return tuple(sorted(admitted))
