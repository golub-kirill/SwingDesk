"""The daily run, as one vertical slice.

Order follows the course's own pipeline (SCREENER_SPEC 3) with the constraint from Appendix T that
open positions are evaluated before new candidates - a run-order rule, not a suggestion.

This is the walking skeleton: one instrument, one feed, one derived observation, one risk
calculation, one journal entry, one report. It deliberately exercises both paths - a component that
computes and a component that refuses - because the refusal path is the harder machinery and a
ratified Track A criterion.
"""

from __future__ import annotations

import hashlib
import json
import platform as platform_info
import subprocess
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from swingdesk.application import checklist as checklist_builder
from swingdesk.application.universe import UniverseSelection
from swingdesk.contracts.checklist import Checklist
from swingdesk.contracts.market import BarSeries as BarSeriesLike
from swingdesk.contracts.market import CorporateAction, Interval, Series
from swingdesk.contracts.observation import ObservationSeries, ParameterUse
from swingdesk.contracts.position import ActionKind, ManagementAction, Position
from swingdesk.contracts.reference import Instrument
from swingdesk.contracts.run import RunManifest, RunMode
from swingdesk.derived_observations import atr, correlation
from swingdesk.journal_evidence.journal import DecisionRecord, Journal
from swingdesk.journal_evidence.positions import PositionStore
from swingdesk.market_data import YAHOO, BarStore, VendorUnavailable, check, vendor_yahoo
from swingdesk.market_data import freshness as fresh
from swingdesk.market_data.completeness import SessionFinding
from swingdesk.platform.clock import Clock
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset
from swingdesk.reference_data import calendar as cal
from swingdesk.reference_data import classification
from swingdesk.reference_data.classification import ClassificationStore
from swingdesk.reference_data.universe import vendor_symbol
from swingdesk.trade_management import manage, portfolio
from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.trade_management.sizing import Refusal, RiskSnapshot, size_long, to_base_currency


@dataclass
class InstrumentOutcome:
    """Everything one instrument produced, and why it ended where it did."""

    instrument: Instrument
    bars: int = 0
    completeness_findings: tuple[SessionFinding, ...] = ()
    observations: ObservationSeries | None = None
    risk: RiskSnapshot | Refusal | None = None
    decision: DecisionRecord | None = None
    checklist: Checklist | None = None

    correlation: portfolio.Concentration | None = None
    """Whether this candidate duplicates an open position, and every pair that was looked at.

    `None` means the check was NOT REACHED - the candidate refused earlier, or the run had no
    position store. That is a third state, distinct from "cleared it" and from "could not measure
    it", and the report prints all three apart (`DR-006` §3).
    """

    sector: portfolio.SectorCapacity | None = None
    """Whether this candidate fits inside the sector budget, and what the book already holds there.

    `None` is the same third state `correlation` describes: not reached, rather than cleared or
    unmeasurable.
    """


@dataclass
class PositionOutcome:
    """One open position and what the run proposed for it."""

    position: Position
    action: ManagementAction | None = None
    stale: bool = False

    split: manage.SplitGuard | None = None
    """Whether a split has re-denominated prices under this position's stop (`DR-016` §7).

    `None` means the guard did not run at all - there is no position store, so there was no
    position to guard. Its own `is_unavailable` covers the different case where the guard ran and
    could not answer.
    """


@dataclass
class RunResult:
    manifest: RunManifest
    outcomes: list[InstrumentOutcome] = field(default_factory=list)
    positions: list[PositionOutcome] = field(default_factory=list)
    steps: tuple[str, ...] = ()
    universe: UniverseSelection | None = None

    capacity: portfolio.Capacity | Refusal | None = None
    """What room the book had for one more position, or why that could not be answered.

    `None` means the cap was NOT EVALUATED - no position store was passed, so the run had no way to
    know the book. That is `unavailable`, not `pass`: a gap in the system and a fact about the
    account are different claims, and collapsing them is the error `HANDOFF.md` §7 calls the most
    damaging this product can make. The report prints which of the three it was.
    """

    correlation: portfolio.CorrelationLimit | Refusal | None = None
    """The correlation cap in force for this run, or why there was none.

    The LIMIT, not a verdict - each candidate carries its own on `InstrumentOutcome.correlation`,
    because correlation is a property of a pair and not of the book. Recorded at run level for the
    one case the per-candidate field cannot express: a threshold or a lookback with no value, which
    refuses every candidate and must be reported even on a run where nothing reached step 6.
    """

    sector_limit: Decimal | Refusal | None = None
    """How much of the book may sit in one sector, or why that has no value."""

    sector_book: portfolio.SectorBook | Refusal | None = None
    """The open book split by sector - a run-level fact, unlike correlation.

    `None` means it was never computed: no position store, or no candidate reached step 6c. It
    carries its own unattributed and unclassifiable totals, so a report can say how much of the
    split it is entitled to trust.
    """

    @property
    def decisions(self) -> list[DecisionRecord]:
        return [o.decision for o in self.outcomes if o.decision is not None]

    @property
    def actionable(self) -> list[ManagementAction]:
        """Proposals needing the owner's answer before anything happens (D6)."""
        return [p.action for p in self.positions if p.action is not None and p.action.is_actionable]

    @property
    def positions_ran_first(self) -> bool:
        """The run's own record of its order, not an assertion about it.

        `CHECKLIST_SPEC` §4 requires open positions and gaps to be checked first, and a claim that
        they were is worth less than a trace showing it.
        """
        if "positions" not in self.steps or "candidates" not in self.steps:
            return "positions" in self.steps
        return self.steps.index("positions") < self.steps.index("candidates")


