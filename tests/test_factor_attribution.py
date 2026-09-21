"""`tools/factor_attribution.py` - the six-factor regression `DR-049` made a required curve.

The properties worth breaking a build over, each one a way an alpha can be wrong while looking
right:

* **percent becomes fraction exactly once.** French publishes `-0.67` for −0.67%. Divide twice and
  every beta is right while every alpha is a hundredth of itself;
* **the regression is on EXCESS return.** Forget to subtract `RF` and the alpha quietly contains
  the risk-free rate - which is positive, and which is exactly the direction that flatters;
* **a portfolio that IS its factors has no alpha.** The strongest test available, because it has a
  known answer;
* **alpha annualises by COMPOUNDING.** `alpha * 252` overstates a positive alpha;
* **a monthly row is dated by the month's LAST day**, or a January strategy return joins December's
  factors.
"""

from __future__ import annotations

import importlib.util
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def fa():
    sys.path.insert(0, str(REPO / "tools"))
    spec = importlib.util.spec_from_file_location(
        "factor_attribution", REPO / "tools" / "factor_attribution.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _factors(fa, n: int, seed: int = 5) -> dict[date, dict[str, float]]:
    """`n` days of independent factor returns, already in FRACTIONS."""
    rng = random.Random(seed)
    out: dict[date, dict[str, float]] = {}
    for i in range(n):
        day = date(2020, 1, 1) + timedelta(days=i)
        out[day] = {name: rng.gauss(0.0, 0.01) for name in fa.FACTORS}
        out[day]["RF"] = 0.00008
    return out


# --- the unit conversions -------------------------------------------------------------------------


def test_percent_becomes_fraction(fa) -> None:
    assert fa.to_fraction({"Mkt-RF": -0.67, "RF": 0.01}) == pytest.approx(
        {"Mkt-RF": -0.0067, "RF": 0.0001})


def test_a_daily_token_is_its_own_day(fa) -> None:
    assert fa.read_day("20260731") == date(2026, 7, 31)


def test_a_monthly_token_is_the_month_s_LAST_day(fa) -> None:
    # The first reading of a month's factor return is known at its END. Dating it to the first
    # would join January's strategy return to December's factors.
    assert fa.read_day("202607") == date(2026, 7, 31)
    assert fa.read_day("202602") == date(2026, 2, 28)
    assert fa.read_day("202412") == date(2024, 12, 31)


def test_a_leap_february_is_handled(fa) -> None:
    assert fa.read_day("202402") == date(2024, 2, 29)


# --- reading the store ------------------------------------------------------------------------------


def _store(fa, tmp_path, rows: list[str]) -> Path:
    path = tmp_path / "factors-daily.csv"
    header = "date," + ",".join(fa.FACTORS) + ",RF"
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


def test_the_store_holds_percent_and_the_reader_returns_fractions(fa, tmp_path) -> None:
    path = _store(fa, tmp_path, ["20200102,1.00,0.50,-0.25,0.10,0.05,0.20,0.01"])
    got = fa.load(path)
    assert got[date(2020, 1, 2)]["Mkt-RF"] == pytest.approx(0.01)
    assert got[date(2020, 1, 2)]["RF"] == pytest.approx(0.0001)


def test_a_row_with_the_library_s_missing_marker_is_DROPPED(fa, tmp_path) -> None:
    path = _store(fa, tmp_path, ["20200102,1.00,0.50,-0.25,0.10,0.05,0.20,0.01",
                                 "20200103,-99.99,-99.99,-99.99,-99.99,-99.99,-99.99,-99.99"])
    got = fa.load(path)
    assert date(2020, 1, 2) in got
    assert date(2020, 1, 3) not in got, "a missing marker is not a -99.99% return"


def test_a_row_missing_a_factor_is_dropped_rather_than_filled(fa, tmp_path) -> None:
    path = _store(fa, tmp_path, ["20200102,1.00,0.50,-0.25,0.10,0.05,,0.01"])
    assert fa.load(path) == {}


# --- the regression ---------------------------------------------------------------------------------


def test_a_portfolio_that_IS_its_factors_has_no_alpha(fa) -> None:
    # The strongest test available: build the strategy FROM the factors and the intercept must be
    # zero. Any unit error, any forgotten RF, any sign flip moves it off zero.
    factors = _factors(fa, 600)
    weights = {"Mkt-RF": 1.0, "SMB": 0.5, "HML": -0.3, "RMW": 0.0, "CMA": 0.0, "MOM": 0.0}
    strategy = {day: row["RF"] + sum(weights[n] * row[n] for n in fa.FACTORS)
                for day, row in factors.items()}
    found = fa.attribute(strategy, factors, 252)
    assert found.alpha_a_period == pytest.approx(0.0, abs=1e-12)
    assert not found.alpha_survives
    for name, weight in weights.items():
        assert found.betas[name] == pytest.approx(weight, abs=1e-9)
    assert found.r_squared == pytest.approx(1.0, abs=1e-9)


def test_a_known_alpha_is_recovered(fa) -> None:
    factors = _factors(fa, 800, seed=9)
    daily_alpha = 0.0004
    strategy = {day: row["RF"] + daily_alpha + 0.8 * row["Mkt-RF"]
                for day, row in factors.items()}
    found = fa.attribute(strategy, factors, 252)
    assert found.alpha_a_period == pytest.approx(daily_alpha, abs=1e-9)
    assert found.betas["Mkt-RF"] == pytest.approx(0.8, abs=1e-9)
    assert found.alpha_survives, "a noiseless alpha must clear its own standard error"


def test_forgetting_the_risk_free_rate_would_show_up_as_alpha(fa) -> None:
    # The strategy earns EXACTLY the risk-free rate and nothing else. Its alpha is zero, and a
    # regression that skipped the RF subtraction would report the whole risk-free rate instead.
    factors = _factors(fa, 400)
    strategy = {day: row["RF"] for day, row in factors.items()}
    assert fa.attribute(strategy, factors, 252).alpha_a_period == pytest.approx(0.0, abs=1e-12)


def test_alpha_annualises_by_compounding_not_by_multiplying(fa) -> None:
    factors = _factors(fa, 400)
    daily = 0.001
    strategy = {day: row["RF"] + daily for day, row in factors.items()}
    found = fa.attribute(strategy, factors, 252)
    assert found.alpha_annual == pytest.approx((1 + daily) ** 252 - 1, rel=1e-6)
    assert found.alpha_annual > daily * 252, "compounding must exceed multiplying for a gain"


def test_the_t_statistic_falls_as_noise_rises(fa) -> None:
    factors = _factors(fa, 700, seed=3)
    rng = random.Random(4)
    quiet = {d: r["RF"] + 0.0003 + rng.gauss(0, 0.0005) for d, r in factors.items()}
    rng = random.Random(4)
    noisy = {d: r["RF"] + 0.0003 + rng.gauss(0, 0.02) for d, r in factors.items()}
    assert abs(fa.attribute(quiet, factors, 252).alpha_t) > \
           abs(fa.attribute(noisy, factors, 252).alpha_t)


def test_the_survival_test_is_the_two_sided_five_per_cent_one(fa) -> None:
    made = fa.Attribution(periods=300, periods_a_year=252, alpha_a_period=0.0, alpha_annual=0.0,
                          alpha_t=1.95, betas={}, betas_t={}, r_squared=0.0, hac_lag=4,
                          first=None, last=None)
    assert not made.alpha_survives
    assert fa.Attribution(**{**made.__dict__, "alpha_t": 1.97}).alpha_survives
    assert fa.Attribution(**{**made.__dict__, "alpha_t": -2.5}).alpha_survives, "two-sided"


# --- alignment ----------------------------------------------------------------------------------------


def test_alignment_is_an_inner_join_and_never_a_fill(fa) -> None:
    factors = _factors(fa, 100)
    strategy = {day: 0.001 for day in factors}
    strategy[date(2031, 1, 1)] = 0.001          # a day the library does not reach
    days, excess, _ = fa.align(strategy, factors)
    assert len(days) == 100 and len(excess) == 100
    assert date(2031, 1, 1) not in days, "a period with no factor row cannot be attributed"


def test_a_factor_row_missing_RF_is_skipped(fa) -> None:
    factors = _factors(fa, 50)
    del factors[date(2020, 1, 10)]["RF"]
    days, _, _ = fa.align({d: 0.001 for d in factors}, factors)
    assert date(2020, 1, 10) not in days


def test_too_few_periods_refuses_rather_than_fitting_noise(fa) -> None:
    factors = _factors(fa, 6)
    with pytest.raises(ValueError, match="cannot fit"):
        fa.attribute({d: 0.001 for d in factors}, factors, 252)


# --- the standard errors --------------------------------------------------------------------------------


@pytest.mark.parametrize(("n", "expected"), [(1, 1), (100, 4), (2659, 8), (3002, 8),
                                            (3923, 9)])
def test_the_hac_lag_is_a_function_of_the_sample(fa, n, expected) -> None:
    # floor(4 * (n/100) ** (2/9)) - a fixed lag flatters a long sample and starves a short one.
    assert fa.hac_lag(n) == expected


def test_hac_errors_are_wider_than_naive_ones_on_autocorrelated_noise(fa) -> None:
    # Strongly autocorrelated residuals are exactly what an ordinary standard error understates,
    # and understating it is what turns noise into a discovery.
    factors = _factors(fa, 900, seed=11)
    rng = random.Random(12)
    drift, series = 0.0, {}
    for day, row in factors.items():
        drift = 0.97 * drift + rng.gauss(0, 0.002)
        series[day] = row["RF"] + drift
    found = fa.attribute(series, factors, 252)
    _, excess, design = fa.align(series, factors)
    import numpy as np

    X = np.column_stack([np.ones(len(excess)), np.asarray(design)])
    y = np.asarray(excess)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    naive = float(np.sqrt((resid @ resid) / (len(y) - X.shape[1])
                          * np.linalg.pinv(X.T @ X)[0, 0]))
    hac = abs(found.alpha_a_period / found.alpha_t) if found.alpha_t else float("inf")
    assert hac > naive, "Newey-West must not be narrower than the naive error here"

def test_the_newey_west_sandwich_matches_an_independent_implementation(fa) -> None:
    """The module builds `S` with matrix algebra; this builds it with three nested loops.

    Written differently ON PURPOSE. The property "wider than the naive error" is true of several
    WRONG kernels - dropping Bartlett's weight, missing the last lag, or leaving the cross-lag term
    unsymmetrised all make it wider too - so only an independent computation of the same quantity
    pins it.
    """
    import numpy as np

    rng = random.Random(21)
    n, k = 80, 2
    design = [[rng.gauss(0, 0.01) for _ in range(k)] for _ in range(n)]
    excess = [0.0004 + 0.7 * row[0] - 0.2 * row[1] + rng.gauss(0, 0.003) for row in design]

    beta, errors, _ = fa.regress(excess, design)

    X = np.column_stack([np.ones(n), np.asarray(design)])
    y = np.asarray(excess)
    resid = y - X @ np.asarray(beta)
    lag = fa.hac_lag(n)

    width = k + 1
    s = [[0.0] * width for _ in range(width)]
    for i in range(width):
        for j in range(width):
            total = sum(X[t, i] * resid[t] * X[t, j] * resid[t] for t in range(n))
            for step in range(1, lag + 1):
                weight = 1.0 - step / (lag + 1.0)
                forward = sum(X[t, i] * resid[t] * X[t - step, j] * resid[t - step]
                              for t in range(step, n))
                backward = sum(X[t - step, i] * resid[t - step] * X[t, j] * resid[t]
                               for t in range(step, n))
                total += weight * (forward + backward)
            s[i][j] = total

    inv = np.linalg.pinv(X.T @ X)
    expected = np.sqrt(np.diag(inv @ np.asarray(s) @ inv))
    assert errors == pytest.approx(list(map(float, expected)), rel=1e-9)


def test_the_bartlett_weight_falls_with_the_lag(fa) -> None:
    # A property the loop version above would share with a constant weight, stated separately so
    # the intent is visible: lag 1 counts for more than lag L, and lag L+1 counts for nothing.
    lag = fa.hac_lag(500)
    weights = [1.0 - step / (lag + 1.0) for step in range(1, lag + 1)]
    assert weights == sorted(weights, reverse=True)
    assert weights[-1] > 0 and 1.0 - (lag + 1) / (lag + 1.0) == 0.0
