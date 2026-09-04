"""The symbol directory store.

The tests that matter are about the store's one deliberate difference from `BarStore`: a directory
pull is a complete snapshot, not a set of independent facts. Reading "everything known by K" would
union every symbol ever seen and make a delisting invisible — which is precisely the bias this
project cannot afford to add to the one it already cannot escape.
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.reference_data.universe import DirectoryEntry

# The cases below import `fetch_directory`, which lives in `tools/`. This module used to rely on
# another test module having put that directory on the path first, so the file passed in a full
# alphabetical run and failed half its cases when run alone - the shape `test_gates.py` and
# `test_vendor_yahoo.py` already avoid by inserting their own path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))


def test_collection_is_disabled_without_the_local_file(tmp_path: Path) -> None:
    from fetch_directory import collection_enabled

    assert collection_enabled(tmp_path) is False


def test_collection_is_disabled_when_the_flag_is_false(tmp_path: Path) -> None:
    from fetch_directory import collection_enabled

    (tmp_path / ".swingdesk-local.json").write_text(
        '{"directory_pull_enabled": false}', encoding="utf-8"
    )
    assert collection_enabled(tmp_path) is False


def test_collection_is_enabled_only_by_an_explicit_true(tmp_path: Path) -> None:
    from fetch_directory import collection_enabled

    (tmp_path / ".swingdesk-local.json").write_text(
        '{"directory_pull_enabled": true}', encoding="utf-8"
    )
    assert collection_enabled(tmp_path) is True


def test_malformed_json_refuses_rather_than_defaulting(tmp_path: Path) -> None:
    """Unset is not default (AGENTS.md 3). A broken switch refuses."""
    from fetch_directory import collection_enabled

    (tmp_path / ".swingdesk-local.json").write_text("{not json", encoding="utf-8")
    assert collection_enabled(tmp_path) is False


def test_a_non_boolean_value_refuses(tmp_path: Path) -> None:
    from fetch_directory import collection_enabled

    (tmp_path / ".swingdesk-local.json").write_text(
        '{"directory_pull_enabled": "yes"}', encoding="utf-8"
    )
    assert collection_enabled(tmp_path) is False


def test_the_committed_example_has_automation_off(tmp_path: Path) -> None:
    """The example is committed; the real file is ignored. It must never enable anything."""
    import json
    from pathlib import Path as P

    example = P(__file__).resolve().parents[1] / ".swingdesk-local.example.json"
    assert json.loads(example.read_text(encoding="utf-8"))["directory_pull_enabled"] is False


def test_scheduled_mode_reports_a_disabled_config_without_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    import fetch_directory

    monkeypatch.setattr(fetch_directory, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["fetch_directory", "--scheduled"])
    monkeypatch.setattr(fetch_directory, "_download", lambda _url: pytest.fail("downloaded"))

    assert fetch_directory.main() == 0
    assert capsys.readouterr().out == (
        "directory pull disabled - no .swingdesk-local.json with directory_pull_enabled: true\n"
    )


def test_scheduled_mode_reports_a_closed_nyse_without_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    import fetch_directory

    (tmp_path / ".swingdesk-local.json").write_text(
        '{"directory_pull_enabled": true}', encoding="utf-8"
    )
    monkeypatch.setattr(fetch_directory, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["fetch_directory", "--scheduled"])
    monkeypatch.setattr(fetch_directory.cal, "is_open", lambda _exchange, _date: False)
    monkeypatch.setattr(fetch_directory, "_download", lambda _url: pytest.fail("downloaded"))

    assert fetch_directory.main() == 0
    assert capsys.readouterr().out == "not an NYSE session - nothing to collect\n"


def test_scheduled_mode_refuses_an_unreadable_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    import fetch_directory

    (tmp_path / ".swingdesk-local.json").write_text(
        '{"directory_pull_enabled": true}', encoding="utf-8"
    )
    monkeypatch.setattr(fetch_directory, "REPO", tmp_path)
    monkeypatch.setattr(sys, "argv", ["fetch_directory", "--scheduled"])
    monkeypatch.setattr(
        fetch_directory.Path,
        "read_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("not readable")),
    )
    monkeypatch.setattr(fetch_directory, "_download", lambda _url: pytest.fail("downloaded"))

    assert fetch_directory.main() == 0
    assert capsys.readouterr().out == (
        "directory pull disabled - no .swingdesk-local.json with directory_pull_enabled: true\n"
    )


def test_a_refusal_writes_its_audit_row_under_the_repo_and_nowhere_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The store the collector opens is a property of `REPO`, never of the working directory.

    Every policy refusal leaves through `_finish`, which writes an audit row - so a store resolved
    against the process's working directory is a store the three cases above wrote into. They patch
    `REPO`, pass no `--data`, and the default was `Path("data")`: run from the repository root, that
    is the operator's own append-only audit table, and it holds their rows.
    """
    import fetch_directory

    repo = tmp_path / "repo"
    elsewhere = tmp_path / "elsewhere"
    repo.mkdir()
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(fetch_directory, "REPO", repo)
    monkeypatch.setattr(sys, "argv", ["fetch_directory", "--scheduled"])
    monkeypatch.setattr(fetch_directory, "_download", lambda _url: pytest.fail("downloaded"))

    assert fetch_directory.main() == 0

    assert not (elsewhere / "data").exists()
    with DirectoryStore(repo / "data" / "directory.duckdb") as store:
        rows = store.audit()
    assert [(row[2], row[8]) for row in rows] == [("SCHEDULED", "DISABLED")]


