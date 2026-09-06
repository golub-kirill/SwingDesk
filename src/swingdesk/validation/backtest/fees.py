"""What the VENUE bills, as opposed to what the broker charges. `DR-039`.

`costs.py` models a commission and a slippage — a broker's price for a service. These are different
animals: **regulators set them, they fall asymmetrically, and they change on a calendar nobody here
controls.** `costs.CostModel` can express none of that, which is why this is a separate module
rather than two more fields on it.

**Three fees, from Alpaca Clearing's own Brokerage Fee Schedule** (template updated 2026-09-01),
which is the document that bills. `DR-039` §9 records why that distinction earned its own section:
the record was first written from FINRA's and the SEC's pages, and the broker's schedule disagreed.

| | rate | side | of what |
|---|---|---|---|
| SEC transaction fee | `0.0000206 × value` | **sell only** | proceeds |
| FINRA TAF | `0.000195 / share`, max `$9.79` per TRADE | **sell only** | shares |
| FINRA CAT | `0.000003 / equivalent share` | **both** | shares, `× 0.01` for OTC |

**THE RATES ARE EFFECTIVE-DATED AND `rates_on` REFUSES OUTSIDE THE RANGE.** Section 31 was
**$0.00 per million until 2026-04-04**. A backtest over 2016–2026 charging today's rate across the
whole window would be arithmetically consistent everywhere and wrong throughout, and `DR-039` §6
could only warn about that. Refusing makes it impossible instead — `AGENTS.md` §3, *missing data
yields a coded refusal, never a guess*, and the guess here would be silent and confident.

**The table is DATA, in `registry/fee_schedule.yml`.** Two reasons and neither is tidiness. Gate 7
enforces `REQ-DATA-001` — no event date as a literal in executable code — and an effective date is
exactly that; the gate's own remedy is *"read it from the calendar, the store or a parameter"*. And
gate 22's argument for the directory policy transfers whole: *"A limit in a literal is changed by
editing a line. A limit here is changed by a commit a gate reads and a reviewer sees."* When a rate
moves, that file gains an entry and nothing here changes.

**Nothing in this module reads that file.** `load_schedule` is the only function that touches disk
and no other function calls it: a caller loads a schedule and passes it in. That is `costs.py`'s
standing rule — *"a study pins its own values and records them"* — and it matters more here, because
a rate that moved underneath a finished study would change its meaning without changing its text.

**Charged PER DAY, not per trade, and that is the schedule's own rule** (page 4, verbatim):

    Fees are calculated on the exact executed quantity, including fractional shares, with no
    rounding of share quantity. Each fee type is aggregated separately at the daily, per-account
    level. After aggregation, each fee total is rounded up to the nearest cent $0.01.

Summing per-trade fees over-charges every day holding more than one trade, because each trade's
sub-cent amount would round up separately. `test_fees.py` pins that difference at a factor of ten
rather than describing it.

**NOT WIRED INTO ANY STUDY.** `DR-039` is `proposed`. Charging these would change what a backtest
computes, which is a separate decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

__all__ = [
    "DEFAULT_SCHEDULE_PATH",
    "FeeRefusal",
    "RegulatoryRates",
    "Sale",
    "Schedule",
    "day_fees",
    "load_schedule",
    "rates_on",
]

#: Where the committed schedule lives. Passed to `load_schedule`, never read implicitly.
DEFAULT_SCHEDULE_PATH = Path("registry/fee_schedule.yml")


@dataclass(frozen=True, slots=True)
class FeeRefusal:
    """No fee is charged and the reason says why.

    Never a zero. A zero reads as *this trade was free*, which is a different claim from *this
    project cannot price that session* — and only one of them is true outside the schedule's range.
    """

    code: str
    reason: str

    def __str__(self) -> str:
        return f"{self.code}: {self.reason}"


@dataclass(frozen=True, slots=True)
class RegulatoryRates:
    """One schedule, in force from `effective` until a later entry supersedes it."""

    effective: date
    sec_rate_on_value: Decimal
    taf_per_share: Decimal
    taf_max_per_trade: Decimal
    cat_per_equivalent_share: Decimal

    def __post_init__(self) -> None:
        for name in ("sec_rate_on_value", "taf_per_share", "cat_per_equivalent_share"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.taf_max_per_trade <= 0:
            raise ValueError("taf_max_per_trade must be > 0")


@dataclass(frozen=True, slots=True)
class Schedule:
    """Every rate set this project can serve, plus the constants that span all of them."""

    rates: tuple[RegulatoryRates, ...]
    otc_cat_equivalence: Decimal
    source: str

    def __post_init__(self) -> None:
        if not self.rates:
            raise ValueError("a schedule with no rates can price nothing; it would refuse always")


@dataclass(frozen=True, slots=True)
class Sale:
    """One executed sale. Both quantities are needed: TAF is per share, the SEC fee is per dollar."""

    proceeds: Decimal
    shares: Decimal

    def __post_init__(self) -> None:
        if self.proceeds < 0 or self.shares < 0:
            raise ValueError("a sale cannot have negative proceeds or shares")


def load_schedule(path: Path = DEFAULT_SCHEDULE_PATH) -> Schedule:
    """Read the committed schedule. The ONLY function here that touches disk, and nothing calls it.

    A caller loads once and passes the result, so a study records which schedule it ran against
    instead of inheriting whatever the file says the day someone re-reads it.
    """
    import yaml

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    rates = tuple(
        RegulatoryRates(
            effective=entry["effective"],
            sec_rate_on_value=Decimal(str(entry["sec_rate_on_value"])),
            taf_per_share=Decimal(str(entry["taf_per_share"])),
            taf_max_per_trade=Decimal(str(entry["taf_max_per_trade"])),
            cat_per_equivalent_share=Decimal(str(entry["cat_per_equivalent_share"])),
        )
        for entry in document["schedules"]
    )
    return Schedule(
        rates=tuple(sorted(rates, key=lambda entry: entry.effective)),
        otc_cat_equivalence=Decimal(str(document["otc_cat_equivalence"])),
        source=str(document["source"]),
    )


def _up(amount: Decimal) -> Decimal:
    """Round UP to the cent. The schedule's word, and it applies to a DAY's total, not a trade's."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_CEILING)


