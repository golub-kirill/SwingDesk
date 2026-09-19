"""Which of `PR-024`'s entries were garbage? EXPLORATORY - where `PR-026`..`PR-029` came from.

**Hypothesis generation, and it says so in its payload.** On 2026-09-19 the owner, shown that
`CARD-001` breaks even entered at 15:55, asked whether the card buys garbage and wanted ideas. This
slices `PR-024`'s own entries - the 15:55 arm's net per dollar, and the open's beside it - by what
was known at the SIGNAL close: price, ATR as a share of price, the signal day's and the last five
days' return, the distance above the 20-day mean and below the 52-week high, the open's own quoted
half-spread, `SPY` against its 200-day mean, and the kind of instrument. It looked at the answer,
so nothing in it is evidence; four of its ideas were registered as `PR-026`..`PR-029` on a window
it never read, and `trial_budget.py` counts one configuration per feature sliced.

**The kind of instrument uses the registered rule** (`run_pr026.levered_name`). The first cut of
this slicing, on 2026-09-19, used a rougher name pattern and reported 407 leveraged-or-inverse
entries at −0.70% a trade; the rule `PR-026` registers counts 423 at −0.68%, and is the one to cite.

    PYTHONPATH=$PWD/src python tools/measure_entry_features.py --data <store> --minutes <m> \
        --quotes <q> --directory <dir> --as-of <t> --minutes-as-of <t> --quotes-as-of <t>
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import attribute_pr024 as attribution
import run_pr024 as p24
import run_pr026 as registered
from run_pr014 import BENCHMARK
from run_pr016 import atr_registry
from swingdesk.contracts.market import Interval, Series
from swingdesk.derived_observations import atr as atr_component
from swingdesk.market_data import BarStore
from swingdesk.market_data.quotes import OPEN

RESULT = REPO / "docs" / "decisions" / "measurements" / "entry-features-2026-09-19.json"
QUINTILES = 5
#: Sessions of history a feature reads back: the 52-week high.
HISTORY = 252
FEATURES = ("price", "atr_share", "signal_day_return", "five_day_return", "above_20_day_mean",
            "below_52_week_high", "open_half_spread_bps")


def row(label: str, group: Sequence[dict[str, Any]]) -> dict[str, Any]:
    close = [g["close_net"] for g in group]
    opened = [g["open_net"] for g in group if g["open_net"] is not None]
    return {"group": label, "entries": len(close),
            "close_mean": statistics.fmean(close) if close else None,
            "close_win_share": sum(x > 0 for x in close) / len(close) if close else None,
            "close_median": statistics.median(close) if close else None,
            "open_mean": statistics.fmean(opened) if opened else None}


def quintiles(records: Sequence[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    usable = sorted((r for r in records if r[key] is not None), key=lambda r: r[key])
    out = []
    for q in range(QUINTILES):
        group = usable[q * len(usable) // QUINTILES:(q + 1) * len(usable) // QUINTILES]
        if group:
            out.append({**row(f"Q{q + 1}", group), "from": group[0][key], "to": group[-1][key]})
    return out


def features_of(args: argparse.Namespace, walked: Sequence[attribution.Walked]
                ) -> list[dict[str, Any]]:
    """Each priced entry's 15:55 and open net, and what was known at its signal close."""
    index = registered.directory_index(args.directory, None)
    by_name: dict[str, list[attribution.Walked]] = defaultdict(list)
    for w in walked:
        if w.priced((p24.LATE,), ("net",)):
            by_name[w.entry.instrument_id].append(w)
    records: list[dict[str, Any]] = []
    with BarStore(args.data / "bars.duckdb") as bars:
        as_of = p24.read_instant(args.as_of, bars.latest_knowledge_time())
        spy = bars.as_of(BENCHMARK, Interval.DAY, Series.RAW, as_of)
        if spy is None:
            raise SystemExit(f"{BENCHMARK} is not in the store")
        spy_pairs = [(b.session_date, float(b.close)) for b in spy.bars]
        registry = atr_registry()
        for name in sorted(by_name):
            series = bars.as_of(name, Interval.DAY, Series.RAW, as_of)
            if series is None:
                continue
            position = {b.session_date: i for i, b in enumerate(series.bars)}
            atr_series = atr_component.compute(series, registry)
            entry = registered.listing(index, name)
            for w in by_name[name]:
                i = position.get(w.entry.signal_date)
                atr = atr_series.observations[i].value if i is not None else None
                if i is None or i < HISTORY or atr is None:
                    continue
                closes = [float(b.close) for b in series.bars[i - HISTORY + 1:i + 1]]
                close = closes[-1]
                _, regime = registered.features(series, w.entry.signal_date, spy_pairs)
                spread = w.spreads.get(OPEN)
                records.append({
                    "close_net": p24.per_dollar(w.trade(p24.LATE)),
                    "open_net": (p24.per_dollar(w.trade(p24.BASE))
                                 if w.priced((p24.BASE,), ("net",)) else None),
                    "close_exit": w.trade(p24.LATE).exit_reason.value,
                    "price": close, "atr_share": float(atr) / close,
                    "signal_day_return": close / closes[-2] - 1,
                    "five_day_return": close / closes[-6] - 1,
                    "above_20_day_mean": close / statistics.fmean(closes[-20:]) - 1,
                    "below_52_week_high": close / max(closes) - 1,
                    "open_half_spread_bps": float(spread) if spread is not None else None,
                    "spy_above_200": regime,
                    "kind": ("unlisted" if entry is None else "stock" if not entry.is_etf
                             else "levered fund" if registered.is_levered(entry) else "fund"),
                })
    return records


