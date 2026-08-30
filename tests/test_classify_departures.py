"""Classifying a directory departure: delisting, rename, or an answer this route cannot give.

`DR-008` c3 records the ambiguity: *"a departure is an observation, not a delisting - a ticker
change looks the same"*. These tests pin the decision logic, which is the part that can be wrong
quietly — the network half is exercised by running the tool.

**The case that matters most is `test_a_ticker_still_listed_at_edgar_is_NOT_called_survival`.**
Measured 2026-08-25 over 87 real departures: 34 of the 36 resolvable names still carried their
departed ticker in EDGAR's metadata while being absent from the vendor's live directory. The
metadata lags. A classifier that read a present ticker as "still trading" would report survival for
names that had delisted the previous week, and the survivorship bound would be understated in the
flattering direction — which is the exact error `EVIDENCE_SUMMARY.md` §3 exists to prevent.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import classify_departures as cd

WINDOW = (date(2026, 8, 3), date(2026, 8, 24))
CIK = {"AVB": 915912, "TALK": 1803901, "BNZI": 1826011}


def _record(*, name="Example Inc", tickers=(), exchanges=(), forms=()):
    """A `submissions/CIK….json` shaped enough for `classify` to judge."""
    return {
        "name": name,
        "tickers": list(tickers),
        "exchanges": list(exchanges),
        "filings": {"recent": {
            "form": [form for form, _ in forms],
            "filingDate": [filed for _, filed in forms],
        }},
    }


@pytest.fixture
def edgar(monkeypatch):
    """Replace the network with a dict, so the decision logic is what is under test."""
    responses: dict[str, dict] = {}

    def fake_get(url: str):
        return responses.get(url)

    monkeypatch.setattr(cd, "_get", fake_get)
    return responses


def _submissions(cik: int) -> str:
    return cd.SUBMISSIONS.format(cik=cik)


# ---------------------------------------------------------------- structured symbols


@pytest.mark.parametrize("symbol", ["BBBY.W", "AXIA$C", "MUA.V", "SES.W"])
def test_a_structured_symbol_is_counted_apart_and_costs_no_request(symbol, edgar) -> None:
    """Warrants, units, rights and classes depart on SEPARATION, not on any corporate failure.

    `DR-003` records them as systematically preferred shares and units rather than a random slice,
    so folding them into a delisting rate inflates it with events that are not delistings. `edgar`
    is left empty on purpose: reaching the network here would be a wasted request and the empty
    stub proves none is made.
    """
    result = cd.classify(symbol, CIK, WINDOW)
    assert result["verdict"] == "structured"


# ---------------------------------------------------------------- the timely discriminator


def test_a_form_25_inside_the_window_is_a_delisting(edgar) -> None:
    """The discriminator that IS timely: the form date lands on the pull the symbol vanished at.

    `AVB` left between the 08-14 and 08-17 pulls and filed on 08-17.
    """
    edgar[_submissions(CIK["AVB"])] = _record(
        name="AVALONBAY COMMUNITIES INC", tickers=["AVB"], exchanges=["NYSE"],
        forms=[("25-NSE", "2026-08-17")],
    )
    result = cd.classify("AVB", CIK, WINDOW)
    assert result["verdict"] == "delisted"
    assert "2026-08-17" in str(result["why"])


def test_a_form_25_OUTSIDE_the_window_does_not_make_a_delisting(edgar) -> None:
    """`probe_edgar.py`'s control: Apple files Form 25s to retire individual securities and is
    listed. An old notice says nothing about a departure that happened this month."""
    edgar[_submissions(CIK["TALK"])] = _record(
        tickers=["TALK"], exchanges=["Nasdaq"], forms=[("25-NSE", "2021-06-22")],
    )
    result = cd.classify("TALK", CIK, WINDOW)
    assert result["verdict"] != "delisted"


def test_a_ticker_still_listed_at_edgar_is_NOT_called_survival(edgar) -> None:
    """The lag, and the reason this classifier does not read a present ticker as "still trading".

    34 of 36 resolvable departures looked exactly like this on 2026-08-25 while being absent from
    the vendor's live directory. Reading it as survival would understate the survivorship exposure
    in the flattering direction.
    """
    edgar[_submissions(CIK["TALK"])] = _record(tickers=["TALK"], exchanges=["Nasdaq"])
    result = cd.classify("TALK", CIK, WINDOW)
    assert result["verdict"] == "still listed at EDGAR"
    assert "lags" in str(result["why"]), "the verdict must carry the caveat, not just the label"


# ---------------------------------------------------------------- the other verdicts


def test_a_filer_with_no_ticker_at_all_is_delisted(edgar) -> None:
    """`EQR` reports exactly this. It is the discriminator `probe_edgar.py` validated on a 2024
    delisting, and it stays correct - it is only the TIMELINESS that fails at short horizons."""
    edgar[_submissions(CIK["AVB"])] = _record(tickers=[], exchanges=[])
    assert cd.classify("AVB", CIK, WINDOW)["verdict"] == "delisted"


def test_a_filer_listing_a_DIFFERENT_ticker_is_a_rename(edgar) -> None:
    """The other half of `DR-008` c3's ambiguity, and the half that is not a delisting at all."""
    edgar[_submissions(CIK["BNZI"])] = _record(tickers=["NEWT"], exchanges=["Nasdaq"])
    result = cd.classify("BNZI", CIK, WINDOW)
    assert result["verdict"] == "renamed"
    assert "NEWT" in str(result["why"])


def test_a_symbol_with_no_CIK_is_UNRESOLVED_and_never_assumed_either_way(edgar) -> None:
    """`unresolved` is a real answer. Forty of the eighty-seven land here, and calling them
    "not delisted" would manufacture survival exactly where the bound is most sensitive."""
    result = cd.classify("NOSUCH", CIK, WINDOW)
    assert result["verdict"] == "unresolved"


def test_an_unreachable_EDGAR_is_unresolved_rather_than_a_verdict(edgar) -> None:
    """A network failure must not be reported as a fact about the world - `AGENTS.md` §12,
    `unavailable` is not `pass`. The stub returns `None`, which is what `_get` returns on failure."""
    result = cd.classify("AVB", CIK, WINDOW)
    assert result["verdict"] == "unresolved"
    assert "unreachable" in str(result["why"]).lower()


def test_the_boundary_dates_of_the_window_are_INSIDE_it(edgar) -> None:
    """A notice filed on the first or last day of the observation window counts.

    Off by one here would silently drop the departures at both ends, which are the ones a reader is
    most likely to check by hand.
    """
    for filed in ("2026-08-03", "2026-08-24"):
        edgar[_submissions(CIK["AVB"])] = _record(
            tickers=["AVB"], exchanges=["NYSE"], forms=[("25-NSE", filed)],
        )
        assert cd.classify("AVB", CIK, WINDOW)["verdict"] == "delisted", filed


def test_a_notice_one_day_outside_the_window_does_not_count(edgar) -> None:
    """The positive control for the boundary above: the window is a window, not a direction."""
    edgar[_submissions(CIK["AVB"])] = _record(
        tickers=["AVB"], exchanges=["NYSE"], forms=[("25-NSE", "2026-08-02")],
    )
    assert cd.classify("AVB", CIK, WINDOW)["verdict"] != "delisted"
