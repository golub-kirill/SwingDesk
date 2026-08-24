"""The run report.

Every displayed number resolves to a registered component with a version, a recorded parameter
provenance, and a validation status (CHARTER 4, the ratified v1 finish line). A value computed from
`assumed` inputs is marked as such adjacent to the number it produced - not in a footnote
(PARAMETER_REGISTRY 5).
"""

from __future__ import annotations

from pathlib import Path

from swingdesk.application.pipeline import InstrumentOutcome, RunResult
from swingdesk.application.universe import UniverseSelection
from swingdesk.presentation.funnel import funnel
from swingdesk.trade_management import portfolio
from swingdesk.trade_management.sizing import Refusal

_RULE = "─" * 78


def _universe_block(result: RunResult) -> list[str]:
    """How the candidates were chosen, and how complete that choice was.

    The coverage line is the point. "47 instruments" reads like the rule's answer; "47 admitted, out
    of 312 measured of 13,048 eligible" reads like what it is - a subset that will grow as bars are
    fetched. Printing only the first would let a partial universe be mistaken for the population.
    """
    selection = result.universe
    if selection is None:
        return []

    rule = selection.rule
    lines = [
        "UNIVERSE — selected by rule, not by a list (DR-003)",
        _RULE,
        f"  rule           close >= {rule.min_price} · {rule.adtv_window}d ADTV >= "
        f"{rule.min_adtv:,.0f} · >= {rule.min_history} bars",
        f"  members        {len(selection.members)}",
        f"  coverage       {selection.measured} of {selection.eligible} eligible symbols have "
        f"stored bars ({selection.coverage:.1%})",
    ]
    if selection.directory_pull is not None:
        lines.append(f"  directory      pulled {selection.directory_pull:%Y-%m-%d}")
    for parameter in selection.parameters:
        flag = "  <- ASSUMED, not evidence" if parameter.is_assumed else ""
        lines.append(f"      {parameter.id:<26} {parameter.value}   [{parameter.provenance}]{flag}")

    if selection.is_partial:
        lines += [
            "",
            "  PARTIAL UNIVERSE. This is a subset of what the rule admits, not the rule's answer:",
            "  a symbol with no stored bars cannot be measured, so it cannot be admitted. Run",
            "  tools/refresh_universe.py to raise coverage.",
        ]
    if selection.capped_from is not None:
        lines += [
            "",
            f"  CAPPED to {len(selection.members)} of {selection.capped_from} admitted, by dollar",
            "  volume. A cap is a RANKING and the rule is not — these results are about the most",
            "  liquid members, and do not describe the universe.",
        ]
    return lines


def render_empty_universe(selection: UniverseSelection) -> str:
    """What to say when the rule admits nobody. Not an error, and not silence either."""
    return "\n".join([
        _RULE,
        "UNIVERSE EMPTY — no instrument met the DR-003 liquidity rule",
        _RULE,
        f"  eligible symbols in the directory   {selection.eligible}",
        f"  of those, with stored bars          {selection.measured}",
        "  admitted by the rule                0",
        "",
        "  With no bars stored, this is a coverage problem rather than a market one:",
        "    python tools/fetch_directory.py     # if the directory is empty",
        "    python tools/refresh_universe.py    # to fetch bars for eligible symbols",
        _RULE,
    ])


def _positions_block(result: RunResult) -> list[str]:
    """Open positions first, because that is the order the run used and the order that matters.

    A proposal is shown as a proposal. Nothing here has happened; D6 routes stop moves and partial
    exits through the owner, and a report that reads like a confirmation would be lying about that.
    """
    if not result.positions:
        return []

    lines = ["", "OPEN POSITIONS — evaluated before candidates (CHECKLIST_SPEC 4)", _RULE]
    for outcome in result.positions:
        position = outcome.position
        flag = "  [STALE DATA]" if outcome.stale else ""
        lines.append(
            f"  {position.instrument_id:<12} {position.shares:>5} sh @ {position.entry_price}"
            f"  stop {position.current_stop}  open risk {position.open_risk}{flag}"
        )
        # The split guard's own line, and only when it has something to say. A clean check on an
        # instrument with actions on record is the ordinary case and printing it every evening
        # would train the eye past the two lines that matter (`DR-016` §7).
        guard = outcome.split
        if guard is not None and (guard.alert is not None or guard.is_unavailable):
            lines.append(f"      splits:   {guard.note}")

        if outcome.action is not None:
            action = outcome.action
            marker = "NEEDS YOUR APPROVAL" if action.is_actionable else "no action"
            lines.append(f"      proposed: {action.kind.value:<14} {marker}")
            lines.append(f"      because:  {action.reason}")
    pending = len(result.actionable)
    if pending:
        lines.append("")
        lines.append(f"  {pending} proposal(s) await your approval. Nothing has been done.")
    return lines


