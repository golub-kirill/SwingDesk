"""`tools/fetch_history.py`: resolved by identity, bars and actions written under one knowledge time.

The vendor is replaced; the stores are real. What could silently be wrong is which instrument a
symbol becomes and whether the two series of one pull share its instant, and both are store facts.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]


def _tool() -> ModuleType:
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location("_fetch_history", REPO / "tools" / "fetch_history.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _directory(root: Path, symbols: list[str]) -> None:
    from swingdesk.reference_data.directory import DirectoryStore
    from swingdesk.reference_data.universe import DirectoryEntry

    directory = DirectoryStore(root / "directory.duckdb")
    directory.record([DirectoryEntry(symbol=s, name=s, venue="P", is_etf=True, is_test_issue=False)
                      for s in symbols], datetime(2026, 1, 1, tzinfo=UTC), source="test")
    directory.close()


def _series(name: str, known: datetime):  # type: ignore[no-untyped-def]
    from swingdesk.contracts.market import Bar, BarSeries, Interval, Series

    days = [date(2007, 6, 1) + timedelta(days=i) for i in (0, 3, 4)]
    bars = tuple(Bar(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
                     event_time=datetime.combine(d, time(13, 30), tzinfo=UTC), session_date=d,
                     open=Decimal("150"), high=Decimal("151"), low=Decimal("149"),
                     close=Decimal("150.5"), volume=1_000, knowledge_time=known) for d in days)
    return BarSeries(instrument_id=name, interval=Interval.DAY, series=Series.RAW,
                     knowledge_time=known, bars=bars)


def _dividend(name: str, known: datetime):  # type: ignore[no-untyped-def]
    from swingdesk.contracts.market import CorporateAction, CorporateActionKind

    return CorporateAction(instrument_id=name, kind=CorporateActionKind.DIVIDEND,
                           effective_date=date(2007, 6, 4), value=Decimal("0.55"), knowledge_time=known)


def test_bars_and_dividends_land_under_one_knowledge_time(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    from swingdesk.contracts.market import CorporateActionKind, Interval, Series
    from swingdesk.market_data import BarStore

    tool = _tool()
    _directory(tmp_path, ["SPY", "BIL"])
    asked: list[tuple[str, str]] = []

    def fake_fetch(instrument, interval, known, period=None):  # type: ignore[no-untyped-def]
        asked.append((instrument.id, period))
        return _series(instrument.id, known)

    monkeypatch.setattr(tool, "fetch", fake_fetch)
    monkeypatch.setattr(tool, "fetch_actions", lambda instrument, known, period="max":
                        (_dividend(instrument.id, known),))
    assert tool.run(tmp_path, tmp_path, ["SPY", "BIL"], "max", 0.0) == 0
    assert asked == [("SPY", "max"), ("BIL", "max")]
    with BarStore(tmp_path / "bars.duckdb") as store:
        known = store.latest_knowledge_time()
        assert known is not None
        for name in ("SPY", "BIL"):
            assert len(store.as_of(name, Interval.DAY, Series.RAW, known).bars) == 3
            actions = store.actions_as_of(name, known)
            assert [a.kind for a in actions] == [CorporateActionKind.DIVIDEND]
            assert actions[0].knowledge_time == known, "one instant for the pull's bars and actions"


def test_a_symbol_the_directory_does_not_know_is_refused_and_nothing_is_fetched(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _tool()
    _directory(tmp_path, ["SPY"])
    asked: list[str] = []
    monkeypatch.setattr(tool, "fetch", lambda instrument, *a, **k: asked.append(instrument.id))
    assert tool.run(tmp_path, tmp_path, ["SPY", "NOPE"], "max", 0.0) == tool.MISSING
    assert asked == []
    assert not (tmp_path / "bars.duckdb").exists()


def test_a_symbol_becomes_the_instrument_every_stored_bar_carries(tmp_path: Path) -> None:
    from swingdesk.reference_data.directory import DirectoryStore

    tool = _tool()
    _directory(tmp_path, ["BRK.B"])
    with DirectoryStore(tmp_path / "directory.duckdb") as directory:
        found, missing = tool.resolve(directory, ["BRK.B"], datetime(2026, 2, 1, tzinfo=UTC))
    assert missing == []
    assert found[0].id == "BRK.B" and found[0].ticker == "BRK-B"


def test_a_vendor_failure_is_reported_not_raised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _tool()
    _directory(tmp_path, ["SPY"])

    def down(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise tool.VendorUnavailable("SPY 1d: no data returned")

    monkeypatch.setattr(tool, "fetch", down)
    assert tool.run(tmp_path, tmp_path, ["SPY"], "max", 0.0) == tool.VENDOR
