"""`tools/run_pr025.py`: the opening auction against 15:55, for `CARD-001`'s entries.

The cases that carry the study:

* **`O` and `C` ARE `PR-024`'s arms** - the same inputs give the same trades, to the digit, so every
  difference against them is the auction and nothing else;
* **the cross is the listing market's print** - the largest one flagged `O` or `6`, not the first
  venue that stamped one;
* **the auction arm reads its entry session from the cross's own minute**, and the closing arm
  cannot exit on its entry session at all;
* **each reading is priced on the entries IT needs** - a missing cross drops `A - C`, not `X - C`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

from swingdesk.contracts.market import BarSeries, Interval, Series
from swingdesk.market_data.auctions import CLOSING, OPENING, AuctionStore, Print
from swingdesk.market_data.quotes import CLOSE, ELEVEN, OPEN

REPO = Path(__file__).resolve().parents[1]
KNOWN = datetime(2026, 1, 5, tzinfo=UTC)


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def run() -> ModuleType:
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tools"))
    return _load("_run_pr025", REPO / "tools" / "run_pr025.py")


@pytest.fixture(scope="module")
def world() -> ModuleType:
    return _load("_run_pr024_world_for_025", REPO / "tests" / "test_run_pr024.py")


def _print(at: datetime, price: float, size: int, conditions=("@", "O", "X"), exchange="Q"):
    return Print(at=at, price=Decimal(f"{price:.4f}"), size=size, exchange=exchange,
                 conditions=tuple(conditions))


def _windows(world, session, spreads=(20.0, 5.0, 2.0), mid=100.0, missing=()):
    asked = {OPEN: session.open_time + timedelta(seconds=5),
             ELEVEN: session.open_time.replace(hour=11, minute=0),
             CLOSE: session.close_time - timedelta(minutes=5)}
    out = {}
    for (moment, at), half in zip(asked.items(), spreads, strict=True):
        at = at.astimezone(UTC)
        out[moment] = None if moment in missing else (at, tuple(world._quotes(at, half, mid)))
    return out


def _auctions(session, open_price, close_price, missing=()):
    opened = session.open_time.astimezone(UTC)
    closed = session.close_time.astimezone(UTC)
    out = {
        OPENING: (_print(opened + timedelta(milliseconds=100), open_price - 0.5, 50, ("@", "O"), "P"),
                  _print(opened + timedelta(milliseconds=900), open_price, 20000),
                  _print(opened + timedelta(milliseconds=901), open_price, 20000, ("@", "Q"))),
        CLOSING: (_print(closed + timedelta(milliseconds=50), close_price + 0.3, 100, ("@", "M"), "P"),
                  _print(closed + timedelta(milliseconds=300), close_price, 90000, ("@", "6", "X"))),
    }
    for side in missing:
        out[side] = ()
    return out


def _series(bars) -> BarSeries:
    return BarSeries(instrument_id="X", interval=Interval.DAY, series=Series.RAW,
                     knowledge_time=KNOWN, bars=tuple(bars))


def _priced(run, world, path, *, missing_quotes=(), missing_auctions=(), spreads=(20.0, 5.0, 2.0)):
    entry, bars, minutes, entered = world._day_and_after(run.base, path)
    got = run.price_entry(entry, _series(bars), Decimal(2), tuple(minutes),
                          _windows(world, entered, spreads, missing=missing_quotes),
                          _auctions(entered, float(minutes[0].open), float(minutes[-1].close),
                                    missing_auctions),
                          entered, None, Counter())
    return got, entry, bars, minutes, entered


# --- the cross ------------------------------------------------------------------------------------


def test_the_cross_is_the_largest_flagged_print_not_the_first(run) -> None:
    at = datetime(2026, 3, 2, 14, 30, tzinfo=UTC)
    prints = (_print(at, 99.0, 50, ("@", "O"), "P"), _print(at + timedelta(seconds=1), 100.0, 9000),
              _print(at + timedelta(seconds=1), 101.0, 90000, ("@", "Q")))
    assert run.cross_price(prints, OPENING).price == Decimal("100.0000")
    assert run.cross_price(prints, CLOSING) is None, "no print flagged 6"
    assert run.cross_price((), OPENING) is None and run.cross_price(None, OPENING) is None


def test_a_tie_in_size_keeps_the_earlier_print(run) -> None:
    at = datetime(2026, 3, 2, 21, 0, tzinfo=UTC)
    prints = (_print(at + timedelta(seconds=2), 50.2, 700, ("@", "6")),
              _print(at, 50.1, 700, ("@", "6")))
    assert run.cross_price(prints, CLOSING).price == Decimal("50.1000")


def test_the_minute_holding_an_instant(run, world) -> None:
    session = world.cal.session(world.NYSE, date(2026, 3, 2))
    minutes = world._minutes(session, lambda i: 100.0)
    inside = minutes[3].at + timedelta(seconds=59)
    assert run.minute_holding(minutes, inside) is minutes[3]
    assert run.minute_holding(minutes, minutes[4].at) is minutes[4], "a minute ends before the next"
    assert run.minute_holding(minutes, minutes[0].at - timedelta(seconds=1)) is None


# --- the arms -------------------------------------------------------------------------------------


def test_o_and_c_are_pr024_s_own_trades_to_the_digit(run, world) -> None:
    """THE REPRODUCTION PROPERTY: identical inputs, identical trades, every costing but the one
    whose stress this study defines differently."""
    def path(i: int) -> float:
        return 100.0 + 0.004 * i

    got, entry, bars, minutes, entered = _priced(run, world, path)
    theirs = run.base.price_entry(entry, _series(bars), Decimal(2), tuple(minutes),
                                  _windows(world, entered), entered, None, Counter())
    assert not isinstance(theirs, str)
    for arm in (run.OPEN_ARM, run.LATE):
        for costing in ("net", "gross", "exits_at_registry", "anchored_stop"):
            assert got.trade(arm, costing) == theirs.trades[costing][arm], (arm, costing)


def test_the_auction_arm_pays_the_cross_and_no_spread(run, world) -> None:
    got, _, _, minutes, _ = _priced(run, world, lambda i: 100.0)
    trade = got.trade(run.AUCTION)
    assert trade.entry_price == minutes[0].open, "the listing market's cross, not the 99.5 venue print"
    assert got.paid[run.AUCTION] == 0
    assert got.trade(run.OPEN_ARM).entry_price > trade.entry_price, "O pays its half-spread"


def test_a_fall_at_ten_stops_the_auction_arm_as_it_stops_the_open(run, world) -> None:
    """The cross is in the 09:30 minute, so the auction arm holds through 10:00 like the open."""
    def path(i: int) -> float:
        return 94.0 if 30 <= i < 60 else 100.0

    got, entry, *_ = _priced(run, world, path)
    assert got.trade(run.AUCTION).exit_date == entry.session_date
    assert got.trade(run.AUCTION).exit_reason.value == "stop"
    assert got.trade(run.LATE).exit_date != entry.session_date


def test_a_late_cross_starts_the_auction_arm_s_session_at_its_own_minute(run, world) -> None:
    """A NYSE opening delayed to 09:45: the fall at 09:35 hit the continuous open, not an order
    waiting for a cross that had not printed yet."""
    def path(i: int) -> float:
        return 94.0 if 5 <= i < 10 else 100.0

    entry, bars, minutes, entered = world._day_and_after(run.base, path)
    auctions = _auctions(entered, 100.0, float(minutes[-1].close))
    late = entered.open_time.astimezone(UTC) + timedelta(minutes=15, milliseconds=200)
    auctions[OPENING] = (_print(late, 100.0, 20000),)
    got = run.price_entry(entry, _series(bars), Decimal(2), tuple(minutes),
                          _windows(world, entered), auctions, entered, None, Counter())
    assert got.trade(run.OPEN_ARM).exit_date == entry.session_date
    assert got.trade(run.AUCTION).exit_date != entry.session_date


def test_a_cross_outside_the_session_s_minutes_is_a_reason(run, world) -> None:
    entry, bars, minutes, entered = world._day_and_after(run.base, lambda i: 100.0)
    auctions = _auctions(entered, 100.0, 100.0)
    auctions[OPENING] = (_print(entered.open_time.astimezone(UTC) - timedelta(minutes=2), 100.0,
                                20000),)
    got = run.price_entry(entry, _series(bars), Decimal(2), tuple(minutes),
                          _windows(world, entered), auctions, entered, None, Counter())
    assert got.missing[run.AUCTION] == "cross_outside_the_minutes"


def test_the_closing_arm_cannot_exit_on_its_entry_session(run, world) -> None:
    """A collapse and recovery inside the day is invisible to an order that fills at the close."""
    def path(i: int) -> float:
        return 80.0 if 100 <= i < 200 else 100.0

    got, entry, _, minutes, _ = _priced(run, world, path)
    closing = got.trade(run.CLOSING_ARM)
    assert closing.entry_price == minutes[-1].close and got.paid[run.CLOSING_ARM] == 0
    assert closing.exit_date != entry.session_date
    assert got.trade(run.AUCTION).exit_date == entry.session_date


def test_the_cost_stress_charges_an_auction_the_close_s_spread(run, world) -> None:
    got, *_ = _priced(run, world, lambda i: 100.0, spreads=(20.0, 5.0, 2.0))
    stressed = got.trade(run.AUCTION, "cost_adverse")
    assert stressed.entry_price == got.trade(run.AUCTION).entry_price * (1 + Decimal(2) / 10000)
    late = got.trade(run.LATE, "cost_adverse")
    assert late.entry_price == got.trade(run.LATE).entry_price, "C at its own spread"


# --- each reading on its own entries --------------------------------------------------------------


def test_a_missing_opening_cross_drops_a_c_and_not_x_c(run, world) -> None:
    got, *_ = _priced(run, world, lambda i: 100.0, missing_auctions=(OPENING,))
    assert got.missing[run.AUCTION] == "no_opening_cross"
    assert run._pairs([got], run.AUCTION, run.LATE, "net") == []
    assert run._pairs([got], run.CLOSING_ARM, run.LATE, "net") == [got]


def test_a_missing_close_quote_is_kept_against_what_needs_it(run, world) -> None:
    """C cannot enter without the close's spread; A and O can, but a flat day's clock exit is
    charged at the close's spread, so their NET walks fail too - and their gross walks do not."""
    got, *_ = _priced(run, world, lambda i: 100.0, missing_quotes=(CLOSE,))
    assert got.missing[run.LATE] == "no_fresh_two_sided_quote"
    assert got.trades[run.AUCTION]["net"] == "exit_quote_missing"
    assert run._pairs([got], run.AUCTION, run.OPEN_ARM, "net") == []
    assert run._pairs([got], run.AUCTION, run.OPEN_ARM, "gross") == [got]