def _capacity_block(result: RunResult) -> list[str]:
    """Room in the book for one more position, or why that could not be answered (`DR-006` §8.3).

    Three outcomes, printed apart on purpose. "Within the cap", "the cap has no value" and "the book
    was never read" are three different claims, and a block that showed the first for all three
    would be the `unavailable`-as-`pass` collapse `HANDOFF.md` §7 names as this product's most
    damaging possible error.
    """
    capacity = result.capacity
    lines = ["", "BOOK CAPACITY — the cap DR-006 §8.3 ratified", _RULE]

    if isinstance(capacity, Refusal):
        lines.append(f"  REFUSED  {capacity}")
        lines.append("           no candidate was admitted; the cap itself has no value")
        return lines

    if capacity is None:
        if "positions" not in result.steps:
            lines.append("  UNAVAILABLE  the book was not read this run, so the cap could not be")
            lines.append("               applied. That is `unavailable` - not `within the cap`.")
        else:
            lines.append(f"  positions      {len(result.positions)} open")
            lines.append("  NOT ASSESSED   no candidate reached sizing, so nothing was compared")
            lines.append("                 against the cap")
        return lines

    caps, book = capacity.caps, capacity.book
    lines.append(f"  positions      {book.count} / {caps.max_concurrent}"
                 f"   [{portfolio.MAX_CONCURRENT}]")
    lines.append(f"  open risk      {book.open_risk_r:.2f}R / {caps.max_open_risk}R"
                 f"   [{portfolio.MAX_OPEN_RISK}]")
    if capacity.binding is not None:
        lines.append(f"  BINDING        {capacity.binding}")
        lines.append(f"                 {capacity.reason}")
    else:
        lines.append(f"  room           {capacity.reason}")
    lines.append("")
    lines.append("  Each candidate is measured against the BOOK ALONE. Watch names do not consume")
    lines.append("  capacity from one another, so the room above is for ONE more position, not for")
    lines.append("  every candidate below it (ALLOCATION_SPEC §6 rule 4 - rs.ranking_method unset).")
    return lines


def _correlation_block(result: RunResult) -> list[str]:
    """The other half of step 6: is this the same bet the book already holds? (`DR-006` §2.)

    Printed apart from BOOK CAPACITY because it fails in a different direction, and a reader who
    cannot see that distinction cannot use either block. A book cap that has no value refuses
    everything; a correlation that could not be MEASURED refuses nothing and says so. Folding the
    two into one "portfolio checks" block would make the second look like the first.

    The counts are derived from the outcomes rather than carried alongside them, so this block can
    never disagree with the decisions above it - the same rule `_funnel_block` follows.
    """
    limit = result.correlation
    lines = ["", "CORRELATION — the same bet twice? (DR-006 §2)", _RULE]

    if isinstance(limit, Refusal):
        lines.append(f"  REFUSED  {limit}")
        lines.append("           no candidate was admitted; the cap itself has no value")
        return lines

    if limit is None:
        lines.append("  UNAVAILABLE  the cap was not read this run")
        return lines

    lines.append(
        f"  threshold      r >= {limit.threshold} over {limit.lookback} shared session(s)"
        f"   [{portfolio.CORRELATION_THRESHOLD}]"
    )

    checked = [
        outcome.correlation for outcome in result.outcomes if outcome.correlation is not None
    ]
    if not checked:
        if "positions" not in result.steps:
            lines.append("  UNAVAILABLE  the book was not read this run, so no candidate could be")
            lines.append("               correlated against it. That is `unavailable`, and it is")
            lines.append("               not the same claim as `these are independent`.")
        else:
            lines.append("  NOT ASSESSED   no candidate reached the correlation check")
        return lines

    if not checked[0].pairs:
        lines.append("  no open position, so there was nothing for a candidate to duplicate")
        return lines

    refused = [check for check in checked if not check.admitted]
    unmeasurable = [check for check in checked if check.is_unavailable]
    partial = [check for check in checked if check.unmeasured and not check.is_unavailable]

    lines.append(f"  candidates     {len(checked)} correlated against {len(checked[0].pairs)} "
                 f"open instrument(s)")
    lines.append(f"  refused        {len(refused)}   duplicate exposure, Skip/RISK")
    if unmeasurable:
        lines.append(
            f"  UNAVAILABLE    {len(unmeasurable)}   could not be correlated at all and were "
            f"admitted UNCHECKED"
        )
        lines.append(f"                 {unmeasurable[0].reason}")
    if partial:
        lines.append(
            f"  partial        {len(partial)}   cleared the positions that could be measured, "
            f"with others unchecked"
        )
    if not unmeasurable and not partial:
        lines.append("  every pair was measured; nothing was admitted on an unchecked comparison")
    return lines


