"""Selection without the universe in memory - phase A of the loader plan.

**Why this exists.** `PR-018` ran for about fifty minutes and held 23.4 GB when it was measured; a
query-plus-construction estimate predicted 3.6 minutes. The gap is memory: every study loads every
series, keeps all of them for the whole run, and the machine pages. The only phase with a real reason
to see many instruments at once is the cross-sectional ranking, and on 2026-09-12 it was checked:

* `ByMarketPathStrength` scores each candidate from **its own series and the benchmark alone** -
  `ranking._beat_share(series, index, lookback, benchmark_daily)`;
* it then orders the scores with `ranking._ordered`: highest first, ties broken on instrument id,
  a total order.

**So the cross-section needs SCORES at once, never series.** Pass A reads one instrument, keeps
`{formation date: score}` and drops the series; pass B sorts scores per date. Peak memory is one
series plus a few megabytes of decimals.

**Nothing here re-implements the ranking.** The score is `_beat_share` and the order is `_ordered`,
imported from the live module, so the streamed and in-memory paths cannot drift apart except in the
loop around them - and `tests/test_stream_selection.py` holds that loop to the in-memory one, date by
date, on series built to produce ties.

**Two details that decide whether the two paths agree, both carried deliberately:**

* **an unscored candidate still counts toward the pool.** `select` takes `int(len(ordered) * decile)`
  over every admitted candidate, `UNSCORED` ones included, so dropping them would shrink the decile;
* **a thin date is skipped before anything is recorded**, as the in-memory loop does, so it adds to
  neither the selected nor the every-name entry sets.

**Not yet used by any study.** Adopting it in a runner is a separate change, and that change must
first reproduce a committed study to the digit - `PR-018`'s §9 check is the obvious one.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_momentum_horizon import RULE
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.decision_logic.ranking import UNSCORED, _beat_share, _ordered
from swingdesk.market_data import BarStore
from swingdesk.reference_data import universe as rules


@dataclass
class Selection:
    """What the in-memory loop in `run_pr016`..`run_pr019` produces, in the same shapes."""

    selected: dict[str, list[date]] = field(default_factory=dict)
    everything: dict[str, list[date]] = field(default_factory=dict)
    thin: int = 0


@dataclass(frozen=True, slots=True)
class _Named:
    """A record `ranking.Ranked` accepts, carrying only what `_ordered` reads and the date it is for.

    Not `run_pr014.Candidate`: that one lacks `session_date`, which `Ranked` requires, and mypy
    refuses it here as it refuses it in `run_pr014.select` itself. `_ordered` reads only
    `instrument_id`; the index is the position the score was computed at, already spent.
    """

    instrument_id: str
    index: int
    session_date: date


def score_instrument(
    series: BarSeries,
    formations: list[date],
    benchmark_daily: Mapping[date, Decimal],
    lookback: int,
    rule: rules.LiquidityRule = RULE,
) -> dict[date, Decimal]:
    """Every formation date this name is ADMITTED on, with its score there.

    `UNSCORED` where `_beat_share` cannot answer, never omitted: the candidate is still in the pool
    the decile is sized from.
    """
    admitted = _admitted_dates(series, rule, formations)
    position = {bar.session_date: i for i, bar in enumerate(series.bars)}
    scores: dict[date, Decimal] = {}
    for session in sorted(admitted):
        value = _beat_share(series, position[session], lookback, benchmark_daily)
        scores[session] = UNSCORED if value is None else value
    return scores


def select_streamed(
    scores: Mapping[str, Mapping[date, Decimal]],
    formations: Iterable[date],
    decile: Decimal,
    min_names: int = MIN_NAMES_PER_DATE,
) -> Selection:
    """Pass B: the cross-section at each formation date, from scores alone."""
    pools: dict[date, list[str]] = defaultdict(list)
    for name in sorted(scores):
        for session in scores[name]:
            pools[session].append(name)

    out = Selection()
    for session in formations:
        pool = pools.get(session, [])
        if len(pool) < min_names:
            out.thin += 1
            continue
        for name in pool:
            out.everything.setdefault(name, []).append(session)
        ordered = _ordered([(scores[name][session], _Named(name, 0, session)) for name in pool])
        size = int(len(ordered) * decile)
        for candidate in ordered[:size] if size >= 1 else []:
            out.selected.setdefault(candidate.instrument_id, []).append(session)
    return out


def scores_from_store(
    store: BarStore,
    names: Iterable[str],
    as_of: datetime,
    formations: list[date],
    benchmark_daily: Mapping[date, Decimal],
    lookback: int,
    min_bars: int,
) -> dict[str, dict[date, Decimal]]:
    """Pass A against the store: one series in memory at a time.

    `min_bars` is the same length filter every runner applies before a series is kept, so a name
    the in-memory loop would never have loaded is not scored here either.
    """
    out: dict[str, dict[date, Decimal]] = {}
    for name in names:
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series is None or len(series.bars) < min_bars:
            continue
        got = score_instrument(series, formations, benchmark_daily, lookback)
        if got:
            out[name] = got
    return out
