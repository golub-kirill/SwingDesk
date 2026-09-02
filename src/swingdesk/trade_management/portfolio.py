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

**`assess`, `assess_correlation` and `assess_sector` do not allocate between candidates, and
`allocate` does.** Each `assess_*` measures ONE candidate against the OPEN BOOK alone, which was the
whole story until 2026-09-02 and is still the right shape for the candidate loop: a `Watch` is not a
position and consumes no capacity.

~~Choosing which of several admissible candidates gets the last slot is a ranking,
`rs.ranking_method` is `unset`, and `ALLOCATION_SPEC` §6 rule 4 forbids falling back to id order -
which would be an alphabetical bias silently applied. Owner ruling, 2026-08-22.~~ **That reasoning
was sound and its premise is gone.** `DR-030` ruled `rs.ranking_method` = `descending` on
2026-09-01, so a ratified ordering now exists and `ALLOCATION_SPEC` §6 rule 4 is satisfied rather
than dodged - the sentence is struck rather than deleted because the rule it names still governs
what `allocate` may be given: an ordering the registry ratified, never the order the system
happens to hold.

**Why `allocate` had to exist the day after `CARD-001` started emitting `Trade`.** While every
terminal state was `Watch`, a human read the report and applied the caps by choosing. `DR-030` §2.4
kept that model - *"this value picks which names are eligible, and the ratified caps pick which are
taken"* - and `scan --submit` then took the eligible set to a venue with nothing in between. Measured
on run `run-20260902T143239Z-b908f635`: **114 `Trade` decisions, 103.5R, 114 positions**, against
ratified caps of 4 and 4R, every one of them admitted because `pipeline` prices the book ONCE and
every candidate was therefore measured against the same empty book. `allocate` is where "the
ratified caps pick which are taken" stops being a sentence in a decision record and becomes code.

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
from swingdesk.reference_data import classification
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

#: How much of the book may sit in one sector or theme. 2R, `assumed:DR-006` - one third of the
#: book at the ratified 6R and half of it at the 4R §8.3 settled on, which is a consequence worth
#: knowing rather than a re-derivation: the anchor moved and this number did not.
MAX_SECTOR_RISK = "risk.max_sector_risk"

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


# ------------------------------------------------------------------ sector


def sector_limit(registry: ParameterRegistry) -> Decimal:
    """How much of the book may sit in one sector, or `ParameterUnset` naming it.

    One number and no companion, unlike the other two pairs here - the window a correlation is
    measured over is part of that threshold's definition, and 2R is complete on its own.
    """
    limit, _ = registry.decimal_value(MAX_SECTOR_RISK)
    return limit


@dataclass(frozen=True, slots=True)
class SectorBook:
    """The open book's risk in R, split by sector.

    Carries what it could NOT attribute as prominently as what it could, and the two are different
    facts. `unclassified_r` is risk from positions whose look-through covered only part of the
    instrument - measured, and belonging to no sector. `unmeasured` is positions whose exposure
    could not be judged at all. Both make the per-sector figures an UNDERSTATEMENT, which is the
    permissive direction, so neither may be silent.
    """

    by_sector: Mapping[str, Decimal]

    unclassified_r: Decimal
    """R from positions that WERE classified, left over by a look-through covering part of the
    instrument. Measured, and belonging to no sector."""

    unmeasured: tuple[classification.Exposure, ...]
    """Positions whose composition could not be judged at all."""

    unmeasured_r: Decimal
    """R held by those positions. Reported apart from `unclassified_r` because the two are different
    gaps: one is composition the vendor did not report, the other is a position the vendor could not
    be asked about. Adding them would make one number that answers neither question."""

    total_r: Decimal

    def held_in(self, sector: str) -> Decimal:
        """Open risk already sitting in one sector, in R. Zero when nothing is."""
        return self.by_sector.get(sector, Decimal(0))

    @property
    def is_complete(self) -> bool:
        """Every position was attributed in full. False means the split understates some sector."""
        return not self.unmeasured and self.unclassified_r == 0