def rates_on(session: date, schedule: Schedule) -> RegulatoryRates | FeeRefusal:
    """The rates in force on `session`, or a refusal naming the range the schedule covers.

    **Refusing is the whole point of the function.** The alternative — returning the newest rates for
    any date — is what makes a 2016 backtest silently charge a 2026 fee, and no test would see it
    because the arithmetic would be perfectly consistent.
    """
    applicable = [rates for rates in schedule.rates if rates.effective <= session]
    if not applicable:
        earliest = min(rates.effective for rates in schedule.rates)
        return FeeRefusal(
            "DATA",
            f"no regulatory fee schedule is known for {session.isoformat()}; this one starts at "
            f"{earliest.isoformat()} and the rates before it are not recorded anywhere in this "
            f"project (DR-039). Charging the current rate backwards would be a guess",
        )
    return max(applicable, key=lambda rates: rates.effective)


def day_fees(
    session: date,
    schedule: Schedule,
    *,
    sales: tuple[Sale, ...] = (),
    shares_bought: Decimal = Decimal(0),
    otc: bool = False,
) -> dict[str, Decimal] | FeeRefusal:
    """One session's regulatory fees for one account, by fee type.

    Aggregated per fee type across the whole day and rounded up ONCE, which is the schedule's rule
    and not a simplification. `shares_bought` is separate because CAT is the only fee a buy pays.

    Returns cents per fee type. A caller wanting one number sums them; the rounding has already
    happened, and rounding a sum of rounded values would charge a second time.
    """
    rates = rates_on(session, schedule)
    if isinstance(rates, FeeRefusal):
        return rates

    sold_shares = sum((sale.shares for sale in sales), Decimal(0))
    proceeds = sum((sale.proceeds for sale in sales), Decimal(0))

    # TAF's cap is PER TRADE, so it binds before the day is aggregated. Capping the day's total
    # instead would under-charge an account that made several trades at size.
    taf_raw = sum(
        (min(sale.shares * rates.taf_per_share, rates.taf_max_per_trade) for sale in sales),
        Decimal(0),
    )

    equivalence = schedule.otc_cat_equivalence if otc else Decimal(1)
    cat_shares = (sold_shares + shares_bought) * equivalence

    return {
        "sec": _up(proceeds * rates.sec_rate_on_value),
        "taf": _up(taf_raw),
        "cat": _up(cat_shares * rates.cat_per_equivalent_share),
    }
