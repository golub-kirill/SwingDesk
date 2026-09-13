"""`tools/remeasure.py` - the scheduled re-observation, and the guard that keeps it from being a search.

`AGENTS.md` §19.7: re-observing a registered question spends no trial ONLY because every point is
scheduled and recorded whatever it says. Two properties carry that, and both fail silently:

* **append-only.** A series that can be rewritten can have its unwelcome points removed.
* **no backdating.** A point earlier than the last one would be re-drawing the past - the search in
  time the ruling's guard exists to stop - whether the earlier instant was asked for or arrived
  because an older store was restored.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
LAST = "2026-09-06T22:00:00-05:00"


@pytest.fixture(scope="module")
def tool():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_remeasure", REPO / "tools" / "remeasure.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _point(as_of: str) -> dict[str, Any]:
    return {"as_of": as_of, "window": {"start": "2022-09-04", "end": "2026-09-04"},
            "trades": 100, "months": 48, "candidate": None, "candidate_level": 0.01,
            "index_leg": None, "branch": "null",
            "candidate_minus_index": {"observed": -0.1, "low": -0.2, "high": 0.0}}


def _seeded(tool, root: Path) -> Path:
    path = tool.series_path(root, "PR-019b")
    tool.append(path, {"study": "PR-019b", "recorded_at": "2026-09-07T00:00:00+00:00",
                       **_point(LAST)})
    return path


def test_the_series_is_append_only(tool, tmp_path):
    path = tmp_path / "series.jsonl"
    tool.append(path, {"study": "X", "n": 1})
    first = path.read_bytes()
    tool.append(path, {"study": "X", "n": 2})
    assert path.read_bytes().startswith(first), "an earlier point is never rewritten"
    assert [p["n"] for p in tool.read_series(path)] == [1, 2]


def test_an_earlier_as_of_is_refused(tool):
    with pytest.raises(SystemExit, match="refused"):
        tool.refuse_backdating([_point(LAST)], "2026-06-01T22:00:00-05:00")


def test_the_same_or_a_later_as_of_is_accepted(tool):
    tool.refuse_backdating([_point(LAST)], LAST)
    tool.refuse_backdating([_point(LAST)], "2026-12-06T22:00:00-05:00")
    tool.refuse_backdating([], "2020-01-01T00:00:00+00:00")


def test_a_run_appends_one_stamped_record(tool, tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(tool.STUDIES, "PR-019b", lambda data, as_of: _point(LAST))
    monkeypatch.setattr(sys, "argv", ["remeasure.py", "PR-019b", "--data", str(tmp_path)])

    assert tool.main() == 0

    series = tool.read_series(tool.series_path(tmp_path, "PR-019b"))
    assert len(series) == 1
    assert series[0]["study"] == "PR-019b" and series[0]["recorded_at"]
    assert "RE-OBSERVATIONS, not results" in capsys.readouterr().out


def test_an_asked_for_earlier_instant_is_refused_before_anything_runs(tool, tmp_path,
                                                                      monkeypatch):
    path = _seeded(tool, tmp_path)
    before = path.read_bytes()
    monkeypatch.setitem(tool.STUDIES, "PR-019b",
                        lambda data, as_of: pytest.fail("a backdated run must not start"))
    monkeypatch.setattr(sys, "argv", ["remeasure.py", "PR-019b", "--data", str(tmp_path),
                                      "--as-of", "2026-01-01T00:00:00-05:00"])

    with pytest.raises(SystemExit, match="refused"):
        tool.main()
    assert path.read_bytes() == before


def test_an_older_store_is_refused_after_the_run_and_writes_nothing(tool, tmp_path, monkeypatch):
    """No instant asked for, but the store's own latest is earlier - a restored backup, say. The
    run happens; the point is still refused, because the series would move backwards."""
    path = _seeded(tool, tmp_path)
    before = path.read_bytes()
    monkeypatch.setitem(tool.STUDIES, "PR-019b",
                        lambda data, as_of: _point("2026-08-01T22:00:00-05:00"))
    monkeypatch.setattr(sys, "argv", ["remeasure.py", "PR-019b", "--data", str(tmp_path)])

    with pytest.raises(SystemExit, match="refused"):
        tool.main()
    assert path.read_bytes() == before


def test_no_series_is_said_rather_than_printed_as_an_empty_table(tool, capsys):
    tool.report([])
    assert "has not run" in capsys.readouterr().out


def test_pr016_is_re_observed_and_reported_on_its_own_quantity(tool, capsys):
    """`PR-016` reads ranked minus unselected, not `PR-019b`'s candidate minus index."""
    assert set(tool.STUDIES) == {"PR-019b", "PR-016"} == set(tool.READS)
    point = {"as_of": LAST, "window": {}, "trades": 300, "months": 48, "branch": "inconclusive",
             "ranked_minus_unselected": {"observed": 0.09, "low": 0.02, "high": 0.16}}
    tool.report([{"study": "PR-016", "recorded_at": "2026-09-13T21:00:00", **point}])
    out = capsys.readouterr().out
    assert "ranked - unselected" in out and "+0.0900 [+0.0200, +0.1600]" in out


def test_the_weekly_pass_runs_every_study_and_keeps_the_first_failure():
    wrapper = (REPO / "tools" / "remeasure.cmd").read_text(encoding="utf-8")
    runs = [line for line in wrapper.splitlines() if "remeasure.py" in line
            and not line.startswith("REM")]
    assert [line.split("remeasure.py\" ")[1].split()[0] for line in runs] == ["PR-019b", "PR-016"]
    assert "if %RC%==0 set RC=%ERRORLEVEL%" in wrapper


def test_the_report_says_how_far_the_read_quantity_has_moved(tool, capsys):
    later = {**_point("2026-09-13T22:00:00-05:00"),
             "candidate_minus_index": {"observed": -0.05, "low": -0.15, "high": 0.05}}
    tool.report([{"study": "PR-019b", "recorded_at": "2026-09-07T00:00:00", **_point(LAST)},
                 {"study": "PR-019b", "recorded_at": "2026-09-14T00:00:00", **later}])
    assert "moved +0.0500R since the first point" in capsys.readouterr().out
