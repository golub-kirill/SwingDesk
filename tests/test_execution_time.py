"""The paired execution-time comparison, and the three ways the pairing quietly breaks.

`measure_execution_time.py` answers the one question `DR-040` §4 refused to: does the gross survive
moving the trade off the open? The answer is only worth anything if the comparison stays paired:

* **every column must price the SAME trade.** Entry and exit at the same moment of the day, same
  entry date, same holding period. A column that slipped a session would be measuring drift.
* **a session missing any of the three moments is dropped whole.** A half-day that closes at 13:00
  has no 15:30 bar; taking its 09:30 price and pairing it against a different session's close is
  unpaired on exactly the days the clock matters most.
* **only 09:30, 11:00 and 15:30 are read**, and the opening price is the 09:30 bar's OPEN while the
  closing price is the 15:30 bar's CLOSE. Reading the wrong end of either bar moves the measurement
  by most of a session.

No network. Bars are literal dicts in the venue's own shape.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def timing():
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location(
        "_execution_time", REPO / "tools" / "measure_execution_time.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def bar(stamp: str, open_: float, close: float) -> dict[str, object]:
    """One 30-minute bar, stamped in UTC as the venue stamps them."""
    return {"t": stamp, "o": open_, "h": max(open_, close), "l": min(open_, close), "c": close}


# August is EDT, so 09:30 ET is 13:30Z, 11:00 is 15:00Z and 15:30 is 19:30Z.
AUG_OPEN = "2024-08-14T13:30:00Z"
AUG_ELEVEN = "2024-08-14T15:00:00Z"
AUG_CLOSE = "2024-08-14T19:30:00Z"


def one_session(timing, opens=(100.0, 110.0, 120.0)) -> dict[date, dict[str, Decimal]]:
    found: dict[date, dict[str, Decimal]] = {}
    timing.reduce_into(found, [
        bar(AUG_OPEN, opens[0], opens[0] + 1),
        bar(AUG_ELEVEN, opens[1], opens[1] + 1),
        bar(AUG_CLOSE, opens[2], opens[2] + 5),
    ])
    return found


# --- which price each moment means -------------------------------------------------------------

def test_the_open_is_the_bars_open_and_the_close_is_the_bars_close(timing):
    """The 09:30 bar's OPEN is the opening print; the 15:30 bar's CLOSE is the closing print."""
    found = one_session(timing)
    prices = found[date(2024, 8, 14)]
    assert prices["09:30 open"] == Decimal("100")
    assert prices["11:00"] == Decimal("110")
    assert prices["15:30 close"] == Decimal("125"), "the close is the bar's close, not its open"


def test_extended_hours_bars_are_ignored(timing):
    """04:00 and 19:00 ET are real bars on this tape and are not any of the three moments."""
    found: dict[date, dict[str, Decimal]] = {}
    timing.reduce_into(found, [
        bar("2024-08-14T08:00:00Z", 90.0, 90.0),   # 04:00 ET, pre-market
        bar(AUG_OPEN, 100.0, 101.0),
        bar("2024-08-14T23:00:00Z", 130.0, 130.0),  # 19:00 ET, post-market
    ])
    assert set(found[date(2024, 8, 14)]) == {"09:30 open"}


def test_the_session_clock_follows_daylight_saving(timing):
    """13:30Z is the opening bell in August and 14:30Z is the opening bell in February."""
    winter: dict[date, dict[str, Decimal]] = {}
    timing.reduce_into(winter, [bar("2024-02-14T14:30:00Z", 50.0, 51.0),
                                bar("2024-02-14T13:30:00Z", 40.0, 41.0)])
    assert winter[date(2024, 2, 14)] == {"09:30 open": Decimal("50")}


# --- a session must carry all three --------------------------------------------------------------

def test_a_session_missing_a_moment_is_dropped_whole(timing):
    """A 13:00 half-day close has no 15:30 bar. Half a session cannot be paired against a full one."""
    partial: dict[date, dict[str, Decimal]] = {}
    timing.reduce_into(partial, [bar(AUG_OPEN, 100.0, 101.0), bar(AUG_ELEVEN, 110.0, 111.0)])
    assert timing.complete_sessions(partial) == {}


def test_a_complete_session_survives(timing):
    assert set(timing.complete_sessions(one_session(timing))) == {date(2024, 8, 14)}


# --- the pairing ---------------------------------------------------------------------------------

def _series(timing, n: int, step: float = 1.0) -> dict[date, dict[str, Decimal]]:
    """`n` complete sessions whose three prices differ, so a column swap is visible."""
    from datetime import timedelta
    return {
        date(2024, 1, 1) + timedelta(days=i): {
            "09:30 open": Decimal(str(100 + i * step)),
            "11:00": Decimal(str(200 + i * step)),
            "15:30 close": Decimal(str(300 + i * step)),
        }
        for i in range(n)
    }


def test_every_column_prices_the_same_entry_and_exit_dates(timing):
    """The whole design. Each column must use its OWN price at both ends of the SAME window."""
    sessions = _series(timing, 21)
    rows = timing.paired_returns(sessions, hold=20)
    assert len(rows) == 1
    when, row = rows[0]
    assert when == date(2024, 1, 1), "the ENTRY date travels with the row, not the exit date"
    assert row["09:30 open"] == (Decimal(120) - Decimal(100)) / Decimal(100)
    assert row["11:00"] == (Decimal(220) - Decimal(200)) / Decimal(200)
    assert row["15:30 close"] == (Decimal(320) - Decimal(300)) / Decimal(300)


def test_windows_do_not_overlap(timing):
    """Two entries inside one holding period would count the same forward window twice."""
    rows = timing.paired_returns(_series(timing, 61), hold=20)
    assert len(rows) == 3


def test_a_series_shorter_than_the_hold_produces_nothing(timing):
    assert timing.paired_returns(_series(timing, 20), hold=20) == []
    assert timing.paired_returns({}, hold=20) == []


# --- the cost restatement ------------------------------------------------------------------------

def test_net_charges_a_round_trip_not_one_side(timing):
    """26.46 bps per side is 52.92 bps of round trip, and the sign is a deduction."""
    net = timing.net_of_spread(Decimal("0.01"), Decimal("26.46"))
    assert net == Decimal("0.01") - Decimal("0.005292")


def test_a_cheaper_moment_deducts_less(timing):
    """If this inverts, the whole finding inverts."""
    assert timing.net_of_spread(Decimal("0.01"), Decimal("4.03")) > \
        timing.net_of_spread(Decimal("0.01"), Decimal("26.46"))


def test_the_charged_spreads_are_the_measured_ones(timing):
    """Pinned from `quoted-spread-2026-09-06.json`; a drifted constant changes every net figure."""
    assert timing.SPREAD_BPS_PER_SIDE["09:30 open"] == Decimal("26.46")
    assert timing.SPREAD_BPS_PER_SIDE["11:00"] == Decimal("5.75")
    assert timing.SPREAD_BPS_PER_SIDE["15:30 close"] == Decimal("4.03")


# --- the interval must not pretend the entries are independent -----------------------------------

def test_clustering_collapses_one_date_to_one_observation(timing):
    """Sixty names entering on the same day are one observation of that day's overnight gap."""
    same_day = [(date(2024, 1, 1), Decimal(n)) for n in (1, 2, 3)]
    assert timing.clustered_by_date(same_day) == [Decimal(2)]


