"""Building the tradeable universe from a rule instead of from a list.

`CHARTER.md` §4 wants the daily run to start from a *rule*. DR-003 fixes the rule's numbers;
`reference_data.universe` implements the test; this module is what joins the two stores that answer
it - the symbol directory (who is listed) and the bar store (who is liquid).

The join lives here rather than in `reference_data` because `reference_data` sits below
`market_data` in the dependency law, and a calendar package that could read bars would be the exact
inversion `DEPENDENCY_LAW.md` forbids.

**The honest part of this module is `coverage`.** The directory names roughly 13,000 eligible US
symbols; the store holds bars for whatever has been fetched so far. A universe computed from the
second while claiming to be computed from the first would be a survivorship filter of our own
making - "liquid" would silently mean "liquid, among the ones we happened to fetch". So the
selection carries both counts, the report prints them, and a partial universe says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from swingdesk.contracts.market import Interval, Series
from swingdesk.contracts.observation import ParameterUse
from swingdesk.contracts.reference import Instrument
from swingdesk.market_data import BarStore
from swingdesk.platform.parameters import ParameterRegistry, ParameterUnset
from swingdesk.reference_data import universe as rules
from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.trade_management.sizing import Refusal

#: The ADTV averaging window, in sessions. Encoded in the parameter's own id -
#: `universe.min_adtv_20d` is a 20-day figure - and fixed by DR-003. Changing one without the
#: other is a defect, which is why the window is not separately configurable.
ADTV_WINDOW = 20


@dataclass(frozen=True, slots=True)
class Membership:
    """One admitted instrument, with the measurements that admitted it.

    The numbers travel with the member because E02 has to say *why* something is in the universe,
    and re-deriving them at report time would be a second computation that could disagree.
    """

    instrument: Instrument
    close: Decimal
    adtv: Decimal
    bars: int


@dataclass(frozen=True, slots=True)
class UniverseSelection:
    """The universe as of one instant, with the evidence for how complete it is."""

    as_of: datetime
    rule: rules.LiquidityRule
    parameters: tuple[ParameterUse, ...]
    directory_pull: datetime | None
    eligible: int
    measured: int
    members: tuple[Membership, ...]
    capped_from: int | None = None

    @property
    def instruments(self) -> list[Instrument]:
        return [member.instrument for member in self.members]

    @property
    def by_id(self) -> dict[str, Membership]:
        return {member.instrument.id: member for member in self.members}

    @property
    def coverage(self) -> Decimal:
        """Share of eligible symbols the store could actually answer for."""
        if not self.eligible:
            return Decimal(0)
        return (Decimal(self.measured) / Decimal(self.eligible)).quantize(Decimal("0.0001"))

    @property
    def is_partial(self) -> bool:
        """True when the store has not seen every eligible symbol.

        A partial universe is usable - it is what a tiered refresh produces on the way up - but it
        is not the rule's answer, and anything computed from it inherits that.
        """
        return self.measured < self.eligible


BuiltRule = tuple[rules.LiquidityRule, tuple[ParameterUse, ...]]


def rule_from_registry(registry: ParameterRegistry) -> BuiltRule | Refusal:
    """Build the DR-003 rule from the registry, or refuse.

    Fail-closed: an unset threshold produces a refusal naming it, never a default. A universe built
    on a guessed liquidity floor would put every downstream result on an unrecorded assumption.
    """
    try:
        min_price, price_use = registry.decimal_value("universe.min_price")
        min_adtv, adtv_use = registry.decimal_value("universe.min_adtv_20d")
        min_history, history_use = registry.int_value("universe.min_bar_history")
    except ParameterUnset as unset:
        return Refusal(
            code="UNIVERSE",
            reason="the liquidity rule cannot be built; universe construction refuses rather than "
                   "admitting everything",
            parameter_id=unset.parameter_id,
        )

    rule = rules.LiquidityRule(
        min_price=min_price,
        min_adtv=min_adtv,
        adtv_window=ADTV_WINDOW,
        min_history=min_history,
    )
    return rule, (price_use, adtv_use, history_use)


def select(
    directory: DirectoryStore,
    store: BarStore,
    rule: rules.LiquidityRule,
    as_of: datetime,
    *,
    parameters: tuple[ParameterUse, ...] = (),
    limit: int | None = None,
) -> UniverseSelection:
    """Instruments the rule admits as of `as_of`, from bars known at `as_of`.

    Both stores are read as-of, so a run pinned to a past instant gets that instant's directory and
    that instant's bars. Using today's listings to filter an older window is survivorship bias with
    extra steps, and it is the specific mistake DR-003 was written to avoid.
    """
    entries = directory.as_of(as_of, eligible_only=True)
    # Every instrument's ADTV window and true bar count, in ONE query. The rule reads three things
    # off a series - how many bars it has, its last close, and the mean dollar volume over the last
    # `adtv_window` of them - and this used to read the whole stored history per instrument to
    # answer them. On the ten-year store that was 3.57 million bars, 3,720 queries and 73 seconds,
    # of which 99.4% was discarded (`BarStore.tails`).
    #
    # It also narrows `measured` by one edge case, named because a silent change to a reported
    # coverage number is the kind of thing this project counts as a defect. `instrument_ids` asked
    # only whether the store held ANY bar for a symbol; `tails` asks whether it holds DAILY RAW
    # bars, which is what the rule reads. An instrument with only hourly bars used to be counted as
    # measured and then rejected, which reported coverage the rule could not actually deliver. No
    # such instrument exists today - the two agree at 3,718 of 13,136 eligible, measured
    # 2026-08-24 - and the narrower reading is the honest one if one ever does.
    tails = store.tails(Interval.DAY, Series.RAW, as_of, rule.adtv_window)

    members: list[Membership] = []
    measured = 0
    for entry in entries:
        instrument = rules.to_instrument(entry)
        found = tails.get(instrument.id)
        if found is None:
            continue
        bars, series = found
        measured += 1

        # `history` is the stored series' full length; `series` is its tail. The alternative -
        # letting the rule infer the count from the tail - would silently fail `min_history` for
        # every instrument in the universe.
        if not rule.admits(series, history=bars):
            continue
        adtv = rules.average_dollar_volume(series, rule.adtv_window)
        if adtv is None:  # unreachable while admits() requires a full window; belt and braces
            continue
        members.append(
            Membership(
                instrument=instrument,
                close=series.bars[-1].close,
                adtv=adtv,
                bars=bars,
            )
        )

    # Sorted by id, not by liquidity. An unordered collection feeding the run is the classic source
    # of silent non-determinism (DETERMINISM_SPEC 3.2), and ordering by ADTV would quietly turn a
    # membership rule into a ranking the moment anyone truncated the list.
    members.sort(key=lambda member: member.instrument.id)

    capped_from: int | None = None
    if limit is not None and len(members) > limit:
        # Truncation IS a ranking, so it is done explicitly and recorded. The rule says who is
        # admissible; a cap says who we had time for, and the two must never be confused.
        capped_from = len(members)
        members = sorted(members, key=lambda m: m.adtv, reverse=True)[:limit]
        members.sort(key=lambda member: member.instrument.id)

    return UniverseSelection(
        as_of=as_of,
        rule=rule,
        parameters=parameters,
        directory_pull=directory.latest_pull(as_of),
        eligible=len(entries),
        measured=measured,
        members=tuple(members),
        capped_from=capped_from,
    )


__all__ = ["ADTV_WINDOW", "Membership", "UniverseSelection", "rule_from_registry", "select"]