def _sector_block(result: RunResult) -> list[str]:
    """How the open book's risk is spread across sectors, and what it could not place (`DR-006` §2).

    **The unattributed totals are printed next to the split, not under it.** A sector table that
    showed only what it could place would read as a complete picture of the book, and the two ways
    it is incomplete both push the same way: an unclassifiable position and a partial look-through
    each make every sector figure an UNDERSTATEMENT, which admits candidates the full picture would
    have refused.
    """
    limit = result.sector_limit
    lines = ["", "SECTOR — how much of the book sits in one theme (DR-006 §2)", _RULE]

    if isinstance(limit, Refusal):
        lines.append(f"  REFUSED  {limit}")
        lines.append("           no candidate was admitted; the cap itself has no value")
        return lines

    if limit is None:
        lines.append("  UNAVAILABLE  the cap was not read this run")
        return lines

    lines.append(f"  cap            {limit}R in any one sector   [{portfolio.MAX_SECTOR_RISK}]")

    book = result.sector_book
    if isinstance(book, Refusal):
        lines.append(f"  REFUSED  {book}")
        return lines
    if book is None:
        if "positions" not in result.steps:
            lines.append("  UNAVAILABLE  the book was not read this run, so its sector split could")
            lines.append("               not be computed. That is not `inside the cap`.")
        else:
            lines.append("  NOT ASSESSED   no candidate reached the sector check")
        return lines

    if book.by_sector:
        for sector, risk in book.by_sector.items():
            over = "  <- AT OR PAST THE CAP" if risk >= limit else ""
            lines.append(f"      {sector:<28} {risk:.2f}R{over}")
    else:
        lines.append("      (no open risk could be placed in any sector)")

    if book.unclassified_r:
        lines.append(
            f"  unattributed   {book.unclassified_r:.2f}R of {book.total_r:.2f}R sits in no "
            f"sector - partial look-throughs, spent as reported and not normalised"
        )
    if book.unmeasured:
        lines.append(
            f"  UNCLASSIFIED   {len(book.unmeasured)} open position(s) holding "
            f"{book.unmeasured_r:.2f}R could not be placed at all"
        )
        lines.append(f"                 {book.unmeasured[0].unavailable}")
    if not book.is_complete:
        lines.append("  The split above therefore UNDERSTATES every sector it shows.")

    unchecked = [
        outcome.sector
        for outcome in result.outcomes
        if outcome.sector is not None and outcome.sector.is_unavailable
    ]
    if unchecked:
        lines.append(
            f"  UNAVAILABLE    {len(unchecked)} candidate(s) could not be classified and were "
            f"admitted UNCHECKED"
        )
        lines.append(f"                 {unchecked[0].candidate.unavailable}")
    return lines