def test_the_reading_counts_its_own_pairs_and_reads_the_sign(run, world) -> None:
    """Flat prices, every arm on the clock: A pays nothing, C pays 2 bps, so A - C is 2 bps."""
    import dataclasses

    got, *_ = _priced(run, world, lambda i: 100.0)
    months = [dataclasses.replace(got, entry=run.base.Entry(
        "X", date(2023 + m // 12, 1 + m % 12, 2), date(2023 + m // 12, 1 + m % 12, 3)))
        for m in range(30)]
    cell = run.reading(months, run.AUCTION, run.LATE, drawn=40, resamples=20)
    assert cell["pairs"] == 30 and cell["complete_share"] == 0.75
    assert cell["difference"]["estimate"] == pytest.approx(0.0002, abs=2e-5)
    assert cell["gross_part"]["estimate"] == pytest.approx(0.0, abs=1e-9)
    # The level is the FIRST arm's own: the auction paid nothing in and 2 bps out.
    assert cell["level"]["estimate"] == pytest.approx(-0.0002, abs=2e-5)


def test_a_pair_needs_both_of_its_arms(run, world) -> None:
    got, *_ = _priced(run, world, lambda i: 100.0)
    assert run._pairs([got], run.AUCTION, run.LATE, "net") == [got]
    got.trades[run.LATE]["net"] = "zero_shares"
    assert run._pairs([got], run.AUCTION, run.LATE, "net") == []


def test_minutes_that_are_not_the_bar_price_nothing(run, world) -> None:
    entry, bars, minutes, entered = world._day_and_after(run.base, lambda i: 100.0)
    bars[30] = world._bar("X", entered, 100.0, 103.0, 99.9, 100.0)
    got = run.price_entry(entry, _series(bars), Decimal(2), tuple(minutes),
                          _windows(world, entered), _auctions(entered, 100.0, 100.0), entered,
                          None, Counter())
    assert got.early == "minutes_mismatch" and got.trades == {}


def test_the_verdict_is_pr024_s_branch_table_on_a_c(run) -> None:
    cell = {"difference": {"lo": 0.001, "hi": 0.002, "width": 0.001, "estimate": 0.0015},
            "level": {"hi": 0.01}, "cost_adverse": {"estimate": 0.001},
            "complete_share": 0.95, "pairs": 3000, "months": 48}
    assert run.branch_for(cell) == "ACCEPT"
    assert run.branch_for({**cell, "complete_share": 0.5}) == "REFUSED"


# --- end to end -----------------------------------------------------------------------------------


def _auction_world(tmp_path, world, run):
    args, entries = world._world(tmp_path, run.base)
    from swingdesk.market_data import BarStore

    with BarStore(tmp_path / "bars.duckdb") as bars, \
            AuctionStore(tmp_path / "auctions.duckdb") as auctions:
        for e in entries:
            series = bars.as_of(e.instrument_id, Interval.DAY, Series.RAW, KNOWN)
            bar = next(b for b in series.bars if b.session_date == e.session_date)
            session = world.cal.session(world.NYSE, e.session_date)
            made = _auctions(session, float(bar.open), float(bar.close))
            for side, prints in made.items():
                auctions.write(e.instrument_id, e.session_date, side,
                               session.open_time if side == OPENING else session.close_time,
                               prints, 100, KNOWN, "test")
    return argparse.Namespace(**vars(args), auctions=tmp_path / "auctions.duckdb",
                              auctions_as_of=None), entries


def test_the_run_goes_end_to_end_on_synthetic_stores(run, world, tmp_path) -> None:
    args, entries = _auction_world(tmp_path, world, run)
    payload = run.build(args)
    assert payload["branch"] == "SMOKE" and payload["prereg"] == "PR-025"
    assert payload["trials"] == 2
    assert set(payload["cells"]) == {"A-C", "X-C", "A-O"}
    assert payload["cells"]["A-C"]["pairs"] == len(entries)
    assert payload["crosses"]["closing_equals_bar_close"] == len(entries)
    assert payload["crosses"]["opening_equals_bar_open"] == len(entries)
    for key in ("country", "split", "perturbations", "measured_span", "as_of", "excluded_by_arm",
                "reproduces_pr024", "diagnostics"):
        assert key in payload
    assert set(payload["perturbations"]["registered"]) == set(payload["perturbations"]["run"])
    json.dumps(payload, default=run.base._default)


def test_the_registered_verdict_is_read_from_a_c(run, world, tmp_path, monkeypatch) -> None:
    args, _ = _auction_world(tmp_path, world, run)
    args.resamples = run.base.BOOTSTRAP_RESAMPLES
    monkeypatch.setattr(run, "branch_for", lambda cell: f"{cell['first']}-{cell['second']}")
    monkeypatch.setitem(run.base.TOKEN, "A-C", "read A-C")
    monkeypatch.setattr(run, "write_qa", lambda priced: None)
    monkeypatch.setattr(run.base, "BOOTSTRAP_RESAMPLES", 20)
    args.resamples = 20
    payload = run.build(args)
    assert payload["branch"] == "A-C" and payload["verdict"] == "read A-C"


def test_a_bar_s_float_tail_is_the_same_print(run, world) -> None:
    """103.769997 in the stored bar is the 103.77 cross; a cent away is not."""
    got, *_ = _priced(run, world, lambda i: 100.0)
    got.bar = got.bar.model_copy(update={"open": got.crosses[run.AUCTION].price - Decimal("0.000003"),
                                         "close": got.crosses[run.CLOSING_ARM].price
                                         + Decimal("0.01")})
    seen = run.crosses_against_the_bar([got])
    assert seen["opening_equals_bar_open"] == 1
    assert seen["closing_equals_bar_close"] == 0


def test_reproduction_reads_pr024_s_qa_rows(run, world, tmp_path) -> None:
    args, _ = _auction_world(tmp_path, world, run)
    priced, *_ = run.price_sample(args, run.base.read_sample(args.sample))
    qa = tmp_path / "qa.csv"
    rows = ["instrument_id,session_date,arm,exit_date,exit_reason,per_dollar"]
    for p in priced[:3]:
        t = p.trade(run.LATE)
        rows.append(f"{p.entry.instrument_id},{p.entry.session_date},C,{t.exit_date},"
                    f"{t.exit_reason.value},{round(run.base.per_dollar(t), 6)}")
    t = priced[0].trade(run.OPEN_ARM)
    rows.append(f"{priced[0].entry.instrument_id},{priced[0].entry.session_date},O,{t.exit_date},"
                f"{t.exit_reason.value},{round(run.base.per_dollar(t), 6) + 0.01}")
    qa.write_text("\n".join(rows) + "\n", encoding="utf-8")
    assert run.reproduces_pr024(priced, qa) == {"checked": 4, "differ": 1, "not_priced": 0}


def test_the_report_prints_every_reading(run, world, tmp_path, capsys) -> None:
    args, _ = _auction_world(tmp_path, world, run)
    run.report(run.build(args))
    printed = capsys.readouterr().out
    for label in ("A-C", "X-C", "A-O", "net per dollar", "cost-adverse", "date-weighted",
                  "reproduces PR-024", "paid bps"):
        assert label in printed
