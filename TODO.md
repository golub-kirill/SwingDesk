# TODO — the single open-work list

**Status:** working document · **Owner:** shared · **Last reconciled:** 2026-08-25

**Provenance marks are a claim about THIS file, so the reconciliation date is too.** Items touched on 2026-08-24/25 carry `[v]` on the strength of a check made then; everything older kept the mark it had. A `[c]` is an *unverified* item, not a smaller one, and promoting it means checking it rather than retyping it.

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

### THE ONLY RATIFIED LIVE CRITERION CANNOT FIRE — found 2026-08-24

- [ ] **`[v]` `k.drawdown_pause` is ratified, scope `live`, and nothing enforces it.**
      `registry/criteria.yml` ratifies it: trigger *"Realised drawdown exceeds
      `validation.max_allowable_drawdown`"*, action *"Pause - not kill. Reduce size per the risk-off
      ladder and review."* The threshold is **owner-set at 20** percent of equity.
      **Nothing in `src/` computes realised drawdown.** Two matches for the word exist in the whole
      package and both are prose inside a study's docstring. The parameter's `read_by` is `none`.
      **And its ACTION is unreachable too:** it prescribes the risk-off ladder, and
      `risk.risk_off_ladder` is itself `unset` with no reader.
      **Every gate passed over it, and each for a defensible reason.** Gate 3g checks that a
      criterion's inputs EXIST - the value is there, so it passes, and its own docstring says it
      checks existence rather than discrimination. Gate 1 accepts `read_by: none` because `none` is
      honest and many parameters legitimately precede their consumer. Neither asks whether a
      RATIFIED criterion can fire.
      **It was the only criterion with scope `live`**, so this was not one of several - it was all of
      them. Derive the current set:
      ```bash
      PYTHONPATH=$PWD/src python tools/verify_parameters.py
      ```
      which now prints the cited-by-a-ratified-criterion subset of the unwired parameters on every
      run, so the finding cannot be lost again the way it was found.
      **Harmless today and only today.** `DR-014` rules no owner capital and there are no positions,
      so no drawdown exists to breach anything. The moment a position is opened, the project's own
      kill switch is decorative.
      **What closing it needs is bigger than a wiring job and touches owner decisions**: realised
      drawdown needs an account-equity concept and an equity curve, and the store holds neither.
      Fills are recorded per position; nothing aggregates them into equity. Starting capital,
      mark-to-market versus realised-only, and whether the curve is per-account or per-strategy are
      all decisions, not implementation details.
      **Do not set a number to make a gate green.** The threshold is already set; what is missing is
      the measurement, and inventing an equity definition to satisfy a criterion would be the
      `AGENTS.md` §3 failure - a thing looking more validated than it is.

      **NARROWED 2026-08-25 — the blocker was tested rather than accepted, and it is ONE question,
      not three.** The paragraph above lists starting capital, mark-to-market versus realised-only,
      and per-account versus per-strategy. Checked one at a time against the artefacts that own them:
      - **Peak-relative is not open at all and was never listed as such.** `GLOSSARY.md` transcribes
        the course: `Drawdown` = *"снижение капитала от предыдущего пика"* - a decline from the
        previous peak. So the denominator is the running peak, from the requirements source.
      - **Starting capital has an owner.** `account.equity` is `owner`-set and `DR-014` rules paper
        only, no owner capital. There is a number and somebody set it.
      - **Per-account versus per-strategy has no subject today.** `positions.strategy` and
        `strategy_version` are columns on the store, so either is computable the moment one matters;
        measured 2026-08-25 the store holds **zero** positions across zero strategies.
      - **Mark-to-market versus realised-only is genuinely open, and the criterion's own word does
        not settle it.** `k.drawdown_pause` says *"Realised drawdown"*, which reads as closed-trades
        only - but `PR-009` uses *realised* throughout in the other sense, the drawdown that actually
        occurred as against the permuted ones. **The same word is doing different work in a ratified
        criterion and a registered study**, and only the owner can say which one the kill switch means.
      **What is computable the day that lands, stated so the ruling is worth taking.** The
      realised-only reading needs nothing new: `fills` carries `filled_on`, `shares`, `price` and
      `commission`, and `positions` carries `entry_price`, `shares` and `initial_costs_per_share`.
      The mark-to-market reading additionally needs a daily valuation of open positions, which is a
      bar read the store already serves.
      **And it is not urgent, which is measured rather than assumed:** the position store is empty
      on every table, so either definition reports 0.00% today.

      **RULED AND BUILT 2026-08-30.** The owner settled the open half: `k.drawdown_pause` means the
      drawdown that actually OCCURRED, **including open positions marked to market** - the reading
      `PR-009` was already using, not the closed-trades one the word suggests. `criteria.yml`
      carries it as amendment **v1.1.2**, with a pointer comment at the field, because the file is
      frozen and amendments are appended rather than applied in place.
      **A separate decision record was considered for this and deliberately NOT used**, and that is
      recorded here so the absence is a choice rather than an omission. The question was what one
      word in one ratified criterion means; a DR is the instrument for a choice with alternatives to
      reject, and this had a right answer once the two readings were written down. The amendment
      mechanism is the one this file already owns for exactly this.
      **The measurement is built and wired to nothing.** It reads the position store only - not the
      journal - and reports 0.00% against zero positions, which is the point: the criterion stops
      being unevaluable. `risk.risk_off_ladder` stays `unset` and the prescribed ACTION stays the
      owner's; making the kill switch measurable is not the same as making it automatic.

- [ ] **`[v]` `risk.liquidity_cap_order_to_adtv_pct` is owner-set at 1.0 and read by nothing.**
      **Promoted from `[c]` 2026-08-30 by reading the registry**: `provenance: owner`, `value: 1.0`,
      `read_by: none`. Gate 1 prints the whole orphan list on every run, so derive it there rather
      than from this line.
      The second owner-set orphan. Measured context from `DR-003`'s addendum: at the current account
      size a position is a median 0.0026% of one session's dollar volume, so the cap is nowhere near
      binding and would only begin to at roughly a $2.2M account. Unenforced rather than urgent -
      recorded so it is not rediscovered as a surprise.


~~**`master` went RED on its own, 2026-08-22, and it is fixed in this branch.**~~ **CLOSED
2026-08-22** — merged as `7f3568a` and verified on `master` 2026-08-24. Four tests in `test_cli.py`
seeded a proposal dated 2026-08-16 and let `pending` / `respond` read the wall clock;
`management.proposal_expiry_days` is 3 sessions, so on 2026-08-20 the window closed and gate 8 began
failing on an untouched tree. Fixed by pinning `--as-of` the way the file's own expiry tests already
do, and the trap is in `AGENTS.md` §12. Kept struck through rather than deleted because it stood at
the head of "Blocking now" for two days after it stopped blocking anything, which is its own small
lesson about where a closed item goes.

**The 2026-08-11 freeze lifted on 2026-08-17.** `application/pipeline.py`,
`trade_management/sizing.py` and `tools/daily_run.cmd` are still the frozen files, and a merge to
one that moves decision output still resets `a.run_completes` (`HANDOFF.md` §5).

**What blocks the next thing worth doing.** The two items that stood here on 2026-08-18 are both
closed — the R denominator by re-measurement, the staleness gate by `DR-015` being built — and what
follows them is open work rather than a blocker. **Corporate actions is the one to read**: it is the
last of the three "specified, implemented, wired to nothing" findings still open, and `DR-015` §4
hands it over by name. *Half of it closed 2026-08-23 — the write-time revision comparison is built
and `data.revision_epsilon` is ruled; what is left is the item directly below.*

- [ ] **`[v]` A restated close is detected and printed, and nothing REFUSES on it** (`DR-016`
      §10.4). `market_data/store.py:close_revision` reports every close restated past
      `data.revision_epsilon` and `tools/refresh_universe.py` prints them; the decision path never
      sees one. Making it a `DATA_ERR` / `Critical` is an `application/pipeline.py` change, and
      that file is **frozen** under `DR-015` §3 — a change moving decision output resets
      `a.run_completes`, which `SESSION-HANDOFF` §1 names the slowest thing on the board.
      **It also needs a decision nobody has taken:** does the run refuse the INSTRUMENT or the
      SESSION? A close restated 5% invalidates that instrument's entry, share count and stop
      together; it says nothing about the other 1,147.
      **Not urgent, and that is measured rather than assumed.** `DR-016` §8.2 read the scoped form
      firing **zero** times across the whole capture window, so nothing is being missed while this
      waits. Spending a counter reset on a path that has never fired is the worse trade — land it
      alongside the next change that touches `pipeline.py` for its own reasons.

- [x] **`[v]` The R denominator was asserted by nothing — CLOSED 2026-08-18 by re-measurement, not
      by work.** On the morning of 08-17, `planned_risk` could be replaced with the constant
      `Decimal('42')` and the entire suite stayed green, including the test `INVARIANTS.md` §1 names
      as enforcing that invariant — which asserts `(net/x)*x == net`, an identity that cannot fail
      for any `x`. ~~That test is still a tautology and should be replaced.~~ **REPLACED
      2026-08-25**, the last open half of this item. `test_r_denominator_is_the_planned_risk` now
      pins the denominator's VALUE — 99.00, worked by hand from the fixture's own parameters and
      carried beside the test — and separately pins which field `r_multiple` divides by. **Proven
      against three mutants rather than asserted:** `planned_risk = Decimal("42")` and
      `risk_per_share = entry - stop` (costs dropped) both fail the first assertion, and
      `r_multiple` dividing by `risk_per_share` fails the second, at `net = 0.01` — the two agree at
      zero, which is why a property over a range catches it and a single example would not.
      The three plausible denominators here are 99.00, the allowed risk of 100.00 and the per-share
      5.50; only the exact value tells them apart, which is why the test carries a number.
      **But the defect it left open is closed.** Re-measured on `master` after PR #9 merged: the
      `Decimal('42')` mutant is **killed**, and so is `risk_per_share = entry - stop + costs` →
      `entry - stop`. What kills them is `test_sizing_and_position_agree_on_the_denominator`, the
      cross-module property test written as part of #9 — it asserts the *equality* of `sizing`'s and
      `Position`'s denominators rather than either value, so it constrains `planned_risk` without
      naming it.
      **The base rate is now 1 of 11, not 3.** The sole survivor is `calendar.sessions_behind`,
      below.
      **RE-MEASURED 2026-08-23: that last survivor is dead too, and the survivor count is 0 of 11.**
      `DR-015` gave `sessions_behind` a caller (`market_data/freshness.py`), and with it the two
      mutations that matter now die loudly — returning a constant 0 takes **11** tests with it, and
      an off-by-one takes **7**. Wiring dead code is what killed the mutant; nobody wrote a test
      against it.
      **One mutation still survives and is EQUIVALENT, which is a different thing from a gap.**
      `if last_bar >= latest.session_date` → `>` changes nothing: at equality the long path computes
      a one-session window and returns 0 by the other route. Recorded so the next audit does not
      chase it.
      **But DELETING that early return is not equivalent, and nothing covered it.** A bar dated
      after the last completed session then calls the calendar with `start > end`, which raises
      `ValueError` — the freshness check stops answering and one such bar takes the whole run down
      instead of refusing one candidate. `AGENTS.md` §12 records 296 stored bars whose
      `knowledge_time` predated their own session close, so the input is not hypothetical.
      `test_a_bar_dated_AFTER_the_last_completed_session_is_fresh_and_does_not_raise` closes it and
      is the only one of the twenty in that file that the deletion turns red.
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
      liquidity $5M proxies.
      **THE FLOOR IS SWEPT NOW, 2026-08-23 — and `DR-003`'s PLATEAU DOES NOT EXIST** (`DR-003`
      addendum, `tools/measure_liquidity_floor.py`; derive the figures with that command, never
      from this line). The record chose 5M because *"the choice is insensitive anywhere on the
      5M–25M plateau"*, argued from *"two instruments out of 115"* over the 5M→10M doubling — 5.3%
      of that sample's admitted set. Over the measured population the same step costs **12.9%**,
      and **a third of the universe is gone by 25M**. There is no break in the distribution
      anywhere: the sweep's cheapest step costs 7.0% of members per doubling and its dearest 33.5%.
      **The sample was good and wrong in exactly one place.** Five of six ADTV percentiles replicate
      within ×0.96–×1.18. The sixth is **p75, high by ×1.77** — and p75 is the single number the
      plateau argument was built on. Gap 3 of that record predicted this in the right words and was
      recorded as a limitation rather than treated as one.
      **No threshold moves.** The 2026-08-18 quality-proxy argument above is untouched and is now
      the ONLY argument the floor has. What dies is *"it sits on a plateau"*, which was the reason
      of record for three weeks — a future argument for moving the floor gains nothing from this,
      and a future argument for keeping it has lost its stated reason.
      **What a $3M–$8M sweep would now be testing** is therefore the level of a measure whose form
      is unvalidated (above) **and** whose value the distribution does not select. Any floor is a
      choice on a continuum and has to be argued from what the screen is FOR.
      **The one thing that could still overturn it:** coverage past roughly half the directory
      moving p75. The stored set is an alphabetical prefix — 99.0% of measured names sit in the
      directory's first half — and p75 is where sample and population already disagree. Cheap to
      re-check after more `tools/refresh_universe.py --budget 500` passes.

- [ ] **`[v]` Corporate actions — THE SPLIT GUARD IS BUILT (2026-08-23, `DR-016` §9); the revision
      comparison is the only half left and it is the only half that needs a ruling.**
      A split either happened or it did not, so the held-position guard carries no threshold and
      was built ahead of the ruling. `manage.split_guard` pauses a position when a split took
      effect after its stop was set, carries the restated stop into the reason, and **never applies
      it** — `CHARTER.md` A-001 reserves that to the owner. It runs BEFORE the freshness check: a
      stale series recovers tomorrow, a split does not, and it is the one condition under which
      evaluating anyway yields a confident wrong `EXIT_NOW` rather than a refusal.
      **§8.5's empty table now has a caller.** The run fetches actions for HELD names only — at most
      `risk.max_concurrent_positions` — which is what makes it affordable in the evening pass.
      Fail-open like the bar fetch, and `SplitGuard` carries `refreshed` apart from `stored`,
      because zero actions means either "never split" or "nobody asked" and the store cannot record
      a negative. An unanswered guard reports `unavailable` and does **not** pause.
      **The write-time revision comparison is BUILT too, 2026-08-23** (`DR-016` §10.2), once the
      owner ruled. `market_data/store.py:close_revision` is the rule, `BarStore.write` takes the
      epsilon, `WriteResult.close_revisions` reports, and `tools/refresh_universe.py` reads the
      registry and prints. Three properties are pinned by tests: the epsilon governs the ALARM and
      never the record, `None` means NOT CHECKED rather than clean, and the comparison is relative
      so a cent means what it should at $5 and at $500.
      **What is left is one item and it is below:** surfacing the fault in the decision path.

- [ ] **`[v]` Corporate actions — DR-016 DRAFTED and its PRECONDITION IS NOW BUILT (2026-08-18).**
      **The actions series exists.** `POINT_IN_TIME_SPEC` §4 named three series and the tree had
      two; `DR-016` named the third as its own blocker. Built: `CorporateAction` on the contract, a
      bitemporal `corporate_actions` table beside the bars with `write_actions` / `actions_as_of`,
      and `vendor_yahoo.fetch_actions` reading the vendor's splits and dividends.
      **Not a `Series` member, deliberately** — a split has no open/high/low/close, so putting it in
      that enum would mean inventing five empty fields and the first component to read one would
      get numbers back. It is its own record with its own table, which is what "with their own
      `knowledge_time`" in the spec's own row requires.
      **Wired into no decision when this landed.** The gate needs `data.revision_epsilon`, which
      was `unset` pending the ruling below, so storing an action changed nothing the run decides — which is exactly why
      it was safe to land before the ruling. 11 tests, 5 mutants killed including the look-ahead one
      (an action learned later must be invisible to an earlier read).
      **RE-MEASURED 2026-08-23 (`DR-016` §8) — the value survives, the SCOPE does not.** §2's table
      left the `open` column blank, and the open is the widest of the four price fields: its MEDIAN
      revision (0.128%) is larger than the proposed threshold, while the close's largest revision in
      the whole window is 0.084%, twelve times below it. At `0.001` over all four fields the gate
      raises about **94 `Critical` faults per evening**; over `close` alone it fires **zero** times.
      §5 of that record rejected exactly this for volume and then carried it across one field over.
      Derive the figures with `python tools/measure_revisions.py`, never from this line.
      §8.4 recommends the same number scoped to `close`, which is §3's own reasoning taken one step
      further. **§8.5 also found that `corporate_actions` holds zero rows** — the table, contract,
      vendor call and read path all exist and nothing ever calls `fetch_actions`, the third instance
      of the `AGENTS.md` §7 shape inside the record that closed the previous one.
      **RULED 2026-08-23, as §8.4 recommended: keep `0.001`, scope it to `close`.**
      `data.revision_epsilon` moves `unset` → **`owner`**, its unit narrows from *"relative
      tolerance per series"* to *"relative tolerance on the close"* — the old wording is what let
      one number span four fields whose distributions are an order of magnitude apart — and its
      `read_by` moves from `none` to `swingdesk.market_data.store:close_revision`. The comparison
      is built with it (`DR-016` §10), because a ratified decision reaching no code is a decision
      that did not happen and this record had already produced two of that shape.
      **It does not touch `application/pipeline.py`**, which is frozen under `DR-015` §3, so no
      counter was spent on a path §8.2 measured firing **zero** times.
      The original wording of the ask, kept because it is what was ruled on:
      `data.revision_epsilon = 0.001`, **scoped to `close`** (§8.4), not to all four price fields as
      §3 first wrote; volume taken out of §4's
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
      anywhere in `src/` — and `data.revision_epsilon` was `unset`. Needs its own record, same shape
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
      **OVERRIDDEN BY THE OWNER 2026-08-24 for one study, and the override is recorded rather than
      assumed.** `PR-013` was registered on owner direction while this suspension stood. A council
      is advisory and the owner is not, so the direction governs — but two things are worth having
      in writing.
      **First, the resume condition as written can never be met.** It waits on one real end-to-end
      cycle, and measured the same day: the system has recorded 11,240 decisions and **not one
      `Trade`**, the live path's terminal state is `Watch — sized; awaiting a trigger`, and there is
      no trigger in it. A suspension whose exit condition is unreachable is a permanent stop, which
      is not what the council voted for.
      **Second, the owner's reason is a constraint the council did not have.** Six months, and at
      four concurrent positions held twenty sessions that is 25 live trades against a ratified floor
      of 100. Waiting for the cycle and waiting for the evidence are the same wait, and it is longer
      than the horizon.
      **Still suspended:** everything else on the list above. This override is one study, named.
      **LIFTED ENTIRELY BY THE OWNER 2026-08-30, and NOTHING IS REGISTERED AGAINST IT.**
      The reason is the one already written two paragraphs up and never acted on: the exit condition
      waits on a real end-to-end cycle through a `Trade`, `Trade` is unreachable on the live path,
      and a suspension that cannot end is a permanent stop nobody voted for. The council voted to
      pause research until the system could carry a cycle; it did not vote to stop research
      forever, and by 2026-08-24 those had become the same thing. Lifting it is the honest reading
      of what was decided, not a reversal of it.
      **It is permission, not a plan.** No study is registered here and none should be registered
      casually: every study competes with Track A for the same evening window and the same
      single-writer stores, and Track A is inside a ratified 120-day timebox whose binding
      constraint is measured to be machine availability. The next study needs its own case for
      going ahead of that, made at the time.
- [x] **`[v]` Gate 16 was RED — fixed 2026-08-15.** Both undeclared worktrees are now named in
      `HANDOFF.md` §2. `python tools/verify_branches.py` exits 0.
- [x] **`[v]` `HANDOFF.md` §2's stale rows — fixed at the mechanism, 2026-08-15.** §2 is now
      generated by `tools/build_state.py` and gated by gate 24, so Track A (**4/20**), the directory
      census (**10 pulls / 2 confirmed**) and universe coverage (**28.5%**) are computed rather than
      typed. Two new standing measurements came with it: PIT integrity (**CLEAN**, 0 bars whose
      `event_time` postdates their `knowledge_time`) and the dirty-tree run count (**11 of 13**).

**PR #3 merged.** This file has been on `master` since.

## 2. Picked work

### The second pass is conditional now; its TIME is still wrong and that part is the owner's

**`DR-019` built the condition** — the 19:30 pass asks the journal whether the first run refused
anything a retry could repair, runs when it did, declines cleanly when it did not, and **runs anyway
when it cannot tell**. Measured before building: across every evening that ran both passes the two
runs decided byte-identically, and the failure the pass insures against has never been observed in
this repository.

- [ ] **`[v]` Move the pass later — needs the owner, and it costs an evening rather than code.**
      Measured 2026-08-24, times local against a 15:00 close: the tail of names had no Monday bar at
      **~3.5 h** (first pass) or **~4.5 h** (second pass), and every one of them had it at
      **~7.1 h**. So a pass at 19:30 will keep missing what it exists to catch.
      `docs/runbooks/README.md` §1a makes registering a scheduled task the owner's step, and the
      task is `Logon Mode: Interactive only` — a later pass means being logged in later. That is a
      decision about the owner's evening, not about the software.
- [ ] **`[v]` Measure the arrival curve before moving anything.** The window above rests on **one**
      session. Probing the vendor hourly after the close for a week costs nothing but patience and
      turns a single observation into a distribution — and `AGENTS.md` §15 rule 1 asks exactly that
      of a claim this load-bearing. Cheap shape: for the names the run refused, ask the vendor again
      each hour and record when the session first appears.
- [x] **`[v]` ~~The `E11` event calendar has no source.~~ REFUTED 2026-08-30 — a free, keyless
      source exists and this claim was never tested.**
      ```bash
      python tools/probe_events.py --days 5
      ```
      Nasdaq's own calendar is backed by a JSON endpoint taking one date per call. It serves the
      **forward** schedule with a session bucket — before the open, after the close, or not supplied
      — which is the field this system actually needs, because the question at 18:30 is whether
      tonight's position carries an event over the next session. It also serves past dates with the
      realised figure. No account, no key, two headers.
      **The claim drifted through three strengths and only the weakest was true.**
      `application/checklist.py` said the calendar is not **wired** — correct. This line said it has
      no **source**. `REQUIREMENTS.md` §7 said no event calendar **exists**. Nobody was careless at
      any step and the qualifier simply did not survive the copy, which is `DR-003` gap 1 and the
      Canada refutation repeating in a different subject. `AGENTS.md` §15 rule 2 is the rule: a
      claim about what a SOURCE holds is tested against the source, never inferred from what our
      code received. All three sites are corrected.
      **What it does NOT settle, stated before anyone over-reads it.**
      • **The schedule AS KNOWN on an earlier date is not recoverable.** An old date returns what
      the source says about it today, so a study can know an announcement happened on a session and
      cannot know the date was already published five sessions earlier, or revised. `E11` asks the
      forward question at decision time and is unaffected; a **backtest** of any event rule is not.
      Same survivorship-shaped bound `probe_canada.py` records for TMX.
      • **A row mixes an event-dated fact with a current-state one** — `marketCap` does not vary
      with the announcement date, which the probe demonstrates rather than asserts by finding a
      symbol on two dates and comparing. Reading it as the capitalisation at announcement would be
      an invariant-6 violation.
      • **Canadian coverage is UNTESTED.** Every symbol in the sampled window sat inside
      `directory.duckdb`, which is consistent with a US-only calendar and does not establish one.
      The test that would settle it is a TSX-only name, and the probe does not make it. Not written
      as a "cannot".
      • **It settles the SOURCE and not the RULE.** `screen.earnings_buffer_days` stays `unset` and
      nothing here proposes a value.
