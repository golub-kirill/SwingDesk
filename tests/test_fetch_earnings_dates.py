"""Which EDGAR filings count as a results announcement - the part of the fetch that is a rule."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import fetch_earnings_dates as fetch  # noqa: E402


def _block(*rows: tuple[str, str, str, str]) -> dict[str, list[str]]:
    """A `filings.recent` block: form, items, accepted, filed - column-wise, as EDGAR serves it."""
    return {
        "form": [r[0] for r in rows], "items": [r[1] for r in rows],
        "acceptanceDateTime": [r[2] for r in rows], "filingDate": [r[3] for r in rows],
        "accessionNumber": [f"acc-{i}" for i in range(len(rows))],
    }


def test_only_an_8k_carrying_item_2_02_is_an_announcement() -> None:
    block = _block(
        ("8-K", "2.02,9.01", "2024-05-02T20:30:00.000Z", "2024-05-02"),
        ("8-K", "5.02,9.01", "2024-05-10T20:30:00.000Z", "2024-05-10"),   # an executive leaving
        ("8-K/A", "2.02", "2024-05-12T20:30:00.000Z", "2024-05-12"),      # a correction
        ("10-Q", "", "2024-05-03T20:30:00.000Z", "2024-05-03"),
        ("8-K", "12.02", "2024-06-01T20:30:00.000Z", "2024-06-01"),       # not 2.02 by substring
    )
    found = fetch.results_filings(block)
    assert [f["accepted"] for f in found] == ["2024-05-02T20:30:00.000Z"]


def test_a_block_with_no_items_column_yields_nothing_rather_than_failing() -> None:
    block = _block(("8-K", "", "2024-05-02T20:30:00.000Z", "2024-05-02"))
    del block["items"]
    assert fetch.results_filings(block) == []


def test_the_ticker_map_is_keyed_as_the_store_spells_a_ticker() -> None:
    payload = {"0": {"cik_str": 1067983, "ticker": "BRK-B", "title": "BERKSHIRE"},
               "1": {"cik_str": 320193, "ticker": "aapl", "title": "Apple"}}
    assert fetch.ticker_map(payload) == {"BRK-B": 1067983, "AAPL": 320193}


def test_no_contact_is_invented(monkeypatch) -> None:
    monkeypatch.delenv("SWINGDESK_EDGAR_CONTACT", raising=False)
    assert fetch.user_agent().endswith("(contact not configured)")
