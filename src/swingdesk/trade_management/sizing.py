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


def _costs_per_share(
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

    try:
        equity, equity_use = registry.decimal_value("account.equity")
        risk_pct, risk_use = registry.decimal_value("risk.per_trade_pct")
    except ParameterUnset as unset:
        return Refusal(
            "RISK",
            "a required risk parameter has no value; the system refuses rather than assuming one",
            parameter_id=unset.parameter_id,
        )

    costs_result = _costs_per_share(entry, currency, registry)
    if isinstance(costs_result, Refusal):
        return costs_result
    costs, bp_use, floor_use = costs_result

    risk_per_share = entry - stop + costs
    if risk_per_share <= 0:
        return Refusal("STOP", f"risk per share {risk_per_share} is not positive after costs")

    # Step 3-4. Allowed risk, then shares, rounded DOWN. Always down (Appendix C).
    allowed_risk = (equity * risk_pct / Decimal(100)).quantize(Decimal("0.01"))
    shares = int((allowed_risk / risk_per_share).to_integral_value(rounding=ROUND_DOWN))
    if shares <= 0:
        return Refusal(
            "RISK",
            f"allowed risk {allowed_risk} buys 0 shares at {risk_per_share} per share",
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

    position_value = (Decimal(shares) * entry).quantize(Decimal("0.01"))
    if position_value > max_value:
        shares = int((max_value / entry).to_integral_value(rounding=ROUND_DOWN))
        position_value = (Decimal(shares) * entry).quantize(Decimal("0.01"))
        if shares <= 0:
            return Refusal("LIQ", f"position-value cap {max_value} buys 0 shares at {entry}")

    return RiskSnapshot(
        equity=equity,
        risk_pct=risk_pct,
        allowed_risk=allowed_risk,
        entry=entry,
        stop=stop,
        costs_per_share=costs,
        risk_per_share=risk_per_share,
        shares=shares,
        position_value=position_value,
        planned_risk=(Decimal(shares) * risk_per_share).quantize(Decimal("0.01")),
        parameters=(equity_use, risk_use, bp_use, floor_use, value_use),
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