class _DownloadResponse:
    def __init__(self, headers: dict[str, str], body: bytes) -> None:
        self.headers = headers
        self.body = body
        self.read_limit: int | None = None

    def __enter__(self) -> _DownloadResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        self.read_limit = limit
        return self.body


def test_download_refuses_an_excessive_declared_size(monkeypatch: pytest.MonkeyPatch) -> None:
    import fetch_directory

    response = _DownloadResponse(
        {"Content-Length": str(fetch_directory.MAX_RESPONSE_BYTES + 1)}, b""
    )
    monkeypatch.setattr(fetch_directory.urllib.request, "urlopen", lambda *_args, **_kwargs: response)

    with pytest.raises(ValueError, match=r"declared .* exceeds the cap"):
        fetch_directory._download("https://example.test/directory")
    assert response.read_limit is None


def test_download_refuses_a_body_over_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    import fetch_directory

    response = _DownloadResponse({}, b"x" * (fetch_directory.MAX_RESPONSE_BYTES + 1))
    monkeypatch.setattr(fetch_directory.urllib.request, "urlopen", lambda *_args, **_kwargs: response)

    with pytest.raises(ValueError, match=r"body exceeds the .* byte cap"):
        fetch_directory._download("https://example.test/directory")
    assert response.read_limit == fetch_directory.MAX_RESPONSE_BYTES + 1


# ---------------------------------------------------------- session-date corroboration

def test_trailer_time_parses_the_vendor_format() -> None:
    import fetch_directory

    result = fetch_directory._trailer_time("File Creation Time: 0813202621:31|||||||")
    assert result == datetime(2026, 8, 13, 21, 31, tzinfo=fetch_directory._TRAILER_ZONE)


def test_trailer_time_is_none_without_a_trailer() -> None:
    import fetch_directory

    assert fetch_directory._trailer_time("Symbol|Name\nAAPL|Apple\n") is None


def test_trailer_time_is_none_for_an_impossible_date() -> None:
    """13 as a month, 40 as a day - the regex matches digits, not calendar validity."""
    import fetch_directory

    assert fetch_directory._trailer_time("File Creation Time: 1340202621:31|||||||") is None