def _checklist_block(outcome: InstrumentOutcome) -> list[str]:
    """The pre-trade checklist, with the unanswered items shown rather than summarised away.

    An `unavailable` item is a gap in the SYSTEM, and printing it next to the passes is the only
    way the operator can tell the difference between "checked and fine" and "nobody checked".
    """
    checklist = outcome.checklist
    if checklist is None:
        return []

    counts = checklist.counts
    lines = [
        f"  pre-trade checklist  Appendix {checklist.appendix} · {checklist.terminal_state()}",
        f"      {counts['pass']} pass · {counts['fail']} fail · "
        f"{counts['unavailable']} unavailable · {counts['human']} for you",
    ]
    for item in checklist.failures:
        lines.append(f"      FAIL  {item.id}  {item.text}")
        lines.append(f"            {item.note}")
    unavailable = [i for i in checklist.items if i.state.value == "unavailable"]
    if unavailable:
        lines.append(f"      not checkable yet: {', '.join(i.id for i in unavailable)}")
    return lines


def _funnel_block(result: RunResult) -> list[str]:
    """What happened to today's candidates, aggregated (US-022).

    Always printed, even when there are no candidates at all — a quiet day (nothing triggered) and
    a broken one (a parameter went unset, a source went stale) must not read the same, and the old
    footer's single `decisions <n>` could not tell them apart. `funnel()` reads only what `result`
    already carries, so this block can never disagree with the per-instrument blocks above it.
    """
    stats = funnel(result)
    lines = [
        "FUNNEL — what happened to today's candidates (US-022)",
        _RULE,
        f"  eligible         {stats.eligible}",
        f"  measured         {stats.measured}",
        f"  admitted         {stats.admitted}",
        f"  evaluated        {stats.evaluated}",
        "",
        f"  Trade            {stats.trade}",
        f"  Watch            {stats.watch}",
        f"  Skip             {stats.skip}",
        f"  Pause            {stats.pause}",
    ]
    if stats.unaccounted:
        lines.append(f"  UNACCOUNTED      {stats.unaccounted}   <- evaluated with no decision recorded")
    # is_reconciled is reported here, not asserted in funnel.py: a broken invariant belongs in the
    # render where a human sees it, not in an exception raised over a run that already did its job.
    if not stats.is_reconciled:
        lines.append(
            "  RECONCILIATION FAILED — the buckets above do not sum to evaluated. Treat this "
            "report as a defect, not as today's answer."
        )
    lines += [
        "",
        f"  changed          {stats.changed}   (decision differs from its previous run)",
        f"  first sighting   {stats.first_sighting}   (no previous decision on record)",
    ]
    if stats.skip_causes:
        lines.append("")
        lines.append("  skip causes, most common first:")
        for cause in stats.skip_causes:
            # A parameter_id marks a SYSTEM fault (an unset threshold); its absence marks a fact
            # about the account or the market. Same code, different meaning - shown separately
            # rather than collapsed, which is exactly how 1131 unset-parameter refusals once read
            # as an ordinary quiet day.
            label = f"{cause.code} [{cause.parameter_id}]" if cause.parameter_id else cause.code
            lines.append(f"      {label:<32} {cause.count}")
    return lines


