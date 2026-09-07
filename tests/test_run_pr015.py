"""`PR-015`'s four new signals, its split, and the decision rule that reads three windows.

The study's claim is that five arms differ only in what they RANK on. Four things carry that and
none raises an error when wrong:

* **the split has to be stable.** Python's builtin `hash()` is salted per process for `str`, so a
  name split built on it lands differently on every run. The "holdout" would then be a fresh random
  sample each time — which looks exactly like a split, passes every test that checks it is roughly
  half, and protects against nothing.
* **the skip in `MOM_252_21` has to be real.** Without it the arm carries the most recent month,
  which is the reversal the `REVERSAL_21` arm is built on — the two arms would overlap in the one
  place they are supposed to be opposite, and the study would compare a signal with itself.
* **the reversal sign has to be negative.** Rank on the raw return and the arm silently becomes
  short-horizon momentum. The numbers would be perfectly well-formed.
* **§6 has to read BOTH holdouts.** The whole cost of the two-way split is paid at that line, and a
  rule that read one would produce a verdict indistinguishable from the registered one.

No store, no network.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from swingdesk.contracts.market import Bar, BarSeries, Interval, Series

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pr015():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_pr015", REPO / "tools" / "run_pr015.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def series(name: str, closes: list[str], highs: list[str] | None = None) -> BarSeries:
    when = datetime(2015, 1, 1, tzinfo=UTC)
    peaks = highs or closes
    bars = tuple(
        Bar(
            instrument_id=name, interval=Interval.DAY, series=Series.RAW,
            event_time=when + timedelta(days=i),
            session_date=date(2015, 1, 1) + timedelta(days=i),
            open=Decimal(c), high=Decimal(peaks[i]), low=Decimal(c), close=Decimal(c),
            volume=Decimal(1_000_000), knowledge_time=when,
        )
        for i, c in enumerate(closes)
    )
    return BarSeries(
        instrument_id=name, interval=Interval.DAY, series=Series.RAW,
        knowledge_time=when, bars=bars,
    )


def flat_then(final: str, length: int = 300) -> list[str]:
    """A flat series with one different close at the end."""
    return ["100"] * (length - 1) + [final]


# --- the split -----------------------------------------------------------------------------------

def test_the_name_split_is_stable_across_processes(pr015):
    """The mutation this file exists for.

    SHA-256 of the id, not `hash()`. The value is pinned here so that swapping the function - to
    the builtin, to a different digest, to a different byte - fails rather than silently producing
    a different universe on the next run.
    """
    assert pr015.half_of("AAPL") == pr015.half_of("AAPL")
    # Names chosen so that BOTH halves appear. The first version of this pin happened to draw five
    # names that all land in A, which a constant function would also satisfy - a pin that cannot
    # fail is not a pin.
    pinned = {n: pr015.half_of(n) for n in ("AAPL", "TSLA", "NVDA", "META", "JPM", "WMT")}
    assert pinned == {"AAPL": "A", "TSLA": "B", "NVDA": "A", "META": "B", "JPM": "A", "WMT": "B"}


def test_the_split_is_close_to_even_over_many_names(pr015):
    """A split that is 90/10 halves nothing. Over 2,000 ids it should land near even."""
    names = [f"SYM{i:04d}" for i in range(2000)]
    a = sum(1 for n in names if pr015.half_of(n) == "A")
    assert 900 < a < 1100


def test_every_window_of_the_two_by_two_is_reachable_and_named(pr015):
    early, late = date(2020, 6, 1), date(2023, 6, 1)
    assert pr015.window_of(early, "A") == "primary"
    assert pr015.window_of(late, "A") == "holdout_time"
    assert pr015.window_of(early, "B") == "holdout_names"
    assert pr015.window_of(late, "B") == "diagnostic_both"


def test_the_split_date_itself_belongs_to_the_primary_window(pr015):
    """`PRIMARY_END` is inclusive. An off-by-one here moves one rebalance between windows and
    nothing anywhere would say so."""
    assert pr015.window_of(pr015.PRIMARY_END, "A") == "primary"
    assert pr015.window_of(pr015.PRIMARY_END + timedelta(days=1), "A") == "holdout_time"


# --- the four signals ----------------------------------------------------------------------------

def test_reversal_ranks_the_LOSERS_first(pr015):
    """Sign. Rank on the raw return instead and the arm quietly becomes short-horizon momentum -
    the opposite of the one thing this arm was added to test."""
    loser = series("L", flat_then("80"))
    winner = series("W", flat_then("120"))
    assert pr015.reversal_21(loser, 299) > 0
    assert pr015.reversal_21(winner, 299) < 0
    assert pr015.reversal_21(loser, 299) > pr015.reversal_21(winner, 299)


def test_reversal_reads_exactly_twenty_one_sessions(pr015):
    """A move older than the window must not move the score."""
    closes = ["100"] * 260 + ["50"] + ["100"] * 39  # a crash 40 sessions ago
    assert pr015.reversal_21(series("X", closes), 299) == 0


def test_the_high_proximity_score_is_one_at_a_new_high_and_below_it_otherwise(pr015):
    at_high = series("H", ["100"] * 299 + ["150"], highs=["100"] * 299 + ["150"])
    off_high = series("O", ["100"] * 299 + ["75"], highs=["100"] * 299 + ["100"])
    assert pr015.high_52w(at_high, 299) == Decimal(1)
    assert pr015.high_52w(off_high, 299) == Decimal("0.75")


def test_the_high_proximity_score_forgets_a_peak_older_than_the_window(pr015):
    """252 sessions, not "ever". A name that peaked three years ago is at its 52-week high today."""
    highs = ["100"] * 20 + ["500"] + ["100"] * 279
    stale = series("S", ["100"] * 300, highs=highs)
    # At session 252 the trailing window is sessions 1..252 and still contains the old peak.
    assert pr015.high_52w(stale, 252) == Decimal("0.2")
    # At session 299 it is 48..299 and does not.
    assert pr015.high_52w(stale, 299) == Decimal(1)


def test_the_calmest_name_scores_HIGHEST_on_low_volatility(pr015):
    """The arm is MINUS the deviation, so the top decile is the calmest names. Drop the minus and
    the arm becomes a high-volatility screen and still produces a table."""
    calm = series("C", [str(100 + (i % 2)) for i in range(300)])
    wild = series("W", [str(100 + (i % 2) * 40) for i in range(300)])
    assert pr015.lowvol_126(calm, 299) > pr015.lowvol_126(wild, 299)
    assert pr015.lowvol_126(calm, 299) < 0


def test_momentum_skips_the_most_recent_month(pr015):
    """The skip is the whole difference between this arm and plain momentum, and it is why this arm
    and REVERSAL_21 are not two readings of one signal.

    Two names with an identical year and opposite last months must score the SAME here.
    """
    base = ["100"] * 49 + [str(100 + i) for i in range(1, 232)]  # 280 sessions, rising
    crashed = series("C", base + ["100"] * 20)
    surged = series("S", base + ["400"] * 20)
    # 300 bars, so index 299 is the LAST one and `period_return` can read it. The first version of
    # this fixture built 299 and asked for index 299: both sides returned None, the assertion
    # compared None to None, and the mutant that deletes the skip survived it.
    assert len(crashed.bars) == 300
    scored = pr015.mom_252_21(crashed, 299)
    assert scored is not None and scored > 0
    assert scored == pr015.mom_252_21(surged, 299)


def test_a_signal_that_cannot_be_computed_returns_None_rather_than_a_number(pr015):
    """A short series must drop out of the ranking, not sort to the bottom with a fabricated
    score. `PR-013`'s rankers sort an unscoreable name last so it competes and loses, which is
    right for a book and wrong for a decile study."""
    short = series("T", ["100"] * 30)
    assert pr015.high_52w(short, 29) is None
    assert pr015.lowvol_126(short, 29) is None
    assert pr015.mom_252_21(short, 29) is None


# --- the decision rule ---------------------------------------------------------------------------

def cell(net: float, low: float, high: float, *, n: int = 40, control: float = 0.05,
         stress: float | None = None) -> dict[str, object]:
    return {
        "rebalances": n,
        "sample_rule_met": n >= 24,
        "net_annual": net,
        "net_low": low,
        "net_high": high,
        "net_annual_3x": net - 0.02 if stress is None else stress,
        "net_excludes_zero": n >= 24 and (low > 0 or high < 0),
        "control_universe_annual": control,
        "both_negative": net < 0 and control < 0,
    }


def arm(name: str, primary, time, names) -> dict[str, object]:
    return {"arm": name, "primary": primary, "holdout_time": time, "holdout_names": names}


def test_nothing_qualifying_on_the_primary_window_is_a_REJECT(pr015):
    rows = [arm("A", cell(0.03, -0.05, 0.11), cell(0.02, -0.01, 0.05), cell(0.02, -0.01, 0.05))]
    outcome = pr015.decide(rows)
    assert outcome["verdict"] == "reject"


def test_both_holdouts_must_exclude_zero(pr015):
    """The cost of the two-way split is paid here. A rule reading one holdout would accept this."""
    passes = cell(0.12, 0.04, 0.20)
    fails = cell(0.06, -0.01, 0.13)
    assert pr015.decide([arm("A", cell(0.12, 0.04, 0.2), passes, passes)])["verdict"] == "accept"
    assert pr015.decide([arm("A", cell(0.12, 0.04, 0.2), passes, fails)])["verdict"] \
        == "inconclusive"
    assert pr015.decide([arm("A", cell(0.12, 0.04, 0.2), fails, passes)])["verdict"] \
        == "inconclusive"


def test_the_failing_holdout_is_named_in_the_reason(pr015):
    passes = cell(0.12, 0.04, 0.20)
    fails = cell(0.06, -0.01, 0.13)
    why = str(pr015.decide([arm("A", cell(0.12, 0.04, 0.2), passes, fails)])["why"])
    assert "holdout_names" in why
    assert "holdout_time" not in why


def test_the_largest_QUALIFYING_arm_is_chosen_not_the_largest_arm(pr015):
    """§6 selects on the largest estimate WHOSE INTERVAL EXCLUDES ZERO. An arm with a bigger point
    estimate and a straddling interval must not win - that is selecting on noise."""
    loud = arm("LOUD", cell(0.30, -0.10, 0.70), cell(0.2, 0.1, 0.3), cell(0.2, 0.1, 0.3))
    solid = arm("SOLID", cell(0.12, 0.04, 0.20), cell(0.1, 0.02, 0.18), cell(0.1, 0.02, 0.18))
    outcome = pr015.decide([loud, solid])
    assert outcome["verdict"] == "accept"
    assert outcome["arm"] == "SOLID"


def test_a_tie_at_the_top_is_fail_closed(pr015):
    """Two arms with the same qualifying estimate: §6 names an arm and cannot discriminate, and
    picking one after the run is exactly the snoop the split exists to prevent."""
    one = arm("ONE", cell(0.12, 0.04, 0.20), cell(0.1, 0.02, 0.2), cell(0.1, 0.02, 0.2))
    two = arm("TWO", cell(0.12, 0.03, 0.21), cell(0.1, 0.02, 0.2), cell(0.1, 0.02, 0.2))
    outcome = pr015.decide([one, two])
    assert outcome["verdict"] == "inconclusive"
    assert set(outcome["arms"]) == {"ONE", "TWO"}


def test_an_arm_that_dies_at_triple_costs_is_inconclusive(pr015):
    passes = cell(0.12, 0.04, 0.20)
    thin = cell(0.12, 0.04, 0.20, stress=-0.01)
    outcome = pr015.decide([arm("A", thin, passes, passes)])
    assert outcome["verdict"] == "inconclusive"
    assert "3x costs" in str(outcome["why"])


def test_two_losers_are_not_compared_on_which_loses_less(pr015):
    """`PREREG_TEMPLATE` rule 8's required branch. An interval strictly BELOW zero excludes zero,
    so without this branch a losing arm beating a worse universe would reach the holdout tests."""
    # `stress` is held positive on purpose: §6 says the both-negative branch fires "regardless",
    # so it must be reached even when the arm would ALSO fail another branch. The first version of
    # this fixture let the 3x branch answer first and the required branch was never exercised.
    losing = cell(-0.05, -0.12, -0.01, control=-0.09, stress=0.01)
    outcome = pr015.decide([arm("A", losing, losing, losing)])
    assert outcome["verdict"] == "inconclusive"
    assert "both negative" in str(outcome["why"])


def test_a_window_below_the_sample_minimum_cannot_qualify(pr015):
    """§8: 24 rebalances. A thin window with a clean interval must not carry a verdict."""
    thin = cell(0.12, 0.04, 0.20, n=9)
    assert thin["net_excludes_zero"] is False
    passes = cell(0.12, 0.04, 0.20)
    assert pr015.decide([arm("A", thin, passes, passes)])["verdict"] == "reject"


def test_the_diagnostic_cell_is_never_read_by_the_rule(pr015):
    """Amendment A-1: the fourth cell of the 2x2 is reported and not consulted. If §6 ever grew a
    branch that read it, this study would be selecting on four windows and registering three."""
    passes = cell(0.12, 0.04, 0.20)
    row = arm("A", cell(0.12, 0.04, 0.2), passes, passes)
    row["diagnostic_both"] = cell(-0.90, -1.5, -0.5, control=-0.9)
    assert pr015.decide([row])["verdict"] == "accept"


# --- the arms share one population ---------------------------------------------------------------

def test_every_arm_ranks_within_the_pool_it_is_given(pr015):
    """The five arms must differ in ORDER and never in membership: a name absent from one arm's
    output because that arm could not score it is a population difference wearing a signal's
    clothes. The history floor in `main` is the maximum over the arms for this reason."""
    names = [f"N{i:03d}" for i in range(40)]
    by_name = {
        n: series(n, [str(100 + (i % 7) + j * 0.1) for j in range(300)])
        for i, n in enumerate(names)
    }
    by_name["SPY"] = series("SPY", ["100"] * 300)
    pool = [pr015.Candidate(n, 299) for n in names]
    for name in pr015.SCORERS:
        top = pr015.rank_by(name, pool, by_name, by_name["SPY"])
        assert top, f"{name} selected nothing"
        assert set(top) <= set(names)
        assert len(top) == int(len(names) * float(pr015.DECILE))


def test_a_thin_window_cannot_qualify_however_clean_its_interval_is(pr015):
    """§8's minimum, at the one line that enforces it.

    A window with nine rebalances still produces an interval - it is just an interval about nine
    numbers - and it can easily sit entirely above zero. `qualifies` is what refuses it, and it was
    inlined in `main` until a surviving mutant showed that no test could reach it there.
    """
    clean_and_thin = {"net_low": 0.04, "net_high": 0.2, "sample_rule_met": False}
    clean_and_full = {"net_low": 0.04, "net_high": 0.2, "sample_rule_met": True}
    straddling = {"net_low": -0.04, "net_high": 0.2, "sample_rule_met": True}
    below_zero = {"net_low": -0.2, "net_high": -0.04, "sample_rule_met": True}
    assert pr015.qualifies(clean_and_thin) is False
    assert pr015.qualifies(clean_and_full) is True
    assert pr015.qualifies(straddling) is False
    # An interval strictly BELOW zero excludes zero too. §6 relies on the both-negative branch to
    # stop that becoming a finding, not on this flag.
    assert pr015.qualifies(below_zero) is True
    assert pr015.qualifies({"rebalances": 0, "sample_rule_met": False}) is False


# --- the capped, overlapping book (amendment A-2) ------------------------------------------------
#
# `risk.max_concurrent_positions` is 4 and it binds long before the decile does, so the book this
# system can hold is four names and not a hundred and thirty. Three things carry that and none
# raises: which name fills a freed slot, what an EMPTY slot costs, and whether the cost is
# annualised by the rebalance step or by the holding period.


def test_a_freed_slot_takes_the_best_name_that_is_not_already_held(pr015):
    """Taking the top-ranked name outright would let one name occupy two slots - a bigger bet than
    the cap permits, and a book that quietly concentrates while reporting four positions."""
    held = ["AAA", "BBB", "CCC"]
    assert pr015.fill(held, ["AAA", "BBB", "DDD", "EEE"], 4) == ["AAA", "BBB", "CCC", "DDD"]


def test_a_full_book_buys_nothing(pr015):
    """The cap is a cap. A rebalance that found a better name may not act on it: the position it
    would replace has not reached `exit.max_holding_period`, and the holding period is the subject
    of this study."""
    held = ["AAA", "BBB", "CCC", "DDD"]
    assert pr015.fill(held, ["ZZZ"], 4) == held


def test_the_slot_stays_empty_when_every_eligible_name_is_already_held(pr015):
    """The owner's instruction, literally: *"or non-overlapping if there is no good place"*.
    Filling it with the next name down would be the study answering a question nobody asked."""
    held = ["AAA", "BBB"]
    assert pr015.fill(held, ["AAA", "BBB"], 4) == ["AAA", "BBB"]
    assert pr015.fill(held, [], 4) == ["AAA", "BBB"]


def test_the_book_is_built_in_age_order_so_the_oldest_can_be_dropped(pr015):
    """The caller drops `held[0]` when the book is full, so a new name must go on the END. Append
    at the front and positions would be closed in the order they were BOUGHT-in-reverse, which is
    a last-in-first-out book and not a twenty-session hold."""
    book = []
    for step, name in enumerate(("AAA", "BBB", "CCC", "DDD")):
        book = pr015.fill(book, [name], 4)
        assert book[-1] == name
        assert len(book) == step + 1


def index_for(names: dict[str, object], start, end):
    return {n: {start: 0, end: 1} for n in names}


def test_an_empty_slot_is_cash_and_its_drag_is_charged(pr015):
    """The mutation this section exists for.

    Three names each up 10% in a FOUR-slot book returns 7.5%, not 10%. Dividing by `len(held)`
    would price the book as if the fourth quarter of the capital did not exist - and it would
    flatter exactly the dates on which the screen could not fill the book, which are the early
    ones with a thin cross-section.
    """
    start, end = date(2015, 1, 1), date(2015, 1, 2)
    by_name = {n: series(n, ["100", "110"]) for n in ("A", "B", "C")}
    idx = {n: {start: 0, end: 1} for n in by_name}
    three_of_four = pr015.capped_return(["A", "B", "C"], by_name, idx, start, end, 4)
    three_of_three = pr015.capped_return(["A", "B", "C"], by_name, idx, start, end, 3)
    assert three_of_four == Decimal("0.075")
    assert three_of_three == Decimal("0.1")


def test_an_unpriceable_name_is_not_treated_as_cash(pr015):
    """`run_pr014.book_return`'s rule, and it is the opposite of the one above: an EMPTY slot did
    not move because there was nothing in it, while a name whose bar cannot be read moved by an
    amount nobody knows. Carrying it at zero is a claim."""
    start, end = date(2015, 1, 1), date(2015, 1, 2)
    by_name = {n: series(n, ["100", "110"]) for n in ("A", "B")}
    by_name["GHOST"] = series("GHOST", ["100", "110"])
    idx = {"A": {start: 0, end: 1}, "B": {start: 0, end: 1}, "GHOST": {}}
    # Two priceable names up 10% in a 3-slot book where the third holds an unreadable name: the
    # unreadable slot leaves the denominator, so this is 10%, not 6.7%.
    assert pr015.capped_return(["A", "B", "GHOST"], by_name, idx, start, end, 3) == Decimal("0.1")


def test_a_book_of_only_unpriceable_names_returns_None(pr015):
    start, end = date(2015, 1, 1), date(2015, 1, 2)
    by_name = {"GHOST": series("GHOST", ["100", "110"])}
    assert pr015.capped_return(["GHOST"], by_name, {"GHOST": {}}, start, end, 1) is None


# --- the power floor (§8) ------------------------------------------------------------------------

def test_an_interval_wider_than_the_floor_is_underpowered(pr015):
    assert pr015.underpowered({"net_low": -0.30, "net_high": 0.30}) is True
    assert pr015.underpowered({"net_low": -0.20, "net_high": 0.20}) is False
    assert pr015.underpowered({"rebalances": 0}) is True


def test_a_grid_where_nothing_was_measurable_is_NOT_a_rejection(pr015):
    """The most expensive thing a null can do wrongly is close a question.

    `PR-012` refused a verdict on a four-position book for want of sample. A grid of five arms whose
    intervals are all ±40 points has refuted nothing - and `reject` would go into the record as if
    it had.
    """
    fog = cell(0.02, -0.40, 0.44)
    outcome = pr015.decide([arm("A", fog, fog, fog), arm("B", fog, fog, fog)])
    assert outcome["verdict"] == "inconclusive"
    assert "power floor" in str(outcome["why"])


def test_a_null_measured_inside_the_floor_IS_a_rejection(pr015):
    """The other half. A tight interval around zero is a real refutation and must be recorded as
    one, or the floor becomes a way for any result to avoid being a finding."""
    tight = cell(0.01, -0.08, 0.10)
    outcome = pr015.decide([arm("A", tight, tight, tight)])
    assert outcome["verdict"] == "reject"


def test_a_qualifying_but_underpowered_arm_does_not_reach_the_holdouts(pr015):
    """An interval can exclude zero and still be far too wide to act on: [+1%, +60%] excludes zero
    and says almost nothing. The floor is checked on the SELECTED arm before the holdouts."""
    huge = cell(0.30, 0.01, 0.60)
    passes = cell(0.12, 0.04, 0.20)
    outcome = pr015.decide([arm("A", huge, passes, passes)])
    assert outcome["verdict"] == "inconclusive"
    assert "power floor" in str(outcome["why"])


def test_the_cost_is_annualised_by_the_REBALANCE_STEP_not_the_holding_period(pr015):
    """The mutant that survived the first pass, and it was invisible for the worst reason.

    The book rebalances every 5 sessions and holds each position 20. Annualising by 20 divides the
    cost by four - and does it to EVERY arm equally, so no comparison in the table looks wrong and
    the only symptom is that the whole study is 4.7 points a year too cheap.

    The anchor: a four-name book that re-picks nothing replaces one slot of four every rebalance -
    25% - and pays 6.30% a year at DR-005's 25bp, which is exactly what a 20-session hold with no
    netting costs.
    """
    assert pr015.STEP == pr015.HORIZON // pr015.MAX_CONCURRENT == 5
    no_netting = pr015.book_annual_cost(Decimal(1) / Decimal(pr015.MAX_CONCURRENT))
    assert no_netting == Decimal("0.063")
    # And netting is worth exactly what it nets: half the turnover, half the cost.
    assert pr015.book_annual_cost(Decimal("0.125")) == no_netting / 2


def test_the_pool_reading_subtracts_the_style_gap_and_nothing_else(pr015, capsys):
    """`rs.benchmark` is SPY and its status is `assumed`, not ratified.

    `benchmark-fit-2026-09-06` measured this universe as an equal-weighted mid-cap book whose 3.02%
    annual "loss" to SPY is the mega-cap concentration of 2016-2026 - a different asset, not a worse
    strategy. So every arm carries a style drag its signal did not cause, and a book beating its own
    pool by two points can still print negative against SPY. This reading separates them, and it
    must be a SUBTRACTION of two recorded numbers rather than anything re-estimated.
    """
    result = {"rows": [{
        "arm": "REVERSAL_21",
        "primary": {"net_annual": -0.01, "control_universe_annual": -0.03},
        "holdout_time": {"net_annual": 0.02, "control_universe_annual": -0.03},
        "holdout_names": {"rebalances": 0},
    }]}
    assert pr015.report(result) == 0
    printed = capsys.readouterr().out
    # Asserted on the WHOLE line, not on the substring "+2.00%": that string also appears in the
    # holdout row's `net vs SPY` column, and a first version of this test passed a mutant that
    # ADDED the two numbers because of exactly that collision.
    primary = next(line for line in printed.splitlines() if "primary" in line)
    assert primary.split() == ["REVERSAL_21", "primary", "-1.00%", "-3.00%", "+2.00%"]
    # A window with no cell is skipped rather than printed as a zero.
    assert "holdout_names" not in printed
