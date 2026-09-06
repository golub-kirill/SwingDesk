"""`PR-014`: at what holding period does the RATIFIED selection rule earn a net excess?

Registered 2026-09-06 and merged before this file existed, which is the evidence that the plan
predates the data (`PREREG_TEMPLATE` §3 rule 1). Read `docs/prereg/PR-014-holding-period.md` first;
this implements it and decides nothing on its own.

**The two things that make this study different from every sweep before it.**

**1. It ranks the way the CARD ranks.** `rs.benchmark_form` is `path` and `rs.lookback` is 126, both
`owner` via `DR-030`, and the live pipeline scores with
`decision_logic.ranking.ByMarketPathStrength` - the share of sessions a name beat `rs.benchmark`.
Every prior measurement of this family used a point-to-point return over 252 sessions instead,
a signal that ranker's own docstring puts at **Spearman ~0.6** against it. So `EVIDENCE_SUMMARY`
§§8, 8a and 11 measured something the card does not do. This calls the live class rather than
reimplementing it, so the study and the system cannot drift apart (amendment A-2).

**2. Windows overlap.** Ten years hold seventeen non-overlapping 126-session windows, which is why
nothing at that horizon could ever be resolved - a property of the estimator, not the market. The
owner lifted the constraint on 2026-09-06 (amendment A-1). This holds `K = horizon / 21` overlapping
sub-portfolios formed 21 sessions apart: every formation date contributes and `1/K` of the book
turns over per rebalance. **It creates no information** - ten years remain ten years - and the
moving-block bootstrap in `§5b` is what keeps the interval honest about that.

    python tools/run_pr014.py --data <store>
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_momentum_horizon import RULE
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.decision_logic.ranking import ByMarketPathStrength
from swingdesk.market_data import BarStore

#: `rs.benchmark`, `assumed:DR-018`.
BENCHMARK = "SPY"

#: `rs.lookback`, ratified `owner` via `DR-030`. **126, not the 252 every exploratory sweep used.**
LOOKBACK = 126

#: `screen.relative_strength_rule` = `top_decile`, ratified `owner` via `DR-030`.
DECILE = Decimal("0.10")

#: The rebalance step, in sessions. About one month; the period at which one sub-portfolio is
#: retired and one opened, so `1/K` of the book turns over.
STEP = 21

#: `PR-014` §5's grid: one month to one year.
HORIZONS = (20, 42, 63, 126, 189, 252)

#: `PR-014` §5's split. The horizon is SELECTED on the primary window and only REPORTED on the
#: holdout, which is the whole reason a twelve-cell sweep is allowed to name a winner at all.
PRIMARY_END = date(2021, 12, 31)

#: `DR-005`, ratified. Two sides per rebalance for a long-only book, four for a spread.
SLIPPAGE_BPS = Decimal("25")
SIDES = {"long_only": 2, "long_short": 4}

#: `validation.stress_cost_multiplier`, and `PR-014` §5's registered perturbation: the selected cell
#: must still be positive when costs are tripled.
STRESS_MULTIPLE = Decimal(3)

#: `PR-014` §5b. Block length `max(K, 6)` rebalances; seed and resamples fixed before the run.
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260906
MIN_BLOCK = 6

#: `PR-014` §8. Rebalance dates required in each window before a cell may carry a verdict.
MIN_REBALANCES = 24

#: The short leg's borrow proxy, `EVIDENCE_SUMMARY` §11's construction unchanged.
SHORT_POOL = Decimal("0.25")

#: Sessions in a year, for annualising. A 21-session period is one twelfth of it.
SESSIONS_PER_YEAR = 252
PERIODS_PER_YEAR = Decimal(SESSIONS_PER_YEAR) / Decimal(STEP)


@dataclass(frozen=True, slots=True)
class Candidate:
    """The two fields `ranking.Ranked` reads. Nothing here can reach a bar the date has not seen."""

    instrument_id: str
    index: int


def period_return(series: BarSeries, start: int, end: int) -> Decimal | None:
    """Close-to-close return between two positional indices, or None if either is unusable."""
    if start < 0 or end >= len(series.bars) or end <= start:
        return None
    first = series.bars[start].close
    if first <= 0:
        return None
    return (series.bars[end].close - first) / first


def select(
    ranker: ByMarketPathStrength, candidates: list[Candidate], decile: Decimal
) -> tuple[list[str], list[str]]:
    """`(top, bottom)` instrument ids at the ratified cutoff, via the LIVE ranker.

    Both ends come from one ordering, so the long and short legs of a spread are the two ends of
    the same ranking rather than two separately-computed lists.
    """
    ordered = ranker(candidates)
    size = int(len(ordered) * decile)
    if size < 1:
        return [], []
    return (
        [c.instrument_id for c in ordered[:size]],
        [c.instrument_id for c in ordered[-size:]],
    )


def book_return(
    names: list[str],
    series_by_name: dict[str, BarSeries],
    index_of: dict[str, dict[date, int]],
    start: date,
    end: date,
) -> Decimal | None:
    """Equal-weighted return of `names` between two SESSION DATES.

    A name without a bar on either date contributes nothing rather than being carried at zero: a
    position whose price cannot be read is not a position that did not move.
    """
    values: list[Decimal] = []
    for name in names:
        positions = index_of.get(name)
        if positions is None:
            continue
        first, last = positions.get(start), positions.get(end)
        if first is None or last is None:
            continue
        value = period_return(series_by_name[name], first, last)
        if value is not None:
            values.append(value)
    if not values:
        return None
    return sum(values, Decimal(0)) / len(values)


def moving_block_bootstrap(
    values: list[Decimal], block: int, seed: int, resamples: int
) -> tuple[float, float, float] | None:
    """Mean and a 95% percentile interval that survives autocorrelation.

    **Required rather than optional here.** Overlapping sub-portfolios share holdings, so successive
    rebalance returns are dependent by construction and an i.i.d. resample would report an interval
    several times too narrow - which is exactly the flattering direction. Kunsch (1989), an
    AUTHORED IMPORT (`AGENTS.md` §10.3): the course supplies no method for dependent data.

    Blocks are drawn with replacement and laid end to end until the resample matches the sample's
    length, so each resample carries the same number of observations as the original.
    """
    n = len(values)
    if n < 2 or block < 1:
        return None
    numbers = [float(v) for v in values]
    mean = statistics.mean(numbers)
    width = min(block, n)
    starts = n - width + 1
    blocks_needed = -(-n // width)
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(resamples):
        total = 0.0
        count = 0
        for _ in range(blocks_needed):
            begin = rng.randrange(starts)
            for offset in range(width):
                if count >= n:
                    break
                total += numbers[begin + offset]
                count += 1
        means.append(total / count)
    means.sort()
    return mean, means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]


def annual_cost(horizon: int, arm: str, per_side_bps: Decimal) -> Decimal:
    """What a year of this arm's turnover costs, as a fraction.

    `K = horizon / STEP` sub-portfolios means `1/K` of the book turns per rebalance and there are
    `252/STEP` rebalances a year, so the horizon cancels into `252/horizon` full turns - the same
    figure a non-overlapping book pays. **Overlapping spreads the turnover out; it does not reduce
    it**, and a tool that reported otherwise would be selling the construction as a free lunch.
    """
    turns = Decimal(SESSIONS_PER_YEAR) / Decimal(horizon)
    return turns * Decimal(SIDES[arm]) * per_side_bps / Decimal(10000)


def decide(rows: list[dict[str, object]], stress: Decimal) -> dict[str, object]:
    """`PR-014` §6's decision rule, applied by the machine rather than by a reader.

    The rule was fixed before the data and is mechanical, so executing it here removes the one step
    where a reader's judgement could enter: **the SHORTEST horizon whose primary interval excludes
    zero**, never the largest point estimate.

    **The tie-break is deliberately fail-closed.** §6 names a horizon and not an arm, so if two arms
    qualified at the same shortest horizon the rule would not discriminate - and picking one after
    seeing the data is exactly the snoop the split exists to prevent. That case returns
    `inconclusive` and says why.
    """
    qualifying = [
        r for r in rows
        if isinstance(r.get("primary"), dict) and r["primary"].get("net_excludes_zero")
    ]
    if not qualifying:
        return {"verdict": "reject",
                "why": "no horizon's primary-window net interval excludes zero at 1x costs"}

    shortest = min(int(r["horizon"]) for r in qualifying)
    at_shortest = [r for r in qualifying if int(r["horizon"]) == shortest]
    if len(at_shortest) > 1:
        return {"verdict": "inconclusive", "horizon": shortest,
                "why": "more than one arm qualifies at the shortest horizon and PR-014 §6 names a "
                       "horizon, not an arm; choosing between them after the run is not registered"}

    chosen = at_shortest[0]
    primary, holdout = chosen["primary"], chosen["holdout"]
    gross = Decimal(str(primary["gross_annual"]))
    stressed = gross - Decimal(str(chosen["annual_cost"])) * stress
    common = {"horizon": shortest, "arm": chosen["arm"],
              "stressed_net": float(round(stressed, 6))}
    if stressed <= 0:
        return {"verdict": "inconclusive",
                "why": f"the selected cell turns negative at {stress}x costs", **common}
    if primary.get("both_negative"):
        return {"verdict": "inconclusive",
                "why": "the arm and the buy-and-hold control are both negative", **common}
    if not isinstance(holdout, dict) or not holdout.get("net_excludes_zero"):
        return {"verdict": "inconclusive",
                "why": "the horizon qualifies on the primary window and fails on the holdout",
                **common}
    return {"verdict": "accept",
            "why": "the shortest qualifying horizon clears 1x and 3x costs on the primary window "
                   "and its interval excludes zero on the holdout without re-selection",
            **common}


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_pr014")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path,
                        default=Path("docs/prereg/results/PR-014.json"))
    args = parser.parse_args()

    store = BarStore(args.data / "bars.duckdb")
    as_of = store.latest_knowledge_time()
    if as_of is None:
        print("the bar store is empty")
        return 1

    series_by_name: dict[str, BarSeries] = {}
    for name in sorted(store.instrument_ids(as_of)):
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series and len(series.bars) >= LOOKBACK + max(HORIZONS) + STEP + 1:
            series_by_name[name] = series
    store.close()
    if BENCHMARK not in series_by_name:
        raise SystemExit(f"{BENCHMARK} has too little history to serve as the benchmark")

    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}
    benchmark = series_by_name[BENCHMARK]
    calendar = [b.session_date for b in benchmark.bars]
    rebalances = calendar[LOOKBACK::STEP]
    print(f"as_of {as_of.isoformat()}   instruments {len(series_by_name)}   "
          f"rebalance dates {len(rebalances)}   lookback {LOOKBACK} (ratified, path form)")

    admitted = {n: _admitted_dates(s, RULE, rebalances) for n, s in series_by_name.items()}

    # One ranking per rebalance date, reused by every horizon: the SELECTION does not depend on how
    # long the book will hold it, and re-ranking per horizon would be twelve times the work for the
    # same answer.
    picks: dict[date, tuple[list[str], list[str]]] = {}
    adtv_rank: dict[date, set[str]] = {}
    admitted_on: dict[date, list[str]] = {}
    for session in rebalances:
        candidates = [
            Candidate(name, positions[session])
            for name, positions in index_of.items()
            if session in positions and session in admitted[name]
        ]
        if len(candidates) < MIN_NAMES_PER_DATE:
            continue
        ranker = ByMarketPathStrength(
            series=series_by_name, benchmark=benchmark, lookback=LOOKBACK
        )
        picks[session] = select(ranker, candidates, DECILE)
        admitted_on[session] = [c.instrument_id for c in candidates]
        volumes = {
            c.instrument_id: sum(
                (b.close * b.volume for b in
                 series_by_name[c.instrument_id].bars[max(0, c.index - 19): c.index + 1]),
                Decimal(0),
            )
            for c in candidates
        }
        ordered = sorted(volumes.items(), key=lambda pair: (-pair[1], pair[0]))
        adtv_rank[session] = {n for n, _ in ordered[:int(len(ordered) * SHORT_POOL)]}
    print(f"  formation dates with a full cross-section: {len(picks)}\n")

    rows: list[dict[str, object]] = []
    for horizon in HORIZONS:
        k = max(1, round(horizon / STEP))
        for arm in ("long_only", "long_short"):
            windows: dict[str, list[Decimal]] = {"primary": [], "holdout": []}
            control: dict[str, list[Decimal]] = {"primary": [], "holdout": []}
            for i, session in enumerate(rebalances[:-1]):
                nxt = rebalances[i + 1]
                if nxt not in index_of[BENCHMARK]:
                    continue
                legs = [rebalances[i - j] for j in range(k) if i - j >= 0]
                legs = [d for d in legs if d in picks]
                if len(legs) < k:
                    continue
                longs, shorts = [], []
                for formed in legs:
                    top, bottom = picks[formed]
                    top_return = book_return(top, series_by_name, index_of, session, nxt)
                    if top_return is None:
                        continue
                    longs.append(top_return)
                    if arm == "long_short":
                        pool = adtv_rank.get(formed, set())
                        borrowable = [n for n in bottom if n in pool] or bottom
                        short_return = book_return(
                            borrowable, series_by_name, index_of, session, nxt
                        )
                        if short_return is not None:
                            shorts.append(short_return)
                if not longs:
                    continue
                long_leg = sum(longs, Decimal(0)) / len(longs)
                bench = period_return(
                    benchmark, index_of[BENCHMARK][session], index_of[BENCHMARK][nxt]
                )
                if bench is None:
                    continue
                if arm == "long_only":
                    excess = long_leg - bench
                else:
                    if not shorts:
                        continue
                    excess = long_leg - (sum(shorts, Decimal(0)) / len(shorts))
                where = "primary" if session <= PRIMARY_END else "holdout"
                windows[where].append(excess)
                # `PR-014` §6's control, and it is registered rather than optional: the verdict has
                # a branch for "the arm AND the control are both negative", and that branch cannot
                # be evaluated without this number. Buy-and-hold the whole admitted universe over
                # the same period - a selection rule that merely matches it has selected nothing.
                held = admitted_on.get(session)
                if held:
                    everything = book_return(held, series_by_name, index_of, session, nxt)
                    if everything is not None:
                        control[where].append(everything - bench)

            cost = annual_cost(horizon, arm, SLIPPAGE_BPS)
            row: dict[str, object] = {
                "horizon": horizon, "arm": arm, "K": k,
                "annual_cost": float(round(cost, 6)),
            }
            for window, values in windows.items():
                block = max(k, MIN_BLOCK)
                interval = moving_block_bootstrap(
                    values, block, BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES
                )
                enough = len(values) >= MIN_REBALANCES
                cell: dict[str, object] = {"rebalances": len(values), "sample_rule_met": enough}
                if interval:
                    mean, low, high = interval
                    annual = Decimal(str(mean)) * PERIODS_PER_YEAR
                    cell |= {
                        "gross_annual": float(round(annual, 6)),
                        "net_annual": float(round(annual - cost, 6)),
                        "net_low": float(round(Decimal(str(low)) * PERIODS_PER_YEAR - cost, 6)),
                        "net_high": float(round(Decimal(str(high)) * PERIODS_PER_YEAR - cost, 6)),
                        "block": block,
                    }
                    cell["net_excludes_zero"] = bool(
                        enough and (cell["net_low"] > 0 or cell["net_high"] < 0)
                    )
                    # §6's both-negative branch needs the control's SIGN, and nothing else.
                    held_values = control[window]
                    if held_values:
                        universe = (
                            sum(held_values, Decimal(0)) / len(held_values)
                        ) * PERIODS_PER_YEAR
                        cell["control_universe_annual"] = float(round(universe, 6))
                        cell["both_negative"] = bool(
                            Decimal(str(cell["net_annual"])) < 0 and universe < 0
                        )
                    # The registered block is `max(K, 6)`, which at K=6 is exactly one holding
                    # period - the shortest length that spans the dependence. A longer block widens
                    # the interval, so this DIAGNOSTIC is reported beside the registered figure
                    # rather than replacing it: changing the statistic after seeing the result is
                    # the data snooping this study exists to avoid.
                    wider = moving_block_bootstrap(
                        values, block * 2, BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES
                    )
                    if wider:
                        _, low2, high2 = wider
                        cell["diagnostic_double_block"] = {
                            "block": block * 2,
                            "net_low": float(round(
                                Decimal(str(low2)) * PERIODS_PER_YEAR - cost, 6)),
                            "net_high": float(round(
                                Decimal(str(high2)) * PERIODS_PER_YEAR - cost, 6)),
                        }
                    # `PR-014` §5's registered perturbation, run on EVERY cell rather than only on
                    # the one §6 selects: a stress applied to the winner alone cannot show that the
                    # ranking of the grid is stable under it.
                    cell["net_annual_3x"] = float(round(
                        Decimal(str(cell["gross_annual"])) - cost * STRESS_MULTIPLE, 6))
                    # Kept so a reader can re-test the interval without a 35-minute re-run.
                    cell["series"] = [float(round(v, 8)) for v in values]
                row[window] = cell
            rows.append(row)

    print("ANNUALISED NET EXCESS over the benchmark, by holding period")
    print(f"  {'horizon':>8}{'K':>4}  {'arm':<11}{'cost/yr':>9}"
          f"{'PRIMARY net':>13}{'interval':>24}{'n':>5}"
          f"{'HOLDOUT net':>13}{'interval':>24}{'n':>5}")
    for row in rows:
        line = f"  {row['horizon']:>8}{row['K']:>4}  {row['arm']:<11}{row['annual_cost'] * 100:>8.2f}%"
        for window in ("primary", "holdout"):
            cell = row[window]
            if "net_annual" not in cell:
                line += f"{'too few':>13}{'-':>24}{cell['rebalances']:>5}"
                continue
            star = "*" if cell["net_excludes_zero"] else " "
            line += (f"{cell['net_annual'] * 100:>+12.2f}%{star}"
                     f"  [{cell['net_low'] * 100:+8.2f}%,{cell['net_high'] * 100:+8.2f}%]"
                     f"{cell['rebalances']:>5}")
        print(line)
    print("\n  * = the net interval excludes zero AND the sample rule is met")
    print(f"  Sample rule: >= {MIN_REBALANCES} rebalances per window (PR-014 §8)")

    outcome = decide(rows, STRESS_MULTIPLE)
    print(f"\nVERDICT (PR-014 §6, applied mechanically): {str(outcome['verdict']).upper()}")
    if "horizon" in outcome:
        print(f"  cell    {outcome['horizon']} sessions, {outcome['arm']}")
        print(f"  at {STRESS_MULTIPLE}x costs   {float(outcome['stressed_net']) * 100:+.2f}%")
    print(f"  because {outcome['why']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "prereg": "PR-014",
        "trials": 12,
        # The census gate reads BOTH of these. A result carrying a prereg id and no verdict is a
        # supporting analysis rather than a study, and `verify_study_summary.py` counts it as one.
        "verdict": outcome["verdict"],
        "decision": outcome,
        "stress_multiple": str(STRESS_MULTIPLE),
        "as_of": as_of.isoformat(),
        "lookback": LOOKBACK,
        "benchmark_form": "path, via decision_logic.ranking.ByMarketPathStrength",
        "benchmark": BENCHMARK,
        "decile": str(DECILE),
        "step": STEP,
        "primary_end": PRIMARY_END.isoformat(),
        # `CARD-001`'s scope. `DR-003` gap 1 keeps Canada out: the NASDAQ Trader files cover US
        # venues only, so a `.TO` universe would be a list rather than a rule.
        "country": "USA",
        "split": {
            "primary": f"2016-08-22 to {PRIMARY_END.isoformat()}",
            "holdout": f"after {PRIMARY_END.isoformat()}",
            "buys": "protection against a twelve-cell sweep naming its own maximum. The horizon is "
                    "selected on the primary window ONLY and then read on the holdout without "
                    "re-selection; without it, 'the best horizon' is a statement about noise",
        },
        "perturbations": {
            "registered": ["cost_stress_1x", "cost_stress_3x"],
            "run": ["cost_stress_1x", "cost_stress_3x"],
            "note": "WALKFORWARD_SPEC 4 numbers 3 and 4. Run on EVERY cell as `net_annual_3x`, not "
                    "only on the cell §6 selects - a stress applied to the winner alone cannot "
                    "show the grid's ranking is stable under it.",
        },
        "slippage_bps_per_side": str(SLIPPAGE_BPS),
        "bootstrap": {
            "kind": "moving block", "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED, "min_block": MIN_BLOCK,
        },
        "min_rebalances": MIN_REBALANCES,
        "short_pool": str(SHORT_POOL),
        "instruments": len(series_by_name),
        "formation_dates": len(picks),
        "rows": rows,
        "survivorship": "absent - the directory is today's. Long-only is biased UP, long-short DOWN",
        "not_measured": [
            "borrow fees, hard-to-borrow rates, Regulation SHO locates, the uptick rule",
            "regulatory fees - about 0.9% of the slippage term, excluded, pessimistic for H1",
            "market impact",
        ],
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