ExposureFor = Callable[[str], "classification.Exposure"]
"""An instrument id to its judged sector composition. Injected rather than looked up, so this module
holds no store and no vendor - the same arrangement `RateFor` has for the FX rule."""


def sector_book(
    positions: Sequence[Position],
    rate_for: RateFor,
    r_unit: Decimal,
    exposure_for: ExposureFor,
) -> SectorBook | Refusal:
    """Split the open book's risk across sectors, or refuse naming what blocked the conversion.

    Currency is converted per position before anything is added, for the reason `book` gives at
    length: `Position.open_risk` is in the INSTRUMENT's currency and adding those raw produces a
    number in no currency at all.

    **A partial look-through spends what it reports and no more.** Weights summing to 0.94 put 94%
    of the position's R into sectors and the remaining 6% into `unclassified_r`. Normalising to 1
    would invent composition the vendor did not report; dropping the position would hide exposure
    that was measured. The remainder is carried visibly instead, which is the only option that
    neither invents nor discards.
    """
    if r_unit <= 0:
        return Refusal(
            "RISK",
            f"1R is {r_unit} in base currency, so open risk cannot be expressed in R; sector risk "
            f"cannot be measured against a cap denominated in R",
        )

    by_sector: dict[str, Decimal] = {}
    unclassified = Decimal(0)
    unmeasured: list[classification.Exposure] = []
    unmeasured_risk = Decimal(0)
    total = Decimal(0)

    for position in positions:
        currency = currency_for(position.instrument_id)
        rate = rate_for(currency)
        if isinstance(rate, Refusal):
            return Refusal(
                rate.code,
                f"open position {position.position_id} is denominated in {currency} and its sector "
                f"risk cannot be totalled without a rate: {rate.reason}",
                parameter_id=rate.parameter_id,
            )
        base_per_local, _uses = rate
        risk_r = position.open_risk * base_per_local / r_unit
        total += risk_r

        exposure = exposure_for(position.instrument_id)
        if not exposure.is_available:
            unmeasured.append(exposure)
            unmeasured_risk += risk_r
            continue
        attributed = Decimal(0)
        for weight in exposure.weights:
            share = risk_r * weight.weight
            by_sector[weight.sector] = by_sector.get(weight.sector, Decimal(0)) + share
            attributed += share
        unclassified += risk_r - attributed

    return SectorBook(
        # Sorted into a fresh dict: this feeds a report and a decision reason, and an insertion
        # order that follows whatever order the position store returned is the named determinism
        # hazard (`DETERMINISM_SPEC` §3.2).
        by_sector={sector: by_sector[sector] for sector in sorted(by_sector)},
        unclassified_r=unclassified,
        unmeasured=tuple(unmeasured),
        unmeasured_r=unmeasured_risk,
        total_r=total,
    )