def _held_instrument(instrument_id: str) -> Instrument:
    """An Instrument for a position whose id is not among today's candidates.

    A position is held regardless of whether the screener still nominates it, so the run must be
    able to fetch it anyway. The exchange comes from the same symbology rule the CLI uses; nothing
    here is guessed beyond what that rule already encodes.

    The id is PRESERVED, never re-derived - it is the identity, and re-minting it here would split
    a position's history from the bars written under the universe path's id.

    The ticker is the vendor's form, and getting that from the id needs `vendor_symbol`, not a
    `.TO` strip. This is the same defect that once made `BRK.A` and `BRK.B` absent from every
    universe, "indexed as possibly delisted": the directory writes `BRK.B` and the vendor wants
    `BRK-B`. That was fixed where the universe builds instruments and missed here, so a held
    dual-class position asked for `BRK.B`, got `VendorUnavailable`, and fell through to the stored
    bars - which is worse than failing, because the position went on being managed against data
    that had quietly stopped refreshing.
    """
    base = instrument_id.upper().removesuffix(".TO")
    return Instrument(
        id=instrument_id,
        ticker=vendor_symbol(base),
        exchange=cal.exchange_for(instrument_id),
        currency=cal.currency_for(instrument_id),
    )


def _exit_policy(registry: ParameterRegistry) -> ExitPolicy | Refusal:
    """The run's exit semantics, from the registry, or a coded refusal naming what is missing.

    There used to be no such function. `ExitPolicy(Decimal("2.0"), 20)` appeared as a literal in two
    places, and the candidate path did not use it at all - it sized against `entry - 1x ATR` while
    management and the checklist used `2x ATR`. So the stop a candidate was sized on and the stop
    that would later exit it were different distances, and neither carried provenance.

    Both are hard-coded defaults for parameters the registry holds UNSET (`exit.atr_stop_multiple`,
    `exit.max_holding_period`). "Unset is not default" is a non-negotiable, and this was the one
    place in the decision path that broke it - the more quietly for the value being plausible.

    CONSEQUENCE, stated because it is large: with both parameters unset, every candidate now Skips
    with a coded refusal naming the parameter, and open positions PAUSE rather than being managed on
    an invented stop. That is the fail-closed design working, and it is the same shape the 4,486
    `risk.per_trade_pct` refusals took before that parameter was set. The run still completes, and
    every candidate still leaves with a decision and a reason code.
    """
    try:
        multiple, _ = registry.decimal_value("exit.atr_stop_multiple")
        holding, _ = registry.int_value("exit.max_holding_period")
    except ParameterUnset as unset:
        return Refusal(
            "RISK",
            "no exit policy: the ATR stop multiple and the maximum holding period are what turn an "
            "observation into a stop, and sizing against an assumed one is the silent-default this "
            "registry exists to prevent",
            parameter_id=unset.parameter_id,
        )
    return ExitPolicy(multiple, holding)


def _freshness_window(registry: ParameterRegistry) -> int | Refusal:
    """How many sessions behind is too stale to decide on, or a coded refusal naming the parameter.

    Same shape as `_exit_policy` above, for the same reason: `data.freshness_window` is a ruled
    number (`DR-015`, `assumed`), and an unset one must refuse rather than pick a plausible default.
    Read ONCE per run and passed down, so the registry is not re-read 1152 times.

    `DATA_QUALITY_SPEC` §2.1 has specified this gate since it was written and
    `calendar.sessions_behind` has implemented the measurement the whole time - with no caller. It
    was the last mutant surviving the entire suite, and it survived as dead code rather than as a
    weak test. `DR-015` supplied the number it was waiting for.
    """
    try:
        allowed = fresh.window(registry)
    except ParameterUnset as unset:
        return Refusal(
            "DATA",
            "no freshness window: how many sessions behind is too stale to decide on is a ruled "
            "number, and deciding on data of unknown age is the silent-default this registry "
            "exists to prevent",
            parameter_id=unset.parameter_id,
        )
    return allowed


def _portfolio_caps(registry: ParameterRegistry) -> portfolio.Caps | Refusal:
    """The book's two bounds, or a coded refusal naming the parameter that has no value.

    Third function of this shape in this module, and the shape is the point: `_exit_policy`,
    `_freshness_window` and this one all read a ruled number ONCE per run and hand down either the
    value or a `Refusal` carrying the parameter id. An unset cap must refuse rather than admit
    everything, because a limit nobody set is not a limit of infinity - it is a limit nobody set.

    `DR-006` §8.3 ratified both on 2026-08-22 with provenance `owner`, and until this call existed
    neither was read by any line of code (`AGENTS.md` §7).
    """
    try:
        return portfolio.limits(registry)
    except ParameterUnset as unset:
        return Refusal(
            "RISK",
            "no portfolio cap: how much open risk the book may carry and how many positions may be "
            "held at once are ruled numbers, and admitting a candidate against an unmeasured book "
            "is the silent-default this registry exists to prevent",
            parameter_id=unset.parameter_id,
        )