def test_corroborated_session_date_accepts_agreement_within_tolerance() -> None:
    """The confirmed case: trailer as ET, Last-Modified 44 seconds later - the real observation
    that established the trailer's timezone (2026-08-13)."""
    import fetch_directory

    result = fetch_directory._corroborated_session_date(
        "File Creation Time: 0813202621:31|||||||",
        "Fri, 14 Aug 2026 01:31:44 GMT",
    )
    assert result == date(2026, 8, 13)


def test_corroborated_session_date_refuses_the_utc_interpretation() -> None:
    """If the trailer were (wrongly) read as UTC instead of America/New_York, Last-Modified would
    be 4 hours off - well outside tolerance. This is the mechanism that would have caught the
    majority guess in this project's own design review, had it shipped."""
    import fetch_directory

    result = fetch_directory._corroborated_session_date(
        "File Creation Time: 0813202621:31|||||||",
        "Thu, 13 Aug 2026 21:31:44 GMT",  # what Last-Modified would read if trailer were UTC
    )
    assert result is None


def test_corroborated_session_date_refuses_a_missing_last_modified_header() -> None:
    import fetch_directory

    assert fetch_directory._corroborated_session_date(
        "File Creation Time: 0813202621:31|||||||", None
    ) is None


def test_corroborated_session_date_refuses_a_missing_trailer() -> None:
    import fetch_directory

    assert fetch_directory._corroborated_session_date(
        "Symbol|Name\nAAPL|Apple\n", "Fri, 14 Aug 2026 01:31:44 GMT"
    ) is None


def test_corroborated_session_date_refuses_an_unparseable_header() -> None:
    import fetch_directory

    assert fetch_directory._corroborated_session_date(
        "File Creation Time: 0813202621:31|||||||", "not a date"
    ) is None


MONDAY = datetime(2026, 1, 12, 21, 0, tzinfo=UTC)
FRIDAY = MONDAY + timedelta(days=4)


def _entry(symbol: str, venue: str = "Q", **kwargs) -> DirectoryEntry:
    return DirectoryEntry(
        symbol=symbol, name=f"{symbol} Inc", venue=venue,
        is_etf=kwargs.get("is_etf", False),
        is_test_issue=kwargs.get("is_test_issue", False),
    )


@pytest.fixture
def store(tmp_path):
    with DirectoryStore(tmp_path / "directory.duckdb") as opened:
        yield opened


# ------------------------------------------------------------------ snapshot semantics

def test_a_read_before_any_pull_is_empty_not_an_error(store) -> None:
    """"We did not know" is a real answer, and the caller must not read it as "nothing was listed"."""
    assert store.as_of(MONDAY) == ()
    assert store.latest_pull(MONDAY) is None


def test_as_of_reads_one_pull_not_the_union_of_all_of_them(store) -> None:
    """The load-bearing test.

    If `as_of` unioned every row known by K, a symbol that stopped being listed would stay in the
    universe forever and the store would manufacture survivorship bias rather than measure it.
    """
    store.record([_entry("TEST1"), _entry("TEST2")], MONDAY, "fixture")
    store.record([_entry("TEST1")], FRIDAY, "fixture")

    assert [e.symbol for e in store.as_of(FRIDAY)] == ["TEST1"]
    assert [e.symbol for e in store.as_of(MONDAY)] == ["TEST1", "TEST2"]


def test_a_read_between_pulls_gets_the_earlier_one(store) -> None:
    """Point-in-time: a run pinned to Wednesday must not see Friday's directory."""
    store.record([_entry("TEST1"), _entry("TEST2")], MONDAY, "fixture")
    store.record([_entry("TEST1")], FRIDAY, "fixture")

    wednesday = MONDAY + timedelta(days=2)
    assert [e.symbol for e in store.as_of(wednesday)] == ["TEST1", "TEST2"]


