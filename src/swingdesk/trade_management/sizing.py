"""Position sizing, in the order the course mandates.

Appendix C supplies the only arithmetic in the course. Modules 48-51 and 93 name every risk concept
and quantify none, so the formulas here are transcribed and every input is a registry parameter.

The ordering is not reorderable (RISK_SPEC 3):

    1. invalidation                    -> stop
    2. stop + costs per share          -> risk per share
    3. equity x risk %                 -> allowed risk $
    4. floor(allowed risk / per share) -> shares
    5. position-value and liquidity caps
    6. portfolio checks

Narrowing the stop to obtain a larger position reverses 1 and 4. The course names that as a
prohibited move, and it is why the stop is an *input* here rather than something this function
chooses.

Costs (step 2) are price-aware and currency-aware (DR-010, 2026-08-13). The single flat
`risk.costs_allowance` DR-009 set is retired: it charged the same amount per share regardless of
price or currency, which understated cost on expensive instruments and merged two currencies into
one number - both closed here, not carried forward as debt.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from swingdesk.contracts.observation import ParameterUse
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset


@dataclass(frozen=True, slots=True)
class Refusal:
    """A coded refusal. Never a value, never a default.

    Carries the skip code so the candidate's decision records why, and the parameter id when the
    cause is an unset threshold - a refusal that does not name the missing input is not actionable.
    """

    code: str
    reason: str
    parameter_id: str | None = None

    def __str__(self) -> str:
        suffix = f" [{self.parameter_id}]" if self.parameter_id else ""
        return f"{self.code}: {self.reason}{suffix}"


#: Currencies this system prices costs in. `account.base_currency` is USD; CAD arrives from
#: `.TO`-suffixed instruments (`reference_data.universe`). Any other currency has no parameter to
#: read and refuses (`AGENTS.md` 3: "USA and Canada are never merged").
_SUPPORTED_CURRENCIES = ("USD", "CAD")


@dataclass(frozen=True, slots=True)
class RiskSnapshot:
    """The Risk Snapshot entity of Appendix G, as computed.

    `planned_risk` is frozen here and is the denominator of R forever after - not the current risk,
    not the risk after a partial. That invariant is only enforceable because this value is stored
    immutably at entry (RISK_SPEC 2).
    """

    equity: Decimal
    risk_pct: Decimal
    allowed_risk: Decimal
    entry: Decimal
    stop: Decimal
    costs_per_share: Decimal
    risk_per_share: Decimal
    shares: int
    position_value: Decimal
    planned_risk: Decimal
    parameters: tuple[ParameterUse, ...]

    @property
    def uses_assumed_parameters(self) -> bool:
        return any(parameter.is_assumed for parameter in self.parameters)


def costs_per_share(
    entry: Decimal, currency: str, registry: ParameterRegistry
) -> tuple[Decimal, ParameterUse, ParameterUse] | Refusal:
    """Round-trip cost per share: `max(floor, bp/10000 * entry)`, both terms per-currency (DR-010).

    Neither term alone is honest at every price. A flat floor undercharges an expensive instrument
    (DR-009's own confession: a quarter of the true cost at $200); a pure proportional term
    undercharges a cheap one, because spread behaves like a fixed minimum rather than a fraction of
    price - understating cost is the unsafe direction, since `risk_per_share = entry - stop + costs`
    means a smaller `costs` silently produces MORE shares. The floor is carried forward from the
    single constant DR-009 set (0.25, itself derived from 50bp at a $50 reference), so cheap
    instruments are priced exactly as before rather than newly guessed at.
    """
    if currency not in _SUPPORTED_CURRENCIES:
        return Refusal(
            "RISK",
            f"no cost parameters for currency {currency!r}; supported: {_SUPPORTED_CURRENCIES}",
        )
    suffix = currency.lower()
    try:
        bp, bp_use = registry.decimal_value(f"risk.costs_bp_{suffix}")
        floor, floor_use = registry.decimal_value(f"risk.costs_floor_{suffix}")
    except ParameterUnset as unset:
        return Refusal(
            "RISK",
            "a required risk parameter has no value; the system refuses rather than assuming one",
            parameter_id=unset.parameter_id,
        )
    proportional = (bp / Decimal(10_000) * entry).quantize(Decimal("0.0001"))
    return max(floor, proportional), bp_use, floor_use


def to_base_currency(
    currency: str, registry: ParameterRegistry
) -> tuple[Decimal, tuple[ParameterUse, ...]] | Refusal:
    """Base-currency units per one unit of `currency`, and the parameters that produced it.

    Public since 2026-08-22, unchanged otherwise. The portfolio cap has to total an open book that
    may hold both currencies, and a second conversion written next to it would be the same rule in
    two places - the failure master ТЗ §8 forbids and this repository has already paid for. One
    caller inside this module, one in `trade_management.portfolio`, one rule.

    Returns exactly `1` with no FX parameter recorded when the instrument is already denominated in
    `account.base_currency` - the common case, and one that must not be made to depend on a rate
    nobody needs.

    Otherwise a rate is REQUIRED and its absence is a refusal naming the parameter. That is the
    fail-closed rule applied to the one input this function used to supply for itself: before
    2026-08-16 it never read `account.base_currency` at all, so a CAD instrument was sized against a
    USD equity as though the two were the same unit. Nothing refused, nothing was flagged, and the
    error was exactly the size of the rate.

    A rate is a measured market fact and carries an as-of. Defaulting one to unblock a trade is the
    substitution `AGENTS.md` 3 forbids, so `account.fx_rate_<ccy>` starts `unset` and stays that way
    until an owner sets it with a source.
    """
    base_use = registry.use("account.base_currency")
    base = str(base_use.value).upper()
    if currency.upper() == base:
        return Decimal(1), ()

    parameter_id = f"account.fx_rate_{currency.lower()}"
    if parameter_id not in registry:
        return Refusal(
            "RISK",
            f"no FX rate parameter exists for {currency} against base {base}; sizing across "
            f"currencies without one would size the position by an unrecorded factor",
        )
    try:
        rate, rate_use = registry.decimal_value(parameter_id)
    except ParameterUnset as unset:
        return Refusal(
            "RISK",
            f"instrument is {currency} and the account is {base}; sizing across currencies "
            f"requires an FX rate and none is set. Refusing rather than treating {currency} as "
            f"{base}",
            parameter_id=unset.parameter_id,
        )
    if rate <= 0:
        return Refusal("RISK", f"{parameter_id} is {rate}; a rate must be positive",
                       parameter_id=parameter_id)
    return rate, (base_use, rate_use)


def allowed_risk(
    registry: ParameterRegistry,
) -> tuple[Decimal, ParameterUse, ParameterUse] | Refusal:
    """One R in `account.base_currency`: `equity x risk %` (Appendix C, step 3 of RISK_SPEC §3).

    Extracted from `size_long` on 2026-08-22 because a second caller appeared. The portfolio cap is
    denominated in R (`risk.max_open_risk` = 4R), so anything comparing a book to it needs the
    currency value of one R - and `swingdesk open-position` needs it without sizing anything at all.
    Re-deriving `equity x pct / 100` at that call site would put the only arithmetic the course
    supplies in two places.
    """
    try:
        equity, equity_use = registry.decimal_value("account.equity")
        risk_pct, risk_use = registry.decimal_value("risk.per_trade_pct")
    except ParameterUnset as unset:
        return Refusal(
            "RISK",
            "a required risk parameter has no value; the system refuses rather than assuming one",
            parameter_id=unset.parameter_id,
        )
    return (equity * risk_pct / Decimal(100)).quantize(Decimal("0.01")), equity_use, risk_use


def size_long(
    entry: Decimal,
    stop: Decimal,
    currency: str,
    registry: ParameterRegistry,
) -> RiskSnapshot | Refusal:
    """Size a long, or refuse with a code.

    Returns a Refusal rather than raising, because a refusal is an expected outcome that belongs in
    the candidate's record - not an exception to be caught somewhere and turned into a log line.

    `currency` selects which cost parameters apply (DR-010) - there is deliberately no default
    currency, because guessing one is exactly the silent-oversizing risk the split exists to close.
    """
    # Step 1-2. Stop first. A stop at or above entry is not an invalidation level for a long.
    if stop >= entry:
        return Refusal(
            "STOP",
            f"stop {stop} is not below entry {entry}; no logical invalidation",
        )

    # And a stop must be a PRICE. `stop >= entry` alone let a zero or negative stop through: it is
    # below entry, the arithmetic that follows is finite, and 98 shares came back against a
    # "risk per share" larger than the entry price itself.
    #
    # Reachable on the live path, not a hypothetical - the stop arrives as
    # `entry - atr_stop_multiple * atr`, so any instrument whose ATR exceeds half its price at a 2.0
    # multiple produces one. `universe.min_price` is 5.00, which does not exclude that.
    #
    # `Position` already refuses it (`initial_stop` is `gt=0`), so the two contracts disagreed: the
    # run would size and propose a trade the store could never record. Found by
    # `test_sizing_and_position_agree_on_the_denominator` on its first run, which is what a
    # cross-module property test is for.
    if stop <= 0:
        return Refusal(
            "STOP",
            f"stop {stop} is not a positive price; an instrument cannot be stopped out at or "
            f"below zero",
        )

    budget = allowed_risk(registry)
    if isinstance(budget, Refusal):
        return budget
    allowed, equity_use, risk_use = budget
    equity, risk_pct = Decimal(equity_use.value), Decimal(risk_use.value)

    # Step 2b. The account and the instrument may not be in the same currency, and until 2026-08-16
    # this function assumed they were. `account.equity` is denominated in `account.base_currency`;
    # `entry`, `stop` and `costs` are denominated in the INSTRUMENT's currency. Dividing an allowed
    # risk in USD by a risk-per-share in CAD sizes a `.TO` candidate as though CAD were USD - an
    # oversizing error of whatever the rate happens to be, with no refusal and nothing on the record
    # saying a conversion was skipped.
    #
    # `costs_per_share` reads per-currency cost parameters and so LOOKED currency-aware, which is
    # what made this survive review: the costs were right and the denominator they fed was measured
    # in a currency the numerator never shared.
    fx_result = to_base_currency(currency, registry)
    if isinstance(fx_result, Refusal):
        return fx_result
    base_per_local, fx_uses = fx_result

    costs_result = costs_per_share(entry, currency, registry)
    if isinstance(costs_result, Refusal):
        return costs_result
    costs, bp_use, floor_use = costs_result

    risk_per_share = entry - stop + costs
    if risk_per_share <= 0:
        return Refusal("STOP", f"risk per share {risk_per_share} is not positive after costs")

    # Step 3-4. Allowed risk, then shares, rounded DOWN. Always down (Appendix C).
    #
    # `allowed_risk` is in the account's base currency and `risk_per_share` is in the instrument's,
    # so the budget is converted INTO the instrument's currency before the division. Converting the
    # budget rather than the per-share risk keeps `allowed_risk` reported in the units the owner set
    # it in - the number on the report should be the number in the registry.
    allowed_risk_local = (allowed / base_per_local).quantize(Decimal("0.01"))
    shares = int((allowed_risk_local / risk_per_share).to_integral_value(rounding=ROUND_DOWN))
    if shares <= 0:
        return Refusal(
            "RISK",
            f"allowed risk {allowed_risk_local} {currency} buys 0 shares at "
            f"{risk_per_share} per share",
        )

    # Step 5. Caps are applied AFTER the raw share count, never folded into it.
    try:
        max_value, value_use = registry.decimal_value("risk.max_position_value")
    except ParameterUnset as unset:
        return Refusal(
            "RISK",
            "position-value cap has no value; sizing without a cap is not permitted",
            parameter_id=unset.parameter_id,
        )

    # The cap is a base-currency figure (`risk.max_position_value` is 25% of `account.equity`), so
    # the position is converted UP to base to compare. Comparing a CAD position value against a USD
    # cap is the same error as the sizing division and was present in the same line.
    max_value_local = (max_value / base_per_local).quantize(Decimal("0.01"))
    position_value = (Decimal(shares) * entry).quantize(Decimal("0.01"))
    if position_value > max_value_local:
        shares = int((max_value_local / entry).to_integral_value(rounding=ROUND_DOWN))
        position_value = (Decimal(shares) * entry).quantize(Decimal("0.01"))
        if shares <= 0:
            return Refusal(
                "LIQ",
                f"position-value cap {max_value_local} {currency} buys 0 shares at {entry}",
            )

    return RiskSnapshot(
        equity=equity,
        risk_pct=risk_pct,
        allowed_risk=allowed,
        entry=entry,
        stop=stop,
        costs_per_share=costs,
        risk_per_share=risk_per_share,
        shares=shares,
        position_value=position_value,
        planned_risk=(Decimal(shares) * risk_per_share).quantize(Decimal("0.01")),
        parameters=(equity_use, risk_use, bp_use, floor_use, value_use, *fx_uses),
    )


def r_multiple(net_pnl: Decimal, snapshot: RiskSnapshot) -> Decimal:
    """R = net P&L / planned risk $ (Appendix C).

    The denominator is the risk planned at entry. It does not move when the stop moves or a partial
    is taken - that is what makes R comparable across trades, and it is the invariant most often
    broken in systems of this kind.
    """
    if snapshot.planned_risk == 0:
        raise ValueError("planned risk is zero; R is undefined")
    return net_pnl / snapshot.planned_risk
