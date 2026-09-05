"""Which vintage a study runner reads at, and where that moment comes from.

**Owner ruling 2026-09-05, option (a): read the recorded snapshot back.** `run_pr012.py` and
`run_pr013.py` took `store.latest_knowledge_time()` and then wrote the value they used into the
result as `snapshot` - the one number that would make the study reproducible, recorded and never
read again.

**What paid for it, measured the same day by `tools/measure_study_drift.py`:** since PR-013's
recorded snapshot, 1,220 rows inside its own window had been revised - `APH` at close x0.5 from a
2:1 split re-adjusted through history, `DFNS` at x125 from a reverse split. A re-run read those
names at a fraction and a multiple of what the study read and said nothing, while `HANDOFF.md`
cited such a re-run as evidence that a code change had moved nothing.

**Two stores, two clocks** (`AGENTS.md` section 12), so `--reproduce` pins both or it is not a
reproduction: `snapshot` for the bars and the directory, `run_at` for the classifications.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import run_pr012 as runner

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
SNAPSHOT = "2026-08-24T07:15:39.144611-05:00"
RUN_AT = "2026-08-24T23:29:17.037743+00:00"


@pytest.fixture
def published(tmp_path):
    """A result record shaped like PR-012's and PR-013's, carrying both vintages."""
    path = tmp_path / "PR-013.json"
    path.write_text(json.dumps({"snapshot": SNAPSHOT, "run_at": RUN_AT}), encoding="utf-8")
    return path


def test_a_fresh_run_still_reads_the_stores_latest(tmp_path):
    """The default is unchanged - pinning a NEW study to an old vintage is the opposite mistake."""
    vintage = runner.resolve_vintage(
        as_of_arg=None, reproduce=False, result_path=tmp_path / "absent.json", now=NOW)

    assert vintage.as_of is None          # main() falls back to latest_knowledge_time()
    assert vintage.clock == NOW
    assert "fresh run" in vintage.source


def test_reproduce_reads_the_recorded_snapshot_back(published):
    """The ruling, in one assertion: the bars come from the study's own record."""
    vintage = runner.resolve_vintage(
        as_of_arg=None, reproduce=True, result_path=published, now=NOW)

    assert vintage.as_of == datetime.fromisoformat(SNAPSHOT)


def test_reproduce_pins_the_classification_clock_too(published):
    """Two stores, two clocks. Pinning one and reading the other at `now` is not a reproduction."""
    vintage = runner.resolve_vintage(
        as_of_arg=None, reproduce=True, result_path=published, now=NOW)

    assert vintage.clock == datetime.fromisoformat(RUN_AT)
    assert vintage.clock != NOW


def test_as_of_pins_the_bars_and_SAYS_it_does_not_pin_the_rest(tmp_path):
    """`--as-of` names one moment over two stores, so it must not read as a full reproduction."""
    vintage = runner.resolve_vintage(
        as_of_arg=SNAPSHOT, reproduce=False, result_path=tmp_path / "absent.json", now=NOW)

    assert vintage.as_of == datetime.fromisoformat(SNAPSHOT)
    assert vintage.clock == NOW
    assert "classifications still read at now" in vintage.source


def test_two_vintages_at_once_is_refused(published):
    with pytest.raises(SystemExit) as refusal:
        runner.resolve_vintage(as_of_arg=SNAPSHOT, reproduce=True, result_path=published, now=NOW)

    assert "pass one" in str(refusal.value)


def test_reproducing_a_study_that_was_never_published_is_refused(tmp_path):
    with pytest.raises(SystemExit) as refusal:
        runner.resolve_vintage(
            as_of_arg=None, reproduce=True, result_path=tmp_path / "absent.json", now=NOW)

    assert "does not exist" in str(refusal.value)


@pytest.mark.parametrize("present, missing", [("run_at", "snapshot"), ("snapshot", "run_at")])
def test_a_record_missing_either_vintage_REFUSES_rather_than_falling_back(tmp_path, present, missing):
    """The failure that would be silent: falling back to `now` and calling it a reproduction.

    A study published before these fields existed cannot be reproduced, permanently. Saying so is
    the honest answer; reading today's store and reporting cells is not.
    """
    path = tmp_path / "PR-013.json"
    path.write_text(json.dumps({present: SNAPSHOT if present == "snapshot" else RUN_AT}),
                    encoding="utf-8")

    with pytest.raises(SystemExit) as refusal:
        runner.resolve_vintage(as_of_arg=None, reproduce=True, result_path=path, now=NOW)

    assert missing in str(refusal.value)
    assert "cannot be reproduced" in str(refusal.value)


# ------------- AUD-001: a replay pins the DATA and not the CODE, added 2026-09-05
#
# `PR-012` pinned to its own snapshot did not reproduce its SECTOR arm, and the published
# explanation blamed the classification store. It was wrong. Two commits had changed how a stored
# row is JUDGED, and 23 instruments flipped their usability verdict on the SAME rows at the SAME
# clock - 23 being the entire discrepancy. A replay that prints its numbers without saying the code
# moved invites exactly that misattribution.


def test_a_study_records_the_code_it_was_interpreted_by() -> None:
    """The asymmetry this closes: `RunManifest` has carried `code_hash` since the journal existed
    and a study result carried neither it nor `code_dirty`."""
    version = runner.code_version()

    assert set(version) == {"code_hash", "code_dirty"}
    assert isinstance(version["code_dirty"], bool)
    assert version["code_hash"]


def test_a_replay_says_UNAVAILABLE_when_the_study_recorded_no_code() -> None:
    """Every study published before 2026-09-05 is in this position permanently. Saying so is the
    only honest output - `unavailable` is not `pass`."""
    line = runner.report_code_drift(None, "abc1234")

    assert "UNAVAILABLE" in line
    assert "AUD-001" in line


def test_a_replay_says_MOVED_when_the_code_has_changed() -> None:
    """The line that would have prevented the wrong finding."""
    line = runner.report_code_drift("61f6d6e", "abc1234")

    assert "MOVED" in line
    assert "61f6d6e" in line and "abc1234" in line
    assert "REINTERPRETATION" in line


def test_a_replay_says_nothing_alarming_when_the_code_is_unchanged() -> None:
    """Positive control. Without it the two assertions above pass for a function that always
    shouts, which would be the manufactured alarm `AGENTS.md` section 12 warns about."""
    line = runner.report_code_drift("abc1234", "abc1234")

    assert "unchanged" in line
    assert "MOVED" not in line and "UNAVAILABLE" not in line


def test_reproduce_carries_the_recorded_code_into_the_vintage(tmp_path: Path) -> None:
    """End to end: the field reaches the resolver, not just the payload."""
    path = tmp_path / "PR-012.json"
    path.write_text(
        json.dumps({"snapshot": SNAPSHOT, "run_at": RUN_AT, "code_hash": "61f6d6e"}),
        encoding="utf-8",
    )

    vintage = runner.resolve_vintage(as_of_arg=None, reproduce=True, result_path=path, now=NOW)

    assert vintage.recorded_code == "61f6d6e"


def test_a_result_without_a_code_hash_still_reproduces(tmp_path: Path) -> None:
    """A missing code version must NOT refuse the replay - every published study lacks one, and
    refusing would make them all unreproducible over a field invented after they ran."""
    path = tmp_path / "PR-012.json"
    path.write_text(json.dumps({"snapshot": SNAPSHOT, "run_at": RUN_AT}), encoding="utf-8")

    vintage = runner.resolve_vintage(as_of_arg=None, reproduce=True, result_path=path, now=NOW)

    assert vintage.recorded_code is None
    assert vintage.as_of is not None