def test_recording_the_same_instant_twice_replaces_rather_than_merges(store) -> None:
    """Re-running a fetch must not half-merge two downloads into a snapshot that never existed."""
    store.record([_entry("TEST1"), _entry("TEST2")], MONDAY, "fixture")
    store.record([_entry("TEST3")], MONDAY, "fixture")

    assert [e.symbol for e in store.as_of(MONDAY)] == ["TEST3"]
    assert store.pulls() == ((MONDAY, "fixture", 1, None),)


SESSION = date(2026, 8, 13)


def test_source_session_date_is_stored_when_given(store) -> None:
    stored = store.record([_entry("TEST1")], MONDAY, "fixture", SESSION)
    assert stored == SESSION
    assert store.pulls() == ((MONDAY, "fixture", 1, SESSION),)


def test_a_strictly_later_session_date_is_accepted(store) -> None:
    store.record([_entry("TEST1")], MONDAY, "fixture", SESSION)
    later = store.record([_entry("TEST1")], FRIDAY, "fixture", SESSION + timedelta(days=1))
    assert later == SESSION + timedelta(days=1)


def test_a_non_increasing_session_date_is_rejected_but_the_pull_is_still_recorded(store) -> None:
    """The stale-file symptom: a repeat or earlier date most likely means the vendor's file did not
    regenerate, not a legitimate second observation of an earlier session. Fails closed on the
    CLAIM - the rows are still there, only the date is dropped."""
    store.record([_entry("TEST1")], MONDAY, "fixture", SESSION)

    same_date = store.record([_entry("TEST1")], FRIDAY, "fixture", SESSION)
    assert same_date is None
    assert [e.symbol for e in store.as_of(FRIDAY)] == ["TEST1"]  # rows recorded regardless

    earlier_date = store.record(
        [_entry("TEST1")], FRIDAY + timedelta(days=1), "fixture", SESSION - timedelta(days=1)
    )
    assert earlier_date is None


def test_a_none_session_date_is_stored_as_none(store) -> None:
    """The ordinary unattributed case - no claim was ever made, so nothing to reject."""
    stored = store.record([_entry("TEST1")], MONDAY, "fixture")
    assert stored is None
    assert store.pulls() == ((MONDAY, "fixture", 1, None),)


def test_an_empty_pull_is_refused(store) -> None:
    """An empty snapshot is indistinguishable from every symbol delisting at once.

    A failed download that returned nothing would otherwise be recorded as a market event.
    """
    with pytest.raises(ValueError, match="empty directory pull"):
        store.record([], MONDAY, "fixture")


# ------------------------------------------------------------------ eligibility

def test_eligible_only_drops_test_issues_and_unknown_venues(store) -> None:
    store.record(
        [
            _entry("TEST1"),
            _entry("TEST2", is_test_issue=True),
            _entry("TEST3", venue="ZZ"),
            _entry("TEST4", is_etf=True),
        ],
        MONDAY, "fixture",
    )
    assert [e.symbol for e in store.as_of(MONDAY, eligible_only=True)] == ["TEST1", "TEST4"]


def test_etfs_stay_in_scope(store) -> None:
    """CHARTER: equities *and* ETFs. 58 of 115 sampled instruments were ETFs (DR-003)."""
    store.record([_entry("TEST1", is_etf=True)], MONDAY, "fixture")
    assert len(store.as_of(MONDAY, eligible_only=True)) == 1


# ------------------------------------------------------------------ departures

def test_departures_report_what_stopped_appearing(store) -> None:
    """The only free survivorship evidence this project can ever collect."""
    store.record([_entry("TEST1"), _entry("TEST2"), _entry("TEST3")], MONDAY, "fixture")
    store.record([_entry("TEST1"), _entry("TEST4")], FRIDAY, "fixture")

    assert store.departures(MONDAY, FRIDAY) == ("TEST2", "TEST3")


def test_departures_are_directional(store) -> None:
    """Arrivals are not departures. Reversing the arguments must not report new symbols as gone."""
    store.record([_entry("TEST1")], MONDAY, "fixture")
    store.record([_entry("TEST1"), _entry("TEST2")], FRIDAY, "fixture")

    assert store.departures(MONDAY, FRIDAY) == ()
    assert store.departures(FRIDAY, MONDAY) == ("TEST2",)


