# TODO — the single open-work list

**Status:** working document · **Owner:** shared · **Last reconciled:** 2026-08-17

This is the **only** place open and pending work is listed. If a task is not here, it is not tracked.
Sessions add and close items here; nowhere else keeps a parallel list.

## The rule this file lives under

**This file holds work items. It never holds measured counts.** `AGENTS.md` §10.5 gives every
measured number exactly one owner, and a to-do list that restates one becomes the next stale copy —
which is the disease, not the cure. Where an item needs a number, it names the **command** that
derives it:

```bash
python tools/check_gates.py          # gate status
python tools/track_a_streak.py       # the a.run_completes counter (run from the MAIN checkout)
python tools/verify_counts.py        # every census this project knows how to derive
```

Provenance marks: **`[v]`** verified against code or data, most recently 2026-08-17 · **`[c]`**
carried from the open-tasks audit, not independently re-checked. A `[c]` item is not a smaller
claim than a `[v]` one — it is an *unverified* one, and promoting it means checking it, not
retyping it.

---

## 1. Blocking now

**`master` went RED on its own, 2026-08-22, and it is fixed in this branch.** Four tests in
`test_cli.py` seeded a proposal dated 2026-08-16 and let `pending` / `respond` read the wall clock;
`management.proposal_expiry_days` is 3 sessions, so on 2026-08-20 the window closed and gate 8 began
failing on an untouched tree. Fixed by pinning `--as-of` the way the file's own expiry tests already
do, and the trap is now in `AGENTS.md` §12. The 2026-08-11 freeze lifted on 2026-08-17.

**What blocks the next thing worth doing.** The two items that stood here on 2026-08-18 are both
closed — the R denominator by re-measurement, the staleness gate by `DR-015` being built — and what
follows them is open work rather than a blocker. **Corporate actions is the one to read**: it is the
last of the three "specified, implemented, wired to nothing" findings still open, and `DR-015` §4
hands it over by name.

- [x] **`[v]` The R denominator was asserted by nothing — CLOSED 2026-08-18 by re-measurement, not
      by work.** On the morning of 08-17, `planned_risk` could be replaced with the constant
      `Decimal('42')` and the entire suite stayed green, including the test `INVARIANTS.md` §1 names
      as enforcing that invariant — which asserts `(net/x)*x == net`, an identity that cannot fail
      for any `x`. That test is still a tautology and should be replaced.
      **But the defect it left open is closed.** Re-measured on `master` after PR #9 merged: the
      `Decimal('42')` mutant is **killed**, and so is `risk_per_share = entry - stop + costs` →
      `entry - stop`. What kills them is `test_sizing_and_position_agree_on_the_denominator`, the
      cross-module property test written as part of #9 — it asserts the *equality* of `sizing`'s and
      `Position`'s denominators rather than either value, so it constrains `planned_risk` without
      naming it.
      **The base rate is now 1 of 11, not 3.** The sole survivor is `calendar.sessions_behind`,
      below.
      **A conclusion that rested on this and no longer stands:** "a wrong R could be why the base
      strategy is negative" — R was never wrong, it was merely unasserted, so there is no prior
      result to re-derive. **The entry-filter family stays closed.**
- [x] **`[v]` The staleness gate is specified, implemented, and not wired — BUILT 2026-08-18
      (`DR-015`).** `calendar.sessions_behind` has a caller: `market_data/freshness.py`, read at
      both decision points in `pipeline.py`. The retry wrapper is `market_data/retry.py`, injected
      in `cli.py` so the pipeline never sleeps, and the 19:30 second pass is an argument to
      `tools/daily_run.cmd`. `data.freshness_window`'s `read_by` names its consumer, so the
      decided-not-wired count fell **27 → 26**.
      **The gap was not theoretical, and the number is the finding.** Measured against the
      2026-08-17 scheduled run before any of it existed: of 1152 evaluated candidates, **67 (5.8%)
      ended the run one session behind** — last bar Friday 08-14, last completed session Monday
      08-17. Every one was sized and left on `Watch` against a stale close, and every one reported
      `completeness clean`. That is correct and is the point: §2.2 looks for a hole *inside* the
      stored window, and a series that simply stops early has no hole. Nothing in the report told
      those 67 apart from the other 1085.
      **The held-position half is the one `TODO` §1 named** — fetching is fail-open by design and
      `managed.stale` was set only when there were **no** bars at all, so a position whose fetch
      failed was managed against stored bars of any age, silently. Fail-open on the FETCH is
      unchanged; deciding on what it fell back to is now fail-closed, and the position PAUSEs.
      **Track A restarted 2026-08-18** — two frozen files, and the change moves decision output.

- [ ] **`[v]` `data.staleness_action_threshold` is still `unset` and still read by nothing.**
      `DR-015` set `data.freshness_window` and did not touch this one. They are not duplicates:
      the window is **per instrument** — this candidate is too stale to size — while Appendix T's
      *"при stale data или mismatch новые сделки блокируются"* is a **system-wide** block on new
      entries. Today a run where every candidate is stale refuses each one individually and says
      nothing about the run as a whole. Needs a ruling, or an explicit decision that the
      per-instrument gate discharges it and the parameter should be retired (`AGENTS.md` §11).

- [x] **`[v]` Unclosed bars — GUARD BUILT 2026-08-18, deletion ruled by the owner and pending one
      command.** Found while measuring for `DR-016`, by accident.
      **The scope was three times what I first reported, and the first number came from a method
      that structurally undercounts.** I found 98 by comparing consecutive versions, which can only
      see a bad bar that was later corrected. Re-scoped against the calendar directly — every stored
      bar whose `knowledge_time` predates its own session's close — the answer is **296**, all from
      one manual fetch on 2026-08-03 at 13:25 local, 2.5 hours before the 16:00 ET close. Stored
      closes were out by up to **4.3%**. The same fetch also wrote ~350 bars per session for
      07-27→07-31; those sessions had closed, so those bars are correct and are untouched.
      **`CALENDAR_SPEC.md` §5 forbids the unclosed current bar and `last_completed_session` enforced
      it on every READ. Nothing enforced it on WRITE.** Now `BarStore.write` does: a bar captured
      before its session's close is refused before the revision comparison, so a partial print can
      neither enter the store nor overwrite a good bar already in it. Counted on `WriteResult`
      rather than dropped silently. A session the calendar does not know is allowed through —
      `unavailable` is not `fail`, applied to a write. 4 tests, both mutants killed.
      **OWNER RULING, 2026-08-18: delete the rows, do not supersede them.** *"We have no reason to
      replay broken stuff step by step."* This is a deliberate exception to `CHANGE_MANAGEMENT.md`
      §3 (rollback is supersede, never revert): a replay pinned to a `knowledge_time` before the
      deletion will not reproduce, and that is the accepted cost, recorded rather than discovered.
      **DONE 2026-08-18 — the owner ran it.** 296 rows deleted, store 1,920,316 → **1,920,020**,
      `unclosed bars still present: 0`. Verified independently afterwards: the **1,768** good bars
      the same 13:25 fetch wrote for sessions 07-27…07-31 are untouched, 3,412 instruments still
      hold a valid 2026-08-03 bar, and PIT integrity is clean. Backup kept beside the store.
      **The gap heals itself.** `pipeline.run` fetches a full year per universe member every evening
      and `write` inserts what is missing, so a member's 2026-08-03 bar returns on the next
      scheduled run — correct this time. 96 of the 296 are current members; the other 200 are not
      evaluated at all until `refresh_universe.py` reaches them, which refetches them anyway.

