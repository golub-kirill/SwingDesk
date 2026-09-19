"""`tools/measure_entry_features.py`: `PR-024`'s entries sliced by what the signal close knew.

Exploratory, and the payload says so; what matters here is that each slice is the population it
names - quintiles that partition the entries, a kind read by `PR-026`'s own rule, and a close arm
read net - so the hypotheses it produced can be traced to the entries that produced them.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

from swingdesk.reference_data.directory import DirectoryStore
from swingdesk.reference_data.universe import DirectoryEntry

REPO = Path(__file__).resolve().parents[1]
KNOWN = datetime(2026, 1, 5, tzinfo=UTC)


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    return _load("_measure_entry_features", REPO / "tools" / "measure_entry_features.py")


@pytest.fixture(scope="module")
def world() -> ModuleType:
    return _load("_run_pr024_world_for_features", REPO / "tests" / "test_run_pr024.py")


def test_quintiles_partition_the_entries_in_order(tool) -> None:
    records = [{"close_net": i / 100, "open_net": None, "x": float(i)} for i in range(10)]
    rows = tool.quintiles(records, "x")
    assert [r["entries"] for r in rows] == [2] * 5
    assert rows[0]["from"] == 0.0 and rows[-1]["to"] == 9.0
    assert rows[-1]["close_mean"] == pytest.approx(0.085)
    assert rows[0]["close_win_share"] == 0.5, "0.00 is not a win"


def test_a_row_reads_the_close_arm_and_the_open_beside_it(tool) -> None:
    got = tool.row("g", [{"close_net": 0.02, "open_net": -0.01},
                         {"close_net": -0.04, "open_net": None}])
    assert got["entries"] == 2 and got["close_mean"] == pytest.approx(-0.01)
    assert got["open_mean"] == pytest.approx(-0.01) and got["close_win_share"] == 0.5


def test_the_measurement_runs_on_synthetic_stores(tool, world, tmp_path, monkeypatch) -> None:
    args, _ = world._world(tmp_path, tool.p24)
    with DirectoryStore(tmp_path / "directory.duckdb") as directory:
        directory.record([DirectoryEntry("AAA", "Alpha Corp", "NYSE", False, False),
                          DirectoryEntry("BBB", "Direxion Daily Beta Bull 3X Shares", "NYSE Arca",
                                         True, False)], KNOWN, "test")
    monkeypatch.setattr(tool, "HISTORY", 30)
    namespace = argparse.Namespace(**vars(args), directory=tmp_path / "directory.duckdb",
                                   out=tmp_path / "out.json")
    payload = tool.build(namespace)
    assert payload["exploratory"] is True
    assert payload["overall"]["entries"] > 0
    assert set(payload["kinds_counted"]) <= {"stock", "levered fund"}
    assert payload["kinds_counted"].get("levered fund", 0) > 0, "BBB is marked by PR-026's rule"
    assert set(payload["by_feature"]) == set(tool.FEATURES)
