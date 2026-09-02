"""Does this system's book say what the venue says? A pure comparison, and a coded answer.

**The code is `TECH`, and it is not invented here.** Appendix N's skip-reason table already carries
it: *"Broker/platform/journal mismatch"*, whose prescribed action is *"Pause new entries"*. The
course anticipated this exact condition, so the reconciliation reports in the vocabulary that
already exists rather than growing a parallel one (`AGENTS.md` 5, `CODES.md`).

**Pure by construction.** No network, no store, no clock: two sequences in, one report out. The
adapter reads the venue, the caller reads the book, and this decides whether they agree - which
means the hard part is testable without either.

**What a divergence is NOT.** A `.TO` position in this system's book is not something the venue
failed to report; Alpaca trades US equities and cannot hold it. `AGENTS.md` 3 keeps USA and Canada
separate, and counting a Canadian holding as an unrecorded exit would be that rule broken by an
omission rather than by an assertion. Those positions are reported `out_of_scope` and are not
divergences. The venue's market comes from the committed policy, so this module names no exchange.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from swingdesk.contracts.broker import BrokerFill, BrokerPosition, PlacedOrder, PositionSide
from swingdesk.contracts.position import Position
from swingdesk.contracts.reference import Exchange
from swingdesk.reference_data import calendar as cal

#: The course's own code for this condition (`CODES.md`, Appendix N). Its prescribed action is
#: "Pause new entries", which is what a caller does with a report that does not agree.
MISMATCH_CODE = "TECH"

#: The asset class this system can describe. A venue holding anything else is reported rather than
#: interpreted: `RISK_SPEC` sizes equity from a per-share stop, and an option or a crypto pair is
#: not a smaller version of that problem.
SUPPORTED_ASSET_CLASS = "us_equity"


@dataclass(frozen=True, slots=True)
class Divergence:
    """One thing the two sides do not agree about.

    `reason` is a short machine-readable discriminator UNDER `TECH`, never a replacement for it.
    The course's code says what to do; this says which shape of mismatch produced it.
    """

    instrument_id: str
    reason: str
    detail: str


@dataclass(frozen=True, slots=True)
class Agreement:
    """One position both sides describe identically."""

    instrument_id: str
    shares: int
    book_entry_price: Decimal
    venue_entry_price: Decimal


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """What the two books say about each other.

    `agrees` is the only thing a caller should branch on, and it is deliberately false when
    anything at all diverged: `FAIL_CLOSED_POLICY` 3 forbids a score clearing a critical gate, and
    "mostly reconciled" is a score.
    """

    venue: str
    market: str
    agreed: tuple[Agreement, ...]
    divergences: tuple[Divergence, ...]
    out_of_scope: tuple[str, ...]
    unrecorded_symbols: tuple[str, ...]

    @property
    def agrees(self) -> bool:
        return not self.divergences

    @property
    def code(self) -> str | None:
        """`TECH` when the two disagree, `None` when they do not. Never a severity or a count."""
        return None if self.agrees else MISMATCH_CODE


def reconcile(
    book: Sequence[Position],
    held: Sequence[BrokerPosition],
    venue: str,
    market: str,
) -> Reconciliation:
    """Compare this system's open positions against what the venue says it holds.

    `book` is what `PositionStore.open_as_of` returned; `held` is what the venue reported. Both are
    taken as given - a caller that could not read one of them has nothing to reconcile and must say
    so rather than passing an empty sequence, which would read here as *the venue holds nothing*.
    """
    scope = Exchange(market)

    in_scope: list[Position] = []
    out_of_scope: list[str] = []
    for position in book:
        if cal.exchange_for(position.instrument_id) is scope:
            in_scope.append(position)
        else:
            out_of_scope.append(position.instrument_id)

    by_symbol = {holding.symbol: holding for holding in held}
    matched: set[str] = set()

    agreed: list[Agreement] = []
    divergences: list[Divergence] = []

    for position in sorted(in_scope, key=lambda p: p.instrument_id):
        holding = by_symbol.get(position.instrument_id)
        if holding is None:
            divergences.append(Divergence(
                position.instrument_id, "book_only",
                f"the book holds {position.shares} shares and {venue} reports no position. "
                f"An exit that happened at the venue and was never recorded looks exactly like "
                f"this.",
            ))
            continue

        matched.add(holding.symbol)
        divergence = _compare(position, holding, venue)
        if divergence is not None:
            divergences.append(divergence)
        else:
            agreed.append(Agreement(
                instrument_id=position.instrument_id,
                shares=position.shares,
                book_entry_price=position.entry_price,
                venue_entry_price=holding.average_entry_price,
            ))

    for holding in sorted(held, key=lambda h: h.symbol):
        if holding.symbol in matched:
            continue
        divergences.append(Divergence(
            holding.symbol, "venue_only",
            f"{venue} holds {holding.shares} shares at {holding.average_entry_price} and this "
            f"system's book has no open position. An entry that was never recorded looks exactly "
            f"like this - and until it is, no risk cap has ever seen it.",
        ))

    return Reconciliation(
        venue=venue,
        market=market,
        agreed=tuple(agreed),
        divergences=tuple(divergences),
        out_of_scope=tuple(sorted(out_of_scope)),
        unrecorded_symbols=tuple(sorted(holding.symbol for holding in held
                                        if holding.symbol not in matched)),
    )


def _compare(position: Position, holding: BrokerPosition, venue: str) -> Divergence | None:
    """One position against one holding. `None` means they agree about everything checked."""
    if holding.side is PositionSide.SHORT:
        return Divergence(
            position.instrument_id, "short",
            f"{venue} reports a SHORT. Every stop validator in this system requires the stop below "
            f"entry, so a short is a position this software cannot describe, not one it holds "
            f"differently.",
        )

    if holding.asset_class and holding.asset_class != SUPPORTED_ASSET_CLASS:
        return Divergence(
            position.instrument_id, "asset_class",
            f"{venue} reports asset class {holding.asset_class!r}, not {SUPPORTED_ASSET_CLASS!r}.",
        )

    whole = holding.whole_shares
    if whole is None:
        return Divergence(
            position.instrument_id, "fractional",
            f"{venue} holds {holding.shares} shares. This system records whole shares, so the "
            f"quantity cannot be represented - rounding it would make the two books disagree by "
            f"design.",
        )

    if whole != position.shares:
        return Divergence(
            position.instrument_id, "shares",
            f"the book says {position.shares} shares and {venue} says {whole}. A partial exit or a "
            f"partial fill that was never recorded looks exactly like this.",
        )

    if holding.average_entry_price != position.entry_price:
        return Divergence(
            position.instrument_id, "entry_price",
            f"the book entered at {position.entry_price} and {venue} reports an average of "
            f"{holding.average_entry_price}. Every R this position reports is denominated in the "
            f"first number (RISK_SPEC 2), so the two describing different trades is not cosmetic.",
        )

    return None


def unrecorded_fills(
    fills: Sequence[BrokerFill],
    book: Sequence[Position],
) -> tuple[BrokerFill, ...]:
    """Executions at the venue for instruments this system's book has never opened.

    Deliberately weaker than it looks, and the weakness is the honest part: the venue reports an
    order id and a symbol, and `contracts.position.Fill` settles a `position_id` and an approved
    `sequence`. Nothing in a venue's answer carries either. So this reports *which executions have
    no counterpart in the book* and never guesses which approved action one of them settles - a
    wrong join here would write evidence against a plan that did not produce it, which is the
    `HINDSIGHT` control turned inside out.
    """
    known = {position.instrument_id for position in book}
    return tuple(fill for fill in fills if fill.symbol not in known)


def uncommitted_exposure(
    book: Sequence[Position],
    held: Sequence[BrokerPosition],
    live_orders: Sequence[PlacedOrder],
    market: str,
) -> tuple[str, ...]:
    """Symbols the VENUE is exposed to that this system's book does not carry. `DR-027` §11.

    **This is the question a submission has to ask, and `reconcile` does not ask it.** `reconcile`
    compares two descriptions of the same position and reports every kind of disagreement, which is
    what an operator wants at 18:35. A caller about to ADD exposure needs one narrower answer: is
    there anything out there the caps were not measured against? Everything else - a share count
    that differs by one, an entry price that drifted - is a reconciliation problem and not a reason
    the arithmetic on *how many more* is wrong.

    **An unfilled order counts.** A resting bracket will fill or will not, and until the venue says
    which, that name is spoken for. Counting only filled positions is what would let the same name
    be entered on two consecutive evenings, which is the whole failure this exists to stop.

    **Out-of-scope book positions are ignored, in scope-symmetry with `reconcile`.** A `.TO` holding
    is not something this venue failed to report, and a venue symbol that matches no book position
    is the finding - never the other way round.

    Returns them sorted, empty when the venue holds nothing the book has not accounted for. Empty
    is the ONLY safe answer, and a caller that treats a non-empty tuple as advisory has reinvented
    the `unavailable`-admits-unchecked inversion (`DR-025` §2.1).
    """
    scope = Exchange(market)
    known = {
        position.instrument_id for position in book
        if cal.exchange_for(position.instrument_id) is scope
    }
    at_venue = {holding.symbol for holding in held}
    at_venue |= {order.symbol for order in live_orders}
    return tuple(sorted(at_venue - known))