def build(args: argparse.Namespace) -> dict[str, Any]:
    walked, _, instants = attribution.walk_sample(args, p24.read_sample(args.sample))
    records = features_of(args, walked)

    def split(value: Callable[[dict[str, Any]], Any]) -> list[dict[str, Any]]:
        groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for r in records:
            groups[value(r)].append(r)
        return [row(str(k), g) for k, g in sorted(groups.items(), key=lambda kv: str(kv[0]))]

    return {
        "for": "the hypotheses of PR-026..PR-029",
        "exploratory": True,
        "purpose": ("PR-024's own entries sliced by what was known at the signal close; "
                    "hypothesis generation only - it looked at the answer"),
        "as_of": instants,
        "population": "PR-024-sample.jsonl, the 15:55 arm's net per dollar, the open's beside it",
        "overall": row("all", records),
        "by_feature": {key: quintiles(records, key) for key in FEATURES},
        "by_market_regime": split(lambda r: r["spy_above_200"]),
        "by_kind": split(lambda r: r["kind"]),
        "by_close_exit": split(lambda r: r["close_exit"]),
        "kinds_counted": dict(Counter(r["kind"] for r in records)),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--minutes", type=Path, required=True)
    parser.add_argument("--quotes", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--sample", type=Path, default=p24.SAMPLE)
    parser.add_argument("--as-of")
    parser.add_argument("--minutes-as-of")
    parser.add_argument("--quotes-as-of")
    parser.add_argument("--out", type=Path, default=RESULT)
    args = parser.parse_args(argv)
    payload = build(args)
    args.out.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    overall = payload["overall"]
    print(f"entries {overall['entries']}   15:55 mean {overall['close_mean'] * 100:+.3f}%   "
          f"win {overall['close_win_share']:.1%}")
    for key, rows in payload["by_feature"].items():
        print(f"  {key}: " + "  ".join(f"{r['group']} {r['close_mean'] * 100:+.2f}%"
                                      for r in rows))
    for block in ("by_market_regime", "by_kind"):
        print(f"  {block}: " + "  ".join(f"{r['group']} n={r['entries']} {r['close_mean'] * 100:+.2f}%"
                                         for r in payload[block]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


