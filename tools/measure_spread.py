"""Measure the effective spread across the stored universe, to inform DR-005.

`costs.slippage_model` has been `assumed` since DR-004 - 5bps per side, chosen as "on the optimistic
side of plausible" and never checked. PR-005 then reported the base strategy flat at 1x costs and
clearly negative at 3x, which puts the sign of the project's headline result inside that unmeasured
number. This measures it.

**No network.** Corwin-Schultz and Abdi-Ranaldo read daily high, low and close, and the bar store
already holds two years of them. That is the whole reason this is the cheapest high-value study
available: DR-004 rejected spread-derived slippage as "correct and unavailable" because no free
source serves historical intraday quotes - but these estimators never needed quotes.

Read-only over `data/`. Reaches no vendor, so unlike the other tools here it could run in CI; it
does not, because it reads a store CI has no copy of (CI_POLICY 4).

    python tools/measure_spread.py --data C:/PycharmProjects/SwingDesk/data
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.application import universe as selection_rules
from swingdesk.contracts.market import Interval, Series
from swingdesk.market_data import BarStore
from swingdesk.reference_data import universe as rules
from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.validation.studies import spread as study

# --- DR-003's liquidity rule, pinned here rather than read from the registry ------------
# A study records what it actually ran under, so a later ratification cannot silently change what a
# committed measurement means. Same practice as tools/run_pr005.py.
MIN_PRICE = Decimal("5.00")
MIN_ADTV = Decimal(5_000_000)
ADTV_WINDOW = 20
MIN_HISTORY = 250

#: Usable pairs below which an instrument is reported but excluded from the population summary.
#: Both estimators are noisy per name; a handful of sessions produces a number, not a measurement.
MIN_PAIRS = 200

#: Reporting resolution. The estimators compute at `spread.PRECISION` (34 digits) because ln and exp
#: need the headroom, but writing 34 digits of a noisy estimate into an evidence record would make it
#: look far more precise than it is - the failure "nothing looks more validated than it is" names.
#: Nine decimal places is 0.00001bp, well past anything the estimate means, and it is deterministic.
REPORT_QUANTUM = Decimal("0.000000001")


def _report(value: Decimal | None) -> str | None:
    return str(value.quantize(REPORT_QUANTUM)) if value is not None else None


def main() -> int:
    parser = argparse.ArgumentParser(prog="measure_spread")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--limit", type=int, default=None,
                        help="measure only the first N instruments; for a timing check, not a run")
    parser.add_argument("--min-pairs", type=int, default=MIN_PAIRS)
    parser.add_argument("--out", type=Path,
                        default=Path("docs/decisions/measurements/spread-sample.json"))
    args = parser.parse_args()

    store = BarStore(args.data / "bars.duckdb")
    directory = DirectoryStore(args.data / "directory.duckdb")

    as_of = store.latest_knowledge_time()
    if as_of is None:
        print("the bar store is empty; nothing to measure")
        return 1

    # Read both stores at the instant the bars' knowledge ends, so the directory used to filter is
    # the one contemporaneous with them. Filtering an older window with a newer listing file is
    # survivorship bias with extra steps (application/universe.py select()).
    rule = rules.LiquidityRule(
        min_price=MIN_PRICE, min_adtv=MIN_ADTV, adtv_window=ADTV_WINDOW, min_history=MIN_HISTORY
    )
    selection = selection_rules.select(directory, store, rule, as_of)
    a_tier = {member.instrument.id for member in selection.members}

    instrument_ids = store.instrument_ids(as_of)
    if args.limit is not None:
        instrument_ids = instrument_ids[: args.limit]

    print(f"as_of {as_of.isoformat()}")
    print(f"instruments stored: {len(instrument_ids)}  A-tier: {len(a_tier)}")

    rows: list[dict[str, object]] = []
    estimates: list[study.SpreadEstimate] = []
    a_tier_estimates: list[study.SpreadEstimate] = []
    started = time.monotonic()

    for index, instrument_id in enumerate(instrument_ids, start=1):
        series = store.as_of(instrument_id, Interval.DAY, Series.RAW, as_of)
        estimate = study.estimate_instrument(series.bars)
        if estimate is None:
            continue

        member = instrument_id in a_tier
        rows.append({
            "instrument_id": instrument_id,
            "a_tier": member,
            "bars": len(series.bars),
            "pairs_used": estimate.pairs_used,
            "pairs_skipped": estimate.pairs_skipped,
            "negative_pairs": estimate.negative_pairs,
            "corwin_schultz": _report(estimate.corwin_schultz),
            "corwin_schultz_mean": _report(estimate.corwin_schultz_mean),
            "abdi_ranaldo": _report(estimate.abdi_ranaldo),
        })

        if estimate.pairs_used >= args.min_pairs:
            estimates.append(estimate)
            if member:
                a_tier_estimates.append(estimate)

        if index % 250 == 0:
            elapsed = time.monotonic() - started
            print(f"  [{index}/{len(instrument_ids)}] measured={len(rows)} {elapsed:.0f}s")

    everything = study.summarise(estimates)
    a_tier_summary = study.summarise(a_tier_estimates)

    def _summary(summary: study.Summary) -> dict[str, object]:
        return {
            "instruments": summary.instruments,
            "corwin_schultz": {str(p): _report(v) for p, v in summary.corwin_schultz.items()},
            "corwin_schultz_mean": {
                str(p): _report(v) for p, v in summary.corwin_schultz_mean.items()
            },
            "abdi_ranaldo": {str(p): _report(v) for p, v in summary.abdi_ranaldo.items()},
            "abdi_ranaldo_per_side_bps": {
                str(p): str(study.per_side_bps(v).quantize(Decimal("0.01")))
                for p, v in summary.abdi_ranaldo.items()
            },
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "as_of": as_of.isoformat(),
                "estimators": ["corwin_schultz_2012", "abdi_ranaldo_2017"],
                "precision": study.PRECISION,
                "report_quantum": str(REPORT_QUANTUM),
                "negative_rule": study.NegativeRule.ZERO.value,
                "min_pairs": args.min_pairs,
                "liquidity_rule": {
                    "min_price": str(MIN_PRICE),
                    "min_adtv": str(MIN_ADTV),
                    "adtv_window": ADTV_WINDOW,
                    "min_history": MIN_HISTORY,
                },
                "instruments_stored": len(instrument_ids),
                "instruments_measured": len(rows),
                "instruments_summarised": len(estimates),
                "a_tier_members": len(a_tier),
                "a_tier_summarised": len(a_tier_estimates),
                "summary_all": _summary(everything),
                "summary_a_tier": _summary(a_tier_summary),
                "rows": sorted(rows, key=lambda row: str(row["instrument_id"])),
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print(f"\nwrote {args.out}: {len(rows)} measured, {len(estimates)} summarised")
    for label, summary in (("all", everything), ("A-tier", a_tier_summary)):
        if not summary.abdi_ranaldo:
            continue
        median = summary.abdi_ranaldo[50]
        print(f"  {label:<7} Abdi-Ranaldo median spread {median:.6f} "
              f"= {study.per_side_bps(median):.2f} bps per side  (n={summary.estimated})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