def render(result: RunResult) -> str:
    manifest = result.manifest
    lines: list[str] = [
        _RULE,
        f"SwingDesk run {manifest.run_id}",
        _RULE,
        f"  started        {manifest.started_at:%Y-%m-%d %H:%M:%S %Z}",
        f"  code           {manifest.code_hash}" + ("  DIRTY TREE" if manifest.code_dirty else ""),
        f"  config         {manifest.config_hash}",
        f"  snapshot       {manifest.snapshot_id}",
        f"  calendar       {manifest.calendar_version}",
        f"  platform       {manifest.platform}",
        f"  output hash    {manifest.output_hash}",
    ]
    if manifest.universe_hash is not None:
        lines.append(f"  universe hash  {manifest.universe_hash}")
    lines.append("")

    universe = _universe_block(result)
    if universe:
        lines.extend(universe)
        lines.append("")

    lines.extend(_positions_block(result))
    lines.extend(_capacity_block(result))
    lines.extend(_correlation_block(result))
    lines.extend(_sector_block(result))
    if result.positions or result.universe is not None:
        lines.extend(["", "CANDIDATES", _RULE])

    for outcome in result.outcomes:
        instrument = outcome.instrument
        lines.append(f"{instrument.ticker} ({instrument.exchange.value}, {instrument.currency})")
        lines.append(f"  bars stored          {outcome.bars}")

        if outcome.completeness_findings:
            lines.append(f"  completeness         {len(outcome.completeness_findings)} finding(s)")
            for finding in outcome.completeness_findings[:3]:
                lines.append(f"      {finding}")
        elif outcome.bars:
            lines.append("  completeness         clean (every session matched the calendar)")

        observations = outcome.observations
        if observations is not None:
            latest = observations.observations[-1]
            value = "none (warm-up)" if latest.value is None else f"{latest.value:.4f}"
            lines.append(f"  {observations.component} v{observations.component_version}")
            lines.append(f"      ATR                {value}  {observations.units}")
            lines.append(f"      validation         {observations.validation_status}")
            for parameter in observations.parameters:
                flag = "  <- ASSUMED, not evidence" if parameter.is_assumed else ""
                lines.append(
                    f"      {parameter.id:<18} {parameter.value}   [{parameter.provenance}]{flag}"
                )

        risk = outcome.risk
        if isinstance(risk, Refusal):
            lines.append(f"  risk                 REFUSED  {risk}")
        elif risk is not None:
            lines.append(f"  entry / stop         {risk.entry} / {risk.stop}")
            lines.append(f"  risk per share       {risk.risk_per_share}")
            lines.append(f"  shares               {risk.shares}   (rounded down)")
            lines.append(f"  planned risk         {risk.planned_risk}   <- R denominator, frozen")

        # Only when the candidate CLEARED it. A refusal already reads out in full on the DECISION
        # line below, and printing the same sentence twice trains the eye to skip both.
        concentration = outcome.correlation
        if concentration is not None and concentration.admitted and concentration.pairs:
            lines.append(f"  correlation          {concentration.reason}")

        sector = outcome.sector
        if sector is not None and sector.admitted:
            lines.append(f"  sector               {sector.reason}")

        decision = outcome.decision
        if decision is not None:
            detail = f"  [{decision.reason_code}]" if decision.reason_code else ""
            lines.append(f"  DECISION             {decision.decision}{detail}")
            if decision.reason:
                lines.append(f"      {decision.reason}")
        lines.extend(_checklist_block(outcome))
        lines.append("")

    lines.extend(_funnel_block(result))
    lines.append("")

    assumed = sorted(
        {
            parameter.id
            for outcome in result.outcomes
            if outcome.observations
            for parameter in outcome.observations.parameters
            if parameter.is_assumed
        }
    )
    lines += [
        _RULE,
        f"  decisions        {len(result.decisions)}",
        f"  assumed inputs   {len(assumed)}" + (f"  ({', '.join(assumed)})" if assumed else ""),
        "",
        "  Every setup in this system is Untested. A decision here means the components",
        "  computed what their specs say - not that the trade has an edge.",
        _RULE,
    ]
    return "\n".join(lines)


def write(result: RunResult, directory: Path) -> Path:
    """Persist the report as one file per run, and return where it went.

    `US-001` requires that "a dated report is produced" and `PRODUCT_SURFACES` 3.1 lists dated
    reports among the CLI's outputs. Until 2026-08-16 neither happened. `render()` returned a
    string, `cli.py` printed it, and `daily_run.cmd` redirected stdout into `data/daily_run.log` -
    an append-only file that interleaves the preflight, the run and the directory sidecar, and
    rotates at 50MB. A report the owner has to go find inside that is not a delivered report, and
    everything older than the rotation is gone for good. `ROADMAP.md` recorded this row as **done**
    on the strength of the run rendering something.

    **The filename is the run_id and nothing else.** It already carries the run's start instant
    (`run-YYYYMMDDTHHMMSSZ-<unique>`), so it sorts chronologically and traces straight to the
    journal's `runs` row. Formatting a date separately would put a second copy of a fact the
    manifest already owns into a filename, and `AGENTS.md` 10.5 is about exactly that drift.

    **Plain text, and that is the honest half of the requirement.** `PRODUCT_SURFACES` 3.1 says
    "HTML/PDF" and this is not that. Adding an HTML path now means rendering one run through two
    independent code paths - the defect this project keeps finding under other names - so HTML
    waits for one renderer with two backends, and until then this claims text and only text.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.manifest.run_id}.txt"
    path.write_text(render(result), encoding="utf-8")
    return path