- [ ] **`[v]` ADTV admission reads provisional volume — DR-017 DRAFTED 2026-08-18, needs a ruling.**
      `universe.min_adtv_20d` admits on 20-day average dollar volume, and the vendor's recent volume
      is not final: of 7,131 settled bars served twice, **7,129 had volume rewritten** (p50 1.1%,
      p90 32%, p99 83%, max 164×), against a close that moves p90 0.02%. **6 of 1,172 instruments
      cross the $5M line between first sight and settlement, all six the same direction.**
      **CORRECTION to my own number, and it is the substance of DR-017 §2.** I first reported the
      settlement curve as *"a cliff at 8 calendar days"*. Wrong unit — `AGENTS.md` §3 makes sessions
      the unit of every duration here, and eight calendar days is a different quantity every week.
      Re-measured in sessions over the daily-run era (5,980 revisions): **0 sessions 16.9% · 1
      session 80.1% · 2 sessions 3.0% · 3+ sessions ZERO.** Much tighter than the calendar figure
      implied, and it makes the lag **3 sessions rather than ~6**.
      **The methodological trap, worth carrying beyond this item:** across the whole store the tail
      runs to 5 sessions, and every one of those comes from the single 2026-08-09 capture that
      re-observed bootstrap bars. **Age-at-re-fetch is not settlement age** — if nothing looks at a
      bar for five sessions, a revision made at one session old is recorded as five. Only a
      gap-free observation regime separates them, so the measurement is restricted to one.
      **Proposed:** `universe.adtv_lag_sessions = 3` — three, not two, because two is the oldest age
      at which a revision was *seen*, and three is the first with a measured zero.
      **Council-reviewed, direction chosen 4–1 on reproducibility rather than bias:** a lagged window
      makes admission idempotent, so a replayed screen returns what the live screen returned. One
      universe and one lag for live admission AND studies.
      **MEASURED 2026-08-18, and it reframes what the screen is FOR** (`DR-003` addendum). Over the
      2026-08-17 run's 1,148 sized candidates: risked $100/trade, position value median **$1,355**
      and max **$2,500**, against an admitted set whose 20-day ADTV is median **$46.8M**. Position
      as a share of one session's dollar volume: median **0.0026%**, worst **0.0462%** — against a
      conventional 10%-of-ADV execution limit, that is **200× inside it**, and the screen would only
      begin to bind at roughly a **$2.2M** account.
      So `$5M` is **not a liquidity constraint at this size**; it is a **quality proxy** — tighter
      spread, real price discovery, not a shell. Two consequences: raising it buys no executability
      and would have to be argued on spread or data quality instead, and **`DR-017`'s lag is
      justified by reproducibility ALONE** — it cannot also be defended as protecting the owner from
      an unfillable position, and that weaker argument is now blocked from being borrowed later.
      **The SHAPE of the rule is off-convention too.** Index providers screen on turnover relative
      to size, not absolute dollars: S&P's **FALR** (annual dollar traded ÷ float-adjusted market
      cap, ≥ 0.75) and MSCI's **ATVR** (annualised traded value ÷ free-float cap, 20% developed).
      $5M/day is heavy turnover for a $200M company and a rounding error for a $200B one. So the
      proposed $3M–$8M sweep tests the LEVEL of a measure whose FORM is also unvalidated — recorded
      as a constraint rather than a defect, because a ratio needs point-in-time float-adjusted market
      cap and this project has no free source for it, the same wall that made index membership
      unusable.
      **Still open and NOT decided by DR-017:** is backfilled volume executable? The fill-in is
      overwhelmingly upward; if it is late off-exchange prints then settled ADTV overstates the very
      liquidity $5M proxies. And `universe.min_adtv_20d = $5M` is itself `assumed` and never swept —
      a $3M–$8M sweep would test it and settle whether the six crossers are noise, in one pass.

- [ ] **`[v]` Corporate actions — DR-016 DRAFTED and its PRECONDITION IS NOW BUILT (2026-08-18).**
      **The actions series exists.** `POINT_IN_TIME_SPEC` §4 named three series and the tree had
      two; `DR-016` named the third as its own blocker. Built: `CorporateAction` on the contract, a
      bitemporal `corporate_actions` table beside the bars with `write_actions` / `actions_as_of`,
      and `vendor_yahoo.fetch_actions` reading the vendor's splits and dividends.
      **Not a `Series` member, deliberately** — a split has no open/high/low/close, so putting it in
      that enum would mean inventing five empty fields and the first component to read one would
      get numbers back. It is its own record with its own table, which is what "with their own
      `knowledge_time`" in the spec's own row requires.
      **Wired into no decision.** The gate needs `data.revision_epsilon`, which is `unset` pending
      the ruling below, so storing an action changes nothing the run decides — which is exactly why
      it was safe to land before the ruling. 11 tests, 5 mutants killed including the look-ahead one
      (an action learned later must be invisible to an earlier read).
      **What still needs the owner:**
      `data.revision_epsilon = 0.001`, scoped to price only; volume taken out of §4's
      raw-immutability rule and given no parameter, because the course names no such concept and the
      measured distribution contains no threshold. **Its precondition is `Series.ACTIONS`**, which
      `POINT_IN_TIME_SPEC.md` §4 names and `contracts/market.py` does not implement — the vendor does
      supply splits and dividends (`yfinance` 1.5.2), so the record is buildable once the series
      exists. **Zero positions exist today, so the catastrophic case has no current exposure** — the
      guard should land before the first real position, not after.
      Original statement of the risk, still accurate: `DR-015` §4 hands it over
      explicitly. Both decision paths read `Series.RAW`; raw bars are unadjusted, so a split does
      not restate history — **the next bars arrive at a different price level**. A 2:1 split over a
      weekend leaves a stored stop of 290 compared against Monday raw prices near 145: an instant
      stop-out that never happened, on a position still held.
      `DATA_QUALITY_SPEC.md` §4 specifies the gate in full, including the `DATA_ERR`/`Critical`
      case for a changed raw bar. **Nothing is implemented** — no mention of splits or dividends
      anywhere in `src/` — and `data.revision_epsilon` is `unset`. Needs its own record, same shape
      as `DR-015`. **Stale data makes the system decide on old information, which is now refused.
      An unhandled split makes it decide on *wrong* information while every freshness check
      passes.**

### Closed — kept for the reasoning, not as work

- [x] **`[v]` Track A restart rule + idle-day diagnostic — landed 2026-08-16, council-reviewed (5
      advisors + peer review, unanimous on both original questions).** A merge to a frozen file that
      changes decision output resets `a.run_completes` to zero from the merge date. Written into
      `HANDOFF.md` §5. The council's sharper catch: the restart alone doesn't fix what the counter
      proves — `CLEAN_EXIT_CODES = (0, 2)` counts a day where every candidate Skips identically
      (exit params unset) the same as a day that evaluated something, so most days between PR #9
      landing and DR-006 ratifying will read "clean" while idle. `tools/track_a_streak.py` now
      prints a second, additional line from `journal.duckdb` — how many counted days were idle —
      without touching what `a.run_completes` itself measures. 5 new tests
      (`tests/test_gates.py`), each confirmed to fail against a broken `_idle()`.
- [x] **`[v]` New research suspended — 2026-08-16, same council, unanimous.** No new
      pre-registrations, UDR-004 paused, PR-001/PR-002 re-registration paused. **Not suspended:**
      DR-006 ratification (unblocking, not research — but must land on evaluated values, not a
      rubber stamp, or it repeats the pattern one level up) and PR-005 (a hard blocker on the exit
      card, not a study). Resume research once one real end-to-end cycle — proposal → owner sees it
      → position opened → managed → approved → applied → filled — has actually run. See §6b for the
      gap analysis that prompted this and the build order now underway.
- [x] **`[v]` Gate 16 was RED — fixed 2026-08-15.** Both undeclared worktrees are now named in
      `HANDOFF.md` §2. `python tools/verify_branches.py` exits 0.
- [x] **`[v]` `HANDOFF.md` §2's stale rows — fixed at the mechanism, 2026-08-15.** §2 is now
      generated by `tools/build_state.py` and gated by gate 24, so Track A (**4/20**), the directory
      census (**10 pulls / 2 confirmed**) and universe coverage (**28.5%**) are computed rather than
      typed. Two new standing measurements came with it: PIT integrity (**CLEAN**, 0 bars whose
      `event_time` postdates their `knowledge_time`) and the dirty-tree run count (**11 of 13**).

**PR #3 merged.** This file has been on `master` since.

## 2. Picked work

- [x] **`[v]` Task 8 — PR-005 trade-log replay. Done 2026-08-16.**
      `tools/run_pr005_replay.py` + `docs/prereg/results/PR-005-trades.csv` (26,351 trades) +
      `PR-005-trades-provenance.json`. **PR-009, the exit card and the EDGAR backfill are
      unblocked** — on a documented basis, not a pretended one.
      **What reproduces exactly:** the whole `primary` period, all ten cells. And in the holdout,
      the ungated arm (`NONE`), `MA_STACK` (B) and `PRICE_AND_STACK` (C) — trade counts and mean R
      to every digit. 16 of 20 cells exact.
      **What does not, and why it never will.** `ABOVE_LONG_MA` (A) and `STRUCTURE` (D) differ in
      the holdout by ≤0.00052 mean R at *identical* trade counts. Those are the two gates that turn
      on a single margin: A is one threshold with no confirmation, D depends on exact pivot
      extremes. B and C need two conditions at once, so a marginal revision cannot flip them, and
      NONE is not gated at all. A handful of revised closes therefore move A and D and nothing
      else. **PR-005 ran at 02:02 UTC on 2026-08-03 and fetched live; the store's earliest
      `knowledge_time` for this sample is later. The bytes it read exist nowhere and refetching
      cannot recover them.** Measured, not assumed: the pre-refetch state already differed by
      +0.177R (A) and +0.339R (D) *with one fewer trade*, so the missing sessions were never the
      main cause.
      **The refetch was still worth it** (owner-authorised write to the live store): the gap was
      three sessions — 2026-07-21, 07-22, 07-31 — not one, for six of eight instruments. 26 rows,
      no bar inside the window revised. It restored the missing VGK trade and corrected an FBNC
      exit from `stop_gap`/07-23 to `stop`/07-22.
      **`LEG` and `NDSN` have no 2026-07-31 bar and the vendor does not supply one** — refetched
      successfully, the session simply is not there while 60 other instruments have it. A standing
      data-quality fact about this source. It affects no trade: neither has an `end_of_data` exit
      in any arm (checked, after the opposite hypothesis was tested and refuted).
      **Publishing took two keys, deliberately.** `--write` alone still refuses; `--accept-drift`
      is required and writes the cell-by-cell comparison beside the log. **`PR-009` must register
      against this replay's vintage, not against PR-005's published aggregate** — they are now
      known not to be the same thing, and the provenance file says so in the artifact itself.
