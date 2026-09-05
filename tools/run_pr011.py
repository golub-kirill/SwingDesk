"""PR-011's runner: does a 2 x ATR stop cost about 1R, on names whose ATR is a large share of price?

`docs/prereg/PR-011-stop-integrity-by-volatility-band.md` is the protocol and this file implements
it. Every constant below is pinned there before this file existed; none is read from the registry at
run time, because a study that inherits a live value changes meaning the day that value is ratified
(`ExitPolicy`'s own docstring, and `PR-005`'s precedent).

**The entries are a CENSUS, not a strategy**, and that is the design's load-bearing choice. Every
admitted name is entered on every 20th session with no trigger and no gate, so there is no entry
FAMILY here - which is what keeps this out of the one `HANDOFF.md` §7 closes by evidence. The
question is whether `entry - stop` is a risk measure on these names, not whether a screen picks
winners.

**The exit semantics are the system's, by CALLING it.** `ExitPolicy.evaluate` and `CostModel` are
the same objects `validation/backtest/engine.py` uses, so a stop-out here is a stop-out there. A
second implementation of the exit rule would be the one-logic-in-two-places failure this repository
has paid for more than once.

**What the statistic can and cannot see** (prereg §10 A-2). `evaluate` fills at the OPEN when a
session gaps through the stop and at THE STOP ITSELF when the low merely touches it, so on daily
bars a stop-out costs exactly 1R unless the market gapped. Overshoot is therefore the gap-through
cost, intraday slippage past a touched stop is invisible, and every band's figure is biased DOWNWARD.

    python tools/run_pr011.py --data data                 # measure, write nothing
    python tools/run_pr011.py --data data --write         # publish the result of record
    python tools/run_pr011.py --data data --limit 50      # a smoke run; --write is refused
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from swingdesk.application.universe import ADTV_WINDOW
from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.contracts.trade import ExitReason
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.platform.parameters import ParameterRegistry
from swingdesk.reference_data import universe as rules
from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.validation.backtest import CostModel, ExitPolicy

RESULT = REPO / "docs" / "prereg" / "results" / "PR-011.json"

# --- pinned by the pre-registration, section 5
ATR_PERIOD = 14
ATR_STOP_MULTIPLE = Decimal("2.0")
MAX_HOLDING_BARS = 20
FORMATION_EVERY = 20
SLIPPAGE_BPS = Decimal(25)
#: `DR-009` established the broker's fee structure as NO commission plus a 1.5% CAD-USD conversion,
#: and `DR-010` left that standing. This study is US-only, so the conversion fee is not engaged.
COMMISSION_PER_SHARE = Decimal(0)
STRESS_MULTIPLE = Decimal(3)
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260904
MIN_EVENTS_PER_BAND = 200

#: The DR-003 liquidity rule, pinned. `adtv_lag=0` matches PR-012 and PR-013: DR-017's lag postdates
#: those studies and using it here would make three studies describe three different universes.
MIN_PRICE = Decimal("5.00")
MIN_ADTV = Decimal(5_000_000)
MIN_HISTORY = 250

#: Band edges as ATR(14)/close at the SIGNAL bar. Upper bound exclusive, so the bands partition.
#: B5 is where 2 x ATR meets or exceeds the price - the arithmetic break the live path refuses.
BANDS: tuple[tuple[str, Decimal, Decimal], ...] = (
    ("B1", Decimal(0), Decimal("0.03")),
    ("B2", Decimal("0.03"), Decimal("0.06")),
    ("B3", Decimal("0.06"), Decimal("0.10")),
    ("B4", Decimal("0.10"), Decimal("0.50")),
    ("B5", Decimal("0.50"), Decimal(10_000)),
)
ARM_BAND = "B4"
CONTROL_BAND = "B1"

# --- the decision rule, section 6 and amendment A-1
#: PINNED, never read from the registry: a cap ratified mid-study would rewrite the decision rule.
MAX_OPEN_RISK_R = Decimal(4)
MAX_CONCURRENT_POSITIONS = 4
#: The one JUDGEMENT in the threshold - owner ruling 2026-09-04. Not arithmetic, and A-1 says so.
MATERIALITY_FRACTION = Decimal("0.25")
THRESHOLD_R = MATERIALITY_FRACTION * MAX_OPEN_RISK_R / MAX_CONCURRENT_POSITIONS

#: What section 5 registers and what this file runs. Gate 25 checks the pair against the verdict.
PERTURBATIONS_REGISTERED = ("cost stress 3x",)
PERTURBATIONS_CONSIDERED_NOT_REGISTERED = (
    "stop-multiple sweep", "band-edge sweep", "holding-period sweep",
)


@dataclass(frozen=True, slots=True)
class Event:
    """One census entry, walked to its exit."""

    instrument_id: str
    signal_date: date
    band: str
    atr_pct: Decimal
    entry: Decimal
    stop: Decimal
    exit_reason: str
    #: Excess loss beyond the placed stop, in R. `None` unless the exit was a stop-out.
    overshoot: Decimal | None
    gapped: bool
    net_r: Decimal


def band_of(atr_pct: Decimal) -> str:
    """Which band an ATR-percent lands in. Upper bound exclusive; the bands partition."""
    for name, low, high in BANDS:
        if low <= atr_pct < high:
            return name
    return BANDS[-1][0]


def _atr_registry() -> ParameterRegistry:
    return ParameterRegistry(
        {"atr.period": {"id": "atr.period", "value": ATR_PERIOD, "provenance": "assumed:Wilder 1978",
                        "status": "assumed", "unit": "bars", "named_in": ["M18-T0280"]}}
    )


def walk(series: BarSeries, atr_values: list[Decimal | None], rule: rules.LiquidityRule,
         policy: ExitPolicy, costs: CostModel) -> tuple[list[Event], dict[str, int]]:
    """Every 20th session, entered at the next open and walked to its exit.

    Non-overlapping by construction: the step is the holding period, so one name never holds two
    positions at once and no session is counted twice.

    Returns the events and a count of the entries that never opened, by reason. A signal that
    produced no event is COUNTED and never silently dropped - the same discipline `Skipped` enforces
    in the engine, and for the same reason: a dropped refusal makes a population look cleaner than
    it is.
    """
    events: list[Event] = []
    refused: dict[str, int] = defaultdict(int)
    bars = series.bars

    for index in range(0, len(bars) - 1, FORMATION_EVERY):
        atr = atr_values[index]
        if atr is None or atr <= 0:
            refused["no_atr"] += 1
            continue
        if not rule.admits(series, index):
            refused["not_admitted"] += 1
            continue

        signal = bars[index]
        entry_bar = bars[index + 1]
        entry = costs.buy_fill(entry_bar.open)
        stop = policy.stop_for(entry, atr)
        atr_pct = atr / signal.close

        if stop <= 0:
            # The live path's own refusal (`sizing.size_long`), reproduced here rather than
            # inferred. Counted BY BAND as well as in total, because the band comes from the signal
            # bar and the stop from the next open: membership of B5 and the arithmetic break can
            # disagree at the boundary, and A-2 promises the record carries both rather than
            # letting one be inferred from the other.
            refused["stop_not_positive"] += 1
            refused[f"stop_not_positive_{band_of(atr_pct)}"] += 1
            continue

        risk_per_share = entry - stop
        exit_price: Decimal | None = None
        reason: ExitReason | None = None
        for offset in range(0, MAX_HOLDING_BARS + 1):
            position = index + 1 + offset
            if position >= len(bars):
                break
            decision = policy.evaluate(bars[position], stop, offset)
            if decision.exited and decision.price is not None and decision.reason is not None:
                exit_price, reason = decision.price, decision.reason
                break
        if exit_price is None or reason is None:
            # The window ended with the position open. Closed at the last close and flagged, never
            # dropped - open positions at the end of a window are not randomly distributed.
            exit_price, reason = bars[min(index + 1 + MAX_HOLDING_BARS, len(bars) - 1)].close, \
                ExitReason.END_OF_DATA

        filled = costs.sell_fill(exit_price)
        stopped = reason in (ExitReason.STOP, ExitReason.STOP_GAP)
        events.append(Event(
            instrument_id=series.instrument_id,
            signal_date=signal.session_date,
            band=band_of(atr_pct),
            atr_pct=atr_pct,
            entry=entry,
            stop=stop,
            exit_reason=reason.value,
            overshoot=(stop - exit_price) / risk_per_share if stopped else None,
            gapped=reason is ExitReason.STOP_GAP,
            net_r=(filled - entry) / risk_per_share,
        ))
    return events, dict(refused)


def bootstrap_difference(
    by_date: dict[date, tuple[list[Decimal], list[Decimal]]], seed: int, resamples: int,
) -> tuple[float, float, float] | None:
    """Mean(arm) - mean(control) with a 95% percentile interval, resampling DATES.

    Dates rather than events, because every name entered on one session shares that session's
    market move: the cross-section is one observation, not a thousand (PR-013 §5, inherited). The
    two bands are resampled TOGETHER on the same dates, so the comparison stays paired.
    """
    dates = sorted(by_date)
    if len(dates) < 2:
        return None

    def difference(sample: list[date]) -> float | None:
        arm = [float(v) for d in sample for v in by_date[d][0]]
        control = [float(v) for d in sample for v in by_date[d][1]]
        if not arm or not control:
            return None
        return sum(arm) / len(arm) - sum(control) / len(control)

    point = difference(dates)
    if point is None:
        return None
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(resamples):
        sample = [dates[rng.randrange(len(dates))] for _ in range(len(dates))]
        value = difference(sample)
        if value is not None:
            draws.append(value)
    if len(draws) < 2:
        return None
    draws.sort()
    return point, draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws)) - 1]


def verdict(
    arm: dict[str, object], control: dict[str, object], difference: tuple[float, float, float] | None,
) -> tuple[str, str]:
    """The pre-registration's decision rule, in code (§6 and A-1).

    Order matters. The sample rule refuses BEFORE anything is compared, because REFUSED and
    INCONCLUSIVE are different claims (`AGENTS.md` §12): one says the study could not look, the
    other that it looked and could not tell.
    """
    if not arm["meets_minimum"] or not control["meets_minimum"]:
        return "refused", (
            f"the sample rule is not met: {ARM_BAND} has {arm['events']} stop-out(s) and "
            f"{CONTROL_BAND} has {control['events']}, against a floor of {MIN_EVENTS_PER_BAND} each"
        )
    if difference is None:
        return "refused", "too few signal dates carry both bands to resample"

    point, low, high = difference
    both_near_zero = (
        arm["ci_low"] is not None and control["ci_low"] is not None
        and float(arm["ci_low"]) <= 0 <= float(arm["ci_high"])          # type: ignore[arg-type]
        and float(control["ci_low"]) <= 0 <= float(control["ci_high"])  # type: ignore[arg-type]
    )
    if both_near_zero:
        return "reject", (
            "the stop holds everywhere measured - neither band's mean overshoot is "
            "distinguishable from zero, so a screen removing names on which nothing goes wrong "
            "buys nothing"
        )
    if low <= 0 <= high:
        return "reject", f"the interval on the difference includes zero ({low:.4f}, {high:.4f})"
    if point < float(THRESHOLD_R):
        return "reject", (
            f"the difference is {point:.4f}R, below the registered threshold of {THRESHOLD_R}R"
        )
    return "accept", (
        f"{ARM_BAND} overshoots {CONTROL_BAND} by {point:.4f}R, at or above the registered "
        f"{THRESHOLD_R}R, and the interval excludes zero"
    )


def band_lines(by_band: dict[str, dict[str, object]], *, limited: bool) -> list[str]:
    """The per-band printout. A SMOKE RUN PRINTS COUNTS AND NOT STATISTICS.

    That is a safeguard rather than tidiness. `--limit` walks an ALPHABETICAL PREFIX - `AGENTS.md`
    §12: a prefix is not a sample - so its band means are not an early answer but a biased one.
    Printing them shows whoever is debugging the runner a DIRECTION, and a drafter who has seen a
    direction cannot report the real run as confirmatory (`PREREG_TEMPLATE.md` rule 3). Measured
    cost of learning this: PR-011 amendment A-3, written after exactly that happened on 2026-09-04.

    Counts are printed either way: §8 makes deriving them step 1 of this runner, and a count is not
    a result.
    """
    lines = []
    for name, _, _ in BANDS:
        row = by_band[name]
        line = f"  {name}: entries={row['entries']} stop-outs={row['events']}"
        if not limited:
            line += f" mean_overshoot={row['mean_overshoot']} gap_rate={row['gap_through_rate']}"
        lines.append(line)
    if limited:
        lines.append("  (band statistics withheld: --limit walks an alphabetical prefix, and a "
                     "prefix is not a sample)")
    return lines


def _summarise(events: list[Event], band: str) -> dict[str, object]:
    stops = [e for e in events if e.band == band and e.overshoot is not None]
    values = [float(e.overshoot) for e in stops if e.overshoot is not None]
    entry = {
        "entries": sum(1 for e in events if e.band == band),
        "events": len(stops),
        "meets_minimum": len(stops) >= MIN_EVENTS_PER_BAND,
        "gap_through_rate": (sum(1 for e in stops if e.gapped) / len(stops)) if stops else None,
        "mean_overshoot": None, "ci_low": None, "ci_high": None,
        "mean_net_r": None,
    }
    net = [float(e.net_r) for e in events if e.band == band]
    if net:
        entry["mean_net_r"] = sum(net) / len(net)
    if len(values) >= 2:
        mean = sum(values) / len(values)
        rng = random.Random(BOOTSTRAP_SEED)
        draws = sorted(
            sum(values[rng.randrange(len(values))] for _ in range(len(values))) / len(values)
            for _ in range(BOOTSTRAP_RESAMPLES)
        )
        entry["mean_overshoot"] = mean
        entry["ci_low"] = draws[int(0.025 * BOOTSTRAP_RESAMPLES)]
        entry["ci_high"] = draws[int(0.975 * BOOTSTRAP_RESAMPLES) - 1]
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_pr011")
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--write", action="store_true",
                        help="publish docs/prereg/results/PR-011.json. Without it nothing is "
                             "written and the run is a measurement only")
    parser.add_argument("--limit", type=int, default=None,
                        help="walk only the first N names. A SMOKE RUN - --write is refused with "
                             "it, because a result of record over a truncated universe is not the "
                             "universe the pre-registration fixed")
    args = parser.parse_args()

    if args.write and args.limit is not None:
        print("--write and --limit together would publish a result over a universe PR-011 did not "
              "register. Refused.")
        return 2

    costs = CostModel(commission_per_share=COMMISSION_PER_SHARE, slippage_bps=SLIPPAGE_BPS)
    policy = ExitPolicy(atr_stop_multiple=ATR_STOP_MULTIPLE, max_holding_bars=MAX_HOLDING_BARS)
    registry = _atr_registry()
    rule = rules.LiquidityRule(
        min_price=MIN_PRICE, min_adtv=MIN_ADTV, adtv_window=ADTV_WINDOW,
        min_history=MIN_HISTORY, adtv_lag=0,
    )

    with (
        BarStore(args.data / "bars.duckdb") as store,
        DirectoryStore(args.data / "directory.duckdb") as directory,
    ):
        as_of = store.latest_knowledge_time()
        if as_of is None:
            raise SystemExit("bar store is empty")
        stored = set(store.instrument_ids(as_of))
        symbols = sorted({e.symbol for e in directory.as_of(as_of, eligible_only=True)} & stored)
        if args.limit is not None:
            symbols = symbols[:args.limit]
        print(f"snapshot {as_of.isoformat()}  ·  {len(symbols)} name(s) to walk")

        events: list[Event] = []
        refused: dict[str, int] = defaultdict(int)
        walked = 0
        for count, symbol in enumerate(symbols, start=1):
            series = store.as_of(symbol, Interval.DAY, Series.RAW, as_of)
            if len(series.bars) < MIN_HISTORY:
                refused["short_history"] += 1
                continue
            observations = atr_component.compute(series, registry).observations
            if len(observations) != len(series.bars):
                refused["atr_length_mismatch"] += 1
                continue
            found, misses = walk(series, [o.value for o in observations], rule, policy, costs)
            events.extend(found)
            for key, value in misses.items():
                refused[key] += value
            walked += 1
            if count % 250 == 0:
                print(f"  [{count}/{len(symbols)}] walked={walked} events={len(events)}")

    print(f"walked {walked} name(s) · {len(events)} entry(ies) · refused {dict(refused)}")

    by_band = {name: _summarise(events, name) for name, _, _ in BANDS}
    paired: dict[date, tuple[list[Decimal], list[Decimal]]] = defaultdict(lambda: ([], []))
    for event in events:
        if event.overshoot is None:
            continue
        if event.band == ARM_BAND:
            paired[event.signal_date][0].append(event.overshoot)
        elif event.band == CONTROL_BAND:
            paired[event.signal_date][1].append(event.overshoot)
    usable = {d: v for d, v in paired.items() if v[0] and v[1]}
    difference = bootstrap_difference(usable, BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES)

    if args.limit is None:
        outcome, reason = verdict(by_band[ARM_BAND], by_band[CONTROL_BAND], difference)
    else:
        outcome, reason = "not computed", (
            "--limit walks an alphabetical prefix, which is not the universe PR-011 §4 registered"
        )
    sessions = sorted({e.signal_date for e in events})
    payload = {
        "prereg": "PR-011",
        "verdict": outcome,
        "verdict_reason": reason,
        "country": "US",
        "exploratory": False,
        "survivorship": (
            "absent - today's directory. Here the bias runs TOWARD finding nothing: a delisted "
            "name is disproportionately one whose volatility exploded, which is this study's top "
            "band"
        ),
        "scope_unmet": [],
        "single_market": True,
        "trials": 1,
        "parameters": {
            "atr_period": ATR_PERIOD,
            "atr_stop_multiple": str(ATR_STOP_MULTIPLE),
            "max_holding_bars": MAX_HOLDING_BARS,
            "formation_every": FORMATION_EVERY,
            "slippage_bps": str(SLIPPAGE_BPS),
            "commission_per_share": str(COMMISSION_PER_SHARE),
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "min_events_per_band": MIN_EVENTS_PER_BAND,
            "bands": {name: [str(low), str(high)] for name, low, high in BANDS},
            "arm_band": ARM_BAND,
            "control_band": CONTROL_BAND,
            "threshold_r": str(THRESHOLD_R),
            "threshold_formula": (
                "materiality_fraction x max_open_risk / max_concurrent_positions, evaluated once "
                "at registration (amendment A-1)"
            ),
            "materiality_fraction": str(MATERIALITY_FRACTION),
            "max_open_risk_r_pinned": str(MAX_OPEN_RISK_R),
            "max_concurrent_positions_pinned": MAX_CONCURRENT_POSITIONS,
            "liquidity_rule": {
                "min_price": str(MIN_PRICE), "min_adtv": str(MIN_ADTV),
                "min_history": MIN_HISTORY, "adtv_lag": 0,
            },
        },
        "perturbations": {
            "registered": list(PERTURBATIONS_REGISTERED),
            "run": list(PERTURBATIONS_REGISTERED),
            "considered_not_registered": list(PERTURBATIONS_CONSIDERED_NOT_REGISTERED),
            "note": (
                "the cost stress moves the net figure only. The primary statistic is measured in R "
                "against the placed stop and is pre-cost by construction, so no stress can move it"
            ),
        },
        "split": {
            "registered": "none - nothing is fitted and nothing is selected from any window",
            "buys": (
                "NOTHING, and section 5 says so. Every band edge, the multiple, the period and the "
                "horizon are fixed before the run, so a holdout would cost sample and protect "
                "against a selection risk this study does not carry (PREREG_TEMPLATE 7)"
            ),
        },
        "measurement_bound": (
            "overshoot is non-zero only when a session GAPPED through the stop - a touched stop "
            "fills at the stop by construction - so intraday slippage is invisible and every "
            "band's figure is biased downward (amendment A-2)"
        ),
        "snapshot": as_of.isoformat(),
        "window": [sessions[0].isoformat(), sessions[-1].isoformat()] if sessions else [],
        "names_walked": walked,
        "entries": len(events),
        "refused": dict(refused),
        "difference": (
            {"point": difference[0], "ci_low": difference[1], "ci_high": difference[2],
             "dates": len(usable)}
            if difference else None
        ),
        "bands": by_band,
        "run_at": datetime.now(UTC).isoformat(),
    }

    print(f"\nverdict: {outcome} - {reason}")
    for line in band_lines(by_band, limited=args.limit is not None):
        print(line)

    if args.write:
        RESULT.parent.mkdir(parents=True, exist_ok=True)
        RESULT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {RESULT}")
    else:
        print("\nnothing written - pass --write to publish the result of record")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
