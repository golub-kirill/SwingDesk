"""The current market regime, as a label with a threshold that was fitted before it was applied.

Course grounding: M30-T0450 `Определение текущего режима`, Definition, Derived Observations layer.
The course defines a regime as `сочетание направления, breadth и volatility` and names no indicator,
no threshold and no count of regimes. Everything numeric here is authored, and PR-002 is the study
that would say whether any of it carries information.

The topic's own standard is the constraint worth keeping visible:

    "Инструмент используется как измеритель, а не как источник уверенности. Параметры фиксируются
    версией стратегии, а добавленная ценность проверяется против простой базовой модели."

A gauge, not a source of confidence; and the added value is checked against a simple baseline model.
PR-002's random-partition baseline is that requirement, not an invention.

**Thresholds are fitted once and then frozen.** `fit` takes a training window and returns a
classifier; `label` applies it forward. A tercile boundary computed over the whole sample is a label
that read the future, and "regimes are identifiable in hindsight and not in advance" is precisely
the null PR-002 exists to test. Splitting fit from apply is what makes that test meaningful rather
than circular.

Pure. No I/O, no clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from swingdesk.contracts.component import ComponentSpec

SPEC = ComponentSpec(
    component="M30-T0450-v5.0", name="Current regime", version=1,
    validation="Not Applicable", units="label",
)
SPECS = (SPEC,)

COMPONENT = SPEC.component
VERSION = SPEC.version
VALIDATION = SPEC.validation
UNITS = SPEC.units


class Variant(StrEnum):
    """The four candidates PR-002 registered. Not a menu to be extended after seeing results."""

    BREADTH_TERCILE = "BREADTH_TERCILE"
    BREADTH_MEDIAN = "BREADTH_MEDIAN"
    VOL_TERCILE = "VOL_TERCILE"
    BREADTH_X_VOL = "BREADTH_X_VOL"


class UnfittedClassifier(Exception):
    """Raised when a variant is asked to label without a training window.

    A coded refusal rather than a default threshold: a classifier that invents its own boundary is
    a classifier fitted on whatever it happens to be looking at.
    """


def _percentile(values: list[Decimal], fraction: Decimal) -> Decimal:
    """Nearest-rank, same estimator as the overlap study. Stated because it is a choice."""
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, round(float(fraction) * (len(ordered) - 1))))
    return ordered[int(rank)]


@dataclass(frozen=True, slots=True)
class Classifier:
    """A fitted variant: the thresholds, frozen, plus the window they came from."""

    variant: Variant
    breadth_cuts: tuple[Decimal, ...] = ()
    volatility_cuts: tuple[Decimal, ...] = ()
    fitted_on: int = 0

    @property
    def regimes(self) -> tuple[str, ...]:
        match self.variant:
            case Variant.BREADTH_TERCILE:
                return ("BREADTH_LOW", "BREADTH_MID", "BREADTH_HIGH")
            case Variant.BREADTH_MEDIAN:
                return ("BREADTH_LOW", "BREADTH_HIGH")
            case Variant.VOL_TERCILE:
                return ("VOL_LOW", "VOL_MID", "VOL_HIGH")
            case Variant.BREADTH_X_VOL:
                return ("QUIET_WEAK", "QUIET_STRONG", "LOUD_WEAK", "LOUD_STRONG")
        raise ValueError(f"unhandled variant {self.variant!r}")

    def label(self, breadth: Decimal | None, volatility: Decimal | None) -> str | None:
        """The regime for one session, or None when an input is missing.

        None is not a regime. A session the classifier cannot label is excluded from the study
        rather than assigned a default one, for the same reason an undecided trend verdict is not
        a rejection.
        """
        if not self.fitted_on:
            raise UnfittedClassifier(
                f"{self.variant} has no thresholds; fit it on a training window first"
            )

        match self.variant:
            case Variant.BREADTH_TERCILE:
                if breadth is None:
                    return None
                low, high = self.breadth_cuts
                if breadth <= low:
                    return "BREADTH_LOW"
                return "BREADTH_HIGH" if breadth > high else "BREADTH_MID"

            case Variant.BREADTH_MEDIAN:
                if breadth is None:
                    return None
                return "BREADTH_HIGH" if breadth > self.breadth_cuts[0] else "BREADTH_LOW"

            case Variant.VOL_TERCILE:
                if volatility is None:
                    return None
                low, high = self.volatility_cuts
                if volatility <= low:
                    return "VOL_LOW"
                return "VOL_HIGH" if volatility > high else "VOL_MID"

            case Variant.BREADTH_X_VOL:
                if breadth is None or volatility is None:
                    return None
                loud = volatility > self.volatility_cuts[0]
                strong = breadth > self.breadth_cuts[0]
                if loud:
                    return "LOUD_STRONG" if strong else "LOUD_WEAK"
                return "QUIET_STRONG" if strong else "QUIET_WEAK"

        raise ValueError(f"unhandled variant {self.variant!r}")


def fit(
    variant: Variant,
    breadth: list[Decimal | None],
    volatility: list[Decimal | None],
) -> Classifier:
    """Fit thresholds on a training window. The window is the caller's to choose and to record."""
    usable_breadth = [value for value in breadth if value is not None]
    usable_volatility = [value for value in volatility if value is not None]

    third, two_thirds, half = Decimal("0.3333"), Decimal("0.6667"), Decimal("0.5")

    match variant:
        case Variant.BREADTH_TERCILE:
            if len(usable_breadth) < 3:
                raise ValueError("not enough breadth observations to fit terciles")
            cuts = (_percentile(usable_breadth, third), _percentile(usable_breadth, two_thirds))
            return Classifier(variant, breadth_cuts=cuts, fitted_on=len(usable_breadth))

        case Variant.BREADTH_MEDIAN:
            if len(usable_breadth) < 2:
                raise ValueError("not enough breadth observations to fit a median")
            return Classifier(
                variant, breadth_cuts=(_percentile(usable_breadth, half),),
                fitted_on=len(usable_breadth),
            )

        case Variant.VOL_TERCILE:
            if len(usable_volatility) < 3:
                raise ValueError("not enough volatility observations to fit terciles")
            cuts = (
                _percentile(usable_volatility, third),
                _percentile(usable_volatility, two_thirds),
            )
            return Classifier(variant, volatility_cuts=cuts, fitted_on=len(usable_volatility))

        case Variant.BREADTH_X_VOL:
            if len(usable_breadth) < 2 or len(usable_volatility) < 2:
                raise ValueError("not enough observations to fit both medians")
            return Classifier(
                variant,
                breadth_cuts=(_percentile(usable_breadth, half),),
                volatility_cuts=(_percentile(usable_volatility, half),),
                fitted_on=min(len(usable_breadth), len(usable_volatility)),
            )

    raise ValueError(f"unhandled variant {variant!r}")


def label_changes(labels: list[str | None]) -> int:
    """How often the label flips across a window, ignoring gaps.

    PR-002's selection rule: among variants, choose the one whose assignment is most STABLE on the
    validation window - fewest changes per unit time - and explicitly NOT the one with the largest
    outcome difference. Selecting on the outcome would be the study answering its own question.
    """
    changes = 0
    previous: str | None = None
    for current in labels:
        if current is None:
            continue
        if previous is not None and current != previous:
            changes += 1
        previous = current
    return changes
