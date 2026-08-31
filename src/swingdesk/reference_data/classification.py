"""What an instrument is made of: sector, industry, and an ETF's look-through (`DR-006` §2, §8.7).

`ALLOCATION_SPEC` §2 has named `risk.max_sector_risk` since it was written and `DR-006` §3 recorded
it as unevaluable, because `Instrument.sector` is `None` and no free point-in-time source was in
hand. §8.4 split that claim in two and only one half survived: `yfinance` - already this project's
only bar vendor - serves sector and industry directly, and `funds_data.sector_weightings` serves an
ETF's composition, which is exactly what Appendix C's control cell requires when it says an ETF must
count toward its constituents' sector. What is genuinely missing is the **point-in-time** version.

**The point-in-time gap is encoded rather than described.** This store is read as-of, so a run
replayed at a date before the first pull finds nothing and reports `unavailable` - which is the
truth. It does not, and must not, answer a 2016 question with today's classification. That restricts
a BACKTEST and does not restrict live admission, and §8.4 d is explicit that conflating the two is
what made §3 read as a blocker.

**And the vendor lies about bond funds, which is why `look_through` exists.** `NEAR` comes back
healthcare 100.0%, every other sector 0.0%; it is a short-maturity bond fund with no equity sectors
at all. Consumed naively, one bond ETF would spend an entire sector budget on a fiction - silently,
which is worse than the check not existing. The guard is a precondition of the sector cap rather
than a refinement of it (§8.7).

Fetching lives in `market_data.vendor_yahoo` and the refresh in `tools/refresh_classifications.py`,
so nothing in this layer reaches the network - the same arrangement `BarStore` has with the bars it
holds.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import duckdb

from swingdesk.contracts.reference import Classification, SectorWeight
from swingdesk.platform import schema

_SCHEMA = """
CREATE TABLE IF NOT EXISTS classifications (
    knowledge_time  TIMESTAMPTZ NOT NULL,
    instrument_id   VARCHAR     NOT NULL,
    quote_type      VARCHAR     NOT NULL,
    industry        VARCHAR,
    -- DR-021. NULLABLE on purpose: every row written before 2026-08-31 has no answer here, and an
    -- unanswered equity share is not a zero one. `look_through` reads only a POSITIVE share as
    -- evidence of equity, so a NULL behaves exactly as the guard did before this column existed.
    equity_share    DECIMAL(9,6),
    PRIMARY KEY (knowledge_time, instrument_id)
);

