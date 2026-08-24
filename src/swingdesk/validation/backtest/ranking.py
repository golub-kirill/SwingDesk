"""Rankings a study can pin: the four forms `DR-018` characterised, plus the control they need.

`book.run_book` takes a `Ranking` and has no default, because falling back to whatever order the
system happens to have is an alphabetical bias silently applied. These are the implementations a
study chooses from. **None of them is proposed here** - `AGENTS.md` section 8 governs proposing a
rule, and `ALLOCATION_SPEC` section 3 sends an ordering adopted from the course to a
pre-registration. This module is machinery; the pre-registration picks the arm.

**Why `ByRawReturn` exists and must be in every study that uses the others.** `DR-018` section 1
proved that on a single cross-section a MARKET benchmark cannot change a ranking: its return is one
constant for every name that day, so dividing by it is a strictly monotone transform of the name's
own return. Point-to-point relative strength against an index IS raw return. So a study that ranked
by it and reported an edge would be reporting momentum under another name, and the only way to know
is to run momentum as an arm. Measured: sector-relative reads Spearman 0.75-0.82 against raw return
and the market path form about 0.6, so both depart - but neither is evidence until the control says
what plain momentum did on the same book.

**No look-ahead, and the type system is what enforces it.** A `Candidate` carries `index`, the
instrument's own bar index at the decision session, and every score here reads
`series.bars[:index + 1]`. A ranking is handed the candidates, never the future.

**A total order is mandatory.** Every ranking below breaks ties on `instrument_id`, because two
candidates that compare equal would otherwise leave the book depending on dictionary order and a
re-run would not be a re-run (`DETERMINISM_SPEC` 3.2).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from swingdesk.contracts.market import BarSeries
from swingdesk.validation.backtest.book import Candidate

#: A score no ranking can produce, used to sort a name that cannot be scored to the BOTTOM rather
#: than dropping it. A dropped candidate is an unrecorded exclusion; a bottom-ranked one competes
#: and loses, which is a different and honest claim.
UNSCORED = Decimal(-10**9)


def _window_return(series: BarSeries, index: int, lookback: int) -> Decimal | None:
    """Price return over `lookback` sessions ending at `index`. None when the window is short.

    Reads `bars[index - lookback]` through `bars[index]` and nothing beyond. `None` means the rule
    had nothing to answer with, which is not the same as a return of zero.
    """
    start = index - lookback
    if start < 0 or index >= len(series.bars):
        return None
    first = series.bars[start].close
    if first <= 0:
        return None
    return (series.bars[index].close - first) / first


def _beat_share(series: BarSeries, index: int, lookback: int,
                benchmark: BarSeries, benchmark_index: int) -> Decimal | None:
    """Share of sessions in the window whose daily return beat the benchmark's. Path-dependent.

    **Not a function of the endpoint return**, which is the whole point: it is the form `DR-018`
    section 2 measured escaping the identity that makes a point-to-point market comparison
    decorative.

    Both series are walked over their OWN indices, so a name that did not trade on a session the
    benchmark did is compared over the sessions they share rather than being silently misaligned.
    """
    if index - lookback < 0 or benchmark_index - lookback < 0:
        return None
    by_session: dict[date, Decimal] = {}
    for offset in range(index - lookback + 1, index + 1):
        previous = series.bars[offset - 1].close
        if previous <= 0:
            return None
        by_session[series.bars[offset].session_date] = (
            (series.bars[offset].close - previous) / previous
        )
    wins = 0
    compared = 0
    for offset in range(benchmark_index - lookback + 1, benchmark_index + 1):
        previous = benchmark.bars[offset - 1].close
        if previous <= 0:
            return None
        session = benchmark.bars[offset].session_date
        own = by_session.get(session)
        if own is None:
            continue
        compared += 1
        if own > (benchmark.bars[offset].close - previous) / previous:
            wins += 1
    if compared == 0:
        return None
    return Decimal(wins) / Decimal(compared)


def _ordered(scored: list[tuple[Decimal, Candidate]]) -> list[Candidate]:
    """Highest score first, ties broken on instrument_id. A total order, always."""
    return [
        candidate for _, candidate in
        sorted(scored, key=lambda pair: (-pair[0], pair[1].instrument_id))
    ]


@dataclass(frozen=True, slots=True)
class ByRawReturn:
    """Plain momentum over `lookback` sessions. **The control every other arm needs.**

    `DR-018` section 1: a market point-to-point relative strength ranks IDENTICALLY to this, so a
    study running one of those without running this cannot tell an edge from momentum.
    """

    series: Mapping[str, BarSeries]
    lookback: int

    def __call__(self, candidates: list[Candidate]) -> list[Candidate]:
        scored: list[tuple[Decimal, Candidate]] = []
        for candidate in candidates:
            series = self.series.get(candidate.instrument_id)
            value = None if series is None else _window_return(
                series, candidate.index, self.lookback
            )
            scored.append((UNSCORED if value is None else value, candidate))
        return _ordered(scored)


@dataclass(frozen=True, slots=True)
class ByMarketPathStrength:
    """Share of sessions the name beat `rs.benchmark`. The form that escapes `DR-018`'s identity.

    Measured at Spearman ~0.6 against a raw-return ranking, so it is a genuinely different signal -
    and it is the form in which the CHOICE of index matters (SPY against QQQ at 0.616 on 63
    sessions). It is not proposed; a pre-registration picks it or does not.
    """

    series: Mapping[str, BarSeries]
    benchmark: BarSeries
    lookback: int

    def __call__(self, candidates: list[Candidate]) -> list[Candidate]:
        by_session = {bar.session_date: index for index, bar in enumerate(self.benchmark.bars)}
        scored: list[tuple[Decimal, Candidate]] = []
        for candidate in candidates:
            series = self.series.get(candidate.instrument_id)
            benchmark_index = by_session.get(candidate.session_date)
            value = None
            if series is not None and benchmark_index is not None:
                value = _beat_share(
                    series, candidate.index, self.lookback, self.benchmark, benchmark_index
                )
            scored.append((UNSCORED if value is None else value, candidate))
        return _ordered(scored)


@dataclass(frozen=True, slots=True)
class BySectorRelativeStrength:
    """Return over `lookback`, divided by the name's own sector's return over the same window.

    **A per-name denominator, which is why it can reorder** where a market one cannot - `DR-018`
    section 7, Spearman 0.75-0.82 against raw return.

    `sector_return` is supplied by the caller rather than computed here, and that is a boundary
    rather than laziness: the sector's mean depends on which names are in the universe, which is a
    study's decision and not this module's. It takes the decision session and returns a return per
    sector, computed from bars up to that session and no further.

    A name with no sector, or whose sector has no return that session, scores `UNSCORED` and sorts
    to the bottom. It competes and loses rather than disappearing.
    """

    series: Mapping[str, BarSeries]
    sector_of: Mapping[str, str]
    sector_return: Callable[[date], Mapping[str, Decimal]]
    lookback: int

    def __call__(self, candidates: list[Candidate]) -> list[Candidate]:
        scored: list[tuple[Decimal, Candidate]] = []
        sessions = {candidate.session_date for candidate in candidates}
        returns = {session: self.sector_return(session) for session in sessions}
        for candidate in candidates:
            series = self.series.get(candidate.instrument_id)
            sector = self.sector_of.get(candidate.instrument_id)
            own = None if series is None else _window_return(
                series, candidate.index, self.lookback
            )
            benchmark = returns[candidate.session_date].get(sector) if sector else None
            value = None
            if own is not None and benchmark is not None and benchmark != -1:
                value = (1 + own) / (1 + benchmark)
            scored.append((UNSCORED if value is None else value, candidate))
        return _ordered(scored)


__all__ = [
    "UNSCORED",
    "ByMarketPathStrength",
    "ByRawReturn",
    "BySectorRelativeStrength",
]
