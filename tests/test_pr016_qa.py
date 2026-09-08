"""The QA re-check's own arithmetic, on bars where the answer is by hand.

`BACKTEST_PROTOCOL` §7 asks for an INDEPENDENT reconstruction, so `verify_pr016_qa.py` imports
nothing from the harness — Wilder's ATR, the two fill rules and the four ordering rules are written
out again there. **That independence is exactly what makes it able to be wrong on its own**, and a
re-check that silently agrees is worth less than no re-check at all: it would report "2,390 agreed"
whatever the run had produced.

So these tests do not compare it to the engine. They assert the arithmetic against hand-built bars,
which is the only way to tell a correct second implementation from a second copy of the first.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def qa():
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location("_qa", REPO / "tools" / "verify_pr016_qa.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Bar:
    def __init__(self, o: str, h: str, low: str, c: str, day: int = 1) -> None:
        self.open, self.high, self.low, self.close = (
            Decimal(o), Decimal(h), Decimal(low), Decimal(c))
        self.session_date = date(2020, 1, 1) + timedelta(days=day)


def flat(n: int, price: str = "100", spread: str = "2") -> list[Bar]:
    """`n` identical bars whose true range is `spread` every session."""
    high = str(Decimal(price) + Decimal(spread) / 2)
    low = str(Decimal(price) - Decimal(spread) / 2)
    return [Bar(price, high, low, price, day=i) for i in range(n)]


# --- Wilder's ATR --------------------------------------------------------------------------------

def test_atr_declines_to_answer_before_warm_up(qa) -> None:
    """A partially warmed average looks exactly like a valid one downstream, which is why the
    component refuses. A re-check that filled in early values would reconstruct a stop the run
    never placed."""
    values = qa.wilder_atr(flat(20), 14)
    assert values[0] is None
    assert all(v is None for v in values[:14])
    assert values[14] is not None


def test_atr_of_a_constant_range_is_that_range(qa) -> None:
    values = qa.wilder_atr(flat(40, spread="2"), 14)
    assert values[-1] == pytest.approx(Decimal(2))


def test_true_range_counts_the_GAP_against_the_previous_close(qa) -> None:
    """The reason it is TRUE range: a bar that opens far from the last close has range its own
    high-low misses, and a stop is placed off that number."""
    bars = flat(20, price="100", spread="2")
    bars.append(Bar("200", "201", "199", "200", day=20))     # own range 2, gap 100
    values = qa.wilder_atr(bars, 14)
    without_gap = qa.wilder_atr(flat(21, spread="2"), 14)
    # true range 101, not 2: max(201-199, |201-100|, |199-100|). Wilder then SMOOTHS it in, so
    # the assertion is the exact smoothed value rather than a hand-waved "much bigger" - the
    # smoothing is half of what is under test.
    assert values[-1] == pytest.approx((Decimal(2) * 13 + Decimal(101)) / 14)
    assert values[-1] > without_gap[-1] * 4


def test_the_average_smooths_rather_than_re_averaging(qa) -> None:
    """Wilder: `(prev * (period - 1) + latest) / period`. A simple rolling mean would move
    differently and every stop after warm-up would sit somewhere else."""
    bars = flat(15, spread="2") + [Bar("100", "116", "84", "100", day=15)]   # a 32-wide bar
    values = qa.wilder_atr(bars, 14)
    previous = values[14]
    assert values[15] == pytest.approx((previous * 13 + Decimal(32)) / 14)


# --- the four ordering rules ---------------------------------------------------------------------

STOP, TARGET = Decimal("90"), Decimal("110")


def test_a_session_opening_below_the_stop_fills_at_the_OPEN(qa) -> None:
    bars = [Bar("100", "101", "99", "100"), Bar("85", "112", "84", "111", day=2)]
    assert qa.walk(bars, 0, STOP, TARGET, 20) == (1, Decimal("85"), "stop_gap")


def test_a_session_opening_above_the_target_fills_at_the_TARGET(qa) -> None:
    """The favourable gap is not credited: a real limit would have filled at 118."""
    bars = [Bar("100", "101", "99", "100"), Bar("118", "120", "117", "119", day=2)]
    assert qa.walk(bars, 0, STOP, TARGET, 20) == (1, TARGET, "target")


def test_a_bar_reaching_both_legs_intraday_takes_the_STOP(qa) -> None:
    bars = [Bar("100", "111", "89", "105")]
    assert qa.walk(bars, 0, STOP, TARGET, 20) == (0, STOP, "stop")


def test_the_target_beats_the_clock_on_the_final_session(qa) -> None:
    bars = flat(20) + [Bar("100", "111", "99", "101", day=20)]
    assert qa.walk(bars, 0, STOP, TARGET, 20) == (20, TARGET, "target")


def test_a_position_reaching_neither_leg_times_out_at_the_close(qa) -> None:
    bars = flat(30)
    assert qa.walk(bars, 0, STOP, TARGET, 20) == (20, Decimal("100"), "time")


def test_the_entry_bar_itself_can_stop_the_position_out(qa) -> None:
    """The engine manages a position from the bar it opened on. A re-check that started one bar
    later would silently move every same-session stop-out to the next session."""
    bars = [Bar("100", "101", "88", "95"), Bar("95", "96", "94", "95", day=2)]
    assert qa.walk(bars, 0, STOP, TARGET, 20) == (0, STOP, "stop")


def test_a_two_slot_policy_never_takes_a_target(qa) -> None:
    """`unselected_two_slot` passes no target, which is what `PR-005` ran."""
    bars = flat(10) + [Bar("100", "130", "99", "129", day=10)] + flat(15)
    index, _, reason = qa.walk(bars, 0, STOP, None, 20)
    assert reason == "time"
    assert index == 20


def test_a_window_ending_while_the_position_is_open_returns_nothing(qa) -> None:
    """The caller turns that into `end_of_data` at the last close - it is not the walk's to name."""
    assert qa.walk(flat(5), 0, STOP, TARGET, 20) is None


