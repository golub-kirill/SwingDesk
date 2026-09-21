"""How much of the real delisting record does Alpaca's inactive list actually hold?

**The gap `measure_delisted_universe.py` admitted and could not close.** That measurement counted
1,973 inactive US equity assets on a major exchange and said, in its own limits block, that their
completeness against an independent census was *"MEASURABLE and unmeasured"*. This measures it.

**The independent census is SEC EDGAR**, and `tools/probe_edgar.py` established on 2026-08-24 that
it is free, official and complete back to 1993: Form **25** and **25-NSE** are the notifications of
removal from listing. What that probe did not do was enumerate them.

**Three things learned by probing before building, each of which would have corrupted the result:**

1. **Form 25 carries NO `primary_doc.xml`** - measured 0 of 14, against 13 of 14 for `25-NSE`. A
   pipeline that fetched only the XML would silently drop every ISSUER-filed delisting, which is a
   different kind of event from an exchange-filed one, and would have looked like a clean 93%
   success rate while dropping a category. Form 25's security class is recoverable from the
   submission text: it sits immediately before the literal `(Description of class of securities)`.
2. **A Form 25 is not a company.** It removes ONE CLASS of security, so one company delisting its
   shares and its warrants files twice - `AMBAC FINANCIAL GROUP` does exactly that in 2020Q1. The
   census counts EVENTS and the join counts ISSUERS, and those are different numbers.
3. **Most of them are not equity at all.** Of 40 descriptions read by hand from a 2020Q1 sample,
   11 were common or ordinary shares; the rest were notes, preferred stock, ETFs, warrants, units,
   depositary shares, ETNs, LP interests and rights. **A raw Form 25 count overstates company
   delistings by roughly three times**, so the classifier below is the measurement, not a detail
   of it.

**Why a SAMPLE and not a census**, decided before any of it was fetched: EDGAR serves names and
dates and never prices or tickers, and prices exist only at the broker. So EDGAR cannot ADD one
tradable name to the universe - it can only say how much of it is missing, which is a SHARE, and a
share is what a stratified sample estimates. A census is ~20,000 fetches for a number a few hundred
gives.

    python tools/measure_edgar_coverage.py [--per-quarter 20] [--from 2016] [--to 2026]

Read-only. SEC's fair-access policy asks for a contact address in the `User-Agent`; this sends
whatever `SWINGDESK_EDGAR_CONTACT` holds and says so when it holds nothing. **It never transmits an
address it was not given** (`probe_edgar.py`'s rule, kept). Network tool, never run in CI
(`CI_POLICY` §4).
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import measure_delisted_universe as alpaca

OUT = REPO / "docs" / "decisions" / "measurements" / "edgar-coverage-2026-09-21.json"
INDEX = "https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/form.idx"
ARCHIVE = "https://www.sec.gov/Archives/{path}"
PRIMARY = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/primary_doc.xml"

#: SEC's fair-access ceiling is 10 requests a second. This sits well under it; the measurement is
#: a few hundred requests and there is nothing to gain by crowding a public service.
DELAY_SECONDS = 0.15

SAMPLE_SEED = 20260921

#: What a Form 25 puts immediately AFTER the security's description. Measured on three filings on
#: 2026-09-21 - it is a printed form, so the marker is stable in a way a layout is not.
FORM25_MARKER = "(Description of class of securities)"

#: Checked FIRST. "Units, each consisting of one share of Class A Common Stock" contains the words
#: "Common Stock" and is not common stock, so an inclusive test alone classifies it wrongly.
NOT_COMMON = re.compile(
    r"(?i)\b(note|notes|bond|debenture|preferred|warrant|right|unit|units|etf|etn|fund|"
    r"depositary|depository|adr|american depositar|trust preferred|subordinated|senior|"
    r"floating rate|cumulative|partnership interest|limited partner)\b")
IS_COMMON = re.compile(r"(?i)\b(common stock|common shares|ordinary shares|ordinary share|"
                       r"class [a-z] common|common share)\b")

#: EDGAR decorates a name with a state or country suffix and a corporate form. Neither is part of
#: the company, and leaving them in turns a match into a miss.
EDGAR_SUFFIX = re.compile(r"/[A-Z]{2,3}\b")
CORPORATE = re.compile(
    r"(?i)\b(incorporated|inc|corporation|corp|company|co|limited|ltd|plc|llc|lp|llp|nv|sa|ag|"
    r"holdings|holding|group|trust|the|new)\b")

UNAVAILABLE = 4


@dataclass(frozen=True)
class Filing:
    """One notification of removal from listing, as the quarterly index lists it."""

    form: str
    company: str
    cik: str
    filed: str
    path: str
    quarter: str


def user_agent() -> str:
    """SEC asks for a contact. This sends one only if the operator supplied one."""
    contact = os.environ.get("SWINGDESK_EDGAR_CONTACT", "").strip()
    return f"SwingDesk-research/1.0 ({contact or 'contact not supplied'})"


def get(url: str, accept: str = "text/plain") -> str | None:
    """One GET, or None. A measurement reports what it could not read; it does not die."""
    headers = {"User-Agent": user_agent(), "Accept": accept, "Accept-Encoding": "gzip"}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", "replace")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return None


def quarters(first_year: int, last_year: int) -> list[tuple[int, int]]:
    return [(y, q) for y in range(first_year, last_year + 1) for q in (1, 2, 3, 4)]


def filings_in(year: int, quarter: int) -> list[Filing]:
    """Every Form 25 and 25-NSE the quarter's index lists, or an empty list if it is not there.

    The index is fixed-width text and the last column is the path. A quarter that has not happened
    yet returns nothing rather than raising, which is what makes the caller's range safe to
    over-specify.
    """
    body = get(INDEX.format(year=year, quarter=quarter))
    if body is None:
        return []
    out: list[Filing] = []
    for line in body.splitlines():
        if not line.startswith(("25 ", "25-NSE")):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        form = "25-NSE" if line.startswith("25-NSE") else "25"
        out.append(Filing(form=form, company=" ".join(parts[1:-3]), cik=parts[-3],
                          filed=parts[-2], path=parts[-1], quarter=f"{year}Q{quarter}"))
    return out


def read_filing(filing: Filing) -> tuple[str | None, str]:
    """The class of security this filing removes, and WHOSE it was.

    Two shapes because the forms are two shapes, and the fallback is the whole point: `25-NSE` is
    XML with a `descriptionClassSecurity` element, and Form 25 is a printed form whose class sits
    immediately before `(Description of class of securities)`.

    **The issuer comes from the FILING, not from the index**, and that is not a nicety. A `25-NSE`
    is filed BY THE EXCHANGE, so the index's company column names Cboe or Nasdaq for 203 of 462
    rows in 2020Q1 - 44% - and a join on that column can never match a broker's list of companies.
    The first run of this measurement did exactly that and reported 8.6% coverage with
    "NASDAQ Stock Market LLC" among the companies it could not find.
    """
    issuer = filing.company
    if filing.form == "25-NSE":
        accession = filing.path.rsplit("/", 1)[-1].replace(".txt", "").replace("-", "")
        xml = get(PRIMARY.format(cik=filing.cik, accession=accession), "application/xml")
        if xml:
            named = re.search(r"<issuer>.*?<entityName>(.*?)</entityName>", xml, re.S)
            if named:
                issuer = " ".join(html.unescape(named.group(1)).split())
            found = re.search(r"<descriptionClassSecurity>(.*?)</descriptionClassSecurity>", xml,
                              re.S)
            if found:
                return " ".join(html.unescape(found.group(1)).split()), issuer
    body = get(ARCHIVE.format(path=filing.path))
    if body is None:
        return None, issuer
    # Entities first, tags second: a filing writes `&nbsp;` and `&amp;` around the
    # description, and leaving them in puts "&amp;" inside a company name the join
    # then fails to match.
    flat = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(body)).split())
    at = flat.find(FORM25_MARKER)
    if at < 0:
        return None, issuer
    # The description is the run of text before the marker, and the label before THAT ends in a
    # closing bracket - so the bracket is where this class's description starts.
    before = flat[:at].strip()
    start = before.rfind(")")
    candidate = (before[start + 1:] if start >= 0 else before[-120:]).strip()
    # **And it is REFUSED when it does not look like one.** A filing with co-registrants puts a
    # list of companies where this expects a security, and `SEASPAN` did exactly that on the first
    # run: "Corporation, Seaspan Containership 2180 Ltd., Seaspan ...". Returning that would
    # classify a company list as "not common stock" silently, which is a wrong answer wearing the
    # clothes of a right one. Returning None makes it an UNREADABLE filing, which the report counts
    # and a reader can see.
    if len(candidate) > 100 or len(CORPORATE.findall(candidate)) >= 2:
        return None, issuer
    return (candidate or None), issuer


def is_common_stock(description: str | None) -> bool:
    """Common or ordinary shares, and nothing that merely mentions them."""
    if not description:
        return False
    if NOT_COMMON.search(description):
        return False
    return bool(IS_COMMON.search(description))


def normalise(name: str) -> str:
    """A company name reduced to what two sources can agree on."""
    cleaned = EDGAR_SUFFIX.sub(" ", name.upper())
    cleaned = re.sub(r"[^A-Z0-9 ]+", " ", cleaned)
    cleaned = CORPORATE.sub(" ", cleaned)
    return " ".join(cleaned.split())


def head(name: str, words: int = 2) -> str:
    """The first significant words - a looser key, so name variants can be told from real gaps."""
    return " ".join(normalise(name).split()[:words])


def sample(filings: Sequence[Filing], per_quarter: int) -> list[Filing]:
    """A seeded, stratified draw: the same number from every quarter that has that many.

    Stratified rather than uniform because delistings cluster - 2020 and 2022 are not 2017 - and a
    uniform draw would let one bad year speak for the decade.
    """
    rng = random.Random(SAMPLE_SEED)
    by_quarter: dict[str, list[Filing]] = {}
    for filing in filings:
        by_quarter.setdefault(filing.quarter, []).append(filing)
    drawn: list[Filing] = []
    for quarter in sorted(by_quarter):
        pool = sorted(by_quarter[quarter], key=lambda f: (f.cik, f.path))
        drawn.extend(pool if len(pool) <= per_quarter else rng.sample(pool, per_quarter))
    return drawn


def alpaca_names() -> dict[str, list[str]] | None:
    """Every inactive Alpaca asset on a real exchange, keyed by normalised name.

    Imported rather than re-fetched: this is the SAME list `measure_delisted_universe.py` counted,
    and a second enumeration could drift from the one the coverage number is about.
    """
    status, body = alpaca.get(f"{alpaca.ASSETS}?status=inactive&asset_class=us_equity")
    if status != 200 or not isinstance(body, list):
        return None
    out: dict[str, list[str]] = {}
    for asset in alpaca.listed(body):
        key = normalise(str(asset.get("name", "")))
        if key:
            out.setdefault(key, []).append(str(asset.get("symbol", "")))
    return out


def coverage(drawn: Sequence[Filing], by_name: dict[str, list[str]],
             progress: bool = True) -> dict[str, Any]:
    """Read each sampled filing, keep the common-stock ones, and see which the broker remembers."""
    heads: dict[str, list[str]] = {}
    for key, symbols in by_name.items():
        heads.setdefault(" ".join(key.split()[:2]), []).extend(symbols)

    read = unreadable = 0
    common: list[dict[str, Any]] = []
    for n, filing in enumerate(drawn, 1):
        description, issuer = read_filing(filing)
        time.sleep(DELAY_SECONDS)
        if description is None:
            unreadable += 1
            continue
        read += 1
        if not is_common_stock(description):
            continue
        key, prefix = normalise(issuer), head(issuer)
        common.append({
            "company": issuer, "index_filer": filing.company,
            "cik": filing.cik, "filed": filing.filed,
            "form": filing.form, "quarter": filing.quarter, "description": description[:120],
            "exact": key in by_name, "by_prefix": prefix in heads,
            "symbols": by_name.get(key) or heads.get(prefix) or [],
        })
        if progress and n % 100 == 0:
            print(f"  ... {n}/{len(drawn)} filings read")

    exact = sum(1 for row in common if row["exact"])
    loose = sum(1 for row in common if row["exact"] or row["by_prefix"])
    return {
        "sampled": len(drawn), "read": read, "unreadable": unreadable,
        "common_stock_events": len(common),
        "common_stock_share_of_filings": len(common) / read if read else 0.0,
        "matched_exact": exact,
        "matched_including_prefix": loose,
        "coverage_exact": exact / len(common) if common else 0.0,
        "coverage_including_prefix": loose / len(common) if common else 0.0,
        "unmatched_examples": [row["company"] for row in common
                               if not (row["exact"] or row["by_prefix"])][:15],
        "matched_examples": [f"{row['company']} -> {','.join(row['symbols'][:2])}"
                             for row in common if row["exact"]][:10],
    }


#: Below this, a coverage figure is more likely a broken join than a finding about the world.
#: Chosen from what the defect actually looked like: the first run of this measurement joined on
#: the index's filer column instead of the filing's issuer and reported an exact-name match rate of
#: **1.7%**. A real gap between a broker's memory and the SEC's record is a gap of tens of percent;
#: a structural mismatch is a gap of tens of PARTS PER THOUSAND, and the two do not overlap.
SUSPECT_BELOW = 0.10


def suspect_join(coverage_share: float) -> str:
    """Empty when the number is plausible, and an accusation of the instrument when it is not.

    `AGENTS.md` §12: a rate near an extreme accuses the instrument before it accuses the world.
    This says so IN THE REPORT, because the first time it happened the only thing that caught it
    was a person reading the unmatched names.
    """
    if coverage_share >= SUSPECT_BELOW:
        return ""
    return ("SUSPECT: a coverage this low is more likely a broken join than a finding. Check that "
            "the name joined on is the ISSUER from the filing and not the FILER from the index - "
            "a 25-NSE is filed by the exchange, so the index names Cboe or Nasdaq for roughly "
            "half the rows. Read `unmatched_examples` before believing this number.")


def interval(hits: int, total: int) -> tuple[float, float]:
    """A 95% Wald interval on a share. Wide when the sample is small, which is the honest signal."""
    if total == 0:
        return (float("nan"), float("nan"))
    p = hits / total
    half = 1.96 * (p * (1 - p) / total) ** 0.5
    return (max(0.0, p - half), min(1.0, p + half))


def report(payload: dict[str, Any]) -> None:
    got = payload["result"]
    print(f"EDGAR delisting census {payload['window']}")
    print(f"  Form 25 + 25-NSE filings enumerated : {payload['filings_enumerated']:,}"
          f"   ({payload['quarters_read']} quarters)")
    print(f"  sampled                             : {got['sampled']:,}"
          f"   read {got['read']:,}, unreadable {got['unreadable']:,}")
    print(f"  of those, COMMON STOCK              : {got['common_stock_events']:,}"
          f"   ({100 * got['common_stock_share_of_filings']:.1f}% of filings)")
    print(f"  implied common-stock delistings     : ~{payload['implied_common_events']:,.0f}"
          " over the window")
    lo, hi = payload["coverage_interval"]
    print(f"  ALPACA REMEMBERS                    : {100 * got['coverage_including_prefix']:.1f}%"
          f"  [{100 * lo:.1f}%, {100 * hi:.1f}%]"
          f"   (exact-name only: {100 * got['coverage_exact']:.1f}%)")
    if got["unmatched_examples"]:
        print(f"  not found at the broker, e.g.       : "
              f"{'; '.join(got['unmatched_examples'][:5])}")
    if got["matched_examples"]:
        print(f"  found, e.g.                         : {'; '.join(got['matched_examples'][:3])}")
    warning = suspect_join(got["coverage_including_prefix"])
    if warning:
        print(f"  !! {warning}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--per-quarter", type=int, default=20,
                        help="filings drawn from each quarter")
    parser.add_argument("--from", dest="first", type=int, default=2016,
                        help="first year - Alpaca serves no bars before 2016, so nothing earlier "
                             "could be repaired even if EDGAR lists it")
    parser.add_argument("--to", dest="last", type=int, default=2026)
    parser.add_argument("--cache", type=Path,
                        help="a JSON to keep the enumerated filings in. The 43 quarterly indexes "
                             "are ~50MB each and dominate the run; the join is what gets iterated "
                             "on, so re-reading them every time is the wrong thing to repeat")
    args = parser.parse_args(argv)

    by_name = alpaca_names()
    if by_name is None:
        print("EDGAR coverage: UNAVAILABLE - the broker's inactive list could not be read")
        return UNAVAILABLE

    filings: list[Filing] = []
    read_quarters = 0
    if args.cache and args.cache.exists():
        kept = json.loads(args.cache.read_text(encoding="utf-8"))
        filings = [Filing(**row) for row in kept["filings"]]
        read_quarters = kept["quarters"]
        print(f"enumeration read from {args.cache}")
    else:
        for year, quarter in quarters(args.first, args.last):
            found = filings_in(year, quarter)
            time.sleep(DELAY_SECONDS)
            if found:
                read_quarters += 1
                filings.extend(found)
        if args.cache and filings:
            args.cache.parent.mkdir(parents=True, exist_ok=True)
            args.cache.write_text(json.dumps(
                {"quarters": read_quarters, "filings": [f.__dict__ for f in filings]}),
                encoding="utf-8")
    if not filings:
        print("EDGAR coverage: UNAVAILABLE - no quarterly index could be read")
        return UNAVAILABLE

    drawn = sample(filings, args.per_quarter)
    print(f"enumerated {len(filings):,} filings across {read_quarters} quarters;"
          f" reading {len(drawn):,}")
    got = coverage(drawn, by_name)
    lo, hi = interval(got["matched_including_prefix"], got["common_stock_events"])

    payload = {
        "measured": "2026-09-21",
        "asked_by": "the owner, 2026-09-21 - asked what else needs measuring and to think EDGAR "
                    "through so delistings can be pulled properly",
        "exploratory": True,
        "trials": 0,
        "why_no_trial": "it counts FILINGS and NAMES. No return is read, no rule is evaluated and "
                        "nothing is selected on performance",
        "tool": "tools/measure_edgar_coverage.py",
        "window": f"{args.first}..{args.last}",
        "quarters_read": read_quarters,
        "filings_enumerated": len(filings),
        "by_form": {"25": sum(1 for f in filings if f.form == "25"),
                    "25-NSE": sum(1 for f in filings if f.form == "25-NSE")},
        "sample": {"per_quarter": args.per_quarter, "seed": SAMPLE_SEED,
                   "stratified_by": "calendar quarter"},
        "result": got,
        "implied_common_events": len(filings) * got["common_stock_share_of_filings"],
        "coverage_interval": [lo, hi],
        "suspect_join": suspect_join(got["coverage_including_prefix"]),
        "broker_inactive_names": len(by_name),
        "limits": {
            "a_filing_is_a_CLASS_not_a_company": "one company delisting its shares and its "
                                                 "warrants files twice, so the event count is "
                                                 "above the company count and only the "
                                                 "common-stock rows are joined",
            "the_join_is_by_NAME": "EDGAR carries no ticker and the broker carries no CIK, so the "
                                   "join is two spellings of one company. The exact and "
                                   "prefix-matched figures are both reported because their "
                                   "difference IS the name-matching error, and the truth is at or "
                                   "above the looser one",
            "coverage_is_not_completeness_of_PRICES": "a name the broker lists is a name whose "
                                                      "bars can be asked for, not one whose bars "
                                                      "are known to be there. PR-036's own fetch "
                                                      "is the precedent - stored is not the same "
                                                      "as served",
            "2016_floor": "the window opens in 2016 because the broker serves no daily bar before "
                          "it on the Basic plan. An EDGAR delisting from 2014 is real and "
                          "unrepairable, and is deliberately outside this measurement rather "
                          "than counted as a miss",
        },
    }
    payload["as_of"] = datetime.now(UTC).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report(payload)
    print(f"  written to {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - the entry point
    raise SystemExit(main())
