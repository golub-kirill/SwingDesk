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


def daily_returns(series: BarSeries) -> dict[date, Decimal]:
    """Every session's return against the previous STORED bar, keyed by session.

    Public because the benchmark's map is built once per ranking call rather than once per
    candidate, and because `PR-012`'s prefix-sum optimisation must build the same thing to be
    comparable with the reference below.
    """
    out: dict[date, Decimal] = {}
    for index in range(1, len(series.bars)):
        previous = series.bars[index - 1].close
        if previous > 0:
            out[series.bars[index].session_date] = (
                (series.bars[index].close - previous) / previous
            )
    return out


def _beat_share(series: BarSeries, index: int, lookback: int,
                benchmark_daily: Mapping[date, Decimal]) -> Decimal | None:
    """Share of the name's last `lookback` sessions whose return beat the benchmark's.

    **Not a function of the endpoint return**, which is the whole point: it is the form `DR-018`
    section 2 measured escaping the identity that makes a point-to-point market comparison
    decorative.

    **The window is the NAME's, and that is a decision.** An earlier version also required the
    benchmark to hold `lookback` bars of its own and intersected the two positional windows, so a
    gappy benchmark shrank or erased a candidate's score. That makes the score depend on the
    benchmark's bar count, which is not a property of the candidate and not what `rs.lookback`
    means. Found 2026-08-24 by `tests/test_run_pr012.py`, which set the fast path against this
    function on deliberately gappy series and caught them disagreeing.

    A session with no benchmark return is not counted - neither as a win nor as a loss. It is
    unanswerable, and folding it into either would be the `UNKNOWN`-becomes-a-verdict collapse.
    """
    if index - lookback < 0 or index >= len(series.bars):
        return None
    wins = 0
    compared = 0
    for offset in range(index - lookback + 1, index + 1):
        previous = series.bars[offset - 1].close
        if previous <= 0:
            return None
        benchmark = benchmark_daily.get(series.bars[offset].session_date)
        if benchmark is None:
            continue
        compared += 1
        if (series.bars[offset].close - previous) / previous > benchmark:
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
        # Built once per call rather than once per candidate. The benchmark is one series and every
        # candidate compares against the same map.
        benchmark_daily = daily_returns(self.benchmark)
        scored: list[tuple[Decimal, Candidate]] = []
        for candidate in candidates:
            series = self.series.get(candidate.instrument_id)
            value = None
            if series is not None:
                value = _beat_share(series, candidate.index, self.lookback, benchmark_daily)
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
    "daily_returns",
]
