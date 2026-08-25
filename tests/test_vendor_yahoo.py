"""The vendor boundary drops rows it cannot validate, and it must say so.

**What paid for this, 2026-08-24.** The scheduled run left 86 of 1,141 admitted candidates on
`Skip`/`DATA`, *"one session behind"* - and the report said `completeness clean` for every one of
them. It could say both because they are not the same claim: `DR-015` §2.2 established that
completeness looks for a hole INSIDE the stored window, and a series whose newest row never arrived
simply ends early, which is not a hole.

`fetch`'s own comment asserted the opposite - that a dropped row *"then fails the completeness
check, which is the correct place for it to surface"*. Nothing tested that sentence and it was
false, so a row the vendor sent and this adapter refused was indistinguishable from a row the vendor
never sent. Those are different problems: one is ours, one is theirs.

The fake vendor below is a module substituted into `sys.modules`, because `fetch` does its
`import yfinance` inside the function - which is what makes it substitutable without a plugin seam.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from decimal import Decimal
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest

from swingdesk.contracts.market import Interval
from swingdesk.contracts.reference import Exchange, Instrument
from swingdesk.market_data import vendor_yahoo

KNOWN_AT = datetime(2026, 8, 24, 23, 31, tzinfo=UTC)


def _instrument() -> Instrument:
    """`TEST.1` per `AGENTS.md` §5 - a test instrument is never a real ticker."""
    return Instrument(id="TEST.1", ticker="TEST.1", exchange=Exchange.NYSE, currency="USD")


def _frame(rows: list[dict]) -> pd.DataFrame:
    index = pd.DatetimeIndex([r.pop("when") for r in rows], tz="America/New_York")
    return pd.DataFrame(rows, index=index)


def _install(monkeypatch: pytest.MonkeyPatch, frame: pd.DataFrame) -> None:
    """Substitute a `yfinance` whose `Ticker(...).history(...)` returns exactly `frame`."""
    fake = ModuleType("yfinance")
    fake.Ticker = lambda symbol: SimpleNamespace(history=lambda **kwargs: frame)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yfinance", fake)


def _row(when: str, *, volume: object = 1_000, close: object = 10.0) -> dict:
    return {"when": when, "Open": 10.0, "High": 11.0, "Low": 9.0, "Close": close, "Volume": volume}


def test_a_row_the_adapter_refuses_is_named_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole point: a refused row must not leave the series silently one bar short."""
    _install(monkeypatch, _frame([_row("2026-08-21"), _row("2026-08-24", volume=float("nan"))]))
    series = vendor_yahoo.fetch(_instrument(), Interval.DAY, KNOWN_AT)

    assert len(series.bars) == 1, "the good row still comes back - this is fail-open at the boundary"
    err = capsys.readouterr().err
    assert "TEST.1" in err
    assert "2026-08-24" in err, "the session that was lost has to be identifiable"
    assert "1 of 2 rows failed validation" in err


def test_a_clean_response_says_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The positive control. A warning printed on every fetch is a warning nobody reads."""
    _install(monkeypatch, _frame([_row("2026-08-21"), _row("2026-08-24")]))
    series = vendor_yahoo.fetch(_instrument(), Interval.DAY, KNOWN_AT)

    assert len(series.bars) == 2
    assert capsys.readouterr().err == ""


def test_the_report_is_bounded_when_a_whole_response_is_malformed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A vendor-wide malformation must cost a line, not one line per session per instrument."""
    bad = [_row(f"2026-07-{day:02d}", volume=float("nan")) for day in range(1, 21)]
    _install(monkeypatch, _frame([*bad, _row("2026-08-24")]))
    vendor_yahoo.fetch(_instrument(), Interval.DAY, KNOWN_AT)

    err = capsys.readouterr().err.strip()
    assert len(err.splitlines()) == 1
    assert "20 of 21 rows failed validation" in err
    assert "and 17 more" in err, "the count is the fact; the first few carry the reason"


def test_a_response_with_no_usable_row_still_raises(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reporting the drop must not turn a total failure into a silent empty series.

    Fetching is fail-open and deciding is fail-closed; `VendorUnavailable` is how the boundary hands
    that decision up. The report is additional to it, never instead of it.
    """
    _install(monkeypatch, _frame([_row("2026-08-24", volume=float("nan"))]))
    with pytest.raises(vendor_yahoo.VendorUnavailable, match="no usable rows"):
        vendor_yahoo.fetch(_instrument(), Interval.DAY, KNOWN_AT)
    assert "1 of 1 rows failed validation" in capsys.readouterr().err


def test_the_good_rows_are_unchanged_by_the_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dropped neighbour must not perturb the bars that survived it."""
    _install(monkeypatch, _frame([_row("2026-08-21", close=10.5), _row("2026-08-24", volume=None)]))
    (bar,) = vendor_yahoo.fetch(_instrument(), Interval.DAY, KNOWN_AT).bars
    assert bar.close == Decimal("10.5")
    assert bar.session_date.isoformat() == "2026-08-21"


def test_a_row_the_CONTRACT_refuses_is_reported_on_one_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`Bar` rejects a close outside `[low, high]`, and pydantic renders that over several lines.

    Found by a fixture that made exactly that mistake. A log spending six lines per refused row per
    instrument is one nobody reads, so the reason is collapsed and bounded.
    """
    _install(monkeypatch, _frame([_row("2026-08-21"), _row("2026-08-24", close=99.0)]))
    vendor_yahoo.fetch(_instrument(), Interval.DAY, KNOWN_AT)

    err = capsys.readouterr().err.strip()
    assert len(err.splitlines()) == 1, err
    assert "2026-08-24" in err and "ValidationError" in err