def _correlation_limit(registry: ParameterRegistry) -> portfolio.CorrelationLimit | Refusal:
    """The correlation cap, or a coded refusal naming the parameter that has no value.

    Fourth function of this shape, and the same reasoning: an unset threshold is not a threshold of
    infinity. Note where this refuses and where it does not - an UNSET parameter refuses every
    candidate, while a pair that could not be MEASURED admits and is reported `unavailable`
    (`DR-006` §3). Those look alike from a distance and are opposite obligations: one is the
    registry failing closed on a number nobody ruled, the other is the system declining to claim a
    check it could not perform.
    """
    try:
        return portfolio.correlation_limit(registry)
    except ParameterUnset as unset:
        return Refusal(
            "RISK",
            "no correlation cap: the r at which two names stop being independent bets, and the "
            "window it is measured over, are both authored numbers, and admitting a candidate "
            "without them would call an unchecked pair a diversified one",
            parameter_id=unset.parameter_id,
        )


def _sector_limit(registry: ParameterRegistry) -> Decimal | Refusal:
    """How much of the book may sit in one sector, or a coded refusal naming the parameter.

    Fifth function of this shape. The same rule applies and the same distinction holds: an UNSET
    limit refuses every candidate, while an instrument that could not be CLASSIFIED is admitted
    unchecked and reported `unavailable` (`DR-006` §3).
    """
    try:
        return portfolio.sector_limit(registry)
    except ParameterUnset as unset:
        return Refusal(
            "RISK",
            "no sector cap: how much of the book may sit in one sector or theme is an authored "
            "number, and admitting a candidate without it would let a concentrated book look like "
            "a diversified one",
            parameter_id=unset.parameter_id,
        )


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True,
            cwd=Path(__file__).resolve().parents[3],
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - a missing git is not a run failure
        return "unknown"