- [ ] **`[v]` The buffer needs a ruling or a study, and the literature says the obvious framing is
      backwards — searched 2026-08-30 under `AGENTS.md` §16.** Recorded before anyone sets the
      value, because the reason a threshold has its value is what §16 rule 1 governs.
      **Peer-reviewed, top rank (§16 rule 2), and it points AGAINST a blanket avoid-earnings
      rule on return grounds.** Prices *rise* around scheduled announcements on average: Frazzini &
      Lamont, *The Earnings Announcement Premium and Trading Volume* (NBER w13090, 2007), put the
      premium above 7% a year and tie it to the volume surge and limited investor attention; Savor &
      Wilson, *Earnings Announcements and Systematic Risk* (**Journal of Finance**, 2016), measure
      an annualised abnormal return near 9.9% for scheduled announcers, persistent across stocks
      over long horizons and priced as risk; Barber, De George, Lehavy & Trueman find the same
      premium internationally (**JFE**, 2013). **So a rule that flattens before every announcement
      gives up a documented positive mean.** The course names the catalyst check and quantifies
      nothing (`EVENT_SPEC`), which is §16's situation exactly: an `Operational Course Rule`, not an
      `Empirical Result`.
      **What the literature does not touch, and it is why the rule may still be right here.** A mean
      is not a stop. `PR-007` fixes the exit at 2.0 × ATR(14) with no trailing, and an overnight
      announcement gap opens through a stop rather than at it — so the realised loss on that trade
      is not 1R, and **1R is the unit every validation threshold in this system is expressed in**.
      That is a claim about the denominator, not about expectancy. **Marked conjecture
      (`AGENTS.md` §10.4): nothing here measures it.** The check that would settle it is a
      pre-registered study over the stored bars — realised loss versus 1R on trades held through an
      announcement, against trades that were not — and it is registrable today because the forward
      calendar is only needed for the LIVE rule, while the historical side needs just the
      announcement dates, which the same source serves.
      **§16 rule 4 applies and is not discharged here:** the course and the literature disagree,
      both are recorded, and which one the system follows is the owner's or a study's. The trap to
      avoid is setting the buffer and letting it read as alpha; on this evidence it would be
      variance and tail control, bought with a known cost.
      `E11` remains one of the eight items keeping every candidate at `Research`
      (`docs/08-pm/plans/2026-08-24-the-trade-flow.md` §2).


### THE MOST EXPENSIVE IMPOSSIBILITY IN THE AUDIT: "Canada cannot be enumerated" — REFUTED 2026-08-25

- [x] **`[v]` It can be enumerated. Free, no account, no key.** `python tools/probe_canada.py --full`.
      TMX's own listed-company directory is backed by a JSON endpoint — one call per leading
      character per exchange, returning symbol and name, and stamping its own `last_updated`.
      **How the claim hardened, which is the transferable part.** `DR-003` gap 1 was careful and
      honest: *"Canada has no free symbol directory **in hand** … this project **cannot presently**
      enumerate them."* That says nobody had one, not that none exists. `PR-002`'s report then cites
      it as *"Canada cannot be enumerated (`DR-003`)"* — unqualified — and **drops §6's requirement
      of significance in both countries independently**, which is the requirement whose failure is
      why `PR-002` could not reach an affirmative verdict.
      **A qualified "not in hand" became an unqualified "cannot", and a study lost half its scope
      to it.** Nothing was dishonest at any step; the qualifier simply did not survive the citation.
      That is `AGENTS.md` §15 in one example, and §12's citation trap in another.
- [ ] **`[v]` What this does NOT settle, stated before anyone over-reads it.**
      **Point-in-time membership is untouched.** The endpoint serves TODAY's directory, and applying
      it to old data is survivorship bias with extra steps — the same objection `DR-003`'s own table
      raises against index membership. So this does not retroactively repair `PR-002`.
      **Bar coverage is a separate question.** Whether the vendor serves usable history for a given
      `.TO` symbol is not asked here, and the Canadian half of the store is empty today.
      **It is an unofficial endpoint on a consumer site**, exactly like the bar source (`ADR-0001`),
      and carries the same caveat: undocumented, unversioned, free to change without notice.
- [ ] **`[v]` What it DOES unblock, and this is the reason it matters.** `DR-003` gap 1 says the
      liquidity rule *"applies to `.TO` instruments identically"* and that the Canadian universe is
      *"a list rather than a rule"* only because it could not be enumerated. With enumeration the
      universe becomes a RULE on both sides, which is what `BR-9` and `AGENTS.md` §3's
      never-merge non-negotiable both assume. A future study CAN carry a two-country requirement
      instead of declaring it unmeetable.
      **Needs an owner decision before anything is built**: adding a second directory source is a
      change to what the daily run does, and `DR-008` governs how a directory is pulled, attributed
      and audited. This entry records the refutation, not a plan.

### AUDIT THE IMPOSSIBILITY CLAIMS — owner instruction, 2026-08-24, and `AGENTS.md` §15 is the rule

**The ask:** *"Мы очень часто верим, что у нас нет возможности или не получается, и зарубаем на
корню, не проверяя. Это уже не первый раз... Плюс, в планах у нас бы сделать аудит всего
пройденного, потому что вот на таких моментах мы могли уже попадаться в других исследованиях."*

**Derive the surface, never quote it from here** — every `cannot`, `no free source`, `not
obtainable`, `impossible`, `will never`, `not the lever` in a governed document:

```bash
git ls-files '*.md' | xargs grep -nEi "cannot be|can never|is not obtainable|no free source|not possible|impossible|there is no legal|is not the (next )?lever|will never|no way to"
```

**What this is NOT.** An owner decision is not an impossibility claim. `D1` (no orders), `D10` (no
paid data) and `CHARTER.md` §3's non-goals are *chosen*, and §15 rule 5 keeps them closed. The
target is a sentence asserting something about the WORLD that nobody tested.

**Ranked by what the claim is load-bearing for, sharpest first:**

- [x] **`[v]` "No free source serves delisted history" — TESTED 2026-08-24, and it was half false.**
      It was the load-bearing premise under the survivorship bound that erases `PR-002`, and the
      project had named a candidate refutation — the EDGAR backfill — and parked it, so the claim
      and its test coexisted here without anyone running one against the other.
      **Run it yourself: `python tools/probe_edgar.py`.** SEC EDGAR keeps every filer back to 1993,
      **free, official, no registration and no cost**. A delisted issuer's submissions record shows
      empty ticker and exchange lists, and Form `25` / `25-NSE` dates the event. Verified against a
      real delisting (Eagle Bulk Shipping) with a still-listed control.
      **Access terms, measured:** no `User-Agent` returns **403**, a descriptive one returns
      **200**. The probe transmits no address unless the operator sets `SWINGDESK_EDGAR_CONTACT`.
      **What the CONTROL taught, and it changes how the data must be used:** Apple files Form 25 and
      25-NSE too and is listed — those retire individual securities, not the company. So a Form 25
      is **not** a company delisting; the field that discriminates is the empty ticker/exchange
      list, and the form dates it.
      **What is now measurable and what is not.** How many names vanished, and when: measurable.
      What those trades would have returned: not — no free source serves the price path of a symbol
      that has gone, so the −2R assumption stays an assumption. `VENDOR_COMPARISON.md` §7 and
      `EVIDENCE_SUMMARY.md` §3 are both amended in place.
- [x] **`[v]` DONE 2026-08-25 — and it needed NO owner action. The blocker was false.**
      This item read *"it needs ONE owner action first — a contact address for the SEC header"*, on
      the strength of a measurement that `www.sec.gov` returns 403 to a descriptive `User-Agent`
      while `data.sec.gov` returns 200. **Retested with the header held constant, and the host was
      never the variable: `www.sec.gov` requires a `User-Agent` AND an `Accept` header.** Six
      probes, one header isolated at a time, repeated against flakiness.
      **How the wrong conclusion was reached is the transferable part.** `probe_edgar.fetch()` has
      always sent `Accept: application/json`; the `www.sec.gov` probe was made separately and sent
      only a `User-Agent`. **The two hosts were compared with different headers**, the difference
      was attributed to the host, and a real measurement waited fifteen days on an owner action
      nobody needed. `AGENTS.md` §17 — verify at the right granularity — and §15's asymmetry: a
      wrong impossibility costs everything downstream of it, silently.
      `tools/probe_edgar.py` now **re-derives that table on every run** rather than carrying it as
      prose, which is §10.6's argument applied to a reachability fact.
      **THE MEASUREMENT, taken: `python tools/classify_departures.py`.** Of the **87** symbols that
      left the directory between 2026-08-03 and 2026-08-24, **26 are confirmed delistings of that
      security**, 11 are structured symbols (warrants, units, rights, classes) that depart on
      separation, 1 is a rename, 40 are unresolved and 9 report *still listed at EDGAR*. Derive the
      numbers with the command; never from this line.
      **The methodological finding is worth more than the count, and it corrects `probe_edgar`'s
      own validated method.** Two discriminators disagree at short horizons: the filer's TICKER LIST
      is **not timely** — 34 of the 36 resolvable names still carried their departed ticker in EDGAR
      metadata while absent from the vendor's live directory — while the **Form 25 / 25-NSE DATE
      is**, and it lands on the same pull the symbol vanished at. `AVB` left between the 08-14 and
      08-17 pulls and filed on 08-17; `WBS` left between 08-19 and 08-20 and filed on 08-20. So a
      RECENT departure is classified by the form date; the ticker list is right for history only.
      **And it refutes this file's own eyeball.** The earlier version of this item read *"`AVB` is a
      large S&P 500 REIT and cannot have [delisted]"*. AvalonBay filed a 25-NSE the day it left, is
      absent from both live vendor files, and so is Equity Residential — which reports **no ticker
      at all** at EDGAR. An eyeball is a claim too.
      **What it does NOT establish**, stated so the number is not over-read: `unresolved` is not
      *not delisted*; *still listed at EDGAR* is not survival, because the metadata lags; and the
      RETURN half of the survivorship bound is untouched, so −2R stays an assumption.