@dataclass(frozen=True, slots=True)
class SectorCapacity:
    """Whether one more position fits inside the sector budget, and which sector decided."""

    admitted: bool
    limit: Decimal
    book: SectorBook
    candidate: classification.Exposure
    requested_r: Decimal
    binding: str | None
    """The sector that would go past the cap, or `None` when the candidate was admitted."""

    @property
    def is_unavailable(self) -> bool:
        """The CANDIDATE could not be classified, so the check did not run.

        Admits, because `DR-006` §3 forbids a check the system could not perform from refusing every
        candidate - a sector gate that refused for want of sector data would stop the system
        entirely while looking like risk discipline. An unmeasured POSITION is a different and
        weaker gap: it makes the split understate, and it is reported on `book.is_complete`.
        """
        return not self.candidate.is_available

    def projected(self, sector: str) -> Decimal:
        """Risk in one sector if this candidate were taken, in R."""
        return self.book.held_in(sector) + self.requested_r * self._weight(sector)

    def _weight(self, sector: str) -> Decimal:
        for weight in self.candidate.weights:
            if weight.sector == sector:
                return weight.weight
        return Decimal(0)

    @property
    def reason(self) -> str:
        """The text that travels on the refusal, or on the admission."""
        if self.binding is not None:
            return (
                f"taking this candidate would put {self.projected(self.binding):.2f}R in "
                f"{self.binding}, past the {self.limit}R {MAX_SECTOR_RISK} allows; the book "
                f"already carries {self.book.held_in(self.binding):.2f}R there"
            )
        if self.is_unavailable:
            return f"UNAVAILABLE - {self.candidate.unavailable}"
        if not self.candidate.weights:
            return "this candidate has no sector exposure to spend"
        heaviest = max(
            (weight.sector for weight in self.candidate.weights),
            key=lambda sector: (self.projected(sector), sector),
        )
        text = (
            f"heaviest sector after this candidate is {heaviest} at "
            f"{self.projected(heaviest):.2f}R of the {self.limit}R {MAX_SECTOR_RISK} allows"
        )
        # Built clause by clause rather than as one sentence, because the two gaps are independent
        # and a fixed sentence prints "0.00R sits in no sector" next to a real unclassified
        # position - a zero that reads as reassurance about the wrong quantity.
        gaps = []
        if self.book.unmeasured:
            gaps.append(
                f"{len(self.book.unmeasured)} open position(s) holding "
                f"{self.book.unmeasured_r:.2f}R could not be classified"
            )
        if self.book.unclassified_r:
            gaps.append(
                f"{self.book.unclassified_r:.2f}R sits in no sector from partial look-throughs"
            )
        if gaps:
            text += "; " + " and ".join(gaps) + ", so the split understates"
        return text


def assess_sector(
    book: SectorBook,
    limit: Decimal,
    candidate: classification.Exposure,
    requested_r: Decimal,
) -> SectorCapacity:
    """Does one more position fit inside the sector budget? (`RISK_SPEC` §3 step 6, `DR-006` §2.)

    **An ETF consumes its constituents' sector budget rather than sitting outside it.** That is
    Appendix C's control cell requiring ETFs to count toward sector risk, and it is why a candidate
    is measured through its weights rather than by a single label: a broad index fund spends a
    little of every sector, a sector fund spends nearly all of one, and both are the same
    arithmetic.

    **The WORST sector binds, and only it is named.** A candidate can push two sectors past the cap
    at once; the reason carries one, because a refusal with two causes is a refusal an owner cannot
    answer. Passing this function requires being inside the cap in every sector, so naming one is a
    reporting choice and not a gap in enforcement - the same rule `assess` follows for the book.

    **An unclassifiable CANDIDATE is admitted unchecked**, and says so. `DR-006` §3 again: a gap in
    the system and a fact about the trade are different claims, and a sector cap that refused every
    unclassified name would refuse most of the universe on the day the store was first created.
    """
    binding: str | None = None
    if candidate.is_available:
        over = [
            weight.sector
            for weight in candidate.weights
            if book.held_in(weight.sector) + requested_r * weight.weight > limit
        ]
        if over:
            binding = max(
                over,
                key=lambda sector: (
                    book.held_in(sector)
                    + requested_r * next(
                        w.weight for w in candidate.weights if w.sector == sector
                    ),
                    sector,
                ),
            )
    return SectorCapacity(
        admitted=binding is None,
        limit=limit,
        book=book,
        candidate=candidate,
        requested_r=requested_r,
        binding=binding,
    )


# ------------------------------------------------------------------ allocation


@dataclass(frozen=True, slots=True)
class Allocatable:
    """One candidate offered to `allocate`, carrying only what a cap needs to judge it.

    Not an `InstrumentOutcome`: this module sits below `application` and holds no pipeline type, so
    the caller maps whatever the run produced onto these three fields. `exposure` is the candidate's
    own judged composition - the same value `assess_sector` was given in the candidate loop.
    """

    instrument_id: str
    requested_r: Decimal
    exposure: classification.Exposure


@dataclass(frozen=True, slots=True)
class Allocated:
    """One candidate's verdict, and the reason travels whichever way it went.

    Same rule `Arming` follows in the broker package: a line saying only *passed over* is one nobody
    can act on, and a line saying only *taken* is one nobody can audit. `binding` is the parameter
    id that stopped it, so a caller can tell a full book from a full sector without parsing prose.
    """

    instrument_id: str
    taken: bool
    reason: str
    binding: str | None = None


