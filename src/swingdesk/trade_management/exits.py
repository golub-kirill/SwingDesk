"""How a position ends, decided by rule.

Lives in `trade_management` because that is the layer the course assigns exits to - M52-M58 are
Trade Management topics, and `EXIT_MODEL_SPEC.md` owns the four-slot model. It sat in
`validation.backtest` until N2 needed it on the live path too, which is the moment a shared rule
stops being a backtest detail. The backtest imports it from here; there is one implementation, not
two (Production Rules 3.8).

Appendix J's Exit stage: all rules, without discretionary hindsight - every exit follows a rule, and
the thing being excluded is named as discretionary hindsight.

This implements three of the course's four exit slots (`EXIT_MODEL_SPEC.md`): protective, profit
and time. The contextual slot is absent.

**The profit slot arrived on 2026-09-07 (`DR-042`) and is OPTIONAL, which is the whole design.**
`target_r_multiple` defaults to None and a policy without one behaves exactly as this file did
before - same branches, same order, same prices. That is not politeness to callers: `PR-002`,
`PR-005`, `PR-011` and `PR-012` all published trade logs under the two-slot policy, and a default
target would silently re-price every one of them. The sentence this paragraph replaces said adding
a target "would mean PR-005 compared five gates through two exit models, which is a different
study". It still would - so PR-005 keeps its policy and PR-016 states its own.

Gap handling is the part worth reading. A session that OPENS below the stop fills at the open, and
the loss recorded is the actual loss. Assuming every stopped trade loses exactly 1R is the single
most common way a backtest flatters itself, and on the instruments where it matters most - the ones
that gap - it is wrong by a lot.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from swingdesk.contracts.market import Bar
from swingdesk.contracts.trade import ExitReason


@dataclass(frozen=True, slots=True)
class ExitDecision:
    """What happened to the position on this bar.

    `ambiguous` marks a bar on which BOTH legs were reachable intraday - the low took out the stop
    and the high reached the target - and a daily bar cannot say which came first. The flag exists
    so the size of the tie-break assumption is a counted number rather than an implied one. It is
    never a reason to change the answer; `evaluate` resolves it the same way every time.
    """

    exited: bool
    price: Decimal | None = None
    reason: ExitReason | None = None
    ambiguous: bool = False

    def __post_init__(self) -> None:
        """An exit without a price or a reason is not an exit.

        The fields are optional because a non-exit has neither, and that left
        `ExitDecision(exited=True)` constructible - it would have produced a Trade with a None exit
        price and no recorded reason. mypy surfaced it at the backtest engine's call site as an
        unnarrowed `Decimal | None`; the fix belongs here, where the invariant lives.
        """
        if self.exited and (self.price is None or self.reason is None):
            raise ValueError("an exit must carry both a price and a reason")


@dataclass(frozen=True, slots=True)
class ExitPolicy:
    """Protective stop plus a maximum holding period.

    `atr_stop_multiple` and `max_holding_bars` are study constants pinned by the caller, not
    registry reads. A study that inherited them would change meaning the next time an owner
    edits a value, so it pins its own and never reads the registry here.

    The reason used to be that `exit.atr_stop_multiple` and `exit.max_holding_period` were
    `unset`. `DR-012` set both on 2026-08-17 - `assumed`, value 2.0 and 20 - so THE RULE
    SURVIVES AND THE REASON DOES NOT, and the rule matters more now than it did then: the
    day they were ratified is exactly the day an inheriting study would have moved.
    `DR-012` section 8.3 ordered this correction in the ratifying commit and it did not
    happen; the sentence stood false for nineteen days.
    """

    atr_stop_multiple: Decimal
    max_holding_bars: int
    target_r_multiple: Decimal | None = None

    def __post_init__(self) -> None:
        if self.atr_stop_multiple <= 0:
            raise ValueError(f"atr_stop_multiple must be > 0, got {self.atr_stop_multiple}")
        if self.max_holding_bars < 1:
            raise ValueError(f"max_holding_bars must be >= 1, got {self.max_holding_bars}")
        if self.target_r_multiple is not None and self.target_r_multiple <= 0:
            # Same refusal `broker/submit.py:target_price` makes on the live path, for the same
            # reason: a target at or below the entry is an instruction to sell at a loss, and the
            # OCO contract rejects it. The harness must not be able to express what the venue
            # would refuse.
            raise ValueError(f"target_r_multiple must be > 0, got {self.target_r_multiple}")

    def stop_for(self, entry_price: Decimal, atr: Decimal) -> Decimal:
        """Initial protective stop. Set before size, always (RISK_SPEC 3)."""
        return entry_price - self.atr_stop_multiple * atr

    def target_for(self, entry_price: Decimal, risk_per_share: Decimal) -> Decimal | None:
        """The take-profit limit, `target_r_multiple` R above entry. None when the slot is unused.

        `risk_per_share` is the position's own denominator - `entry - stop`, frozen at entry
        (`RISK_SPEC` 2) - so the target is volatility-normalised by construction, which is the
        argument `DR-029` gave for expressing it in R rather than in percent.

        Deliberately takes the risk per share rather than recomputing `stop_for`: the live path's
        R includes costs and the backtest's does not, and a target that silently recomputed its own
        denominator would disagree with the position it belongs to. One denominator, passed in.
        """
        if self.target_r_multiple is None:
            return None
        return entry_price + self.target_r_multiple * risk_per_share

    def evaluate(
        self, bar: Bar, stop: Decimal, bars_held: int, target: Decimal | None = None
    ) -> ExitDecision:
        """Check one bar against the policy. Every ambiguity resolves against the strategy.

        **The order is the rule.** A daily bar records four prices and no times, so on a bar that
        touches more than one leg the sequence is unknowable and has to be assumed. Each assumption
        here is the pessimistic one:

        1. **The open is not ambiguous** - it is the session's first trade, so a leg the open
           itself satisfies fired before anything intraday could. A gap through the stop fills at
           the OPEN, which is worse than the stop.
        2. **A gap through the target fills at the TARGET, not at the open.** A real limit order
           would have filled at the better price; this does not credit it. Carried over verbatim
           from `measure_exit_surface.py`, which set the convention on 2026-09-06.
        3. **Intraday, the stop is checked BEFORE the target.** When the low reached the stop and
           the high reached the target on the same bar, the stop is taken. This is what
           `backtesting.py` (kernc) does for the same reason, and the bar is flagged `ambiguous`
           so the count is reportable.
        4. **The stop is checked before the TIME exit** - unchanged, and the reason is unchanged:
           the opposite order converts some losses into time exits at a usually better price.

        Note 3 and 4 together mean a bar can satisfy the target and still exit at the stop. That is
        the cost of daily bars, and `DR-042` records it as an assumption with a measured size
        rather than as an implementation detail.
        """
        # (1) and (2): the open, where the sequence is known rather than assumed.
        if bar.open <= stop:
            # Gapped through. The fill is the open, not the stop.
            return ExitDecision(True, bar.open, ExitReason.STOP_GAP)
        if target is not None and bar.open >= target:
            return ExitDecision(True, target, ExitReason.TARGET)

        # (3): intraday, where it is not. `ambiguous` says the bar could have gone either way.
        both_reachable = target is not None and bar.low <= stop and bar.high >= target
        if bar.low <= stop:
            return ExitDecision(True, stop, ExitReason.STOP, ambiguous=both_reachable)
        if target is not None and bar.high >= target:
            return ExitDecision(True, target, ExitReason.TARGET)

        # (4): the clock, last.
        if bars_held >= self.max_holding_bars:
            return ExitDecision(True, bar.close, ExitReason.TIME)
        return ExitDecision(False)
