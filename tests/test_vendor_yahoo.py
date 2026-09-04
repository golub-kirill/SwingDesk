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
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest

from swingdesk.contracts.market import Interval
from swingdesk.contracts.reference import Exchange, Instrument

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import vendor_integrity
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

    **Amended 2026-09-04.** This asserted the whole of stderr was ONE line, and that was always a
    stronger claim than the docstring made: the subject is the collapsing of a multi-line pydantic
    render, not the total. A close outside `[low, high]` is *also* arithmetically impossible, so it
    now carries a `VENDOR INTEGRITY` line beside its refusal - deliberately, and covered below.
    The assertion is narrowed to what this test is actually about.
    """
    _install(monkeypatch, _frame([_row("2026-08-21"), _row("2026-08-24", close=99.0)]))
    vendor_yahoo.fetch(_instrument(), Interval.DAY, KNOWN_AT)

    err = capsys.readouterr().err.strip()
    refusals = [line for line in err.splitlines() if line.startswith("vendor row(s) refused")]
    assert len(refusals) == 1, err
    assert "2026-08-24" in refusals[0] and "ValidationError" in refusals[0]


# ------------------------------------------------------- an impossible bar is not a late one
#
# Measured 2026-09-04 across the whole run log: 1,120 refusals in one evening, 1,113 of them the
# same routine condition, and `DFNM`'s arithmetically impossible bar invisible among them. The
# first run of `tools/vendor_integrity.py` then found **770** such bars across 311 instruments and
# 52 runs - not one. Every one had been buried since the log began.


def _impossible_row(when: str) -> dict:
    """Yahoo's own numbers for `DFNM` on 2026-09-03, scaled to a `TEST.n` instrument.

    The open sits above the high. A session's high IS the highest price of that session and the
    open is a trade inside it, so no publication delay produces this - which is precisely what
    separates it from a `close` the vendor has not computed yet.
    """
    return {"when": when, "Open": 47.37, "High": 47.355, "Low": 47.27,
            "Close": 47.30, "Volume": 1_000}


def test_an_impossible_bar_gets_its_own_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """THE REGRESSION. Without a prefix of its own it is one of a thousand identical lines."""
    _install(monkeypatch, _frame([_row("2026-08-21"), _impossible_row("2026-08-24")]))
    vendor_yahoo.fetch(_instrument(), Interval.DAY, KNOWN_AT)

    err = capsys.readouterr().err
    assert "VENDOR INTEGRITY" in err, (
        "an open outside its own session range is arithmetically impossible and must be findable "
        "without grouping a thousand lines by hand"
    )
    assert "TEST.1" in err and "2026-08-24" in err
    assert "outside [" in err, "the numbers themselves, so the reader can check the claim"


def test_a_late_close_does_NOT_get_that_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The control that stops the prefix meaning nothing.

    This is the 1,113-a-day case - the vendor's end-of-day process has not run. It is still
    refused and still counted, and it is NOT an integrity finding. A prefix that appears on every
    refusal is the noise it was added to cut.
    """
    _install(monkeypatch, _frame([_row("2026-08-21"), _row("2026-08-24", close=float("nan"))]))
    vendor_yahoo.fetch(_instrument(), Interval.DAY, KNOWN_AT)

    err = capsys.readouterr().err
    assert "VENDOR INTEGRITY" not in err
    assert "1 of 2 rows failed validation" in err, "still refused, still counted, still visible"


def test_the_impossible_bar_is_also_still_counted_as_a_refusal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """It gets an EXTRA line, never a different one. Losing it from the count would trade one
    kind of silence for another."""
    _install(monkeypatch, _frame([_row("2026-08-21"), _impossible_row("2026-08-24")]))
    vendor_yahoo.fetch(_instrument(), Interval.DAY, KNOWN_AT)
    printed = capsys.readouterr().err

    assert "1 of 2 rows failed validation" in printed
    assert printed.count("VENDOR INTEGRITY") == 1


# ------------------------------------------------------------------ the history tool reads BOTH


def test_the_integrity_tool_reads_the_legacy_line_shape() -> None:
    """A history tool that cannot read history is decoration.

    The `VENDOR INTEGRITY` prefix landed 2026-09-04. Every one of the 770 violations already in
    the log was written before it, inside a `vendor row(s) refused` line - so a parser that only
    understood the new shape would answer *"has this happened before?"* with *no*, for all 770.
    """
    legacy = ("vendor row(s) refused  DFNM 1d: 1 of 252 rows failed validation - 2026-09-03 "
              "(ValidationError: 1 validation error for Bar Value error, open 47.369999 outside "
              "[47.270000, 47.355000] [type=value_error])")
    found = vendor_integrity.violations(legacy)

    assert len(found) == 1
    symbol, field, distance = found[0]
    assert symbol == "DFNM"
    assert field == "open"
    # 47.369999 is 0.014999 above a high of 47.355, against a midpoint of 47.3125.
    assert Decimal("0.031") < distance < Decimal("0.032"), distance


def test_the_integrity_tool_reads_the_new_line_shape() -> None:
    current = ("VENDOR INTEGRITY  DFNM 1d 2026-09-03  1 validation error for Bar Value error, "
               "open 47.369999 outside [47.270000, 47.355000]")
    found = vendor_integrity.violations(current)

    assert [(s, f) for s, f, _d in found] == [("DFNM", "open")]


def test_the_integrity_tool_ignores_a_refusal_that_is_merely_late() -> None:
    """The positive control for the parser: it must not count the routine case as a violation."""
    routine = ("vendor row(s) refused  AIS 1d: 1 of 252 rows failed validation - 2026-09-03 "
               "(ValidationError: 1 validation error for Bar close Input should be a finite "
               "number [type=finite_number, input_value=Decimal('NaN')])")
    assert vendor_integrity.violations(routine) == []
