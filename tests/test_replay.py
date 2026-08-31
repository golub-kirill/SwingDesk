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


class _Branches(dict):
    """What each instrument decided, as `(decision, reason_code)`, plus its free text."""

    def __init__(self, decisions) -> None:
        super().__init__({d.instrument_id: (d.decision, d.reason_code) for d in decisions})
        self._reasons = {d.instrument_id: d.reason or "" for d in decisions}

    def reason(self, instrument_id: str) -> str:
        return self._reasons[instrument_id]


def _decisions(case) -> _Branches:
    """Re-run the case for its decisions. `replay()` returns only the hash, which is the point of a
    determinism gate and exactly why it cannot say WHICH branches a case still covers."""
    import tempfile
    from pathlib import Path

    from swingdesk.contracts.run import RunMode
    from swingdesk.journal_evidence.journal import Journal
    from swingdesk.market_data import BarStore
    from swingdesk.platform.clock import FixedClock

    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        with BarStore(root / "b.duckdb") as store, Journal(root / "j.duckdb") as journal:
            result = harness.run(
                list(case.instruments), FixedClock(case.as_of),
                harness._registry_for(case.parameters), store, journal,
                mode=RunMode.REPLAY, lookback=case.lookback, fetcher=harness._fetcher(case),
            )
    return _Branches(result.decisions)


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

    # Counting instruments was all this asserted until 2026-08-18, which is a count and not a
    # branch: the case could have lost the warm-up path entirely and still shown four rows. It
    # nearly did - `DR-015`'s freshness gate drops a stale series BEFORE warm-up is reached, and
    # TEST.3's bars ended a month before the as-of. Now the outcomes themselves are asserted.
    case = harness.load_case(case_dir)
    branches = _decisions(case)

    assert branches["TEST.1"] == ("Watch", None), "a candidate that sizes"
    # A different exchange AND a different currency. It reaches sizing on the TSX calendar and is
    # then refused for the reason PR #9 introduced: the account is USD and `account.fx_rate_cad` is
    # null in this case, so the R denominator cannot be expressed in the account's own currency.
    assert branches["TEST.2.TO"] == ("Skip", "RISK"), "a second exchange, and the FX refusal"
    assert branches["TEST.3"] == ("Skip", "DATA"), "warm-up incomplete"
    assert branches["TEST.4"] == ("Skip", "DATA"), "no recorded bars: the vendor refuses"
    assert branches["TEST.5"] == ("Skip", "DATA"), "two sessions behind: dropped by the window"

    # Same code, different causes - so the reasons are what tell the three DATA branches apart.
    assert "warm-up" in branches.reason("TEST.3")
    assert "no recorded bars" in branches.reason("TEST.4")
    assert "dropped from this run" in branches.reason("TEST.5")

    assert len(case.instruments) == 5
    # Named rather than counted. This read `len(case.bars) == 4` until `DR-024` added the benchmark
    # series, and a count cannot say WHICH series is missing - it went red for the one reason that
    # was not a defect. `SPY` is in `bars` and NOT in `instruments` on purpose: it is the
    # denominator the RS line is measured against, not a candidate the run decides on.
    assert set(case.bars) == {"TEST.1", "TEST.2.TO", "TEST.3", "TEST.5", "SPY"}
    assert "TEST.4" not in case.bars, "TEST.4 is deliberately absent so the fetcher refuses"
    assert "SPY" not in {i.id for i in case.instruments}, "the benchmark is not a candidate"


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


def test_the_case_exercises_the_relative_strength_path(case_dir) -> None:
    """`DR-024`. The gate must cover the RS line, not merely pin its absence.

    When the RS field was added to `output_hash` the recorded case had no `rs.benchmark`, so it
    replayed with the measure UNAVAILABLE and would have frozen that as the reference - a gate
    covering a new computation only in the branch where it does not run. The fixture was extended
    with a benchmark instead, and this asserts the extension survives.

    The benchmark walks the ZIGZAG path deliberately. On the rising path every fixture instrument is
    the same arithmetic, so the RS line would be exactly 1.0 on every session and the recorded hash
    would pin the plumbing and none of the measure.
    """
    import json

    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    bars = json.loads((case_dir / "bars.json").read_text(encoding="utf-8"))

    benchmark = case["parameters"].get("rs.benchmark")
    assert benchmark == "SPY", "the case must name a benchmark or it pins only the unavailable path"
    assert benchmark in bars, "the benchmark is named but has no bars, which IS the unavailable path"

    closes = [row[4] for row in bars[benchmark]["bars"]]
    assert len(set(closes)) > 1, "a flat benchmark makes every RS line constant"