def _config_hash(registry: ParameterRegistry) -> str:
    """Hash of the resolved parameter state. Values are hashed, never recorded (SECURITY 2.5).

    The hash covers values and provenance, not merely which ids are set. An earlier version hashed
    set-ness alone, so changing a threshold left config_hash unmoved - a replay would then report a
    different output with nothing pinned having changed, and blame the decision path for what was
    really a config edit. The replay gate surfaced that the first time it was pointed at a case.
    """
    payload = json.dumps(
        {
            pid: (
                {"value": entry.get("value"), "provenance": entry.get("provenance")}
                if entry.get("value") is not None
                else None
            )
            for pid, entry in sorted(registry._entries.items())  # noqa: SLF001
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _universe_hash(selection: UniverseSelection) -> str:
    """Hash of the rule and the members it selected.

    The universe is an INPUT, so it is pinned like config is. Both halves matter: the rule alone
    would not move when the store gained bars for a newly-liquid symbol, and the member list alone
    would not move when a threshold changed on a day it happened to admit the same names.
    """
    payload = json.dumps(
        {
            "rule": {
                "min_price": str(selection.rule.min_price),
                "min_adtv": str(selection.rule.min_adtv),
                "adtv_window": selection.rule.adtv_window,
                "min_history": selection.rule.min_history,
            },
            "members": [member.instrument.id for member in selection.members],
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _trade_terms(risk: RiskSnapshot | Refusal | None) -> dict[str, str] | None:
    """The four numbers that make a proposal actionable, or None when there is no trade.

    A refusal contributes nothing here on purpose - its code is already carried on the decision, and
    a refusal has no shares, no stop and no risk to pin.
    """
    if not isinstance(risk, RiskSnapshot):
        return None
    return {
        "entry": str(risk.entry),
        "stop": str(risk.stop),
        "shares": str(risk.shares),
        "planned_risk": str(risk.planned_risk),
    }


def _output_hash(result: RunResult) -> str:
    """Hash of what the run DECIDED - including the numbers the owner would act on.

    `DETERMINISM_SPEC` 8 carried this as an open question: whether the hash covers the full trace or
    just the decisions, deferred because a full trace churns on cosmetic changes and a gate that
    cries wolf gets ignored. That concern is right, and the answer is not to hash everything. It is
    to hash what an owner would ACT ON differently: two runs that hash alike must be two runs the
    owner could not tell apart at the point of doing something.

    By that standard the previous payload - instrument, bar count, decision, reason code and latest
    ATR - was not close, and this was measured rather than reasoned about:

      - halving every candidate's share count left the hash at 78732401bd216ae2;
      - moving every stop 40% further away left it at 78732401bd216ae2;
      - a run holding an open position it proposed EXIT_NOW for hashed identically to a run holding
        no position at all, because the position half - which Appendix T requires to run FIRST - was
        absent from the payload in every form, including its own existence.

    Gate 9 passed in all four cases, and `a.reproducible` reads "reproduces byte-identically" on the
    strength of it. So the shares to buy, the stop to buy them against, the risk that entails, and
    every proposal on an open position could all change without one check noticing.

    Excluded deliberately, and this is the churn guard that keeps the gate believable: free-text
    reasons, checklists, timestamps, and `previous_decision`. Prose gets rewritten without the
    decision changing; the others are identity or context rather than something acted upon.
    """
    payload = {
        "candidates": [
            {
                "instrument": o.instrument.id,
                "bars": o.bars,
                "decision": o.decision.decision if o.decision else None,
                "code": o.decision.reason_code if o.decision else None,
                "atr": str(o.observations.observations[-1].value)
                if o.observations and o.observations.observations[-1].value is not None
                else None,
                "trade": _trade_terms(o.risk),
            }
            for o in result.outcomes
        ],
        # Present even when empty, so "no positions" and "positions not evaluated" hash apart.
        "positions": [
            {
                "position_id": p.position.position_id,
                "version": p.position.version,
                "stale": p.stale,
                "action": {
                    "kind": p.action.kind.value,
                    "code": p.action.reason_code,
                    "old_stop": str(p.action.old_stop) if p.action.old_stop is not None else None,
                    "new_stop": str(p.action.new_stop) if p.action.new_stop is not None else None,
                    "shares_affected": p.action.shares_affected,
                }
                if p.action is not None
                else None,
            }
            for p in result.positions
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


class Fetcher(Protocol):
    """What the run needs from a bar source.

    A Protocol rather than a Callable alias, because every call site passes `period` by keyword and
    a positional alias silently permitted that while describing something else. mypy found the
    mismatch: the declared type and the real contract had drifted apart with nothing to notice.
    """

    def __call__(
        self,
        instrument: Instrument,
        interval: Interval,
        knowledge_time: datetime,
        period: str | None = None,
    ) -> BarSeriesLike: ...


class ActionsFetcher(Protocol):
    """What the run needs from a corporate-actions source (`DR-016` §7).

    Separate from `Fetcher` because a split is not a bar and the vendor serves it from a different
    endpoint - the same boundary `vendor_yahoo.fetch_actions` draws.

    **Injected and defaulting to nothing.** A run given no actions fetcher does not fetch, and the
    split guard then reads whatever the store already holds. That keeps the suite offline by
    construction (CI_POLICY 4) rather than by every test remembering to stub a second vendor, and
    it makes the production wiring an explicit line in `cli.py` that a gate can be pointed at.
    """

    def __call__(
        self,
        instrument: Instrument,
        knowledge_time: datetime,
        period: str = "max",
    ) -> tuple[CorporateAction, ...]: ...


def run(
    instruments: list[Instrument],
    clock: Clock,
    registry: ParameterRegistry,
    store: BarStore,
    journal: Journal,
    *,
    mode: RunMode,
    lookback: str = "1y",
    fetcher: Fetcher | None = None,
    actions_fetcher: ActionsFetcher | None = None,
    positions: PositionStore | None = None,
    classifications: ClassificationStore | None = None,
    exits: ExitPolicy | None = None,
    universe: UniverseSelection | None = None,
) -> RunResult:
    """One pass of the daily pipeline.

    `mode` is required and keyword-only, so a caller cannot omit it and cannot pass it by accident
    in the wrong position. Deriving it from the injected clock and fetcher would be automatic and
    would re-create exactly the inference `SYSTEM_MODES.md` §3 objects to: today `swingdesk scan`
    with no `--as-of` IS the live path, and nothing said so.

    `fetcher` is injected so the suite can run offline against recorded fixtures. CI must never
    touch the network: a suite that fetches is neither deterministic nor available offline, and it
    would hammer a rate-limited free tier (CI_POLICY 4).

    `universe` supplies the candidates when `instruments` is empty - the rule-driven path
    (CHARTER 4). Passing both is allowed and means "these instruments, and here is the universe they
    were judged against", which is how a held position that has fallen out still gets evaluated.
    """
    fetch = fetcher or vendor_yahoo.fetch
    if universe is not None and not instruments:
        instruments = universe.instruments
    started = clock.now()
    # run_id and started_at are identity, not inputs - domain code never reads them, and they are
    # excluded from output_hash. So a replay under a pinned clock must still get a unique id, or
    # re-running the same as-of date would collide in the journal. The decision inputs stay pinned;
    # only the label varies.
    unique = uuid4().hex[:8]
    run_id = f"run-{started:%Y%m%dT%H%M%SZ}-{unique}"
    snapshot_id = f"snap-{started:%Y%m%dT%H%M%SZ}-{unique}"

    manifest = RunManifest(
        run_id=run_id,
        started_at=started,
        mode=mode,
        code_hash=_git("rev-parse", "--short", "HEAD"),
        code_dirty=bool(_git("status", "--porcelain")),
        config_hash=_config_hash(registry),
        snapshot_id=snapshot_id,
        calendar_version=cal.calendar_version(),
        platform=f"{platform_info.system()} python{sys.version.split()[0]}",
        component_versions={atr.COMPONENT: atr.VERSION},
        parameters=universe.parameters if universe is not None else (),
        universe_hash=_universe_hash(universe) if universe is not None else None,
    )
    journal.start_run(manifest)
    store.create_snapshot(snapshot_id, started, started, note=run_id)

    result = RunResult(manifest=manifest, universe=universe)
    steps: list[str] = []

    # One exit policy for the whole run - management, sizing and the checklist. An injected policy
    # still wins so a study can pin its own; otherwise it comes from the registry and may refuse.
    policy = exits if exits is not None else _exit_policy(registry)

    # How stale is too stale, read once for the whole run (DATA_QUALITY_SPEC 2.1, DR-015).
    #
    # WHERE THE SPEC'S "REFETCH ONCE" IS DISCHARGED, because this is a judgment and not an omission.
    # 2.1 reads "stale -> refetch once; still stale -> DATA skip", which describes a store-first
    # system that fetches on demand. This pipeline is fetch-first: every candidate and every held
    # position is fetched at the top of its own branch BEFORE anything reads the store, and since
    # DR-015 the injected fetcher retries a VendorUnavailable three times. So by the time freshness
    # is assessed below, the instrument has already had between one and three fetch attempts in this
    # run, and the refetch obligation is met by construction. Issuing another vendor call here would
    # be a second request for the same bars milliseconds after the first - 67 of them on the
    # 2026-08-17 universe - and would answer no question the first one did not.
    freshness_window = _freshness_window(registry)

    # The book's two bounds, read once for the whole run (`DR-006` §8, `RISK_SPEC` §3 step 6).
    caps = _portfolio_caps(registry)
    if isinstance(caps, Refusal):
        # Recorded on the result immediately, not only when a candidate trips it: a run where every
        # candidate refused earlier for some other reason must still report that the cap itself has
        # no value. An unset limit that nothing happened to reach is still an unset limit.
        result.capacity = caps

    # The correlation cap, read once for the whole run (`DR-006` §2, `RISK_SPEC` §3 step 6). Same
    # treatment and the same reason as the two above it.
    correlation_cap = _correlation_limit(registry)
    result.correlation = correlation_cap

    # And the sector cap. `RISK_SPEC` §3 step 6 names all three in one breath.
    sector_cap = _sector_limit(registry)
    result.sector_limit = sector_cap

    # An instrument id to its judged sector composition, memoised per run.
    #
    # `look_through` applies `DR-006` §8.7's degeneracy guard, so nothing that reaches the budget
    # below has been taken from the vendor unexamined. Note the shape of the no-store case: it is an
    # `Exposure` that is UNAVAILABLE with a reason, not an empty one - a run without a
    # classification store must report that it could not check, never that there was nothing to
    # check. Those two render identically if the distinction is dropped here, and only one of them
    # is true.
    exposures: dict[str, classification.Exposure] = {}

    def exposure_for(instrument_id: str) -> classification.Exposure:
        if instrument_id not in exposures:
            if classifications is None:
                exposures[instrument_id] = classification.Exposure(
                    instrument_id=instrument_id,
                    weights=(),
                    unavailable=(
                        "this run was given no classification store, so no instrument could be "
                        "placed in a sector"
                    ),
                )
            else:
                exposures[instrument_id] = classification.look_through(
                    classifications.as_of(instrument_id, started), instrument_id
                )
        return exposures[instrument_id]

    # Base-currency units per one unit of an instrument's currency, closed over this run's registry.
    # `sizing.to_base_currency` is the ONE place that knows the rule and the one place that refuses
    # when `account.fx_rate_cad` is unset; the portfolio module borrows it rather than owning a
    # second copy.
    # Memoised per currency: the rate depends on nothing else, and the candidate loop asks for it
    # once per instrument - 1152 times on the measured universe, for one of two answers. The book
    # is priced once for the same reason; leaving this uncached would have been inconsistent with
    # the decision three lines below it.
    rates: dict[str, tuple[Decimal, tuple[ParameterUse, ...]] | Refusal] = {}

    def rate_for(currency: str) -> tuple[Decimal, tuple[ParameterUse, ...]] | Refusal:
        if currency not in rates:
            rates[currency] = to_base_currency(currency, registry)
        return rates[currency]

    # The open book, and its price in base currency.
    #
    # `None` means NOT EVALUATED rather than empty: without a position store this run cannot know
    # what is held, and admitting candidates against an unknown book while reporting a cap would be
    # the `unavailable`-read-as-`pass` collapse (`AGENTS.md` §12). An EMPTY list is a different and
    # stronger fact - the store was read and holds nothing - and the caps then bind normally.
    open_positions: list[Position] | None = None
    priced_book: portfolio.Book | Refusal | None = None

    # Daily returns for every instrument the book holds, keyed by instrument id and built ONCE on
    # the first candidate that reaches step 6. Lazy for the same reason `priced_book` is: a run
    # where nothing sizes should not pay for reads nothing will consume. Keyed by INSTRUMENT rather
    # than by position, so two positions in one name are correlated once - which is also why a
    # candidate already in the book meets itself at r = 1 and is refused.
    book_returns: dict[str, tuple[correlation.DailyReturn, ...]] | None = None

    # --- open positions, BEFORE any candidate -------------------------------------------
    # CHECKLIST_SPEC 4 requires open positions and gaps to be checked first. Not a preference about
    # code - a data failure must never lock the owner out of managing risk on positions already
    # open (TEST_STRATEGY 6), so this phase runs before anything that can fail on fresh data.
    if positions is not None:
        steps.append("positions")
        known = {instrument.id: instrument for instrument in instruments}
        # Read ONCE and kept: the candidate path prices this same list against the caps, and a
        # second `open_as_of` would let the two halves of the run disagree about what is held.
        open_positions = positions.open_as_of(started)
        for position in open_positions:
            managed = PositionOutcome(position=position)
            result.positions.append(managed)

            # Refresh the held instrument's bars whether or not it is a candidate today. A position
            # is held regardless of whether the screener still likes it, and evaluating one against
            # the previous run's bars would manage yesterday's risk.
            #
            # Fetching is FAIL-OPEN (FAIL_CLOSED_POLICY row 1): a vendor failure falls back to the
            # last valid stored snapshot rather than blocking. Only when there is no snapshot at all
            # does the position pause - the one case where risk genuinely cannot be evaluated.
            instrument = known.get(position.instrument_id) or _held_instrument(position.instrument_id)
            try:
                refreshed = fetch(instrument, Interval.DAY, started, period=lookback)
            except VendorUnavailable:
                pass
            else:
                store.write(refreshed.bars, started)

            # Corporate actions for a HELD name, and only for a held name (`DR-016` §7, §8.5).
            #
            # Bounded work: `risk.max_concurrent_positions` is 4, so this is at most four extra
            # vendor calls an evening - which is what makes it affordable here and unaffordable
            # across a 1,148-member universe. §8.5 found the actions table holding zero rows with
            # every part of the path built; this is the caller that feeds it.
            #
            # Fail-open, exactly as the bar fetch above is: a vendor failure leaves whatever is
            # stored standing. What changes is that the run then knows it did not ask, and
            # `split_guard` reports `unavailable` rather than a clean bill of health.
            actions_refreshed = False
            if actions_fetcher is not None:
                try:
                    store.write_actions(actions_fetcher(instrument, started), started)
                except VendorUnavailable:
                    pass
                else:
                    actions_refreshed = True
            managed.split = manage.split_guard(
                position,
                store.actions_as_of(position.instrument_id, started),
                refreshed=actions_refreshed,
            )

            held = store.as_of(position.instrument_id, Interval.DAY, Series.RAW, started)
            if not held.bars:
                # No bars for a position we hold. Recorded as stale rather than skipped: the owner
                # must be told a position could not be evaluated, not left to infer it from silence.
                managed.stale = True
                managed.action = ManagementAction(
                    position_id=position.position_id, proposed_at=started,
                    kind=ActionKind.PAUSE, reason_code="DATA",
                    reason="no bars available for an open position; management cannot be evaluated",
                    old_stop=position.current_stop,
                )
            elif managed.split.alert is not None:
                # BEFORE freshness, and that ordering is the decision worth stating. A stale series
                # recovers by itself tomorrow; a split does not, and it is the one condition here
                # under which evaluating anyway produces a CONFIDENT wrong answer rather than a
                # refusal - `manage.evaluate` would read the pre-split stop as breached and propose
                # `EXIT_NOW` on a stop-out that never happened. A transient staleness must not mask
                # that for a day.
                #
                # PAUSE, and the stop is NOT adjusted. `stop_after` travels in the reason so the
                # owner can act on it; applying it here would rewrite a risk parameter they set,
                # which `CHARTER.md` A-001 reserves to them.
                managed.stale = True
                managed.action = ManagementAction(
                    position_id=position.position_id, proposed_at=started,
                    kind=ActionKind.PAUSE, reason_code="DATA",
                    reason=managed.split.alert.reason,
                    old_stop=position.current_stop,
                )
            elif isinstance(freshness_window, Refusal):
                managed.action = ManagementAction(
                    position_id=position.position_id, proposed_at=started,
                    kind=ActionKind.PAUSE, reason_code=freshness_window.code,
                    reason=f"{freshness_window.reason} ({freshness_window.parameter_id})",
                    old_stop=position.current_stop,
                )
            elif (aged := fresh.assess(
                instrument.exchange, held.bars[-1].session_date, started, freshness_window
            )).verdict is not fresh.Verdict.FRESH:
                # The gap TODO.md 1 named, now closed. Fetching here is fail-open by design
                # (FAIL_CLOSED_POLICY row 1) and `stale` was set ONLY when there were no bars at
                # all - so a position whose fetch failed went on being managed against stored bars
                # of any age, silently, and the next cause of that fallback would have looked
                # exactly like the dual-class ticker bug PR #9 fixed. Fail-open on the FETCH is
                # correct and unchanged; what changes is that deciding on what it fell back to is
                # now fail-closed, which is the distinction row 2 of section 7 draws.
                #
                # PAUSE rather than skip: a held position cannot be skipped, and it must never be
                # dropped from the run - CHECKLIST_SPEC 4 exists so a data failure can never lock
                # the owner out of managing risk on something already open. So the window's
                # DROPPED verdict lands here as a pause too; the reason says which it was.
                managed.stale = True
                managed.action = ManagementAction(
                    position_id=position.position_id, proposed_at=started,
                    kind=ActionKind.PAUSE, reason_code="DATA",
                    reason=f"{aged.reason}; management cannot be evaluated",
                    old_stop=position.current_stop,
                )
            else:
                bar = held.bars[-1]
                bars_held = sum(1 for b in held.bars if b.session_date >= position.opened_on) - 1
                observations = atr.compute(held, registry)
                latest_atr = observations.observations[-1].value
                if isinstance(policy, Refusal):
                    # A held position must never be managed against an invented stop. Pausing says
                    # so; silently applying a default would move a real stop on a guess.
                    managed.action = ManagementAction(
                        position_id=position.position_id, proposed_at=started,
                        kind=ActionKind.PAUSE, reason_code=policy.code,
                        reason=f"no exit policy; management cannot be evaluated ({policy})",
                        old_stop=position.current_stop,
                    )
                else:
                    managed.action = manage.evaluate(
                        position, bar, policy, started, bars_held=max(bars_held, 0), atr=latest_atr
                    )
            positions.propose(managed.action, run_id=run_id)

    steps.append("candidates")

    for instrument in instruments:
        outcome = InstrumentOutcome(instrument=instrument)
        result.outcomes.append(outcome)

        # 1. Source facts. Fetching is fail-open; deciding is not.
        try:
            series = fetch(instrument, Interval.DAY, started, period=lookback)
        except VendorUnavailable as unavailable:
            outcome.decision = DecisionRecord(
                instrument.id, "Skip", "DATA", str(unavailable)[:200]
            )
            continue

        store.write(series.bars, started)
        stored = store.as_of(instrument.id, Interval.DAY, Series.RAW, started)
        outcome.bars = len(stored)

        # 2. Freshness, against the calendar (DATA_QUALITY_SPEC 2.1). BEFORE completeness, which is
        # 2.2 and answers a different question - and the order matters because the two are easy to
        # mistake for each other. Completeness looks for a hole INSIDE the stored window; a series
        # that simply stops early has no hole and passes it. Measured on the 2026-08-17 run: 67 of
        # 1152 candidates were one session behind, every one of them reported `completeness clean`,
        # and every one was sized and left on Watch against a stale close.
        if isinstance(freshness_window, Refusal):
            outcome.decision = DecisionRecord(
                instrument.id, "Skip", freshness_window.code,
                freshness_window.reason, freshness_window.parameter_id,
            )
            continue
        if stored.bars:
            aged = fresh.assess(
                instrument.exchange, stored.bars[-1].session_date, started, freshness_window
            )
            if aged.verdict is not fresh.Verdict.FRESH:
                # Both verdicts refuse, and the reason distinguishes them: STALE may recover on its
                # own tomorrow, DROPPED means the run stopped trying (DR-015 2.1).
                outcome.decision = DecisionRecord(instrument.id, "Skip", "DATA", aged.reason)
                continue

        # 3. Completeness, against the calendar. This is what separates a half-day from a gap.
        # The empty-bars fallback uses the RUN's clock, not the wall clock. It read date.today()
        # until ruff's DTZ011 found it: a replay of an old manifest would have measured completeness
        # against the date of the replay, so that branch was reproducible only on the day it ran.
        # Gate 7 could not see it - `application` is not one of the pure packages it guards.
        window_start = stored.bars[0].session_date if stored.bars else started.date()
        window_end = stored.bars[-1].session_date if stored.bars else started.date()
        report = check(stored, instrument.exchange, YAHOO, window_start, window_end)
        outcome.completeness_findings = report.findings
        if not report.is_complete:
            outcome.decision = DecisionRecord(
                instrument.id, "Skip", "DATA",
                f"{len(report.findings)} incomplete session(s); first: {report.findings[0]}",
            )
            continue

        # 4. Derived observation.
        outcome.observations = atr.compute(stored, registry)
        latest = outcome.observations.observations[-1]
        if latest.value is None:
            outcome.decision = DecisionRecord(
                instrument.id, "Skip", "DATA", "warm-up incomplete; no observation emitted"
            )
            continue

        # 5. Risk. Stop derived from the observation BY THE RUN'S EXIT POLICY, then size. Stop
        # before size, always - and the same policy that will later exit the position, so the
        # distance a candidate is sized on is the distance it is actually stopped at.
        if isinstance(policy, Refusal):
            outcome.decision = DecisionRecord(
                instrument.id, "Skip", policy.code, policy.reason, policy.parameter_id
            )
            continue
        entry = stored.bars[-1].close
        stop = policy.stop_for(entry, latest.value)
        sized = size_long(entry, stop, instrument.currency, registry)
        outcome.risk = sized

        if isinstance(sized, Refusal):
            outcome.decision = DecisionRecord(
                instrument.id, "Skip", sized.code, sized.reason, sized.parameter_id
            )
            continue

        # 6. The book. `RISK_SPEC` §3's binding sequence puts portfolio checks AFTER the position
        # and liquidity caps of step 5, which live inside `size_long` - so this runs on a candidate
        # that has already been sized, and the report can show the size that did not fit.
        #
        # The book is priced ONCE per run, lazily, on the first candidate that sizes: `r_unit` is
        # 1R in base currency and comes from that candidate's own `allowed_risk`, which is
        # `account.equity` x `risk.per_trade_pct` / 100. Taking it from a snapshot the run already
        # computed keeps the sizing law in `sizing.py` and nowhere else.
        if isinstance(caps, Refusal):
            outcome.decision = DecisionRecord(
                instrument.id, "Skip", caps.code, caps.reason, caps.parameter_id
            )
            continue
        # An unset correlation threshold or lookback refuses here, OUTSIDE the position-store
        # branch below, exactly as the book cap does one line up. The reason is the same: a limit
        # with no value is a fact about the registry, and it holds whether or not this run happens
        # to know what the book contains. What the branch below governs is the MEASUREMENT, which
        # genuinely needs a book to measure against.
        if isinstance(correlation_cap, Refusal):
            outcome.decision = DecisionRecord(
                instrument.id, "Skip", correlation_cap.code, correlation_cap.reason,
                correlation_cap.parameter_id,
            )
            continue
        if isinstance(sector_cap, Refusal):
            outcome.decision = DecisionRecord(
                instrument.id, "Skip", sector_cap.code, sector_cap.reason, sector_cap.parameter_id
            )
            continue
        if open_positions is not None:
            if priced_book is None:
                priced_book = portfolio.book(open_positions, rate_for, sized.allowed_risk)
                if isinstance(priced_book, Refusal):
                    result.capacity = priced_book
            if isinstance(priced_book, Refusal):
                outcome.decision = DecisionRecord(
                    instrument.id, "Skip", priced_book.code, priced_book.reason,
                    priced_book.parameter_id,
                )
                continue

            requested = rate_for(instrument.currency)
            if isinstance(requested, Refusal):
                # Unreachable while `size_long` refuses the same instrument for the same reason,
                # and handled anyway: a caller that ever sizes without converting must not have
                # this branch silently size the book in two currencies.
                outcome.decision = DecisionRecord(
                    instrument.id, "Skip", requested.code, requested.reason, requested.parameter_id
                )
                continue
            base_per_local, _ = requested
            requested_r = sized.planned_risk * base_per_local / sized.allowed_risk

            capacity = portfolio.assess(priced_book, caps, requested_r)
            # A REFUSAL STICKS; an admission does not overwrite one.
            #
            # `requested_r` varies per candidate because the share count rounds DOWN, so on a
            # partly-full book one candidate can be refused (3.50R + 0.60R > 4R) and the next
            # admitted (3.50R + 0.40R <= 4R). Assigning unconditionally left `result.capacity`
            # holding whichever candidate happened to be evaluated last, and the report then said
            # "room for 2 more position(s)" on a run whose funnel showed RISK skips - the report
            # contradicting the decisions it was rendering.
            # `reported`, not `held` - that name already belongs to the held position's bars
            # earlier in this function, and mypy caught the reuse.
            reported = result.capacity
            if not (isinstance(reported, portfolio.Capacity) and not reported.admitted):
                result.capacity = capacity
            if not capacity.admitted:
                # NO `parameter_id`. A full book is a fact about the ACCOUNT, not an unset
                # threshold, and `funnel.py` splits skip causes on exactly that field - the
                # distinction that once let 1131 unset-parameter refusals read as a quiet day.
                outcome.decision = DecisionRecord(
                    instrument.id, "Skip", "RISK", capacity.reason
                )
                continue

            # 6b. Correlation, AFTER the book cap and inside the same step (`RISK_SPEC` §3 step 6
            # names open risk, sector risk, correlation and event exposure together). Second
            # because a full book is the cheaper and more actionable reason to report: "no room"
            # is a fact the owner can act on, while "this duplicates a position you hold" is only
            # worth saying about a candidate that would otherwise have fitted.
            if book_returns is None:
                # Read from the STORE, not from the fetch above: a held instrument is refreshed in
                # the positions phase and may also be a candidate today, and reading the store means
                # both paths correlate the same bars as of the same knowledge_time. A position whose
                # instrument has no stored bars yields an empty stream, which `measure` reports as
                # `unavailable` - it does not refuse, and it does not silently drop the position out
                # of the check.
                book_returns = {
                    position.instrument_id: correlation.daily_returns(
                        store.as_of(position.instrument_id, Interval.DAY, Series.RAW, started)
                    )
                    for position in open_positions
                }
            outcome.correlation = portfolio.assess_correlation(
                correlation.daily_returns(stored), book_returns, correlation_cap
            )
            if not outcome.correlation.admitted:
                # NO `parameter_id`, for the same reason the book cap carries none: a candidate that
                # duplicates a position is a fact about the ACCOUNT, and both thresholds have
                # values. An unset one refuses above, where it does name its parameter.
                outcome.decision = DecisionRecord(
                    instrument.id, "Skip", "RISK", outcome.correlation.reason
                )
                continue

            # 6c. Sector, the last of the three portfolio checks `RISK_SPEC` §3 step 6 names.
            # The book is split ONCE per run - it is a property of what is held, not of the
            # candidate - while the verdict is per candidate, because an ETF and a single share
            # spend that budget in completely different shapes.
            if result.sector_book is None:
                result.sector_book = portfolio.sector_book(
                    open_positions, rate_for, sized.allowed_risk, exposure_for
                )
            if isinstance(result.sector_book, Refusal):
                outcome.decision = DecisionRecord(
                    instrument.id, "Skip", result.sector_book.code, result.sector_book.reason,
                    result.sector_book.parameter_id,
                )
                continue
            outcome.sector = portfolio.assess_sector(
                result.sector_book, sector_cap, exposure_for(instrument.id), requested_r
            )
            if not outcome.sector.admitted:
                outcome.decision = DecisionRecord(
                    instrument.id, "Skip", "RISK", outcome.sector.reason
                )
                continue

        outcome.decision = DecisionRecord(instrument.id, "Watch", None,
                                          "sized; awaiting a trigger")

    # from_state (TRANSITION_SPEC 4). Read as of the run's START, so it reports what the journal
    # said before this run touched it. Every other field on the record says what the candidate
    # BECAME; without this one a Skip that was a Watch yesterday reads like a Skip that has been a
    # Skip all week. Not part of output_hash - it describes what the run knew, not what it decided,
    # and a replay against an empty journal correctly finds nothing.
    previously = journal.latest_decisions([o.instrument.id for o in result.outcomes], started)
    for outcome in result.outcomes:
        was = previously.get(outcome.instrument.id)
        if outcome.decision is not None and was is not None:
            outcome.decision = replace(outcome.decision, previous_decision=was)

    # The pre-trade checklist is generated for every candidate that reached a decision - including
    # a Skip, because a skipped candidate's checklist is what makes the skip reviewable.
    for outcome in result.outcomes:
        if outcome.decision is None:
            continue
        outcome.checklist = checklist_builder.generate(
            outcome.instrument, run_id, started, risk=outcome.risk, decision=outcome.decision,
            # A refused policy is no policy: the checklist reports the exit item UNAVAILABLE rather
            # than describing a stop the run never adopted.
            exits=None if isinstance(policy, Refusal) else policy, universe=universe,
        )

    result.steps = tuple(steps)
    journal.record_decisions(run_id, clock.now(), result.decisions)

    output_hash = _output_hash(result)
    journal.complete_run(run_id, output_hash, clock.now())
    result.manifest = manifest.model_copy(
        update={"output_hash": output_hash, "completed_at": clock.now()}
    )
    return result