CREATE TABLE IF NOT EXISTS classification_weights (
    knowledge_time  TIMESTAMPTZ   NOT NULL,
    instrument_id   VARCHAR       NOT NULL,
    sector          VARCHAR       NOT NULL,
    weight          DECIMAL(9,6)  NOT NULL,
    PRIMARY KEY (knowledge_time, instrument_id, sector)
);
"""

#: The vendor kinds whose sectors are a LOOK-THROUGH rather than the instrument's own.
#: `DR-006` §8.7 names "a quoteType that is not an equity fund" as half the guard, and this is the
#: list that decides which half of the guard an answer is judged by.
FUND_KINDS = frozenset({"ETF", "MUTUALFUND"})

#: The eleven sectors this vendor uses, keyed by their separator-free lowercase form.
#:
#: **The vendor spells them TWO different ways and the difference is silent.** Measured across the
#: 68 instruments of `PR-005` on 2026-08-23: an equity comes back `Financial Services`, a fund
#: look-through comes back `financial_services`, and `Real Estate` becomes `realestate` with no
#: separator at all. Both vocabularies hold exactly these eleven and nothing else.
#:
#: Left unmapped, a share and an ETF in the same sector would never add into the same bucket - so
#: `LYV` (Communication Services) and `FCOM` (communication_services) would each get their own
#: budget, and a concentrated book would report as a diversified one. That is the cap failing in
#: the PERMISSIVE direction, silently, which is the failure mode `DR-006` §8.7 was written about
#: one layer up.
SECTOR_LABELS = {
    "basicmaterials": "basic materials",
    "communicationservices": "communication services",
    "consumercyclical": "consumer cyclical",
    "consumerdefensive": "consumer defensive",
    "energy": "energy",
    "financialservices": "financial services",
    "healthcare": "healthcare",
    "industrials": "industrials",
    "realestate": "real estate",
    "technology": "technology",
    "utilities": "utilities",
}


def canonical_sector(label: str) -> str:
    """One spelling per sector, whichever of the vendor's two an answer arrived in.

    Separator-free and lowercase for the lookup, so `Real Estate`, `real_estate` and `realestate`
    are one key. A sector outside the known eleven is lowercased and returned as it came - the
    vendor adding a twelfth must not be dropped on the floor, and a label this table has never seen
    is still a better bucket than no bucket.
    """
    key = "".join(character for character in label.lower() if character.isalnum())
    return SECTOR_LABELS.get(key, label.strip().lower())


class ClassificationStore:
    """Instrument classifications, appended per pull and read as-of a knowledge time.

    Append-only and bitemporal in the same sense `BarStore` is: a reclassification is a new row at a
    later `knowledge_time`, never an update. A sector that changed is a fact worth keeping - it is
    the only evidence this project will ever hold about how its own classification drifted, since
    the vendor publishes a current answer and no archive.

    Read semantics are `BarStore`'s and not `DirectoryStore`'s, deliberately. A directory pull is a
    complete snapshot, so reading "everything known by K" would make a delisting invisible; a
    classification is an independent fact per instrument, and the latest one known at K is exactly
    the right answer for each.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self.path))
        self._connection.execute(_SCHEMA)
        # A store never opens against a schema it cannot serve (`platform/schema.py`).
        schema.reconcile(self._connection, _SCHEMA)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> ClassificationStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ----------------------------------------------------------------- writes

    def record(self, classifications: Iterable[Classification]) -> int:
        """Append classifications, returning how many were written.

        `INSERT OR REPLACE` on the primary key, which is `(knowledge_time, instrument_id)` - so
        re-running a pull at the same instant is idempotent and a pull at a later instant appends a
        new version rather than overwriting the old one.
        """
        written = 0
        for classification in classifications:
            self._connection.execute(
                "INSERT OR REPLACE INTO classifications VALUES (?, ?, ?, ?, ?)",
                [
                    classification.knowledge_time,
                    classification.instrument_id,
                    classification.quote_type,
                    classification.industry,
                    classification.equity_share,
                ],
            )
            # Cleared first: a later pull reporting FEWER sectors must not leave the sectors it
            # dropped standing next to the ones it kept. Same knowledge_time, same answer.
            self._connection.execute(
                "DELETE FROM classification_weights WHERE knowledge_time = ? AND instrument_id = ?",
                [classification.knowledge_time, classification.instrument_id],
            )
            for weight in classification.weights:
                self._connection.execute(
                    "INSERT OR REPLACE INTO classification_weights VALUES (?, ?, ?, ?)",
                    [
                        classification.knowledge_time,
                        classification.instrument_id,
                        weight.sector,
                        weight.weight,
                    ],
                )
            written += 1
        return written

    # ------------------------------------------------------------------ reads

    def as_of(self, instrument_id: str, knowledge_time: datetime) -> Classification | None:
        """The latest classification for one instrument known at `knowledge_time`, or `None`.

        `None` means the store cannot answer - never that the instrument has no sector. The caller
        turns that into `unavailable`, and `unavailable` is not a pass (`AGENTS.md` §12).
        """
        row = self._connection.execute(
            """
            SELECT knowledge_time, quote_type, industry, equity_share
            FROM classifications
            WHERE instrument_id = ? AND knowledge_time <= ?
            ORDER BY knowledge_time DESC
            LIMIT 1
            """,
            [instrument_id, knowledge_time],
        ).fetchone()
        if row is None:
            return None

        learned, quote_type, industry, equity_share = row
        weights = self._connection.execute(
            """
            SELECT sector, weight
            FROM classification_weights
            WHERE instrument_id = ? AND knowledge_time = ?
            ORDER BY sector
            """,
            [instrument_id, learned],
        ).fetchall()
        return Classification(
            instrument_id=instrument_id,
            quote_type=quote_type,
            industry=industry,
            weights=tuple(
                SectorWeight(sector=sector, weight=weight) for sector, weight in weights
            ),
            equity_share=equity_share,
            knowledge_time=learned,
        )

    def instrument_ids(self, knowledge_time: datetime) -> tuple[str, ...]:
        """Every instrument this store can answer for at `knowledge_time`, sorted.

        What a refresh pass needs to report coverage rather than present a partial answer as the
        whole one - the same reason `BarStore.instrument_ids` exists.
        """
        rows = self._connection.execute(
            "SELECT DISTINCT instrument_id FROM classifications WHERE knowledge_time <= ? "
            "ORDER BY 1",
            [knowledge_time],
        ).fetchall()
        return tuple(row[0] for row in rows)