- [ ] **`[v]` ~~NEXT, and it needs ONE owner action first — a contact address for the SEC header.~~**
      **Struck 2026-08-25 — see above.** Kept visible rather than deleted, per §10.5's convention:
      an item that parked a measurement behind an owner action for fifteen days on an untested
      premise is worth more visible than absent.
      *(This item replaces a more optimistic version written an hour earlier the same day, before
      the host boundary was measured. `AGENTS.md` §15 applies to one's own claims too.)*
      **The measurement worth having:** `directory.duckdb` holds 18 pulls, and **87 symbols present
      at the first pull are absent at the last** — over three weeks. `DR-008` c3 records that a
      departure is an observation and not a delisting, *because a ticker change looks the same*.
      **EDGAR resolves exactly that ambiguity**: a company that still files and still lists moved or
      renamed; one with empty ticker and exchange lists and a Form 25 delisted. Classifying those 87
      turns the project's own departure record from ambiguous into counted, and it is the first
      empirical purchase anyone has had on the survivorship question.
      **Eyeballing the sample already shows it is a mixture**, which is why it is worth doing rather
      than assuming: `BBBY` plainly delisted, `AVB` is a large S&P 500 REIT and cannot have, and a
      good share of the rest are SPAC units and warrants that "depart" on separation.
      **The blocker, measured rather than guessed.** Lookup by CIK works today. Lookup by TICKER
      needs `www.sec.gov/files/company_tickers.json`, and `www.sec.gov` returns **403** to a
      descriptive `User-Agent` while `data.sec.gov` returns **200** — two probes each way. The SEC
      asks for a contact address in the header. **That address is the owner's to supply and no agent
      may invent one**; set `SWINGDESK_EDGAR_CONTACT` and the route opens.
      **Then it is a measurement, not a study**: it describes the universe and evaluates no strategy,
      so it spends no trial.
- [x] **`[v]` "A fourth estimator is the same family" — AUDITED 2026-08-25, and it SURVIVES.**
      The clause read as a bare prediction closing a search. It is not: `PR-010` §"What this
      establishes" carries a mechanism, and the row now states it. **Each estimator's zero-spread
      floor is calibrated at THIS universe's measured volatility**, so the floor is a property of
      the INPUT rather than of the estimator's construction — which is why both estimators read
      *less* on the real universe than on a spreadless series. Any method inferring a spread from
      daily OHLC infers it from price variation, and here volatility's contribution swamps the
      spread's.
      **And the "fourth" is concrete rather than hypothetical:** the same `bidask` package ships
      Roll (1984) and the generalized OHL / OHLC / CHL / CHLO variants. The mechanism covers them,
      so trying one is predicted to reproduce the floor, not to escape it.
      **What would overturn it** is therefore not a new estimator but a different INPUT — intraday
      quotes, or `PR-006`'s real fills, which is what the row already names as the only route left.
- [x] **`[v]` "Batching is not the lever; the lever would be concurrency" — AUDITED 2026-08-25.
      Correct about batching, and the concurrency half needs no owner decision at all.**
      It read as a lever named and parked, which §15 rule 4 treats as a decision nobody took. It is
      not: **`NFR.md` §3 already rules on it, in both directions.** The table says *"Incremental
      daily refresh ≤ 20 min ... vendor rate-limited. I/O-bound; **concurrency applies here**"* and,
      one row down, *"Decision path ≤ 5 min ... **Not a place to optimise with concurrency**"*. So
      whether concurrency is permitted at the fetch stage was settled before the question was asked.
      **What blocks it is that nothing needs it.** The vendor phase is about three minutes against
      a twenty-minute refresh budget, and the whole run about six against forty-five end to end.
      Derive both with `python tools/measure_latency.py`. Concurrency would buy time **no
      requirement asks for** — the same reasoning that removed the calendar cache, where 23 seconds
      cost 228 MB and discharged no requirement.
      **So it is correctly not done, for a better reason than the one recorded.** The old wording
      implied a pending owner decision and would have sent a future session to ask about something
      that needs no asking. The vendor-relationship concern — parallel requests against an
      unofficial scrape on a free tier — is real and stays real; it simply is not the binding
      constraint, because the speed is not wanted.
      **What would change it:** universe growth. The budgets bind at roughly seven times the current
      fetch count, and coverage is 28% of the directory.
- [x] **`[c]→[v]` "There is no legal source of probability" — AUDITED 2026-08-25, and it is the
      one closure that was never really an impossibility claim.**
      It is a statement about this system's own evidence, not about the world, and it is therefore
      **derivable**: a probability needs a validated expectation, and a parameter reaches
      `validated` only by citing a study that ACCEPTed. Both are counted by tools that already run
      on every gate pass — `verify_studies.py` for accepted verdicts, `verify_parameters.py` for
      validated parameters — and both report none today.
      `EVIDENCE_SUMMARY.md` §4 now names those commands, so the sentence **stops being true the day
      either changes**, with nobody having to remember to revisit it. That is what §15 rule 1 asks
      for, and it is why this row needed an amendment rather than an investigation.
- [x] **`[v]` THE DOCUMENT PASS RAN 2026-08-25, and it found the OPPOSITE of what it looked for.**
      182 hits across 74 files. Almost all are **definitions, not claims about the world** — *"a
      result that cannot be reproduced is not a result"*, *"a prohibiting condition can never be
      outvoted"* — and §15 rule 5 keeps owner decisions (`D1`, `D10`, the charter non-goals) closed.
      The surface is far smaller than 182 suggests.
      **What it did find is a different disease, and a worse one: four claims already REFUTED that
      were still standing, unqualified, in live documents.** Not untested claims — *corrected* ones
      whose correction never propagated. All four fixed:
      • `RISK_REGISTER.md` **D-3** rated *"Canada cannot be enumerated"* **high / accepted** in a
      live risk register, the day after the refutation. Restated: enumeration is settled, the
      residual is point-in-time membership and empty Canadian coverage, and the rating fell.
      • `UX_TASK_FLOWS.md` carried the same claim in the USA/Canada row.
      • `UX_TASK_FLOWS.md` also read *"no free point-in-time sector source is in hand"* — false
      since `DR-006` §12 built `ClassificationStore` on 2026-08-23. **Its EVIDENCE was true and its
      CONCLUSION was false**: `Instrument.sector` really is `None` and nothing sets it, but the live
      path reads the STORE, never that field, so the field said nothing about the source.
      • `REGIME_SPEC.md` carried the exact sentence `EVIDENCE_SUMMARY.md` §3 struck on 2026-08-24 —
      *"that exposure can never be confirmed or ruled out"* — refuted by `tools/probe_edgar.py`.
      **Both refutations were re-verified from the source before anything was edited** (§15 rule 2,
      applied to this session's own trust): `probe_canada.py` returned 842 symbols stamped
      `last_updated 2026-08-25 03:55`, and `probe_edgar.py` reproduced the Eagle Bulk delisting
      against the still-listed Apple control.
      **The mechanism is one sentence and it is why gate 31 exists**: a correction lands in the
      document that owns the claim, and the copies elsewhere keep the refuted wording. That is
      `AGENTS.md` §10.5's disease applied to CLAIMS instead of counts, and §10.5's own answer — one
      owner, and a gate — had never been extended to them.
- [ ] **`[c]` The remaining surface, and it is now small enough to name.** The document pass above
      cleared the refuted-but-standing class. What is left is the ORIGINAL question — a claim about
      the world that nobody tested — and the honest position is that it has been sampled, not
      swept. Re-derive with the command above; a claim that survives with a test named beside it is
      worth more than one that was merely never challenged.
- [x] **`[v]` FIRST INSTANCE PAST DOCUMENTS: "none of that is mechanically detectable" — AUDITED
      AND REFUTED FOR HALF OF WHAT IT NAMES, 2026-08-25.** `AI_AUTHORITY_MODEL.md` §11 and
      `application/ai_guard.py` both said none of §3a clause 1's six routes — synonym, paraphrase,
      translation, colour, emoji, score — is mechanically detectable. **Three of them are finite
      sets and one was never open.** Closed: translation, emoji, colour-as-a-phrase. Never open:
      the numeric form of a score, already refused by clause 3's numeral rule. Genuinely
      undetectable and still the real limitation: paraphrase and open-ended synonym.
      **The sharpest part is what the TEST said.** The case recording the translation hole was
      called *"a translated decision word passes too"* and **contained no translated decision
      word** — it was the paraphrase case in Russian. So the route had never been exercised, and
      when it finally was the guard failed it outright: `_tokens` matched `[A-Za-z_]+`, so Cyrillic
      was never tokenised at all. **A limitation can be documented and untested at the same time**,
      and a test named after a hole is not the same thing as a test of it.
      **A-001's standing condition is still NOT discharged** and the guard is still necessary and
      not sufficient. What changed is where a fresh session should look: paraphrase, not
      "everything".
      Drift is guarded the way the vocabularies are — every enum member must carry a translation,
      **confirmed red** by removing one entry from each table.
- [x] **`[v]` THE CODE PASS RAN 2026-08-25 and found nothing.** `src/` and `tools/` carry about
      thirty matches and essentially all are **design invariants or coded refusals** — *"a fill can
      never exist without the acknowledgement that let it in"*, *"management cannot be evaluated"* —
      not claims about the world. That is the discipline working: a refusal in this code names the
      input it lacked rather than asserting the input cannot exist.
      **One is a real claim and it survives, narrowed.** `contracts/reference.py` justifies
      ticker-as-label with *"we cannot detect reuse from price continuity because no free source
      serves delisted history"*. Still true of PRICES, which is what the sentence rests on. Worth
      recording that EDGAR now makes the WEAKER form checkable — a Form 25 dates the death of the
      old security, so a ticker appearing after that date is a reuse candidate — but nothing in this
      project needs that today and building it would be speculative.
- [ ] **`[c]` Study scope sections — still open, and deliberately last.** `PR-002`'s report is the
      known instance and its Canada citation is already recorded above. Amending a published report
      is governed by `AUDIT_AND_IMMUTABILITY.md`, so this is a different kind of task from editing a
      live document and should not be done casually.

### A STALE COUNT IN A DOCSTRING, AND WHY GATE 14 STILL SHOULD NOT SCAN CODE — 2026-08-25

- [x] **`[v]` `reference_data/directory.py` said "the six pulls made before this existed" and the
      answer was SEVEN.** A hand-typed measured count, in code, invisible to gate 14 — that gate
      scans markdown only. `AGENTS.md` §10.5's disease one file type over.
      **Fixed the way §10.5 says rather than by widening a gate:** the docstring no longer carries
      the number, it names the derivation. A count that is derived cannot go stale in any file type.
- [x] **`[v]` MEASURED AND DELIBERATELY NOT BUILT: a gate over CITED FILE PATHS — 2026-08-30.**
      **The idea came from a real instance**, which is why it deserved measuring rather than
      dismissing: the entry trigger moved to `decision_logic/triggers.py` and `RULE_SPEC.md` still
      pointed at its old home. Nothing in the tree could have caught that — gate 3e resolves *ids*,
      gate 35 *test names*, gate 38 *gate numbers*, and a file path is none of those.
      **Measured over every tracked document:** 364 backticked repository paths, 107 distinct,
      **5 unresolved**. And every one of the five is legitimate:
      • `registry/rules.yml` (×2), `registry/external_services.yml` and `tests/test_trade_log.py`
      are forward references — planned files a document names before they exist, which is a
      document doing its job.
      • `src/core/freshness.py` in `ADR-0002` is **not a stale path at all**. It is a path in
      **TradAlert, the owner's prior system**, cited as precedent. I read it as stale on the first
      pass and the ADR's own sentence says otherwise; git has never known any of the four, which is
      what sent me to read the line.
      **So the gate would arrive RED over five true sentences**, and the only way to ship it is a
      hand-kept allowlist of exceptions — three of which are plans that will land and then need
      removing again, and one that points at a different repository. That is the shape of the three
      widenings rejected on 2026-08-25, and `CI_POLICY.md` §3's cost applies: a gate whose first run
      is all false positives teaches its reader to skim.
      **The contrast is the useful part.** Gates 35 and 38 shipped on the same shape of measurement
      and cost nothing, because both found **zero** live hits — prevention with an empty exception
      set. This one is prevention with a maintained one, and that is a different trade.
      ```bash
      # the measurement, if anyone wants to re-run it before proposing this again
      git ls-files '*.md' | xargs grep -ohE '`(src|tools|tests|docs|registry|golden)/[A-Za-z0-9_./-]+`'
      ```
- [x] **`[v]` MEASURED AND DELIBERATELY NOT BUILT: gate 14 over `.py`.** The obvious response to the
      above, tested before adopting. Across 133 tracked Python files the existing patterns produce
      **7 hits, of which 6 disagree with the tree — and all six are false positives.**
      • `check_gates.py`'s `"8 tests"` is the **gate's NAME**, not a test count.
      • `verify_prereg_conformance.py`'s *"condition 4 gates rather than reports"* — *"4 gates"*
      where `gates` is a **verb**.
      • Three are illustrations inside `verify_counts.py`'s own comments, and one of those is a
      quotation of a past defect.
      • `verify_study_summary.py`'s is a comment reading *"'465 registered' is a component count,
      and a gate that flagged it would be noise"* — **the comment predicting this false positive was
      flagged by it.**
      **And the real defect above was NOT among the hits**, because it is spelled *"six"* and
      because *"directory pulls"* is not a quantity gate 14 derives. So the extension costs six
      false positives and catches zero real defects including the one that prompted it.
      **Same shape as the word-number experiment, same conclusion, and now twice measured:** gate
      14's precision comes from being narrow, and the way out of a stale count is `AGENTS.md` §10.5
      — name the command, not the number — not a wider net.

### THE AUDIT'S OWN BASE RATE — measured 2026-08-25, and the owner's hypothesis holds

**The ask was whether this project had been stopping itself on untested "cannot"s.** Seven
impossibility claims have now actually been TESTED rather than read. **Four were false.**

| Claim | Outcome |
|---|---|
| *"No free source serves delisted history"* | **half false** — EDGAR gives the fact and date, free and official; prices stay closed |
| *"Canada cannot be enumerated"* | **false** — TMX serves its directory free, no account |
| *"None of §3a's six routes is mechanically detectable"* | **false for three of six**, and a fourth was never open |
| *"`www.sec.gov` 403s, so a lookup by ticker needs an owner-supplied contact"* | **false** — it needed an `Accept` header |
| *"A fourth spread estimator is the same family"* | **survives**, and now carries the mechanism rather than the prediction |
| *"There is no legal source of probability in this system"* | **survives**, and is now derivable from two gates rather than asserted |
| *"Batching is not the lever"* | **the claim survives; the PARKING did not** — `NFR.md` §3 had already ruled on concurrency in both directions |

**Three of the four refutations came from testing at a FINER GRANULARITY than the original test**,
which is `AGENTS.md` §17 and is the transferable lesson: the header rather than the host, the six
routes rather than "none of it", *"no directory in hand"* rather than *"cannot be enumerated"*. The
original measurements were not sloppy — each was correct about what it actually measured, and each
conclusion was drawn one level coarser than the evidence supported.

**And the cost was never symmetric.** Every refuted claim had closed real work: a study dropped half
its scope, a measurement waited fifteen days on an owner action nobody needed, a guard was described
as hopeless when half of it was a finite set. `AGENTS.md` §15's asymmetry is not a theory here; it
is the measured outcome of seven tests.

**Widen it past documents when the document pass is done.** The same shape lives in code comments
and in study scope sections - `PR-002`'s report alone carries several - and a study that narrowed
its own scope on an untested "cannot" is the most expensive instance of this there could be.

**Already overturned, 2026-08-24, and it is why this exists.** The evening run refused a block of
candidates reading *"a refetch did not bring it current"*. Re-asking the same vendor the same
evening returned every one of those sessions, clean. The owner asked; nobody had checked.


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
      ~~**`LEG` and `NDSN` have no 2026-07-31 bar and the vendor does not supply one** — refetched
      successfully, the session simply is not there while 60 other instruments have it. A standing
      data-quality fact about this source.~~ It affects no trade: neither has an `end_of_data` exit
      in any arm (checked, after the opposite hypothesis was tested and refuted).
      **STRUCK 2026-08-25, and it was false about three hours after it was written.** The store
      holds both bars: `LEG` 2026-07-31 close **9.80**, `NDSN` **297.78**, both stamped
      `knowledge_time` **2026-08-17 18:30:46** — the ordinary scheduled pass, the same evening.
      It was vendor **LAG**, not vendor absence, and the difference is the whole claim: a lag is
      waited out, an absence is a property of the source. The item further down found this on
      2026-08-24 and said it *"should stop being repeated"*; it was still here until now, which is
      the citation sweep `AGENTS.md` §12 asks for and nobody ran on this file.
      Re-verified against the live store before striking, rather than taken from the item that
      reported it.
      **Publishing took two keys, deliberately.** `--write` alone still refuses; `--accept-drift`
      is required and writes the cell-by-cell comparison beside the log. **`PR-009` must register
      against this replay's vintage, not against PR-005's published aggregate** — they are now
      known not to be the same thing, and the provenance file says so in the artifact itself.
- [x] **`[v]` THE DAILY RUN WAS BREACHING A RATIFIED NFR BUDGET BY 4x AND NOTHING MEASURED IT —
      FIXED 2026-08-24.** Derive the figures with the commands named below, never from this line.
      **`NFR.md` §3 budgets the DECISION PATH at ≤ 5 minutes.** Measured on 2026-08-24 before
      any change: 19.0 min of pipeline compute over the 1,141-member universe plus 71.9 s of
      universe selection — **20.2 minutes, four times the budget.** After: **2.7 minutes**,
      inside it with room.
      **Why nobody saw it.** The same table budgets the END-TO-END run at ≤ 45 min, and
      end-to-end was ~24 min — comfortable. The breach was in a row that only an instrumented
      run can measure, and nothing in this tree measured any of `NFR.md` §3's budgets:
      `data/daily_run.log` gives end-to-end duration and no split, and **the requirement
      lives in the split.**
      **`tools/measure_latency.py` closes that half of it**, built the same day: it replays
      the vendor from the store, times universe selection and the pipeline separately, and
      compares the total against the budget **read out of `NFR.md`** rather than a copy —
      a tool asserting its own ratified threshold is the drift §10.5 exists to stop, and it
      refuses rather than assuming five minutes if the row cannot be parsed. That one
      coupling is pinned by a test, because reformatting §3's table would otherwise disarm
      the tool silently. Reads **160.5 s, 139 s to spare**.
      **Two budgets are still unmeasured** and are named rather than quietly dropped: the
      incremental refresh (≤ 20 min, I/O-bound and explicitly a place concurrency applies)
      and report generation (≤ 30 s). Neither is close to binding today; both would need the
      run itself to record a split, which `application/pipeline.py` being frozen makes a
      sequencing question rather than a coding one.
      **Not asserted about earlier runs.** The last run to complete was 2026-08-17 at 11m45s
      end-to-end, before the universe was deepened to ten years; its decision-path share was
      never recorded and is not reconstructible.
      **Swept for residual quadratics 2026-08-25, and `src/` is clean — a negative worth having,
      because it says where NOT to look next.** The code graph carries a `linear_scan_in_loop`
      property, which is the hidden O(n²) a loop-depth count misses and is exactly the shape the
      biggest hot spot below had. Asked of all 1,450 indexed functions: **eight hits, every one in
      `tools/`** — gate verifiers that sweep documents once — and **none in `src/`**. The deepest
      loop nest anywhere in `src/` is 2, in places where it is inherent (sessions × members for
      breadth, positions × weights for the sector book, both bounded small).
      **Two limits, stated so the next reader does not over-read it.** The index is built at
      `master`'s tip, and `transitive_loop_depth` — the cross-function version — is **not populated**
      in this index, so nothing here rules out a quadratic assembled from two functions. Both were
      checked with a positive control before being reported; the first query looked clean only
      because the property was absent, which is `AGENTS.md` §9's warning arriving in practice.
      **Three hot spots, none of them in a frozen file, and the biggest was quadratic.**
      `completeness.check` asked `BarSeries.bars_on` - a linear scan - once per session date, and
      the pipeline checks each instrument's WHOLE stored extent, so sessions ≈ bars: ~2,500 x
      ~2,500 per instrument, 7.2 billion comparisons a run. Affordable at the old median of 510
      bars and not at ten years, which is why the run had crept from ~5 min to ~12 before the
      deepening and to ~24 after it. `calendar.sessions` read a pandas frame with `iterrows`, which
      builds a Series per row, for two columns. `checklist._load_items` re-parsed the checklist
      registry per candidate.
      **And `universe.select` read 3.57 MILLION bars to answer three numbers** - a bar count, a
      last close and a twenty-session average - one full history per instrument, 3,720 queries, 73
      seconds, 99.4% discarded. `BarStore.tails` answers all three in one query.
      **Measured end to end: ~24 min -> ~6 min a pass, and the remaining time is the VENDOR**, not
      this code: **160 s of compute over the full 1,141**, measured directly rather than
      extrapolated, against ~3 min of 1,141 sequential fetches — and `tools/verify_reproducible.py`
      timed two whole passes end to end at **11m40s**. The compute halves that
      were fixed are 150.2 s -> 15.4 s for 150 instruments (9.8x) and 71.9 s -> 1.7 s for selection
      (41x).
      **Byte-identity was proven, not assumed, SIX times, and the last two go through code paths
      the pipeline never touches:** the same `output_hash` before and after at every step on a
      150-instrument pass; all 1,141 selection members identical member for member against the
      pre-change loop written out verbatim; `tools/verify_reproducible.py` reproducing
      `50e1646b933a4a9d` - the hash recorded on `master` before the change - over the full universe;
      **`tools/run_pr005_replay.py` reproducing all 20 of PR-005's cells** through the backtest
      engine; and **`tools/run_pr012.py` reproducing all 12 of PR-012's cells** - trade counts,
      deferred counts, mean net R and both CI bounds - through `run_book`, the ranking and the
      classification store, ending on the same `REFUSED` for the same reason. So it moves no
      decision output and spends no `a.run_completes` counter.
      **Two run times worth knowing before a session waits on one:** `run_pr012.py` is **13m37s**
      and `verify_reproducible.py` is **11m40s** for both passes. They are now the two most
      expensive tools in the tree.
      **A fourth hot spot, found by measuring my own fix — and the fix for it was BUILT AND THEN
      REMOVED THE SAME DAY, which is the part worth carrying.** The calendar cache thrashes: the
      windows asked for are each instrument's stored extent, 372 distinct ones over the admitted
      1,141, so no exact-window cache can hold them. Quantising the ends to whole years collapses
      them to **36** spans and cuts the pass **159 s -> 136 s** — equivalence measured over 886
      windows, 0 mismatches.
      **It retains 228 MB, measured**, because the saving comes precisely from keeping ~199,000
      built `ExchangeSession` objects alive at ~1.2 kB each. `NFR.md` §3 budgets the decision path
      at **5 minutes** and it now runs in **2.7**, so those 23 seconds bought nothing any
      requirement asks for while the memory was real. Removed, and `sessions`' own cache dropped
      from 32 entries to **4** on a second measurement: simulated over the run's actual window
      sequence an LRU of 4 hits 58.7% and an LRU of 64 hits 63.6%, because two windows cover 669
      of the 1,141 instruments and most of the rest appear once. Sixteen times the memory for five
      points.
      **The cheaper route, for whoever revisits it:** a lighter `ExchangeSession` — it is a
      pydantic model at ~1.2 kB and a frozen slotted dataclass would be a fraction of that — not a
      bigger cache.
      **What it found that was NOT performance:** deleting the window filter in
      `completeness.check` left the whole suite green as it stood that morning, because every
      fixture in that file builds its
      series exactly over the window it then checks. The rule the code comment had always stated
      was asserted by nothing. Closed with a test that overhangs both ends.
      **BATCHING THE VENDOR IS NOT THE NEXT LEVER — measured 2026-08-24, so nobody spends a session
      on it.** With compute cut, the vendor is now the majority of the run, and one HTTP request per
      instrument looks like the obvious target. `yf.download` over 20 tickers at once returns in
      **144 ms each against 167 ms one at a time — 1.2x**, because that call is a convenience
      wrapper over the same per-symbol endpoint rather than a batch endpoint. The lever would be
      CONCURRENCY, not batching, and that means parallel requests against an unofficial scrape of a
      consumer site (`ADR-0001`) on a free tier — a different kind of decision from a refactor.
      **The data half is already measured and it came out clean:** batch and single-ticker returns
      agree on **250 of 251 bars** for every one of 20 names, and the only disagreement is the
      CURRENT unclosed session, which `BarStore.write` refuses by construction. So whoever picks
      concurrency up does not have to re-establish equality, only decide about the vendor.
- [ ] **`[v]` PR-005'S PUBLISHED TRADE LOG NO LONGER MATCHES A FRESH REPLAY — and the reason is
      seven bars that arrived three hours after it was published. Found 2026-08-24; needs an owner
      decision, and NOTHING under `docs/prereg/results/` was touched.**
      Run it yourself: `PYTHONPATH=$PWD/src python tools/run_pr005_replay.py --data <store>`.
      **The measurement.** A replay against the current store reproduces `PR-005.json` **exactly in
      all 20 cells** — trade counts and mean R to six decimals. The published provenance beside the
      log records something different: `1x/A/holdout` off by 0.000326 and `1x/D/holdout` by
      0.000520, 16 of 20 exact. Both are true of their own vintage.
      **What moved, named precisely.** `PR-005-trades.csv` was generated at series knowledge_times
      of **2026-08-17T15:58**. The scheduled run at **18:30:46 the same evening** wrote **7 bars
      inside the study window** that the replay had not seen: `LEG` and `NDSN` for 2026-07-21,
      07-22 and 07-31, and `KMB` for 07-22. With those present the two single-margin gates — A
      turns on one threshold, D on exact pivot extremes — land where `PR-005` had them. Verified as
      a fact about the STORE, not about this branch: the same replay at pre-change `master`
      (`65e2165`) gives the same 20 exact cells, and the in-window `knowledge_time` maximum is
      2026-08-17 18:30, so nothing since has touched this sample.
      **A recorded standing fact is FALSE and should stop being repeated.** §2 of this file says
      *"`LEG` and `NDSN` have no 2026-07-31 bar and the vendor does not supply one … a standing
      data-quality fact about this source."* The store holds both — `LEG` close 9.80, `NDSN` close
      297.78 — fetched by the ordinary evening pass **three hours after** that sentence was
      written. It was vendor LAG, not vendor absence, and the difference is the whole claim.
      **And the provenance's `why_not` is falsified in its practical implication.** It reads *"the
      bytes the study read no longer exist anywhere and cannot be recovered by refetching."* The
      bytes may not be recoverable; the RESULT was, by the next scheduled run.
      **The owner decision, and it is not an agent's to take.** The published CSV is a protected
      record (`AGENTS.md` §11 rule 2) and re-publishing it rewrites the research record. Three
      options: leave it and note the vintage; re-publish with `--write --accept-drift` so the log
      matches a replay anyone can reproduce today; or publish the new one alongside. **`PR-009` is
      what turns on the answer** — it was told to register against *"this replay's vintage, not
      PR-005's published aggregate … they are now known not to be the same thing"*, and on the
      current store they ARE the same thing while the CSV on disk is not.
      **RULED 2026-08-30: LEAVE IT AND DATE IT.** The first of the three options. `PR-005-trades.csv`
      and its provenance stay exactly as published; nothing under `docs/prereg/results/` is
      rewritten. What was missing was never the bytes - it was the vintage, stated where a reader
      meets the file: the log was generated at series `knowledge_time` **2026-08-17T15:58**, and the
      scheduled run at 18:30:46 that evening wrote 7 bars inside the study window that it had not
      seen. Both the log and a fresh replay are correct about their own vintage, and re-publishing
      would trade a reproducible discrepancy for an unreproducible one.
      **The `why_not` line stays too, and stays falsified in its practical implication** - that is
      what correcting forward means. The bytes are gone; the RESULT came back on the next scheduled
      run, and the note above is the record of it.
      **What still turns on this is `PR-009`.** It was told to register against this replay's
      vintage rather than `PR-005`'s published aggregate, and on the current store those agree while
      the CSV on disk does not. That instruction is unchanged by this ruling: register against a
      replay anyone can reproduce today, and cite the dated vintage above for why the CSV differs.
- [ ] **`[c]` UDR-004 — regime ontology.** Three candidate lists now: ТЗ's 8, course v5.0's 11,
      v7.0's 7 (`RECONCILIATION_PLAN.md` §5). Ties to `USER_STORIES.md`:304 (US-004 unsatisfiable
      while `regime.classifier_rule` is contested).
- [ ] **`[v]` Plain names for the opaque ids — owner instruction 2026-08-24, sweep DEFERRED by the
      owner.** *"Я хер знает что такое NFR. Не знаю, что такое PR-012, DR-012, DR-018, ранбук."*
      The rule is in `AGENTS.md` §5 and applies from now on: an identifier gets a plain-language
      name the first time it appears in anything the owner reads, and the bare id is never the whole
      sentence. **The ids themselves stay** — roughly fifty references point at them, four gates
      resolve them, and renaming a `DR-NNN` would edit an append-only record.
      **What is deferred is the sweep of existing documents** (*"по-хорошему, пиши нормальные имена,
      но потом"*). Correct them as they are touched rather than in one pass; a pass over every
      document that cites an id is the blast radius §11 rule 3 warns about.
- [ ] **`[c]` G-3 next timebox.**
- [ ] **`[v]` Test LOGON-mode behaviour — still open; the SLEEP half is now measured and the
      answer is `lost`.** Needs a log-out before 18:30 one evening, then read `Last Run Time`
      against the trigger. That half settles `AGENTS.md` §10.4's marked conjecture and a sleep does
      not settle it: they are different mechanisms.
      **What was measured, 2026-08-24, from the Windows event log** (`HANDOFF.md` §5): the machine
      slept over the 2026-08-20 18:30 trigger and woke at 19:01 local, the task carries
      `StartWhenAvailable=true`, and **no 18:30 entry exists in `data/daily_run.log` for that day**
      while the 19:30 pass ran. A missed pass is dropped, not deferred.
      **No code change came out of it**, and that was checked rather than assumed:
      `tools/track_a_streak.py` reads 18:30 ± 30 min, so a day carrying only the 19:30 pass is
      already `None` and already breaks the streak. The finding is operational —
      **`a.run_completes` can be reset by the machine sleeping**, and the evidence for it is an
      absence rather than an error.
- [x] **`[v]` Re-measure universe coverage — DISCHARGED BY THE MECHANISM, not by a measurement.**
      `HANDOFF.md` §2's runtime block is generated by `tools/build_state.py` and gated by gate 24,
      so the coverage figure is recomputed on every run and cannot be ~10 days stale again. Derive
      it with that command; this line deliberately does not repeat it (`AGENTS.md` §10.5).

### `DR-008` IS RATIFIED AND ROUGHLY HALF UNIMPLEMENTED — measured 2026-08-25

**`HANDOFF.md` §5 named this check open and nobody had run it.** It is run now, clause by clause
against the code, and the answer is worse than the open question implied.

**How it was found is the part worth keeping.** Not by reading the record — by gate 31, which
checks that a command a document tells you to run accepts the arguments given. `DR-008`'s emergency
block names `python tools/fetch_directory.py --emergency-repull --reason "..."`, and argparse has
never had either flag. **The command block was the one mechanically checkable sentence in an
otherwise prose record**, and it was the thread that pulled the rest out.

**Gate 20 exists BECAUSE of `DR-008` and passed the whole time.** Its own docstring says so: *"the
defect this exists for, 2026-08-11: `DR-008` was ratified 2026-08-10 ... and specified a collector
with config gating, calendar eligibility, a response cap, validation and audit rows. None of it was
built."* Gate 20 checks that a record names an implementer and that the token appears in that file.
`implemented_by: tools/daily_run.cmd :: fetch_directory.py` satisfies it. **It verifies that a
decision names an implementer, never that the implementer implements the decision** — `AGENTS.md`
§17 in one example, and the sharpest one this repository has.

- [x] **`[v]` BUILT 2026-08-25 — the audit row, the forced pull, the already-recorded guard and the
      supersession record.** They are one change because none works alone: a guard with no override
      strands an operator whose first pull was malformed, an override with nothing to override is
      decoration, and both need the audit table to record a mode and a reason at all.
      **The guard has a measured cost behind it, not a tidiness argument.** `directory.duckdb` holds
      18 pulls of which **3 were same-session duplicates** — 2026-08-13 22:09, and the 19:30 second
      passes of 08-18 and 08-19 — each spending two HTTP requests and storing a full ~13,000-row
      snapshot that `DirectoryStore.record` then stripped of its session date. `DR-008` says an
      already-recorded session makes **zero requests**. Verified against a copy of the live store:
      the guard fires today for session 2026-08-24.
      **`record(..., supersedes=...)` is the one documented exception to monotonicity**, and it had
      to exist: without it a forced replacement stored a NULL date and `pull_for_session` went on
      answering with the snapshot the operator had just corrected.
      **The guard fails OPEN by construction** — it keys on the ATTRIBUTED session, so a pull whose
      trailer did not corroborate is invisible to it and the next pass fetches again. That is the
      correct direction: the failure mode is today's behaviour, never something worse.
- [x] **`[v]` EVERY CLAUSE IS NOW IMPLEMENTED — the audit that opened this section is closed the
      same day, 2026-08-25.** Kept in full rather than collapsed to a tick: the list is the evidence
      that each clause was checked against the code, and one entry below (`retry`) is a correction
      of this audit's own reading rather than a gap. Struck items were built this session.
      • ~~**Process lock**~~ **BUILT 2026-08-25.** `O_CREAT | O_EXCL` — one atomic syscall, no
      check-then-create window, same behaviour on Windows where this runs. Taken around the fetch
      and the write only, never across the declining branches: a run that decided to do nothing
      must not block one that would have worked.
      **The stale-lock problem was the real design question and getting it wrong is worse than
      having no lock.** `DR-008` gives the forced pull no way past this lock, so one left by a
      KILLED process would refuse every pull **for ever, with no override** — and a missed pull is
      permanently unrecoverable, because the vendor publishes current state and not an archive. That
      trade is backwards: the lock prevents duplicate REQUESTS and a stale one would cost the
      departure record itself. So a lock older than `limits.lock_stale_after_seconds` (600, generous
      by two orders of magnitude) is **reclaimed and reported** — it means a previous run died,
      which is worth seeing — and an unreadable lock is reclaimed too, because *cannot tell* must
      not mean *blocked permanently* for a resource whose loss is unrecoverable. Six tests including
      the boundary control: a lock just INSIDE the timeout is still held.
      • ~~**Checksums**~~ **BUILT 2026-08-25.** One SHA-256 over both response bodies, stored on
      the pull. **One digest over the PAIR, not one each**, because a pull is a complete snapshot —
      the record's own framing, and the reason `as_of` reads the latest pull rather than unioning.
      A length prefix separates the two bodies so that moving bytes between the files cannot
      collide, which is pinned by a test.
      **What it is FOR is one question:** whether the vendor served the same bytes again. An
      unattributed pull is ambiguous between *the file did not regenerate* and *the trailer was
      unreadable*, and those want different responses — the first is the vendor being slow, the
      second is a parsing problem on our side. Raw bodies are never archived (`DR-008` forbids it),
      so the digest is the only trace there can be. The eighteen existing pulls read `None`, which
      is the honest answer and must not be read as an empty digest.
      • **Retry — NOT a gap, and this line said otherwise for an hour.** *"It **may** retry one
      failed attempt after 60 seconds"* is a CEILING, not an obligation — §"rejected alternatives"
      lists *"unlimited retry inside one command"* as the thing it bounds. `_download` retries zero
      times, which is inside the ceiling and therefore compliant. Recorded rather than deleted
      because reading a permission as a requirement is how a clean implementation acquires an
      imaginary defect, and this audit was written to stop the opposite error.
      • ~~**The committed machine-readable policy**~~ **BUILT 2026-08-25 as
      `registry/directory_pull_policy.yml` + GATE 22.** Neither the filename nor the gate number is
      invented — `plans/2026-08-11-evidence-foundation.md` names both, deferred rather than
      dismissed.
      **The clause is not "put constants in YAML", and the reason matters.** These are the limits on
      what this project's software may ask of somebody else's free server. A limit in a literal is
      changed by editing a line; a limit in a committed, gated policy is changed by a commit a gate
      reads and a reviewer sees. `DR-008`'s own rejected-alternatives table names what it guards:
      *"unlimited retry inside one command — can hammer the source without a new human decision."*
      **The new human decision is the point.**
      **Gate 22's second check is the one with teeth:** a source URL left as a literal in
      `tools/fetch_directory.py` fails **even when it agrees with the policy**, because agreeing
      today is how every drift here has looked on the day it was written (`AGENTS.md` §10.5). Read
      from the syntax tree, so a gate about a network tool never imports one. Both check classes
      **confirmed red** — a planted URL literal, and a zero cap.
      **`.swingdesk-local.json` is deliberately NOT in the policy**: the policy is what this project
      commits to doing to someone else's server, and the switch is one machine's own state.
      Committing it would turn an operator's local choice into a repository fact.
      • ~~**Exact HEADER validation**~~ **BUILT 2026-08-25.** Row shape was checked from the start
      and refuses a short row; the header was `splitlines()[1:]`-ed away without being compared to
      anything, so a vendor that reordered its columns would have been parsed silently **by
      position** — `parts[6]` read as `ETF` while holding something else. `otherlisted.txt` is why
      this is not hypothetical: it carries BOTH an `ACT Symbol` and a `NASDAQ Symbol` column, and
      `parse_other_listed`'s own docstring already warned that reading the wrong one produces a
      universe of symbols that fetch empty. The read positions are now a named mapping the header is
      checked against, so `parts[6]` says what it is; a TRAILING column the vendor adds is accepted,
      because a column nothing reads cannot change an answer, and `NextShares` was appended once
      already. Four tests, **all confirmed red** with the check removed.
      • ~~**Gap recording, and its severities**~~ **BUILT 2026-08-25.** `attributed_sessions()` and
      `gaps(expected)`; the caller supplies the sessions so the store never learns about exchanges,
      which is the layer contract *and* the reason the withdrawn version was wrong.
      **Measured on the live store: zero gaps inside the attributed window** — 8 sessions,
      2026-08-13 to 2026-08-24, every one present. **Coverage starts at the first ATTRIBUTED pull,
      not the first pull**: 8 NYSE sessions between 2026-08-03 and 2026-08-13 are covered only by
      pulls that could not be placed on a session, and `DR-008` c3 forbids backfilling them.
      The severity rule turns on one subtlety worth keeping: **a Friday and the Monday after it are
      CONSECUTIVE sessions.** Counting calendar days would report an `ERROR` every Monday; counting
      them as non-adjacent would miss a two-session outage across a weekend, which is the most
      likely shape of one.
      • ~~**"After the latest session has completed"**~~ **BUILT 2026-08-25.** Eligibility checked
      `cal.is_open(NYSE, today)` only, so a scheduled run at 09:00 on a trading day was eligible and
      would have pulled a file describing YESTERDAY. Now `last_completed_session(...) == today`.
      **Measured before changing it rather than after:** both scheduled passes (18:30 and 19:30
      local = 19:30 and 20:30 ET) sit after the 16:00 ET close and stay eligible; a 09:00 run does
      not, which is the defect. Not reachable from today's trigger, so this is a correctness fix and
      never was an outage.
- [ ] **`[v]` The MANUAL mode is outside `DR-008` entirely, and that is a gap in the RECORD.**
      The bare form honours neither the local switch nor the calendar. `DR-008` describes scheduled
      collection and the forced pull and never mentions a third mode, so the code is not violating
      the record — the record does not cover it. Deliberately left alone: narrowing what a human
      operator can do by hand is a decision, not a defect, and `AGENTS.md` §14 says ask.

### DONE 2026-08-24: slim `AGENTS.md` — owner instruction, cut and verified

**A one-off instruction, not a standing rule** — an editorial request about one artefact, so it cites no `AGENTS.md` section and gate 30 accepts it on that mark rather than on a pointer that would have to be invented.

**The ask:** *"У нас agents выглядят уже как книжка... Можно ли его сделать нормальным, чистеньким,
без прозы? Правила, конвенции, всё как есть."* Yes. The brief is below so a fresh session starts
cutting rather than measuring.

**The hard constraint, measured 2026-08-24: section numbers CANNOT change.** 153 references across
the repository point at `AGENTS.md` sections, and **16 of them sit in files that may not be
edited** — accepted decision records, ADRs, pre-registrations. Renumbering means rewriting ratified
documents to chase a heading, which §11 rule 2 forbids. Most-cited: §12 (28 references), §3 (26),
§10.5 (25), §7 (17), §10.6 (15).

**So: same headings, same numbers, same rules. Cut the narrative inside them, nothing else.**

**Where the weight actually is** — 7,146 words total:

| words | section |
|---:|---|
| **2,185** | §12 traps — **a third of the file** |
| 659 | §10 the four rules of 2026-08-09 |
| 477 | §5 conventions |
| 402 | §10.6 |
| 389 | §9 finding things in the code |

**The cutting rule: one rule, one line, plus ONE clause saying what paid for it.** Not a paragraph
retelling the incident. Worked example — the worktree/`PYTHONPATH` trap goes from 130 words to
about 25 without losing either the instruction or the reason to believe it.

**Target: ~3,000-3,500 words.** Roughly half.

**The one objection, and it is not rhetorical.** In this repository the war stories are load-bearing:
the culture rests on *every rule was paid for*, and a bare rule with no price reads as arbitrary and
gets ignored — which is the failure mode §12 exists to prevent. So **keep one price clause per rule**
and say in the file that the full accounts remain reachable through `git log -p AGENTS.md`.

**Deliberately not started at the end of a long session.** It is the most-cited document in the
tree; a large edit made tired is how this repository has been burned before.

**CUT 2026-08-24, and the risk above was answered with a check rather than with care.** Three
things were asserted mechanically after the edit, not read for: every `##`/`###` heading is
**byte-identical and in the same order**; every `AGENTS.md` section reference across every tracked
file still **resolves** — none dangling; and §13's owner block is **unchanged byte for byte**. No
document, parameter or component id appears in the new file that was not in the old one, so the cut
could not invent a citation. All gates pass.

**It came in ABOVE the target, and the target was the estimate that was wrong.** Roughly a third
was removed, not a half. The arithmetic the brief did not do: the file's tables, command blocks and
the owner's verbatim quotation are unshrinkable, and the rest is about sixty distinct rules. At
**one rule plus one price clause each** — which this same brief calls non-negotiable, because a bare
rule reads as arbitrary and gets ignored — the floor sits well above 3,500 words. Reaching the
number needs one of two things the owner has not asked for: **drop the price clauses, or drop
rules.** Neither was taken.

What actually went: every restatement, every second example, every paragraph that retold an
incident already summarised in its own first sentence. §12 was a third of the file and is the
section that changed most. Derive the current length with `python -c "print(len(open('AGENTS.md',
encoding='utf-8').read().split()))"`, never from this line.

### The dated session-handoff files are outside the document map, and one has already broken a record

**Owner question, 2026-08-24: why a permanent `HANDOFF.md` AND a dated `SESSION-HANDOFF-<date>.md`,
and should it continue?** Measured rather than argued, and the answer needs an owner ruling.

`AGENTS.md` §10.7 names **four** documents and gives each an owner. `SESSION-HANDOFF-<date>.md` is a
fifth, outside the map. **Seven have been created and four deleted in six days**, two of them
replacing themselves.

**Three costs, all measured:**

1. **Things die in it.** Four traps lived only in `SESSION-HANDOFF-2026-08-24.md` §3 and were
   migrated to `AGENTS.md` §12 on 2026-08-24, hours before that file was deleted by its own
   instruction. Nothing would have noticed their loss.
2. **An append-only record cites one.** `DR-016` line 441 cites `SESSION-HANDOFF` §1. `DR-016` is
   dated 2026-08-18 and the file it points at was deleted **2026-08-23** — so that citation has been
   dangling since, and `AGENTS.md` §11 rule 2 forbids editing the record to fix it. Gate 3e cannot
   see it either: it resolves names of the form `something.md` and the citation is a bare
   `SESSION-HANDOFF §1`. **Demonstrated within the minute:** deleting the file made gate 3e fail
   immediately on a citation in `AGENTS.md` that used the full filename, and stay silent about
   `DR-016`'s bare one. The gate is not weak — the citation style decides whether it can help, and
   an append-only record picked the style the gate cannot see.
3. **Its numbers drift unchecked.** Gate 14 reads `docs/**` plus exactly three root files, and this
   is not one of them. On the day it was deleted it still claimed *"everything is merged"* and a
   gate count two behind the tree.

**Recommendation: stop creating them.** Every section such a file carries already has an owner —
what changed is `git log`, open work is this file, state is `HANDOFF.md` §2 and is generated, what
to do next is `HANDOFF.md` §5, habits are `AGENTS.md` §12. A session that cannot fit its handover
into `HANDOFF.md` is holding something that belongs in one of those, which is exactly what happened
to the four traps.

**Not acted on beyond the migration**: the convention is the owner's to keep or drop, and this entry
is the question rather than the answer.

### Measured and deliberately NOT built: gate 14 over `TODO.md`

**`AGENTS.md` §10.7 says this file never holds a measured count, and nothing enforces it.** Gate 14
reads `docs/**` plus exactly three root files — `README.md`, `AGENTS.md`, `HANDOFF.md` — so the rule
that governs this document is the one rule it cannot see. Probed 2026-08-24 by adding `TODO.md` to
that list: **15 hits, and after marking the six genuinely historical census lines, 8 remain and all
8 are false.**

They are all one shape, and it is the shape the gate's own comment already names for parameters:
*"11 tests, 5 mutants killed"* and *"an engine ignoring the injected trigger takes 17 tests with
it"* are statements about what a change ADDED, not about the suite. The clinching one is
`gate 25's condition 4 gates` — where **"gates" is a verb**.

**So it stays out of scope, and the gap is recorded rather than papered over.** `CI_POLICY` §3's
"a noisy gate gets bypassed" costs more than this drift does, and the drift here is bounded: a
count in a closed `[x]` item is history that only reads wrong, while the same count in `HANDOFF.md`
§2 would be acted on. The six historical lines are now marked with `DONE` and a date, per §10.5's
own convention.

## 3. Contradictions — two documents disagree

Each of these is a silent wrong-answer generator: a session reads one, acts, and is wrong.

### THE DEGENERACY GUARD REFUSES THE INSTRUMENTS ITS OWN RECORD SAYS IT PROTECTS — measured 2026-08-30

- [ ] **`[v]` `DR-006` §12.1 argues the guard is EXACT so a genuine sector ETF clears it. Five of
      the eleven do not.**
      ```bash
      PYTHONPATH=$PWD/src python tools/probe_sector_benchmarks.py --data data
      ```
      §12.1's words: *"A genuine sector ETF is legitimately almost all one sector, so a tolerance
      would refuse the instruments this cap most needs."* The reasoning is sound and the premise is
      half wrong — **almost** all is doing the work, and the SPDR Select Sector funds for
      communication services, energy, healthcare, real estate and utilities each report **exactly**
      one sector at exactly 100%, which is `_degenerate_sector`'s signature exactly.
      **What actually happens is not silent, and that matters for how alarmed to be.** A refused
      look-through makes `SectorCapacity.is_unavailable` true, which **admits** the candidate by
      design (`DR-006` §3: a check the system could not perform must not refuse everything) and puts
      *"UNAVAILABLE — the look-through is degenerate"* on the record. So the system behaves
      correctly given the guard, and the reason travels. **Nothing is fabricated and nothing is
      hidden.**
      **What is wrong is the REASON, and it is wrong in the same way gate 24's was.** The refusal
      text reads *"which is how this vendor describes a fund holding no equity at all"*. For `XLU`
      that sentence is false: it holds almost nothing else. `AGENTS.md` §15 rule 1 and §10.4 both
      say an explanation is itself a claim, and this one is attached to a live risk control.
      **A discriminator exists and it is measured rather than proposed from memory.** The guard
      infers *holds no equity* from the SHAPE of the sector weights; the same vendor call serves the
      fact directly. `funds_data.asset_classes["stockPosition"]` reads **0.0% for `NEAR`**, the bond
      fund the guard was written for, and **99.7–100% for every refused sector proxy**. That is
      `AGENTS.md` §12's proxy trap with the direct measurement sitting beside it in the same
      response.
      **Deliberately NOT changed here.** `DR-006` is accepted, §8.7 is one of its rules, and
      swapping the discriminator changes what the sector cap admits — a decision output. That is an
      amendment to a ratified record and belongs to the owner (§8, §14). What is done is the
      measurement, the command that reproduces it, and the note that the cost is bounded today:
      **none of the five is in the admitted universe**, because none of the eleven has bars stored.
      **What it also settles, and this is `E05`'s first half.** The blocker recorded in
      `application/checklist.py` is *"no sector-to-index mapping exists"* — true of this repository.
      A mapping now exists as a measurement rather than an assertion: **all eleven pairings are
      confirmed by the vendor's own look-through, zero contradicted**, and all eleven are listed and
      not test issues in `directory.duckdb`. What remains for `E05` is authoring the mapping as a
      record and storing the series — and, separately, whether a sector-relative comparison helps at
      all, which is a study and which `PR-012` has already found decorative point-to-point.

**Everything below was EMPTY as of 2026-08-24 — closed, and four of them were not what they
said.** Kept for the reasoning, because the reasoning is the transferable part:

- **`G0 status` and `k.project_timebox` were never disagreements.** One was a stale open item whose
  parenthesis had been wrong from the day it was written; the other was two different fields being
  read as one claim. `AGENTS.md` §12's habit — name the artefact that owns the status before making
  the claim — resolved both, and no gate could have.
- **`HANDOFF.md`:124 pointed at a line that had MOVED**, to `EVIDENCE_SUMMARY.md`, five days before
  anyone tried to resolve it. An audit item carrying a file and a line number ages faster than the
  claim it describes.
- **`docs/README.md` drift and `SPEC_GAP §32/§33` were real, and both got a gate rather than a
  fix** — 15's missing half and 28, which found six more of the same shape on its first run.

**The one pattern under all of it:** nothing here rotted by being wrong when it was written. It
rotted when a *cited* fact moved — a study verdict withdrawn, a charter amended, a parameter given a
value — and the citation stayed. That is what gates 28 and 29 are aimed at, and it is what the habit
is for where no gate can reach.

- [x] **`[v]` `registry/criteria.yml`:222's stale note — fixed 2026-08-15 via v1.1.1 amendment.**
      Council-reviewed (5 advisors + peer review); one response's recommendation was flagged by the
      safety layer for arguing to edit the ratified note in place, and 3 of 5 peer reviewers
      independently converged on the same objection blind to the flag. v1.1.0's note left
      byte-for-byte untouched; a comment (not a data field) points to the v1.1.1 entry, which carries
      the verified correction with its evidence. Same fix applied to
      `docs/00-charter/SUCCESS_AND_KILL_CRITERIA.md`:154 via `AGENTS.md` §10.5's own
      strikethrough-and-append convention. Every gate passed, DONE 2026-08-15.
- [x] **`[v]` G0 status — RESOLVED 2026-08-24, and it was not a disagreement about G0.**
      `docs/README.md` §Gates owns gate status and records **G0 CLOSED 2026-08-02**; `ROADMAP.md`
      §1 and `HANDOFF.md` §2 both agree with it. What `CONSTRAINTS.md` §9 held was a stale OPEN
      ITEM — *"ratify the remaining `criteria.yml` values (one confirmation; closes G0)"* — whose
      precondition was met on 2026-08-08 and whose parenthesis was wrong when it was written: G0
      closed on the finish line being ratified and the criteria frozen at v1.0.0, six days before
      the remaining values were ruled. Ticked with its date, per `AGENTS.md` §10.5's convention.
      **The habit that resolved it is §12's:** name the artefact that owns the status before making
      the claim. Three documents "disagreed" and only one of them was answering the question.
- [x] **`[v]` `PREREG_TEMPLATE.md` §6 carried as OPEN two things `criteria.yml` RATIFIED — FIXED
      2026-08-24.** Found while pricing `b.deflated_sharpe`. The template said the multiple-testing
      correction was *"None is adopted yet"* and asked *"whether the trial count … is per component,
      per strategy, or project-wide"*. `criteria.yml` settled both on **2026-08-08** — the method is
      the deflated Sharpe and the denominator is cumulative across the programme — and
      `EVIDENCE_RECORD_SPEC.md` §1 then states it as fact. **It had been closed for sixteen days
      before anyone noticed.**
      Corrected forward with strikethrough per `AGENTS.md` §10.5's own convention, in its own change
      rather than from inside `TRIAL_BUDGET.md`: the template governs how every study is written and
      editing it from a budget document is the wrong blast radius.
      **The section now also states what a new study OWES it:** how many configurations it will
      evaluate, declared before it runs. An undeclared trial inflates the true denominator while the
      reported one stays flat.
      Live cost avoided: a session writing a pre-registration would have read that no correction was
      adopted and omitted the accounting a ratified criterion requires.
- [x] **`[c]→[v]` The 120-day Track A clock — resolved by the v1.1.1 amendment above.**
      `SUCCESS_AND_KILL_CRITERIA.md`:154's "has not started" is now struck through and corrected.
      Checked `HANDOFF.md` §4 for a third copy before closing this: it already says "reversed
      2026-08-09" (from the §4 rewrite in `279c625`) — consistent with the amendment, no drift.
      The date is 2026-08-09 (`tools/track_a_streak.py`'s own `SCHEDULING_STARTED` constant, which
      cites this same date), not 08-10 — 08-10 is the first NYSE session the schedule was
      *evaluated against*, and the day it failed on batteries.
- [x] **`[v]` SPEC_GAP §32/§33 — RESOLVED 2026-08-24, and reading the row pulled three more with
      it.** §32 leaves `DEFERRED` for **PARTIAL**: A-001 put the AI contour in scope on 2026-08-08
      — outside the ratified v1 finish line, which is a different claim — and
      `AI_AUTHORITY_MODEL.md` was written for it the same day, so the row was citing a non-goal the
      charter had already amended. `COVERAGE_AUDIT.md` §3 grades the contour `PARTIALLY_COVERED`
      and its §4 says *"the coverage status is `MISSING`, not `OUT_OF_SCOPE`"*. §33 stays
      `DEFERRED` and its reason moves to `COVERAGE_AUDIT.md` §5, which rules model governance
      *"not yet"* because it follows the authority model rather than §32.
      **§18 left FULL in the other direction, and it is the one that mattered.** Its only stated
      evidence was **"PR-002 validated"** — that verdict was corrected to `inconclusive` on
      2026-08-16, `regime.classifier_rule` is `assumed:PR-002`, and its `read_by` is **`none`**.
      A Tier-8 table asserted the strongest word this project has, eight days after the study that
      supplied it was withdrawn. `AGENTS.md` §3: *nothing looks more validated than it is.*
      **Two more rows kept their class and lost a stale shortfall.** §30 said *"no portfolio layer
      — correlation, sector and open-risk caps all `unset`"* and §31 said two of `DR-006`'s six
      constraints *"cannot be evaluated"*; all six reach code as of 2026-08-23 and every cap names
      a consumer. Two counts outside their owner went too: §14's `(96)` parameters against 105, and
      §47's *"61-document plan"*.
      **Census: FULL 29 · PARTIAL 26 · ABSENT 0 · DEFERRED 2**, recounted by gate 3e — which was
      proven to fail on a wrong summary before the new one was trusted. `HANDOFF.md` §2's hand-kept
      row carries it.
      **The failure mode is worth carrying beyond this row:** nothing in that table rots by being
      wrong when written. It rots when a *cited* fact moves and the citation stays, and gate 3e can
      see neither a withdrawn verdict nor an amended charter.
- [x] **`[v]` "Two ratified criteria are inert" — RESOLVED 2026-08-24. It is one criterion and two
      reasons, and the claim had MOVED before it was resolved.** The item said `HANDOFF.md`:124; §3
      of that file sent the standing account to `docs/08-pm/EVIDENCE_SUMMARY.md` on 2026-08-15 and
      the sentence went with it, carrying its own `UNRESOLVED` note. So the item pointed at a line
      that no longer existed — worth knowing before the next audit chases one.
      **The second candidate was checked rather than assumed.** `k.drawdown_pause` was this
      project's other inert gate — ratified while `validation.max_allowable_drawdown` was `unset`,
      so its verdict was invariant across every input — and `DR-007` gave it a value on 2026-08-08.
      `RULE_SPEC.md` §7: *"The gate went from unable to fail to untested."* Untested is not inert.
      Corrected with a strikethrough in `EVIDENCE_SUMMARY.md` §6, per `AGENTS.md` §10.5's own
      convention.
      **A second stale claim fell out of it, and it is the spelled-out-count hole again.**
      `EXPECTATION_MODEL.md` §9c read *"One parameter is `validated`"*. The registry holds
      **none** — it has since `PR-002`'s verdict was corrected on 2026-08-16 — and gate 14 could
      not see it twice over: the count is spelled in words, and "parameter is" sits between the
      number and the backticked status its pattern anchors on. Rewritten to name the command.
      **Gate 14 was deliberately NOT extended to match word-numbers**, and the reason is its own
      design note: people write censuses in digits and local statements in words (*"two tests pin
      this"*), so matching words would fire mostly on the second kind — and `CI_POLICY` §3's
      "a noisy gate gets bypassed" is the failure that costs more than the drift.
- [x] **`[v]` `k.project_timebox` — NOT a contradiction. Closed 2026-08-24 by reading the two
      fields.** `status: owner-set` in `criteria.yml` says how the criterion came to exist; `met`
      in `ROADMAP.md` §8 and `RISK_REGISTER.md` G-3 says whether its condition was satisfied
      (G5 closed 2026-08-02, inside a two-month box). Two fields, two questions, no disagreement.
      **What IS open is the successor**, and it is already tracked: `ROADMAP.md` §8 and
      `RISK_REGISTER.md` G-3 both say no next timebox has been set, and `TODO.md` §2 carries it as
      `G-3 next timebox`. That is an owner decision, not a documentation defect.
- [x] **`[v]` `docs/README.md` drift — FIXED AT THE GATE 2026-08-24, not at the instance.**
      Both halves were real: row 06 said 21 stories where 22 exist, and rows 22/23/24 marked
      `REGIME_SPEC` / `EVENT_SPEC` / `CHART_SPEC` `planned` while all three exist and declare
      `drafting` in their own headers.
      **Gate 15's docstring already NAMED this exact drift as one of the four it was written for**
      — and the gate only ever compared a document's own `**Status:**` header against the manifest,
      never the index's Status CELL. So `registry/project_manifest.yml` carried
      `readme_status_text: drafting` for all three while `docs/README.md` went on printing
      `planned` for sixteen days, with the gate green. A gate that names a defect in its docstring
      and does not test for it is a hand-kept count wearing a gate's clothes (`AGENTS.md` §10.6).
      **The check now compares them**, and it found two more the moment it ran: row 02 carried a
      stale `criteria.yml` v1.1.0 reference and a *"time box proposed 2026-08-08"* clause that
      v1.1.1 has since settled, and row 58's manifest entry held the document's Content sentence in
      the status field. One test, whose assertion fails if only the pre-existing document-header
      check fires.
      The 21 was **dropped rather than corrected** — a count in a document that does not own it is
      the next stale copy (`AGENTS.md` §10.5).

## 4. Pending decisions

- [ ] **`[v]` `DR-006` §3 ADMITS AN UNAVAILABLE CANDIDATE UNCHECKED, AND A CAP THAT FAILS OPEN IS
      NOT A CAP — five of five council advisors, 2026-08-31, unanimous and the only thing they all
      volunteered.** 145 admitted universe members have no sector served or nothing stored, and
      every one of them is admitted with no sector charged. The constraint this project writes down
      is *"unavailable must never masquerade as pass"*; §3 is that masquerade, ratified.
      **Two costs nobody had priced, both surfaced in peer review, and they are why this is not a
      one-line flip:** (1) fail-closed makes a single vendor field a TRADING DEPENDENCY — a vendor
      outage or schema change becomes a book-wide halt, and there is no staleness or
      last-known-good policy to fall back on; (2) refusing instruments that are already HELD
      produces a book the guard says cannot exist, so it is a migration rather than a branch.
      **And a third nobody has measured:** refusal is not neutral. Dropping members tilts the
      universe toward funds the vendor happens to classify, which is a selection effect the cap
      itself never sees.
      **AND THE MIGRATION COST IS ZERO RIGHT NOW, measured 2026-08-31.** The review's sharpest
      objection was that refusing instruments already HELD produces a book the guard says cannot
      exist. The position store holds **zero** open positions, so that cost does not exist today and
      will the moment one is opened. If this is to be flipped, the cheap window is while the book is
      empty.
      Ruling this is the owner's. It changes a ratified rule and it costs a Track A restart.

- [ ] **`[c]` Is a SECTOR cap the right unit for a single-name leveraged ETF?** Raised in council
      review 2026-08-31 and not settled anywhere. `AAPU` is 2x one company; charging it to
      "technology" answers a different question from the one its risk poses, which is
      concentration. Related: `R` contains leverage for SIZING but not for sector AGGREGATION — a
      1R `AAPU` and a 1R `XLK` charge technology identically while `AAPU`'s economic exposure is
      twice `XLK`'s. `DR-025` §4.1 records the seam and does not close it.

**Decision records** — DR-007 / DR-008 / DR-010 / **DR-012 / DR-013 / DR-014** are accepted, and
2026-08-30 added **DR-011 / DR-016 / DR-017 / DR-018 / DR-022 / DR-023**.

- [ ] **`[v]` `DR-021` COSTS A COUNTER RESET, AND ITS OWN SECTION 6 SAID IT WOULD NOT — measured
      2026-08-30, which is what section 6 asked someone to do.**
      Section 6 claims the discriminator *"moves no decision output the day it lands"* and then says
      the honest thing: *"it must be measured against the live universe before it is called
      cosmetic."* Measured, and it is not cosmetic.
      **23 admitted universe members are refused by the section 8.7 guard today** — 1,018 spendable,
      23 degenerate, 101 no sector, 44 nothing stored, of 1,186. Robust to `DR-017`'s lag: 23 under
      `adtv_lag=0` and 23 under `adtv_lag=3`, checked both ways so it cannot be an artefact of the
      change that landed the same day.
      **Section 6's error is sampling, not reasoning.** It reasons about the five SPDR Select Sector
      funds, and none of the eleven SPDR funds is in the universe at all — coverage is still an
      alphabetical prefix and the letter X is unreached, the same reason `DR-018` section 2b found
      the benchmark ETFs missing. The guard fires on ANY degenerate-shaped fund, and 23 are admitted.
      **How many would flip is not measured and is certainly not zero.** `CURE` (3x healthcare
      equity, reported healthcare), `DPST` (3x regional banks, financial services) and `DRN` (3x
      real estate, real estate) are being refused on a reason that is false for them, while `BNDW`
      and `BNDX` are global bond funds reported as **technology** and are refused correctly. The
      exact split needs `stockPosition`, which is the next item.
      **The proposed discriminator reads a field this project does not store.** `Classification`
      carries `quote_type`, `industry` and sector weights; so does the table; the vendor adapter
      reads `funds_data.sector_weightings` only. `asset_classes` is read in exactly one place —
      `tools/probe_sector_benchmarks.py`, live over the network. So `still_to_build: the
      discriminator itself` understates it: a contract field, a store column, a vendor-adapter
      change and a refetch of every stored classification come first.
      ~~**So it waits for the next window.**~~ **BUILT AND RATIFIED 2026-08-31**, on the owner's
      grant of a restart for that date - which is what "the next window" turned out to mean.
      `Classification` gained `equity_share`, read from the same vendor response the sector weights
      already came from, and `look_through` refuses a degenerate look-through only when the vendor
      does not positively report equity. `DR-021` section 9 records it.
      **The code alone moves nothing, and that is by construction.** All 1,148 stored
      classifications have `equity_share` NULL, and only a POSITIVE share clears the guard - absence
      is a fact about the vendor, not evidence about the fund. Gate 9 replays to the same hash; no
      Track A restart was spent, and the owner's grant for 2026-08-31 is UNSPENT.
      **RULED 2026-08-31 BY `DR-025`, after a five-advisor council and a web check.** The shape is
      not the evidence and never was: the vendor's sector weights sum to 1.0000 for EVERY fund
      regardless of holdings, including the ten reporting 0% equity. The guard stops reading the
      shape; only a vendor-declared 0% equity refuses. Sector-spendable universe members go
      1018 -> 1041, all in the conservative direction.
      **`DR-021`'s fail-closed polarity was backwards**, and that is the correction worth carrying:
      it made silence REFUSE, but a refusal reports `unavailable` and `DR-006` 3 ADMITS an
      unavailable candidate unchecked - so widening a refusal is the PERMISSIVE direction here, not
      the safe one. `None` therefore does not refuse.
      **Not scaled by the equity share**, and `AAPU` is why: physical equity 0.074 against an
      economic 2x Apple, so scaling would undercharge the most concentrated instrument in the
      universe by ~27x. `DR-025` section 4 has the distribution and the dissent.
      **STILL OPEN, and both are the owner's** - see the two items below.
      ~~**THE BACKFILL IS HELD, AND IT NEEDS ONE OWNER RULING.**~~ Measured against a COPY of the store
      before touching the live one - all 23 re-classified, 0 vendor failures - the equity shares are
      not the two-valued population `DR-021` section 5 assumed:
      the ten genuine bond and commodity funds all report **exactly 0.0000** (`NEAR`, `BNDW`,
      `BNDX`, `UITB`, `FIXD`, `BOND`, `ANGL`, `BCI`, `CARY`, `COMT`) and stay refused, correctly;
      eight are unambiguous equity at 0.626 to 1.000; and then it runs continuously down through
      `AMZU` 0.317, `AVL` 0.172, `AMUU` 0.160, `AAPU` 0.074 to **`BINC` at 0.0001**.
      **`BINC` is a bond fund reporting 0.01% equity.** Under "a positive share admits" its
      `financial_services 100%` look-through is spent in FULL - which is exactly the `NEAR` fiction
      this record exists to stop, at 0.0001 instead of 0.0.
      Section 5's *"0.997 versus 0.0 is not a close call and nothing in this record turns on where a
      line between them would sit"* is therefore FALSE on the live population, and it is the same
      sampling error section 8.2 already records for section 6, in the same record: measured over
      the eleven SPDR funds, concluded over the universe.
      **The ruling, and it is the owner's twice over.** Admitting on any positive share spends a
      sector budget on a bond fund. Picking a floor is a threshold, and section 5 forbids one
      without a citation - and `risk.max_sector_risk` is a `DR-006` cap, which binds a real account.
      A third option exists and is a different design: SCALE the look-through by the equity share,
      so a 7%-equity fund places 7% of its value, which needs no threshold and no admit/refuse - but
      it changes what every fund contributes, not just the degenerate ones, so it is a new record
      rather than an amendment.
      **One thing fell out of it:** `platform/schema.py` refused to open any store missing a
      declared column while it held rows, but its own argument is about `NOT NULL` - filling one
      invents a value. NULL invents nothing. The reconciler now adds a missing NULLABLE column to a
      populated table and still refuses a `NOT NULL` one, naming only the column that cannot be
      added. Without it this record needed a hand migration of the shipped store to record a fact
      already true of every row in it. Nothing here disagrees with `DR-021` section 4 — the defect is real and section 8.1
      makes the case STRONGER, because the guard is wrongly refusing instruments actually in the
      universe rather than hypothetical ones. What is gone is the argument for landing it cheaply.
      **`DR-021` section 8 carries the tables.** The record stays `proposed`; ratifying is the owner's.

- [ ] **`[v]` `DR-017`'s cutover churn, logged as section 4 asked — measured 2026-08-30.**
      *"The first lagged run will admit and refuse a different set than the last unlagged one, and
      that difference is a fact about the fix rather than about the market."* On the live universe:
      **1,128 members unlagged, 1,186 lagged — 58 more, about 5%.**
      Recorded here rather than in `DR-017`, which is accepted and corrected forward only
      (`AGENTS.md` section 11 rule 2). Expect the first evening after the merge to show a membership
      step of roughly this size, and do not read it as instability.

- [ ] **`[v]` §10.5 GIVES EVERY COUNT AN OWNER. NOTHING DOES THAT FOR A STATUS, AND ONE SESSION
      FOUND TWENTY-ODD STALE ONES — the owner's call, because the fix is a rule.**
      `AGENTS.md` §12 already names the shape: *"§10.5 gave every measured COUNT one owner; nothing
      does that for a STATUS, so read a claim about state from the artifact that owns it."* That is
      a **habit**, and habits are what §10.6 rule 1 says do not survive contact with a busy session.
      **The evidence is one day's work rather than an argument.** 2026-08-25, across **15 governed
      documents**: a risk register accepting a risk that had been refuted; a requirement register
      saying a check *"does not exist"* when it had existed since 08-08; an invariants document
      asserting seven tests would fail when one of them could not; a chaos table opening *"must be
      tested, not assumed"* with nothing saying which test covered which row; a ratified, WIRED risk
      cap whose arithmetic ran on a threshold superseded thirteen days earlier; two open items
      blocked on things that had stopped blocking; and `HANDOFF.md`'s own first sentence — *"nothing
      is held in a branch waiting for a decision"* — while two branches held work.
      **None of them was wrong when written.** Every one rotted because a cited fact moved, which is
      exactly what §10.5 exists to stop for numbers and nothing stops for states.
      **What a rule would have to decide, and none of it is an agent's:** whether a status claim must
      name the artefact that owns it the way a count names its command; whether "nothing does X" is
      allowed in prose at all, or must be a derivation; and what the mechanism is, given that four
      gate ideas were probed this session and **three were rejected as too noisy to ship** — a
      backticked parameter near a numeric claim (21 pairings, 1 live hit, a false positive), one near
      a cited `DR-NNN` (15 pairings, 2 live hits, both legitimate), and a reachability gate over
      controlled vocabularies (withdrawn 2026-08-25 in the trade-flow plan). **The one that did ship
      is the shape that works**: gate 35 checks a citation whose subject is EXACT — a named test
      either exists or does not. A status claim in prose is not exact, which is the whole difficulty.
      **Recorded rather than proposed.** `AGENTS.md` §14 makes the rule the owner's, and gate 30
      makes `AGENTS.md` its only home.
- [ ] **`[v]` THE TRIAL BUDGET — `docs/08-pm/TRIAL_BUDGET.md`, written 2026-08-24, `owner-pending`.**
      The number is the owner's. Derive every figure with `python tools/trial_budget.py`, never from
      this line.
      **Three things it measured first, and two were not what the plan assumed:**
      `b.deflated_sharpe` is **ratified and nothing counted its only input** — no parameter, no
      registry field, no code — so a criterion ratified 2026-08-08 could not have fired on any day
      since. The `AGENTS.md` §7 shape again - named, not numbered, because a tally in prose is the
      thing §12 says to stop keeping.
      **13 trials are already spent, against a census that reads 5.** A trial is a CONFIGURATION
      EVALUATED, not a pre-registration filed: `PR-001` tried 4 definitions, `PR-002` fitted 4
      variants and kept 1, `PR-005` ran 5 gate arms. `PR-008` and `PR-010` spend none — a spread
      estimator has no Sharpe to deflate. Counting filings understates the search by about 3×, in
      the flattering direction.
      **The hurdle grows logarithmically, which inverts the plan's §2c.** 1 → 5 trials costs 1.19
      sd(SR); 5 → 50 costs only 1.08 more. The expensive trials are the first ones and they are
      already spent, so rationing late buys almost nothing — **what buys the control is declaring
      and counting trials, not having few of them.** An undeclared trial inflates the true N while
      the reported N stays flat, which is the direction that manufactures significance.
      **Proposed: 25 total, 12 remaining** (+0.29 sd(SR) for the whole remainder), split 4
      cross-sectional / 4 mean-reversion / 2 liquidity corner / 2 reserve.
      **Named, not glossed:** trials are NOT independent, so the table is a conservative upper bound
      rather than a measurement; `sd(SR)` is unknown so the hurdle is in units of it, and converting
      needs journalled trades, of which there are none.
      **Deliberately NOT built: the deflated Sharpe itself.** It cannot be evaluated and building it
      would suggest it can. What was missing was the count, and that now exists.

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
      **10.15R** and ~~−15R is **1.5 sessions** away, not 2.5. Four positions restores the record's
      own intent: 4 × 1.692 = 6.77R → **2.2 sessions**.~~
      **Corrected 2026-08-25: the pause is not −15R.** The registry holds 20 percent of equity,
      `owner`; `DR-007` §3.7's −15R was superseded on 2026-08-09. 1R is exactly 1 percent of equity
      today, so the pause is **20R**: six positions are **2.0** sessions away and the ratified four
      are **3.0**. The ratification is unaffected and the error ran conservative — §1's target was
      two and a half sessions and four gives three. Full working in `DR-006` §18.
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

- [x] **`[v]` The SECTOR cap is WIRED — built 2026-08-23 (`DR-006` §12). All six of `DR-006`'s
      constraints now reach code.** Items **b**, **c** and **d** below are all discharged and the
      plan is kept for the measurements it carries.
      `risk.max_sector_risk` names `trade_management/portfolio.py:sector_limit`. A candidate is
      measured through its sector WEIGHTS, so an ETF consumes its constituents' budget — Appendix
      C's own control cell — and a share and a fund are the same arithmetic. New store
      (`ClassificationStore`, bitemporal, read as-of), new vendor call
      (`vendor_yahoo.fetch_classification`), new pass (`tools/refresh_classifications.py`).
      **§8.7's guard landed with it, and the exactness is deliberate:** a fund reporting one sector
      at *exactly* 1 with every other at *exactly* 0 is refused, because a real single-sector ETF
      carries a remainder and a tolerance would refuse the names the cap most needs to see.
      **THREE incompletenesses, and they are not the same** (`DR-006` §12.4): an unset cap refuses
      every candidate; an unclassifiable CANDIDATE is admitted UNCHECKED; an unclassifiable POSITION
      makes the split understate and refuses nothing.
      **The store started EMPTY on 2026-08-23, so every candidate was admitted unchecked that day
      and the report said so.** That was not a defect — it is §3 being obeyed — but it did mean the
      cap protected nothing until the refresh pass had run. `unchecked` is a coverage number to
      close, not a verdict, and the refresh pass has since moved it: **the run's own SECTOR block
      prints how many candidates were admitted unchecked, and it is no longer all of them.** Read it
      from the latest report in `data/reports/`, never from this line.
      **It is harmless only while the book is empty.** With zero positions there is no risk to place
      in any sector, so an unclassified candidate cannot breach a cap that nothing is consuming. The
      first real position is what turns this coverage number into a hole in `risk.max_sector_risk`.
      **The point-in-time gap is now ENCODED**: read as-of, so a replay before the first pull finds
      nothing rather than answering an older question with today's classification.

- [x] **`[v]` DR-006's last one: SECTOR. §3 called it UNEVALUABLE and that is WRONG — it is
      buildable today. DONE 2026-08-23 — see the entry above.** Kept for the measurements; every
      item in it is discharged.
      **CLOSED 2026-08-23: both rulings taken, and `DR-006` is fully ratified** (§17). Sector cap
      **keeps 2R** and `risk.max_sector_risk` moves `assumed:DR-006` → **`owner`**; §2's *"one third
      of the book"* justification is **retired** because §8.3 moved the anchor to 4R without moving
      the number, so 2R is half the book and the old sentence quotes a premise that has gone. The
      correlation cap **keeps the refusal** and the size-adjustment question §11 has carried since
      2026-08-08 is **closed as unnecessary rather than unauthored**.
      **`risk.correlation_threshold` stays `assumed` on purpose.** The ruling settles the SHAPE of
      the rule, not the number; 0.70 becomes `validated` through a pre-registered study and nothing
      else. `risk.correlation_lookback_sessions` stays `assumed` too — nobody was asked about 60
      sessions and nothing measures it.
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
      can rule on numbers whose checks actually run. **Built 2026-08-23; the ruling is now open and
      is in `DR-006` §13 — four items, of which two want an owner: whether the correlation cap should
      RESIZE rather than refuse, and whether 2R is still the right sector budget now that the book
      anchor moved from 6R to 4R and 2R went from a third of the book to half of it.**
      **BOTH halves are now measured** (`DR-006` §14 and §15, owner asked for research before
      ruling on each). Derive the correlation figures with
      `python tools/measure_correlation_cap.py`. Headline: the cap bites on **20.2%** of candidates
      on a four-position book — never quote `PR-005`'s 43.5%, whose book held a median of 22 —
      refusing costs nothing measurable in return, and the premise **fails on the coarse measure
      and holds five-fold on the precise one**: correlated co-held pairs did not end up losing
      together more often, but they gapped out on the SAME session 4.94× as often, CI [2.32, 7.56].
      §15.4 concludes the size adjustment is unnecessary rather than merely unauthored.
      **The sector half is measured too** (`DR-006` §14).
      Derive the figures with `python tools/measure_sector_cap.py --classifications data/classifications.duckdb`, never from this line. The
      headline: `PR-005` held a median of 20 positions at once and 95% of its days were over four,
      so it never simulated a capped book and cannot be replayed as one — what §14 samples is the
      POPULATION such a book would have drawn from. §14.4 recommends keeping 2R on a new argument
      and states the case against. **§14.6 records a real defect the research found in the build
      itself:** the vendor spells its eleven sectors two ways, so a share and an ETF in one sector
      would each have got their own budget and a concentrated book would have read as diversified.
      Fixed the same day; not reachable from the fixtures and no gate would have caught it.

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

- [ ] **`[v]` VALUES RESTING ON AN UNRATIFIED RECORD ARE COUNTED NOW, not described — 2026-08-25.**
      Gate 1 check 5 required an `assumed:DR-NNN` citation to **resolve to a file**; nothing asked
      whether that file had ever been accepted, and this entry carried the shape in prose for
      twenty-three days. Gate 1 prints the subset on every run — derive it, never from here:
      ```bash
      PYTHONPATH=$PWD/src python tools/verify_parameters.py
      ```
      **Reported, not failed, and that is deliberate.** Ratifying is the owner's act (`AGENTS.md`
      §14), so a gate that went red here would demand a decision it cannot get and would be
      bypassed — the same reasoning gate 1 already applies to its orphan block.
      **The one to read first is the cost model.** Both of its halves are on the list, so every
      net-of-costs figure this project has published is denominated in two records nobody ratified —
      including `HANDOFF.md` §2's *"slippage **measured** — 25bps per side (`DR-005`)"*, where
      *measured* is true of the number and not of the record's standing.
- [ ] **`[v]` Records still `proposed` whose values the system is already using.** ~~DR-009 ·
      DR-001 / DR-002 / DR-005~~ — **that hand-typed list was checked 2026-08-30 and was wrong in
      both directions**, so it is replaced by the command that derives it. Gate 1 has printed this
      subset on every run since 2026-08-25 and no reader had compared the two:
      ```bash
      PYTHONPATH=$PWD/src python tools/verify_parameters.py
      ```
      **What the comparison found.** `DR-004` and `DR-018` each carry a live parameter and were
      **missing** from the list; `DR-009` is `proposed` but **no parameter rests on it**, so it
      belongs with the unratified records in §4 rather than here. The distinction is the whole
      point of the entry: a proposed record with a parameter behind it is a value whose only
      authority is a record nobody ratified, and a proposed record with none is a decision waiting
      to be taken. Ratifying is the owner's act in both cases and neither is an agent's to force.
      **Why the list rotted the way it did.** It was typed on 2026-08-02 and every subsequent record
      — `DR-018`'s benchmark, `DR-010` superseding half of `DR-004` — moved the answer without
      touching the line. `AGENTS.md` §10.6 in one sentence: concentrating a fact makes it findable,
      not true, and the only fix that holds is the tool deriving it.
      **`DR-003` left this list 2026-08-23: RATIFIED**, on the population measurement and on the
      quality-proxy argument, after the same measurement refuted the plateau argument it had been
      standing on since 08-02. Only `universe.min_adtv_20d` moves `assumed` → `owner`;
      `universe.min_price` and `universe.min_bar_history` were not part of the ruling and stay
      `assumed:DR-003`, following `DR-006`'s precedent that an accepted record and an owner-set
      value are different claims.

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
      **b. Register the 19:30 task — DONE 2026-08-18, and this item was FALSE for five days.**
      Confirmed against the machine 2026-08-23: the task exists, is `Enabled`, and has been running
      since it was created. `AGENTS.md` §12 already described the 19:30 pass running and failing —
      *"both passes, once the 19:30 task was registered"* — so two documents here disagreed about a
      fact neither could check, and the stale one was the one being acted on. The owner was handed
      a `schtasks /Create` line for a task that already existed and was one keystroke from replacing
      a working registration.
      **Gate 26 (`tools/verify_schedule.py`) now asks the machine**, per `AGENTS.md` §12's own habit:
      when you find a stale claim, add a gate rather than fixing the instance. Advisory, and
      `UNAVAILABLE` anywhere but the scheduling machine.
      **It is RED as of 2026-08-23 and correctly so:** both passes last ran 2026-08-21 and both
      exited 1 on the schema drift `AGENTS.md` §12 records. `positions.duckdb` carries
      `initial_costs_per_share` again, so **Monday 2026-08-24 is the first run that can get past it
      — and the repair is unverified in production until then.**
      **Two machine settings the verbose query shows and nothing else does:** both tasks are
      `Logon Mode: Interactive only`, and the second pass alone carries
      `Power Management: No Start On Batteries`. Neither is fixable from this repository; both make
      an evening with no log line a different event from a run that decided nothing.

**ADRs — all four unratified.**

- [ ] **`[c]` ADR-0001** market data · **ADR-0002** calendar · **ADR-0003** schema language ·
      **ADR-0004** storage engine.

**UDRs — three open.**

- [ ] **`[c]` UDR-004** (see §2) · **UDR-001** (blocked on the owner's forthcoming book) ·
      **UDR-002** (graph DB choice, owner input). UDR-003 / UDR-007 closed.

**Owner-pending.**

- [ ] **`[c]` Course v7.0 adoption** — 7 unexecuted steps, deferred by owner ruling.

## 5. Studies

- [ ] **`[v]` THE HOLDING HORIZON IS WHY BOTH STUDIES FOUND NOTHING — measured 2026-08-31,
      EXPLORATORY, sets nothing.** `python tools/measure_momentum_horizon.py --data <store>`.
      **The literature first** (`AGENTS.md` §10.3 — searched before authoring). Jegadeesh (1990)
      documents short-term REVERSAL at the one-month horizon; Lehmann (1990) the same weekly;
      Jegadeesh & Titman (1993) document MOMENTUM over 3–12 month formation **and 3–12 month
      holding** periods, their shortest reported hold being **three months**. The standard "12-2"
      construction skips the most recent month to keep the reversal window out of the signal.
      **`PR-012` held 20 sessions and `PR-013` held 5. Both are inside the reversal band, and
      neither skipped the recent month.** Their nulls are what the literature predicts.
      **Measured on this store, restricted to the `DR-003` liquidity rule, gross, deciles, formation
      252 sessions, non-overlapping formation dates:**

      | horizon | skip 0 | 95% interval | skip 21 | 95% interval |
      |---|---|---|---|---|
      | 5 sessions | +0.215% | [−0.150, +0.561] | +0.268% | [−0.076, +0.610] |
      | 20 sessions | +1.016% | [−0.321, +2.263] | +0.908% | [−0.255, +2.059] |
      | 63 sessions | +3.148% | [−0.007, +6.207] | +2.184% | [−0.783, +5.153] |
      | **126 sessions** | **+7.271%** | **[+1.899, +12.512]** | **+6.444%** | **[+0.700, +12.214]** |

      **The spread rises monotonically with horizon and only excludes zero at 126 sessions.** That
      is the horizon structure J&T report, reproduced on this project's own data.
      **So the binding constraint is `exit.max_holding_period` = 20 sessions** (`DR-012`, ratified,
      about one month) — below where the effect is measurable here and inside the band where the
      literature documents the opposite sign.
      **AND THE COST OF MOVING IT, so the trade is visible:** at four concurrent positions, a
      20-session hold allows about 50 entries a year and a 126-session hold about **16**. Reaching
      the horizon where the signal is measurable makes `b.min_sample` slower to reach, not faster.
      That tension is real and is the owner's to weigh.
      **A METHOD ERROR OF MINE, recorded because it inverted the sign.** The first run measured
      every name in the store with enough history — 2,742 — rather than the ~1,100 the liquidity
      rule admits. Every spread came out NEGATIVE at every horizon. Restricting to the rule flipped
      all eight. The unrestricted set is loaded with leveraged and inverse ETFs whose 12-month
      returns are large and whose reversals are violent, so it measured the store rather than the
      universe. **The liquidity rule is doing more work than a liquidity filter appears to.**
      **What this is NOT.** Gross, not net — at 126 sessions the rebalance drag is far smaller than
      at 5, but it is unmeasured. n = 17 formation dates at 126 sessions. Survivorship is today's
      directory, which biases every figure upward. Exploratory by construction: designed after
      `PR-012`'s and `PR-013`'s numbers were seen, so `PREREG_TEMPLATE` rule 3 applies and it
      advances no validation status and sets no parameter.
      **The skip made it slightly WORSE at every horizon** (7.27 vs 6.44 at 126), which is contrary
      to the convention's rationale and well inside the interval. Reported rather than explained.
      **OWNER RULING 2026-08-31 — `exit.max_holding_period` STAYS AT 20 AND IS A RULE.** *"20 tight,
      it is a rule. Later, separately, we can test and research up to ~40 maybe."* `DR-012` is
      unchanged and needs no supersession; this measurement does not reopen it. The horizon question
      is not closed, it is **scheduled separately** and bounded at about 40 sessions — see the item
      below.

- [ ] **`[ ]` A SEPARATE STUDY OF THE HOLD, BOUNDED AT ~40 SESSIONS — owner ruling 2026-08-31.**
      Not now, and not as an amendment to `DR-012`: a pre-registration of its own, run when the
      desk is otherwise quiet. Scope fixed by the owner at **up to about 40 sessions**, so 63 and
      126 are out of scope however the exploratory numbers read.
      **What the existing measurement already says about that region, so the next session does not
      re-derive it:** the tool has no 40-session point, and the two it brackets with **both include
      zero** — 20 sessions +1.016% [−0.321, +2.263] and 63 sessions +3.148% [−0.007, +6.207]. A
      study bounded at 40 is therefore expected to be **underpowered on this store's history**, and
      that expectation belongs in the pre-registration as a stated prior rather than being
      discovered as a null. It is also below Jegadeesh & Titman's shortest reported hold (three
      months), so a null at 40 refutes nothing about the family.
      **Do not run it as an amendment to `PR-012` or `PR-013`** — both are reported and their scope
      is closed (§10.2, and `PREREG_TEMPLATE` §0's refutation-family check).

- [x] **`[v]` `ROADMAP` P5 — THE FIRST STRATEGY CARD EXISTS, 2026-08-24.** Load-bearing since
      2026-08-02 and untouched until now. Family chosen by the owner: **cross-sectional relative
      strength** — deliberately not the time-series breakout `PR-005` refuted.
      `registry/cards.yml` (machine-readable) +
      `docs/02-domain/CARD-001-cross-sectional-relative-strength.md` (the reasoning) +
      **gate 27** `tools/verify_cards.py`, which checks every component and parameter reference
      resolves, that a card is `Validated` only with an evidence id and carries one only if it is,
      and that a card citing an `unset` input declares it in `blocked_by`.
      **Status `Untested`, and §2 of the card is why it must stay there.** `M31-T0465` carries
      `claim_type: Untested Hypothesis` in the COURSE's own taxonomy, so `ALLOCATION_SPEC` §3
      applies: the ordering needs a pre-registration before it selects a trade, never a decision
      record. All three selection inputs are `unset` and the card refuses — the design working.
      **G6 finally has a denominator: 4, not 465.** `ROADMAP` §3 defines it as "every component a
      live strategy card needs is `active`", and demand-driven coverage had no meaning with no card
      to create the demand. This card needs four components and gate 27 prints how many are active.
      **What the card revealed by existing — see the item below.**

- [x] **`[v]` THE BACKTEST HAD NO PORTFOLIO — BUILT 2026-08-24, `validation/backtest/book.py`.**
      Found by writing the card, which is the argument for P5 in one line. Verified two ways before
      building: nothing in `src/swingdesk/validation/` referenced `portfolio`,
      `risk.max_concurrent_positions` or `risk.max_open_risk`, and the code graph showed `run_arm`'s
      callees were the cost model and the exit policy and nothing else.
      **`run_book` walks a SESSION axis**, not an instrument's bars, so instruments compete. Four
      properties pinned by tests proven to fail without them: `deferred` is a separate outcome from
      `Skip` (`ALLOCATION_SPEC` §5), a slot freed by today's exit is available to today's candidates
      (`CHECKLIST_SPEC` §4), the ranking is injected with **no default**, and `risk.max_open_risk`
      binds independently of the position count. A one-name book with spare capacity reproduces
      `run_arm`'s trades exactly.
      **`engine._close` became `close_position`** so both engines share one definition of what a
      closed trade costs — the `DR-006` precedent, not a new pattern. `PR-005` still replays
      **byte-identically** after the rename; measured, not assumed.
      **What is left is that no study runner calls it**, and that needs the ranking rule, which
      needs a pre-registration. Carried in the card's `blocked_by` as `no-study-runs-the-book`.
      **Three blockers remain, declared in `registry/cards.yml`:** the selection inputs are unset
      (a study, not a decision record), the benchmark FORM is unset (`DR-018`, below), and all four
      components are `registered`.

- [ ] **`[v]` THE 70/30 SPLIT COST PR-012 ITS SAMPLE AND BOUGHT NOTHING** — found 2026-08-24 after
      the refusal, appended to that study's report rather than edited into it.
      `WALKFORWARD_SPEC` §1–§2: a split separates **tuning** from checking, and parameters are
      fitted on train, selected on validation, judged on test. **PR-012 fits nothing and selects
      nothing** — §5 says so in its own words. So train and validation were empty by construction
      and the split discarded **70% of the judged sample for a protection there was nothing to
      protect**: roughly 600 trades per arm became roughly 185, which is the whole reason §8's floor
      was missed.
      **The obvious fix is not available to whoever noticed it.** `PREREG_TEMPLATE` rule 3
      downgrades a redesign made after seeing the data to **exploratory**, and the numbers are seen.
      A pooled re-run can be honest or confirmatory, not both. The three real options and their
      costs are in the report; the cheapest-looking one — running it and treating the verdict as
      confirmatory — is undetectable data snooping and is the trap.
      **The template gap is filed with it:** §2's form asks for `split` and `selection rule` as
      separate fields and never relates them, so a split copied from a study of a different shape
      looks like rigour and behaves like a sample cut.
      **CLOSED 2026-08-30 at the template AND at the gate.** `PREREG_TEMPLATE` §5's form now carries
      a `split buys` field with `none` as an explicitly legitimate answer, §7 carries the accounting,
      and rule 7 states it. Gate 25 gained condition 6: a reported study must DECLARE `split.buys`,
      the same shape as the `perturbations` condition and for the same reason - `none` is a
      declaration, silence is not. All seven reported studies now carry it, read from each
      pre-registration's own §5 and marked `recorded`; no measurement changed.
      **The DATES were never the declaration**, and that is what the gate had to be written around:
      `PR-002` carried a full three-way train/validation/test block from the day it ran while the
      question of what it bought went unasked for the study's whole life. A condition satisfied by
      the presence of a `split` key would have passed `PR-002` and `PR-012` both. A test pins that.
      **What is NOT closed:** the pooled re-run. Rule 3 still downgrades it to exploratory for
      whoever has read the numbers, and this session has.

- [ ] **`[v]` A DECISION RULE NEEDS A BRANCH FOR "BOTH THE ARM AND THE CONTROL ARE NEGATIVE" —
      `PR-013` found it, could not fix it, and the template now asks for it.**
      `PR-013`'s two reject clauses were *the CI includes zero* and *the point estimate is at or
      below the control's*. Its `MARKET` arm's holdout CI **excluded** zero — entirely **below** it
      — while its mean (-0.007595) sat very slightly **above** the control's (-0.007938). Neither
      clause fired, so an arm sitting wholly in negative territory landed in `inconclusive`.
      Confirmed against the registered function rather than inferred.
      **It could not be fixed by the study that found it.** Patching a decision rule after seeing
      the data is the redesign `PREREG_TEMPLATE` rule 3 downgrades, so `PR-013` disclosed the gap
      and left it — correctly.
      **Closed at the template 2026-08-30:** §6's form now requires a `both negative` branch and
      rule 8 states why. Comparing two losers on which loses less is not a finding.
      **NOT closed at a gate, and the reason is stated rather than left as an omission.** Gate 25
      checks declarations against a verdict; this one needs the arm's and the control's point
      estimates declared in a comparable shape, and the seven reported studies do not share one.
      Requiring it retrospectively would mean inventing a schema for results already published. The
      next study to register a comparison should declare both, and the gate can bite from there.

- [ ] **`[v]` PR-013 RAN, THE SAMPLE RULE WAS MET, AND THE ORDERING CARRIES NOTHING BEFORE COSTS.**
      2026-08-24, owner direction (variant C). `docs/prereg/results/PR-013-report.md`; derive every
      figure with `python tools/run_pr013.py --data <store>`, never from this line.
      **The sample problem is solved and that is the structural result.** 142 holdout formation
      dates against a minimum of 100 — `PR-012` could reach only 181–203 trades against its own 200
      and refused. What bought it was the HORIZON, not the unit: five-session formation gives five
      times as many independent dates as a twenty-session hold permits trades to be opened. Ranking
      names rather than trades buys nothing by itself — every name ranked on one date shares that
      date's market move, so a cross-section is ONE observation. That correction was made while
      designing and is the transferable part.
      **The finding is in the GROSS column and it is stronger than the verdict.** All six gross
      intervals include zero, in both periods and all three arms. Largest point estimate +0.24% over
      five sessions, interval −0.15% to +0.61%. The three forms do not separate from each other
      either. Survivorship biases every figure UPWARD, so a measurement inclined to find an edge
      found none.
      **The net column is arithmetic, not a finding:** 100 bps per formation date at a five-session
      rebalance is ~50% a year, larger than every point estimate, so every net interval is below
      zero by construction.
      **The registered decision rule has a gap, disclosed rather than patched.** An arm whose CI
      sits wholly BELOW zero landed in `inconclusive`, because §6's reject clauses are "CI includes
      zero" or "at or below the control" and neither fires when both arm and control are losing.
      Confirmed by calling the registered function. **The next pre-registration needs a branch for
      *both arms and control are negative*** — comparing two losers on which loses less is not a
      finding. Fixing it now would be the redesign rule 3 downgrades.
      **3 trials spent.** Exploratory by declaration (§0b), so it advances no validation status and
      sets none of `CARD-001`'s four `unset` inputs.
      **It does not refute the family** (§9): one lookback and one horizon, neither searched, and
      that was deliberate to avoid spending trials on a sweep.
- [ ] **`[v]` PR-012 RAN AND REFUSED A VERDICT — and the reason is structural, not fixable by
      data.** 2026-08-24. `docs/prereg/results/PR-012-report.md`; derive every figure with
      `python tools/run_pr012.py`, never from this line.
      **The sample rule fired.** §8 fixed a minimum of 200 holdout trades per arm and said what
      happens if it is not met: *"the study reports the measurement and refuses a verdict."* Two of
      three arms are under it and **one of those is the CONTROL**, so the comparison does not exist.
      That is a REFUSAL, not an `inconclusive` — the first says there was not enough data to look
      with, the second says the study looked and could not tell.
      **§8 predicted this exact failure mode before the run**, and the arithmetic is now measured: a
      four-position book held at most 20 sessions is a ceiling of about 50 entries a year, so a
      2.9-year holdout supplies roughly 145 trades at best. **The universe was deepened for this
      study** — median 510 bars to 2,512 — **and the ceiling did not move**, because the binding
      constraint is `risk.max_concurrent_positions` against `exit.max_holding_period` and BOTH ARE
      RATIFIED. Every route out changes something ratified or the study's shape; the report lists
      them with what each costs.
      **Observations, which are not evidence:** every holdout interval straddles zero, and neither
      ranking arm beat the momentum control. So even at an adequate sample §6's `accept` branch
      could not have fired.
      **Three trials spent.** A refused study still spends them — `b.deflated_sharpe` deflates by
      shots taken at the data, not by shots that produced an answer.
      **Two gates could not represent an honest outcome, and both are fixed.** Gate 3f's verdict
      vocabulary had no `REFUSED`, so the first study to hit `PREREG_TEMPLATE` §8 failed the gate
      for obeying the template. And `trial_budget.py` counted PR-012 as **0** trials because it had
      no per-study rule — it now reads a study's own declared `trials`, which is what §6 of the
      template requires a study to state before it runs.
      **Open:** pooling the primary window is the honest route to a sample, and §5 fixed the split
      before the run, so it needs a NEW pre-registration rather than an amendment.

- [ ] **`[v]` `a.reproducible` HAS NEVER BEEN MEASURED ON THE REAL UNIVERSE, and the reason is
      not the one `HANDOFF.md` gives.** Found 2026-08-24 by reading `journal.duckdb` rather than the
      documents.
      Gate 9 checks it on `golden/replay/daily-three-instruments` — real, and **three instruments**.
      Determinism defects live where iteration order, set membership and dictionary insertion have
      room to differ, and three names give them almost none.
      **The sharper finding:** `HANDOFF.md` says the 12 dirty-tree journalled runs hold this
      criterion short. Measured: of 22 runs, 12 carry `code_dirty` — but **not one of the ten CLEAN
      ones was recorded at the code this repository now runs.** So replaying any stored manifest
      today mismatches on `code_hash`, correctly and uninformatively. The criterion is about a
      re-run at the SAME code, so no stored run could demonstrate it whatever its dirty flag says.
      Also measured: **every scheduled run from 2026-08-17 onward is clean**; the dirty ones are
      2026-08-02 → 08-14 plus one manual run on 08-22. The dirty-tree era is over and its records
      are immutable, so nothing there is fixable — only supersedable by a clean demonstration.
      **BUILT: `tools/verify_reproducible.py`.** Runs the pipeline twice at one pinned clock over
      the stored universe and compares output hashes. Same code, same snapshot, same parameters, so
      **nothing pinned CAN change** — which makes a mismatch here a stronger signal than one in gate
      9. Both passes journal into a **throwaway** database: a determinism check that wrote to
      `data/journal.duckdb` would add two runs to the evidence record every time anyone asked, and
      `a.run_completes` counts journalled runs.
      Reports `UNAVAILABLE` (exit 4) rather than a traceback when a store is held by another
      process — `ADR-0004` makes them single-writer, so a refresh pass holding one is the design
      working.
      **RUN 2026-08-24, AND IT PASSES.** Both passes over the full **1,141**-instrument universe
      produced output hash `50e1646b933a4a9d`. **`a.reproducible` has its first production
      measurement**, and it is one of the four Track A criteria `k.track_a_timebox`'s kill trigger
      counts. Derive it with `python tools/verify_reproducible.py --data …`, never from this line.
      **What it does and does not establish.** It establishes that the decision path is
      deterministic over 1,141 real instruments carrying a median of 2,512 bars each — where
      iteration order, set membership and dictionary insertion have every chance to bite, and gate
      9's three-instrument case gives them almost none. It does **not** establish that a stored
      manifest replays: no journalled run was recorded at this code, and that remains true.
      ~~**It is slow — about twenty minutes a pass** on the deepened store, so it is a deliberate
      check rather than a merge gate.~~
      **RE-MEASURED 2026-08-24 after the performance work in §2: 11m40s for BOTH passes**, so
      about six minutes each including 1,141 live vendor fetches. Still a deliberate check rather
      than a merge gate - it touches the network, which `CI_POLICY` §4 forbids a gate to do - but
      the reason is no longer the clock.
      **And it re-established the criterion at the NEW code, which is the point:** both passes
      produced `50e1646b933a4a9d`, byte-identical to the hash this same tool recorded on `master`
      before any of the changes. Same decision output over the full production universe, from
      different code.

- [ ] **`[v]` `M31-T0464` IS `specified` — 2026-08-24, and the gate caught the shortcut.**
      `derived_observations/relative_strength.py` computes the RS line: the ratio of an
      instrument's close to `rs.benchmark`'s, rebased to 1.0 at their first SHARED session. An
      `ALGORITHM_SPEC` record in the docstring, seven property tests, no parameters.
      **Parameter-free on purpose.** The ratio is the OBSERVATION; a change in it over a lookback is
      a READING of it, and `rs.lookback` belongs to whatever measures the change. A component with
      no unset parameter can never refuse for want of a value.
      **The docstring states what it cannot do**, because the misuse is natural: ranking a
      cross-section by this value is identical to ranking by raw return (`DR-018` §1). The RS line
      is a legitimate thing to look at and a decorative thing to sort by.
      **Gate 11 refused the first version.** It claimed `M31-T0464` AND `M77-T1138` — the same
      measure at the Setup stage — reasoning that one implementation beats two. **Production Rules
      3.8 forbids two components sharing one definition**, and the rule is about what a catalogue
      row MEANS rather than about duplicated code. `M77-T1138` stays `registered` until someone
      reads the source PDFs and can say whether it names something distinct; those PDFs are not in
      this repository.
      **Still `specified`, not `active`.** It declares no parameters and could activate on
      verification alone — it is held because activation is a decision (`ROADMAP` §9), the same
      reason ATR and SMA are held.
      **Open:** `M31-T0465` (the hypothesis) and `M33-T0487` (the screen) are still `registered`,
      and both need `PR-012`'s values.

- [ ] **`[v]` THE BENCHMARK EXISTS NOW, AND POINT-TO-POINT RELATIVE STRENGTH IS DECORATIVE** —
      `DR-018`, written 2026-08-24, `proposed`. Derive every figure with
      `python tools/measure_benchmark.py`, never from this line.
      **The blocker was cheap and the fix found something expensive.** No index series was stored
      only because coverage is an ALPHABETICAL PREFIX that had not reached the letter S; `SPY`,
      `QQQ`, `IWM`, `IVV` and `VOO` were already eligible ETF rows. Fetched, five years each.
      **The finding: on ONE cross-section a benchmark cannot change a ranking.** The usual
      `(1 + own) / (1 + benchmark)` is a strictly monotone transform of the name's own return,
      because the benchmark's return is one constant for every name that day. Measured as a control
      that must return exactly 1: **15 of 15** benchmark x lookback pairs give Spearman
      **1.000000** against ranking on raw return alone, over 1,148 names. So point-to-point relative
      strength is **momentum with a decorative denominator**, and a card declaring it would be
      declaring the family `CARD-001` was chosen to avoid.
      **A PATH-dependent form escapes the identity** — share of sessions the name beat the benchmark
      reads about **0.6** against raw return — and there the index choice bites: SPY against QQQ at
      **0.616** on 63 sessions, while SPY against IVV (same index, different fund) reads **0.973**.
      **The INDEX is the decision; the PROXY is not.**
      `rs.benchmark` = `SPY` (`assumed:DR-018`); `rs.benchmark_form` **`unset`**, because the form
      decides what the card trades and `ALLOCATION_SPEC` §3 sends that to a pre-registration.
      **The RAW-price dividend bias is measured too**, and it survives every choice above: SPY
      **1.52%** a year against QQQ's **0.68%**, so a benchmark comparison that ignores it compares
      two differently-taxed series. The store holds **no adjusted series at all**.
      **`corporate_actions` is no longer empty** — `DR-016` §8.5's finding gets its first caller
      outside the held-position split guard: 101 dividend records for the five funds.
      **Sector-relative strength — MEASURED the same day** (`DR-018` §7,
      `tools/measure_sector_relative.py`). It was the other way out of the identity and it DOES
      reorder: over 1,023 admitted names carrying a dominant sector across all 11 sectors, rho
      against raw return runs **0.750 to 0.819**, where the market point-to-point form gives exactly
      1.0. The tool prints that second column as a CONTROL and fails the run if the two ever differ.
      **The reading that is easy to get wrong: it reorders LESS than the market PATH form does**
      (about 0.6). **Further from raw return is not better.** Both departures are real, neither is
      evidence, and which one predicts is a question only a pre-registration answers.
      **Four measured options now exist** — market or sector, point-to-point or path — and none is
      ratified. `rs.benchmark_form` stays `unset` on purpose: having four characterised options
      rather than one guessed one is what `DR-018` was for.

- [x] **`[v]` The backtest engine expressed ONE strategy family, and it was the refuted one — FIXED
      2026-08-24.** `run_arm` called `breakout_high` directly and the `gate` argument was a per-bar
      FILTER over that call rather than the trigger itself, so the engine was long-only time-series
      breakout with a boolean regime filter and nothing else. Every study, every trade log and the
      whole cost-model calibration describes that one family. A cross-sectional ranking rule or a
      mean-reversion rule **could not be run at all**.
      **The claim that hid it was a SIGNATURE.** `run_arm(series, gate, atr, config)` reads like a
      parameterised engine; the body is what owns "does this code support X" (`AGENTS.md` §12).
      **What changed:** `EntryTrigger` is a protocol answering `True` / `False` / `None`, the third
      being "the rule had nothing to answer with" — the state `unevaluable_bars` counts and the one
      a boolean return would silently fold into a rejection. `BacktestConfig.trigger` replaced
      `trigger_lookback: int = 20`, and **has no default on purpose**: the old default quietly made
      every unconfigured backtest the refuted family, which is a strategy choice nobody made.
      **The guard rail was run, not assumed.** The pre-change and post-change engines, over the same
      store at the same instant, emit a **byte-identical** `PR-005` trade log — established by
      stashing the refactor and re-running, because "a trigger refactor cannot move an exit date" is
      a plausible sentence and not a measurement. Two mutants die: an engine ignoring the injected
      trigger takes 17 tests with it, and one collapsing `None` into `False` takes 2.
      **`tools/run_pr005_replay.py` gained `--data`** so the guard rail can be run from a worktree
      at all; it hardcoded a path that exists only in the main checkout.
      **Still open, and it is the point of the change:** nothing has been RUN through the second
      family. `CloseBelowLow` exists to prove the seam and is **not a proposed strategy** — no card
      declares it and no study registers it. Spending a trial on a family needs `ROADMAP` P5 first.

- [ ] **`[v]` PR-007** registered, unreported — **checked 2026-08-30 against the files rather than
      the mark**: `docs/prereg/PR-007-base-strategy-measured-costs.md` exists and
      `docs/prereg/results/` holds no `PR-007-report.md`. It and `PR-009` are the two registered
      studies with no report, which is what `HANDOFF.md` §2's studies row counts.
- [ ] **`[v]` PR-009 — ~~blocked on Task 8~~. TASK 8 IS DONE, AND THE STUDY IS NAMED AFTER A
      SUPERSEDED THRESHOLD.** Re-checked 2026-08-25.
      **Its title and §1 say −15R.** The registry holds `validation.max_allowable_drawdown` = **20,
      percent of equity, `owner`**, and has since 2026-08-08 — the day PR-009 was registered.
      `DR-007` §3.7 proposed −15R, called it *"the weakest of the fifteen"* and *"the one to argue
      with"*, and the 2026-08-09 reconciliation superseded it because `owner` outranks
      `assumed:DR-007`. **Fourteen of DR-007's fifteen were adopted as proposed and PR-009 quotes
      three of them correctly; the one it got wrong is the one it is about.**
      **Today the units coincide exactly**: `risk.per_trade_pct` is 1.0 percent and `account.equity`
      is static, so 1R is 1 percent of equity and the pause sits at **20R**. The method survives with
      the threshold restated — the title, §1, §3 and §6 all name −15R. That is a registration change.
      **Task 8's blocker is discharged and a different one replaced it**: the trade log exists
      (`docs/prereg/results/PR-005-trades.csv`) and no longer reproduces (§5 above, owner's call).
      New research is also suspended, overridden for `PR-013` only.
      Corrected forward in `PR-009` §10, `prereg/README.md`, `DR-006` §18, `ALLOCATION_SPEC.md`,
      `GO_LIVE_GATES.md` and `CI_POLICY.md`.
- [ ] **`[v]` Reserved prereg ids with nothing written yet:** PR-001b (unblocked, writable now) ·
      PR-003 (needs a daily return series) · PR-004 (needs ~100 journalled trades) · PR-006 (needs a
      forward test). **Checked 2026-08-30 against `docs/prereg/README.md`**, which is the index gate
      3f keeps honest and the only place this belongs; `PR-011` is also unwritten and is tracked in
      its own item two rows down, which is why it is absent here rather than missing.
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
- [x] **`[v]` Prereg id-reservation has a gate — 29, built 2026-08-24.** The index said *"worth
      fixing if a third one appears"* and a third had. `tools/verify_prereg_ids.py` catches all
      three shapes: a study document missing from its own index, an id reserved **by reference
      only** anywhere in `docs/` and not listed (the `PR-006` case the index itself said nothing
      could find), and **two unmerged branches numbering different studies the same** — which is
      `AGENTS.md` §10.2 as a check rather than a habit.
      **Merged branches are excluded, and that is a rule rather than a convenience.** Measured:
      this repository's two real collisions — a second `PR-006` and a second `PR-007` — are both on
      **merged** branches, so the numbering was reconciled and their old filenames are correct
      statements about a commit, the same way a struck-through count is.
      **The cross-branch half says when it could not run.** A shallow CI clone has no other
      branches, and gate 16 and gate 23 both went green-from-the-wrong-place before `AGENTS.md`
      §10.6 rule 2 was written. Five tests, including a real two-branch git fixture that collides.
      **One defect the first run found in the gate itself:** `results/PR-001-report.md` read as a
      second claim on the number, so every reported study collided with itself. A study's output is
      not a reservation.
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
      (citing US-022 without checking it was live). Every gate and every test passed, DONE
      2026-08-11.
- [x] **`[v]` ~~MEASURED 2026-08-17: 3 of 11 mutants survive the entire test suite.~~ RE-MEASURED
      2026-08-29: ALL THREE ARE DEAD, AND NONE OF THEM DIED ON PURPOSE.** The entry was `[v]` and
      steered a build order for twelve days; nothing had re-run it, which is the shape this file
      exists to catch.
      **Method, and the control is the part that matters.** `src/` copied to a scratch root beside
      `registry/`, `golden/` and `docs/`, one mutation applied there, the **whole** suite run against
      the copy. The unmutated copy runs green first — without that, a red result is evidence about
      the fixture rather than the mutation (`AGENTS.md` §9). The first attempt did produce exactly
      that false kill: `src/` alone in a scratch directory makes `test_checklist.py` fail on a
      registry it resolves through the package, and it looks like a dead mutant.
      **What killed each, and it is a different mechanism every time:**
      • `planned_risk` → `Decimal('42')` — killed by the invariant-1 test, which was **rewritten**
      on 2026-08-25 because gate 34 found it asserting `(net/x)*x == net`. The mutant is now one of
      gate 34's own.
      • `risk_per_share = entry - stop + costs` → `entry - stop` — killed by **five** tests, three
      invariants and both replay cases. PR #9 made the R denominator cost-inclusive on 2026-08-17
      and the tests came with it; the survivor died the same day this entry was written.
      • `calendar.sessions_behind` off by one — killed by **seven** freshness tests. `DR-015` wired
      the staleness gate on 2026-08-18, so the *"spec rule implemented in dead code"* half of this
      entry is stale too: `market_data/freshness.py` calls it and `pipeline.py` reaches it from
      there. That is the same false null `AGENTS.md` §12 records the graph reporting for
      `freshness.assess`.
      **Both of the two not already covered are now gate 34 mutants**, so the kills stop being
      incidental: the cost term under invariant 1, the session count under the staleness veto.
      Derive the list and the count from the tool, never from here:
      ```bash
      PYTHONPATH=$PWD/src python tools/verify_invariant_tests.py
      ```
      **And this file had already said so, in another section, six days earlier.** §1's R-denominator
      entry carries *"RE-MEASURED 2026-08-23 … the survivor count is 0 of 11"*, with the same three
      mutants and the same causes. Two sections of one document held opposite answers to one
      question, and the stale one is the entry a reader meets under **Code & gates** — which is
      where someone goes to decide what to build. `AGENTS.md` §10.5's disease does not need two
      documents; one is enough. Nothing catches it: gate 14 owns counts in `HANDOFF.md` §2, and a
      survivor count has no owner at all, which is §4's open question about STATUS restated as a
      number.
      **What this does NOT overturn:** the build order below. Every kill came from a test written
      for a *feature*, not from a mutant list — which is the entry's own conclusion, confirmed
      rather than refuted. The mutant list is cheap insurance against those tests being weakened,
      and that is exactly what putting these two into gate 34 buys.
      **The original measurement, kept because the method and the three non-negotiables are the
      transferable part:** The council's
      own flip condition, turned from an assumption into a number. Method: patch one computed
      quantity per module in committed source, run the **whole** suite, restore, record whether
      anything died. **`git stash push -- src/` cannot do this** — it reverts *uncommitted* work, so
      on a clean tree it stashes nothing and the suite runs unchanged. That is precisely why
      `AGENTS.md` §12's ritual only ever applied to newly written tests, and why auditing the
      existing 480 needs real mutants.
      **The three survivors, and they are not one kind:**
      • `sizing.py` — `planned_risk` replaced with the constant `Decimal('42')`. **The R denominator
      the entire validation programme is expressed in.** Suite green, DONE 2026-08-13.
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
- [x] **`[v]` ~~Six gates have never been proven able to fail.~~ CLOSED 2026-08-24 — and it was six
      only on the day it was written.** `tests/test_gates.py`'s own docstring sets the bar: *"A gate
      that has never been seen red proves nothing"*.
      **Re-measured before working it, by asking the test file rather than this entry.**
      `verify_parameters` (1) and `verify_components` (11) got tests on 2026-08-18 and this item was
      never updated — so the list of things this repository has not caught yet had itself gone stale,
      which is the shape the whole file exists to catch. Derive the current answer, never from this
      line: grep `tests/` for each `tools/verify_*.py` name.
      **The remaining four are done**: 3g (a ratified criterion resting on an `unset` parameter, and
      one naming a parameter absent from the registry), 3e (a dangling citation, an absent parameter,
      a status off the ladder, a gap summary disagreeing with a recount of its own table), 3f (a
      refuted study validating a parameter — the `PR-002` defect, which gate 3e cannot see because
      every reference resolves; plus an index disagreeing with its report, and a verdict token
      outside the vocabulary being named rather than counted), and 2 (a declared source that cannot
      be resolved, and an enum member that has left the document defining it — both need no PDF, so
      they run where CI reports gate 2 `UNAVAILABLE`).
      **What kept them last was structural, not neglect.** Each one's subject is the real tree, so
      planting a defect meant either editing the repository — which this suite must never do — or
      giving the gate a fixture root. `verify_docs` and `verify_criteria` already honoured
      `SWINGDESK_ROOT`; `verify_studies` did not, and now does.
      Every defect test has a positive control on the same fixture, so a red result cannot come from
      a broken fixture instead of the planted defect.
- [x] **`[v]` THE FOUR `--check-only` GENERATORS COULD NOT BE SEEN RED, AND NOW CAN — 2026-08-30.**
      `tests/test_gates.py`'s own docstring sets the bar: *"a gate that has never been seen red
      proves nothing"*. Gates **3b**, **3c**, **3ci** and **3d** were the last of ours below it, and
      the obstacle was structural rather than neglect — the same one `verify_studies` had: without
      a fixture root the only way to make a `--check-only` fail is to edit the real tree, which the
      suite must never do. All four honour `SWINGDESK_ROOT` now, and each has a failure test.
      **`AGENTS.md` §10.6 rule 1 is why these mattered more than their size** — *"if a fact can be
      derived, a tool derives it and `--check-only` gates it"* is the load-bearing sentence under
      every generated document, and four of the five instances had never been exercised.
      **The fixture copies the REAL inputs and lets the generator write its own output**, so the
      test exercises real parsing rather than a stand-in that could agree with a broken generator.
      Then it corrupts the output. **Proven, not assumed:** disabling one generator's comparison
      turns exactly that parameterisation red and leaves the other three green.
      **The audit that found them was wrong the first time, and the correction is the lesson.**
      Matching each gate's tool as `<name>.py` in `tests/` reported **14** gates without a test.
      Five of those were false — the tests name the module without the `.py`, and four more are
      third-party (`ruff`, `mypy`, `import-linter`, `pytest`), whose ability to fail is not this
      repository's claim to prove. The real answer is four, all one class. A proxy that looks like
      a measurement is `AGENTS.md` §12's trap, and the positive control is what caught it — the
      same §9 discipline, applied to an audit instead of to the graph.
- [x] **`[v]` GATE 32 — a checklist item's stated blocker must still be blocking. Built 2026-08-25.**
      `plans/2026-08-24-the-trade-flow.md` §3 stage 4 opens by asking for each `_unavailable` reason
      to be re-checked *"since two were suspected stale and a third may be by the time this is
      worked"* — eight prose strings, read by hand, with no mechanism and no record that the reading
      had happened.
      **The direction of the failure is what makes it expensive.** A reason that outlives its
      blocker keeps a pre-trade item `UNAVAILABLE` after the thing blocking it was supplied, so
      Appendix E goes on returning `Research` and `Trade` stays unreachable for a cause that no
      longer exists.
      **Written for the instance that is about to happen.** `entry.maximum_entry_atr` is `unset` by
      `DR-020` §3 and two items wait on it — `E08` and `E09`, the two of the eight that gate
      *existence* rather than quality. Ratifying `DR-020` is item 1 on `HANDOFF.md` §5's ranked list.
      Before the gate, neither sentence even named the parameter.
      Nine pins across six of the eight items; `E03` and `E05` rest on a missing capability with no
      registry row to pin and are named on every run rather than passed over.
      ```bash
      PYTHONPATH=$PWD/src python tools/verify_checklist_blockers.py
      ```
- [x] **`[v]` GATE 33 — a live branch rewriting the lines you are rewriting. Built 2026-08-25,
      the day it fired on this session.** Gate 16 makes a sibling worktree VISIBLE; it does not say
      the sibling is editing your paragraph. Both trees corrected `RISK_REGISTER.md` D-3 and the
      Canadian row of `UX_TASK_FLOWS.md` on 2026-08-25, two hours apart, with gate 16 green and both
      sessions having read the branch list. Reading the sibling's commit SUBJECTS did not reveal it,
      because they named its other work; reading its DIFF would have, in one command.
      Overlaps are computed in **merge-base coordinates**, so a hit means both trees rewrote the
      same original text rather than merely touched the same file — two sessions appending to
      different parts of this file do not collide and are not reported.
      **Advisory, and it must stay advisory**: parallel work is normal here and vetoing an overlap
      would block ordinary work, which is how a gate gets bypassed (`CI_POLICY.md` §3).
      **It does not run in CI** — a shallow clone has no siblings — and it says so rather than
      reporting clean, the same handling as gate 29's cross-branch half.
      ```bash
      python tools/verify_sibling_edits.py
      ```
- [x] **`[v]` GATE 34 — the tests `INVARIANTS.md` names must be able to fail. Built 2026-08-25.**
      `INVARIANTS.md` §1 said *"seven of nine are enforced by a test that would fail if the
      invariant broke"*, and for invariant 1 that was false for three weeks — the named test
      asserted `(net/x)*x == net`. Gate 8 says the tests pass; **nothing said they could fail**, and
      the document is what a reader trusts.
      Fifteen mutants **on the day it landed**, each a committed source edit applied to a **scratch
      copy** of `src/` — which matters here because two of them land in
      `trade_management/sizing.py`, a frozen file. All were killed, and the list has grown since;
      the tool prints what it holds rather than this line carrying a copy.
      **It also closes the half of `REQ-VALIDATION-001` that `REQUIREMENTS.md` §2 called impossible.**
      That paragraph said mutation testing *"needs a corpus of evaluated criteria before it can.
      Nothing evaluates these yet, so a mutation gate here would have nothing to flip."* It was
      correct when written and went stale: `DR-006` wired the concurrent-position, open-risk,
      correlation and sector caps into the live path and `DR-015` wired the staleness gate. All five
      are now forced to **admit everything** — TradAlert's `if is_long: return True`, which passed
      seven audits — and a named test catches each. **Still `partially met`**: the requirement also
      covers ratified criteria, and `k.drawdown_pause` has no verdict to flip (§1 above).
      **A mutation site that no longer matches is a FAILURE, not a skip**: refactoring the line a
      mutant targets is exactly when the check must speak up.
      Invariants 4 and 7 have no mutant — a signature and a pure function — and the gate names them
      every run rather than reporting a pass over them.
      ```bash
      PYTHONPATH=$PWD/src python tools/verify_invariant_tests.py
      ```
- [x] **`[v]` GATE 7 WAS THE ONE GATE OF THIS REPOSITORY'S OWN MAKING WITH NO FAILURE TEST, AND THE
      AUDIT THAT CLOSED THAT CLASS COULD NOT SEE IT. Fixed 2026-08-25.**
      The closed item above derives its list by *"grep `tests/` for each `tools/verify_*.py` name"*.
      Gate 7 lived as an inline function in `check_gates.py`, so it had no tool file to grep for and
      no way to be pointed at a fixture — **a derivation method with a blind spot exactly the shape
      of the thing it was deriving.** Extracted to `tools/verify_no_wall_clock.py`, honouring
      `SWINGDESK_ROOT`, with seven failure tests including two positive controls.
      **It also now enforces `REQ-DATA-001`'s second clause** — *"No event date may appear as a
      literal in executable code"* — which was a MUST whose status cell read *"verified"*, once, by
      hand. Measured before building: **zero** date literals across all 70 modules in `src/`, so
      this is prevention rather than repair. A hard-coded earnings date is what arrives under time
      pressure and it makes a point-in-time claim false in a way no test notices.
      Both halves are AST-parsed: a `date` built from variables passes, a docstring mentioning
      `datetime.now()` passes, and `market_data` may read the clock because only three packages are
      pure.
- [x] **`[v]` Two tools claimed gate 16 — fixed 2026-08-25.** `verify_studies.py`'s docstring opened
      *"Gate 16"*; that is `verify_branches.py`'s number, and both `check_gates.py` and `CI_POLICY.md`
      call `verify_studies.py` gate 3f. One line, and the kind that sends a session to the wrong file.
- [x] **`[v]` GATE 35 — a document naming a test must name one that exists. Built 2026-08-25.**
      `INVARIANTS.md` §1 and `REQUIREMENTS.md` §7 both argue enforcement by naming a test, and a
      reader takes the name as proof. **Renaming a test is ordinary, safe work that no other gate
      would notice**, and it silently falsifies the documents a reader trusts to know what is
      enforced. Gate 28's shape aimed at a different subject.
      Measured before building: **23 names cited across the governed documents, 0 unresolved.** So
      this is prevention, and it costs nothing while the answer stays zero.
      Append-only stores are excluded — gate 20 already covers a decision record's `implemented_by`
      marker — and a line marked as history is left alone, the same convention as gate 28.
      ```bash
      python tools/verify_cited_tests.py
      ```
- [ ] **`[v]` THE SECOND PASS DOES NOT RUN ON EXACTLY THE DAYS IT IS FOR — measured 2026-08-29.**
      Both scheduled tasks report the same last run, `2026-08-29 18:50:57`: `StartWhenAvailable`
      caught up the missed triggers together, the first pass started, and the second exited
      **`-2147020576`** = `0x80070420` = `ERROR_SERVICE_ALREADY_RUNNING`.
      **The two failures are not independent, which is the whole finding.** A catch-up happens on
      the days the machine was asleep or logged out; those are the days most likely to carry stale
      data; and the retry that exists to repair stale data is the thing the catch-up kills. Gate 26
      reports it, CI cannot see it (`UNAVAILABLE` off the scheduling machine).
      **A scheduling decision, not a code one**, and it belongs with `DR-019` (the conditional second
      pass), which is still `proposed`: a delay or start-boundary on the second task, or making it
      conditional on the first having finished.
- [ ] **`[v]` THE DAILY RUN MAKES THE NEXT DAILY RUN `code_dirty`, AND NOBODY PRICED THAT — found
      2026-08-29.** ~~My own uncommitted work marked three evenings of scheduled runs dirty.~~
      **That attribution was wrong and is corrected here**; the worktree was clean from the evening
      of 08-25 onward, and the runs went on being dirty anyway.
      **The real cause is in `daily_run.cmd`'s own comment.** Its last step regenerates
      `HANDOFF.md` §2, and the comment says so plainly: *"this leaves `HANDOFF.md` modified and
      uncommitted in the main checkout most evenings."* The manifest's `code_dirty` is computed while
      the pipeline runs — **before** that regeneration — so the flag each evening records the
      PREVIOUS evening's leftover. The chain is visible in the journal: 08-24 both passes clean, the
      08-25 18:30 pass clean, and every pass from 08-25 19:30 onward dirty.
      **The wrapper weighed two costs and there is a third.** Its comment trades an advisory gate-21
      note against gate 24 being red every morning, and picks the note. It does not mention that the
      leftover spends **`a.reproducible`** — one of the four Track A criteria — because a manifest
      pointing at a dirty tree cannot be replayed from its SHA. Those evenings are immutable.
      **Not fixed here.** `tools/daily_run.cmd` is a frozen file, and the options — commit the
      regenerated block, or move the regeneration out of the wrapper — are a decision about what the
      scheduled run is allowed to do to the repository.
      **A THIRD option, and it is the one that says what is really wrong — measured 2026-08-30.**
      `pipeline.py` computes `code_dirty=bool(_git("status", "--porcelain"))` — **the whole working
      tree**, documents included — while `code_hash` is just `rev-parse --short HEAD` and says
      nothing about which files moved. So a modified `HANDOFF.md` marks a run unreplayable by
      exactly the same mechanism a modified `sizing.py` does, and the field's own description says
      it is about *"the code"*. **The verdict is defensible and the SUBJECT is wider than the
      name**, which is the third time today that shape has turned up (gate 24's cause, `DR-006`
      §8.7's reason).
      **What a narrowed check would have to keep**, so this is a proposal rather than a complaint:
      `src/`, `tools/`, `registry/` and `golden/` all feed a run and a dirty one there genuinely
      breaks replay. What does not feed it is `docs/` and the root documents — and the root
      documents are the only thing the wrapper dirties.
      **Still the owner's, and for a better reason than the freeze.** Narrowing moves runs from
      *not replayable* to *replayable*, which is the permissive direction on `a.reproducible`, one
      of the four ratified Track A criteria. `AGENTS.md` §3: nothing may look more validated than it
      is. An agent measuring the subject is right; an agent widening what counts as evidence is not.
      **What cannot be recovered either way:** the journal stores one boolean per run, so which
      files were dirty on any past evening is gone. A narrowed check would apply forward only.
      **ANSWERED AND BUILT 2026-08-30 — `DR-022`.** The owner ratified the narrowing and it is in
      `pipeline.DECIDING_PATHS`: `src/`, `tools/`, `registry/`, `golden/`. The permissive-direction
      objection above is the one the record had to answer, and §5 answers it by measurement rather
      than by argument — `code_dirty` is not in `output_hash`, so narrowing it moves no decision and
      resets no counter. The 18 already-flagged runs keep their flags; `DR-022` §4 records the
      discontinuity that leaves and why re-deriving them is not on offer.
- [ ] **`[v]` GATE 10 IS NOW TWO CHECKS, NOT THREE, AND THE THIRD WAS BUILT UNDER ANOTHER NUMBER —
      re-derived 2026-08-30.** `REQUIREMENTS.md` §7 exists (the linkage the entry below says gate 10
      needs first) and it names what gate 10 should check: *"a row here naming a test or a gate that
      no longer exists"*. **That is gate 35**, built the same day §7 was, and its docstring already
      names `REQUIREMENTS.md` §7 as one of its two subjects. So the narrow check §7 asks for is
      done, and neither document had noticed the other.
      **What is left of gate 10 is checks 1 and 3** — a course id with no requirement row, and a
      spec id cited by no test. Check 2 (a requirement with no test) stays rejected on §7's own
      reasoning: three of the nine correctly have none, and a gate reddening on those would demand
      a test for a capability that does not exist.
      **The half nobody had covered was gate NUMBERS, not test names, and it is gate 38 now.** Gate
      35 resolves a cited TEST; gate 36 keeps the inventory and the runner in step; nothing checked
      a gate number cited in prose, which is exactly what row 12 was — `exists` for seventeen days
      over a number `check_gates.py` has never registered. Measured before building: 363 citations
      across every tracked document, **0 unresolved** once a year and a date are excluded, both from
      one real false positive.
      **Row 10 stays `to build` deliberately.** About twenty documents refer to gate 10 as the thing
      they are waiting for and every one of those sentences is true; gate 38's vocabulary is the
      inventory rather than the runner precisely so those stay legal. Retiring the row would make
      twenty documents stale to save one line.
      **The original entry, kept because its reasoning is what narrowed this:** **Weighed
      and not built 2026-08-25**, with the reason recorded so it is not re-derived: its three checks
      are *a course id with no requirement row*, *a requirement with no test*, and *a spec id cited
      by no test*. The middle one would fire immediately on requirements that are deliberately
      **NOT met** (`REQ-AI-001`, `REQ-AI-002`, `REQ-EVIDENCE-001`), and the third has one active
      component to range over. What it needs first is the linkage `REQUIREMENTS.md` §6 names — each
      requirement paired with the test or gate that enforces it, or an honest "nothing does", the
      way `INVARIANTS.md` §1 already does for its nine. **That artefact is the work; the gate is the
      easy part after it.**
- [x] **`[v]` `CI_POLICY.md` LISTED A GATE THAT HAS NEVER RUN — retired 2026-08-25.** Row **12**
      pointed at `verify_criteria.py` and read **exists**. `check_gates.py` has never registered a
      12: the 2026-08-09 reconciliation found *three* things claiming that number — two tool
      docstrings and this row — resolved it to **3e** and **3g**, and fixed both docstrings. **The
      policy row survived the resolution and said "exists" for seventeen days.** The inventory is
      what a reader counts gates from, and it counted one that is not there.
      Struck rather than deleted, and its TradAlert reasoning — *"an R:R gate was
      `if is_long: return True` and passed seven audits"* — merged into 3g's row rather than lost
      (`AGENTS.md` §11 rule 3: consolidate only with a migration).
      **Row 10 is the honest comparison**: it also has no runner and it says **to build**.
- [x] **`[v]` GATE 36 — the inventory and the runner must name the same gates. Built 2026-08-25,
      out of the row-12 finding directly above.**
      Every other gate protects the tree; this one protects **the list a reader consults to learn
      what is protected**, which nothing else could see. Three exact checks — every registered gate
      has a row, every row claiming to exist is registered, no number is claimed twice — and a gate
      number is a token rather than a judgement, so there is no noise to trade off.
      A row marked `to build` or struck through claims nothing and is left alone, which is how row
      10 has been honest about itself since it was written.
      **What it deliberately does not check:** whether a row DESCRIBES its gate correctly. That is
      prose against behaviour and no gate reads it; what this closes is the two disagreeing about a
      gate's EXISTENCE, which is what actually happened.
      ```bash
      python tools/verify_gate_inventory.py
      ```
- [x] **`[v]` AT MERGE: gates 22 and 31 needed `CI_POLICY.md` rows, and gate 36 insisted. DONE
      2026-08-29 — the two branches are merged and both rows are written.** The prediction held
      exactly: the merge went red on gate 36 and on nothing else of its own making, and the fix was
      the two rows. They are written from the two tools' docstrings rather than copied out of the
      runner's one-line descriptions, because a row a reader consults to learn what is protected
      should say what the gate checks, not what its label says.
      **What the merge also repaired, and it was not predicted.** The sibling had taught
      `tools/build_state.py` to emit the classification command with the flag it requires; this
      side's generated row still carried the form that exits 2. Regenerating §2 fixed it — so gate
      31 arrived and its motivating defect was still live in the block that promises a reader can
      derive the number.
      **The original entry, kept because the reasoning is the transferable part:**
      Checked 2026-08-25 against `claude/swingdesk-open-tasks-2001c8`'s tip: it registers **22**
      (`verify_directory_policy.py`) and **31** (`verify_commands.py`) in `check_gates.py` and adds
      no rows to the inventory. Gate 36 requires the two to name the same gates, so a merge of both
      branches is red until those rows exist. **Two rows; the descriptions are already in the runner
      entries.** Neither branch can add them alone — a row here for a gate this branch does not
      register fails gate 36 from the other side, which is the check being symmetric rather than
      awkward.
- [x] ~~**`[c]` Gate 22** + `DR-008`'s remaining machinery · **Gate 14's word-number hole.**~~ **All three CLOSED by the 2026-08-29 merge, and none of them the way this line
      expected.** Gate 22 is built; `DR-008`'s audit is in §2 clause by clause, with the
      MANUAL-mode gap the only open item left from it; and gate 14's word-number hole was
      built, measured and deliberately reverted — the entry two rows down records why, so
      the next session does not re-derive it. **A one-line `[c]` item naming three
      unrelated things is why this took a merge to notice**: it could not go stale in
      parts, so it read as live in whole.
- [x] **`[v]` GATE 31 BUILT 2026-08-25 — a command a document tells you to run is a command that
      runs.** `HANDOFF.md` §2's **generated** census told a reader to derive the classification
      coverage by running `measure_sector_cap.py` with `--wide` and nothing else. That exits 2:
      `--classifications` is required and has no default. **The one promise §2 makes — derive it
      rather than trust the row — was unkeepable for anyone who tried**, and `tools/build_state.py`
      had emitted it that way since the block was built.
      *(The broken form is described here rather than quoted, because gate 31 objects to a
      document reproducing it — correctly. Quoting a defective command verbatim is how this one
      spread in the first place, and the gate declining to make an exception for its own write-up
      is the property working, not a false positive.)*
      **Three of the five mentions of that tool were unrunnable, and the third is the finding:**
      `UX_TASK_FLOWS.md` got its copy from a session reading §2 and quoting it. This session then
      did exactly the same thing — copied the broken form out of §2 into a row it was writing — and
      the gate caught its own author. A broken command propagates precisely like a stale count.
      **Nothing caught it because a command is neither a citation nor a count.** Gate 3e resolves
      references, gate 24 regenerates numbers. It looked checked from three directions and was
      checked from none.
      **What it found on its first run, all true positives:** the generated row above; `DR-008`'s
      emergency command (two flags argparse never had — see §2); and
      `plans/2026-08-11-evidence-foundation.md` Step 4 naming `--out` on `run_pr005_replay.py`,
      which shipped with `--write` + `--accept-drift` instead. **The plan asked for one key and the
      tool deliberately shipped two**, so that command was overtaken by a decision, not renamed.
      **It also produced two FALSE positives on its first run and they are pinned by a test.**
      `python a.py && python b.py --flag` was read as `a.py --flag`, reporting `AGENTS.md` §2 and
      `docs/README.md` — both correct — as defects. Argument capture now stops at a shell operator.
      A gate whose output must be skimmed is how a real finding gets skipped.
      **Static only, and that is a tested property rather than a claim.** The parser is read out of
      the tool's syntax tree; nothing is imported and nothing is executed, so a gate about running
      commands cannot breach `CI_POLICY.md` §4. `test_the_gate_never_executes_the_tool_it_checks`
      plants a tool that writes a file at import time and was **confirmed red** against a deliberate
      `runpy.run_path` implementation before being accepted green.
      **The honest limitation, stated so nobody over-reads it:** it proves the ARGUMENTS are
      accepted, never that the command succeeds. It is a spelling check on the invocation, not a
      smoke test. It does not check positionals — no tool has a required one today, and a tool that
      grows one is a hole in it.
- [x] **`[v]` `tools/measure_sector_cap.py` can read the STORE — built 2026-08-25.** Its docstring
      already said classifications are read *"from a saved file, or from the store
      `tools/refresh_classifications.py` fills"*, and there was no store route:
      `--classifications` took JSON only, and `refresh_classifications.py` writes no JSON at all.
      **The sentence named a route with no code under it.** Built rather than deleted, because the
      store is what the daily run enforces against and the dated JSON snapshot is a 68-name trade
      slice. `--classifications` now dispatches on suffix, and the `.duckdb` route reads through
      `ClassificationStore.as_of` + `look_through` — the same reader the pipeline uses, so a
      coverage number measured there is the coverage the cap actually has.
- [x] **`[v]` Gate 22 BUILT 2026-08-25** — `registry/directory_pull_policy.yml` and
      `tools/verify_directory_policy.py`. See §2 for the whole `DR-008` audit: five clauses built
      this session, two still open (the process lock, and eligibility checking *"after the latest
      session has completed"* rather than merely that today is a session).
- [x] **`[v]` GATE 14'S WORD-NUMBER HOLE — BUILT, MEASURED, AND REVERTED 2026-08-25. The hole is
      real and pattern-matching is the wrong fix.** Recorded because the next session will have the
      same idea.
      **What was built:** every check's `(\d+)` generalised to digits-or-words, one to ninety-nine,
      with an `as_int` that reads `36`, `thirty-six` and `Thirty Six` alike. It worked.
      **What it found on the real tree: 19 failures and ZERO real drift.** Every one was a subset
      statement or history — `RULE_SPEC.md` *"Three tests, one pair of verdicts"* (three specific
      tests), `PR-005` *"compare five gates through six exit rules"* (the study's GATING ARMS, not
      merge gates), `CI_POLICY.md` *"the two gates whose subject is change over time"*, `DR-006`
      *"passed sixteen gates"* (historical), and `HANDOFF.md` §2's own quotation of the defect.
      **The reason is structural, and it is why the digit form works as well as it does.** English
      prose spells small numbers out, and a small number in prose is almost always a count of
      SPECIFIC THINGS rather than a census. `(\d+)` is an accidental but effective discriminator
      between the two, and removing it removes the discrimination, not the blind spot.
      **What actually closed the hole was generation, not matching.** The instance that motivated
      this — *"Twenty-two gates"*, wrong for as long as it took someone to notice by eye — sat in
      `HANDOFF.md` §2, and §2 is generated now (gate 24). A number that is recomputed cannot be
      stale in any spelling.
      **What is left of the hole, stated so it is not re-opened by accident:** a census spelled in
      words, in a document that is not §2. The ownership half of gate 14 would catch it *if* the
      pattern matched — and the measurement above is that making the pattern match costs 19 false
      positives to buy that. `CI_POLICY.md` §3 records what a noisy gate is worth.
- [ ] **`[v]` The `specified` components awaiting activation** — pivots (M12-T0201, M12-T0202),
      moving average (M25-T0382), breadth (M31-T0459) and relative strength (M31-T0464). Every one
      carries an `implements` that gate 11 resolves against real code. Derive the roster, never from
      here:
      ```bash
      PYTHONPATH=$PWD/src python tools/verify_components.py
      ```
      **This line was `[c]` and wrong at both edges for twelve days, and the corrections were in
      this same file the whole time.** It named `regime` (M30-T0450) and `trend` (M33-T0485), both
      **demoted** to `registered` on 2026-08-18 because neither module carries the specification
      record the ladder requires — §6 says so in a closed item. And it never gained
      `M31-T0464`, which became `specified` on 2026-08-24 — §5 says *that* in a closed item.
      **Two sections of one document, opposite answers, twice in one file**, which is the same shape
      as the mutant-survivor entry corrected on 2026-08-29.
      **It is caught now.** Gate 14 reads `TODO.md` for the parameter statuses and the component
      activation states — and only those; the 2026-08-24 probe that rejected the whole pattern set
      here measured its noise entirely in the tests/gates family, and never separated the patterns
      that produced it. Measured before adding: 2 hits over this file, 1 real drift and 1 quotation
      of the earlier probe's own evidence, which is in the gate's `ALLOWED` rather than paraphrased.
      **Activation itself stays demand-driven** (`HANDOFF.md` §4): the test before activating one is
      naming the strategy card that consumes it. No card, and `registered` costs nothing.
- [x] **`[v]` ~~`tools/` under mypy~~ — THE CHECKING MACHINERY IS UNDER GATE 5 AS OF 2026-08-30,
      and the sweep everyone was dreading was one missing file.**
      Every `verify_*`, every `build_*`, `check_gates.py` and `track_a_streak.py` type-check clean
      and gate 5 covers them. The research runners (`run_pr*`, `measure_*`, `probe_*`) stay out.
      **`src/swingdesk/py.typed` did not exist.** Without that PEP 561 marker mypy treats this
      project's own fully-typed package as UNTYPED the moment a tool imports it, so every script in
      `tools/` got `Any` for every `swingdesk` symbol. **142 of the 247 errors were that one fact
      repeated** — and the count is the least of it: the checker was blind at the one boundary
      where a tool meets the system, which is exactly where a wrong argument gets written. Adding
      the marker took the total to 113 and raised `arg-type` from 7 to **16**: nine real argument
      errors that had been invisible the whole time. What was left in the machinery after that was
      34 annotations, not 242.
      **It caught a fail-open on its first run, in a verification tool.**
      `verify_reproducible.py` declared `hashes: list[str]` and appended `manifest.output_hash`,
      which is `str | None`. Two passes that produced NOTHING compare `None == None` and print
      *"byte-identical output"* as evidence for `a.reproducible`. **Latent rather than live** —
      `run()` has exactly one exit today and always sets the hash — and now guarded, because the
      comparison was unprotected against a state its own type declares. It could not have been
      found by reading: the line is correct-looking.
      **The old deferral reason is also gone and worth recording as such.** It was *"`tools/` is
      where a parallel effort is most likely to be editing and 43 files of annotation churn is the
      worst possible merge surface"*. True when written; today nothing is unmerged. Derive the
      remaining count, never from here: `PYTHONPATH=$PWD/src python -m mypy tools/`.
- [ ] **`[v]` THE NINE NEWLY-VISIBLE ARGUMENT ERRORS: two were real, seven were inference, four
      are UNCHECKED — and the split is stated rather than rounded off.** Adding `py.typed` raised
      `arg-type` in `tools/` from 7 to 16. What each turned out to be, checked one at a time:
      • **Real, and fixed** — `verify_reproducible.py` comparing two `str | None` hashes declared
      `list[str]`; and `run_pr005_replay.py` building the replay window with a generator, so a
      recorded window of one or three dates would have replayed over a window nobody chose. That
      second one is small and it is in the tool whose whole job is to say whether a PUBLISHED result
      still reproduces, which makes a silently wrong window the one answer it must never give. It
      refuses with a reason now.
      • **Inference, not defects** — `run_pr002` (`min(key=...)` and two reuse sites), `run_pr005`
      (`Decimal` from an `object`), `run_pr013` (a cascade from one heterogeneous dict),
      `measure_correlation_cap` (a dict literal mixing `int`, `float` and `list`), `measure_pivots`
      (a local `_Series` test-double passed to the real component). Every one is mypy narrowing a
      variable from a first assignment, in a runner whose result completed. Recorded so the next
      session does not re-chase them.
      • ~~**NOT checked, and this line is the whole of what is left:** `measure_benchmark.py`
      (two sites), `measure_sector_relative.py` (two), `run_pr008.py` (two), `run_pr012.py` (two).~~
      **CHECKED 2026-08-30, all eight, and all eight are clean.** Seven are the same
      heterogeneous-dict shape as the cleared ones — a `dict[str, object]` whose values are then
      read as numbers, with the `None` cases already guarded at the call site.
      **The eighth was worth opening and is the reason this line existed.** `run_pr012.py:382`
      passes `dict[str, list[bool]]` where `run_book` declares `list[bool | None]`, and a signal
      series with no `None` in it would be the `UNKNOWN`-becomes-`FALSE` collapse `RULE_SPEC.md` §4
      forbids — the exact defect the engine's own docstring is written against. **It is not that.**
      The argument is the per-bar `gates` FILTER, not the trigger; the trigger is
      `AlwaysEligible(LOOKBACK)`, passed separately, and an all-`True` filter is "no filter". The
      three-state type belongs to the gate for its own reason (`engine.py`: *"a None gate does not
      trade: it is not a rejection"*), and mypy's complaint is list invariance. **Recorded because
      the check was worth making and the answer was no** — a prior that eight sites look alike is
      not the same claim as having opened them, which is why this line was written as open rather
      than closed.
      ```bash
      PYTHONPATH=$PWD/src python -m mypy tools/
      ```
- [ ] **`[c]` The rest of that line, untouched:** structured logging · backup/restore ·
      chaos scenarios · breadth card (parked) · `sizing.py` cost-model swap.

### Correctness findings from the 2026-08-15 review — all `[v]`

- [x] **`[v]` Live path silently defaulted the exit policy — fixed 2026-08-16.** `_exit_policy()`
      reads `exit.atr_stop_multiple` and `exit.max_holding_period` and REFUSES when unset. **They
      were unset when this was written and were ratified 2026-08-17 (`DR-012`)**, so the refusal
      path is now the exceptional one rather than the only one.
      Candidates Skip with the parameter named; open positions PAUSE rather than being managed on an
      invented stop. Old behaviour `pipeline.py`:289 and :369 both use
      `exits or ExitPolicy(Decimal("2.0"), 20)` — a hard-coded constant with no registry read and no
      provenance, while `exit.atr_stop_multiple` and `exit.max_holding_period` were both `unset`.
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
      **Measured 2026-08-25 and it changes the urgency, not the diagnosis: NEITHER implementation
      has a production caller.** `sizing.r_multiple` is called from `trade_management/__init__`'s
      re-export and from one test; `Position.r_at` from two tests. Nothing in `src/` outside their
      own modules calls either — asked of the code graph and then **verified against the files**,
      because the graph reports `freshness.assess` at zero fan-in too and that one is called twice
      in `pipeline.py` under an alias (`AGENTS.md` §9: a null result is evidence only after a
      positive control).
      **Why they are dead is not a defect**: the live path has never opened a position, so no code
      has ever needed R. The consequence for this item is that a change to either **cannot move
      decision output today**, which is the thing that would otherwise make it expensive on a frozen
      file.
      **And the backtest's third R is NOT a third implementation of this quantity** — checked
      before assuming it was. `validation/backtest/engine.py` divides by `entry_price - stop` where
      `entry_price` already carries slippage and commission rides on the `Trade`; the registry's
      `costs.commission_model` note names that split explicitly (*"this is what a backtest
      charges"*). Two cost MODELS by design, not one quantity written twice.
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

      ~~**(a) is blocked on `DR-003` gap 1, not on an engineering choice.**~~ **The blocker moved
      2026-08-25 and the item did not, so it is restated rather than struck.** The old reasoning:
      resolving identity means resolving against a directory, `DR-003` recorded that Canada had no
      free symbol directory in hand, so a `.TO` instrument had nothing to resolve against and
      fail-closed would refuse every Canadian candidate. Owner's call 2026-08-16 was **source a TSX
      directory first**, and identity resolution waited on it.
      **A source exists.** `DR-003` *"Gap 1 is closed"* — TMX serves its own directory free, no
      account, no key (`python tools/probe_canada.py --full`, re-verified 2026-08-25). The owner's
      call is satisfied on its own terms; what is left is wiring, and `DR-008` governs how any
      directory is pulled, attributed and audited, so a second source is that record's business
      rather than a free-hand fetch.
      **And the refusal it feared binds on almost nothing today — measured, not assumed.**
      `HANDOFF.md` §2's `Canada` row owns the numbers: the directory holds **zero** `.TO` symbols
      and the bar store holds **one** `.TO` instrument, 252 bars from a single fetch on 2026-08-02
      that has never been refreshed. So *"fail-closed would refuse every Canadian candidate"*
      refuses an empty set drawn from the directory. **The one instrument is itself an instance of
      this defect** rather than a counterexample: it holds bars while absent from the directory, so
      nothing could resolve it either way.
      Blocks any historical edge claim; does not block Track-A-only PAPER. **Changes the daily-run
      path — behind the freeze.**
- [ ] **Half the journalled runs carry `code_dirty = true`.** `a.reproducible` requires a
      byte-identical re-run from a stored manifest; a manifest pointing at a dirty tree cannot be
      replayed from its SHA. **`HANDOFF.md` §2 owns the count** — this line read ~~11 of 13~~ until
      2026-08-25, which was true when written and is a second copy of a figure §2 generates
      (`AGENTS.md` §10.5). The dirty era ended on 2026-08-17 and its records are immutable, so the
      share falls only by adding clean runs.
- [ ] **Almost every recorded `Skip` is `RISK / risk.per_trade_pct`** — unset-parameter refusals,
      i.e. a system fault rather than market judgment. That parameter was set 2026-08-11. Any
      statistic over the decision history must segment these out first.
      ~~4,486 of 4,510~~ **— corrected 2026-08-25, and the numerator is the half that cannot move.**
      No such skip has been recorded since the parameter was set, so the count of them is frozen
      while the denominator grows with every evening; quoting the pair makes the ratio look worse
      than it is and it was already stale. Derive both from `data/journal.duckdb`, which
      `HANDOFF.md` §3 names as their owner:
      ```sql
      SELECT reason_code, parameter_id, COUNT(*) FROM decisions WHERE decision = 'Skip'
      GROUP BY 1, 2 ORDER BY 3 DESC;
      ```
- [x] **`[v]` EVERY DECISION THE LIVE PATH CAN EMIT IS NOW ACCOUNTED FOR — measured 2026-08-25.**
      `REQ-VALIDATION-001` asks after every gate, veto and filter; gate 34 covers five of them by
      mutation. This is the complementary question and it is answerable exactly: **which of
      `pipeline.py`'s `DecisionRecord` construction sites does the suite ever execute?**
      **17 sites. 15 executed, 2 never.** Both are defensive branches and **both are now explained
      in the file** rather than one of them being explained and the other looking like a gap:
      - the FX branch already said *"unreachable while `size_long` refuses the same instrument for
        the same reason, and handled anyway"*;
      - the **sector-book refusal did not**, and it is unreachable for a provable reason:
        `portfolio.book` and `portfolio.sector_book` refuse on identical preconditions — a
        non-positive 1R, or a held position whose currency has no rate — over the same positions
        with the same `rate_for` and `allowed_risk`, and `book` is priced first, so a candidate
        that reaches the sector split has already cleared them. Its `book` twin **is** tested
        (`test_a_cad_position_in_the_book_refuses_every_candidate`).
      **Method, so it can be repeated without adding a dependency:** `sys.settrace` scoped to
      `pipeline.py` alone while the suite runs, ~3 minutes. `coverage` is not a declared dependency
      and adding one to answer a question once would be the wrong trade (gates 17, 18).
      **Widened the same day to every `Refusal` in the live modules, and this half found real
      gaps.** 27 refusal sites across `pipeline`, `universe`, `cli`, `portfolio`, `sizing`,
      `freshness` and `store`: **18 executed, 9 never**. All nine now are — 27 of 27.
      **Five were in `sizing.py`**, which is the most safety-critical file in the tree and frozen:
      an unsupported currency, an unset cost parameter, a non-positive risk-per-share after costs, an
      unset position-value cap, and a cap too small to buy one share. Each was reachable and each
      now has a test asserting the code and the wording that reaches the owner. **No source
      changed** — these were missing tests, not missing guards.
      **Four were in `cli.py`**, and all four block the recording of a fill that has ALREADY
      happened at the broker, which is what makes their wording matter. Three needed no monkeypatch;
      the fourth does, and **that is a design observation worth keeping**: `_expiry` loads the
      registry itself while `_capacity_for` takes one, so only the second has an injection point.
      **The measurement is a committed tool now, so it is a command rather than a memory** —
      `TEST_STRATEGY.md` §5 documents it and says why it is not a merge gate:
      ```bash
      PYTHONPATH=$PWD/src python tools/measure_refusal_coverage.py
      ```
      It reads a comment saying a branch is unreachable and counts it separately, which is what
      keeps it from being permanently red over branches that are defensive by design — and it makes
      those two comments load-bearing rather than decorative.
      **What it does NOT establish:** that each site is exercised for the right REASON. A line
      executed is not a branch asserted, and the two are the same distance apart as gate 8 and gate
      34.
- [ ] **Tests cover the safe branch of the risky code, three times over.** See §8.

## 6b. The operational chain — what a full cycle needs

- [ ] **`[v]` ALPACA PAPER TRADING — owner instruction 2026-08-31. Wire it as the broker so
      strategies, guesses and the whole chain can be tested against a real venue.**
      <https://docs.alpaca.markets/us/docs/paper-trading>. Researched 2026-08-31:
      endpoint `https://paper-api.alpaca.markets` (env `APCA_API_BASE_URL`); paper keys are
      DISTINCT from live keys; accounts are free and open to anyone globally; default balance
      **$100k**, settable at creation and not changeable afterwards without a reset; **IEX market
      data included at no cost** and the Market Data API is identical between paper and live; the
      API specification is the same as live, so migration is a base-URL change.
      **IT FITS `DR-014` EXACTLY.** That record rules no owner capital in the observable state of
      the project — paper only. An Alpaca paper account is that, with a real venue's fills, halts,
      partial fills and rejects instead of a fixture.
      **THE D1 QUESTION WAS PUT TO THE OWNER AND ANSWERED, 2026-08-31** — *"treat выставление
      заявок as not a crossing rules, because its not a real money. Order only means the real one."*
      `DR-026` records it, and records that the ruling answers `D1` (whose stated reason is
      *"removes the largest irreversible-risk surface"*) and **leaves three constraints standing
      whose reason is not money at all**: `CHARTER.md` §3's automated-trading non-goal, and A-001
      §1–§2. Read §5 of `DR-026` before building any write path.
      **(a) READ-ONLY — DONE 2026-08-31.** `swingdesk broker` reads the paper account and reconciles
      it against `PositionStore`, reporting in the course's own `TECH` code (Appendix N,
      *"Broker/platform/journal mismatch"*, action *"pause new entries"*). `ADR-0005` places the
      package; `registry/broker_policy.yml` + **gate 39** hold the limits and the one allowed host;
      `tests/test_broker.py` runs it all against recorded fixtures.
      **`APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` are not set, so it has NEVER been run against
      the live endpoint** — the field names come from Alpaca's published reference, not from an
      observed response. That is the next thing to do and it is the owner's: set the two variables
      in the environment (never in a file here — this repository is public) and run
      `swingdesk broker`.
      **What (a) deliberately does NOT do, and it is not a gap that more code closes.** A broker's
      answer cannot construct a `Position`: the venue knows symbol, quantity and average entry and
      does **not** know the STOP, which is what `RISK_SPEC.md` §2 denominates every R in. Nor can a
      fill be joined to an approved action — the venue carries an order id, and `Fill` settles a
      `position_id` and a `sequence`. So it reconciles and reports; `open-position` and
      `record-fill` still take the owner's judgment. Both close only with a `client_order_id` this
      system sets and a bracket order carrying the stop — which is to say, only with (b).
      **(b) ORDER PLACEMENT — open, and `DR-026` §4 lists the six things it must carry.** The
      unresolved question is §5 and it is the owner's: **may the system submit a paper order that no
      human approved order-by-order?** An owner-approved one is already permitted by every
      constraint; an unapproved one needs A-001 amended, which its own text says admits no
      configuration.
      **Constraints already binding on this work:** `SECURITY.md` §2.1 — no secret in the repo, env
      vars or an OS keyring only, and this repository is public (`tools/verify_secrets.py` says so).
      `CI_POLICY` §4 — CI must never touch the network, so every Alpaca test runs against a recorded
      fixture. `DR-011` §6 keeps the notice surface send-only and this must not quietly become an
      inbound control channel.

- [x] **`[v]` GATE 6 HAD NEVER RUN — found and fixed 2026-08-31.** The runner invoked import-linter
      as `python -m importlinter.cli lint-imports`. `importlinter/cli.py` defines a Click group and
      carries **no `if __name__ == "__main__"` block**, and the package has no `__main__.py` — so
      `-m` imported the module, fell off the end and **exited 0 printing nothing**. Every suite run
      since the gate was wired reported `6 import contracts PASS` over a check that never executed.
      **Nothing could have found this by reading**, and that is the point: the failure is
      indistinguishable from success. It surfaced only because `AGENTS.md` §10.8 was actually
      followed — a forbidden import was planted into `derived_observations` to prove the new
      `broker` contract could fail, and it stayed green.
      **The tree was clean when the real runner was finally used** — 4 contracts kept, 0 broken —
      so no violation shipped. That is luck rather than enforcement, and it is exactly what
      `CI_POLICY` §3 rule 2 warns a confidence-manufacturing gate buys.
      Fixed in `check_gates._lint_imports`, which resolves the console script beside the
      interpreter. **Verified by planting the same import again and watching it exit 1.**

- [ ] **`[ ]` WIRE `TECH` INTO THE DAILY RUN, or decide not to.** `swingdesk broker` reports a
      broker/journal mismatch and Appendix N's prescribed action for that code is *"pause new
      entries"* — but nothing pauses anything today, because the reconciliation is a command the
      owner types and the scheduled pass never calls it.
      **The obstacle is real and is a decision, not a wiring task:** making the 18:30 pass reconcile
      means putting the broker network call inside the run that `a.run_completes` counts, so a venue
      outage becomes a failed run. `DR-015`'s staleness machinery is the precedent for how to answer
      that (refuse to DECIDE, do not fail the RUN), and `DR-019` is the precedent for asking whether
      a pass should do a thing at all before teaching it to.
      Blocked behind the owner setting the keys — there is nothing to reconcile against until the
      adapter has been run once for real.

**COMPLETE as of 2026-08-18.** Every buildable item below is done, and the one remaining open entry
(3c, off-desk reach) is a deliberate non-goal rather than a gap — `DR-011` decided it and preserves
the whole analysis so nobody redoes it. The chain ran end to end on 2026-08-17, which is the
condition the 2026-08-16 council set before research resumes; `DR-014` then reordered what "resumes"
means. **It has not run with owner capital and will not** (`DR-014`).


Traced end to end 2026-08-16, not just the pipeline internals: `daily_run.cmd` → `cli.py scan` →
`report.py`. **BUILT and gated** — every gate and every test green, DONE 2026-08-12: candidate
screening, sizing, exit-policy
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
