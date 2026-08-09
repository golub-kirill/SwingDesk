"""Run PR-008: is the assumed 5bp slippage an understatement of the spread this universe pays?

Orchestration only. Every number comes from `validation.studies.effective_spread`, which is pure and
tested, and from `reference_data.universe`, which owns the eligibility rule.

**Offline.** Unlike the other run_pr*.py tools this one reaches no network: it reads the bar store
that already exists. It is still not run in CI, because the store is local data rather than a
committed fixture.

The constants below are read from the pre-registration. They are NOT registry values, and that is
deliberate: a study records what it actually ran under, rather than inheriting whatever gets
ratified later.

    python tools/run_pr008.py
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.market_data.store import BarStore
from swingdesk.reference_data import universe
from swingdesk.validation.studies import effective_spread as spread

# --- DR-003, the liquidity rule this study inherits -------------------------------------
RULE = universe.LiquidityRule(
    min_price=Decimal("5.00"), min_adtv=Decimal("5000000"),
    adtv_window=20, min_history=250,
)

# --- PR-008 sections 4-6, fixed at registration -----------------------------------------
ASSUMED_HALF_SPREAD_BPS = Decimal("5.0")     # DR-004, per side
BREAK_EVEN_MULTIPLE = Decimal("1.3692")      # PR-005's two points; see the prereg section 5
NEGATIVE_RATE_LIMIT = Decimal("0.25")        # section 6's refusal branch
MINIMUM_INSTRUMENTS = 200                    # section 8
MINIMUM_MONTHS_PER_INSTRUMENT = 12           # section 8

#: Fixed at run time rather than at registration - the prereg said "monthly" without pinning the
#: floor. A 21-session month yields ~20 pairs, so 15 admits full months and rejects stubs. Chosen
#: once and not varied; recorded in the JSON so the choice is visible rather than implied.
MINIMUM_PAIRS_PER_MONTH = 15


def _monthly(series: BarSeries) -> list[spread.SpreadWindow]:
    """Both estimators per calendar month, in canonical month order."""
    buckets: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    for bar in series.bars:
        label = f"{bar.session_date.year:04d}-{bar.session_date.month:02d}"
        buckets[label].append((float(bar.high), float(bar.low), float(bar.close)))

    windows: list[spread.SpreadWindow] = []
    for label in sorted(buckets):
        rows = buckets[label]
        windows.append(
            spread.estimate(
                series.instrument_id, label,
                [high for high, _, _ in rows],
                [low for _, low, _ in rows],
                [close for _, _, close in rows],
                minimum_pairs=MINIMUM_PAIRS_PER_MONTH,
            )
        )
    return windows


def _adtv(series: BarSeries) -> Decimal:
    value = universe.average_dollar_volume(series, RULE.adtv_window)
    return Decimal(0) if value is None else value


def _correlation(xs: list[float], ys: list[float]) -> float | None:
    """Pearson r. Used only in the exploratory block."""
    if len(xs) < 2:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    dy = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return numerator / (dx * dy)


def _decile_table(
    rows: list[tuple[Decimal, Decimal]], label: str
) -> list[dict[str, object]]:
    """Median half-spread by decile of `key`. rows are (key, half_spread_bps), unsorted."""
    ordered = sorted(rows, key=lambda row: row[0])
    if not ordered:
        return []
    size = max(1, len(ordered) // 10)
    table: list[dict[str, object]] = []
    for index in range(0, len(ordered), size):
        chunk = ordered[index:index + size]
        if not chunk:
            continue
        middle = spread.median([value for _, value in chunk])
        table.append({
            "decile": len(table) + 1,
            f"{label}_low": str(chunk[0][0]),
            f"{label}_high": str(chunk[-1][0]),
            "instruments": len(chunk),
            "median_half_spread_bps": None if middle is None else str(middle),
        })
    return table[:10]


def _exploratory(
    full_series: dict[str, dict[str, object]], adtv: dict[str, Decimal]
) -> dict[str, object]:
    """Post-hoc diagnostics. NOT evidence - see PREREG_TEMPLATE section 3 rule 4.

    Designed after the registered arm was run and its negative rate seen, so these numbers may
    generate the next pre-registration and may not advance any validation status. They exist because
    "inconclusive" is much more useful when it says WHY, and the why here is checkable: a spread
    measure must fall as liquidity rises and must not track volatility.
    """
    ids = sorted(full_series)
    if not ids:
        return {"note": "no eligible instruments"}

    cs = [float(full_series[i]["cs"] or 0.0) for i in ids]
    ar = [float(full_series[i]["ar"] or 0.0) for i in ids]
    ranges = [float(full_series[i]["range"]) for i in ids]  # type: ignore[arg-type]
    log_adtv = [math.log(float(adtv[i])) for i in ids if float(adtv[i]) > 0]
    paired = [(i, a) for i, a in zip(ids, ar, strict=True) if float(adtv[i]) > 0]

    ratios = sorted(a / r for a, r in zip(ar, ranges, strict=True) if r > 0)
    negatives = sum(1 for i in ids if full_series[i]["cs_negative"])

    return {
        "arm": "full-series pooling, added after the registered arm ran",
        "status": "exploratory - may not advance a validation status",
        "instruments": len(ids),
        "cs_negative_instruments": negatives,
        "cs_negative_rate": str(
            (Decimal(negatives) / Decimal(len(ids))).quantize(Decimal("0.0001"))
        ),
        "correlation_ar_vs_daily_range": _correlation(ar, ranges),
        "correlation_cs_vs_daily_range": _correlation(cs, ranges),
        "correlation_ar_vs_log_adtv": _correlation([a for _, a in paired], log_adtv),
        "correlation_cs_vs_log_adtv": _correlation(
            [c for i, c in zip(ids, cs, strict=True) if float(adtv[i]) > 0], log_adtv
        ),
        "ar_estimate_as_share_of_daily_range": {
            "p10": round(ratios[len(ratios) // 10], 4) if ratios else None,
            "median": round(ratios[len(ratios) // 2], 4) if ratios else None,
            "p90": round(ratios[9 * len(ratios) // 10], 4) if ratios else None,
        },
        "reading": (
            "A spread estimate should correlate strongly NEGATIVELY with liquidity and weakly with "
            "volatility. These do the opposite, which is the signature of an estimator whose noise "
            "floor sits above the quantity it is meant to resolve."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_pr008")
    parser.add_argument("--store", type=Path, default=Path("data/bars.duckdb"))
    parser.add_argument("--out", type=Path, default=Path("docs/prereg/results/PR-008.json"))
    parser.add_argument("--limit", type=int, default=0, help="0 = every instrument")
    args = parser.parse_args()

    if not args.store.exists():
        print(f"no bar store at {args.store}; refusing to continue")
        return 1

    store = BarStore(args.store)
    try:
        # Pin the snapshot to the store's own latest knowledge_time, so the run reproduces.
        knowledge_time = store._connection.execute(  # noqa: SLF001 - research tool
            "SELECT max(knowledge_time) FROM bars"
        ).fetchone()[0]
        instrument_ids = store.instrument_ids(knowledge_time)
        if args.limit:
            instrument_ids = instrument_ids[:args.limit]
        print(f"store {args.store}, knowledge_time {knowledge_time}, "
              f"{len(instrument_ids)} instruments")

        eligible: list[str] = []
        rejected = short = 0
        windows_by_instrument: dict[str, list[spread.SpreadWindow]] = {}
        adtv_by_instrument: dict[str, Decimal] = {}
        price_by_instrument: dict[str, Decimal] = {}
        full_series: dict[str, dict[str, object]] = {}

        for count, instrument_id in enumerate(instrument_ids, start=1):
            series = store.as_of(instrument_id, Interval.DAY, Series.RAW, knowledge_time)
            if len(series.bars) < RULE.min_history:
                short += 1
                continue
            if not RULE.admits(series):
                rejected += 1
                continue

            windows = [w for w in _monthly(series) if w.corwin_schultz is not None]
            if len(windows) < MINIMUM_MONTHS_PER_INSTRUMENT:
                short += 1
                continue

            eligible.append(instrument_id)
            windows_by_instrument[instrument_id] = windows
            adtv_by_instrument[instrument_id] = _adtv(series)
            price_by_instrument[instrument_id] = series.bars[-1].close

            # Exploratory arm - see the report. Full-series pooling and the mean daily range, so
            # the diagnostic can ask what the estimators are actually tracking.
            highs = [float(bar.high) for bar in series.bars]
            lows = [float(bar.low) for bar in series.bars]
            closes = [float(bar.close) for bar in series.bars]
            full_cs, _, full_cs_negative = spread.corwin_schultz(highs, lows, closes)
            full_ar, _, _ = spread.abdi_ranaldo(highs, lows, closes)
            full_series[instrument_id] = {
                "cs": full_cs,
                "ar": full_ar,
                "cs_negative": full_cs_negative,
                "range": sum(
                    (high - low) / close
                    for high, low, close in zip(highs, lows, closes, strict=True)
                ) / len(closes),
            }

            if count % 250 == 0:
                print(f"  [{count}/{len(instrument_ids)}] eligible={len(eligible)}")
    finally:
        store.close()

    print(f"universe: {len(eligible)} eligible, {rejected} rejected by rule, "
          f"{short} short history or too few months")

    if len(eligible) < MINIMUM_INSTRUMENTS:
        print(f"\nsection 8 not met: {len(eligible)} eligible instruments < {MINIMUM_INSTRUMENTS}")
        print("reporting coverage and refusing a verdict")

    # --- cross-sectional aggregation, in canonical instrument order ----------------------
    cs_months: list[Decimal] = []
    ar_months: list[Decimal] = []
    cs_negative_months = ar_negative_months = 0
    total_months = 0

    per_instrument: list[dict[str, object]] = []
    for instrument_id in sorted(eligible):
        windows = windows_by_instrument[instrument_id]
        cs_values = [
            spread.half_spread_bps(w.corwin_schultz)
            for w in windows if w.corwin_schultz is not None
        ]
        ar_values = [
            spread.half_spread_bps(w.abdi_ranaldo)
            for w in windows if w.abdi_ranaldo is not None
        ]
        cs_months.extend(cs_values)
        ar_months.extend(ar_values)
        cs_negative_months += sum(1 for w in windows if w.cs_negative)
        ar_negative_months += sum(1 for w in windows if w.ar_negative)
        total_months += len(windows)

        per_instrument.append({
            "instrument_id": instrument_id,
            "months": len(windows),
            "adtv": str(adtv_by_instrument[instrument_id]),
            "last_close": str(price_by_instrument[instrument_id]),
            "median_cs_half_spread_bps": str(spread.median(cs_values) or Decimal(0)),
            "median_ar_half_spread_bps": str(spread.median(ar_values) or Decimal(0)),
        })

    cs_median = spread.median(cs_months)
    ar_median = spread.median(ar_months)
    cs_negative_rate = (
        Decimal(cs_negative_months) / Decimal(total_months) if total_months else Decimal(0)
    )
    ar_negative_rate = (
        Decimal(ar_negative_months) / Decimal(total_months) if total_months else Decimal(0)
    )

    # ADTV-weighted, over per-instrument medians so a heavily-sampled name cannot dominate twice.
    weighted_cs = spread.weighted_mean([
        (Decimal(str(row["median_cs_half_spread_bps"])), adtv_by_instrument[str(row["instrument_id"])])
        for row in per_instrument
    ])
    weighted_ar = spread.weighted_mean([
        (Decimal(str(row["median_ar_half_spread_bps"])), adtv_by_instrument[str(row["instrument_id"])])
        for row in per_instrument
    ])

    # --- PR-008 section 6, applied -------------------------------------------------------
    if len(eligible) < MINIMUM_INSTRUMENTS:
        verdict, why = "refused", f"{len(eligible)} eligible instruments < {MINIMUM_INSTRUMENTS}"
    elif cs_median is None or ar_median is None:
        verdict, why = "refused", "no usable monthly estimates"
    elif cs_negative_rate > NEGATIVE_RATE_LIMIT or ar_negative_rate > NEGATIVE_RATE_LIMIT:
        verdict = "inconclusive"
        why = (f"negative-estimate rate above {NEGATIVE_RATE_LIMIT}: "
               f"CS {cs_negative_rate:.3f}, AR {ar_negative_rate:.3f}")
    elif cs_median > ASSUMED_HALF_SPREAD_BPS and ar_median > ASSUMED_HALF_SPREAD_BPS:
        verdict = "accept"
        why = "both estimators put the median half-spread above the assumed 5bp"
    elif cs_median <= ASSUMED_HALF_SPREAD_BPS and ar_median <= ASSUMED_HALF_SPREAD_BPS:
        verdict = "reject"
        why = "both estimators put the median half-spread at or below the assumed 5bp"
    else:
        verdict = "inconclusive"
        why = "the estimators fall on opposite sides of 5bp"

    # --- PR-008 section 5 secondary ------------------------------------------------------
    bound_bps = ASSUMED_HALF_SPREAD_BPS * BREAK_EVEN_MULTIPLE
    worst = max(cs_median or Decimal(0), ar_median or Decimal(0))
    pr005_survives = worst < bound_bps

    report: dict[str, object] = {
        "prereg": "PR-008",
        "knowledge_time": str(knowledge_time),
        "store": str(args.store),
        "survivorship": "absent",
        "country": "US",
        "run_parameters": {
            "liquidity_rule": {
                "min_price": str(RULE.min_price), "min_adtv": str(RULE.min_adtv),
                "adtv_window": RULE.adtv_window, "min_history": RULE.min_history,
            },
            "minimum_pairs_per_month": MINIMUM_PAIRS_PER_MONTH,
            "minimum_months_per_instrument": MINIMUM_MONTHS_PER_INSTRUMENT,
            "minimum_instruments": MINIMUM_INSTRUMENTS,
            "assumed_half_spread_bps": str(ASSUMED_HALF_SPREAD_BPS),
            "break_even_multiple": str(BREAK_EVEN_MULTIPLE),
        },
        "coverage": {
            "instruments_in_store": len(instrument_ids),
            "eligible": len(eligible),
            "rejected_by_rule": rejected,
            "short_history_or_months": short,
            "instrument_months": total_months,
        },
        "corwin_schultz": {
            "median_half_spread_bps": None if cs_median is None else str(cs_median),
            "adtv_weighted_half_spread_bps": None if weighted_cs is None else str(weighted_cs),
            "p25_half_spread_bps": str(spread.quantile(cs_months, Decimal("0.25")) or Decimal(0)),
            "p75_half_spread_bps": str(spread.quantile(cs_months, Decimal("0.75")) or Decimal(0)),
            "p95_half_spread_bps": str(spread.quantile(cs_months, Decimal("0.95")) or Decimal(0)),
            "negative_months": cs_negative_months,
            "negative_rate": str(cs_negative_rate),
        },
        "abdi_ranaldo": {
            "median_half_spread_bps": None if ar_median is None else str(ar_median),
            "adtv_weighted_half_spread_bps": None if weighted_ar is None else str(weighted_ar),
            "p25_half_spread_bps": str(spread.quantile(ar_months, Decimal("0.25")) or Decimal(0)),
            "p75_half_spread_bps": str(spread.quantile(ar_months, Decimal("0.75")) or Decimal(0)),
            "p95_half_spread_bps": str(spread.quantile(ar_months, Decimal("0.95")) or Decimal(0)),
            "negative_months": ar_negative_months,
            "negative_rate": str(ar_negative_rate),
        },
        "by_adtv_decile": _decile_table(
            [(adtv_by_instrument[str(r["instrument_id"])],
              Decimal(str(r["median_cs_half_spread_bps"]))) for r in per_instrument],
            "adtv",
        ),
        "by_price_decile": _decile_table(
            [(price_by_instrument[str(r["instrument_id"])],
              Decimal(str(r["median_cs_half_spread_bps"]))) for r in per_instrument],
            "price",
        ),
        "pr005_sensitivity": {
            "break_even_half_spread_bps": str(bound_bps),
            "worst_estimator_median_bps": str(worst),
            "survives_under_every_split": pr005_survives,
            "note": (
                "PR-005's +0.028R survives the spread correction under every commission/slippage "
                "split when the measured half-spread is below the break-even bound. At or above "
                "it, the sign is not determined by what PR-005 recorded."
            ),
        },
        "verdict": verdict,
        "verdict_reason": why,
        "exploratory": _exploratory(full_series, adtv_by_instrument),
        "per_instrument": per_instrument,
    }

    print(f"\n{'estimator':<18}{'median':>10}{'p25':>10}{'p75':>10}{'p95':>10}{'wtd':>10}{'neg':>8}")
    for name, block in (("corwin_schultz", report["corwin_schultz"]),
                        ("abdi_ranaldo", report["abdi_ranaldo"])):
        assert isinstance(block, dict)
        print(f"{name:<18}"
              f"{float(Decimal(str(block['median_half_spread_bps']))):>10.3f}"
              f"{float(Decimal(str(block['p25_half_spread_bps']))):>10.3f}"
              f"{float(Decimal(str(block['p75_half_spread_bps']))):>10.3f}"
              f"{float(Decimal(str(block['p95_half_spread_bps']))):>10.3f}"
              f"{float(Decimal(str(block['adtv_weighted_half_spread_bps']))):>10.3f}"
              f"{float(Decimal(str(block['negative_rate']))):>8.3f}")

    print(f"\nassumed (DR-004): {ASSUMED_HALF_SPREAD_BPS} bp per side")
    print(f"PR-005 break-even: {bound_bps} bp per side")
    print(f"PR-005 survives under every split: {pr005_survives}")
    print(f"\nVERDICT: {verdict} - {why}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