# ------------------------------------------------------------------ the guard


@dataclass(frozen=True, slots=True)
class Exposure:
    """An instrument's sector composition, once the vendor's answer has been judged.

    `weights` empty and `unavailable` set always travel together - either there is a composition to
    spend against a budget, or there is the reason there is not. A consumer reading only `weights`
    cannot mistake a refused look-through for an instrument with no sector exposure, because both
    would be empty and only one is a fact about the instrument.
    """

    instrument_id: str
    weights: tuple[SectorWeight, ...]
    unavailable: str | None = None

    @property
    def is_available(self) -> bool:
        return self.unavailable is None

    @property
    def coverage(self) -> Decimal:
        """The share of the instrument these sectors account for. Below 1 leaves a remainder that
        belongs to no sector and is reported as unclassified rather than spread across the ones
        that were reported."""
        return sum((weight.weight for weight in self.weights), Decimal(0))


def look_through(classification: Classification | None, instrument_id: str) -> Exposure:
    """Judge a vendor classification, or say why it cannot be spent against a sector budget.

    Three refusals, and each is a different fact:

    1. **Nothing stored.** The store has never been asked about this instrument, or was asked only
       after the knowledge time being read at. `unavailable` - the check did not run.
    2. **No sector at all.** The vendor answered and served no sector. Common for an index, a
       warrant, or a name it does not cover.
    3. **A degenerate look-through that the vendor does not say holds equity** (`DR-006` §8.7 as
       amended by `DR-021`). A fund reporting exactly ONE sector at exactly 1 with every other at
       exactly 0 is the `NEAR` signature: a short-maturity bond fund the vendor describes as
       healthcare 100.0%. That SHAPE is the trigger; what settles it is `equity_share`, which the
       vendor serves in the same response. Refused and reported `unavailable`, never consumed.

    **Why the shape alone was not enough, measured.** *"A genuine sector ETF is legitimately almost
    all one sector"* is true, and §8.7 concluded from it that an EXACT test was safe because a real
    single-sector ETF carries a remainder. It does not always: over the SPDR Select Sector family on
    2026-08-30, **five of eleven** report exactly one sector at exactly 100% - `XLC`, `XLE`, `XLV`,
    `XLRE`, `XLU` - and each is 99.7% or more equity. The exact test refused all five for a reason
    that is false for them, and 23 admitted members of the live universe sat in that state.

    **Why the test is still EXACT in both halves.** A tolerance on the sector weight would need a
    number the course does not supply, and it inverts the problem - it would refuse `XLK` at 99.3%
    today and more of the family as they drift. `DR-021` §5 introduces no parameter: the shape must
    be degenerate, and the equity share must be POSITIVELY reported. 0.997 against 0.0 is not a
    close call.

    **`None` is not zero, and the asymmetry is the guard.** An unanswered `equity_share` is a fact
    about the vendor, not about the fund, so it does not clear the refusal. A classification stored
    before that field existed therefore behaves exactly as it did, and this change can only ever
    ADMIT on an affirmative answer - never on silence.

    A partial look-through is NOT refused. Weights summing to less than 1 spend what they report and
    leave the remainder unattributed, because normalising invents composition the vendor did not
    report and dropping the instrument hides exposure that was measured.
    """
    if classification is None:
        return Exposure(
            instrument_id=instrument_id,
            weights=(),
            unavailable=(
                "no classification is stored for this instrument at this knowledge time; the "
                "sector budget could not be measured against it"
            ),
        )

    if not classification.weights or classification.coverage == 0:
        # Every sector at zero is the same non-answer as no sector at all, and it arrives more
        # often - the vendor returns the full sector list with every share zeroed rather than an
        # empty one. Left as "available with zero coverage" it would place none of the position's
        # risk and report the book as complete, which is a fabricated clean bill of health.
        return Exposure(
            instrument_id=instrument_id,
            weights=(),
            unavailable=(
                f"the vendor served no sector for a {classification.quote_type} instrument"
            ),
        )

    # ONE spelling per sector before anything is compared or added. The vendor uses two, and a
    # share and a fund in the same sector would otherwise each get their own budget.
    merged: dict[str, Decimal] = {}
    for weight in classification.weights:
        sector = canonical_sector(weight.sector)
        merged[sector] = merged.get(sector, Decimal(0)) + weight.weight
    contradictory = sorted(sector for sector, share in merged.items() if share > 1)
    if contradictory:
        # Only reachable when the vendor served BOTH spellings of one sector in one answer, which
        # would mean it disagrees with itself about the same fund. Refused rather than clamped:
        # clamping picks a number the vendor never gave, on the one input that proves it is wrong.
        return Exposure(
            instrument_id=instrument_id,
            weights=(),
            unavailable=(
                f"the vendor reported more than 100% in {contradictory[0]}, so its own answer "
                f"about this instrument contradicts itself"
            ),
        )
    canonical = tuple(
        SectorWeight(sector=sector, weight=merged[sector]) for sector in sorted(merged)
    )

    degenerate = (
        _degenerate_sector(canonical)
        if classification.quote_type.upper() in FUND_KINDS
        else None
    )
    # `DR-021`: the shape is the TRIGGER, the vendor's own answer is the DISCRIMINATOR.
    #
    # The shape alone was refusing real sector ETFs. Measured 2026-08-30 over the SPDR Select Sector
    # family, five of eleven report exactly one sector at exactly 100% - `XLC`, `XLE`, `XLV`, `XLRE`
    # and `XLU` - and every one of them is 99.7% or more EQUITY. They were refused with a reason
    # that is false for them, and 23 admitted members of the live universe were in that state.
    #
    # A POSITIVE equity share is the only thing that clears it. `None` does not, and that asymmetry
    # is the whole guard: `NEAR` answers 0.0 and is a bond fund, an unanswered field is a fact about
    # the vendor, and neither is evidence of equity. So a classification stored before this field
    # existed behaves exactly as it did - refused - and the change can only ever ADMIT on an
    # affirmative answer, never on silence.
    holds_equity = classification.equity_share is not None and classification.equity_share > 0
    if degenerate is not None and not holds_equity:
        answered = (
            "the vendor reports 0% equity"
            if classification.equity_share is not None
            else "the vendor did not answer what share is equity, and absence is not evidence of it"
        )
        return Exposure(
            instrument_id=instrument_id,
            weights=(),
            unavailable=(
                f"the look-through is degenerate - {degenerate} at exactly 100% and every other "
                f"sector at exactly 0% - and {answered} (DR-006 8.7, DR-021). Refused rather than "
                f"consumed"
            ),
        )

    # Already sorted by sector above, because these feed a decision reason and an unordered
    # iteration reaching output is the named determinism hazard (`DETERMINISM_SPEC` §3.2).
    return Exposure(instrument_id=instrument_id, weights=canonical)


def _degenerate_sector(weights: Sequence[SectorWeight]) -> str | None:
    """The sector at exactly 1 when every other is exactly 0, else `None` - the `NEAR` signature."""
    full = [weight for weight in weights if weight.weight == 1]
    rest = [weight for weight in weights if weight.weight != 1]
    if len(full) == 1 and all(weight.weight == 0 for weight in rest):
        return full[0].sector
    return None