- [ ] **`[c]` UDR-004 — regime ontology.** Three candidate lists now: ТЗ's 8, course v5.0's 11,
      v7.0's 7 (`RECONCILIATION_PLAN.md` §5). Ties to `USER_STORIES.md`:304 (US-004 unsatisfiable
      while `regime.classifier_rule` is contested).
- [ ] **`[c]` G-3 next timebox.**
- [ ] **`[c]` Test logon-mode behaviour.** Needs a log-out before 18:30 one evening, then read
      `Last Run Time` against the trigger. Settles `AGENTS.md` §10.4's marked conjecture.
- [ ] **`[c]` Re-measure universe coverage.** 28.3% is ~10 days stale. New number goes to
      `HANDOFF.md` §2 only — `DR-005` is append-only.

## 3. Contradictions — two documents disagree

Each of these is a silent wrong-answer generator: a session reads one, acts, and is wrong.

- [x] **`[v]` `registry/criteria.yml`:222's stale note — fixed 2026-08-15 via v1.1.1 amendment.**
      Council-reviewed (5 advisors + peer review); one response's recommendation was flagged by the
      safety layer for arguing to edit the ratified note in place, and 3 of 5 peer reviewers
      independently converged on the same objection blind to the flag. v1.1.0's note left
      byte-for-byte untouched; a comment (not a data field) points to the v1.1.1 entry, which carries
      the verified correction with its evidence. Same fix applied to
      `docs/00-charter/SUCCESS_AND_KILL_CRITERIA.md`:154 via `AGENTS.md` §10.5's own
      strikethrough-and-append convention. All 29 gates pass.
- [ ] **`[c]` G0 status.** `CONSTRAINTS.md`:150 says ratifying the remaining `criteria.yml` values
      "closes G0"; `HANDOFF.md` §2 says G0 is closed.
- [x] **`[c]→[v]` The 120-day Track A clock — resolved by the v1.1.1 amendment above.**
      `SUCCESS_AND_KILL_CRITERIA.md`:154's "has not started" is now struck through and corrected.
      Checked `HANDOFF.md` §4 for a third copy before closing this: it already says "reversed
      2026-08-09" (from the §4 rewrite in `279c625`) — consistent with the amendment, no drift.
      The date is 2026-08-09 (`tools/track_a_streak.py`'s own `SCHEDULING_STARTED` constant, which
      cites this same date), not 08-10 — 08-10 is the first NYSE session the schedule was
      *evaluated against*, and the day it failed on batteries.
- [ ] **`[c]` SPEC_GAP §32/§33** still read `DEFERRED`; `COVERAGE_AUDIT.md` says charter amendment
      A-001 makes them `MISSING, not OUT_OF_SCOPE`.
- [ ] **`[c]` `HANDOFF.md`:124** says "Two ratified criteria are inert" and names only
      `k.strategy_rejected`. Every other source means two *reasons*. Likely a wording defect.
- [ ] **`[c]` `k.project_timebox`** is `owner-set` in YAML, described as `met` in ROADMAP and
      RISK_REGISTER.
- [ ] **`[c]` `docs/README.md` drift** — says 21 stories (22 exist); marks REGIME_SPEC / EVENT_SPEC /
      CHART_SPEC as planned though all three are written.

## 4. Pending decisions

**Decision records** — DR-007 / DR-008 / DR-010 / **DR-012 / DR-013 / DR-014** are accepted.

- [x] **`[v]` DR-012 — ratified by the owner 2026-08-17.** `exit.atr_stop_multiple = 2.0` and
      `exit.max_holding_period = 20` are in the registry carrying `assumed:DR-012`. Provenance argued
      at length in §4 of the record: **never `assumed:PR-005`** (PR-005 held both as study
      *conditions* and was refuted) and **never `validated`**. The project still has **zero**
      `validated` parameters. Ratification makes the system able to decide; it does not make the
      decisions good. Only `PR-009` can move either value.
      **§8.6 ruled: ONE counter reset, attached to PR #9's merge date, not two.** On `master` as it
      stands these values change nothing at all — `pipeline.py` still carries the literal and never
      reads the registry — so the record merges ahead of #9 with no operational consequence.
- [x] **`[v]` DR-013 — proposal expiry, ruled 2026-08-17.** Unblocks §6b item 5b, which was
      unbuildable without the rule. **Non-critical (`MOVE_STOP`, `PARTIAL_EXIT`) expires after 3
      trading days; critical (`EXIT_NOW`) NEVER expires and never auto-applies.** The split is the
      substance: the two classes fail in opposite directions — expiring an `EXIT_NOW` hides live
      risk, keeping a `MOVE_STOP` alive presents stale arithmetic as current.
      `management.proposal_expiry_days = 3`, `assumed:DR-013`. Expiry is computed **at read time**,
      never written by a job — same shape as `pending`, which is the absence of a response rather
      than a status column. **Still to build** (§6b item 5b).
      The owner chose the wall clock over supersession-by-next-run, which was what was recommended;
      §4 of the record keeps the rejected argument, because supersession ties expiry to the scheduler
      and a week of missed runs would silently extend every proposal's life.
- [x] **`[v]` DR-014 — no owner capital, paper only, Canada deferred. Ruled 2026-08-17.** One answer
      that six open items were all secretly hanging on. **The owner will not trade this system with
      their own money in its current or observable state**; paper / simulated positions are the
      authorised vehicle.
- [x] **`[v]` DR-006 — PARTIALLY RATIFIED 2026-08-22. The book cap is 4R, not 6R.**
      The trade log reopened the anchor. §1 justified 6R as "a catastrophic session costs roughly
      the whole open risk, so about 6R … two and a half such days reach the drawdown pause". Measured
      over PR-005's 26,351 trades: a gap exit loses **−1.692R**, not 1R (clean stop −1.070R, worst
      single gap **−11.78R**, 35% of gaps worse than −1.5R). So a whole-book gap session costs
      **10.15R** and −15R is **1.5 sessions** away, not 2.5. Four positions restores the record's own
      intent: 4 × 1.692 = 6.77R → **2.2 sessions**.
      **Ratified, provenance `owner`:** `risk.max_open_risk` **4R** · `risk.max_concurrent_positions`
      **4** · `risk.max_position_value` **2,500** · `risk.liquidity_cap_order_to_adtv_pct` **1.0%**.
      Free consistency: 4 × 2,500 = 10,000 = `account.equity`, so four max-size positions is exactly
      fully invested — §2 wanted that floor and got it only approximately at six.
      **Why a cap and not a forecast, measured:** 89 sessions hold **52%** of all 3,003 gap exits and
      the worst produced **87 simultaneous** gap-outs, so the risk is correlated — but it is **not
      predictable from anything we hold**. Day-of-week refuted (Mon 23.6% vs 19.2% base, Tue 24.7%).
      Prior realised volatility refuted **and inverted**: clustered days follow *lower* vol (7.09%)
      than ordinary ones (8.40%), and standing down above the ordinary p75 gives **lift 0.59×, worse
      than random**. The reflex to cut exposure when vol rises would have made this worse. Full
      argument in `DR-006` §8.

- [x] **`[v]` The CORRELATION cap is WIRED — built 2026-08-23 (`DR-006` §11).** Item **a** below is
      done. A candidate whose daily returns correlate at or above `risk.correlation_threshold` with
      any OPEN position leaves with `Skip` / `RISK` at step 6b, right after the book cap.
      `risk.correlation_lookback_sessions` = 60 is a **new parameter**: the window had been prose
      inside the threshold's own entry, and that entry carried two `note:` keys, so the loader kept
      the second and the window was not in the loaded registry at all (`DR-006` §7, worse than the
      item said). Both stay `assumed:DR-006` and **unratified** — §8.4's condition was a ruling on
      numbers whose checks run, and building the check enables that ruling rather than replacing it.
      **Four readings are authored and one wants an owner ruling:** it REFUSES rather than resizes,
      and the size adjustment `RISK_SPEC.md` §4 names alongside the threshold is still unspecified.
      The other three — sign kept (`r >=`, not `|r| >=`), the window is the last 60 SHARED sessions,
      and a candidate already in the book refuses at r = 1 — are recorded in §11.3.
      **Do not confuse the two failure directions**: an unset parameter refuses every candidate; a
      pair that could not be measured refuses none and reports `UNAVAILABLE`.

