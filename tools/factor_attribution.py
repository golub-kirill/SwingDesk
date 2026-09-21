"""Is the return skill, or is it a factor this project could have bought for nothing?

**The gap `DR-047` left open, and the owner named it.** §3.4 requires four curves, and the fourth -
`SPY` matched to the strategy's own volatility - answers *"am I paid for skill or for exposure"*
only against the MARKET. It says nothing about size, value, profitability, investment or momentum.
A book of small profitable winners can beat volatility-matched `SPY` for years while owning nothing
but well-known factor tilts, and this project would have called that skill.

**So a study now reports alpha from a six-factor regression**, and `DR-049` makes it a curve rather
than a diagnostic:

    r_strategy - RF  =  alpha + b1*(Mkt-RF) + b2*SMB + b3*HML + b4*RMW + b5*CMA + b6*MOM + e

**The factors are free**, which is why this could become a rule rather than a wish: Kenneth
French's data library serves the five factors and momentum as daily and monthly series back to
1963 and 1926, at no cost and with no registration (`tools/fetch_factors.py`).

**Three things that are easy to get wrong and are handled here rather than in a caller:**

1. **French publishes PERCENT.** `-0.67` is −0.67%, not −67%. Every value is divided by 100 on the
   way in, once, at the edge.
2. **The regression is on EXCESS return.** `RF` is subtracted from the strategy before anything
   else, because an alpha measured against a raw return silently includes the risk-free rate.
3. **Daily returns are autocorrelated and heteroskedastic**, so an ordinary standard error
   overstates significance. The errors here are Newey-West with the conventional
   `floor(4*(n/100)^(2/9))` lag, and the t-statistic reported is the one that survives it.

**What it cannot do**, said out loud so no reader over-reads an alpha: six factors are not every
factor, the library's own series ends about two months behind the present, and a regression over a
short window has wide errors whatever its point estimate says. The interval is what this reports;
the point estimate is not the finding.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

#: The six, in the order the report prints them. `Mkt-RF` first because it is the one a
#: volatility-matched benchmark already covered - the other five are what `DR-047` was blind to.
FACTORS: tuple[str, ...] = ("Mkt-RF", "SMB", "HML", "RMW", "CMA", "MOM")

#: French publishes returns as percent. Applied once, at the edge, and never again.
PERCENT = 100.0

#: Newey and West's conventional lag, and it is a FUNCTION of the sample rather than a constant:
#: a fixed lag flatters a long sample and starves a short one.
def hac_lag(n: int) -> int:
    return max(1, math.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))) if n > 1 else 1


@dataclass(frozen=True)
class Attribution:
    """What a factor regression found, in the units a reader needs."""

    periods: int
    periods_a_year: int
    alpha_a_period: float
    alpha_annual: float
    alpha_t: float
    betas: dict[str, float]
    betas_t: dict[str, float]
    r_squared: float
    hac_lag: int
    first: date | None
    last: date | None

    @property
    def alpha_survives(self) -> bool:
        """`|t| > 1.96` on the Newey-West error - the two-sided 5% test, and nothing softer."""
        return abs(self.alpha_t) > 1.96

    def as_dict(self) -> dict[str, Any]:
        return {
            "periods": self.periods, "periods_a_year": self.periods_a_year,
            "alpha_a_period": self.alpha_a_period, "alpha_annual": self.alpha_annual,
            "alpha_t": self.alpha_t, "alpha_survives": self.alpha_survives,
            "betas": self.betas, "betas_t": self.betas_t, "r_squared": self.r_squared,
            "hac_lag": self.hac_lag,
            "first": self.first.isoformat() if self.first else None,
            "last": self.last.isoformat() if self.last else None,
        }


def to_fraction(row: Mapping[str, float]) -> dict[str, float]:
    """One factor row from percent to fraction. The only place the division happens."""
    return {key: value / PERCENT for key, value in row.items()}


def read_day(token: str) -> date:
    """`20260731` or `202607`. A monthly row is dated by the month's LAST day, not its first.

    Dated by the last day because a monthly factor return is earned OVER the month and is known at
    its end, and a study that joins on the first would attribute January's strategy return to
    December's factors.
    """
    # `date(...)` from the parsed pieces rather than `strptime().date()`: a factor row carries a
    # calendar date and no time at all, so constructing a datetime only to discard it invents a
    # midnight in an unstated zone.
    year, month = int(token[:4]), int(token[4:6])
    if len(token) == 8:
        return date(year, month, int(token[6:8]))
    following = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return date.fromordinal(following.toordinal() - 1)


def load(path: Path) -> dict[date, dict[str, float]]:
    """A stored factor file, converted to fractions on the way out.

    The store holds the library's own percentages; every caller sees fractions, and the division
    happens here so no study can forget it. A row with a blank or `-99.99` field - the library's
    own missing marker - is dropped rather than regressed on.
    """
    out: dict[date, dict[str, float]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            token = (row.get("date") or "").strip()
            if not token:
                continue
            values: dict[str, float] = {}
            for name in (*FACTORS, "RF"):
                text = (row.get(name) or "").strip()
                if not text or text.startswith("-99.99") or text.startswith("-999"):
                    values = {}
                    break
                values[name] = float(text)
            if values:
                out[read_day(token)] = to_fraction(values)
    return out


def align(strategy: Mapping[date, float],
          factors: Mapping[date, Mapping[str, float]],
          names: Sequence[str] = FACTORS
          ) -> tuple[list[date], list[float], list[list[float]]]:
    """The periods BOTH sides have, with the strategy's excess return beside the factors.

    An inner join and never a fill: a factor library that ends two months short must shorten the
    regression rather than have its last value carried forward, and a strategy period with no
    factor row is a period this cannot attribute.
    """
    shared = sorted(day for day in strategy if day in factors)
    days: list[date] = []
    excess: list[float] = []
    design: list[list[float]] = []
    for day in shared:
        row = factors[day]
        if any(name not in row for name in names) or "RF" not in row:
            continue
        days.append(day)
        excess.append(strategy[day] - row["RF"])
        design.append([row[name] for name in names])
    return days, excess, design


def regress(excess: Sequence[float], design: Sequence[Sequence[float]]
            ) -> tuple[list[float], list[float], float]:
    """Least squares with an intercept, Newey-West errors, and R².

    Returns `(coefficients, standard_errors, r_squared)` with the intercept first. `lstsq` rather
    than the normal equations because a six-factor design is correlated enough that inverting
    `X'X` directly loses digits for no reason.
    """
    y = np.asarray(excess, dtype=float)
    x = np.asarray(design, dtype=float)
    n = len(y)
    if n <= x.shape[1] + 1:
        raise ValueError(f"{n} periods cannot fit {x.shape[1] + 1} coefficients")
    X = np.column_stack([np.ones(n), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta

    xtx_inv = np.linalg.pinv(X.T @ X)
    lag = hac_lag(n)
    # Newey-West: the white-noise term, then each lag down-weighted by Bartlett's kernel, which is
    # what keeps the estimate positive semi-definite.
    s = (X * resid[:, None]).T @ (X * resid[:, None])
    for step in range(1, lag + 1):
        weight = 1.0 - step / (lag + 1.0)
        a = (X[step:] * resid[step:, None]).T @ (X[:-step] * resid[:-step, None])
        s += weight * (a + a.T)
    cov = xtx_inv @ s @ xtx_inv
    errors = np.sqrt(np.maximum(np.diag(cov), 0.0))

    centred = y - y.mean()
    total = float(centred @ centred)
    r2 = 1.0 - float(resid @ resid) / total if total > 0 else float("nan")
    return list(map(float, beta)), list(map(float, errors)), r2


def attribute(strategy: Mapping[date, float],
              factors: Mapping[date, Mapping[str, float]],
              periods_a_year: int,
              names: Sequence[str] = FACTORS) -> Attribution:
    """The whole answer: alpha, its t-statistic, the six betas, and what was actually regressed."""
    days, excess, design = align(strategy, factors, names)
    beta, errors, r2 = regress(excess, design)
    alpha = beta[0]
    return Attribution(
        periods=len(days), periods_a_year=periods_a_year,
        alpha_a_period=alpha,
        # Compounded, not multiplied: an alpha is a return and returns compound. A study that
        # reports `alpha * 252` overstates a positive one and understates a negative one.
        alpha_annual=(1.0 + alpha) ** periods_a_year - 1.0,
        alpha_t=alpha / errors[0] if errors[0] > 0 else float("nan"),
        betas=dict(zip(names, beta[1:], strict=True)),
        betas_t=dict(zip(names, [b / e if e > 0 else float("nan")
                                 for b, e in zip(beta[1:], errors[1:], strict=True)], strict=True)),
        r_squared=r2, hac_lag=hac_lag(len(days)),
        first=days[0] if days else None, last=days[-1] if days else None,
    )


def report(found: Attribution) -> None:
    print(f"  factor attribution   {found.periods} periods"
          f"   {found.first} .. {found.last}   HAC lag {found.hac_lag}")
    verdict = "SURVIVES" if found.alpha_survives else "does not survive"
    print(f"    alpha {100 * found.alpha_annual:+.2f}% a year   t {found.alpha_t:+.2f}"
          f"   -> {verdict} the six factors")
    print("    " + "  ".join(f"{name} {found.betas[name]:+.2f}(t{found.betas_t[name]:+.1f})"
                             for name in found.betas))
    print(f"    R2 {found.r_squared:.3f}")