def test_clustering_keeps_distinct_dates_apart(timing):
    mixed = [
        (date(2024, 1, 1), Decimal(1)), (date(2024, 1, 1), Decimal(3)),
        (date(2024, 2, 1), Decimal(10)),
    ]
    assert timing.clustered_by_date(mixed) == [Decimal(2), Decimal(10)]


def test_clustering_widens_the_interval_it_replaces(timing):
    """The whole reason it exists: the naive half-width overstates the precision.

    Two dates, thirty identical observations each. Treated as independent the spread looks
    enormously well determined; clustered, there are two numbers and the interval says so.
    """
    deltas = [(date(2024, 1, 1), Decimal(0))] * 30 + [(date(2024, 2, 1), Decimal(1))] * 30
    _, naive = timing.summarise([v for _, v in deltas])
    _, clustered = timing.summarise(timing.clustered_by_date(deltas))
    assert clustered > naive


def test_clustering_is_ordered_by_date(timing):
    out_of_order = [(date(2024, 3, 1), Decimal(3)), (date(2024, 1, 1), Decimal(1))]
    assert timing.clustered_by_date(out_of_order) == [Decimal(1), Decimal(3)]


def test_the_cluster_robust_estimator_keeps_the_entry_weighted_mean(timing):
    """The point estimate is what a book earns; only the UNCERTAINTY is corrected.

    Equal-weighting dates would answer +2.0 here - one date says 1, the other says 3 - while the
    mean an equally-sized book actually earns is +1.5, because three of the four entries were on
    the first date.
    """
    deltas = [
        (date(2024, 1, 1), Decimal(1)), (date(2024, 1, 1), Decimal(1)),
        (date(2024, 1, 1), Decimal(1)), (date(2024, 2, 1), Decimal(3)),
    ]
    mean, _, clusters = timing.cluster_robust(deltas)
    assert mean == Decimal("1.5")
    assert clusters == 2
    assert timing.clustered_by_date(deltas) == [Decimal(1), Decimal(3)]


def test_one_entry_per_date_reproduces_the_independent_interval(timing):
    """With no clustering to do, the sandwich must collapse to the ordinary answer.

    A correction that changed an uncorrelated sample would be a bug, not a correction.
    """
    from datetime import timedelta
    values = [Decimal(v) for v in (1, 2, 3, 4, 5, 6, 7, 8)]
    deltas = [(date(2024, 1, 1) + timedelta(days=i), v) for i, v in enumerate(values)]
    mean, half, clusters = timing.cluster_robust(deltas)
    plain_mean, plain_half = timing.summarise(values)
    assert clusters == len(values)
    assert mean == plain_mean
    # The sandwich divides by N where the sample variance divides by N-1, so they agree to that
    # factor and not exactly. Asserting equality would be asserting the wrong formula.
    assert float(half) == pytest.approx(float(plain_half) * (7 / 8) ** 0.5, rel=1e-9)


def test_perfectly_correlated_entries_claim_no_precision(timing):
    """Every entry on one date is one observation repeated, and its interval must say so."""
    deltas = [(date(2024, 1, 1), Decimal(5))] * 20
    mean, half, clusters = timing.cluster_robust(deltas)
    assert mean == Decimal(5)
    assert clusters == 1
    assert half == 0, "a single cluster carries no independent information"


def test_the_correction_widens_a_clustered_sample(timing):
    """The whole point. Same numbers, same mean, a wider interval once the sharing is admitted."""
    deltas = [(date(2024, 1, 1), Decimal(0))] * 10 + [(date(2024, 2, 1), Decimal(1))] * 10
    _, naive = timing.summarise([v for _, v in deltas])
    _, robust, _ = timing.cluster_robust(deltas)
    assert robust > naive


def test_summarise_reports_a_mean_and_a_half_width(timing):
    mean, half = timing.summarise([Decimal(1), Decimal(2), Decimal(3)])
    assert mean == Decimal(2)
    assert half > 0
    assert timing.summarise([Decimal(5)]) == (Decimal(5), Decimal(0))
    assert timing.summarise([]) == (Decimal(0), Decimal(0))
