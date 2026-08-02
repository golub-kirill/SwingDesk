"""Position sizing, in the order the course mandates.

Appendix C supplies the only arithmetic in the course. Modules 48-51 and 93 name every risk concept
and quantify none, so the formulas here are transcribed and every input is a registry parameter.

The ordering is not reorderable (RISK_SPEC 3):

    1. invalidation                    -> stop
    2. stop + costs allowance          -> risk per share
    3. equity x risk %                 -> allowed risk $
    4. floor(allowed risk / per share) -> shares
    5. position-value and liquidity caps
    6. portfolio checks

Narrowing the stop to obtain a larger position reverses 1 and 4. The course names that as a
prohibited move, and it is why the stop is an *input* here rather than something this function
chooses.
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
    costs_allowance: Decimal
    risk_per_share: Decimal
    shares: int
    position_value: Decimal
    planned_risk: Decimal
    parameters: tuple[ParameterUse, ...]

    @property
    def uses_assumed_parameters(self) -> bool:
        return any(parameter.is_assumed for parameter in self.parameters)


def size_long(
    entry: Decimal,
    stop: Decimal,
    registry: ParameterRegistry,
) -> RiskSnapshot | Refusal:
    """Size a long, or refuse with a code.

    Returns a Refusal rather than raising, because a refusal is an expected outcome that belongs in
    the candidate's record - not an exception to be caught somewhere and turned into a log line.
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
        costs, costs_use = registry.decimal_value("risk.costs_allowance")
    except ParameterUnset as unset:
        return Refusal(
            "RISK",
            "a required risk parameter has no value; the system refuses rather than assuming one",
            parameter_id=unset.parameter_id,
        )

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
        costs_allowance=costs,
        risk_per_share=risk_per_share,
        shares=shares,
        position_value=position_value,
        planned_risk=(Decimal(shares) * risk_per_share).quantize(Decimal("0.01")),
        parameters=(equity_use, risk_use, costs_use, value_use),
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
