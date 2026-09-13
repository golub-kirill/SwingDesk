"""The power estimate `PR-019` registers its minimum detectable effect from.

`PR-018`'s §3 took a prior study's half-width on a stated ground that was false, and the realised
intervals came out five to nine times wider. This tool replaces the borrowed number with a variance
estimate, and four things carry it. None of them raises when wrong:

* **every cell must realise the SAME entries**, or the paired difference is not paired. `spaced` is
  what guarantees it, and a spacing one session short of the longest hold silently re-opens the
  coupling `PR-018` A-1 could only report.
* **the subsample must be stable** when the universe grows, or a re-run is a different estimate
  wearing the same seed.
* **the subsampling noise must be REMOVED, not left in** - and the correction must be allowed to go
  negative, because a floored variance is a floored minimum detectable effect.
* **no level may leak.** A power calculation that prints a mean is the study, run early and
  unregistered.
"""

from __future__ import annotations

import importlib.util
import statistics
import sys
from datetime import date, timedelta
from itertools import pairwise
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def power():
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location("_power_pr019", REPO / "tools" / "power_pr019.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _calendar(n: int) -> tuple[list[date], dict[date, int]]:
    days = [date(2020, 1, 1) + timedelta(days=i) for i in range(n)]
    return days, {d: i for i, d in enumerate(days)}


# --- the grid ------------------------------------------------------------------------------------


def test_the_grid_is_twelve_cells_and_none_carries_a_target(power):
    cells = power.cells()
    assert len(cells) == len(power.HOLDS) * len(power.STOPS) == 12
    assert all(policy.target_r_multiple is None for policy in cells.values())


def test_a_cell_without_a_stop_still_has_an_R_denominator(power):
    """R is `entry - stop`; a null arm priced in different units cannot be subtracted."""
    policy = power.cells()["h60_stopnone"]
    assert policy.protective is False
    assert policy.atr_stop_multiple == power.R_DENOMINATOR_MULTIPLE


def test_each_cell_holds_for_its_own_period(power):
    cells = power.cells()
    for hold in power.HOLDS:
        for label, _ in power.STOPS:
            assert cells[power.cell_name(hold, label)].max_holding_bars == hold


# --- one entry set for every cell ----------------------------------------------------------------


def test_spacing_takes_the_first_signal_and_blocks_the_next_max_hold_sessions(power):
    days, index = _calendar(200)
    signals = [days[0], days[20], days[40], days[60], days[61], days[140]]
    assert power.spaced(signals, index, 60) == [days[0], days[61], days[140]]


def test_a_signal_exactly_spacing_sessions_later_is_still_blocked(power):
    """The boundary that decides whether a 60-session position can still be open.

    A position entered on session 0 and held 60 bars exits at the close of session 60, so an entry
    ON session 60 would find it still open under the longest cell. One session later it is free.
    """
    days, index = _calendar(100)
    assert power.spaced([days[0], days[60]], index, 60) == [days[0]]
    assert power.spaced([days[0], days[61]], index, 60) == [days[0], days[61]]


def test_spacing_is_order_independent(power):
    days, index = _calendar(200)
    signals = [days[140], days[0], days[61], days[20]]
    assert power.spaced(signals, index, 60) == [days[0], days[61], days[140]]


def test_spacing_at_the_longest_hold_means_no_cell_ever_sees_an_open_position(power):
    """The property the whole construction exists for, checked for every hold in the grid."""
    days, index = _calendar(400)
    signals = days[::20]
    taken = power.spaced(signals, index, power.MAX_HOLD)
    gaps = [index[b] - index[a] for a, b in pairwise(taken)]
    assert all(gap > hold for gap in gaps for hold in power.HOLDS)


# --- a stable subsample --------------------------------------------------------------------------


def test_the_subsample_is_deterministic(power):
    names = [f"N{i:04d}" for i in range(2000)]
    assert power.subsample(names, 0.25, 7) == power.subsample(names, 0.25, 7)


def test_the_subsample_keeps_every_name_when_the_universe_grows(power):
    """Hashing the name, not slicing a shuffle, is what makes a later re-run comparable."""
    small = [f"N{i:04d}" for i in range(1000)]
    grown = small + [f"M{i:04d}" for i in range(1000)]
    assert set(power.subsample(small, 0.25, 7)) <= set(power.subsample(grown, 0.25, 7))


def test_the_subsample_is_about_the_fraction_asked_for(power):
    names = [f"N{i:05d}" for i in range(20000)]
    share = len(power.subsample(names, 0.25, 7)) / len(names)
    assert 0.23 < share < 0.27


def test_a_different_seed_draws_a_different_subsample(power):
    names = [f"N{i:04d}" for i in range(2000)]
    assert power.subsample(names, 0.25, 7) != power.subsample(names, 0.25, 8)


@pytest.mark.parametrize("fraction", [0.0, -0.1, 1.5])
def test_an_impossible_fraction_is_refused(power, fraction):
    with pytest.raises(SystemExit):
        power.subsample(["A", "B"], fraction, 7)


# --- the noise a subsample adds is removed -------------------------------------------------------


def test_the_correction_subtracts_exactly_the_within_month_noise(power):
    per_trade = {"2020-01": [0.0, 2.0], "2020-02": [1.0, 3.0], "2020-03": [4.0, 6.0]}
    got = power.variance_components(per_trade)
    means = [1.0, 2.0, 5.0]
    noise = statistics.fmean([statistics.variance(v) / 2 for v in per_trade.values()])
    assert got["var_observed"] == pytest.approx(statistics.variance(means))
    assert got["var_subsample_noise"] == pytest.approx(noise)
    assert got["var_between"] == pytest.approx(statistics.variance(means) - noise)
    assert got["months"] == 3


def test_the_correction_is_allowed_to_go_negative(power):
    """Pure noise around one level: no between-month signal, and the estimate must say so."""
    per_trade = {"2020-01": [-5.0, 5.0], "2020-02": [-5.0, 5.0], "2020-03": [-4.0, 4.0]}
    assert power.variance_components(per_trade)["var_between"] < 0


def test_a_month_with_one_trade_cannot_estimate_its_own_noise_and_is_left_out(power):
    per_trade = {"2020-01": [0.0, 2.0], "2020-02": [1.0, 3.0], "2020-03": [99.0]}
    assert power.variance_components(per_trade)["months"] == 2


def test_too_few_months_is_a_refusal_not_a_number(power):
    with pytest.raises(SystemExit):
        power.variance_components({"2020-01": [0.0, 1.0]})


def test_a_non_positive_variance_gives_no_half_width(power):
    """A negative corrected variance means the subsample was too thin - never a zero MDE."""
    import math

    assert math.isnan(power.half_width(-0.01, 50))
    assert math.isnan(power.half_width(0.0, 50))


def test_a_half_width_is_carried_to_the_out_of_sample_months_by_root_n(power):
    got = power.predicted_oos(0.10, 48)
    assert got == pytest.approx(0.10 * (48 / power.OOS_MONTHS) ** 0.5)
    assert got < 0.10  # more months out of sample, so narrower


def test_an_unusable_half_width_stays_unusable_when_carried(power):
    import math

    assert math.isnan(power.predicted_oos(float("nan"), 48))
    assert math.isnan(power.predicted_oos(0.1, 0))


def test_readable_is_half_the_registered_floor(power):
    assert power.READABLE_HALF_WIDTH == pytest.approx(0.15 / 2)


def test_the_half_width_is_the_normal_approximation(power):
    assert power.half_width(0.04, 100) == pytest.approx(1.96 * 0.02)


# --- no level leaks ------------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["mean", "mean_net_r", "median", "effect", "win_rate", "verdict"])
def test_a_level_anywhere_in_the_payload_is_refused(power, key):
    with pytest.raises(AssertionError):
        power.assert_no_effect_leaked({"contrasts": {"a vs b": {key: 0.1}}})


def test_a_level_inside_a_list_is_refused_too(power):
    with pytest.raises(AssertionError):
        power.assert_no_effect_leaked({"rows": [{"ok": 1}, {"Mean": 0.1}]})


def test_the_payloads_own_metadata_passes(power):
    """The first real run died here: `window` contains `win`, and a substring guard fired on it.

    Every key `build` writes that is NOT a level, listed so a new one that trips the guard fails a
    test in a second instead of a run in ten minutes.
    """
    power.assert_no_effect_leaked({
        "for": "PR-019", "purpose": "x", "as_of": "x", "fraction": 0.25, "seed": 1,
        "universe": 1, "subsample": 1, "formation_dates": 1,
        "formations_skipped_for_a_thin_cross_section": 0,
        "window": {"start": "x", "end": "x", "note": "x"},
        "grid": {"holds": [10], "stops": ["2.0"], "entry_spacing_sessions": 60},
        "entries": {"instruments": 1, "signals_before_spacing": 1, "entries_after_spacing": 1,
                    "trades_shared_by_every_cell": 1, "every_cell_realised_the_same_entries": True},
        "contrasts": {"h10_stop2.0 vs h60_stopnone": {
            "months": 1.0, "var_observed": 1.0, "var_subsample_noise": 0.1, "var_between": 0.9,
            "half_width_uncorrected": 0.1, "half_width_corrected": 0.1}},
        "approximation": "x",
    })


@pytest.mark.parametrize("key", ["Mean", "mean net r", "WIN_RATE"])
def test_the_token_match_is_case_and_separator_blind(power, key):
    with pytest.raises(AssertionError):
        power.assert_no_effect_leaked({key: 0.1})


def test_dispersion_passes(power):
    power.assert_no_effect_leaked({"contrasts": {"a vs b": {
        "var_observed": 1.0, "var_between": 0.5, "half_width_corrected": 0.1, "months": 50.0}}})
