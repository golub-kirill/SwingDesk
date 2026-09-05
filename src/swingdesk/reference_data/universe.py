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


#: The columns each parser reads, by the position it reads them at.
#:
#: **`DR-008` requires "exact header and row shape" and only the row shape was ever checked.** The
#: header line was `splitlines()[1:]`-ed away without being compared to anything, so a vendor that
#: reordered its columns would have been parsed silently BY POSITION: `parts[6]` would go on being
#: read as `ETF` while holding something else, and the universe would be wrong in a way no gate and
#: no test could see. Row shape refuses a short row; nothing refused a rearranged one.
#:
#: Written as index -> name so the binding is stated where the read happens rather than being an
#: unexplained literal, and so `_require_header` can check exactly the dependency the parser has.
#: Trailing columns the vendor may add later are permitted - `NextShares` was appended once already
#: - because a column nothing reads cannot change an answer.
NASDAQ_COLUMNS = {0: "Symbol", 1: "Security Name", 3: "Test Issue", 6: "ETF"}
OTHER_COLUMNS = {0: "ACT Symbol", 1: "Security Name", 2: "Exchange", 4: "ETF", 6: "Test Issue"}


def _require_header(text: str, columns: dict[int, str], filename: str) -> None:
    """Refuse the whole file unless every column the parser reads is where it expects it.

    Refusing beats warning for the same reason a malformed row does: a misread `ETF` flag is
    indistinguishable from the vendor reclassifying a fund, and this store's whole value is that a
    change in it means something.
    """
    first = text.splitlines()[0] if text.splitlines() else ""
    header = [cell.strip() for cell in first.split("|")]
    wrong = {
        index: (columns[index], header[index] if index < len(header) else "<absent>")
        for index in sorted(columns)
        if index >= len(header) or header[index] != columns[index]
    }
    if wrong:
        detail = ", ".join(
            f"column {index} should be {expected!r} and is {found!r}"
            for index, (expected, found) in sorted(wrong.items())
        )
        raise ValueError(
            f"{filename}: the vendor's header is not the one this parser reads by position - "
            f"{detail}. Refusing the file: parsing it anyway would put the wrong field in every "
            f"row and look exactly like a directory that changed (DR-008, exact header shape)."
        )


def parse_nasdaq_listed(text: str) -> tuple[DirectoryEntry, ...]:
    """Parse `nasdaqlisted.txt`: pipe-delimited, with a trailing file-creation line."""
    _require_header(text, NASDAQ_COLUMNS, "nasdaqlisted.txt")
    entries: list[DirectoryEntry] = []
    malformed = 0
    for line in text.splitlines()[1:]:
        if not line.strip():
            continue  # carries no fields, so it cannot be a symbol row that went missing
        parts = line.split("|")
        if parts[0].startswith("File Creation Time"):
            continue
        if len(parts) < 8:
            malformed += 1
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
    if malformed:
        raise ValueError(
            f"{malformed} malformed row(s) in the directory feed. Refusing the file rather than "
            "skipping them: a dropped row is indistinguishable from a departure, and departures "
            "are this project's only survivorship evidence."
        )
    return tuple(entries)


def parse_other_listed(text: str) -> tuple[DirectoryEntry, ...]:
    """Parse `otherlisted.txt`: NYSE, NYSE American, Arca, Cboe, IEX.

    Uses the ACT symbol rather than the NASDAQ symbol - it is the one that matches the vendor's
    ticker for these venues, and picking the wrong column silently produces a universe of symbols
    that fetch empty. This file is the reason the header check exists: it carries BOTH an
    `ACT Symbol` and a `NASDAQ Symbol` column, so reading the wrong position here is not a
    hypothetical failure mode, it is the one the docstring above already warns about.
    """
    _require_header(text, OTHER_COLUMNS, "otherlisted.txt")
    entries: list[DirectoryEntry] = []
    malformed = 0
    for line in text.splitlines()[1:]:
        if not line.strip():
            continue  # carries no fields, so it cannot be a symbol row that went missing
        parts = line.split("|")
        if parts[0].startswith("File Creation Time"):
            continue
        if len(parts) < 8:
            malformed += 1
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
    if malformed:
        raise ValueError(
            f"{malformed} malformed row(s) in the directory feed. Refusing the file rather than "
            "skipping them: a dropped row is indistinguishable from a departure, and departures "
            "are this project's only survivorship evidence."
        )
    return tuple(entries)


#: Directory suffixes the vendor does not accept in any mapped form. Warrants, units and rights are
#: not what CHARTER scopes ("equities and ETFs"), and `ACHR.W` resolves to neither `ACHR-W` nor
#: `ACHR-WT`. Listed so their absence is a recorded exclusion rather than a fetch failure that looks
#: random.
UNMAPPABLE_SUFFIXES = (".W", ".U", ".R")