- [ ] **`[v]` DR-006's last one: SECTOR. §3 called it UNEVALUABLE and that is WRONG — it is
      buildable today.** This is the plan; nothing here is blocked on a ruling. Item **a** is done
      (see above) and is kept for the measurement it carries.
      **a. Correlation is not blocked at all. DONE 2026-08-23.** §3 says "nothing computes a
      correlation matrix" — a statement about missing CODE, not missing data. Measured 2026-08-22:
      the full **1152 × 1152**
      matrix over 60 sessions of daily returns builds from the existing store in **0.09 s**. Of
      662,976 pairs, **1.57% sit at r ≥ 0.70**; median r = 0.091, p99 = **0.759**, so the threshold
      is neither vacuous nor over-broad. **Build:** compute it in the allocation path, refuse a
      candidate whose correlation with an OPEN position is ≥ the threshold. Cheap enough to run
      every evening.
      **b. Sector has a free source, and so does the ETF look-through §2 requires.** `yfinance` —
      already this project's only bar vendor — returns sector and industry directly for equities on
      both exchanges (`AAPL` → Technology, `XOM` → Energy, `CNQ.TO` → Energy). And
      `Ticker.funds_data.sector_weightings` returns an ETF's sector composition, which is exactly
      what §2's *`Учитывать ETF и корреляции`* asks for: `SPY` → technology 37.4%, financials 12.2%;
      `VGK` → financials 25.2%, industrials 19.9%.
      **c. THE TRAP, and it must be guarded before any of this is wired.** The vendor returns a
      confidently fabricated answer for bond funds rather than `unavailable`: **`NEAR` → healthcare
      100.0%**, every other sector 0.0%. `NEAR` is a short-maturity BOND fund with no equity sectors
      at all. Consumed naively it would spend the entire healthcare budget on a fiction. **Refuse a
      look-through whose weights are degenerate** (one sector at 100%, or a quoteType that is not an
      equity fund) and report `unavailable` — never consume it. This is the
      `unavailable`-is-not-`fail` rule (`AGENTS.md` §12) at the point where the vendor lies.
      **d. What stays genuinely missing:** the POINT-IN-TIME sector. The vendor serves today's
      classification, not the one in force in 2016. That restricts a BACKTEST and does not restrict
      live admission, and the two must not be conflated the way §3 conflated them.
      **Both parameters stay `assumed:DR-006` and unratified** until the above is built and the owner
      can rule on numbers whose checks actually run.

- [x] **`[v]` The book cap is WIRED — built 2026-08-22 (`DR-006` §9).** `risk.max_open_risk` (4R) and
      `risk.max_concurrent_positions` (4) both name a consumer now:
      `trade_management/portfolio.py:limits`. A candidate that would push the book past either leaves
      with `Skip` / `RISK` at step 6 of `RISK_SPEC.md` §3, after sizing, and the report carries a
      `BOOK CAPACITY` block. The decided-not-wired census fell by two — derive it with
      `python tools/verify_parameters.py`, never from this line.
      **Three owner rulings shaped it, all 2026-08-22, all argued in `DR-006` §9.2:** `open-position`
      REFUSES over the cap and needs `--acknowledge-over-cap "<reason>"`, which is recorded in a new
      append-only `cap_overrides` table; candidates are measured against the open book alone, never
      against each other; a negative open risk frees R-capacity unclamped while the count cap still
      binds.
      **What it made visible rather than introduced:** `positions.open_risk_as_of` sums across
      currencies with no FX conversion, and cannot convert — the dependency law lets that module
      depend only on `platform`. Its docstring now says so and `portfolio.book` is the only converter.
      **Track A restarted 2026-08-22** — one frozen file, and the change moves decision output.

- [ ] **`[v]` `account.fx_rate_cad` is unset, and that now costs more than it used to.** The book cap
      is denominated in R and R is base currency, so a CAD position's risk has no expression at all:
      `open-position` refuses a `.TO` entry, and if one were recorded anyway the whole book becomes
      untotallable and **every candidate in every later run refuses**. Sizing has refused CAD
      candidates on the same parameter since 2026-08-16, so nothing regressed — the surface just got
      wider.
      **Owner, 2026-08-22: worth setting when the time is right.** Not a value any agent may draft
      (`AGENTS.md` §3): a rate is a measured market fact and needs a source and an as-of date. Canada
      is deferred (`DR-014`), so this is not blocking anything today.

- [ ] **`[v]` The book's R excludes round-trip costs and 1R includes them** (`DR-006` §10).
      `Position.open_risk` is `(entry − stop) × shares`; `sizing.allowed_risk` is spent against
      `entry − stop + costs`. So a book measured in R understates by the cost fraction — small,
      one-directional, and in the PERMISSIVE direction. Not corrected in the build, deliberately:
      `ALLOCATION_SPEC.md` §6 rule 6 names `Position.open_risk` as the quantity, and inventing a
      cost-inclusive variant at the call site would put a second definition of open risk in the tree.
      Needs a domain answer, not an implementation one.

- [ ] **`[c]` DR-009** · **`[c]` DR-001 / DR-002 / DR-003 / DR-005** — proposed since 08-02, used as
      working fact throughout.

- [ ] **`[v]` DR-015 is BUILT (2026-08-18), and left two things for the owner.**
      **a. The retry's per-run ceiling is an implementation reading, not a ruling.** §3 states two
      figures that do not agree: "three attempts, 30 seconds apart" is two sleeps and 60 seconds,
      "ninety seconds" is three. The attempt count is stated twice so it governs per instrument;
      ninety seconds is implemented as a ceiling on the **run**, spent across it. **Why a ceiling at
      all:** the wrapper is called per instrument, the universe was 1152 members on 2026-08-17, and
      unbounded that is over nineteen hours of sleeping in a vendor outage — on a job that must
      finish before `DR-015`'s own 19:30 pass. §7 of the record carries the argument.
      **The question: 90 seconds per run, or the full three attempts for every instrument whatever
      the total?** Nothing else is blocked on the answer.
      **b. Register the 19:30 task.** One `schtasks` line, on the machine that runs the schedule — a
      repository cannot create it. `docs/runbooks/README.md` §1a has the command and the check.
      **Until it exists the retry inside the run is live and the second pass is not**; the two halves
      of §3 are independent.

**ADRs — all four unratified.**

- [ ] **`[c]` ADR-0001** market data · **ADR-0002** calendar · **ADR-0003** schema language ·
      **ADR-0004** storage engine.

**UDRs — three open.**

