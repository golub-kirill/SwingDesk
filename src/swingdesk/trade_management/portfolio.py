"""The book-level risk cap: is there room for one more position? (`DR-006` §8, `RISK_SPEC` §3.6).

`ALLOCATION_SPEC` §2 named six portfolio constraints and reported all six `unset`, so the system
could not tell you that you had too many positions because it did not know what "too many" was.
`DR-006` §8.3 supplied two of the numbers on 2026-08-22 with provenance `owner` -
`risk.max_open_risk` = 4R and `risk.max_concurrent_positions` = 4 - and until this module existed
nothing compared either to anything. `positions.open_risk_as_of` computed the quantity and the CLI
printed it; no code acted on it.

**Why this cap and not a forecast.** Measured over `PR-005`'s 26,351 trades: 89 sessions hold 52% of
all 3,003 gap exits and the worst produced 87 simultaneous gap-outs, so the risk is correlated. It is
also not predictable from anything this project holds - day-of-week refuted, prior realised
volatility refuted AND inverted, standing down above the ordinary p75 giving lift 0.59x, worse than
random (`DR-006` §8.6). A per-trade stop cannot defend against a gap, because the price it names does
not trade between the close and the open. A bound on simultaneous exposure can.

**What this module does NOT do: it does not allocate between candidates.** A `Watch` is not a
position and consumes no capacity, so each candidate is measured against the OPEN BOOK alone.
Choosing which of several admissible candidates gets the last slot is a ranking, `rs.ranking_method`
is `unset`, and `ALLOCATION_SPEC` §6 rule 4 forbids falling back to id order - which would be an
alphabetical bias silently applied. Owner ruling, 2026-08-22.

**Two of `DR-006`'s constraints live here, and they bound different things.** The book cap asks how
much is at risk at once; the correlation cap (below, built 2026-08-23) asks whether what is at risk
is the same bet twice. `RISK_SPEC` §3 step 6 names them in one breath - *check open risk, sector
risk, correlation and event exposure* - and a candidate has to clear both. They fail differently on
purpose: an unset cap refuses every candidate, because a limit nobody set is not a limit of
infinity; a correlation that could not be MEASURED admits and says so, because a check the system
was never able to perform is `unavailable` and must not masquerade as discipline (`DR-006` §3).

Pure: no I/O, no clock, no store. The book is passed in and the FX conversion is injected, so the
one place that knows how to reach base currency stays `sizing.to_base_currency` rather than being
written twice. Returns arrive already computed, for the same reason - `derived_observations.
correlation` owns the statistic and this module owns the verdict.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from swingdesk.contracts.position import Position
from swingdesk.derived_observations import correlation
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data.calendar import currency_for
from swingdesk.trade_management.sizing import Refusal

#: The parameters this module exists to consume. `registry/parameters.yml` names `limits` back
#: through `read_by`, and gate 1 imports and resolves it - so the two can never drift into the
#: "decided, but wired to nothing" state that `AGENTS.md` §7 was written for, which is exactly the
#: state these two were in between their ratification and this file.
MAX_OPEN_RISK = "risk.max_open_risk"
MAX_CONCURRENT = "risk.max_concurrent_positions"

#: The correlation cap's two numbers, both `assumed:DR-006` and both authored - the course names
#: the concept in `M49-T0761` and `M51-T0781` and quantifies neither. They are read together for
#: the same reason the book's two are: a threshold without the window it is measured over is not a
#: threshold, which is why the lookback stopped being a note inside the threshold's own entry
#: (`DR-006` §7) and became a parameter on 2026-08-23.
CORRELATION_THRESHOLD = "risk.correlation_threshold"
CORRELATION_LOOKBACK = "risk.correlation_lookback_sessions"

#: Base-currency units per one unit of the named currency, or a coded refusal. Injected rather than
#: imported so this module holds no FX rule of its own - `sizing.to_base_currency` has that shape.
RateFor = Callable[[str], "tuple[Decimal, object] | Refusal"]


@dataclass(frozen=True, slots=True)
class Caps:
    """The two ratified bounds on the book, as read from the registry."""

    max_open_risk: Decimal
    """Multiples of per-trade risk. 4R (`owner`, 2026-08-22)."""

    max_concurrent: int
    """Positions. 4 (`owner`, 2026-08-22)."""


def limits(registry: ParameterRegistry) -> Caps:
    """Both caps, or `ParameterUnset` naming the first one missing.

    Deliberately NOT defaulted, and both are read here rather than one at a time: they are the same
    constraint counted two ways (`DR-006` §1), so a run that enforced one while the other was unset
    would report discipline it did not have.
    """
    open_risk, _ = registry.decimal_value(MAX_OPEN_RISK)
    concurrent, _ = registry.int_value(MAX_CONCURRENT)
    return Caps(max_open_risk=open_risk, max_concurrent=concurrent)


@dataclass(frozen=True, slots=True)
class Book:
    """The open book, counted and priced in base currency, with R as its unit.

    `r_unit` is 1R in base currency - `account.equity` x `risk.per_trade_pct` / 100. It is taken
    from a `RiskSnapshot.allowed_risk` the run already computed rather than re-derived here, so the
    sizing law lives in exactly one place.
    """

    count: int
    open_risk_base: Decimal
    r_unit: Decimal

    @property
    def open_risk_r(self) -> Decimal:
        """Open risk in R. The unit `risk.max_open_risk` is denominated in."""
        return self.open_risk_base / self.r_unit


def book(positions: Sequence[Position], rate_for: RateFor, r_unit: Decimal) -> Book | Refusal:
    """Price the open book in base currency, or refuse naming what blocked the conversion.

    **Currency is not optional here and summing it away is the defect this guards.**
    `Position.open_risk` is denominated in the INSTRUMENT's currency, and
    `PositionStore.open_risk_as_of` adds those raw - so a mixed USD/CAD book returns a number in no
    currency at all. That has never been wrong because the store holds no positions, and it is the
    same shape as the sizing error closed on 2026-08-16, which was also invisible until a `.TO` name
    appeared. Each position is converted before it is added.

    **A negative open risk is carried through as it is** (owner ruling, 2026-08-22). A position whose
    stop sits above entry can no longer lose money at that stop, so it genuinely frees R-capacity;
    clamping to zero would hide the difference between "risk removed" and "risk locked in as profit",
    which is the reason `Position.open_risk` already refuses to clamp. The concurrency cap still
    bounds how many instruments can gap at once, which is the exposure R cannot express.
    """
    if r_unit <= 0:
        return Refusal(
            "RISK",
            f"1R is {r_unit} in base currency, so open risk cannot be expressed in R; the book "
            f"cannot be measured against a cap denominated in R",
        )

    total = Decimal(0)
    for position in positions:
        currency = currency_for(position.instrument_id)
        rate = rate_for(currency)
        if isinstance(rate, Refusal):
            # Fail closed, and say which position forced it. Adding CAD to USD to keep the run
            # moving is the substitution `AGENTS.md` §3 forbids by name.
            return Refusal(
                rate.code,
                f"open position {position.position_id} is denominated in {currency} and the book "
                f"cannot be totalled without a rate: {rate.reason}",
                parameter_id=rate.parameter_id,
            )
        base_per_local, _uses = rate
        total += position.open_risk * base_per_local
    return Book(count=len(positions), open_risk_base=total, r_unit=r_unit)


@dataclass(frozen=True, slots=True)
class Capacity:
    """Whether one more position fits, and which cap decided.

    Carries its own wording so every caller - the candidate path, `open-position`, the report -
    words the same refusal identically, which is why `freshness.Assessment` has a `reason` too.
    """

    admitted: bool
    binding: str | None
    """The parameter id that bound, or `None` when the candidate was admitted."""

    book: Book
    caps: Caps
    requested_r: Decimal

    @property
    def positions_remaining(self) -> int:
        """Slots left under `risk.max_concurrent_positions`. Never negative in the report."""
        return max(self.caps.max_concurrent - self.book.count, 0)

    @property
    def reason(self) -> str:
        """The text that travels on the refusal, or on the admission."""
        if self.binding == MAX_CONCURRENT:
            return (
                f"the book holds {self.book.count} open position(s) and {MAX_CONCURRENT} allows "
                f"{self.caps.max_concurrent}; taking this candidate would make {self.book.count + 1}"
            )
        if self.binding == MAX_OPEN_RISK:
            return (
                f"the book carries {self.book.open_risk_r:.2f}R of open risk and this candidate "
                f"would add {self.requested_r:.2f}R, past the {self.caps.max_open_risk}R "
                f"{MAX_OPEN_RISK} allows"
            )
        return (
            f"room for {self.positions_remaining} more position(s); "
            f"{self.book.open_risk_r:.2f}R of {self.caps.max_open_risk}R open"
        )


def assess(book: Book, caps: Caps, requested_r: Decimal) -> Capacity:
    """Does one more position of `requested_r` fit inside both caps?

    **Both caps refuse; only the first one to bind is NAMED.** The count is tested first because it
    is the cleaner cause to report - "the book is full" is a fact an owner can act on, while an R
    figure needs the arithmetic explained - and `binding` carries one id because a refusal with two
    causes is a refusal an owner cannot answer. So a candidate over both caps reports the count and
    says nothing about the R budget, which is a reporting choice and not a gap in enforcement:
    passing this function requires being inside both.

    `DR-006` §1 sets the two to the same number, so they normally bind together. If they ever
    diverge, this reports whichever bound first rather than both - `Capacity` has one `binding`
    field, deliberately.
    """
    binding: str | None = None
    if book.count + 1 > caps.max_concurrent:
        binding = MAX_CONCURRENT
    elif book.open_risk_r + requested_r > caps.max_open_risk:
        binding = MAX_OPEN_RISK
    return Capacity(
        admitted=binding is None,
        binding=binding,
        book=book,
        caps=caps,
        requested_r=requested_r,
    )


# ------------------------------------------------------------------ correlation


@dataclass(frozen=True, slots=True)
class CorrelationLimit:
    """The authored correlation cap, as read from the registry."""

    threshold: Decimal
    """Pearson's r at or above which two names stop counting as independent bets. 0.70
    (`assumed:DR-006`) - at r = 0.7 the pair shares about half its variance."""

    lookback: int
    """Sessions of daily returns the threshold is measured over. 60 (`assumed:DR-006`) - a quarter,
    long enough to be stable and short enough to notice a regime change."""


def correlation_limit(registry: ParameterRegistry) -> CorrelationLimit:
    """Threshold and lookback, or `ParameterUnset` naming the first one missing.

    Both, never one: a correlation of 0.70 measured over five sessions and one measured over sixty
    are different claims wearing the same number. Until 2026-08-23 the window lived in a prose note
    on the threshold entry, where no code could read it - and that entry carried TWO `note:` keys,
    so the YAML loader kept the second and the window was not even in the loaded registry. `DR-006`
    §7 named the shape of this defect before anything had tripped over it.
    """
    threshold, _ = registry.decimal_value(CORRELATION_THRESHOLD)
    lookback, _ = registry.int_value(CORRELATION_LOOKBACK)
    return CorrelationLimit(threshold=threshold, lookback=lookback)


@dataclass(frozen=True, slots=True)
class Pair:
    """One candidate-to-open-position correlation, measured or not."""

    instrument_id: str
    measurement: correlation.Measurement


@dataclass(frozen=True, slots=True)
class Concentration:
    """Whether a candidate duplicates something the book already holds.

    Carries every pair it looked at, measured and unmeasured alike. A verdict keeping only the
    binding one could not tell the report the difference between "checked four positions and none
    is close" and "could not measure any of the four" - and those are the two claims `DR-006` §3
    says must never collapse into each other.
    """

    admitted: bool
    limit: CorrelationLimit
    pairs: tuple[Pair, ...]
    binding: Pair | None
    """The correlated position that refused the candidate, or `None` when it was admitted."""

    @property
    def measured(self) -> tuple[Pair, ...]:
        return tuple(pair for pair in self.pairs if pair.measurement.is_available)

    @property
    def unmeasured(self) -> tuple[Pair, ...]:
        return tuple(pair for pair in self.pairs if not pair.measurement.is_available)

    @property
    def closest(self) -> Pair | None:
        """The measured pair with the highest r, or `None` when nothing could be measured."""
        measured = self.measured
        if not measured:
            return None
        return max(measured, key=_coefficient)

    @property
    def is_unavailable(self) -> bool:
        """The book holds positions and not one of them could be correlated with this candidate.

        Read as `unavailable`, never as independence: the check did not run. It still admits,
        because `DR-006` §3 forbids a check the system could not perform from refusing every
        candidate - that would stop the system entirely while looking like risk discipline.
        """
        return bool(self.pairs) and not self.measured

    @property
    def reason(self) -> str:
        """The text that travels on the refusal, or on the admission."""
        if self.binding is not None:
            return (
                f"moves with the open position in {self.binding.instrument_id} at "
                f"r = {_coefficient(self.binding):.2f} over {self.binding.measurement.overlap} "
                f"session(s), at or past the {self.limit.threshold} {CORRELATION_THRESHOLD} "
                f"allows; two names sharing that much variance are one bet, not two"
            )
        if not self.pairs:
            return "the book holds nothing to duplicate"
        if self.is_unavailable:
            return (
                f"UNAVAILABLE - none of the {len(self.pairs)} open position(s) could be correlated "
                f"with this candidate: {self.unmeasured[0].measurement.unavailable}"
            )
        closest = self.closest
        if closest is None:  # pragma: no cover - `measured` is non-empty by the branch above
            return "the book holds nothing to duplicate"
        text = (
            f"closest open position is {closest.instrument_id} at r = {_coefficient(closest):.2f} "
            f"over {closest.measurement.overlap} session(s), inside the {self.limit.threshold} "
            f"{CORRELATION_THRESHOLD} allows"
        )
        if self.unmeasured:
            text += (
                f"; {len(self.unmeasured)} of {len(self.pairs)} open position(s) could not be "
                f"measured and are unchecked rather than clear"
            )
        return text


def _coefficient(pair: Pair) -> Decimal:
    """A measured pair's r. Raises on an unmeasured one rather than substituting a number.

    Every caller here reaches this only after filtering on `is_available`, so a `None` arriving
    would mean the filter had stopped working - and the one thing that must not happen then is a
    silent 0.0, which would report perfect independence and sort the pair to the bottom.
    """
    r = pair.measurement.r
    if r is None:  # pragma: no cover - unreachable while every call site filters first
        raise ValueError(f"{pair.instrument_id} carries no coefficient: unmeasured pairs have no r")
    return r


def assess_correlation(
    candidate_returns: Sequence[correlation.DailyReturn],
    book_returns: Mapping[str, Sequence[correlation.DailyReturn]],
    limit: CorrelationLimit,
) -> Concentration:
    """Does this candidate duplicate an open position? (`RISK_SPEC` §3 step 6, `DR-006` §2.)

    **Against the OPEN BOOK alone, never against other candidates.** Same owner ruling as the book
    cap (`DR-006` §9.2 rule 2): a `Watch` is not a position, and choosing between two admissible
    candidates that correlate with each other is a ranking. `rs.ranking_method` is `unset` and
    `ALLOCATION_SPEC` §6 rule 4 forbids falling back to id order.

    **The sign is not taken away.** The test is `r >= threshold`, not `abs(r) >= threshold`. This
    system is long-only today, so what `DR-006` §2 bounds is duplicate exposure - two names that
    fall together. A strongly negative r is the opposite arrangement, and refusing it would forbid
    the one pairing that reduces the exposure the cap exists to bound.

    **A candidate already in the book refuses at r = 1, and that is the rule working rather than an
    accident.** Adding to a position is the most complete duplicate exposure there is, and the
    course supplies no pyramiding rule that would distinguish it from a second bet (`DR-006` §11).

    **An unmeasurable pair does not refuse.** Too little overlapping history, or a side that did not
    move, is a gap in the SYSTEM; refusing on it would report risk discipline the run does not have
    (`DR-006` §3, `AGENTS.md` §12). It is recorded on the verdict and printed, which is what makes
    the difference visible instead of merely true.
    """
    pairs = tuple(
        Pair(
            instrument_id=instrument_id,
            measurement=correlation.measure(candidate_returns, returns, limit.lookback),
        )
        # Sorted, because this verdict feeds a decision reason and an unordered iteration feeding
        # output is the named determinism hazard (`DETERMINISM_SPEC` §3.2). Two positions at the
        # same r must refuse with the same wording on every run.
        for instrument_id, returns in sorted(book_returns.items())
    )

    binding: Pair | None = None
    for pair in pairs:
        r = pair.measurement.r
        if r is None or r < limit.threshold:
            continue
        # The HIGHEST correlation binds, not the first one encountered. The reason names one
        # position, and an owner reading it should see the strongest cause of the refusal rather
        # than whichever id happened to sort earliest.
        if binding is None or r > _coefficient(binding):
            binding = pair

    return Concentration(
        admitted=binding is None,
        limit=limit,
        pairs=pairs,
        binding=binding,
    )
