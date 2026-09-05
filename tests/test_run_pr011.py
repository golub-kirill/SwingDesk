"""PR-011's runner, on constructed series where the right answer is arithmetic.

The tests that matter are the ones that pin the pre-registration's own text to code: the band edges,
the decision rule's five branches, and the threshold FORMULA rather than the number it produced.
`AGENTS.md` §10.8 - a claim that something is checked is itself a claim, so the checks are here
rather than described.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from pathlib import Path

from swingdesk.application.universe import ADTV_WINDOW
from swingdesk.contracts.market import Bar, BarSeries, Interval, Series
from swingdesk.reference_data import universe as rules
from swingdesk.validation.backtest import CostModel, ExitPolicy

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import run_pr011  # noqa: E402 - the path insert above is what makes this importable

KNOWN = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
FREE = CostModel(commission_per_share=Decimal(0), slippage_bps=Decimal(0))
POLICY = ExitPolicy(atr_stop_multiple=Decimal(2), max_holding_bars=20)

#: Admits everything. The liquidity rule is PR-013's business and is exercised there; these tests
#: are about the walk, and a rule that refused would make every one of them vacuous.
OPEN_RULE = rules.LiquidityRule(
    min_price=Decimal(0), min_adtv=Decimal(0), adtv_window=ADTV_WINDOW,
    min_history=1, adtv_lag=0,
)


def _series(rows: list[tuple[str, str, str, str]]) -> BarSeries:
    """rows are (open, high, low, close), one per consecutive session."""
    bars = []
    for offset, (o, h, low, c) in enumerate(rows):
        session = date(2025, 1, 6) + timedelta(days=offset)
        bars.append(Bar(
            instrument_id="TEST.1", interval=Interval.DAY, series=Series.RAW,
            event_time=datetime(session.year, session.month, session.day, tzinfo=UTC),
            session_date=session, open=Decimal(o), high=Decimal(h), low=Decimal(low),
            close=Decimal(c), volume=1_000_000, knowledge_time=KNOWN,
        ))
    return BarSeries(instrument_id="TEST.1", interval=Interval.DAY, series=Series.RAW,
                     knowledge_time=KNOWN, bars=tuple(bars))


def _flat(count: int, price: str = "100") -> list[tuple[str, str, str, str]]:
    return [(price, price, price, price)] * count


# ------------------------------------------------------------------------------- the bands


def test_the_bands_partition_and_their_edges_are_the_registered_ones() -> None:
    """Upper bound exclusive throughout, so no ATR-percent lands in two bands or in none."""
    assert run_pr011.band_of(Decimal("0.00")) == "B1"
    assert run_pr011.band_of(Decimal("0.03")) == "B2", "the edge belongs to the band above"
    assert run_pr011.band_of(Decimal("0.06")) == "B3"
    assert run_pr011.band_of(Decimal("0.10")) == "B4"
    assert run_pr011.band_of(Decimal("0.4999")) == "B4"
    assert run_pr011.band_of(Decimal("0.50")) == "B5", "2 x ATR meets the price exactly here"
    assert run_pr011.band_of(Decimal("9")) == "B5"


def test_B5_is_where_two_atr_reaches_the_price_and_that_is_arithmetic_not_a_choice() -> None:
    """`entry - 2 x atr <= 0` is `atr / entry >= 0.5`. The band edge is that inequality."""
    _, low, _ = next(b for b in run_pr011.BANDS if b[0] == "B5")
    assert low == 1 / run_pr011.ATR_STOP_MULTIPLE


# ------------------------------------------------------------------------------- the walk


#: The first signal a real liquidity rule can admit. `admits` refuses a series too short for the
#: ADTV window rather than measuring on a partial one, so bar 0 is always refused - which is the
#: rule failing closed, and every fixture below is built to clear it rather than to dodge it.
FIRST_SIGNAL = run_pr011.FORMATION_EVERY


def test_a_touched_stop_costs_exactly_one_R_and_overshoots_by_zero() -> None:
    """`ExitPolicy.evaluate` fills a touched stop AT the stop, so the excess is zero by
    construction. This is amendment A-2's bound, pinned: the statistic can only be non-zero on a
    gap, and a test that did not say so would let the bound rot."""
    rows = _flat(FIRST_SIGNAL + 2) + [("100", "100", "89", "95")] + _flat(3)
    events, refused = run_pr011.walk(_series(rows), [Decimal(5)] * len(rows), OPEN_RULE, POLICY, FREE)

    assert "stop_not_positive" not in refused
    assert len(events) == 1
    assert events[0].exit_reason == "stop"
    assert events[0].overshoot == 0
    assert events[0].gapped is False


def test_a_gap_through_the_stop_overshoots_by_what_the_gap_cost() -> None:
    """Entry 100, stop 90, so 1R is 10. The session opens at 85 and fills there: 0.5R beyond."""
    rows = _flat(FIRST_SIGNAL + 2) + [("85", "86", "84", "85")] + _flat(3)
    events, _ = run_pr011.walk(_series(rows), [Decimal(5)] * len(rows), OPEN_RULE, POLICY, FREE)

    assert len(events) == 1
    assert events[0].exit_reason == "stop_gap"
    assert events[0].gapped is True
    assert events[0].overshoot == Decimal("0.5")


def test_a_time_exit_is_not_a_stop_out_and_carries_no_overshoot() -> None:
    """The statistic is conditional on a stop-out. A time exit that entered the mean as a zero
    would dilute every band by however often it did NOT stop, which is a different question."""
    rows = _flat(FIRST_SIGNAL + run_pr011.MAX_HOLDING_BARS + 2)
    events, _ = run_pr011.walk(_series(rows), [Decimal(1)] * len(rows), OPEN_RULE, POLICY, FREE)

    assert events, "the walk produced entries"
    assert all(e.overshoot is None for e in events)
    assert events[0].exit_reason == "time"


def test_a_non_positive_stop_is_REFUSED_AND_COUNTED_the_way_the_live_path_refuses_it() -> None:
    """`sizing.size_long`'s guard, reproduced rather than inferred. A refusal that vanished would
    make the population look cleaner than it is."""
    rows = _flat(FIRST_SIGNAL + 3, "10")
    events, refused = run_pr011.walk(_series(rows), [Decimal(9)] * len(rows), OPEN_RULE, POLICY, FREE)

    assert events == []
    assert refused["stop_not_positive"] == 1
    # A-2 item 3: the band and the arithmetic break are recorded SEPARATELY, because the band comes
    # from the signal bar and the stop from the next open. ATR 9 on a close of 10 is 90%, so B5.
    assert refused["stop_not_positive_B5"] == 1


def test_the_band_of_a_refused_stop_is_recorded_even_when_it_is_NOT_B5() -> None:
    """The boundary A-2 item 3 is about. ATR 4.80 on a close of 10 is 48% - band B4 - and the next
    open at 9.50 still gives `9.50 - 2 x 4.80 = -0.10`. Band membership and the arithmetic break
    genuinely disagree here, so neither may be inferred from the other."""
    rows = _flat(FIRST_SIGNAL + 1, "10") + [("9.50", "9.50", "9.50", "9.50")] + _flat(2, "9.50")
    events, refused = run_pr011.walk(
        _series(rows), [Decimal("4.80")] * len(rows), OPEN_RULE, POLICY, FREE)

    assert events == []
    assert refused["stop_not_positive_B4"] == 1
    assert "stop_not_positive_B5" not in refused


def test_the_walk_steps_by_the_holding_period_so_entries_never_overlap() -> None:
    """Non-overlapping is what makes each entry an observation rather than a re-reading of the
    same window. The step is the holding period, so one name never holds two positions at once."""
    rows = _flat(101)
    events, _ = run_pr011.walk(_series(rows), [Decimal(1)] * len(rows), OPEN_RULE, POLICY, FREE)

    signals = [e.signal_date for e in events]
    assert signals == sorted(signals)
    gaps = {(b - a).days for a, b in pairwise(signals)}
    assert gaps == {run_pr011.FORMATION_EVERY}


# ------------------------------------------------------------- the threshold and the decision rule


def test_the_threshold_is_the_registered_FORMULA_and_not_a_typed_number() -> None:
    """Amendment A-1. The caps are PINNED, the fraction is the owner's judgement, and the value
    falls out of both - so changing either moves it and nobody has to remember to retype 0.25."""
    assert run_pr011.THRESHOLD_R == Decimal("0.25")
    assert run_pr011.THRESHOLD_R == (
        run_pr011.MATERIALITY_FRACTION
        * run_pr011.MAX_OPEN_RISK_R
        / run_pr011.MAX_CONCURRENT_POSITIONS
    )


def _band(events: int, mean: float | None = None,
          ci: tuple[float, float] | None = None) -> dict[str, object]:
    return {
        "events": events, "meets_minimum": events >= run_pr011.MIN_EVENTS_PER_BAND,
        "mean_overshoot": mean,
        "ci_low": None if ci is None else ci[0], "ci_high": None if ci is None else ci[1],
    }


def test_an_unmet_sample_REFUSES_and_refused_is_not_inconclusive() -> None:
    """`AGENTS.md` §12: one says the study could not look, the other that it looked and could not
    tell. Gate 3f had no REFUSED once, and the first study to obey the template failed for it."""
    outcome, reason = run_pr011.verdict(_band(3), _band(500), (0.9, 0.5, 1.2))

    assert outcome == "refused"
    assert "sample rule" in reason


def test_both_bands_indistinguishable_from_zero_REJECTS_with_its_own_reason() -> None:
    """The `both negative` branch PREREG_TEMPLATE §8 now requires. A screen that removes names on
    which nothing goes wrong buys nothing, and that is a different finding from `no difference`."""
    outcome, reason = run_pr011.verdict(
        _band(500, 0.001, (-0.01, 0.01)), _band(500, 0.000, (-0.01, 0.01)), (0.001, -0.01, 0.4),
    )

    assert outcome == "reject"
    assert "holds everywhere measured" in reason


def test_an_interval_spanning_zero_REJECTS() -> None:
    outcome, reason = run_pr011.verdict(
        _band(500, 0.4, (0.2, 0.6)), _band(500, 0.1, (0.05, 0.2)), (0.3, -0.1, 0.7),
    )

    assert outcome == "reject"
    assert "includes zero" in reason


def test_a_difference_below_the_threshold_REJECTS_even_when_it_is_significant() -> None:
    """Significance is not materiality. With enough events any difference clears zero, which is
    exactly why §6 carries a magnitude as well as an interval."""
    outcome, reason = run_pr011.verdict(
        _band(500, 0.3, (0.25, 0.35)), _band(500, 0.1, (0.05, 0.15)), (0.20, 0.10, 0.30),
    )

    assert outcome == "reject"
    assert "below the registered threshold" in reason


def test_a_material_and_significant_difference_ACCEPTS() -> None:
    outcome, reason = run_pr011.verdict(
        _band(500, 0.5, (0.4, 0.6)), _band(500, 0.1, (0.05, 0.15)), (0.40, 0.25, 0.55),
    )

    assert outcome == "accept"
    assert "0.25R" in reason


# ------------------------------------------------------------------------- the publication guard


def test_a_truncated_universe_cannot_be_PUBLISHED() -> None:
    """`--limit` is a smoke run. A result of record over a subset is not the universe PR-011 §4
    fixed, and the tool refuses rather than trusting whoever typed it."""
    done = subprocess.run(
        [sys.executable, str(TOOLS / "run_pr011.py"), "--write", "--limit", "5"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )

    assert done.returncode == 2
    assert "Refused" in done.stdout


def test_a_smoke_run_prints_counts_and_WITHHOLDS_the_statistics() -> None:
    """The safeguard amendment A-3 paid for. `--limit` walks an alphabetical PREFIX, so its band
    means are not an early answer but a biased one - and a drafter who has seen a direction cannot
    report the real run as confirmatory (`PREREG_TEMPLATE.md` rule 3).

    Counts are printed either way: §8 makes deriving them step 1 of the runner, and a count is not
    a result.
    """
    rows = _flat(FIRST_SIGNAL + 2) + [("85", "86", "84", "85")] + _flat(3)
    events, _ = run_pr011.walk(_series(rows), [Decimal(5)] * len(rows), OPEN_RULE, POLICY, FREE)
    by_band = {name: run_pr011._summarise(events, name) for name, _, _ in run_pr011.BANDS}

    limited = run_pr011.band_lines(by_band, limited=True)
    full = run_pr011.band_lines(by_band, limited=False)

    assert any("entries=" in line for line in limited), "counts are printed either way"
    assert not any("mean_overshoot" in line for line in limited)
    assert not any("gap_rate" in line for line in limited)
    assert any("withheld" in line for line in limited)
    assert any("mean_overshoot" in line for line in full), "the real run prints them"
