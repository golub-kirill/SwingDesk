"""Gate 46's own logic: does a long window carry a reason?

`AGENTS.md` §19 is an owner instruction with a number in it, and a rule with a number is the kind
that rots quietly — the constant drifts to meet whatever the last study happened to measure, or the
exemption list grows until nothing is checked.

Four things carry the gate and none of them raises when wrong:

* **the threshold is the owner's 48 months**, not whatever the studies did.
* **it reads the span the study OBTAINED**, never the one its arguments asked for. `PR-016` asked
  for 10.67 years and got 8.91, and only one of those is a fact about the measurement.
* **an exemption is a NAME with a reason**, so a reader can argue with it. A silent skip is a rule
  nobody applies.
* **a missing span is reported and not failed.** `verify_studies` owns what a result must contain;
  this gate owns whether a window was argued for, and conflating them would make one gate's failure
  look like the other's.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def gate():
    spec = importlib.util.spec_from_file_location("_window", REPO / "tools" / "verify_window.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- the number is the owner's -------------------------------------------------------------------

def test_the_threshold_is_forty_eight_months(gate) -> None:
    """Owner instruction, 2026-09-08. A test is what stops a constant drifting to meet a result."""
    assert gate.MAX_MONTHS == 48
    assert gate.MAX_YEARS == 4.0


# --- the span it reads ---------------------------------------------------------------------------

def test_it_reads_the_span_the_study_OBTAINED(gate) -> None:
    """`PR-016` asked for 10.67 years and measured 8.91. Only one of those is a fact about the
    measurement, and a gate reading the request would pass a study that never got the data."""
    assert gate.span_years({"measured_span": {"years": 8.91, "requested_window_years": 10.67}}) == (
        8.91
    )


def test_a_result_with_no_span_cannot_be_checked_and_is_not_failed(gate) -> None:
    assert gate.span_years({}) is None
    assert gate.span_years({"measured_span": "nine years"}) is None
    assert gate.span_years({"measured_span": {}}) is None


def test_an_integer_span_is_read_as_well_as_a_float(gate) -> None:
    """A study whose span lands on a whole number is not a study that skipped the field."""
    assert gate.span_years({"measured_span": {"years": 9}}) == 9.0


# --- the rationale it looks for -------------------------------------------------------------------

@pytest.mark.parametrize("line", [
    "window rationale: the 2020 drawdown is the subject and four years do not contain it",
    "**window rationale**: a 252-session formation inside a 126-session lookback",
    "  Window Rationale - replicating a published result whose window is fixed",
])
def test_a_rationale_is_recognised_however_it_is_formatted(gate, line: str) -> None:
    assert gate.RATIONALE.search(line), line


@pytest.mark.parametrize("line", [
    "window rationale:",
    "the window rationale is discussed below",
    "window: 2016-01-04 .. 2026-09-04",
])
def test_a_non_rationale_is_not_mistaken_for_one(gate, line: str) -> None:
    """An empty label is the failure mode this catches: a study that added the words and no
    reason would otherwise pass, which is worse than one that added neither."""
    assert not gate.RATIONALE.search(line), line


# --- exemptions are names ------------------------------------------------------------------------

def test_every_exemption_carries_a_reason(gate) -> None:
    """A listed exemption a reader can argue with. An entry with an empty reason is a silent skip
    wearing a name."""
    assert gate.EXEMPT
    for study, reason in gate.EXEMPT.items():
        assert study.startswith("PR-"), study
        assert len(reason) > 20, f"{study}'s exemption says nothing"


def test_the_exempt_studies_are_the_ones_that_predate_the_rule(gate) -> None:
    """`AGENTS.md` §19 is dated 2026-09-08. Nothing registered after it may be on this list, or the
    rule exempts its own enforcement."""
    assert set(gate.EXEMPT) == {"PR-014", "PR-015", "PR-016", "PR-017", "PR-018"}


# --- end to end, on a temporary tree --------------------------------------------------------------

def _study(tmp_path: Path, gate, name: str, years: float, rationale: str | None) -> None:
    (tmp_path / "results").mkdir(exist_ok=True)
    (tmp_path / "results" / f"{name}.json").write_text(
        json.dumps({"verdict": "inconclusive", "measured_span": {"years": years}}),
        encoding="utf-8")
    body = "# PREREG\n\nstatus: reported\n"
    if rationale:
        body += f"\nwindow rationale: {rationale}\n"
    (tmp_path / f"{name}-slug.md").write_text(body, encoding="utf-8")
    gate.RESULTS = tmp_path / "results"
    gate.PREREGS = tmp_path


def test_a_long_window_with_no_rationale_FAILS(gate, tmp_path, capsys) -> None:
    _study(tmp_path, gate, "PR-900", 9.5, None)
    assert gate.main() == 1
    assert "window rationale" in capsys.readouterr().out


def test_the_same_study_with_a_rationale_passes(gate, tmp_path, capsys) -> None:
    _study(tmp_path, gate, "PR-901", 9.5, "the 2020 drawdown is the subject")
    assert gate.main() == 0


def test_a_window_inside_the_limit_needs_no_rationale(gate, tmp_path) -> None:
    _study(tmp_path, gate, "PR-902", 3.9, None)
    assert gate.main() == 0


def test_exactly_four_years_is_inside_the_limit(gate, tmp_path) -> None:
    """`<=`, not `<`. Forty-eight months is the default, not the first value that needs defending."""
    _study(tmp_path, gate, "PR-903", 4.0, None)
    assert gate.main() == 0


def test_a_long_window_with_no_prereg_at_all_fails(gate, tmp_path, capsys) -> None:
    _study(tmp_path, gate, "PR-904", 9.5, None)
    (tmp_path / "PR-904-slug.md").unlink()
    assert gate.main() == 1
    assert "no pre-registration" in capsys.readouterr().out