# ---------------------------------------------- DR-008's audit, guard and forced pull (2026-08-25)
#
# All three were ratified 2026-08-10 and none was built. Gate 20 exists BECAUSE of that omission and
# passed the whole time, because it checks that a record names an implementer, not that the
# implementer implements the record - `AGENTS.md` §17, verify at the right granularity. Gate 31
# found it from the other side: the record's emergency command names flags argparse never had.


def test_an_invocation_that_makes_no_request_still_records_an_audit_row(store) -> None:
    """A refusal that recorded nothing left "declined" and "never ran" indistinguishable."""
    started = datetime(2026, 8, 25, 18, 30, tzinfo=UTC)
    store.record_audit(
        started_at=started, finished_at=started, mode="SCHEDULED", reason=None,
        enabled=False, attempts=0, requests=0, received_bytes=0,
        result="DISABLED", snapshot=None,
    )
    rows = store.audit()
    assert len(rows) == 1
    assert rows[0][2] == "SCHEDULED"
    assert rows[0][8] == "DISABLED"
    assert rows[0][6] == 0, "a declined invocation must record zero requests, not no row"


def test_at_most_one_audit_row_per_invocation(store) -> None:
    """`DR-008` says "at most one", and the primary key is what makes that true rather than hoped."""
    started = datetime(2026, 8, 25, 18, 30, tzinfo=UTC)
    for result in ("DISABLED", "RECORDED"):
        store.record_audit(
            started_at=started, finished_at=started, mode="SCHEDULED", reason=None,
            enabled=True, attempts=0, requests=0, received_bytes=0,
            result=result, snapshot=None,
        )
    assert len(store.audit()) == 1
    assert store.audit()[0][8] == "RECORDED"


def test_pull_for_session_is_what_makes_the_guard_decidable_before_the_network(store) -> None:
    """The vendor's session date arrives WITH the file, so the guard cannot wait for it.

    Until this existed the collector downloaded both files and then let `record` strip the date -
    two requests spent to learn something the store already knew.
    """
    store.record([_entry("AAA")], MONDAY, "src", date(2026, 8, 24))
    assert store.pull_for_session(date(2026, 8, 24)) == MONDAY
    assert store.pull_for_session(date(2026, 8, 25)) is None


def test_a_repeated_forced_reason_is_visible_to_the_caller(store) -> None:
    """`DR-008` requires a NEW reason per forced pull; a reason that repeats is one nobody reads."""
    assert store.last_forced_reason() is None
    first = datetime(2026, 8, 25, 18, 30, tzinfo=UTC)
    store.record_audit(
        started_at=first, finished_at=first, mode="FORCED", reason="truncated first response",
        enabled=True, attempts=1, requests=2, received_bytes=10,
        result="RECORDED", snapshot=first,
    )
    assert store.last_forced_reason() == "truncated first response"

    # A later SCHEDULED row must not become the answer - the requirement is about forced pulls only.
    later = first + timedelta(hours=1)
    store.record_audit(
        started_at=later, finished_at=later, mode="SCHEDULED", reason=None,
        enabled=True, attempts=0, requests=0, received_bytes=0,
        result="ALREADY_RECORDED", snapshot=None,
    )
    assert store.last_forced_reason() == "truncated first response"


def test_the_monotonicity_check_still_refuses_a_repeat_session_by_default(store) -> None:
    """The positive control for the exception below: without `supersedes`, nothing changes."""
    store.record([_entry("AAA")], MONDAY, "src", date(2026, 8, 24))
    again = MONDAY + timedelta(hours=1)
    assert store.record([_entry("AAA")], again, "src", date(2026, 8, 24)) is None


