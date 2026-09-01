"""What a brokerage account REPORTS. Three records, and none of them is an instruction.

These are source facts in the course's sense: they say what happened at a venue, in the past
tense. Nothing here proposes, sizes or decides, and nothing here has an execute verb - the same
boundary `contracts.position.ActionKind` draws, drawn again on the other side of the wire.

**Why these are separate records from `Position` and `Fill` rather than parsed straight into
them.** A broker's position is not this system's position and the difference is not cosmetic:

  - The venue knows the symbol, the quantity and the average entry. It does NOT know the STOP,
    and the stop is what `RISK_SPEC.md` 2 denominates every R in. A `Position` cannot be
    constructed from a broker's answer, and pretending otherwise would invent the denominator the
    entire validation programme is measured in.
  - The venue knows nothing about which strategy opened a trade, or which approved action a fill
    settles. `Fill` carries `position_id` and `sequence` for that reason.

So these records are what the venue said, and turning one into a `Position` or a `Fill` is a
separate, explicit step that either finds the missing facts or refuses (`broker.reconcile`).

**Money is `Decimal` here even though the wire is strings** (`AGENTS.md` 5). Alpaca serialises every
monetary and quantity field as a JSON string; parsing to `float` at the boundary would lose the
exactness on the way in, where no later care can restore it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Side(StrEnum):
    """Which way the venue says it went. Reported, never chosen here."""

    BUY = "buy"
    SELL = "sell"


class FillKind(StrEnum):
    """Whether the order finished. A partial fill is a fact, not an error."""

    FILL = "fill"
    PARTIAL_FILL = "partial_fill"


class PositionSide(StrEnum):
    """`long` or `short`, as the venue reports it.

    `SHORT` exists so a short position can be READ and REFUSED by name. This system sizes and
    stops long positions only (`RISK_SPEC.md`, and every stop validator in `contracts.position`
    requires the stop below entry), so a short at the venue is a book this software cannot
    describe - which is a refusal to report, not a record to drop silently.
    """

    LONG = "long"
    SHORT = "short"


class BrokerAccount(BaseModel):
    """The account, as the venue describes it.

    **No account number and no account id.** `SECURITY.md` 2.4 keeps identifying credentials out of
    error messages, reports and manifests, and a record that carries one will eventually be printed
    by something. `fingerprint` answers the only question this system actually asks of that value -
    *is this the same account as last time* - and answers nothing else.
    """

    model_config = ConfigDict(frozen=True)

    venue: str = Field(description="`venue.name` from the committed broker policy.")
    base_url: str = Field(description="The host that answered. The paper/live boundary is this.")

    fingerprint: str = Field(
        description="A stable digest of the venue's account number. Identifies continuity without "
                    "reproducing the value.",
    )
    status: str = Field(description="The venue's own status string, e.g. ACTIVE.")
    currency: str

    cash: Decimal
    equity: Decimal
    buying_power: Decimal

    trading_blocked: bool
    account_blocked: bool

    observed_at: datetime = Field(description="When we asked. Not when the venue computed it.")


class BrokerPosition(BaseModel):
    """One position the venue says is open.

    `shares` is `Decimal` rather than `int` deliberately: Alpaca fills fractional quantities, and
    this system's `Position.shares` is a whole number. A fractional holding is therefore something
    this software can READ and cannot RECORD, and the difference has to survive as far as the
    reconciliation to be reported as such.
    """

    model_config = ConfigDict(frozen=True)

    symbol: str
    asset_class: str = Field(description="`us_equity` and so on. Read so a non-equity can refuse.")
    exchange: str
    side: PositionSide

    shares: Decimal = Field(description="Signed by `side`, not by this number; always positive.")
    average_entry_price: Decimal
    current_price: Decimal | None = Field(
        default=None,
        description="The venue's last mark. None when it did not supply one - never zero.",
    )
    market_value: Decimal | None = None
    cost_basis: Decimal | None = None
    unrealized_pl: Decimal | None = None

    observed_at: datetime

    @property
    def whole_shares(self) -> int | None:
        """The quantity as a whole number, or `None` when the venue holds a fraction.

        `None` is a refusal and not a rounding. Rounding a fractional holding to record it would
        make this system's book disagree with the venue by design, in the one place where the two
        being identical is the entire point of reading the venue at all.
        """
        if self.shares != self.shares.to_integral_value():
            return None
        return int(self.shares)


class BrokerFill(BaseModel):
    """One execution the venue reports, full or partial.

    This is NOT `contracts.position.Fill`. That record settles an APPROVED action and carries the
    `position_id` and `sequence` it settles; this one carries what the venue knows, which is an
    order id and a symbol. Joining the two is `broker.reconcile`'s job and it can fail.
    """

    model_config = ConfigDict(frozen=True)

    activity_id: str = Field(description="The venue's own id. Also its pagination token.")
    order_id: str

    symbol: str
    side: Side
    kind: FillKind

    transaction_time: datetime = Field(description="When the execution happened at the venue.")
    price: Decimal = Field(gt=0, description="Per share, as executed.")
    shares: Decimal = Field(gt=0, description="This execution only, not the order's total.")

    cumulative_shares: Decimal | None = Field(
        default=None, description="The order's filled total after this execution.",
    )
    remaining_shares: Decimal | None = Field(
        default=None, description="`leaves_qty`: what the order still has to fill.",
    )
    order_status: str | None = None

    observed_at: datetime = Field(description="When we learned this. Not when it happened.")

    @property
    def whole_shares(self) -> int | None:
        """The executed quantity as a whole number, or `None` for a fractional execution."""
        if self.shares != self.shares.to_integral_value():
            return None
        return int(self.shares)


class EntryOrder(BaseModel):
    """One entry this system intends to submit. An INTENT, and not yet a fact.

    Separate from `PlacedOrder` for the reason `Position` is separate from `BrokerPosition`: what
    was asked for and what happened are different claims, and a record that conflates them cannot
    describe a rejection.

    `DR-027` 3 argues every field. The two that carry the most weight:

      - `limit_price` is the price the SIZING used, not a price chosen for this order. Every R the
        resulting position reports is denominated in `entry - stop + costs` frozen at entry, so a
        fill anywhere else makes that R a fiction in the flattering direction. It is also the
        `CHASE` and `LATE` controls by construction - an order that can only fill at the decision
        price cannot chase - which is why this introduces no threshold.
      - `stop_price` is submitted WITH the entry, as a bracket leg. A stop the market cannot see
        protects nothing between runs.
    """

    model_config = ConfigDict(frozen=True)

    client_order_id: str = Field(
        description="Deterministic from session date and instrument. The venue rejects a "
                    "duplicate, so a retried pass cannot submit the same entry twice.",
    )
    session_date: date = Field(description="The session this decision belongs to.")

    instrument_id: str
    symbol: str = Field(description="What the venue calls it.")

    shares: int = Field(gt=0, description="Whole shares. The sizing produced this number.")
    limit_price: Decimal = Field(gt=0)
    stop_price: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def _stop_below_entry(self) -> EntryOrder:
        if self.stop_price >= self.limit_price:
            raise ValueError(
                f"stop {self.stop_price} is not below the limit {self.limit_price}. This system "
                f"describes long positions only, and a bracket whose stop is at or above its entry "
                f"would be rejected by the venue after being recorded here as sent."
            )
        return self

    @property
    def risk_per_share(self) -> Decimal:
        """What one share risks at the submitted prices, before costs.

        Not the R denominator - `Position.initial_risk_per_share` adds costs and is frozen at the
        FILL. This is the quantity a reviewer checks the order against.
        """
        return self.limit_price - self.stop_price


class PlacedOrder(BaseModel):
    """What the venue said about an order it was sent. A fact, and not a position.

    An accepted order is not a fill: `leaves_qty` exists because partial fills do, and `DR-027` 6
    keeps `Position` a thing created from the fill.
    """

    model_config = ConfigDict(frozen=True)

    order_id: str = Field(description="The venue's id.")
    client_order_id: str = Field(description="Ours, echoed back. Proof the id we derived landed.")

    symbol: str
    status: str = Field(description="The venue's own status string, e.g. `accepted` or `new`.")
    submitted_at: datetime

    filled_shares: Decimal = Field(
        default=Decimal(0),
        description="Almost always zero at submission. Read rather than assumed, because a "
                    "marketable order can fill inside the response.",
    )

    observed_at: datetime