# --- the labelling artefact ----------------------------------------------------------------------

def test_end_of_data_against_time_on_the_last_bar_is_a_label_difference(qa) -> None:
    """Found on the first real run: 10 of 2,400. The engine's loop stops one bar short because an
    ENTRY needs `bars[i + 1]`, so a position completing its hold on the final bar is closed as
    `END_OF_DATA` at the same close it would have got as `TIME`."""
    bars = flat(21)
    differences = ["exit_reason: run end_of_data vs rebuilt time"]
    rebuilt = {"exit_reason": "time", "exit_date": bars[-1].session_date}
    assert qa.is_final_bar_label(differences, rebuilt, bars)


def test_the_same_label_difference_NOT_on_the_last_bar_is_a_real_disagreement(qa) -> None:
    """The clause that keeps this bucket honest. Anywhere but the final bar, the engine had no
    reason to say `end_of_data` and the run and the evidence really differ."""
    bars = flat(30)
    differences = ["exit_reason: run end_of_data vs rebuilt time"]
    rebuilt = {"exit_reason": "time", "exit_date": bars[10].session_date}
    assert not qa.is_final_bar_label(differences, rebuilt, bars)


def test_a_price_difference_is_never_a_label_difference(qa) -> None:
    bars = flat(21)
    rebuilt = {"exit_reason": "time", "exit_date": bars[-1].session_date}
    assert not qa.is_final_bar_label(
        ["exit_reason: run end_of_data vs rebuilt time", "exit_price: run 1 vs rebuilt 2"],
        rebuilt, bars)


def test_the_other_direction_is_not_excused(qa) -> None:
    """`time` recorded where the evidence says `end_of_data` is a different fault and is not this
    artefact. Excusing it symmetrically would hide it."""
    bars = flat(21)
    rebuilt = {"exit_reason": "end_of_data", "exit_date": bars[-1].session_date}
    assert not qa.is_final_bar_label(
        ["exit_reason: run time vs rebuilt end_of_data"], rebuilt, bars)


# --- the comparison ------------------------------------------------------------------------------

def row(**over: str) -> dict[str, str]:
    base = {"entry_price": "100.5", "stop_price": "90.25", "exit_price": "110.75",
            "exit_date": "2020-01-21", "exit_reason": "target", "shares": "97",
            "initial_risk_per_share": "10.25", "costs": "0.97"}
    base.update(over)
    return base


def rebuilt(**over) -> dict:
    base = {"entry_price": Decimal("100.5"), "stop_price": Decimal("90.25"),
            "exit_price": Decimal("110.75"), "exit_date": date(2020, 1, 21),
            "exit_reason": "target", "shares": 97,
            "initial_risk_per_share": Decimal("10.25"), "costs": Decimal("0.97")}
    base.update(over)
    return base


def test_an_exact_match_reports_nothing(qa) -> None:
    assert qa.compare(rebuilt(), row()) == []


def test_a_price_that_differs_in_the_last_place_is_a_DISAGREEMENT(qa) -> None:
    """Exact `Decimal`, not `approx`. These are the same arithmetic on the same stored numbers, so
    a difference is a disagreement and never a rounding artefact - §7's own sentence."""
    assert qa.compare(rebuilt(entry_price=Decimal("100.500001")), row()) != []


def test_every_recorded_field_is_compared_and_none_is_skipped(qa) -> None:
    """A field left out of `CHECKED` is a field the re-check cannot fail on, and nothing would
    say so."""
    wrong = {"entry_price": "1", "stop_price": "1", "exit_price": "1",
             "exit_date": "2020-02-02", "exit_reason": "stop", "shares": "1",
             "initial_risk_per_share": "1", "costs": "1"}
    assert set(wrong) == set(qa.CHECKED), "a field was added to CHECKED and not to this test"
    for field in qa.CHECKED:
        assert qa.compare(rebuilt(), row(**{field: wrong[field]})) != [], field
