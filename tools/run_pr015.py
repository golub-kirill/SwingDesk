"""`PR-015`: at a twenty-session hold, does ANY long-only selection signal earn a net excess?

Registered 2026-09-07 and committed before this file existed, which is the evidence that the plan
predates the data (`PREREG_TEMPLATE` §3 rule 1). Read
`docs/prereg/PR-015-twenty-session-long-only-screen.md` first; this implements it and decides
nothing on its own.

**What makes this study different from every one before it: it varies the SIGNAL.** `PR-013`,
`PR-014` and every exploratory sweep here hold one family - relative strength, in one form or
another - and vary the horizon, the construction, the universe or the cost. `PR-014` is what makes
the question ripe rather than speculative: corrected on 2026-09-07, it found the ratified rule earns
nothing that replicates on a holdout at ANY hold from one month to a year. That removes the horizon
as an explanation and leaves the signal.

**The book is FOUR positions, not a decile** - amendment A-2, owner instruction 2026-09-07.
`risk.max_concurrent_positions` is 4, `status: owner`, and `screen.relative_strength_rule`'s own
registry note has said the consequence since `DR-030`: *"the top decile is ~110 and
`risk.max_concurrent_positions` (4) binds LONG before it does, so this value picks who is ELIGIBLE
and the ratified caps pick who is TAKEN."* Four positions, each held 20 sessions, entered 5 sessions
apart so exactly one slot frees per rebalance. A freed slot takes the best eligible name not already
held, or stays EMPTY.

**The 5-session entry grid is an APPROXIMATION**, declared in A-2: the live pipeline scans every
session and would enter whenever a slot happened to be free. Even spacing is the standard
overlapping-portfolio construction and it is what is computable here - ranking ~1,300 names takes
twenty minutes at 313 dates and a daily grid is 2,500. It costs realism about ENTRY TIMING, not
about the cap.

**Four things this file has to get right, and none of them raises when wrong.**

**0. The cost is annualised by the STEP, not by the holding period.** The book rebalances every 5
sessions and holds each position 20; using 20 divides the cost by four, does it to every arm
equally, and leaves a table in which nothing looks wrong.

**1. Every arm runs on ONE cross-section.** The five signals need different amounts of history -
126 sessions for the path form, 252 for momentum-with-skip - and admitting each name to the arms it
happens to have history for would compare five signals on five populations. The floor is the MAXIMUM
over the five, applied once, so a difference between arms is a difference between signals.

**2. Cost comes from MEASURED turnover.** `PR-014` charged `252/horizon` full book turns a year -
gross - and its ACCEPT did not survive the correction. Measured for the incumbent at this horizon:
37.2% of the book bought per rebalance, 2.35% a year, against 6.30% charged. `annual_cost` is
imported from `measure_decile_persistence.py` rather than restated, so the study and the cost input
cannot drift.

**3. The name split has to be STABLE.** Python's builtin `hash()` is salted per process, so a split
built on it would differ between runs and would not be a split. SHA-256, as §5a registers.

    PYTHONPATH=$PWD/src python tools/run_pr015.py --data <store>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_decile_persistence import annual_cost
from measure_momentum_horizon import RULE
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates
from run_pr014 import (
    BENCHMARK,
    DECILE,
    Candidate,
    book_return,
    moving_block_bootstrap,
    period_return,
    select,
    turnover,
)
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.decision_logic.ranking import ByMarketPathStrength
from swingdesk.market_data import BarStore

#: `exit.max_holding_period`, `assumed:DR-012`. The top of the owner's 14-20 band and the value the
#: system would actually trade. ONE horizon: PR-014 answered the horizon question.
HORIZON = 20

#: `risk.max_concurrent_positions`, value 4, `status: owner`, read by
#: `trade_management.portfolio:limits`. **The book, not the decile** - amendment A-2, owner
#: instruction 2026-09-07. `screen.relative_strength_rule`'s own registry note has said it since
#: DR-030: at ~1,100 admitted names the top decile is ~110 and this cap binds long before it does,
#: so the decile picks who is ELIGIBLE and this picks who is TAKEN.
MAX_CONCURRENT = 4

#: Sessions between rebalances: `HORIZON / MAX_CONCURRENT`. Exactly one slot frees each time, so
#: the four positions overlap evenly and each is held its full HORIZON.
STEP = HORIZON // MAX_CONCURRENT

#: §8's power floor, fixed before any number exists. A four-name book is noisy and `PR-012` refused
#: a verdict on one; an interval wider than this end to end could not have detected an edge worth
#: trading, so a null read off it is evidence of nothing.
POWER_FLOOR = Decimal("0.50")

#: The end of the PRIMARY window. Inherited from `PR-014` rather than chosen here, so that no split
#: was picked to suit a result.
PRIMARY_END = date(2021, 12, 31)

#: `rs.lookback`, ratified `owner` via `DR-030`. Used by the PATH_126 arm only.
LOOKBACK = 126

#: The longest history any arm needs (MOM_252_21 and HIGH_52W). Applied to EVERY arm - see the
#: module docstring, point 1.
HISTORY = 252

SLIPPAGE_BPS = Decimal("25")
STRESS_MULTIPLE = 3
BOOTSTRAP_SEED = 20260907
BOOTSTRAP_RESAMPLES = 10_000
#: The book overlaps MAX_CONCURRENT deep by construction, so consecutive returns share all but one
#: position and the dependence spans that many rebalances. Six covers four with a margin.
BLOCK = 6
MIN_REBALANCES = 24


def half_of(instrument_id: str) -> str:
    """`A` or `B`, from SHA-256 of the id. §5a registers this function by name and for a reason.

    Python's builtin `hash()` is salted per process for str, so a split built on it would land
    differently on every run and the "holdout" would be a fresh random sample each time - which
    looks exactly like a split and protects against nothing.
    """
    return "A" if hashlib.sha256(instrument_id.encode()).digest()[0] % 2 == 0 else "B"


def reversal_21(series: BarSeries, index: int) -> Decimal | None:
    """MINUS the trailing 21-session return. The top decile is last month's biggest LOSERS.

    The one arm here whose sign is opposite to everything this repository has measured.
    `README.md` has cited Jegadeesh (1990) and Lehmann (1990) since August - holds of a month or
    less sit inside the window where the literature documents reversal - and no study here has ever
    ranked in that direction.
    """
    value = period_return(series, index - 21, index)
    return None if value is None else -value


def high_52w(series: BarSeries, index: int) -> Decimal | None:
    """Close over the highest high of the trailing 252 sessions. Top decile = nearest its high."""
    if index < HISTORY or index >= len(series.bars):
        return None
    window = series.bars[index - HISTORY + 1: index + 1]
    peak = max(bar.high for bar in window)
    if peak <= 0:
        return None
    return series.bars[index].close / peak


def lowvol_126(series: BarSeries, index: int) -> Decimal | None:
    """MINUS the standard deviation of the trailing 126 daily returns. Top decile = calmest."""
    if index < LOOKBACK or index >= len(series.bars):
        return None
    closes = [bar.close for bar in series.bars[index - LOOKBACK: index + 1]]
    returns = [
        (closes[i] / closes[i - 1]) - 1 for i in range(1, len(closes)) if closes[i - 1] > 0
    ]
    if len(returns) < 2:
        return None
    return -Decimal(str(statistics.pstdev([float(r) for r in returns])))


def mom_252_21(series: BarSeries, index: int) -> Decimal | None:
    """The return from t-252 to t-21 - momentum with the standard skipped month.

    Jegadeesh & Titman (1993) skip the most recent month precisely because it carries the reversal
    the arm above is built on. This repository has measured 252-session POINT-TO-POINT momentum
    with no skip, and 126-session path strength, and never this.
    """
    return period_return(series, index - HISTORY, index - 21)


#: The four signals with no component, and the live class that has one. A callable per arm, so the
#: study cannot accidentally price one arm differently from another.
SCORERS = {
    "REVERSAL_21": reversal_21,
    "HIGH_52W": high_52w,
    "LOWVOL_126": lowvol_126,
    "MOM_252_21": mom_252_21,
}
ARMS = ("PATH_126", *sorted(SCORERS))


def rank_by(
    arm: str,
    candidates: list[Candidate],
    series_by_name: dict[str, BarSeries],
    benchmark: BarSeries,
) -> list[str]:
    """The top decile under one arm's signal, or `[]` when the cross-section cannot be scored.

    `PATH_126` goes through `select` and the LIVE `ByMarketPathStrength`, for `PR-014` amendment
    A-2's reason: a study that reimplements the ratified rule can drift from it. The other four have
    no component and are scored here - declared in §5 as a reimplementation risk, and the reason a
    win by one of them means "build a component", not "change a parameter".
    """
    if arm == "PATH_126":
        ranker = ByMarketPathStrength(
            series=series_by_name, benchmark=benchmark, lookback=LOOKBACK
        )
        top, _ = select(ranker, candidates, DECILE)
        return top
    scorer = SCORERS[arm]
    scored: list[tuple[Decimal, str]] = []
    for candidate in candidates:
        value = scorer(series_by_name[candidate.instrument_id], candidate.index)
        if value is not None:
            scored.append((value, candidate.instrument_id))
    size = int(len(scored) * DECILE)
    if size < 1:
        return []
    # Sorted by score descending, ties broken by id so the selection is deterministic and does not
    # depend on the order names came out of the store.
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [name for _, name in scored[:size]]


def fill(held: list[str], eligible: list[str], cap: int) -> list[str]:
    """The book after one rebalance: keep what is still open, refill the freed slot from `eligible`.

    **This is the whole of amendment A-2 in six lines, and every clause is load-bearing.**

    * `held` is what the previous `cap - 1` rebalances opened and have not yet aged out. The caller
      drops the oldest before calling, because a position reaches `exit.max_holding_period` on a
      schedule and not because a better name appeared.
    * The freed slot takes the highest-ranked eligible name **not already held**. Taking the
      highest-ranked name outright would let one name occupy two slots, which is a bigger bet than
      the cap permits and would quietly concentrate the book.
    * If no eligible name is free, **the slot stays EMPTY.** The owner's instruction is explicit -
      *"or non-overlapping if there is no good place"* - and filling it with the next name down
      would be the study answering a question nobody asked.

    Returns the book in age order, oldest first, so the caller can drop the oldest next time.
    """
    if len(held) >= cap:
        return list(held)
    for name in eligible:
        if name not in held:
            return [*held, name]
    return list(held)


def capped_return(
    held: list[str],
    series_by_name: dict[str, BarSeries],
    index_of: dict[str, dict[date, int]],
    start: date,
    end: date,
    cap: int,
) -> Decimal | None:
    """The book's return over `cap` SLOTS, not over the names that happen to be in it.

    **An empty slot is cash and earns zero, and that drag is real.** Dividing by `len(held)` would
    price a three-name book as if the fourth quarter of the capital did not exist, which flatters
    every date on which the screen could not fill the book - exactly the dates a thin cross-section
    produces, which are the early ones.

    **An unpriceable name is not cash.** A name whose bar cannot be read on either end leaves both
    the numerator and the denominator, the same rule `run_pr014.book_return` uses: carrying it at
    zero would be a claim that it did not move.
    """
    if cap < 1:
        return None
    total = Decimal(0)
    slots = cap
    for name in held:
        positions = index_of.get(name)
        first = positions.get(start) if positions else None
        last = positions.get(end) if positions else None
        value = (
            period_return(series_by_name[name], first, last)
            if first is not None and last is not None else None
        )
        if value is None:
            slots -= 1
            continue
        total += value
    return None if slots < 1 else total / Decimal(slots)


def qualifies(cell: dict[str, object]) -> bool:
    """Whether a window's interval counts as excluding zero. **§6 reads nothing else.**

    Two conditions and the second is the one that gets dropped: the interval must not straddle zero
    AND the window must meet §8's minimum of `MIN_REBALANCES`. A thin window produces a perfectly
    well-formed interval - it is just an interval about nine numbers - and a flag that forgot the
    sample rule would let it carry a verdict. Extracted rather than inlined so that it can be
    mutated on its own; inlined in `main` it was the one load-bearing line no test could reach.
    """
    if "net_low" not in cell:
        return False
    return bool(cell.get("sample_rule_met")
                and (Decimal(str(cell["net_low"])) > 0 or Decimal(str(cell["net_high"])) < 0))


def window_of(formation: date, half: str) -> str:
    """Which of §5a's windows a rebalance belongs to.

    The fourth cell - half B after the split date - is NOT one of the three §5a registers. It is
    computed and reported as `diagnostic_both`, and `decide()` never reads it. Amendment A-1,
    before the run: reporting a number the rule does not consult is different from selecting on it,
    and withholding a cell that exists is its own kind of silence.
    """
    early = formation <= PRIMARY_END
    if half == "A":
        return "primary" if early else "holdout_time"
    return "holdout_names" if early else "diagnostic_both"


def book_annual_cost(mean_turnover: Decimal) -> Decimal:
    """A year of the book's measured turnover, annualised by the REBALANCE STEP.

    **The step, not the holding period, and the difference is a factor of `MAX_CONCURRENT`.** The
    book rebalances every 5 sessions - 50.4 times a year - even though each position is held 20.
    Annualising by 20 would divide the cost by four and would do it silently: the table would look
    entirely normal and every arm would be flattered by the same amount, so no comparison between
    arms would look wrong either.

    A sanity anchor for the number: a four-name book that re-picks nothing turns one slot of four
    every 5 sessions, which is 25% per rebalance and **6.30% a year** at `DR-005`'s 25bp - exactly
    what a 20-session hold with no netting costs. Netting is what a persistent name buys, and
    whether the top-ranked name persists is what this study measures rather than assumes.
    """
    return annual_cost(mean_turnover, STEP, "long_only", SLIPPAGE_BPS)


def underpowered(cell: dict[str, object]) -> bool:
    """Whether a window's interval is too wide for a null read off it to mean anything.

    §8's power floor, and it exists because `PR-012` measured a four-position book and refused a
    verdict. **A wide interval and a small effect look identical in a table** - both print as "the
    interval contains zero" - and only this line separates "the signal does nothing" from "four
    positions could not have shown it either way".
    """
    if "net_low" not in cell:
        return True
    return Decimal(str(cell["net_high"])) - Decimal(str(cell["net_low"])) > POWER_FLOOR


def decide(rows: list[dict[str, object]]) -> dict[str, object]:
    """`PR-015` §6's decision rule, applied by the machine rather than by a reader.

    The rule was fixed before the data: **the arm with the LARGEST primary-window net excess whose
    interval excludes zero**, then read on both holdouts without re-selecting. The tie-break is
    fail-closed for the same reason `PR-014`'s is - choosing between two equals after seeing the
    data is not registered.
    """
    qualifying = [
        r for r in rows
        if isinstance(r.get("primary"), dict) and r["primary"].get("net_excludes_zero")
    ]
    if not qualifying:
        # §6's REJECT branch is gated on the power floor. A grid in which nothing was measurable is
        # not a refutation, and recording one as `reject` would let an underpowered study close a
        # question - the single most expensive thing a null can do wrongly.
        measurable = [r for r in rows if not underpowered(r.get("primary", {}))]
        if not measurable:
            return {"verdict": "inconclusive",
                    "why": f"no arm's primary interval is inside the {POWER_FLOOR * 100:.0f} "
                           f"point power floor (PR-015 §8): the instrument failed, not the signals"}
        return {"verdict": "reject",
                "why": "no arm's primary-window net interval excludes zero at 1x costs"}

    best = max(Decimal(str(r["primary"]["net_annual"])) for r in qualifying)
    at_best = [r for r in qualifying
               if Decimal(str(r["primary"]["net_annual"])) == best]
    if len(at_best) > 1:
        return {"verdict": "inconclusive",
                "why": "more than one arm ties for the largest qualifying primary estimate; "
                       "choosing between them after the run is not registered",
                "arms": [str(r["arm"]) for r in at_best]}

    chosen = at_best[0]
    common = {"arm": chosen["arm"],
              "stressed_net": chosen["primary"].get("net_annual_3x")}
    if underpowered(chosen["primary"]):
        return {"verdict": "inconclusive",
                "why": f"the selected arm's primary interval is wider than the "
                       f"{POWER_FLOOR * 100:.0f} point power floor (PR-015 §8)", **common}
    # The both-negative branch is checked FIRST, and the order is not arbitrary: §6 says the
    # verdict is inconclusive "regardless of which loses less", which makes it an override rather
    # than one test among several. An arm that is losing AND dies at 3x costs should be reported as
    # the first thing, because "it loses" is the finding and "it also loses more when charged more"
    # is arithmetic.
    if chosen["primary"].get("both_negative"):
        return {"verdict": "inconclusive",
                "why": "the arm and the equal-weighted universe control are both negative",
                **common}
    if Decimal(str(chosen["primary"]["net_annual_3x"])) <= 0:
        return {"verdict": "inconclusive",
                "why": f"the selected arm turns negative at {STRESS_MULTIPLE}x costs", **common}
    failed = [
        name for name in ("holdout_time", "holdout_names")
        if not (isinstance(chosen.get(name), dict) and chosen[name].get("net_excludes_zero"))
    ]
    if failed:
        return {"verdict": "inconclusive",
                "why": f"the arm qualifies on the primary window and fails {' and '.join(failed)}",
                **common}
    return {"verdict": "accept",
            "why": "the arm with the largest qualifying primary estimate clears 1x and 3x costs "
                   "and excludes zero on BOTH holdouts without re-selection",
            **common}


def report(result: dict[str, object]) -> int:
    """Read a committed result and print what the book earned OVER ITS OWN POOL.

    **Why this reading exists, and why it is not the verdict.** `rs.benchmark` is `SPY` and its
    status is `assumed`, not ratified. `benchmark-fit-2026-09-06` measured that this universe is an
    equal-weighted mid-cap book which tracks MDY, RSP and IWM at half `SPY`'s tracking error, and
    that its 3.02% annual "loss" to `SPY` is the mega-cap concentration of 2016-2026 - a different
    asset, not a worse strategy. **Every arm therefore carries a style drag that has nothing to do
    with its signal**, and a book beating its own pool by two points would still print negative
    against `SPY`.

    The separation needs no new number and no new selection: the study already records the arm's net
    excess over `SPY` and the equal-weighted admitted pool's excess over `SPY` for the same dates.
    The difference is the book against the pool it selected from. §6 does not read it and it changes
    no verdict - `AGENTS.md` §10.6 rule 4 is why it is computed HERE rather than typed into a report.

    The pool is charged NO cost, because nobody trades it. That makes this reading conservative for
    the book, which pays its measured turnover in full.
    """
    print("WHAT THE BOOK EARNED OVER ITS OWN POOL, not over SPY")
    print("  arm minus the equal-weighted admitted universe of the same half and dates.")
    print("  The arm is NET of its measured turnover; the pool is charged nothing.")
    print()
    print(f"  {'arm':<13}{'window':<16}{'net vs SPY':>12}{'pool vs SPY':>13}"
          f"{'book vs pool':>14}")
    rows = result.get("rows", [])
    if not isinstance(rows, list):
        print("  no rows in this result")
        return 1
    for row in rows:
        for window in ("primary", "holdout_time", "holdout_names"):
            cell = row.get(window, {})
            if "net_annual" not in cell or "control_universe_annual" not in cell:
                continue
            book = Decimal(str(cell["net_annual"]))
            pool = Decimal(str(cell["control_universe_annual"]))
            print(f"  {row['arm']:<13}{window:<16}{book * 100:>+11.2f}%{pool * 100:>+12.2f}%"
                  f"{(book - pool) * 100:>+13.2f}%")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_pr015")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--as-of", default=None,
                        help="read the store at this knowledge instant instead of the latest")
    parser.add_argument("--out", type=Path,
                        default=Path("docs/prereg/results/PR-015.json"))
    parser.add_argument("--report", action="store_true",
                        help="read the committed result and print the book-against-its-own-pool "
                             "table, without re-running. Touches no store and decides nothing")
    args = parser.parse_args()

    if args.report:
        return report(json.loads(args.out.read_text(encoding="utf-8")))

    store = BarStore(args.data / "bars.duckdb")
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
    if as_of is None:
        print("the bar store is empty")
        return 1

    series_by_name: dict[str, BarSeries] = {}
    for name in sorted(store.instrument_ids(as_of)):
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series and len(series.bars) >= HISTORY + HORIZON + 1:
            series_by_name[name] = series
    store.close()
    if BENCHMARK not in series_by_name:
        raise SystemExit(f"{BENCHMARK} has too little history to serve as the benchmark")

    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}
    benchmark = series_by_name[BENCHMARK]
    calendar = [b.session_date for b in benchmark.bars]
    # STEP, not HORIZON. One slot frees per rebalance and a position is held HORIZON sessions =
    # MAX_CONCURRENT steps; stepping by HORIZON would build a one-position book that only LOOKED
    # capped at four.
    formations = calendar[HISTORY::STEP]
    halves = {n: half_of(n) for n in series_by_name}
    print(f"as_of {as_of.isoformat()}   instruments {len(series_by_name)}   "
          f"formation dates {len(formations)}   hold {HORIZON}   step {STEP}   "
          f"cap {MAX_CONCURRENT}")

    admitted = {n: _admitted_dates(s, RULE, formations) for n, s in series_by_name.items()}

    # One candidate list per (date, half), shared by all five arms. The history floor is the
    # MAXIMUM any arm needs, applied here once - see the module docstring, point 1.
    pools: dict[tuple[date, str], list[Candidate]] = {}
    for session in formations:
        for half in ("A", "B"):
            pool = [
                Candidate(name, positions[session])
                for name, positions in index_of.items()
                if halves[name] == half
                and (position := positions.get(session)) is not None
                and position >= HISTORY
                and session in admitted[name]
            ]
            if len(pool) >= MIN_NAMES_PER_DATE:
                pools[(session, half)] = pool
    usable = sorted({d for d, _ in pools})
    print(f"  formation dates with >= {MIN_NAMES_PER_DATE} names in BOTH halves: "
          f"{sum(1 for d in usable if (d, 'A') in pools and (d, 'B') in pools)}")
    print(f"  first usable formation: {usable[0] if usable else 'none'}\n")

    windows = ("primary", "holdout_time", "holdout_names", "diagnostic_both")
    excess: dict[tuple[str, str], list[Decimal]] = {}
    decile: dict[tuple[str, str], list[Decimal]] = {}
    control: dict[tuple[str, str], list[Decimal]] = {}
    turns: dict[tuple[str, str], list[Decimal]] = {}
    filled: dict[tuple[str, str], list[int]] = {}
    skipped: dict[tuple[str, str], int] = {}
    warmups: dict[tuple[str, str], int] = {}
    for arm in ARMS:
        for half in ("A", "B"):
            # The book is a SEQUENCE, carried across formation dates and across the split date. A
            # book does not liquidate because a study drew a line in 2021, and starting the holdout
            # from an empty book would charge it four entries the real book never made.
            held: list[str] = []
            previous_weights: dict[str, Decimal] = {}
            rebalanced = 0
            for i, session in enumerate(formations[:-1]):
                nxt = formations[i + 1]
                if nxt not in index_of[BENCHMARK]:
                    continue
                bench = period_return(
                    benchmark, index_of[BENCHMARK][session], index_of[BENCHMARK][nxt]
                )
                if bench is None:
                    continue
                # The oldest position has reached exit.max_holding_period and closes. It closes
                # on a SCHEDULE, not because a better name appeared: that is what a holding period
                # is. BEFORE the pool check, because a date with too thin a cross-section to select
                # from is still a date on which an open position ages - freezing the book through a
                # gap would hold a name past its registered horizon.
                if len(held) >= MAX_CONCURRENT:
                    held = held[1:]
                pool = pools.get((session, half))
                if pool is None:
                    skipped[(arm, half)] = skipped.get((arm, half), 0) + 1
                    previous_weights = {
                        n: Decimal(1) / Decimal(MAX_CONCURRENT) for n in held
                    }
                    continue
                eligible = rank_by(arm, pool, series_by_name, benchmark)
                held = fill(held, eligible, MAX_CONCURRENT)
                if not held:
                    continue
                gross = capped_return(
                    held, series_by_name, index_of, session, nxt, MAX_CONCURRENT
                )
                if gross is None:
                    continue
                key = (arm, window_of(session, half))
                excess.setdefault(key, []).append(gross - bench)
                filled.setdefault(key, []).append(len(held))
                # The first MAX_CONCURRENT rebalances of a sequence fill the book from empty, so a
                # short book there is the RAMP and not a slot the screen could not fill. Counted
                # separately: without this the "no good place" branch would look as though it fired
                # when all that happened was the book starting.
                if rebalanced < MAX_CONCURRENT:
                    warmups[key] = warmups.get(key, 0) + 1
                rebalanced += 1
                # The whole ELIGIBLE decile, reported and never read by §6 (A-2). It is what
                # separates "the signal is weak" from "four positions cannot express it".
                whole = book_return(eligible, series_by_name, index_of, session, nxt)
                if whole is not None:
                    decile.setdefault(key, []).append(whole - bench)
                pooled = book_return(
                    [c.instrument_id for c in pool], series_by_name, index_of, session, nxt
                )
                if pooled is not None:
                    control.setdefault(key, []).append(pooled - bench)
                # Turnover of the BOOK, measured rather than assumed - PR-014 amendment A-3. Each
                # slot is 1/MAX_CONCURRENT of the capital whether or not the book is full, so an
                # empty slot costs nothing to hold and the arithmetic stays honest about cash.
                weights = {n: Decimal(1) / Decimal(MAX_CONCURRENT) for n in held}
                turns.setdefault(key, []).append(turnover(previous_weights, weights))
                previous_weights = weights

    rows: list[dict[str, object]] = []
    for arm in ARMS:
        row: dict[str, object] = {"arm": arm}
        for window in windows:
            key = (arm, window)
            values = excess.get(key, [])
            cell: dict[str, object] = {"rebalances": len(values),
                                       "sample_rule_met": len(values) >= MIN_REBALANCES}
            interval = moving_block_bootstrap(values, BLOCK, BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES)
            measured = turns.get(key, [])
            if interval and measured:
                mean_turn = sum(measured, Decimal(0)) / len(measured)
                cost = book_annual_cost(mean_turn)
                periods = Decimal(252) / Decimal(STEP)
                mean, low, high = interval
                cell |= {
                    "turnover_per_rebalance": float(round(mean_turn, 4)),
                    "annual_cost": float(round(cost, 6)),
                    "gross_annual": float(round(Decimal(str(mean)) * periods, 6)),
                    "net_annual": float(round(Decimal(str(mean)) * periods - cost, 6)),
                    "net_low": float(round(Decimal(str(low)) * periods - cost, 6)),
                    "net_high": float(round(Decimal(str(high)) * periods - cost, 6)),
                    "net_annual_3x": float(round(
                        Decimal(str(mean)) * periods - cost * STRESS_MULTIPLE, 6)),
                    "block": BLOCK,
                }
                cell["net_excludes_zero"] = qualifies(cell)
                cell["interval_width"] = float(round(
                    Decimal(str(cell["net_high"])) - Decimal(str(cell["net_low"])), 6))
                cell["inside_power_floor"] = not underpowered(cell)
                sizes = filled.get(key, [])
                if sizes:
                    cell["mean_positions_held"] = round(sum(sizes) / len(sizes), 2)
                    short = sum(1 for n in sizes if n < MAX_CONCURRENT)
                    cell["rebalances_with_an_empty_slot"] = short
                    cell["of_those_the_book_filling_from_empty"] = warmups.get(key, 0)
                    cell["slots_the_screen_could_not_fill"] = max(0, short - warmups.get(key, 0))
                pooled = control.get(key, [])
                if pooled:
                    universe = (sum(pooled, Decimal(0)) / len(pooled)) * periods
                    cell["control_universe_annual"] = float(round(universe, 6))
                    cell["both_negative"] = bool(
                        Decimal(str(cell["net_annual"])) < 0 and universe < 0
                    )
                whole = decile.get(key, [])
                if whole:
                    # The eligible decile, GROSS - it is a diagnostic about the signal and not a
                    # book anyone could hold, so charging it a turnover it never paid would be
                    # inventing a cost for a portfolio that does not exist.
                    cell["diagnostic_decile_gross_annual"] = float(round(
                        (sum(whole, Decimal(0)) / len(whole)) * periods, 6))
                cell["series"] = [float(round(v, 8)) for v in values]
            row[window] = cell
        rows.append(row)

    print(f"ANNUALISED NET EXCESS over the benchmark, long only, {MAX_CONCURRENT} concurrent "
          f"positions, {HORIZON}-session hold, rebalanced every {STEP}")
    print(f"  {'arm':<13}{'held':>5}{'turn/reb':>9}{'cost/yr':>8}  {'PRIMARY':>9}"
          f"{'interval':>21}{'n':>4}"
          f"  {'HOLD-TIME':>10}{'n':>5}  {'HOLD-NAMES':>11}{'n':>5}  {'decile':>8}")
    for row in rows:
        line = f"  {row['arm']:<13}"
        primary = row["primary"]
        if "net_annual" not in primary:
            print(line + "  no cell")
            continue
        star = "*" if primary["net_excludes_zero"] else " "
        wide = "" if primary.get("inside_power_floor") else " !"
        line += (f"{primary.get('mean_positions_held', 0):>5.2f}"
                 f"{primary['turnover_per_rebalance'] * 100:>8.1f}%"
                 f"{primary['annual_cost'] * 100:>7.2f}%"
                 f"{primary['net_annual'] * 100:>+10.2f}%{star}"
                 f" [{primary['net_low'] * 100:+7.2f}%,{primary['net_high'] * 100:+7.2f}%]"
                 f"{primary['rebalances']:>4}")
        for window in ("holdout_time", "holdout_names"):
            cell = row[window]
            if "net_annual" in cell:
                mark = "*" if cell["net_excludes_zero"] else " "
                line += f"  {cell['net_annual'] * 100:>+9.2f}%{mark}{cell['rebalances']:>4}"
            else:
                line += f"  {'-':>10} {'-':>4}"
        gross = primary.get("diagnostic_decile_gross_annual")
        line += f"  {gross * 100:>+7.2f}%" if gross is not None else f"  {'-':>8}"
        print(line + wide)
    print(f"\n  * = the net interval excludes zero AND the sample rule is met "
          f"(>= {MIN_REBALANCES} rebalances, PR-015 §8)")
    print(f"  ! = the primary interval is WIDER than §8's {POWER_FLOOR * 100:.0f} point power "
          f"floor, so a null read off it is evidence of nothing")
    print("  `decile` is the whole ELIGIBLE decile's GROSS excess - a diagnostic (A-2). It is not "
          "a book this system can hold and §6 never reads it.")
    print("  The fourth cell of the 2x2 - half B, late - is in the JSON as `diagnostic_both` and "
          "§6 does not read it (amendment A-1).")

    outcome = decide(rows)
    print(f"\nVERDICT (PR-015 §6, applied mechanically): {str(outcome['verdict']).upper()}")
    if "arm" in outcome:
        print(f"  arm       {outcome['arm']}")
    if outcome.get("stressed_net") is not None:
        print(f"  at {STRESS_MULTIPLE}x costs   {float(outcome['stressed_net']) * 100:+.2f}%")
    print(f"  because {outcome['why']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "prereg": "PR-015",
        "trials": 5,
        "verdict": outcome["verdict"],
        "decision": outcome,
        "stress_multiple": str(STRESS_MULTIPLE),
        "as_of": as_of.isoformat(),
        "horizon": HORIZON,
        "max_concurrent_positions": MAX_CONCURRENT,
        "step": STEP,
        "power_floor": str(POWER_FLOOR),
        "book": f"at most {MAX_CONCURRENT} concurrent positions (risk.max_concurrent_positions, "
                f"owner), each held {HORIZON} sessions, entered {STEP} sessions apart so exactly "
                f"one slot frees per rebalance. The freed slot takes the highest-ranked ELIGIBLE "
                f"name not already held, or stays EMPTY. Amendment A-2, owner instruction "
                f"2026-09-07: the decile is the eligibility screen and the ratified cap is the "
                f"book",
        "caps_not_applied": {
            "risk.max_open_risk": "constrains RISK not count; pricing it needs a stop, a size and "
                                  "an equity curve, none of which this study models",
            "risk.max_sector_risk": "needs a point-in-time sector; classifications.duckdb holds 14 "
                                    "days of knowledge times and the module refuses to answer a "
                                    "2016 question with today's classification",
            "risk.correlation_threshold": "left out on purpose - a risk guard whose bite "
                                          "correlation-cap-calibration-2026-08-23 measured "
                                          "separately, and one that would fire at different rates "
                                          "per arm and confound a comparison BETWEEN signals",
        },
        "history_floor": HISTORY,
        "lookback": LOOKBACK,
        "benchmark": BENCHMARK,
        "decile": str(DECILE),
        "primary_end": PRIMARY_END.isoformat(),
        "country": "USA",
        "split": {
            "primary": "formations on or before 2021-12-31, names in half A",
            "holdout_time": "formations after 2021-12-31, names in half A",
            "holdout_names": "formations on or before 2021-12-31, names in half B",
            "diagnostic_both": "formations after 2021-12-31, names in half B - NOT registered in "
                               "§5a, reported and never read by §6 (amendment A-1)",
            "halves": "sha256(instrument_id)[0] % 2 == 0 -> A",
        },
        "perturbations": {
            "registered": ["cost_stress_1x", "cost_stress_3x"],
            "run": ["cost_stress_1x", "cost_stress_3x"],
            "note": "run on EVERY arm and window as `net_annual_3x`, not only on the arm §6 picks",
        },
        "slippage_bps_per_side": str(SLIPPAGE_BPS),
        "cost_model": "MEASURED one-sided turnover between consecutive books, two sides, charged "
                      "at entry. NOT gross turnover - see PR-014 amendment A-3",
        "bootstrap": {"block": BLOCK, "resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED},
        "min_rebalances": MIN_REBALANCES,
        "instruments": len(series_by_name),
        "formation_dates": len(usable),
        "rebalances_skipped_for_a_thin_cross_section": {
            f"{a}/{h}": n for (a, h), n in sorted(skipped.items())
        },
        "rows": rows,
        "survivorship": "absent - the directory is today's, so every arm is an UPPER BOUND",
        "not_measured": [
            "a buy/hold band, registered as not-run in §5: it makes the holding period emergent",
            "any horizon but 20 sessions - PR-014 answered the horizon question",
            "any cap but 4 - risk.max_concurrent_positions is ratified `owner`, and sweeping it "
            "would be five more configurations and a parameter this study has no standing to move",
        ],
    }, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
