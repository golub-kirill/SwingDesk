"""The power estimate `PR-019` needs BEFORE it registers a minimum detectable effect.

**This exists because `PR-018` got that number wrong and said so.** Its §3 took `PR-017`'s 0.05R on
the stated ground that the arms *"share entries exactly"*; amendment `A-1` recorded before the run
that they do not, and the realised half-widths came out five to nine times wider than predicted.
`PREREG_TEMPLATE` rule 9 permits *"a prior study's interval half-width, a variance estimate, or a
simulation - but not a guess"*, and the prior study's half-width is the thing that just failed.

So this tool produces the variance estimate. It runs the same construction `PR-019` registers - one
entry set shared by every cell, spacing fixed at the longest hold in the grid - on a deterministic
instrument SUBSAMPLE, and reports the dispersion of the paired per-trade difference at the month
level, which is the unit `PR-016`'s moving-block bootstrap resamples.

**It prints no mean and no effect, and `assert_no_effect_leaked` enforces that.** A power calculation
that reported the effect it was sizing would be the study, run early and unregistered, and rule 3
downgrades a design that saw its data. Dispersion is not an effect: the variance of a difference is
invariant to the difference's location, so nothing here can tell anyone which cell won.

**Two things it is NOT.**

* Not a measurement of any cell. The subsample takes the decile WITHIN a smaller pool, so the names
  are not the names `PR-019` will trade. It estimates the variance of the same RULE on a smaller
  universe; the direction of that bias is not known and §3 of the pre-registration says so.
* Not free of the sampling noise a subsample adds. A month's mean difference computed from few
  trades is noisier than one computed from many, so the raw month-level standard deviation
  OVERSTATES the between-month dispersion. `variance_components` removes that term explicitly
  rather than leaving the estimate conservative and unexplained.

    PYTHONPATH=$PWD/src python tools/power_pr019.py --data <store>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from measure_momentum_horizon import RULE
from run_pr013 import MIN_NAMES_PER_DATE, _admitted_dates
from run_pr014 import BENCHMARK, DECILE, Candidate, select
from run_pr016 import (
    COMMISSION_PER_SHARE,
    HOLD,
    LOOKBACK,
    PRIMARY_END,
    RISK_PER_TRADE,
    SLIPPAGE_BPS,
    STEP,
    STOP_MULTIPLE,
    TARGET_R,
    WINDOW_START,
    OnDates,
    atr_registry,
    window_sessions,
)
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.decision_logic.ranking import ByMarketPathStrength
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.trade_management.exits import ExitPolicy
from swingdesk.validation.backtest import BacktestConfig, CostModel
from swingdesk.validation.backtest.engine import run_arm

#: The grid `PR-019` registers. `MAX_HOLD` fixes the entry spacing for every cell, so the entry set
#: is a function of the screen and one constant rather than of the exit policy under test.
HOLDS = (10, 20, 40, 60)
STOPS: tuple[tuple[str, Decimal | None], ...] = (
    ("2.0", Decimal("2.0")),
    ("4.0", Decimal("4.0")),
    ("none", None),
)
MAX_HOLD = max(HOLDS)

#: R has to exist in every cell, including the ones with no protective stop: it is `entry - stop`
#: (`RISK_SPEC` 2), and an arm priced in different units cannot be subtracted from another.
R_DENOMINATOR_MULTIPLE = Decimal("2.0")

#: The ratified exit. Owned HERE and imported by `run_pr019`, so the power estimate sizes exactly
#: the contrast the study reads - the first cut sized three grid contrasts and not this one.
INCUMBENT = "ratified"


def cell_name(hold: int, stop_label: str) -> str:
    return f"h{hold}_stop{stop_label}"


GRID = tuple(cell_name(hold, label) for hold in HOLDS for label, _ in STOPS)

#: The contrasts sized here. The first three bracket the grid - its widest pair, its narrowest
#: adjacent pair, and a stop against none. The rest are §6's own: whichever cell the in-sample rule
#: selects, its out-of-sample difference against the incumbent is the one quantity read.
CONTRASTS: tuple[tuple[str, str], ...] = (
    ("h10_stop2.0", "h60_stopnone"),
    ("h20_stop2.0", "h40_stop2.0"),
    ("h20_stop2.0", "h20_stopnone"),
    *((name, INCUMBENT) for name in GRID),
)

#: `PR-016`'s and `PR-018`'s out-of-sample entry months - the window `PR-019`'s verdict is read on.
#: Half-width scales as `1 / sqrt(months)`, so the in-sample estimate is carried to it.
OOS_MONTHS = 54

#: Half of `PR-019`'s registered 0.15R power floor: a contrast predicted wider than this cannot
#: produce a readable verdict, and the report says which ones before the study runs.
READABLE_HALF_WIDTH = 0.075

DEFAULT_FRACTION = 0.25
DEFAULT_SEED = 20260908

RESULT = REPO / "docs" / "prereg" / "results" / "PR-019-power.json"


def incumbent_policy() -> ExitPolicy:
    """The ratified exit - `2.0 x ATR(14)` stop, `1.0R` target, 20 sessions - on the spaced entries."""
    return ExitPolicy(STOP_MULTIPLE, HOLD, target_r_multiple=TARGET_R)


def cells() -> dict[str, ExitPolicy]:
    """Twelve exit policies, no target in any of them.

    `PR-018` measured that the 1R target costs about 0.05R and buys nothing on the tail -
    `ratified_no_target` reads 3.0% of trades below -2R against the full policy's 2.3% - so the
    grid varies the two things that were shown to matter and holds the one that was not.
    """
    built: dict[str, ExitPolicy] = {}
    for hold in HOLDS:
        for label, multiple in STOPS:
            name = cell_name(hold, label)
            if multiple is None:
                built[name] = ExitPolicy(R_DENOMINATOR_MULTIPLE, hold, protective=False)
            else:
                built[name] = ExitPolicy(multiple, hold)
    return built


def subsample(names: list[str], fraction: float, seed: int) -> list[str]:
    """A deterministic instrument subsample, by hash rather than by a shuffled slice.

    Hashing the NAME means the sample is stable when the universe grows: a store backfilled with
    more instruments keeps every name this run took, so a later re-run of the power estimate is
    comparable to this one instead of merely being the same size.
    """
    if not 0.0 < fraction <= 1.0:
        raise SystemExit(f"fraction must be in (0, 1], got {fraction}")
    cut = int(fraction * (1 << 32))
    kept = []
    for name in names:
        digest = hashlib.sha256(f"{seed}:{name}".encode()).digest()
        if int.from_bytes(digest[:4], "big") < cut:
            kept.append(name)
    return kept


def spaced(dates: list[date], calendar_index: dict[date, int], spacing: int) -> list[date]:
    """Thin one name's selection dates so no two entries fall within `spacing` sessions.

    **This is what makes every cell trade the same entries.** The engine allows one position per
    instrument, so under free entry a cell that holds 60 sessions skips signals a cell that holds 10
    would take - which is exactly the coupling `PR-018` A-1 found and could only report. Spacing the
    entry set at the LONGEST hold in the grid removes the coupling at its source: no cell can ever
    have a position open when the next entry date arrives, so all twelve realise the same trades.

    The cost is stated in the pre-registration and is real: this measures net R PER TRADE on a fixed
    entry schedule, and it cannot rank cells on trades per year or on capital efficiency, because
    the schedule it fixes is the one the longest hold would impose on all of them.
    """
    taken: list[date] = []
    blocked_until = -1
    for session in sorted(dates):
        position = calendar_index[session]
        if position <= blocked_until:
            continue
        taken.append(session)
        blocked_until = position + spacing
    return taken


def variance_components(
    per_trade: dict[str, list[float]],
) -> dict[str, float]:
    """Split the observed month-to-month variance into signal and subsampling noise.

    A month's observed mean difference is the month's true mean plus sampling error of roughly
    `within / n`. Averaging that over months gives the noise floor the subsample ADDED, and
    subtracting it leaves the between-month dispersion the full study would see:

        var(between) = var(observed monthly means) - mean(var(within month) / n(month))

    **The correction can go negative** when the between-month signal is small relative to the noise,
    and it is reported as-is rather than clamped: a floored variance would quietly become a floored
    minimum detectable effect, and a power estimate that cannot come out "this subsample was too
    thin to size anything" is not a power estimate.
    """
    months = sorted(m for m, values in per_trade.items() if len(values) >= 2)
    if len(months) < 2:
        raise SystemExit("too few months with two or more trades to estimate a variance")
    means = [statistics.fmean(per_trade[m]) for m in months]
    observed = statistics.variance(means)
    noise = statistics.fmean(
        [statistics.variance(per_trade[m]) / len(per_trade[m]) for m in months]
    )
    return {
        "months": float(len(months)),
        "var_observed": observed,
        "var_subsample_noise": noise,
        "var_between": observed - noise,
    }


def half_width(variance: float, months: int) -> float:
    """The 95% half-width a bootstrap over `months` entry months would realise at this dispersion.

    A normal approximation to a moving-block bootstrap, and it is an approximation on purpose: the
    block structure of `PR-016`'s bootstrap widens the interval relative to this, so the number
    below is a LOWER bound on the half-width and therefore an optimistic minimum detectable effect.
    The pre-registration states the direction rather than pretending the approximation is exact.
    """
    if variance <= 0.0 or months <= 0:
        return float("nan")
    return 1.96 * math.sqrt(variance / months)


def predicted_oos(in_sample_half_width: float, in_sample_months: int) -> float:
    """Carry an in-sample half-width to the out-of-sample window's month count.

    `1 / sqrt(months)`, the same scaling `AGENTS.md` §19.6 used for the window rule. It assumes the
    between-month dispersion is the same in both windows, which is exactly what a regime change
    would break, so the figure is a prediction and the study reports the realised one beside it.
    """
    if math.isnan(in_sample_half_width) or in_sample_months <= 0:
        return float("nan")
    return in_sample_half_width * math.sqrt(in_sample_months / OOS_MONTHS)


def overlap_inflation(values: list[float], var_between: float, lags: int) -> float:
    """The variance of a mean of OVERLAPPING months, as a multiple of the independent case.

        1 + 2 * sum_{k=1..lags} (1 - k/n) * gamma_k / var_between

    `gamma_k` is the lag-k autocovariance of the month-ordered `values`. **Added 2026-09-13 because
    `half_width` assumes independent months and `PR-019b` paid for it**: a 60-session hold spans
    about three entry months, so a market-paired contrast's index legs overlap from month to month
    by construction, and the estimate ran 1.69x narrow. Measured, this factor read 3.30 and put the
    corrected prediction 7% wide of the realised one.

    The subsample's noise is independent from month to month, so it inflates lag 0 only - which is
    why the numerator reads lags >= 1 straight from the observed values while the denominator is the
    noise-corrected `var_between`. Measured rather than assumed, so where the market cancels - one
    exit against another - it stays near 1, which is why `PR-019` calibrated without it. NaN when
    the variance is unusable or there are too few months for the lags.
    """
    n = len(values)
    if var_between <= 0.0 or n <= lags + 1:
        return float("nan")
    centre = statistics.fmean(values)
    deviations = [v - centre for v in values]
    total = 1.0
    for k in range(1, lags + 1):
        gamma = sum(deviations[i] * deviations[i + k] for i in range(n - k)) / n
        total += 2.0 * (1.0 - k / n) * gamma / var_between
    return total if total > 0.0 else float("nan")


def lags_for_hold(sessions: int, per_month: int = 21) -> int:
    """A hold of `sessions` spans `ceil(sessions / 21)` entry months: that many, less one, lags."""
    return max(0, math.ceil(sessions / per_month) - 1)


def assert_no_effect_leaked(payload: dict[str, Any]) -> None:
    """Refuse to write anything that reports a LEVEL rather than a dispersion.

    The guard is mechanical because the discipline is not self-enforcing: every quantity here is
    computed from per-trade net R, and printing one mean would turn a power calculation into an
    unregistered first look at the study's own answer. `PREREG_TEMPLATE` rule 3 downgrades a design
    that saw its data, so this is the difference between a pre-registration and an exploratory note.
    """
    # Matched as whole `_`/space-separated TOKENS, never as substrings. The first cut matched
    # substrings and killed the first real run after ten minutes on the key `window`, which
    # contains `win` - a guard that fires on its own payload's metadata is a guard nobody keeps.
    banned = {"mean", "median", "effect", "win", "wins", "verdict", "level"}

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                tokens = set(str(key).lower().replace(" ", "_").split("_"))
                if tokens & banned:
                    raise AssertionError(f"a level leaked into the power payload at {path}{key}")
                walk(value, f"{path}{key}.")
        elif isinstance(node, list):
            for item in node:
                walk(item, path)
    walk(payload, "")


def build(args: argparse.Namespace) -> dict[str, Any]:
    store = BarStore(args.data / "bars.duckdb")
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else store.latest_knowledge_time()
    if as_of is None:
        raise SystemExit("the bar store is empty")

    every = sorted(store.instrument_ids(as_of))
    kept = set(subsample(every, args.fraction, args.seed)) | {BENCHMARK}
    series_by_name: dict[str, BarSeries] = {}
    for name in every:
        if name not in kept:
            continue
        series = store.as_of(name, Interval.DAY, Series.RAW, as_of)
        if series and len(series.bars) >= 252 + MAX_HOLD + 1:
            series_by_name[name] = series
    store.close()
    if BENCHMARK not in series_by_name:
        raise SystemExit(f"{BENCHMARK} has too little history to fix the calendar")

    benchmark = series_by_name[BENCHMARK]
    calendar = [bar.session_date for bar in benchmark.bars]
    calendar_index = {session: i for i, session in enumerate(calendar)}
    end = min(PRIMARY_END, calendar[-1])
    sessions = window_sessions(calendar, WINDOW_START, end)
    earliest = calendar[LOOKBACK] if len(calendar) > LOOKBACK else calendar[-1]
    formations = ([d for d in sessions[::STEP] if earliest <= d <= sessions[-MAX_HOLD - 1]]
                  if len(sessions) > MAX_HOLD else [])
    index_of = {n: {b.session_date: i for i, b in enumerate(s.bars)}
                for n, s in series_by_name.items()}
    print(f"as_of {as_of.isoformat()}   universe {len(every)}   subsample {len(series_by_name)}   "
          f"formation dates {len(formations)}   window {WINDOW_START}..{end} (IN SAMPLE ONLY)")

    admitted = {n: _admitted_dates(s, RULE, formations) for n, s in series_by_name.items()}
    selected: dict[str, list[date]] = {}
    thin = 0
    for session in formations:
        pool = [Candidate(n, index_of[n][session]) for n in sorted(admitted)
                if session in admitted[n]]
        if len(pool) < MIN_NAMES_PER_DATE:
            thin += 1
            continue
        ranker = ByMarketPathStrength(series=series_by_name, benchmark=benchmark, lookback=LOOKBACK)
        top, _ = select(ranker, pool, DECILE)
        for name in top:
            selected.setdefault(name, []).append(session)

    entries = {name: spaced(dates, calendar_index, MAX_HOLD) for name, dates in selected.items()}
    entries = {name: dates for name, dates in entries.items() if dates}

    policies = {**cells(), INCUMBENT: incumbent_policy()}
    costs = CostModel(COMMISSION_PER_SHARE, SLIPPAGE_BPS)
    registry = atr_registry()
    #: `cell -> (instrument, entry_date) -> net R`. Keyed by the trade's identity rather than
    #: appended, because the whole construction rests on every cell realising the SAME entries and
    #: a list would let a silent mismatch average away instead of failing.
    by_trade: dict[str, dict[tuple[str, date], float]] = {name: {} for name in policies}
    for count, (name, series) in enumerate(sorted(series_by_name.items()), start=1):
        dates = entries.get(name)
        if not dates:
            continue
        atr_series = atr_component.compute(series, registry)
        gate: list[bool | None] = [True] * len(series.bars)
        for label, policy in policies.items():
            config = BacktestConfig(arm=label, exits=policy, costs=costs,
                                    trigger=OnDates(frozenset(dates)),
                                    risk_per_trade=RISK_PER_TRADE)
            for trade in run_arm(series, gate, atr_series, config).trades:
                by_trade[label][(name, trade.entry_date)] = float(trade.net_r)
        if count % 250 == 0:
            print(f"  simulated {count}/{len(series_by_name)} instruments")

    keys = {label: set(book) for label, book in by_trade.items()}
    shared = set.intersection(*keys.values()) if keys else set()
    identical = all(k == shared for k in keys.values())

    contrasts: dict[str, Any] = {}
    for left, right in CONTRASTS:
        differences: dict[str, list[float]] = defaultdict(list)
        for key in sorted(shared):
            month = key[1].strftime("%Y-%m")
            differences[month].append(by_trade[left][key] - by_trade[right][key])
        components = variance_components(differences)
        months = int(components["months"])
        contrasts[f"{left} vs {right}"] = {
            **components,
            "half_width_uncorrected": half_width(components["var_observed"], months),
            "half_width_corrected": half_width(components["var_between"], months),
        }

    payload: dict[str, Any] = {
        "for": "PR-019",
        "purpose": "a variance estimate for PREREG_TEMPLATE rule 9. No level is reported.",
        "as_of": as_of.isoformat(),
        "fraction": args.fraction,
        "seed": args.seed,
        "universe": len(every),
        "subsample": len(series_by_name),
        "formation_dates": len(formations),
        "formations_skipped_for_a_thin_cross_section": thin,
        "window": {"start": WINDOW_START.isoformat(), "end": end.isoformat(),
                   "note": "IN SAMPLE ONLY - the holdout is not touched by a power estimate"},
        "grid": {"holds": list(HOLDS), "stops": [label for label, _ in STOPS],
                 "entry_spacing_sessions": MAX_HOLD},
        "entries": {"instruments": len(entries),
                    "signals_before_spacing": sum(len(v) for v in selected.values()),
                    "entries_after_spacing": sum(len(v) for v in entries.values()),
                    "trades_shared_by_every_cell": len(shared),
                    "every_cell_realised_the_same_entries": identical},
        "contrasts": contrasts,
        "approximation": (
            "half widths are a normal approximation to the moving-block bootstrap PR-016 runs. "
            "The block structure widens an interval relative to this, so each figure is a LOWER "
            "bound on the half width the study will realise."
        ),
    }
    assert_no_effect_leaked(payload)
    return payload


def report(payload: dict[str, Any]) -> None:
    print(f"\nPR-019 power estimate - dispersion only, no level\n{'=' * 62}")
    entries = payload["entries"]
    print(f"  subsample {payload['subsample']} of {payload['universe']} instruments, "
          f"fraction {payload['fraction']}, seed {payload['seed']}")
    print(f"  {entries['signals_before_spacing']} signals -> "
          f"{entries['entries_after_spacing']} entries after spacing at "
          f"{payload['grid']['entry_spacing_sessions']} sessions")
    print(f"  trades shared by every cell: {entries['trades_shared_by_every_cell']}   "
          f"identical entry sets: {entries['every_cell_realised_the_same_entries']}")
    print(f"\n  {'contrast':<30} {'months':>7} {'raw hw':>9} {'corrected hw':>13} "
          f"{'OOS hw, predicted':>18} {'readable':>9}")
    for name, cell in payload["contrasts"].items():
        predicted = predicted_oos(cell["half_width_corrected"], int(cell["months"]))
        readable = "yes" if predicted <= READABLE_HALF_WIDTH else "no"
        print(f"  {name:<30} {int(cell['months']):>7} "
              f"{cell['half_width_uncorrected']:>9.4f} {cell['half_width_corrected']:>13.4f} "
              f"{predicted:>18.4f} {readable:>9}")
    print(f"\n  predicted = corrected x sqrt(months / {OOS_MONTHS}); readable = predicted <= "
          f"{READABLE_HALF_WIDTH}, half of the 0.15R power floor")
    print(f"\n  {payload['approximation']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--as-of")
    parser.add_argument("--fraction", type=float, default=DEFAULT_FRACTION)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--report", action="store_true",
                        help="re-read the committed estimate instead of running it")
    args = parser.parse_args()

    if args.report:
        if not RESULT.exists():
            raise SystemExit(f"{RESULT} does not exist - run without --report first")
        report(json.loads(RESULT.read_text(encoding="utf-8")))
        return 0

    payload = build(args)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report(payload)
    print(f"\nwrote {RESULT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
