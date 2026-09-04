"""Every bar the vendor served that arithmetic forbids, across the whole run log.

**The defect this exists for, 2026-09-04.** One evening's log carried 1,120 `vendor row(s) refused`
lines. 1,113 were the same routine condition - the current session's close not yet published,
arriving as `NaN`. Among them, invisible, was `DFNM`: an open of `47.369999` against a session
range of `[47.270000, 47.355000]`. The open is a trade that happened inside the session, and the
high is the highest price of that session, so an open above the high is not late data, it is
**impossible** data.

It was found by grouping the lines with a throwaway script. That is not a mechanism anybody can
rely on running, and `AGENTS.md` §10.6 says a fact a tool can derive is derived by that tool.

**What the first run of this tool found, which is the argument for it.** Not one such bar. **770**,
across 311 instruments and 52 runs - roughly fifteen every evening, every one of them buried since
the log began. The question "has this happened before" had an answer nobody could reach.

**It reports and it does not repair**, and that is a decision rather than an omission:

  - the violation is in the vendor's RAW feed, verified 2026-09-04 by refetching `DFNM` with
    `auto_adjust=False, back_adjust=False, repair=False` and getting the same three numbers. There
    is nothing to recompute from;
  - `open` is not a decorative field here - `trade_management/exits.py` decides a gap exit by it
    and `validation/backtest/engine.py` fills an entry at it. Nudging it into range would invent
    the price every R is denominated in;
  - published practice agrees: a bar violating `high >= max(o, l, c)` or `low <= min(o, h, c)` is
    flagged and excluded, with no tolerance offered. The comparison worth recording is `TradAlert`,
    this owner's earlier system, whose validator checks `high < low`, `close > high` and
    `close < low` - and **never checks `open` at all**. The bars refused here it accepted in
    silence.

Stdlib only. Reads a log, writes nothing.

    python tools/vendor_integrity.py
    python tools/vendor_integrity.py --log data/daily_run.log --top 20
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

REPO = Path(os.environ.get("SWINGDESK_ROOT") or Path(__file__).resolve().parents[1])

#: Both spellings, deliberately. The `VENDOR INTEGRITY` prefix was added 2026-09-04; every run
#: before that recorded the same violation only inside a `vendor row(s) refused` line, and a tool
#: that answered "has this happened before" from the new format alone would answer *no* for every
#: one of the 770 that already had. A history tool that cannot read history is decoration.
VIOLATION = re.compile(
    r"Value error, (?P<field>open|high|low|close) (?P<value>[\d.]+) "
    r"outside \[(?P<low>[\d.]+), (?P<high>[\d.]+)\]"
)
#: The instrument, when the line carries one. `VENDOR INTEGRITY <sym> <interval> <date>` and
#: `vendor row(s) refused  <sym> <interval>: ...` both put it in the same position.
SYMBOL = re.compile(r"(?:VENDOR INTEGRITY|vendor row\(s\) refused)\s+(?P<symbol>\S+)")


def violations(text: str) -> list[tuple[str, str, Decimal]]:
    """`(symbol, field, distance beyond the range as a percentage of price)` for every violation."""
    found: list[tuple[str, str, Decimal]] = []
    for line in text.splitlines():
        symbol_match = SYMBOL.search(line)
        symbol = symbol_match.group("symbol") if symbol_match else "?"
        for match in VIOLATION.finditer(line):
            try:
                value = Decimal(match.group("value"))
                low = Decimal(match.group("low"))
                high = Decimal(match.group("high"))
            except InvalidOperation:  # pragma: no cover - a mangled line is not a violation
                continue
            midpoint = (low + high) / 2
            if midpoint <= 0:  # pragma: no cover - a zero price is another gate's failure
                continue
            beyond = (low - value) if value < low else (value - high)
            found.append((symbol, match.group("field"), beyond / midpoint * 100))
    return found


def main(argv: list[str] | None = None) -> int:
    """Report every arithmetically impossible bar the log has ever recorded."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", type=Path, default=REPO / "data" / "daily_run.log")
    parser.add_argument("--top", type=int, default=10, help="how many instruments to name")
    args = parser.parse_args(argv)

    if not args.log.is_file():
        print(f"no run log at {args.log}", file=sys.stderr)
        return 3

    found = violations(args.log.read_text(encoding="utf-8", errors="replace"))
    if not found:
        print("no impossible bars in the log. The vendor has served nothing arithmetic forbids.")
        return 0

    distances = sorted(distance for _symbol, _field, distance in found)
    count = len(distances)
    print(f"{count} impossible bar(s) across {len(set(s for s, _, _ in found))} instrument(s)\n")

    print("field violated:")
    for field, n in Counter(field for _s, field, _d in found).most_common():
        print(f"   {field:<6} {n:>5}  ({100 * n / count:.0f}%)")

    # The DISTRIBUTION, not an average. Whether these are a rounding-scale artefact or genuine
    # corruption is the whole question, and a mean would answer neither.
    print("\nhow far beyond the session's own range, as a percentage of price:")
    for label, index in (("min", 0), ("median", count // 2),
                         ("90th", int(count * 0.9)), ("99th", int(count * 0.99)),
                         ("max", count - 1)):
        print(f"   {label:>7}  {distances[index]:.4f}%")

    print(f"\ninstruments hit most often (top {args.top}):")
    for symbol, n in Counter(s for s, _f, _d in found).most_common(args.top):
        print(f"   {symbol:<10} {n}")

    print("\nRefused, never repaired: `open` decides a gap exit and fills a backtest entry, so a "
          "value nudged into range would invent the price every R is measured in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