def test_a_forced_replacement_keeps_its_session_date(store) -> None:
    """A correction and a second observation are different claims, and only one may repeat a date.

    Without this the replacement stored a NULL date and `pull_for_session` went on answering with
    the snapshot the operator had just corrected - the forced pull would have been a no-op dressed
    as a repair.
    """
    store.record([_entry("AAA")], MONDAY, "src", date(2026, 8, 24))
    later = MONDAY + timedelta(hours=1)
    stored = store.record([_entry("AAA"), _entry("BBB")], later, "src", date(2026, 8, 24),
                          supersedes=MONDAY)
    assert stored == date(2026, 8, 24)
    assert store.pull_for_session(date(2026, 8, 24)) == later


def test_the_superseded_pull_remains_stored_and_the_note_is_appended(store) -> None:
    """`DR-008`: "The previous snapshot remains stored but is no longer canonical."

    Append, never overwrite - `AUDIT_AND_IMMUTABILITY.md` §2. A correction that erased its
    predecessor would present the corrected state as though it had always been so.
    """
    store.record([_entry("AAA")], MONDAY, "src", date(2026, 8, 24))
    later = MONDAY + timedelta(hours=1)
    store.record([_entry("AAA"), _entry("BBB")], later, "src", date(2026, 8, 24), supersedes=MONDAY)
    store.record_supersession(
        recorded_at=later, superseded=MONDAY, replacement=later, reason="truncated first response",
    )

    notes = store.supersessions()
    assert len(notes) == 1
    assert notes[0][1] == MONDAY and notes[0][2] == later
    assert notes[0][3] == "truncated first response"

    # The superseded snapshot is still readable at its own knowledge time - that is what makes the
    # supersession evidence rather than a rewrite.
    assert {e.symbol for e in store.as_of(MONDAY)} == {"AAA"}
    assert {e.symbol for e in store.as_of(later)} == {"AAA", "BBB"}


# ------------------------------------------- DR-008's gap record and its severities (2026-08-25)
#
# "Subsequent missing NYSE sessions are recorded as gaps, never backdated observations. One
# consecutive miss is a log WARNING; two or more are ERROR. Research claiming continuous
# survivorship coverage must query and disclose those gaps."
#
# A gaps() built on knowledge_time was written and withdrawn on 2026-08-12 for misattributing
# evening pulls that cross UTC midnight. source_session_date is what makes a correct one possible.


def test_only_an_ATTRIBUTED_pull_counts_as_coverage(store) -> None:
    """An unattributed pull is a real snapshot and an unknown session. It cannot fill a gap.

    DR-008 c3 forbids backfilling a date a pull never stored, so counting one here would manufacture
    exactly the coverage the record refuses to claim.
    """
    store.record([_entry("AAA")], MONDAY, "src", None)
    assert store.attributed_sessions() == ()

    later = MONDAY + timedelta(days=1)
    store.record([_entry("AAA")], later, "src", date(2026, 8, 24))
    assert store.attributed_sessions() == (date(2026, 8, 24),)


def test_gaps_are_the_expected_sessions_no_pull_is_attributed_to(store) -> None:
    store.record([_entry("AAA")], MONDAY, "src", date(2026, 8, 24))
    expected = [date(2026, 8, 24), date(2026, 8, 25), date(2026, 8, 26)]
    assert store.gaps(expected) == (date(2026, 8, 25), date(2026, 8, 26))


def test_gaps_asks_the_caller_for_the_sessions_and_never_a_calendar(store) -> None:
    """The store must not learn about exchanges - the layer contract, and the reason the withdrawn
    version was wrong. Passing an empty window yields no gaps rather than inventing a calendar."""
    store.record([_entry("AAA")], MONDAY, "src", date(2026, 8, 24))
    assert store.gaps([]) == ()


