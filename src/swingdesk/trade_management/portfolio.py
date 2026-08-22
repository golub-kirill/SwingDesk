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

Pure: no I/O, no clock, no store. The book is passed in and the FX conversion is injected, so the
one place that knows how to reach base currency stays `sizing.to_base_currency` rather than being
written twice.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from swingdesk.contracts.position import Position
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data.calendar import currency_for
from swingdesk.trade_management.sizing import Refusal

#: The parameters this module exists to consume. `registry/parameters.yml` names `limits` back
#: through `read_by`, and gate 1 imports and resolves it - so the two can never drift into the
#: "decided, but wired to nothing" state that `AGENTS.md` §7 was written for, which is exactly the
#: state these two were in between their ratification and this file.
MAX_OPEN_RISK = "risk.max_open_risk"
MAX_CONCURRENT = "risk.max_concurrent_positions"

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
    def risk_remaining_r(self) -> Decimal:
        """R left under `risk.max_open_risk`. May be negative - an over-cap book is a real state."""
        return self.caps.max_open_risk - self.book.open_risk_r

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

    The count is tested first because it is the cleaner cause to report: "the book is full" is a
    fact an owner can act on, while an R figure needs the arithmetic explained. Both are checked -
    `DR-006` §1 sets them to the same number precisely so neither can bind while the other looks
    satisfied, and a run that stopped at the first would not notice if they ever diverged.
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
