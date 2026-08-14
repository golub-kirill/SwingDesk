"""`--symbols-from`: resolving a study's fixed sample by identity, not by today's eligibility.

PR-007 needs the SAME 68 instruments PR-005 admitted, not the current DR-003 answer - eligibility
moves, and re-filtering by it would silently change the sample being reproduced. These tests cover
only the resolution logic; the fetch itself is a network call and stays untested here (CI_POLICY 4).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.reference_data.universe import DirectoryEntry

AS_OF = datetime(2026, 8, 13, tzinfo=UTC)


def _entry(symbol: str, venue: str = "Q") -> DirectoryEntry:
    return DirectoryEntry(symbol=symbol, name=symbol, venue=venue, is_etf=False, is_test_issue=False)


@pytest.fixture
def directory(tmp_path: Path) -> DirectoryStore:
    with DirectoryStore(tmp_path / "d.duckdb") as store:
        store.record([_entry("TEST.1"), _entry("TEST.2")], AS_OF, "fixture")
        yield store


def _sample_file(tmp_path: Path, instruments: list[str]) -> Path:
    path = tmp_path / "sample.json"
    path.write_text(json.dumps({"instruments": instruments}), encoding="utf-8")
    return path


def test_resolves_symbols_present_in_the_directory(tmp_path: Path, directory: DirectoryStore) -> None:
    import refresh_universe

    sample = _sample_file(tmp_path, ["TEST.1", "TEST.2"])
    queue = refresh_universe._fixed_queue(sample, directory, AS_OF)
    assert {i.id for i in queue} == {"TEST.1", "TEST.2"}


def test_reports_a_symbol_missing_from_the_directory_without_dropping_it_silently(
    tmp_path: Path, directory: DirectoryStore, capsys: pytest.CaptureFixture[str]
) -> None:
    """A symbol PR-005 admitted but that no longer resolves is a finding, not noise (PR-007 §0)."""
    import refresh_universe

    sample = _sample_file(tmp_path, ["TEST.1", "DELISTED"])
    queue = refresh_universe._fixed_queue(sample, directory, AS_OF)

    assert {i.id for i in queue} == {"TEST.1"}
    assert "DELISTED" in capsys.readouterr().out


def test_an_empty_directory_resolves_nothing(tmp_path: Path) -> None:
    import refresh_universe

    with DirectoryStore(tmp_path / "empty.duckdb") as empty:
        sample = _sample_file(tmp_path, ["TEST.1"])
        queue = refresh_universe._fixed_queue(sample, empty, AS_OF)
    assert queue == []


def test_fixed_queue_ignores_the_eligibility_rule(tmp_path: Path) -> None:
    """The point of this mode: a test issue is INELIGIBLE under DR-003 and still resolves here,
    because the study already decided its own sample - this tool must not re-filter it."""
    import refresh_universe

    with DirectoryStore(tmp_path / "d.duckdb") as store:
        store.record(
            [DirectoryEntry(symbol="TEST.3", name="TEST.3", venue="Q",
                             is_etf=False, is_test_issue=True)],
            AS_OF, "fixture",
        )
        sample = _sample_file(tmp_path, ["TEST.3"])
        queue = refresh_universe._fixed_queue(sample, store, AS_OF)
    assert {i.id for i in queue} == {"TEST.3"}
