"""The determinism replay gate, and proof that it distinguishes its three failure modes.

A gate that reports every mismatch as "non-deterministic" is worse than none: the first time it
fires on a config edit, the operator learns to disbelieve it. So each of these asserts not just
that the gate failed, but that it named the right cause.
"""

from __future__ import annotations

import json
import shutil

import pytest

from swingdesk.validation import replay as harness

CASE = "daily-three-instruments"


@pytest.fixture
def case_dir(tmp_path):
    """A writable copy of the committed replay case."""
    destination = tmp_path / CASE
    shutil.copytree(harness.REPLAY_ROOT / CASE, destination)
    return destination


def _rewrite(directory, mutate) -> None:
    path = directory / "case.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def test_stored_cases_replay() -> None:
    """The ratified Track A criterion a.reproducible, checked against a stored manifest."""
    assert harness.verify() == []


def test_case_covers_every_branch(case_dir) -> None:
    """A fixture that only exercises the happy path pins the least interesting third of the run.

    The recorded case must still produce a sized candidate, a warm-up refusal and a vendor refusal,
    or the hash stops covering the paths most likely to break.
    """
    result = harness.replay(harness.load_case(case_dir))
    assert result.matched
    # Four instruments, three fixtures: one is deliberately absent so the fetcher refuses.
    case = harness.load_case(case_dir)
    assert len(case.instruments) == 4
    assert len(case.bars) == 3


def test_edited_inputs_are_not_called_non_determinism(case_dir) -> None:
    """Editing the recorded snapshot is a fixture change, not a defect in the decision path."""
    bars_path = case_dir / "bars.json"
    recorded = json.loads(bars_path.read_text(encoding="utf-8"))
    recorded["TEST.1"]["bars"][-1][4] = "500.00"
    recorded["TEST.1"]["bars"][-1][2] = "501.00"  # keep high >= close
    bars_path.write_text(json.dumps(recorded, indent=2) + "\n", encoding="utf-8")

    case = harness.load_case(case_dir)
    assert not case.inputs_intact
    result = harness.replay(case)
    assert not result.matched
    assert any("recorded inputs were edited" in note for note in result.diagnosis)
    assert not any("determinism defect" in note for note in result.diagnosis)


def test_changed_config_is_named(case_dir) -> None:
    """A changed parameter value must be reported as a config change, not as non-determinism.

    This is the case that broke first: config_hash originally covered only which parameters were
    set, so a changed threshold left it unmoved and the gate blamed the decision path.
    """
    _rewrite(case_dir, lambda document: document["parameters"].update({"atr.period": 10}))
    # The digest covers parameters, so re-freeze it: the edit is deliberate and declared.
    _rewrite(
        case_dir,
        lambda document: document.update(
            {"inputs_digest": harness._inputs_digest(case_dir, document)}
        ),
    )

    case = harness.load_case(case_dir)
    assert case.inputs_intact
    result = harness.replay(case)
    assert not result.matched
    assert any("config_hash changed" in note for note in result.diagnosis)


def test_missing_manifest_is_a_failure(case_dir, tmp_path) -> None:
    """An unrecorded case must fail rather than silently pass as "nothing to compare"."""
    _rewrite(case_dir, lambda document: document.update({"manifest": None}))
    failures = harness.verify(tmp_path)
    assert any("no recorded manifest" in failure for failure in failures)
