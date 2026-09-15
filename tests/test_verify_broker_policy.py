"""Gate 39's role checks: every write verb has one job, and the job has the verb its record granted.

The gate reads the committed policy from the syntax of YAML, never importing the adapter, so it is
tested the same way: the committed file, edited in one place, written to a temporary directory.
`DR-043` added the second write verb on 2026-09-14, and these are the checks that keep a second
verb from becoming a third without a decision record.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import verify_broker_policy as gate


def _failures(tmp_path: Path, monkeypatch, edit=None) -> list[str]:
    raw = yaml.safe_load(gate.POLICY.read_text(encoding="utf-8"))
    if edit is not None:
        edit(raw)
    written = tmp_path / "broker_policy.yml"
    written.write_text(yaml.safe_dump(raw), encoding="utf-8")
    monkeypatch.setattr(gate, "POLICY", written)
    failures, _ = gate._policy_failures()
    return failures


def test_the_committed_policy_passes(tmp_path: Path, monkeypatch) -> None:
    assert _failures(tmp_path, monkeypatch) == []


def test_the_package_spells_no_verb_and_reaches_the_transport_twice() -> None:
    """The replace went through `_write`, so the gate's caller count did not have to move."""
    assert gate._package_failures() == []
    assert frozenset({"_get", "_write"}) == gate.TRANSPORT_CALLERS


@pytest.mark.parametrize("verb", ["DELETE", "PUT"])
def test_cancelling_and_overwriting_are_refused(tmp_path: Path, monkeypatch, verb: str) -> None:
    def edit(raw):
        raw["access"]["allowed_methods"].append(verb)

    assert any(verb in failure and "cancelling" in failure
               for failure in _failures(tmp_path, monkeypatch, edit))


def test_the_replace_job_is_patch_and_nothing_else(tmp_path: Path, monkeypatch) -> None:
    def edit(raw):
        raw["write"]["replace_method"] = "POST"

    assert any("That job is PATCH" in failure
               for failure in _failures(tmp_path, monkeypatch, edit))


def test_the_submit_job_is_post_and_nothing_else(tmp_path: Path, monkeypatch) -> None:
    def edit(raw):
        raw["write"]["submit_method"] = "PATCH"

    assert any("That job is POST" in failure
               for failure in _failures(tmp_path, monkeypatch, edit))


def test_a_permitted_verb_with_no_job_fails(tmp_path: Path, monkeypatch) -> None:
    def edit(raw):
        del raw["write"]["replace_method"]

    assert any("exactly one job" in failure
               for failure in _failures(tmp_path, monkeypatch, edit))


def test_a_job_whose_verb_is_not_permitted_fails(tmp_path: Path, monkeypatch) -> None:
    def edit(raw):
        raw["access"]["allowed_methods"] = ["GET", "POST"]

    assert any("exactly one job" in failure
               for failure in _failures(tmp_path, monkeypatch, edit))


def test_the_submit_job_is_required(tmp_path: Path, monkeypatch) -> None:
    def edit(raw):
        del raw["write"]["submit_method"]

    assert any("`write.submit_method` is missing" in failure
               for failure in _failures(tmp_path, monkeypatch, edit))


def test_a_replace_needs_an_endpoint_naming_one_order(tmp_path: Path, monkeypatch) -> None:
    def edit(raw):
        raw["endpoints"]["order"] = "/v2/orders"

    assert any("endpoints.order" in failure
               for failure in _failures(tmp_path, monkeypatch, edit))


def test_taking_the_replace_away_is_a_valid_policy(tmp_path: Path, monkeypatch) -> None:
    """Two deleted lines, and the gate passes - narrowing never needs a third edit."""
    def edit(raw):
        raw["access"]["allowed_methods"] = ["GET", "POST"]
        del raw["write"]["replace_method"]

    assert _failures(tmp_path, monkeypatch, edit) == []
