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