def allocate(
    ordered: Sequence[Allocatable],
    book: Book,
    caps: Caps,
    sectors: SectorBook,
    sector_cap: Decimal,
) -> tuple[Allocated, ...]:
    """Walk a RANKED cross-section and take names until a ratified cap binds.

    **The order is the caller's and this function does not sort.** `ALLOCATION_SPEC` §6 rule 4
    forbids ranking by whatever order the system happens to have, and a function that re-sorted its
    input would be authoring the ordering that `rs.ranking_method` exists to rule. Given the wrong
    order this returns the wrong four names and says so honestly; given no order at all it must not
    be called.

    **The book ACCUMULATES, and that is the entire difference from `assess`.** Each candidate is
    judged against the book plus everything already taken in this same walk, so the four ratified
    numbers bind across one run's own output instead of only across the stored positions. The
    per-candidate verdicts in `pipeline` stay exactly as they were - they answer *may this name be
    held at all*, which is a different question from *does it fit alongside the others decided in
    the same second*.

    **Every rule is `assess` and `assess_sector`, re-entered with a grown book.** Nothing about a
    cap is re-implemented here: specification §8 forbids one logic in two places, and a second copy
    of "count + 1 > max_concurrent" is how the report and the decisions drifted apart once already.

    **A candidate the caps pass over does NOT stop the walk.** `requested_r` varies per candidate
    because the share count rounds down, so a 0.60R name can be refused where the 0.40R name behind
    it fits - the same reason `pipeline` stopped assigning `result.capacity` unconditionally. Every
    name is offered, and the ones that fit are taken.

    **An unclassifiable candidate is still admitted by the SECTOR check and still bounded by the
    other two** (`DR-006` §3). A check the system could not perform must not refuse, but it also
    buys no exemption: the count and open-risk caps do not care what a name is made of.
    """
    running_count = book.count
    running_risk = book.open_risk_base
    by_sector = dict(sectors.by_sector)
    unclassified = sectors.unclassified_r
    unmeasured = list(sectors.unmeasured)
    unmeasured_r = sectors.unmeasured_r
    total_r = sectors.total_r

    verdicts: list[Allocated] = []
    for candidate in ordered:
        so_far = Book(
            count=running_count, open_risk_base=running_risk, r_unit=book.r_unit
        )
        capacity = assess(so_far, caps, candidate.requested_r)
        if not capacity.admitted:
            verdicts.append(Allocated(
                candidate.instrument_id, False, capacity.reason, capacity.binding,
            ))
            continue

        sector_so_far = SectorBook(
            by_sector={sector: by_sector[sector] for sector in sorted(by_sector)},
            unclassified_r=unclassified,
            unmeasured=tuple(unmeasured),
            unmeasured_r=unmeasured_r,
            total_r=total_r,
        )
        sector_verdict = assess_sector(
            sector_so_far, sector_cap, candidate.exposure, candidate.requested_r
        )
        if not sector_verdict.admitted:
            verdicts.append(Allocated(
                candidate.instrument_id, False, sector_verdict.reason, MAX_SECTOR_RISK,
            ))
            continue

        # Taken. The running book grows exactly the way `book` and `sector_book` would have built
        # it from a stored position, so the next candidate is judged against a book of the shape
        # this one will actually have.
        running_count += 1
        running_risk += candidate.requested_r * book.r_unit
        total_r += candidate.requested_r
        if candidate.exposure.is_available:
            attributed = Decimal(0)
            for weight in candidate.exposure.weights:
                share = candidate.requested_r * weight.weight
                by_sector[weight.sector] = by_sector.get(weight.sector, Decimal(0)) + share
                attributed += share
            # A partial look-through spends what it reports and no more, exactly as `sector_book`
            # carries the remainder rather than normalising it away.
            unclassified += candidate.requested_r - attributed
        else:
            unmeasured.append(candidate.exposure)
            unmeasured_r += candidate.requested_r

        verdicts.append(Allocated(candidate.instrument_id, True, capacity.reason))

    return tuple(verdicts)