def is_mappable(symbol: str) -> bool:
    """Is there a vendor symbol we could even ask for?

    `vendor_symbol` returns an unmappable symbol UNCHANGED, so its RESULT cannot tell a caller
    whether a mapping happened - `ACHR.W` in and `ACHR.W` out looks exactly like a symbol that
    needed no translation. A fetch loop therefore asks the vendor for a form it already knows the
    vendor does not use, and reads back "possibly delisted".

    **Measured 2026-09-05, and the measurement is why this is a suffix test and nothing wider.**
    Of the eligible directory, 133 symbols carry these suffixes and **not one has ever had a bar
    stored**. The obvious generalisation - exclude warrants, units and rights by the vendor's own
    Security Name - was tried against the same data and REFUSED: 938 eligible names say
    warrant/unit/right and **738 of them are already fetched**, including `AB`
    ("AllianceBernstein Holding L.P. Units"). The class is served; this spelling of it is not.
    """
    return not symbol.endswith(UNMAPPABLE_SUFFIXES)


def vendor_symbol(symbol: str) -> str:
    """A NASDAQ Trader symbol in the form the price vendor expects.

    The directory and Yahoo disagree on separators, and the disagreement was silently costing this
    project its most liquid names: `BRK.A` and `BRK.B` were absent from every universe, indexed as
    "possibly delisted". They are not.

        BRK.B  -> BRK-B    class shares: the dot becomes a hyphen
        AMH$G  -> AMH-PG   preferred series: `$` becomes `-P`

    Both verified against the vendor before this function was written, on BRK.A/B, AKO.A, AGM.A,
    LEN.B, BAC$B, AMH$G, F$B and BNY$K. Warrants, units and rights map to nothing and are left
    alone - see UNMAPPABLE_SUFFIXES.
    """
    if "$" in symbol:
        base, _, series = symbol.partition("$")
        return f"{base}-P{series}"
    if symbol.endswith(UNMAPPABLE_SUFFIXES):
        return symbol
    return symbol.replace(".", "-")


def to_instrument(entry: DirectoryEntry) -> Instrument:
    """A directory row as an Instrument. Identity is the symbol *plus* the venue's market.

    Tickers get reused after a delisting and we cannot detect reuse from price continuity, because
    no free source serves delisted history. The id is a label we control, not a fact we inferred.

    `id` stays the DIRECTORY symbol and `ticker` carries the vendor's form. Keeping them separate
    means a vendor changing its separator convention does not rewrite the identity of every stored
    bar - which is exactly the kind of silent re-keying a bitemporal store cannot recover from.
    """
    return Instrument(
        id=entry.symbol,
        ticker=vendor_symbol(entry.symbol),
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
    adtv_lag: int
    """Sessions between the run and the END of the ADTV window (`universe.adtv_lag_sessions`).

    `DR-017`, ratified 2026-08-30. Vendor volume is still being written for two sessions after the
    bar: of 5,980 revisions over the daily-run era, none landed on a bar three or more sessions old.
    A window that stops three sessions back therefore averages only settled bars, which is what
    makes admission IDEMPOTENT - a replayed screen returns what the live screen returned.

    **No default, deliberately.** 0 would silently give a caller that has not heard of the lag the
    old, non-reproducible universe; 3 would silently re-write what an already-reported study ran
    under. `DR-017` §3 forbids two universes, and the way to have one is to make every caller say
    which it means rather than inherit a guess. Studies that predate the lag pin 0 - that is the
    rule they ran under, and pinning it is what this record is for.
    """

    def __post_init__(self) -> None:
        # A negative lag ends the window AFTER the run - lookahead, and the one direction that would
        # be invisible in the output because it makes the screen look better rather than worse.
        if self.adtv_lag < 0:
            raise ValueError(f"adtv_lag must be >= 0, got {self.adtv_lag}")

    def admits(
        self, series: BarSeries, as_of_index: int | None = None, *, history: int | None = None
    ) -> bool:
        """Whether the rule admits `series`, judged at `as_of_index` (default: its last bar).

        `history` overrides the bar count the `min_history` test reads, and exists for exactly one
        caller: `BarStore.tails` hands back the last twenty bars of a much longer stored series
        together with that series' true length, because reading the whole history to count it cost
        73 seconds a run. The count is the only thing a tail cannot answer for itself. Everything
        else - the ADTV window, the last close - is read off the bars either way, so both callers
        run this one test on the same numbers rather than a second implementation of it.

        Leave it `None` and the count is the series' own length, which is what every other caller
        means and what this did before the parameter existed.

        **The two tests read different bars, and that is deliberate.** ADTV is measured over the
        window ending `adtv_lag` sessions before `as_of_index`, because volume at that age is still
        being rewritten. The `min_price` test still reads the close AT `as_of_index`: `DR-017` §1
        measured closes moving by 0.02% at p90 against volume's 32%, so a stale close buys nothing,
        and `universe.min_price` is a claim about what an instrument costs to trade NOW. `DR-017`
        lags the ADTV window and nothing else; widening it to the price test would be a second
        decision nobody has taken.

        A series too short for the lagged window is refused rather than measured on a partial one -
        `average_dollar_volume` returns `None` and this returns `False`, the same fail-closed answer
        it has always given a series too short for the unlagged window.
        """
        end = len(series.bars) - 1 if as_of_index is None else as_of_index
        total = end + 1 if history is None else history
        if total < self.min_history:
            return False
        adtv = average_dollar_volume(series, self.adtv_window, end - self.adtv_lag)
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