def test_one_isolated_miss_is_a_WARNING_and_two_in_a_ROW_are_an_ERROR() -> None:
    """`DR-008` says CONSECUTIVE, and consecutive is about a run rather than a total.

    Eight isolated misses are eight recoverable evenings. Two in a row means whatever stopped the
    collector was still stopping it the next day.
    """
    import fetch_directory

    assert fetch_directory.gap_severity([]) is None
    assert fetch_directory.gap_severity([date(2026, 8, 17)]) == "WARNING"
    assert fetch_directory.gap_severity([date(2026, 8, 17), date(2026, 8, 20)]) == "WARNING"
    assert fetch_directory.gap_severity([date(2026, 8, 17), date(2026, 8, 18)]) == "ERROR"


def test_a_friday_and_the_monday_after_it_are_CONSECUTIVE_sessions() -> None:
    """The subtlety that decides whether this rule is usable at all.

    Counting calendar days would call every weekend a two-day gap and report an ERROR every Monday.
    Counting them as non-adjacent would miss a genuine two-session outage across a weekend, which is
    the most likely shape of one. Sessions, not days.
    """
    import fetch_directory

    friday, monday = date(2026, 8, 21), date(2026, 8, 24)
    assert fetch_directory.gap_severity([friday, monday]) == "ERROR"


def test_a_weekend_is_never_itself_a_gap(store) -> None:
    """Saturday is not a missing session, and a window built from the calendar never offers one."""
    from swingdesk.contracts.reference import Exchange
    from swingdesk.reference_data import calendar as cal

    store.record([_entry("AAA")], MONDAY, "src", date(2026, 8, 21))
    later = MONDAY + timedelta(days=1)
    store.record([_entry("AAA")], later, "src", date(2026, 8, 24))
    window = [s.session_date for s in cal.sessions(Exchange.NYSE, date(2026, 8, 21), date(2026, 8, 24))]
    assert store.gaps(window) == ()


# ------------------------------------------------- DR-008's checksum (2026-08-25)
#
# "Both files must pass ... non-empty parse and checksum creation before either becomes canonical",
# and "only validated parsed fields, source timestamps and checksums are stored with a snapshot".
# Raw bodies are never archived, so the digest is the only trace of what the vendor actually served.


def test_a_checksum_is_stored_with_the_pull_and_read_back(store) -> None:
    store.record([_entry("AAA")], MONDAY, "src", None, checksum="abc123")
    assert store.checksum_at(MONDAY) == "abc123"
    assert store.latest_checksum() == "abc123"


def test_a_pull_predating_the_column_reads_None_rather_than_failing(store) -> None:
    """The column was added to a store that already held eighteen pulls. `None` is the honest
    answer for those, and it must not be confused with a pull whose digest was empty."""
    store.record([_entry("AAA")], MONDAY, "src", None)
    assert store.checksum_at(MONDAY) is None
    assert store.latest_checksum() is None


def test_latest_checksum_skips_the_pulls_that_have_none(store) -> None:
    store.record([_entry("AAA")], MONDAY, "src", None)
    later = MONDAY + timedelta(hours=1)
    store.record([_entry("AAA")], later, "src", None, checksum="deadbeef")
    assert store.latest_checksum() == "deadbeef"


def test_identical_bodies_digest_identically_and_different_ones_do_not() -> None:
    import fetch_directory

    assert fetch_directory.digest("a", "b") == fetch_directory.digest("a", "b")
    assert fetch_directory.digest("a", "b") != fetch_directory.digest("b", "a")


def test_the_digest_cannot_be_fooled_by_moving_bytes_between_the_two_FILES() -> None:
    """One digest covers the PAIR, because a pull is a complete snapshot.

    Concatenating without a length prefix would make ("ab", "c") and ("a", "bc") collide - two
    genuinely different snapshots reported as the same one, which is the exact claim the digest
    exists to make.
    """
    import fetch_directory

    assert fetch_directory.digest("ab", "c") != fetch_directory.digest("a", "bc")


# ------------------------------------------- DR-008's process lock (2026-08-25)
#
# "It does not bypass local disablement, the NYSE calendar, source allowlist, response cap,
# validation, PROCESS LOCK or audit" - said of the forced pull, about a lock that did not exist.


