"""Measuring how far the store moved under a reported study since it ran.

**The case that matters most is `test_a_study_read_before_its_bars_existed_is_UNAVAILABLE`**, and
it is here because the first version of this measurement got it wrong in the flattering-looking
direction. It compared a study's vintage against the STORE's earliest `knowledge_time` rather than
against its own instruments' - and `PR-005` ran nine hours after the store's global minimum and
hours before the fetch that first brought its 68 names in. The guard passed, every row of the
sample was then counted as "written since", and the output read as total drift under two published
studies. A number that large is not a finding, it is a broken predicate.

`unavailable` is not `pass` and it is not `fail` (`AGENTS.md` section 10.6 rule 2).
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import measure_study_drift as drift

WINDOW = ("2026-01-01", "2026-12-31")

#: The study read here. Everything before it is what the study saw; after it is what moved.
REFERENCE = "2026-06-01T00:00:00+00:00"


@pytest.fixture
def con():
    """A bar store shaped like the real one, with only the columns this tool reads."""
    connection = duckdb.connect(":memory:")
    connection.execute(
        "create table bars (instrument_id varchar, session_date date, "
        "knowledge_time timestamptz, close decimal(18,6))"
    )
    return connection


def _write(con, rows):
    con.executemany("insert into bars values (?, ?, ?::TIMESTAMPTZ, ?)", rows)


def test_a_study_read_before_its_bars_existed_is_UNAVAILABLE(con):
    """The defect this test exists for: every bar postdates the study's own vintage."""
    _write(con, [("TEST.1", "2026-03-02", "2026-07-01T00:00:00+00:00", 10)])

    result = drift.measure(con, ["TEST.1"], *WINDOW, REFERENCE)

    assert not result.available
    assert "before ANY of its bars were stored" in result.reason
    # And it does NOT report the sample as having drifted, which is what the broken version did.
    assert result.revised == 0 and result.new_sessions == 0


def test_a_revision_is_counted_as_a_revision_not_a_new_session(con):
    """A second version of a session the study already had."""
    _write(con, [
        ("TEST.1", "2026-03-02", "2026-05-01T00:00:00+00:00", 10),
        ("TEST.1", "2026-03-02", "2026-07-01T00:00:00+00:00", 12),
    ])

    result = drift.measure(con, ["TEST.1"], *WINDOW, REFERENCE)

    assert result.available
    assert result.revised == 1
    assert result.new_sessions == 0


def test_a_session_the_study_never_had_is_a_new_session(con):
    """A backfill inside a closed window is a different animal from a revision."""
    _write(con, [
        ("TEST.1", "2026-03-02", "2026-05-01T00:00:00+00:00", 10),
        ("TEST.1", "2026-03-03", "2026-07-01T00:00:00+00:00", 11),
    ])

    result = drift.measure(con, ["TEST.1"], *WINDOW, REFERENCE)

    assert result.revised == 0
    assert result.new_sessions == 1


def test_a_sample_nothing_touched_reports_no_movement(con):
    _write(con, [("TEST.1", "2026-03-02", "2026-05-01T00:00:00+00:00", 10)])

    result = drift.measure(con, ["TEST.1"], *WINDOW, REFERENCE)

    assert result.available
    assert result.revised == 0 and result.new_sessions == 0


def test_a_revision_outside_the_window_is_not_this_study_s_business(con):
    """Ordinary daily accretion past the window end is not drift under the study."""
    _write(con, [
        ("TEST.1", "2026-03-02", "2026-05-01T00:00:00+00:00", 10),
        ("TEST.1", "2027-03-02", "2026-07-01T00:00:00+00:00", 11),
    ])

    result = drift.measure(con, ["TEST.1"], *WINDOW, REFERENCE)

    assert result.revised == 0 and result.new_sessions == 0


def test_another_instrument_s_revision_is_not_counted(con):
    """The study's own names bound the question."""
    _write(con, [
        ("TEST.1", "2026-03-02", "2026-05-01T00:00:00+00:00", 10),
        ("TEST.2", "2026-03-02", "2026-05-01T00:00:00+00:00", 10),
        ("TEST.2", "2026-03-02", "2026-07-01T00:00:00+00:00", 99),
    ])

    result = drift.measure(con, ["TEST.1"], *WINDOW, REFERENCE)

    assert result.revised == 0 and result.new_sessions == 0


@pytest.mark.parametrize(
    "close_moved, lo, hi, expected",
    [
        (0, 1.0, 1.0, "close unchanged"),
        (220, 125.0, 125.0, "close x125"),
        (256, 0.5, 1.0, "close x0.5 to x1"),
    ],
)
def test_the_ratio_names_the_corporate_action(close_moved, lo, hi, expected):
    """A 2:1 split reads x0.5 and a 1:125 reverse split reads x125.

    An absolute percentage buries a corporate action - `abs(diff)/close` renders a halving as
    "50%", which reads like a data fault rather than a split.
    """
    assert drift.describe(close_moved, lo, hi) == expected
