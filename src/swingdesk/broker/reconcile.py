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


def ours(
    live_orders: Sequence[PlacedOrder], sent_order_ids: frozenset[str]
) -> tuple[PlacedOrder, ...]:
    """The live orders THIS system sent, identified by an id it journalled before sending. `DR-032`.

    **Not a shape test and not a prefix match.** An id is ours because it appears in our own record
    of what we put on the wire, never because it looks like something we would have written. A
    prefix test would adopt anything a person typed into the dashboard with the right first word,
    which is precisely the holding `uncommitted_exposure` exists to catch.
    """
    return tuple(order for order in live_orders if order.client_order_id in sent_order_ids)


def uncommitted_exposure(
    book: Sequence[Position],
    held: Sequence[BrokerPosition],
    live_orders: Sequence[PlacedOrder],
    market: str,
    sent_order_ids: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Symbols the VENUE is exposed to that this system's book does not carry. `DR-027` §11.

    **This is the question a submission has to ask, and `reconcile` does not ask it.** `reconcile`
    compares two descriptions of the same position and reports every kind of disagreement, which is
    what an operator wants at 18:35. A caller about to ADD exposure needs one narrower answer: is
    there anything out there the caps were not measured against? Everything else - a share count
    that differs by one, an entry price that drifted - is a reconciliation problem and not a reason
    the arithmetic on *how many more* is wrong.

    **An unfilled order counts** - unless it is one of OURS, named in `sent_order_ids`. A resting
    bracket will fill or will not, and until the venue says which, that name is spoken for. But an
    order this system sent an hour ago and journalled before sending is the exposure it can account
    for BEST, not least, and halting on it is what killed `DR-015`'s 19:30 retry: the first pass
    submitted, the second found its own orders at the venue, called them a mismatch and stopped.

    **Excluding them here obliges the caller to count them elsewhere**, and `DR-032` §3 is that
    obligation: a live order of ours consumes a slot and its R in the ratified caps. Exclude it
    from both and the retry pass adds four more names on top of the four already resting, which is
    the accumulation failure this whole family of guards exists to prevent, one step subtler.

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
    at_venue |= {
        order.symbol for order in live_orders
        if order.client_order_id not in sent_order_ids
    }
    return tuple(sorted(at_venue - known))


#: The venue's own word for an order that triggers at a price. `stop_limit` is included because it
#: still protects - it becomes a limit at the trigger rather than a market order, and a protection
#: that might not fill is a different problem from no protection at all.
PROTECTIVE_TYPES = frozenset({"stop", "stop_limit"})


@dataclass(frozen=True, slots=True)
class Unprotected:
    """One open position whose stop is not standing at the venue. `DR-036`."""

    instrument_id: str
    book_stop: Decimal
    shares: int
    #: What IS resting for this symbol, so the reason can say *nothing at all* apart from *a stop
    #: at the wrong price*. Those need different actions from a person.
    venue_stop: Decimal | None
    reason: str


def unprotected(
    book: Sequence[Position],
    live_orders: Sequence[PlacedOrder],
    market: str,
) -> tuple[Unprotected, ...]:
    """Open positions the venue is not holding a stop for. `DR-036`.

    **`reconcile` compares side, asset class, share count and entry price - and never the stop.**
    The one number that bounds the loss is the one number the reconciliation did not check, and
    `DR-027` §3.2's whole argument for submitting a bracket is that *a stop the market cannot see is
    not a stop*. This asks whether it can still see it.

    **It has to be asked every session, not once.** A bracket's legs inherit the entry's
    `time_in_force`, and `DR-027` §3.3 makes that `day` for a reason that is true of an entry and
    false of a protection: an order that outlives the session outlives the analysis - but the
    POSITION outlives the session too, by up to `exit.max_holding_period` sessions. Measured on
    2026-09-03, the first day this system held anything: all three positions' stop legs read
    `canceled` and their targets `expired` at the first close, leaving three holdings with no
    protection at the venue and a book that still recorded one.

    **A stop at the WRONG price is reported too**, and separately. `manage.apply_approved` writes a
    new `Position` version when the owner approves a stop move and sends nothing anywhere - this
    system has no verb that could - so the book and the venue can disagree about the trigger while
    both hold one. That is a different fact from having none, and a person acts on it differently.

    Pure, and out-of-scope book positions are ignored for the reason `reconcile` gives.
    """
    scope = Exchange(market)
    resting: dict[str, list[PlacedOrder]] = {}
    for order in live_orders:
        if order.order_type in PROTECTIVE_TYPES and order.stop_price is not None:
            resting.setdefault(order.symbol, []).append(order)

    findings: list[Unprotected] = []
    for position in sorted(book, key=lambda p: p.instrument_id):
        if cal.exchange_for(position.instrument_id) is not scope:
            continue
        stops = resting.get(position.instrument_id, [])
        if not stops:
            findings.append(Unprotected(
                position.instrument_id, position.current_stop, position.shares, None,
                f"the book records a stop at {position.current_stop} and {venue_word(stops)} is "
                f"resting at the venue for {position.shares} shares. A stop the market cannot see "
                f"is not a stop (DR-027 3.2).",
            ))
            continue
        # The HIGHEST resting trigger, because that is the one that fires first and is therefore
        # the protection actually in force. A lower one behind it changes nothing about the loss.
        highest = max(stop.stop_price for stop in stops if stop.stop_price is not None)
        if highest != position.current_stop:
            findings.append(Unprotected(
                position.instrument_id, position.current_stop, position.shares, highest,
                f"the book records a stop at {position.current_stop} and the venue is holding one "
                f"at {highest}. Every R this position reports is denominated in the book's number "
                f"(RISK_SPEC 2), and the loss would be taken at the venue's.",
            ))
    return tuple(findings)


def venue_word(stops: list[PlacedOrder]) -> str:
    """`nothing` or `no stop`, so the sentence reads as English in both branches."""
    return "nothing" if not stops else "no matching stop"