- [ ] **`[c]` UDR-004** (see §2) · **UDR-001** (blocked on the owner's forthcoming book) ·
      **UDR-002** (graph DB choice, owner input). UDR-003 / UDR-007 closed.

**Owner-pending.**

- [ ] **`[c]` Course v7.0 adoption** — 7 unexecuted steps, deferred by owner ruling.

## 5. Studies

- [ ] **`[c]` PR-007** registered, unreported.
- [ ] **`[c]` PR-009** registered, blocked on Task 8.
- [ ] **`[c]` Four prereg ids unwritten:** PR-001b (unblocked, writable now) · PR-003 (needs a daily
      return series) · PR-004 (needs ~100 journalled trades) · PR-006 (needs a forward test).
- [ ] **`[v]` `PR-011` — screening out the instrument classes that cannot hold a stop — IS NOT
      WRITTEN.** Migrated here 2026-08-22 from `SESSION-HANDOFF-2026-08-22.md` §3 before that file
      was deleted; it lived nowhere else, which is why it is now in the one open-work list
      (`AGENTS.md` §10.7).
      **The finding it rests on:** the gap rate is not a general property of holding overnight. It
      splits hard by instrument class — bond ETFs **27.4%**, foreign-market ETFs **23.3%**, US single
      names **7.5%** — and both bad classes have a mechanical cause rather than a statistical one. A
      bond ETF's 2×ATR stop is 0.57% of price while round-trip costs eat 88% of it; a foreign ETF's
      underlying trades while the US market is shut, so the stop is unenforceable by construction.
      **The trap, and the reason this is a pre-registration rather than a change:** excluding those
      classes flips the sign of mean net R (−0.0691 → +0.0362) **on the fitted data**. That number is
      post-hoc and **must not be adopted as a finding**. A screen justified by a mechanism is
      registerable; a screen justified by the sign it produces on the sample that suggested it is
      the thing pre-registration exists to stop.
- [ ] **`[c]` Prereg id-reservation has no gate** — three ids have already collided.
      `docs/prereg/README.md`:52 says "worth fixing if a third one appears." A third has appeared.
- [x] **`[v]` PR-002's verdict corrected to `INCONCLUSIVE` — 2026-08-16, council-reviewed.**
      §6 permits `accept` only on both countries; the third amendment (pre-run) assigned a
      single-market result to the `inconclusive` branch; the runner implemented the percentile
      thresholds with no country condition and emitted `accept`. Corrected in `PR-002.json` (original
      verdict preserved) and in the report via `PR-008`'s strikethrough + Correction precedent.
      `regime.classifier_rule` → **`assumed:PR-002`**; **the project now has zero `validated`
      parameters**. `run_pr002.py` now encodes the condition, with a regression test proven to fail
      when it is removed. Cascade fixed in CONSTRAINTS, GLOSSARY, REQUIREMENTS, PARAMETER_REGISTRY,
      REGIME_SPEC, RULE_SPEC.
      **The artifact was deliberately NOT regenerated:** `run_pr002.py` fetches the current directory
      and current Yahoo history, so a re-run samples a different universe over a different window —
      it would replace a reported result rather than reproduce it. Three of five council advisors
      recommended re-running; that would have destroyed the evidence record.
- [ ] **`[v]` PR-002's registered perturbations were not all run.** §5 registers threshold ±20%,
      1-bar execution delay, and cost stress. Only cost stress (1×/3×) is implemented in the runner.
      **So the original `ACCEPT` rested on one of three registered robustness checks** — a defect
      independent of the country condition, and not fixed by the 2026-08-16 correction. Needs a new
      run, which means a new pre-registration: the runner cannot reproduce the 2026-08-02 sample.
- [x] **`[v]` Nothing bound a runner to its own pre-registration — gate 25, 2026-08-16.**
      All five council reviewers converged on this independently as the root cause. Gates 13/14
      check that *documents* agree with the result files; nothing checked that a *verdict* was
      derived using the branches and perturbations its prereg registered. PR-002 failed both — wrong
      branch, 1 of 3 perturbations — and every gate stayed green.
      `tools/verify_prereg_conformance.py` refuses an affirmative verdict over a declared scope
      shortfall (PR-002's exact shape) or with registered perturbations unrun, and requires every
      reported study to state its scope. **It does not parse prose** — a prereg is written for a
      human, and a gate that guesses at English gets bypassed; the obligation is inverted so the
      *result* declares what the prereg constrains. Five tests, each proven to fail on its condition.
      It found a real gap on first run: `PR-010.json` stated no scope at all.
- [x] **`[v]` Every study now declares which registered perturbations it ran — 2026-08-16.**
      Backfilled from each pre-registration and each runner's source, so gate 25's condition 4 gates
      the present tree instead of a hypothetical future study. **The backfill found a second
      undetected instance:** `PR-001` registered "SMA periods moved ±20% (parameter stability)" and
      `run_pr001.py` fixes `SMA_SHORT = 50` / `SMA_LONG = 200` with no sensitivity loop; its report
      never mentions the check. Its `reject` rests on one parameterisation.
- [ ] **`[v]` Two studies rest on fewer checks than they registered.** Gate 25 prints this on every
      run (permitted — concluding less than you registered is always allowed — but the verdict is
      weaker than its report implies):
      `PR-001` unrun `sma_periods_pm20pct` (`overlap_per_regime` was conditional on a classifier
      that did not exist at run time, so it was not runnable rather than skipped) ·
      `PR-002` unrun `thresholds_pm20pct`, `execution_delay_1bar`.
      Both need new runs, which means new pre-registrations: neither runner can reproduce its
      original sample (both fetch the current directory and current Yahoo history).

## 6. Code & gates

- [x] **`[v]` 6.1 — `HANDOFF.md` §2 is generated, not typed.** Done 2026-08-15.
      `tools/build_state.py` + gate 24 (blocking), built on `verify_counts.measure()` and
      `track_a_streak.measure()` so no fact has two implementations. Two blocks: repo-derived
      (everywhere) and `data/`-derived (main checkout, or point `SWINGDESK_DATA` at it).
- [x] **`[v]` 6.2 — Gate 23 no longer reports a false negative from a worktree.** Done 2026-08-15.
      A missing log returns `UNAVAILABLE` (exit 4), not 0, and the suite refuses to print "all gates
      pass" when a gate could not see its subject. `SWINGDESK_DATA` lets a worktree read the real
      stores; it is deliberately **ignored when `SWINGDESK_ROOT` is pinned**, so the test suite stays
      hermetic — three tests caught that ordering the moment it was written the other way round.
- [x] **`[v]` US-022 finished — 2026-08-15.** `report.py` now imports `presentation.funnel` and
      renders a FUNNEL block: eligible/measured/admitted/evaluated in the gherkin's documented order,
      Trade/Watch/Skip/Pause, skip causes broken out by `(code, parameter_id)`, changed/first-sighting,
      and `is_reconciled` checked in the render (not asserted in the pure module) so a broken
      invariant is seen, not raised mid-run. Prints on a run with zero candidates too — zero stated,
      not silence. 4 new tests against the story's own gherkin, `verify_docs.py` gate 3e passes
      (citing US-022 without checking it was live). All 29 gates pass, 407 tests.
- [ ] **`[v]` MEASURED 2026-08-17: 3 of 11 mutants survive the entire test suite.** The council's
      own flip condition, turned from an assumption into a number. Method: patch one computed
      quantity per module in committed source, run the **whole** suite, restore, record whether
      anything died. **`git stash push -- src/` cannot do this** — it reverts *uncommitted* work, so
      on a clean tree it stashes nothing and the suite runs unchanged. That is precisely why
      `AGENTS.md` §12's ritual only ever applied to newly written tests, and why auditing the
      existing 480 needs real mutants.
      **The three survivors, and they are not one kind:**
      • `sizing.py` — `planned_risk` replaced with the constant `Decimal('42')`. **The R denominator
      the entire validation programme is expressed in.** 480 tests green.
      • `sizing.py` — `risk_per_share = entry - stop + costs` → `entry - stop`. Green.
      • `calendar.py:112` — `sessions_behind` returning `max(0, len(window) - 1)`. Green, **and for a
      different reason: the function has no caller anywhere in `src/`** while
      `DATA_QUALITY_SPEC.md`:40 defines staleness through it (`sessions_behind > 0 means stale`). A
      spec rule implemented in dead code. That is a third disease, and the mutation method surfaced
      it by accident.
      **Killed (properly asserted):** `exits.py` stop distance and holding-period comparison,
      `position.py` `open_risk`, `atr.py` true range, `pivots.py` confirmation lag,
      `universe.py` ADTV window and `vendor_symbol`, `directory.py` departure set.
      **What this decides:** survivors on the live decision path *are* concentrated in `sizing.py`
      (2 of 2 there), so a declared-critical-surface gate would catch the ones that matter — but 27%
      overall, and one survivor outside the surface, means a hand-authored list is **regression, not
      detection**. It re-checks defects someone already thought of. `Decimal('42')` came from a human
      hypothesis no machine would have scheduled. The detector that actually worked this session was
      a **cross-module property test** asserting the *equality* of two implementations rather than
      either value — it found the zero-stop sizing defect nobody had hypothesised, on its first run.
      **Build order therefore: seam properties first (detection), mutant list second (cheap
      insurance).** If the mutant list is built, three non-negotiables from the council's peer
      review: a patch that fails to apply is **FAIL** never skip (an exact-string mutant rots on the
      next rename, and a gate that mutated nothing is `(net/x)*x == net` one layer up); it ships with
      one planted survivor proving it can go red; output is named survivors with diffs, never a score.
- [x] **`[v]` Gate 11 checked `spec` for string length while resolving `implements` for real —
      fixed 2026-08-18.** Every one of the seven implemented components pointed at a heading that
      does not exist (`ALGORITHM_SPEC.md#atr`, `#sma`, `#swing-high`, `#swing-low`,
      `REGIME_SPEC.md#classifier`, `#breadth`, `SCREENER_SPEC.md#trend-filter`). The ladder defines
      `specified` as "algorithm spec written", so all six `specified` rows stood in a state they had
      not earned, for months, behind a green gate.
      **What the investigation actually found is better than the defect.** The specifications were
      not missing — **five of the seven carry the full eleven-field `ALGORITHM_SPEC record` in their
      own module docstring**: `atr`, both pivots, `moving_average`, `breadth`. `ALGORITHM_SPEC.md`
      §7 had been asking whether specs belong in that document or beside the code; the tree had
      answered years-of-habit ago and nothing had written it down. §7 item 1 is now closed:
      **beside the code, under the `ALGORITHM_SPEC record` marker.**
      `spec:` now takes two forms and **gate 11 resolves both by content** — a `.md#anchor` must name
      a heading that exists, a `.py` path must carry the marker. A module that does not is the same
      false pointer one file type over.
      **`regime` and `trend` carry no record and were demoted** `specified` → `registered`, `spec`
      nulled. **A documentation status, not a deletion** — the code is untouched, still imported,
      still golden-vectored. What was removed is the claim that a specification was written.
      **CORRECTION, 2026-08-18.** The demotion commit justified this as "both serve the entry-filter
      family closed by evidence". That is true of `trend` and **false of `regime`**:
      • **`trend`** — closed as a per-signal entry filter. `PR-001` and `PR-005` both refuted the
      trend-definition family and `screen.trend_definition` stays `unset`.
      • **`regime`** — **not closed.** `regime.classifier_rule` is SET (`assumed:PR-002`,
      `BREADTH_MEDIAN` split at 0.647), and `PR-002`'s verdict was corrected to INCONCLUSIVE, not
      refuted.
      • **`breadth`** — **parked, not killed** (`HANDOFF.md` §5), and explicitly revivable **as a
      portfolio participation gate — never a per-signal entry filter**.
      So the demotion stands on its own evidence (no record in the module, so `specified` was a
      false claim) and NOT on the reason first given. Regime has a live future role; it is at the
      portfolio level, not the instrument level.
      **Neither is consumed by the live path today** — zero references to `regime`, `trend` or
      `breadth` in `pipeline.py` or `report.py`. Today's Watch/Skip is produced with no regime input
      at all, which is a fact worth knowing before anyone assumes the report reflects one.
      Census moves 458/6/1 → 460/4/1.
      5 tests; the three that assert a *failure* confirmed red against the pre-fix check, the two
      positive controls confirmed green. Restored from a file copy, never `git checkout` — see the
      process note under proposal expiry.
- [ ] **`[v]` Six gates have never been proven able to fail.** `tests/test_gates.py`'s own docstring
      sets the bar — *"A gate that has never been seen red proves nothing"* — and these have zero
      references in it: `verify_parameters` (1), `verify_transcription` (2), `verify_docs` (3e),
      `verify_studies` (3f), `verify_criteria` (3g), `verify_components` (11).
      Measured 2026-08-16 while auditing for the failure mode that bit three times this session
      (gate 23 blind, `build_state` v1, gate 25 v1). **They are not blind in that sense** — every one
      reports what it examined, which is the existing honesty mechanism, and 3f demonstrably caught
      real defects during the PR-002 correction. What is missing is proof that their conditions can
      fire, which is a different and weaker gap than the one already fixed. Fixture-and-assert tests,
      one defect each, in the pattern the file already uses.
- [ ] **`[c]` Gate 10** (traceability) — unblocked now that ATR is active, still to build.
- [ ] **`[c]` Gate 22** + `DR-008`'s remaining machinery · **Gate 14's word-number hole.**
- [ ] **`[c]` 6 specified components awaiting activation** — pivots (M12-T0201, M12-T0202), moving
      average (M25-T0382), regime (M30-T0450), breadth (M31-T0459), trend (M33-T0485). All have real
      implementations.
- [ ] **`[c]` `tools/` under mypy** (100 errors, 21/28 files) · structured logging · backup/restore ·
      chaos scenarios · breadth card (parked) · `sizing.py` cost-model swap.

### Correctness findings from the 2026-08-15 review — all `[v]`

- [x] **`[v]` Live path silently defaulted the exit policy — fixed 2026-08-16.** `_exit_policy()`
      reads `exit.atr_stop_multiple` and `exit.max_holding_period` and REFUSES when unset. **They
      were unset when this was written and were ratified 2026-08-17 (`DR-012`)**, so the refusal
      path is now the exceptional one rather than the only one.
      Candidates Skip with the parameter named; open positions PAUSE rather than being managed on an
      invented stop. Old behaviour `pipeline.py`:289 and :369 both use
      `exits or ExitPolicy(Decimal("2.0"), 20)` — a hard-coded constant with no registry read and no
      provenance, while `exit.atr_stop_multiple` and `exit.max_holding_period` are both `unset`.
      This is a no-silent-default violation sitting in the production path. **Was a frozen file
      queued behind the freeze; the freeze lifted 2026-08-17 and PR #9 merged the same evening.**
- [x] **`[v]` Sizing stop and exit policy disagreed — fixed 2026-08-16.** One policy for the whole
      run: the candidate path now sizes with `policy.stop_for()`, the same distance management and
      the checklist use. Old behaviour `pipeline.py`:343 sizes against `close − 1×ATR`;
      the exit policy everywhere else is `2×ATR`. No shared strategy card reconciles them.
      **Frozen file.**
- [x] **`[v]` CAD is sized against USD with no FX — fixed 2026-08-16 (PR #9).** `size_long` treats CAD as supported, so a `.TO`
      candidate's `risk_per_share` and `position_value` (CAD) are compared against `account.equity`
      (USD) and `risk.max_position_value` with no conversion and no rate recorded. It does not
      refuse — it mis-sizes. **Frozen file.**
- [x] **`[v]` `Position.initial_risk_per_share` excluded costs — fixed 2026-08-16.** Now
      `entry - stop + costs`, with `initial_costs_per_share` stored at entry and frozen with the
      denominator. No migration needed: `positions.duckdb` has never been written, so there were no
      legacy rows. Old behaviour (`entry − stop`) while `size_long`
      includes them (`entry − stop + costs`). Two different R denominators.
- [x] **`[v]` `output_hash` did not cover the numbers that determine the trade — fixed 2026-08-16.**
      Found by changing every stop from 1×ATR to 2×ATR and watching the hash NOT move, then measured
      three more ways: halving every share count and widening every stop 40% both left the golden
      case at `78732401bd216ae2`, and a run proposing `EXIT_NOW` on a held position hashed
      identically to a run holding nothing — the position half of the run, which runs *first*, was
      absent from the payload in every form, including its own existence. Gate 9 passed in all four
      cases while `a.reproducible` claimed byte-identical reproduction. Now covers entry, stop,
      shares, planned risk, and every position and proposal; prose, checklists and timestamps stay
      out as the churn guard (`DETERMINISM_SPEC` §7.2, which this closes as an open item). The
      golden baseline was re-recorded deliberately: `78732401bd216ae2` → `4751a227d2a14884`. Four
      tests assert the hash MOVES, each confirmed to fail against the old payload. **Frozen file.**
- [x] **`[v]` `size_long` sized against a zero or negative stop — fixed 2026-08-17 (PR #9).**
      `stop >= entry` was the only stop check, so `size_long(1.00, 0.00)` returned **98 shares**
      against a risk-per-share of 1.02 — larger than the entry price itself — and a stop of −5.00
      was accepted too. `Position.initial_stop` is `gt=0`, so the two contracts disagreed: the run
      would size and propose a trade the store could never record.
      **Reachable, not hypothetical.** The stop arrives as `entry − atr_stop_multiple × atr`, so any
      instrument whose ATR exceeds half its price at a 2.0 multiple crosses zero, and
      `universe.min_price` of 5.00 does not exclude those. Now a coded `STOP` refusal.
      **Found by the cross-module property test below, on its first run** — which is the argument
      for that test, not a coincidence. **Frozen file; folded into PR #9 rather than sent as its own
      PR, because both touch `sizing.py` and the 2026-08-16 amendment resets the Track A counter per
      *merge* to a frozen file — two PRs would have cost two resets.**
- [x] **`[v]` Nothing asserted that sizing and `Position` agree on the R denominator — added
      2026-08-17.** `test_sizing_and_position_agree_on_the_denominator` (`tests/test_invariants.py`)
      pins the equality across the module boundary the defect above it lived in. Both sides were
      separately correct-looking; the disagreement existed only in the gap between two modules, which
      is exactly where a per-module test cannot look. It asserts the *equality* rather than either
      value, so it survives any change to the cost model. Confirmed red against the pre-fix tree.
- [ ] **`[v]` Two formulas for R, differing by a quantization step.** Found 2026-08-17 by the test
      above. `r_multiple(net, snapshot)` divides by `planned_risk`, which `size_long` quantizes to
      cents; `Position.r_at(price)` divides by `initial_risk_per_share`, unquantized. So
      `Position.initial_risk` reads `99.9648` where `planned_risk` reads `99.96` for the same trade,
      and the two R values differ around the sixth decimal place.
      **Immaterial to any decision and deliberately not fixed in PR #9** — sub-cent, and the fix is a
      choice about which is authoritative rather than a bug fix, on a file already under the freeze.
      It is still one quantity with two implementations, which is what Production Rule 3.8 forbids.
      The test asserts agreement to the cent and names the asymmetry inline.
- [x] **`[v]` A test fixture disagreed with DR-010 at its own entry price — fixed 2026-08-17.**
      `tests/test_positions.py::_position` set `initial_costs_per_share=0.25` and its comment called
      that "DR-010's USD floor", but DR-010 charges `max(floor 0.25, 50bp × entry)` and at the
      fixture's entry of 100 the bp term (0.50) binds — the floor governs only below a 50 entry. The
      fixture the cost-inclusive denominator is demonstrated on therefore modelled a cost `size_long`
      would never charge it. Now 0.50, which is what `size_long(100, 96, "USD")` freezes.
      `tests/test_cli.py::_seeded` got the same treatment at its 300 entry: 1.50, not the floor.

- [ ] **Instrument identity is synthesized instead of resolved — two defects, not one.** Restated
      2026-08-16 after checking each site; the earlier entry named the wrong pair of lines and
      missed (b) entirely. `reference_data/universe.py:159` `to_instrument()` is the *correct*
      construction — `id` from the `DirectoryStore` symbol, `ticker` from `vendor_symbol()` — and
      both sites below bypass it.
      - **(a) `cli.py`:29 really does derive `id` from what the user typed**, which the contract
        forbids ("Never derived from the ticker alone"). Typing `BRK-B` mints id `BRK-B`; the
        universe path calls the same instrument `BRK.B`. That is two identities for one instrument
        in a bitemporal store, which cannot be un-split after the fact. Not yet triggered —
        `bars.duckdb` holds 12 dotted ids and **zero** dashed — but one CLI invocation away.
      - **(b) — fixed 2026-08-16.** `pipeline.py`:99 `_held_instrument()` never derived the id (it
        preserves it); it derived the *vendor ticker* by stripping `.TO`, so a held `BRK.B` asked
        Yahoo for `BRK.B` where the vendor wants `BRK-B`. The fetch raised `VendorUnavailable`, the
        `except` fell through to the stored bars, and the position went on being managed against
        data that had quietly stopped refreshing — worse than failing, because it looks identical
        to working. Now uses `vendor_symbol()`, the same mapping the universe path uses, which is
        exactly the fix `DR-003` gap 2 applied there and missed here. Needed no directory and no
        owner decision, so it landed ahead of (a). **Frozen file.**

      **(a) is blocked on `DR-003` gap 1, not on an engineering choice.** Resolving identity means
      resolving against a directory, and `DR-003` already records that Canada has no free symbol
      directory in hand — so a `.TO` instrument has nothing to resolve against, and fail-closed
      would refuse every Canadian candidate. Owner's call 2026-08-16: **source a TSX directory
      first**; identity resolution waits on it. That makes `DR-003` gap 1 a blocker for a second
      thing now — the US-only universe *and* instrument identity — and it needs its own decision
      record when a source is evaluated. Blocks any historical edge claim; does not block
      Track-A-only PAPER. **Changes the daily-run path — behind the freeze.**
- [ ] **11 of 13 journalled runs carry `code_dirty = true`.** `a.reproducible` requires a
      byte-identical re-run from a stored manifest; a manifest pointing at a dirty tree cannot be
      replayed from its SHA.
- [ ] **4,486 of 4,510 recorded Skips are `RISK / risk.per_trade_pct`** — unset-parameter refusals,
      i.e. a system fault rather than market judgment. That parameter was set 2026-08-11. Any
      statistic over the decision history must segment these out first.
- [ ] **Tests cover the safe branch of the risky code, three times over.** See §8.

## 6b. The operational chain — what a full cycle needs

**COMPLETE as of 2026-08-18.** Every buildable item below is done, and the one remaining open entry
(3c, off-desk reach) is a deliberate non-goal rather than a gap — `DR-011` decided it and preserves
the whole analysis so nobody redoes it. The chain ran end to end on 2026-08-17, which is the
condition the 2026-08-16 council set before research resumes; `DR-014` then reordered what "resumes"
means. **It has not run with owner capital and will not** (`DR-014`).


Traced end to end 2026-08-16, not just the pipeline internals: `daily_run.cmd` → `cli.py scan` →
`report.py`. **BUILT and gated** (30/30 gates, 435 tests): candidate screening, sizing, exit-policy
computation, checklist generation, report rendering, journal evidence, replay/determinism. **NOT
built or wired**, despite the pure logic mostly existing and being unit-tested in isolation — this
is the gap the council's suspend-research call (§1) is about, and the build order it recommended:

- [x] **1. `PositionStore.record()` had no caller anywhere outside tests — fixed 2026-08-16.**
      New `swingdesk open-position TICKER --entry --shares --stop [--opened-on --costs-per-share
      --strategy --position-id --as-of]` command. `initial_costs_per_share` defaults to the DR-010
      formula (`sizing._costs_per_share`, reused rather than reimplemented — `AGENTS.md` §10.5),
      overridable once a broker confirmation names the real cost. `position_id` defaults to
      `POS-<instrument id>-<opened-on>`, which doubles as a guard: a same-instrument same-day
      re-run hits the store's own append-only rejection and refuses cleanly (exit 2) instead of
      duplicating. An invalid stop (`Position`'s own validator) refuses the same way. 6 new tests
      in `tests/test_cli.py`, each confirmed to fail when the command is stubbed out.
      **Branched from PR #9** (`claude/correctness-fx-and-r-denominator`), not master — this needed
      `initial_costs_per_share` on `Position`, which only exists on that branch. So the R
      denominator every position opened through this command reports is cost-inclusive from day
      one; nothing gets written under the old, cost-exclusive schema. **Consequence: this PR cannot
      open against `master` until PR #9 merges** — its diff would otherwise show PR #9's frozen-file
      commits as its own. Held, not blocked: `cli.py` and the tests are ready; rebase onto `master`
      once PR #9 lands, then open normally.
      **2026-08-17: merged the corrected PR #9 in, and the merge broke the command silently.** Master's
      #14/#15 pulled the scan path out of `main()` into `_scan()` (which returns a 3-tuple so the
      notifier can run after the stores close). This block was written against the older inline
      `main()`, so the textual merge dropped it **inside `_scan()`, after that function's own
      `return`** — dead code. ruff clean, mypy clean, every gate green, and every `open-position`
      invocation fell through to `main()`'s final `return 1` printing **nothing at all**. The six
      tests above caught it; **no gate would have**, and neither would review of a diff that shows
      only an import collision. Extracted as `_open_position()` beside `_record_fill`/`_pending`/
      `_respond` and wired into the dispatch; confirmed by deleting the dispatch line again and
      watching the same six go red.

**And the chain closed. `TODO.md` §1's condition for resuming research is met — 2026-08-17.**
Run end to end on a **copy** of the real bar store (live stores never opened for write), with
DR-012's values set locally and reverted afterwards:

| Step | Command | What happened |
|---|---|---|
| 1 | `open-position AAPL --entry 305.59 --shares 5 --stop 290.32` | `POS-AAPL-2026-07-15` recorded, costs `1.5280`/share, R denominator `16.7980` (`83.99` total) |
| 2 | `scan AAPL` | position evaluated **before** candidates; proposed `exit_now`, code `TIME` |
| 3 | `pending` | the observation, the rule, the two bounded choices |
| 4 | `respond … --approve --reason …` | recorded and applied — version 2, `closed 2026-08-17` |
| 5 | `record-fill … --price 311.20 --shares 5` | fill recorded; `slippage UNAVAILABLE — the plan named no price to slip against`; `open risk 0 across the book, recomputed` |

Step 5 is the one to read twice: it **refused to manufacture a slippage number** for a
maximum-holding-period exit, printed the reason, and recomputed the book rather than decrementing
it. The design held under a real run, not just a fixture.

Two things this does NOT establish, stated so the next session does not over-read it: no owner
capital was involved, and it ran on a store copy under a pinned clock. It is the chain proving it
closes, which is exactly what the council's suspend-research call asked for — not a trade.
- [x] **2. `cli.py scan` never opened a `PositionStore` or passed `positions=` into `run()` —
      fixed 2026-08-16.** Now opens `PositionStore(args.data / "positions.duckdb")` alongside the
      existing `BarStore`/`Journal` and passes it through. `cli.py` is not a frozen file, so this
      did not need to wait behind the freeze. Item 1 (position entry) is still open, so the store
      the scheduled job now reads is empty — this is what stops that being the reason a recorded
      position could never be evaluated, not a claim that one exists yet. 2 new tests
      (`tests/test_cli.py`, new file — there was no CLI test coverage at all before this), each
      confirmed to fail against the pre-fix `cli.py`.
- [x] **3a. The report was never persisted — fixed 2026-08-16.** `scan` now writes one file per
      run to `<data>/reports/<run_id>.txt` (`--report-dir` overrides). The `run_id` already carries
      the start instant, so the name sorts chronologically and traces to the journal's `runs` row
      without formatting a second copy of the date (`AGENTS.md` §10.5). A write failure is loud on
      stderr but **not** fatal — the report was still produced on stdout, so `a.run_completes` is
      satisfied and a disk error must not reset a 20-day counter. `tools/daily_run.cmd` is
      untouched (it is frozen; it did not need to change). This also corrected `ROADMAP.md`'s
      finish-line row, which read **done** on the strength of the run merely *rendering* something.
      4 new tests, each confirmed to fail when persistence is stubbed out.
      **Still text, not the HTML/PDF `PRODUCT_SURFACES` §3.1 names** — deliberately, because a
      second rendering path for the same run is the defect this project keeps finding under other
      names. HTML waits for one renderer with a text and an HTML backend.
- [x] **3b. Nothing actively notified the owner — fixed 2026-08-16 (`DR-011`), council-reviewed.**
      `scan` now raises a **local** Windows desktop notification; `--no-notify` suppresses it. No
      token, no dependency, no network call, nothing leaves the machine.
      **The owner's first instruction was to reuse TradAlert's Telegram bot, and the council
      changed that answer.** Its chairman named one assumption that would flip the whole design —
      *is the owner at the machine at 18:30?* — the owner answered **yes**, and Telegram then
      bought nothing but off-desk reach that nobody needed. What it would have cost, all verified
      against the tree rather than argued: `SECURITY.md` §2.1 forbids a secret in the repo and
      `verify_secrets.py` records that **this repo is public**; §3.4's binding property is *never
      stores* and Telegram retains a searchable log on a third party's server, so the obvious
      "content, not transport" amendment would have been **false**; and one bot token is one
      `getUpdates` stream, which TradAlert's approve/reject buttons already own.
      Content rule: a terminal status and the run id, **enforced by `body()`'s signature** — two
      parameters, so no `RunResult` is in scope to interpolate — plus a test on the rendered
      string. §3.4's privacy reason is moot locally; the rule is re-earned on `CHARTER` §4 ground:
      a glanceable summary is one the owner can act on without the report's provenance and
      Untested banner. Failure is loud on stderr, never fatal, with a subprocess timeout — the
      hang case `set RC=%ERRORLEVEL%` does *not* protect against. `daily_run.cmd` untouched
      (frozen, and it did not need to change). 13 + 3 new tests.
      **Found while writing `DR-011`:** §3.4 banned "market data … or decisions" and then gave as
      its own example *"the daily run finished, 3 candidates"* — a count that is both. Corrected by
      strikethrough-and-append; left in place it was a standing instruction to reintroduce exactly
      what the rule forbids.
- [ ] **3c. Off-desk reach is deliberately NOT built.** If "I'm at the machine at 18:30" stops
      being true, re-open `DR-011` — its §1 preserves the whole Telegram analysis so the next
      session does not redo it. Firebase remains specified in §3.4 and unbuilt.
- [x] **4 + 5. The approval loop — built 2026-08-16.** They were one invariant pretending to be two
      items: *nothing is applied without a recorded response* spans both, so they landed together.
      `swingdesk pending` lists unanswered proposals with what US-010 requires to answer them (the
      observation, the rule that produced it, the bounded choices — exactly two).
      `swingdesk respond POS-N SEQ --approve|--reject --reason "…"` records the answer and, on an
      approval, applies it through `manage.apply_approved()` — which until now was built, unit
      tested, and **called from nowhere but tests**, so no decision the owner made could reach the
      store.
      **The response is a separate append-only table, not a status column updated in place.**
      `management.status` records what the *run* proposed and has to stay readable as that forever;
      rewriting it to `approved` would destroy the record of what was asked, which is half of what
      an audit trail is for. It also had nowhere to put what rule 3.8 demands — the owner's reason
      and the moment they answered are different facts from the system's reason and when it asked.
      Verified after a real approval: position versions `[1, 2]`, proposal still reads `proposed`,
      response reads `approved | trend intact | 2026-08-16`.
      The primary key is the proposal being answered, so a second answer is refused **by the
      schema**. `pending` is the *absence of a response*, never `status = 'proposed'` — the first
      definition would have left every answered proposal pending forever. `proposal_at()` reads by
      sequence rather than list position: sequences are monotonic, not contiguous, and indexing
      would have applied the owner's answer to a different proposal than the one they read.
      16 tests, each confirmed red against the unbuilt feature — including two that first passed
      for the wrong reason, because argparse raises `SystemExit` for an unknown command too.
      **Channel: the CLI, locally.** `DR-011` established the owner is at the machine; a Telegram
      approval surface would re-open every question that record settled. `PRODUCT_SURFACES` §3.3
      still names Telegram for this and remains unbuilt.
- [x] **5b — PROPOSAL EXPIRY. Built 2026-08-18.** *(The name is the fix for the name: "5b" is a
      nested list index that tells a reader nothing. It is proposal expiry.)*
      `manage.is_expired()` decides it, `DR-013` rules it, and nothing writes `ActionStatus.EXPIRED`
      to a row — expiry is computed at READ time, the same shape `pending` already uses by defining
      pending as the ABSENCE of a response rather than a status column. There is no daemon here to
      write a stored value, so a stored one would be correct only until nobody was looking.
      **Sessions, not calendar days.** A proposal made Friday is answerable Wednesday and expires
      Thursday. Counting calendar days would expire proposals across exactly the intervals in which
      no bar existed and no risk could have changed.
      **`EXPIRING_KINDS` is a whitelist, deliberately** — `MOVE_STOP` and `PARTIAL_EXIT` only.
      `EXIT_NOW` never expires (`DR-013` §2.1: it would convert the system's loudest statement into
      silence). `PAUSE` was not classified by `DR-013`, so it inherits the fail-closed side rather
      than a classification this module invented.
      `pending` **shows** expired proposals rather than dropping them, and prints `AGE UNKNOWN` on
      stderr when the rule cannot be applied at all. `respond` refuses **before** recording the
      answer — the store's primary key means a recorded response cannot be taken back, so a
      refusal after the write would arrive too late to matter.
      `pending --as-of` added, so staleness is testable at a pinned instant like every other command.
      5 new tests. Two assert the ABSENCE of expiry and so cannot go red against an unbuilt feature;
      both were instead proven against **mutated** implementations (`EXIT_NOW` made expirable, and
      the off-by-one flipped to `>=`).
      **A process defect worth more than the feature.** The first mutation round restored the file
      with `git checkout -- manage.py`, which reverts from the INDEX — and the new function was
      never staged, so the "restore" deleted it. The second mutation then "failed" for the wrong
      reason entirely. Caught only by the full gate suite, which reported `AttributeError: module
      has no attribute 'is_expired'` in 12 tests that had passed targeted minutes earlier.
      **Restore from a copy, never from git, when the ritual's subject is uncommitted.**
- [x] ~~**5b. Nothing expires a proposal.**~~ `ActionStatus.EXPIRED` exists and is never written. A
      stop move proposed on a stale observation stays answerable indefinitely, so an owner
      returning after a week can approve a trail computed against week-old bars. Needs a rule for
      how long a proposal stands.
- [x] **6. US-011 — built 2026-08-16.** `swingdesk record-fill POS-N SEQ --price --shares
      --commission` records what the broker actually did. All three clauses:
      **(a) fill price, shares, commission and slippage recorded** — new `Fill` contract and a
      `fills` table keyed on the approved action it settles, so a fill cannot exist for something
      nobody approved (D6 from the far side of the trade). An unapproved *or rejected* action is
      refused.
      **(b) open risk recomputed across the whole book, never decremented** —
      `PositionStore.open_risk_as_of()` sums the latest version of every open position. Tested
      against a partial exit *and* a trailed stop at once: a decremented running total would still
      read the original 250 minus something and would not know the stop had moved.
      **(c) slippage in R against the ORIGINALLY planned risk** — the denominator never moves,
      so the same dollar miss does not look worse as a position is scaled out.
      **The planned price comes from the ACTION, never from the reporter.** A reference supplied
      after seeing the fill is one that can always be made to look acceptable.
      **And it refuses to compute slippage when the plan named no price.** `EXIT_NOW` is proposed
      for two different reasons: a broken stop, where the stop *is* the reference; and a maximum
      holding period, which is an exit at market and names no price at all. Reporting `0.00` for
      the second would be a manufactured measurement — and it would flatter the strategy, because
      unknown slippage is not absent slippage. `slippage_per_share` returns `None`, and the CLI
      prints `UNAVAILABLE` with the reason. 12 tests, each confirmed red against the unbuilt
      feature.

**An idea from the council's peer review, not yet scoped:** route items 1 and 4-6 through a path that
can carry shadow/paper positions, so the chain can prove itself closes end-to-end without waiting on
the owner's real capital — resolves the "necessary but not sufficient" ceiling multiple advisors
named (closing the loop still depends on the owner actually trading, which is outside code).

## 7. The documents' own open questions

186 items across 61 files. **Not inlined here** — inlining them would make this file the seventh
copy. Load-bearing ones are promoted into §3 and §4 above as they are triaged; the rest stay in
their own documents until promoted.

Load-bearing, not yet promoted: `ALLOCATION_SPEC.md`:191 (`rs.ranking_method` needs a
pre-registration, not a DR) · `ENTITY_MAP.md`:91 (22 vs 24 entity count) ·
`DECISION_STATE_MACHINE.md`:115 (watchlist transition graph) · `VENDOR_COMPARISON.md` (4 blocking
items before it can be frozen) · `POSTMORTEM-2026-08-09.md` §5 item B (no mechanism for causal
claims in reports) · `RISK_REGISTER.md` (18 open risks) · `DEPENDENCY_LAW.md` §4 (4 rules enforced
by review only).

## 8. Closed by verification, 2026-08-15 — do not re-open without new evidence

- **`[v]` The PIT store is clean.** The `LIVE_AS_OF` look-ahead defect is real in code and has
  **never fired** on the real store: `SELECT COUNT(*) FROM bars WHERE event_time > knowledge_time`
  returns **0** over 1,917,879 rows / 3,740 instruments. There is nothing to quarantine and no
  forensic backup to take. **The code fix still stands; the incident response does not.**
  **Update 2026-08-17 — the defect has now been OBSERVED, and it changed a decision.** Still 0 on
  the real store (re-measured, unchanged). But one `scan --as-of 2026-08-14T21:00:00Z` against a
  *copy* of it produced **1** violation immediately: AAPL's `2026-08-17` session written with
  `knowledge_time` `2026-08-14 16:00:00-05:00`, because `--as-of` pins the clock and still fetches
  live, and `store.write(refreshed.bars, started)` stamps every fetched bar with the pinned instant.
  That bar then passed `as_of`'s `knowledge_time <= ?` filter, became `held.bars[-1]`, and the run
  proposed `EXIT_NOW / TIME` — *"maximum holding period reached at 2026-08-17"* — from a run pinned
  three days earlier. **`pipeline.py` calls `store.as_of(...)` with no `end` argument**, though the
  method accepts one and bounds `event_time` with it, so the decision read is unbounded on exactly
  the axis §8's third bullet says has no test. One line closes it; the reproduction above is the
  test it never had. Nothing to quarantine on the real store still holds — the three `--as-of` runs
  it has ever seen were all same-day.
- **`[v]` `--as-of` was run three times** (2026-08-02, `run-20260802T120000Z-*`, identical
  instruments and identical `output_hash`) — a determinism check. The same-`knowledge_time`
  collision therefore *did* occur and was harmless, because the vendor returned byte-identical
  values and `write()` skipped them. The destructive variant needs a vendor revision landing between
  two runs pinned to the same instant.
- **`[v]` The Scheduler is installed and firing.** `data/daily_run.log` shows 18:30:01.47 / .68 / .68
  on 08-12, 08-13, 08-14 — machine-consistent, no non-zero exits.
- **`[v]` The three test-coverage gaps** (recorded here so they are not rediscovered):
  `test_as_of_ignores_later_knowledge` is named "the look-ahead guard" but only exercises the
  `knowledge_time` axis — the broken axis (`event_time` unbounded on the decision read) has no test.
  `test_revision_deltas_not_snapshots` writes the same data three times at one `FixedClock` and
  asserts nothing grows — the destructive same-key-different-value path is untested.
  `test_cad_and_usd_can_be_priced_independently` proves the two currencies read different *cost*
  parameters, which reads as currency safety while the FX defect above goes unasserted.
  Every end-to-end pipeline test runs in `RunMode.LIVE_AS_OF`.