def _lock_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "data"
    directory.mkdir(exist_ok=True)
    return directory


def test_a_second_collector_is_refused_while_the_first_holds_the_lock(tmp_path: Path) -> None:
    import fetch_directory

    now = datetime(2026, 8, 25, 18, 30, tzinfo=UTC)
    directory = _lock_dir(tmp_path)
    with fetch_directory.process_lock(directory, now):
        with pytest.raises(fetch_directory.LockHeld):
            with fetch_directory.process_lock(directory, now):
                pass


def test_the_lock_is_released_on_the_way_out(tmp_path: Path) -> None:
    import fetch_directory

    now = datetime(2026, 8, 25, 18, 30, tzinfo=UTC)
    directory = _lock_dir(tmp_path)
    with fetch_directory.process_lock(directory, now):
        assert (directory / "directory-pull.lock").is_file()
    assert not (directory / "directory-pull.lock").is_file()


def test_the_lock_is_released_even_when_the_body_raises(tmp_path: Path) -> None:
    """A collector that dies mid-pull must not leave the next evening blocked.

    This is the ordinary case of the stale-lock problem, and the `finally` is what keeps it
    ordinary rather than requiring the timeout below to rescue it.
    """
    import fetch_directory

    now = datetime(2026, 8, 25, 18, 30, tzinfo=UTC)
    directory = _lock_dir(tmp_path)
    with pytest.raises(RuntimeError), fetch_directory.process_lock(directory, now):
        raise RuntimeError("the vendor hung up")
    assert not (directory / "directory-pull.lock").is_file()


def test_a_STALE_lock_is_reclaimed_and_says_so(tmp_path: Path) -> None:
    """The design decision, and getting it wrong would be worse than having no lock at all.

    `DR-008` gives the forced pull no way past this lock, so one left by a KILLED process - where
    the `finally` above never ran - would refuse every pull for ever. A missed pull is permanently
    unrecoverable because the vendor publishes current state and not an archive, so a lock that
    never expires would cost the departure record to prevent a duplicate request. Reclaimed, and
    reported: it means a previous run died, which is worth seeing.
    """
    import fetch_directory

    now = datetime(2026, 8, 25, 18, 30, tzinfo=UTC)
    directory = _lock_dir(tmp_path)
    abandoned = now - timedelta(seconds=fetch_directory.LOCK_STALE_AFTER + 5)
    (directory / "directory-pull.lock").write_text(abandoned.isoformat(), encoding="utf-8")

    with fetch_directory.process_lock(directory, now) as note:
        assert "stale" in note


def test_a_lock_just_inside_the_timeout_is_still_held(tmp_path: Path) -> None:
    """The positive control for the reclamation above: the timeout is a boundary, not a bypass."""
    import fetch_directory

    now = datetime(2026, 8, 25, 18, 30, tzinfo=UTC)
    directory = _lock_dir(tmp_path)
    recent = now - timedelta(seconds=fetch_directory.LOCK_STALE_AFTER - 5)
    (directory / "directory-pull.lock").write_text(recent.isoformat(), encoding="utf-8")

    with pytest.raises(fetch_directory.LockHeld):
        with fetch_directory.process_lock(directory, now):
            pass


def test_an_UNREADABLE_lock_is_reclaimed_rather_than_treated_as_held_for_ever(tmp_path: Path) -> None:
    """A lock that cannot be dated cannot be trusted to be live, and "cannot tell" must not mean
    "blocked permanently" for a resource whose loss is unrecoverable."""
    import fetch_directory

    now = datetime(2026, 8, 25, 18, 30, tzinfo=UTC)
    directory = _lock_dir(tmp_path)
    (directory / "directory-pull.lock").write_text("not a timestamp", encoding="utf-8")

    with fetch_directory.process_lock(directory, now) as note:
        assert "unreadable" in note
