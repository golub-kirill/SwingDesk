# TODO — the single open-work list

**Status:** working document · **Owner:** shared · **Last reconciled:** 2026-09-04

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

- [ ] **`[v]` `data.staleness_action_threshold` is still `unset` and still read by nothing.**
      `DR-015` set `data.freshness_window` and did not touch this one. They are not duplicates:
      the window is **per instrument** — this candidate is too stale to size — while Appendix T's
      *"при stale data или mismatch новые сделки блокируются"* is a **system-wide** block on new
      entries. Today a run where every candidate is stale refuses each one individually and says
      nothing about the run as a whole. Needs a ruling, or an explicit decision that the
      per-instrument gate discharges it and the parameter should be retired (`AGENTS.md` §11).
      **RE-TESTED 2026-09-04 AND STILL EXACTLY TRUE**, and the test is written down here rather
      than the verdict, which is what §6's blocker convention asks of a sentence like this one:
      ```bash
      grep -A6 'id: data.staleness_action_threshold' registry/parameters.yml
      grep -rn staleness_action_threshold src/ tools/
      ```
      The registry entry reads `value: null`, `status: unset`, `read_by: none`; the identifier
      appears **nowhere** in `src/` or `tools/`, only in `DATA_QUALITY_SPEC.md`'s parameter list.
      So the ruling this item asks for is still the one thing that would move it.

- [ ] **`[v]` ADTV admission reads provisional volume — ~~DR-017 DRAFTED 2026-08-18, needs a
      ruling~~. RATIFIED BY THE OWNER 2026-08-30; WHAT IS OPEN HERE IS A DIFFERENT QUESTION.**
      Re-tested 2026-09-05: `DR-017` reads `accepted`, `universe.adtv_lag_sessions` = **3**
      with provenance `owner`, and `reference_data/universe.py` windows on it in `admits`.
      **The heading contradicted its own body for six days** — the body's *"Still open and NOT
      decided by DR-017: is backfilled volume executable?"* was always the live question. This
      file already carries the same shape under `a.reproducible`: *"a reader who takes a heading
      as the finding got the opposite of what the paragraph says."*
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
      ~~**Proposed:**~~ **SET, `owner`, 2026-08-30:** `universe.adtv_lag_sessions = 3` — three, not two, because two is the oldest age
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
- [ ] **`[c]` The remaining surface, and it is now small enough to name.** The document pass above
      cleared the refuted-but-standing class. What is left is the ORIGINAL question — a claim about
      the world that nobody tested — and the honest position is that it has been sampled, not
      swept. Re-derive with the command above; a claim that survives with a test named beside it is
      worth more than one that was merely never challenged.
- [ ] **`[c]` Study scope sections — still open, and deliberately last.** `PR-002`'s report is the
      known instance and its Canada citation is already recorded above. Amending a published report
      is governed by `AUDIT_AND_IMMUTABILITY.md`, so this is a different kind of task from editing a
      live document and should not be done casually. **Re-tested 2026-09-05: the blocker is real**
      — `docs/04-journal/AUDIT_AND_IMMUTABILITY.md` exists and is what governs the amendment.

### A STALE COUNT IN A DOCSTRING, AND WHY GATE 14 STILL SHOULD NOT SCAN CODE — 2026-08-25

### THE AUDIT'S OWN BASE RATE — measured 2026-08-25, and the owner's hypothesis holds

**The ask was whether this project had been stopping itself on untested "cannot"s.** Eight
impossibility claims have now actually been TESTED rather than read. **Five were false.**

| Claim | Outcome |
|---|---|
| *"No free source serves delisted history"* | ~~**half false** — EDGAR gives the fact and date, free and official; prices stay closed~~ **FULLY FALSE as of 2026-09-05.** Alpaca serves complete daily paths for delisted names from 2016 on `feed=sip`, and the owner ruled the account free tier. **The second half took twelve more days and one owner question** — *"have you checked EDGAR or Alpaca?"* — because nobody had asked the second source |
| *"Canada cannot be enumerated"* | **false** — TMX serves its directory free, no account |
| *"None of §3a's six routes is mechanically detectable"* | **false for three of six**, and a fourth was never open |
| *"`www.sec.gov` 403s, so a lookup by ticker needs an owner-supplied contact"* | **false** — it needed an `Accept` header |
| *"A fourth spread estimator is the same family"* | **survives**, and now carries the mechanism rather than the prediction |
| *"There is no legal source of probability in this system"* | **survives**, and is now derivable from two gates rather than asserted |
| *"Batching is not the lever"* | **the claim survives; the PARKING did not** — `NFR.md` §3 had already ruled on concurrency in both directions |
| *"No free source serves historical intraday spreads point-in-time"* (`DR-004`) | **FALSE, 2026-09-06** — the venue this project already holds an account with serves consolidated **SIP** NBBO back to 2016 on the free tier; only the last fifteen minutes are withheld, which is the one window a backtest never reads. `tools/probe_quotes.py` re-derives it. **The same vendor had been tested twelve days earlier — for BARS.** Nobody asked it for quotes |

**Four of the five refutations came from testing at a FINER GRANULARITY than the original test**,
which is `AGENTS.md` §17 and is the transferable lesson: the header rather than the host, the six
routes rather than "none of it", *"no directory in hand"* rather than *"cannot be enumerated"*,
and now **the FEED rather than the vendor** — the free tier's real-time feed is one venue holding a
few percent of volume, and at the same instant in 2019 `AAPL` reads 0.49bp on the consolidated tape
against 621.82bp on that one book. The
original measurements were not sloppy — each was correct about what it actually measured, and each
conclusion was drawn one level coarser than the evidence supported.

**And the cost was never symmetric.** Every refuted claim had closed real work: a study dropped half
its scope, a measurement waited fifteen days on an owner action nobody needed, a guard was described
as hopeless when half of it was a finite set. `AGENTS.md` §15's asymmetry is not a theory here; it
is the measured outcome of eight tests, and the eighth is the most expensive yet: it had closed
the route to the one constant every negative headline in this project is computed at.

**A SECOND POPULATION, AND IT IS A DIFFERENT DISEASE — swept 2026-09-05.** The seven above are
IMPOSSIBILITY claims: sentences asserting something about the world. The sweep below tested
**EXPIRED BLOCKERS**: sentences that were TRUE when written and stopped being true while nobody
looked. They are counted apart on purpose — folding them in would inflate the base rate with a
second illness, which is the §17 granularity error this table is itself about.

| Blocker | Outcome |
|---|---|
| `DR-017` *"needs a ruling"* | **expired** — ratified 2026-08-30, and the heading contradicted its own body for six days |
| *"journalled trades, of which there are none"* | **expired** — `POS-AIS-2026-09-03` closed 2026-09-04, the first completed trade |
| *"the entitlement question is open"* | **answered** by the owner, 2026-09-05 |
| *"a status claim in prose is not exact"* | **false for one subclass** — gate 28 runs on 315 files with 0 false positives |
| earnings buffer, pass timing, `PR-003`, `PR-004`, `DR-008`, study scope, `code_dirty` | **all held**, each measured against the store or the machine |

**The two that expired had been closed for six and twelve days respectively**, and neither was
hard to check — one `grep` of a decision record's status line, one `SELECT` against
`positions.duckdb`. **An expired blocker is cheaper to detect than an impossibility and rots the
same way**, because nothing re-reads a sentence that was right when it was written.

**And one held claim was nearly mis-scored, which is the §17 lesson landing on the auditor.**
*"Every scheduled pass since 2026-08-31 is clean"* looked false against the `runs` table until the
population was separated: the dirty rows are HAND runs. Reading the table without the filter would
have produced a confident wrong refutation — the exact error the seven above were made of, pointed
the other way.

**Widen it past documents when the document pass is done.** The same shape lives in code comments
and in study scope sections - `PR-002`'s report alone carries several - and a study that narrowed
its own scope on an untested "cannot" is the most expensive instance of this there could be.

**Already overturned, 2026-08-24, and it is why this exists.** The evening run refused a block of
candidates reading *"a refetch did not bring it current"*. Re-asking the same vendor the same
evening returned every one of those sessions, clean. The owner asked; nobody had checked.

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
      ~~**What still turns on this is `PR-009`.** It was told to register against this replay's
      vintage rather than `PR-005`'s published aggregate, and on the current store those agree
      while the CSV on disk does not.~~ **THEY NO LONGER AGREE — measured 2026-09-05 by running
      the command this entry opens with.** The instruction stands: register against a replay
      anyone can reproduce today, and cite the dated vintage above for why the CSV differs.
      What changed is that "today" is a THIRD vintage rather than `PR-005`'s.

      **RE-MEASURED 2026-09-05, AND THIS ENTRY'S STABILITY CLAIM IS FALSE.** It says *"the
      in-window `knowledge_time` maximum is 2026-08-17 18:30, so nothing since has touched this
      sample"*. True on 2026-08-24; false from **2026-08-27**, three days later and three days
      BEFORE the ruling that rests on it. The in-window maximum is now `2026-08-27 18:30:05`.
      ```bash
      PYTHONPATH=$PWD/src python tools/run_pr005_replay.py --data C:/PycharmProjects/SwingDesk/data
      ```
      **What it says today: `MISMATCH: 0 cell(s) on trade count, 10 on mean R`.** Every trade
      count still reproduces. The ten that do not are **exactly the ten holdout cells** and
      every primary cell is exact — which is the diagnosis rather than a coincidence, because
      holdout begins 2023-07-28 and every changed bar sits inside it.
      **One instrument moved, and it is a REVISION, not a backfill.** `LEG`, 220 bars over
      sessions 2025-08-28 → 2026-07-17, all written by the scheduled pass at 2026-08-27
      18:30:05. Those sessions were already stored: 222 distinct session dates hold 442 rows,
      222 of them written before 2026-08-18. Nothing else among the 68 admitted instruments
      changed inside the window — the rest gained only sessions after 2026-07-31, which is
      ordinary accretion outside the study.
      **And the fields that moved are the ones the revision guard does not watch.** Version 1
      against version 2, over those 220 sessions:

      | field | sessions changed, of 220 |
      |---|---|
      | `close` | **0** |
      | `open` | 20 |
      | `high` | 70 |
      | `low` | 81 |
      | `volume` | 219 |

      The moves are half a cent — `9.820000` → `9.815000`. **`data.revision_epsilon` is scoped
      to `close` alone** by the owner's ruling on `DR-016` §8.4, for a measured reason that
      still holds: the wide form raised roughly 94 faults an evening and over close alone it
      fired zero times. **The guard was silent because nothing it watches changed, and it was
      right to be.**
      **The chain from there is checked, not narrated** (`AGENTS.md` §10.4): `high` and `low`
      are ATR's inputs, ATR is the R denominator, and a cell's mean is taken over R. So gates
      keyed on the close and the pivots produced **identical trades**, while the denominator
      moved in the sixth decimal. That is exactly the observed shape — 0 cells differ on count,
      10 on mean R, and the 10 are the period the revised bars occupy.
      **MEASURED ACROSS THE WHOLE RESEARCH RECORD, 2026-09-05, because the question below was
      put abstractly and got the honest answer *"I have no answer"*.** A principle is hard to
      rule on; a frequency is not. `tools/measure_study_drift.py` asks, per reported study,
      what the store did to its sample after it ran:
      ```bash
      PYTHONPATH=$PWD/src python tools/measure_study_drift.py --data C:/PycharmProjects/SwingDesk/data
      ```
      **Two of the three measurable studies cannot be asked at all, and saying so is the
      result rather than a gap.** `PR-001` and `PR-005` read at 2026-08-03, before ANY of
      their 68 names had a bar in this store — which is what `PR-005-trades-provenance.json`'s
      `why_not` already recorded and what `run_pr005_replay.py` reads `now` for. Their drift is
      unmeasurable by construction, so the tool prints `UNAVAILABLE` instead of a number.
      **`PR-013` can be asked, and the answer is not the half-cent story above.** Since its
      recorded snapshot: **1,220 revised rows inside its own window, and zero new sessions** —
      so every one of them is a rewrite of a session the study had read. Three names carry it:

      | name | revised sessions | what happened to the close |
      |---|---|---|
      | `APH` | 727 | **×0.5** — a 2:1 split re-adjusted through history |
      | `DFNS` | 220 | **×125** — a reverse split, same thing at the other end |
      | `LEG` | 220 | unchanged — the tick corrections that moved `PR-005` |

      **So there are two populations and only one of them is subtle.** A corporate-action
      re-adjustment moves prices by a FACTOR and is the vendor being correct; a tick correction
      moves them by half a cent and is invisible to a close-scoped guard. Both land inside a
      closed study window, and neither is a fault in the store — it keeps every version.
      **AND THE RUNNERS DO NOT READ THE SNAPSHOT THEY RECORD.** `run_pr012.py:254` and
      `run_pr013.py:151` both take `as_of = store.latest_knowledge_time()`, then write
      `"snapshot": as_of` into the result. The value that would make the study reproducible is
      recorded and never read back. A re-run today reads `APH` at half the price the study saw
      and `DFNS` at a hundred and twenty-five times it.
      **That matters beyond tidiness because a re-run is used as EVIDENCE.** `HANDOFF.md` and
      §5 of this file both cite `run_pr012.py` reproducing all 12 of `PR-012`'s cells as proof
      that a code change moved nothing. That argument reads the store at `now`, so a split
      landing in the window breaks it for a reason that has nothing to do with the code.
      **The decision is now a small one, and it is still the owner's** (`AGENTS.md` §14 —
      nothing is built here):
      - **(a) read the recorded snapshot back.** `store.as_of` already takes a knowledge_time;
        the runners pass `latest` where they could pass `record["snapshot"]`. Studies whose
        vintage is IN the store become exactly reproducible, forever, and the byte-identity
        argument above becomes sound. It does nothing for `PR-001` and `PR-005`, whose bytes
        were never here.
      - **(b) leave it and date every re-run**, which is the 2026-08-30 ruling generalised.
        Cheaper today, and it means no reproduction claim can ever be more than *at that
        vintage*.
      ~~**This entry recommends (a) and does not take it.**~~ **RULED (a) AND BUILT 2026-09-05,
      owner instruction.** `run_pr012.py` and `run_pr013.py` take `--as-of` and `--reproduce`;
      the shared resolver is `run_pr012.resolve_vintage`, which `run_pr013` already imports
      from. Four things it does, and the last two are what make it honest:
      - **`--reproduce` reads the study's own record back** — its `snapshot` for the bars and
        the directory, its `run_at` for the classifications. **Two stores, two clocks**
        (`AGENTS.md` §12): pinning the bars and reading classifications at `now` would not be
        a reproduction, and the first draft of this did exactly that.
      - **the default is unchanged.** A fresh run still reads `latest_knowledge_time()`;
        pinning a NEW study to an old vintage is the opposite mistake.
      - **`--reproduce --write` is REFUSED.** A reproduction that publishes is a republication
        under an old vintage; `run_pr005_replay.py` refuses the same thing for the same reason.
      - **a record missing either field refuses rather than falling back.** A study published
        before those fields existed cannot be reproduced, permanently — reading today's store
        and printing cells would be the `unavailable`-as-`pass` inversion this file collects.
      `--as-of` alone says in its own printed line that it pins the bars and **not** the
      classifications, because claiming both would be the §10.8 overstatement. Every run prints
      which vintage it used and where that came from.
      8 tests in `tests/test_study_vintage.py`; mutating `--reproduce` to ignore the record it
      had just read killed exactly the two that assert it, and nothing else.
      ~~**Nothing was re-run and no published result was touched.**~~ **RUN 2026-09-05, and it
      reproduced two arms of three.** No published result was touched — `--reproduce` refuses
      `--write`. The command, and it is the whole evidence:
      ```bash
      PYTHONPATH=$PWD/src python tools/run_pr012.py --data <store> --reproduce --verify-sample 0
      ```
      ```
      vintage: bars at 2026-08-24T07:15:39, classifications at 2026-08-24T15:52:36
               (reproducing PR-012.json)
      snapshot 2026-08-24T07:15:39  ·  admitted 1140
      ```
      **The bar half works exactly.** The admitted universe is 1,140 both times, and all eight
      `MOMENTUM` and `MARKET` cells reproduce — trade counts identical, mean net R identical to
      the printed six decimals. That is the ruling doing its job: before this, a re-run read
      whatever the store held today, `APH` at half the study's price included.
      **The SECTOR arm does not reproduce, and the run names its own cause.** All four sector
      cells differ; two differ on trade COUNT, which no rounding explains:

      | cell | trades | mean net R |
      |---|---|---|
      | `1x/SECTOR` primary | 409 → **408** | 0.344545 → 0.342022 |
      | `1x/SECTOR` holdout | 181 → 181 | 0.160587 → **0.159103** |
      | `3x/SECTOR` primary | 415 → **417** | 0.427230 → 0.405489 |
      | `3x/SECTOR` holdout | 189 → 189 | 0.065513 → **0.061604** |

      `PR-012.json` records `classified: 1013`; the pinned re-run prints **1036**. Same admitted
      universe, same pinned clock, **23 more names carrying a sector**.
      **So pinning both clocks is NOT sufficient, and the residue is the classification store.**
      Measured directly, and it is not what it looks like — nothing was backdated by mistake:
      ```sql
      SELECT knowledge_time, count(DISTINCT instrument_id) FROM classifications GROUP BY 1;
      -- 2026-08-23 15:42:18 -> 1148     2026-08-31 16:59:40 -> 23
      ```
      The store holds exactly **two** `knowledge_time` values. Only the 08-23 one is at or
      before the pinned clock, and at that clock the store answers for **1,148** instruments
      and **1,050** with weights **today** — while the study, reading the same clock, found
      1,013. **A `knowledge_time <= ?` query whose answer grows is a batch LABEL, not a record
      of when a fact became known to us.**
      ~~**What that means, stated as narrowly as the evidence allows.** The bar store is
      point-in-time and the classification store is not: rows reached it under a timestamp at
      or before the study's clock, after the study had read it. `AGENTS.md` §12's *"two stores,
      two clocks"* is about reading one at the other's `knowledge_time`; **this is narrower and
      worse — one store's own clock does not bound its own answer.**~~
      ~~**Consequence:** **no study reading classifications can be reproduced**, `--reproduce`
      or not.~~
      ~~**Not fixed here, and the fix is a decision.** Giving the classification store a true
      insertion time is a schema change.~~

      **WRONG, AND THE AUDIT OVERTURNED IT THE SAME DAY — 2026-09-05.** The store was never the
      cause. `ClassificationStore.record` is `INSERT OR REPLACE` on `(knowledge_time,
      instrument_id)`, so a later pull APPENDS a version and its docstring says exactly that; the
      paragraph above accused it without reading it.
      **What actually moved is the CODE THAT READS THE ROWS.** Two commits touched
      `classification.py` after `PR-012` ran — `61f6d6e` on how the sector guard decides a fund
      holds equity, and `d67b931` on the look-through's shape. Both change the verdict on a stored
      row without touching the row.
      **Reproduced by loading BOTH versions over the same store at the same pinned clock:**
      ```
      instruments classified at the pinned clock        1148
      usable under the code as it was when PR-012 ran   1023
      usable under today's code, SAME rows, SAME clock  1046
      verdicts FLIPPED                                    23
      ```
      **Twenty-three is the whole discrepancy** — the study recorded 1,013 classified and the
      pinned re-run printed 1,036. `AAPU`, `ANGL`, `BNDX`, `BIZD` and nineteen others.
      **So the corrected finding is more general and more useful than the wrong one:**
      **`--reproduce` pins the DATA and not the CODE.** A replay runs today's interpretation over
      the study's sample, and where that interpretation has changed the result moves — and it
      moves in a way that looks exactly like the data moving. `MOMENTUM` and `MARKET` reproduced
      because nothing they read had been reinterpreted; `SECTOR` did not because it had.
      **This is `AGENTS.md` §12's proxy trap once more, and I walked into it while writing about
      it.** The store's answer changing was measured; *the store changed it* was inferred, and the
      inference was the part that mattered. §10.4 asks for the check or the word conjecture — the
      shape of the write was marked conjecture, the CAUSE was not, and the cause is what was wrong.
      **What is genuinely open**, and it is small: nothing records which code version a replay ran
      under, so a reader meeting a moved cell cannot tell a data change from a reinterpretation
      without doing what this audit did. `RunManifest` already carries `code_hash`; a study result
      does not.
      **And one measured aside, because it will surprise the next person who runs it:** the
      pinned run took **about 25 minutes** against the ~13m37s `HANDOFF.md` records for a fresh
      one. ~~Reading `as_of` an older `knowledge_time` over a store that has since grown means
      more versions to filter per query.~~
      **THAT EXPLANATION IS WRONG AND THE MEASUREMENT REFUTES IT — 2026-09-05.** The owner
      asked the question that found it: *how come taking from our own db is slower than
      fetching from the internet?* Timed over 60 random instruments on a copy of the store,
      shuffled between rounds so a warm cache cannot flatter either:

      | read | median | mean | bars returned |
      |---|---|---|---|
      | `as_of` at the store's latest | 24.3 ms | 37.2 ms | 85,335 |
      | `as_of` at the pinned 2026-08-24 vintage | **9.5 ms** | 20.9 ms | 72,384 |
      | at the latest again, as a control | 23.8 ms | 38.6 ms | 85,335 |

      **The old vintage is about two and a half times FASTER, not slower** — it returns fewer
      bars, and that is the whole of it. The control repeats the first row, so this is not a
      cache artefact.
      **And the store is not slower than the network — it is roughly twenty times faster.**
      About **24 ms** to read one instrument locally against about **460 ms** to fetch one over
      HTTP, derived from 7,918 fetches in ~61 minutes. Nothing is inverted.
      **There is no missing index either**, which was the other candidate worth ruling out:
      `bars` carries `PRIMARY KEY(instrument_id, interval, series, event_time, knowledge_time)`,
      so the `WHERE instrument_id = ? AND knowledge_time <= ?` lookup is covered.
      **So what made the pinned run slow is UNEXPLAINED, and this line says so rather than
      guessing twice.** The store went from ~1.9M rows to 7.5M between the two measurements,
      which is the obvious candidate and is **conjecture** (`AGENTS.md` §10.4) until somebody
      isolates it. What is established is only that per-instrument store reads are not the
      cause.
      *(The first version of this paragraph named a mechanism it had not measured, in an entry
      whose subject is claims nobody re-tested. §10.4 asks for the check or the word
      **conjecture**, and it got neither.)*

      **THE ORIGINAL QUESTION, and it is the owner's, because it changes what a guard is FOR.**
      `DR-016` §8.4 scoped the revision guard to the DECISION PATH, where the close is what is
      read and a wider rule cries wolf. **A published study is a different subject with a
      different sensitivity** — it reaches `high` and `low` through ATR — and nothing watches
      that. A result can drift silently on a store this project is right to keep refreshing.
      **Nothing here proposes widening `revision_epsilon`**: that was measured and rejected for
      the path it governs, and re-opening it on this evidence would be carrying a conclusion
      across populations, which is the error this file keeps recording. The candidate is a
      separate check whose subject is a REPLAY rather than a bar.
      **The 2026-08-30 ruling is not disturbed.** *Leave it and date it* was chosen because both
      the log and a replay are correct about their own vintage, and a third vintage strengthens
      that reasoning. What needs saying out loud is that the drift is **ongoing** rather than a
      single event on 2026-08-17.
      **Two places cite the replay's 20-cell reproduction and are deliberately NOT rewritten** —
      `HANDOFF.md`'s optimisation note and §5's version of it. Both claim a CODE CHANGE moved
      nothing, measured on that store at that time, and both are true of their vintage. Each now
      carries one clause pointing here, because a reader who runs the command today meets a
      `MISMATCH` that has nothing to do with what those sentences are about.
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

      **THE BLOCKER IS NOT WHAT THIS ENTRY SAYS IT IS — measured 2026-09-04.** *"Needs a log-out
      before 18:30 one evening"* reads as *somebody must stage an experiment*. The reason no
      ordinary logged-out evening has ever answered it is that **the Task Scheduler operational
      log is DISABLED on this machine**, so every launch decision Windows makes is discarded as
      it is made:
      ```powershell
      (Get-WinEvent -ListLog 'Microsoft-Windows-TaskScheduler/Operational').IsEnabled   # False
      Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-TaskScheduler/Operational'}   # nothing
      ```
      A search for `SwingDesk daily run` across that channel returns **zero** events, which is
      not evidence that the task never missed a trigger — it is evidence that nothing was
      listening. `AGENTS.md` §9's rule about a null needing a positive control, met by the
      channel reporting itself disabled.
      **So the cheap route is to start recording and let an ordinary evening answer it**, rather
      than to stage a log-out. Enabling the channel is a machine setting and therefore the
      owner's, not an agent's:
      ```powershell
      wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true
      ```
      **What is expected, and it is CONJECTURE** (`AGENTS.md` §10.4, §15 rule 3): the task is
      `Interactive only` with `StartWhenAvailable=true`, which reads as *deferred to the next
      logon* rather than *lost* — the opposite of the SLEEP half's measured answer. Nothing has
      tested it, the two are different mechanisms, and predicting one from the other is what
      this file keeps paying for. **The measurement is the point; the prediction closes nothing.**

      **THE CHANNEL IS ON — owner, 2026-09-05.** Confirmed by two tools rather than by being
      told, because *"I enabled it"* and *"it is enabled"* are different claims and the first
      one failed silently once already here (`wevtutil sl` needs an elevated shell and says so
      only if you are reading):
      ```powershell
      wevtutil gl Microsoft-Windows-TaskScheduler/Operational        # enabled: true
      (Get-WinEvent -ListLog 'Microsoft-Windows-TaskScheduler/Operational').IsEnabled   # True
      ```
      **AND IT IS STILL EMPTY, WHICH IS THE HALF WORTH WRITING DOWN.** `RecordCount` is **0**
      and a query returns nothing, so *the channel records launches* is at this moment an
      untested claim — enabling a log and having a log that works are, again, two claims.
      `AGENTS.md` §9: a null needs a positive control, and this one does not have one yet.
      **Nobody needs to stage it.** The next scheduled run supplies it for free — the coverage
      pass on Sunday 11:00, then the 18:30 daily run on Monday. Read the channel after either,
      and a hit is the control; **an empty channel after a run that demonstrably happened is
      itself a finding**, and a bigger one than this entry.
      **What is still open after that is unchanged and is the original question**: an evening
      the machine is LOGGED OUT at 18:30. The difference is that such an evening now leaves a
      record instead of passing unobserved, which is all this was ever blocked on.
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

1. **Things die in it.** Four traps lived only in the dated session handoff of 2026-08-24, §3,
   and were
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

## 4. Pending decisions

- [ ] **`[v]` THE COST CONSTANT DESCRIBES THE OPENING MINUTE AND IS APPLIED TO EVERY MOMENT —
      measured 2026-09-06, `DR-040` is `proposed` and the ruling is the owner's.**
      ```bash
      PYTHONPATH=$PWD/src python tools/probe_quotes.py
      PYTHONPATH=$PWD/src python tools/measure_quoted_spread.py --data <store>
      ```
      `DR-005`'s **25.44 bps per side** turns out to be **accurate for 09:30** — 0.8x to 1.2x of the
      measured median in every one of five years — and **4x to 14x too high** from 10:00 onward.
      `CARD-001` enters at `next session's open`, so the project charges, and pays, the worst value
      the session offers. Buy-and-hold turns positive below **20.6 bps per side** and the ratified
      exit cell below **6.2**; the measured close is **4.0**.
      **Three questions, and none is mine.**
      1. Does `costs.slippage_model`'s note record which moment its value describes? It reads today
         as a property of the universe and is a property of the universe *at the open*.
      2. Does the model gain an execution-time dimension, so a study can state the moment it charges
         for? One constant on both sides of every fill represents none of the three fill types
         `tools/measure_fill_convention.py` counts (50.6% marketable, 32.8% passive, 16.6% unfilled).
      3. Is `CARD-001`'s `entry.method` reopened? It is a card field and changing it creates a new
         version that resets any validation claim (`STRATEGY_CARD_SPEC` 5 rule 2).
      **What must NOT happen without the study**: adopting the late-session number. A later entry
      changes the gross as well as the cost, and the gross was measured at the open. `DR-040` §6
      names the study; it needs intraday bars, which the venue serves free and `data/` does not hold.

- [ ] **`[v]` THE RATIFIED HOLDING PERIOD IS THE MOST EXPENSIVE OF SIX, AND FIXING IT NEEDS NO
      NEW CAPABILITY — `PR-014`, reported 2026-09-06.**
      ```bash
      PYTHONPATH=$PWD/src python tools/run_pr014.py --data <store>
      ```
      **This is the long-only reading, and it is the one this system can act on.**
      `exit.max_holding_period` is **20 sessions, `assumed:DR-012`**, never tested until now, and it
      is the worst of the six horizons measured. A long-only book turns 12.6 times a year at 20
      sessions and twice at 126, so it pays **6.30% a year against 1.00%** — a difference that is
      arithmetic, not an estimate.
      | horizon | cost/yr | primary net | holdout net |
      |---|---|---|---|
      | **20 (ratified)** | **6.30%** | −3.41% | −3.63% |
      | 126 | **1.00%** | **+3.12%** | **+1.39%** |
      **What it does NOT say.** No long-only cell's interval excludes zero at any horizon, so this
      is not evidence the card beats `SPY`. The point estimate moves from negative on both windows
      to positive on both, and the cost falls by 5.30 points; that is all.
      **What the control added.** The equal-weighted admitted universe loses to `SPY` by 1.58% a
      year (primary) and 4.27% (holdout), so at 126 sessions the top decile is **+4.70% against the
      universe it selects from**. The ranking picks better names than its own pool; `SPY` is what
      neither beats.
      **The ruling is the owner's**: `exit.max_holding_period` is a ratified parameter, and changing
      it creates a new `CARD-001` version that resets any validation claim
      (`STRATEGY_CARD_SPEC` 5 rule 2). Nothing about this needs a short book, new data or a new
      component — which is why it is the smallest complete thing available.

- [ ] **`[v]` THE ONE CONSTRUCTION THAT SURVIVES COSTS NEEDS A SHORT LEG THIS SYSTEM DOES NOT
      HAVE — measured 2026-09-06, and whether to build one is the owner's.**
      ```bash
      PYTHONPATH=$PWD/src python tools/measure_short_leg.py --data <store>
      ```
      Restricting the short leg to the most-traded QUARTILE of the admitted universe makes the
      spread **bigger**, not smaller — the true bottom decile is full of thin names that snap back.
      At 126 sessions the liquid quartile nets **+7.705% [+2.515, +12.863]** after charging all four
      sides of a rebalance. **It is the only construction in this project whose net interval
      excludes zero.** Long-only at the same horizon is +4.305% [−0.509, +9.625] and does not.
      **At the ratified 20-session hold nothing survives**: gross +1.069% against 1.00% of cost.
      **What building it would mean**: `trade_management/portfolio.py` states the system is
      long-only; `CARD-001` requires a stop BELOW the entry; `registry/broker_policy.yml` sends
      `side: buy` and `protect_side: sell`. Shorting also brings borrow fees, hard-to-borrow rates,
      Regulation SHO locates and the uptick rule — **none of which is priced**, so the net column is
      a FLOOR on the cost. And `n=17`: the calendar binds here exactly as it does everywhere else.
      **Not mine to start.** It changes what the system can hold, not how well it holds it.

- [ ] **`[v]` INTRADAY BARS ARE NOW WORTH STORING — 2026-09-06, and it is a scope call.**
      The same free tier that serves quotes serves minute bars back to 2016. Nothing in `data/`
      holds them, and the execution-time study above cannot run without them. The cost is storage
      and a vendor adapter; the benefit is the only lever measured this session that is larger than
      the exit policy it would replace. **Not started, and not to be started on my judgement** —
      it widens the data contract, which is `ADR-0001` territory.

- [ ] **`[v]` THE UNIVERSE ADMITS INSTRUMENTS WHOSE STOP IS NARROWER THAN THE COST OF TRADING THEM
      — measured 2026-09-06, and it is the owner's to rule.**
      ```bash
      PYTHONPATH=$PWD/src python tools/measure_gap_cost.py --data <store>
      ```
      `DR-003` screens on **price** and **dollar volume**. Nothing screens on **volatility**, so
      `SGOV` and `SHV` — Treasury-bill ETFs — clear admission. `SGOV`'s daily range is about
      **0.011% of price**, so a `2 × ATR` stop on it is roughly 0.02% of price against a round trip
      costing 0.5%: **the stop is narrower than the cost of trading it by about twenty-five times.**
      **Measured consequence, `DR-006` §10.3.** Gap cost is monotone in `2 × ATR / price`: below
      0.005 it is **−5.490R** over 603 gaps, and above 0.05 it is **−1.401R**. **Six per cent of
      gaps drag the whole mean from about −1.43R to −1.712R.**
      ~~**This is not a hypothetical corner.** A relative-strength ranking is exactly the selection
      rule that ranks a steadily-rising T-bill ETF highly in a falling market.~~
      **TESTED AND REFUTED THE SAME DAY — `DR-006` §11.3.** Across the five worst `SPY` 126-session
      windows in the store, sub-floor names entered the top decile in **one** of them (the COVID
      bottom, 8 of 18) and the best of those ranked **52 of 826**. The book holds **four**. A falling
      market still leaves ninety names up 50–500% — `DRIP`, `DUST`, `VXX`, `AMR`, `BTU` took the top
      of every window — and a flat instrument at 0% does not outrank them.
      **So for `CARD-001` the answer is: not worth fixing now.** The card does not select these
      names, so the screen buys nothing it would ever have paid. It becomes real for a card ranking
      on something other than relative strength, for a materially larger book, or for any
      measurement that enters the universe rather than a selection — which is what `DR-006` §10 did
      and why this surfaced at all.
      **`risk.stop_too_wide_limit` exists for the opposite case** — `unset`, `read_by: none`,
      `named_in: [Appendix N code STOP, M48-T0746]`. There is no minimum counterpart.
      **What is open, and none of it is an agent's:** whether a minimum `ATR / price` belongs in
      admission at all; whether it is a universe rule (`DR-003`) or a sizing refusal
      (`RISK_SPEC` §3); and what the value is. `AGENTS.md` §8 — the course names no number here, so
      if it is a threshold it needs a pre-registration rather than a guess, and if it is a
      structural exclusion it needs a decision record.
      **What it does NOT block.** `DR-006` §10.5: at the measured −1.712R a four-position gapping
      session costs 6.85R against the 6.77R §8 accepted, so **the cap stays at 4** either way. This
      changes what the book may hold, not how large it may be.


- [ ] **`[v]` `DR-039` RATIFIED 2026-09-05, AND WHAT IS LEFT IS THE WIRING — the venue bills a
      published formula, and the model charged an assumed rate for a commission nobody takes.**
      **Both parameters are set** (`owner`), `registry/fee_schedule.yml` holds the effective-dated
      rates and `fees.py` refuses outside its range. **Nothing charges them yet**: wiring these into
      a backtest changes what it computes, which the record says plainly is a separate decision.
      **Still open: whether a paper account is billed the live schedule.** It is the one of the four
      unestablished items the schedule could not answer, and only a live statement can. Owner question: *"Alpaca shows us
      some fees. Shall we research and take them into a project?"*
      `docs/decisions/DR-039-the-venue-bills-a-published-formula.md`, evidence in
      `docs/decisions/measurements/venue-fees-2026-09-05.json`.
      **Three fee categories appeared on this project's first completed trade and not one of them
      exists anywhere in this repository** — REG (SEC Section 31), FINRA TAF, CAT. Meanwhile
      `costs.commission_model` charges `assumed:DR-004`'s 0.005/share, which on that trade is
      **3.4× the entire real fee bill**, for a commission Alpaca does not take.
      **Both formulas were verified against the regulators' own notices**, not estimated: Section 31
      at $20.60 per $1M of proceeds and TAF at $0.000166 per share, each rounded up to the cent,
      reproduce the billed $0.03 and $0.01 exactly. **One observation can do that because they are
      FUNCTIONS, not distributions** — and the same observation says nothing whatever about
      slippage, which this record does not touch.
      **It changes no verdict and is not offered as one.** The fees are **0.9%** of `DR-005`'s
      slippage term. What it replaces is an `assumed` promissory note with a citable formula.
      **What is open is the ruling**, plus four things the record marks unestablished: whether a
      paper account is billed the live schedule, the CAT rate, the TAF per-trade maximum during
      FINRA's 2026 phase-in, and whether Alpaca's round-up is policy.
      **And one thing this session could not do:** Alpaca's own fee schedule PDF is font-encoded,
      no PDF reader exists in the venv, and installing one was declined rather than done quietly.
      The rates here come from the SEC and FINRA, who set them; Alpaca passes them through. Reading
      that PDF is the first thing to close.
      **Accepting it is not a value swap.** `CostModel.commission()` charges symmetrically on share
      count; Section 31 is a rate on SELL PROCEEDS. §6 of the record names the signature change.


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

      **THE WINDOW CLOSED ON 2026-09-03, and the entry named its own closing condition.** *"That
      cost does not exist today and will the moment one is opened."* Three positions opened that
      morning — `AIS`, `BTSG`, `DINO`, the first this project has ever held — filled from the
      brackets `run-20260903T044052Z-84cbe591` placed and recorded by `sync-fills`.
      **What it actually costs, measured rather than feared: still zero, and by luck.** All three
      are classified, so a fail-closed rule would refuse **none** of them:
      ```
      AIS   coverage 0.9999   technology 0.8943, industrials 0.1027, consumer defensive 0.0029
      BTSG  coverage 1.0000   healthcare 1.0000
      DINO  coverage 1.0000   energy 1.0000
      ```
      So the migration is still free, and it is free because of what happened to fill rather
      than because of anything the design does. ~~**145 admitted universe members have no
      sector**~~, and the
      next fill has no reason to avoid them. The entry's own arithmetic still holds; what changed
      is that it is now one unclassified fill away from costing something, where before it was
      zero by construction.

      **THE ARITHMETIC STOPPED HOLDING ON 2026-09-04, AND THE PROPORTION INVERTED — measured
      2026-09-05 from the run's own funnel.** This entry is built on 145 unclassified members
      out of a ~1,150 universe. Both halves of that moved in one evening:

      | evening | admitted | admitted **UNCHECKED** (no sector) |
      |---|---|---|
      | 2026-09-01 | 1,148 | 119 |
      | 2026-09-02 | 1,148 | 123 |
      | 2026-09-03 | 1,142 | 110 |
      | **2026-09-04** | **3,877** | **2,396** |

      ```powershell
      Select-String -Path data\daily_run.log -Pattern 'admitted UNCHECKED|^\s+admitted\s+\d+'
      ```
      **From roughly one in ten to nearly two in three.** *"A cap that fails open is not a cap"*
      now fails open on the MAJORITY of what it is asked about, and the council's unanimous
      objection was raised when it was a tenth.
      **The cause is a tier that widened without its partner, and it is not the vendor's
      fault.** The coverage catch-up took the admitted universe from ~1,150 to 3,877.
      **`tools/refresh_classifications.py` exists and is scheduled NOWHERE** — neither
      `daily_run.cmd` nor `widen_universe.cmd` mentions it, which is why the classification
      store carries exactly two `knowledge_time` batches, 2026-08-23 and 2026-08-31, for about
      1,171 instruments in total. Against 3,877 admitted names, most of the universe has no
      classification to read and cannot acquire one.
      **This is the same shape as the coverage tier itself, and the tool says so in its own
      words** — so this is a tier that was designed and never scheduled, not an oversight invented
      here. `refresh_classifications.py`'s docstring: *"the cadence is tiered the same way: this
      tool, run occasionally, widens sector coverage"*, and then, exactly: **"Until it has run,
      every candidate is admitted UNCHECKED and the report says so."** `refresh_universe.py` was
      specified as periodic work and registered nowhere for three weeks; this is the second of the
      pair, and it is still nowhere. The report has been printing the `UNAVAILABLE` line in the
      funnel every evening.
      *(The same docstring says "the universe was 1152 members on 2026-08-17" — a population figure
      that has since tripled, sitting in the comment that argues the cadence. It is not wrong about
      its own date; it is the reason this entry re-measured rather than quoting it.)*
      **What it changes for this entry, stated narrowly.** The *decision* — fail open or fail
      closed on an unclassified candidate — is unchanged and still the owner's. What is no
      longer true is the COST side of it: flipping to fail-closed would now refuse 2,396 of
      3,521 candidates rather than a tenth, and leaving it open now admits that many unchecked.
      **Neither reading is cheap any more**, which is the opposite of what this entry
      concluded when the window was measured as free.
      **The cheapest move is not the ruling.** Scheduling the classification refresh beside the
      coverage pass would shrink the unclassified set before anyone has to choose, and it is
      one `schtasks /Create` of the same shape the coverage tier needed — the owner's step,
      because the repository cannot create a scheduled task.

      **RUN BY HAND 2026-09-05 ON OWNER INSTRUCTION, AND IT CLOSED MOST OF THE GAP.**
      `refresh_classifications.py --universe --budget 3000`: **3,000 of 3,000 attempted, zero
      vendor failures**, 361 unusable — no sector served, or a degenerate look-through, which
      is `DR-006` §8.7's bond-fund guard doing its job rather than a fetch failing. The store
      went from about 1,171 instruments carrying a sector to **3,984**.
      **Measured against the admitted universe afterwards, which is the number that matters:**

      | | before | after |
      |---|---|---|
      | admitted universe | 3,877 | 3,958 |
      | with a usable sector | ~1,481 | **3,499** |
      | **admitted UNCHECKED** | **2,396** | **459** |

      From nearly two in three back to about one in eight — roughly where the council was
      looking when it called a fail-open cap *"not a cap"*. **The ruling is unchanged and still
      the owner's**; what changed is that it is no longer being made against a universe where
      the cap sees a minority of its subject.
      **459 is not zero and will not become zero**, and the reason is the same class the
      coverage tier hit: some admitted names have no sector the vendor will serve. That is a
      floor to measure, not a backlog to close.
      **And a wrapper that is not on `master` yet cannot be run by a scheduler.** The first
      attempt invoked `tools\widen_classifications.cmd` in the main checkout, where the file
      does not exist because its branch is unmerged — **`cmd /c` returned 0 and did nothing**,
      no log, no error. The tool was run directly instead. One more shape of silent success,
      and worth knowing before the task is registered against a path.

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
      ~~**23 admitted universe members are refused by the section 8.7 guard today** — 1,018
      spendable, 23 degenerate, 101 no sector, 44 nothing stored, of 1,186.~~ **That was
      2026-08-30, and it is not comparable with anything measured after 2026-08-31.**
      **THE COMMAND NOW EXISTS — built 2026-09-05, because these four numbers had none**
      (`AGENTS.md` §10.6), and a hand tally typed into the file whose header says it never holds
      measured counts is how the drift started:
      ```bash
      python tools/measure_sector_cap.py --refusals --data <store>
      ```
      **AND IT REFUTES THE HEADLINE. `DEGENERATE` IS NOW ZERO.** `DR-025`, accepted **2026-08-31**
      — the day AFTER this measurement — supersedes `DR-021` §4 and with it `DR-006` §8.7's shape
      inference. The guard that produced the 23 no longer exists. **Only the vendor's own
      declared zero refuses now**, and the shape is not consulted at all.
      **Two rules, two populations, and the entry compared across both:**
      | | 2026-08-30, by hand | 2026-09-05, by the tool |
      |---|---|---|
      | admitted | 1,186 | **3,958** |
      | spendable | 1,018 | **3,499** |
      | no sector | 101 | **418** |
      | nothing stored | 44 | **0** |
      | refused on SHAPE (`§8.7`) | **23** | the rule is gone |
      | refused on DECLARED 0% equity (`DR-025`) | not a bucket that existed | **41** |
      **Neither column is a correction of the other.** Different rule, and a universe that more
      than tripled meanwhile. Read the command, never the table.
      **`DR-025` also names what the old guard cost:** it refused **five SPDR Select Sector
      funds that are 99.7%+ equity** — exactly the instruments a sector cap exists to catch.
      **The census carries an `other` bucket, and it earned itself on the first run.** The
      `0% equity` matcher was written against the wrong words and put all 41 there rather than
      silently folding them under a neighbouring heading. A refusal reason added later shows up
      as itself.
      **What this does NOT settle:** whether `DR-021` cost a counter reset. That is a fact about
      2026-08-30 and stays true of that day. What falls is the present tense.
      ~~**Section 6's error is sampling, not reasoning.** It reasons about the five SPDR Select
      Sector funds, and none of the eleven SPDR funds is in the universe at all — coverage is still
      an alphabetical prefix and the letter X is unreached, the same reason `DR-018` section 2b
      found the benchmark ETFs missing.~~
      **REFUTED 2026-09-05 BY THE COVERAGE WIDENING: X IS REACHED AND ALL ELEVEN SPDR FUNDS HAVE
      STORED BARS** — `XLB XLC XLE XLF XLI XLK XLP XLRE XLU XLV XLY`, and **253** instruments
      beginning with X carry bars.
      ```sql
      SELECT count(DISTINCT instrument_id) FROM bars WHERE instrument_id LIKE 'X%';
      ```
      **This makes section 6 MORE checkable, not less wrong.** Its reasoning population now exists
      in the store, so *"the discriminator moves no decision output"* can be tested against the
      very funds it reasoned about instead of being rebutted by their absence. **Stored bars are
      not admission** — whether these clear the liquidity rule is a separate question.
      ~~The guard still fires on ANY degenerate-shaped fund.~~ **WRONG, AND IT WAS WRITTEN INTO THIS
      ENTRY ON 2026-09-05 BY THE SAME SWEEP THAT STRUCK THE SENTENCE ABOVE IT.** `DR-025` deleted
      the shape trigger on 2026-08-31. Correcting one half of a paragraph and restating the
      superseded half is the §12 shape at its smallest — and it survived a gate run and a merge.
      ~~**How many would flip is not measured and is certainly not zero.**~~ **IT IS MEASURED NOW,
      2026-09-05, AND THE PREDICTION WAS EXACTLY RIGHT — every named instrument went the way this
      paragraph said it would.** `CURE` (3x healthcare, reported healthcare), `DPST` (3x regional
      banks, financial services) and `DRN` (3x real estate, real estate) were *"refused on a reason
      that is false for them"* — **all three are now spendable.** `BNDW` and `BNDX`, the global bond
      funds reported as **technology** and *"refused correctly"*, **are still refused** — under
      `DR-025`'s declared-0%-equity rule rather than the shape, so they are refused correctly for a
      better reason. So is `NEAR`, the fund §8.7 was written about.
      **That is the rare case of a prediction registered before the fix and checked after it**, and
      it is worth more than the count: the discriminator did what the entry said, on the names the
      entry named. Re-derive with the `--refusals` command above, never from this paragraph.
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
      **NEW EVIDENCE 2026-09-05, AND IT NARROWS THE PROBLEM RATHER THAN SOLVING IT.** This entry
      ends *"a status claim in prose is not exact, which is the whole difficulty"*. **For one
      subclass that is now measured false.** Gate 28 matches a backticked parameter id against a
      backticked status word and compares to the registry; widened the same day from 88 files to
      **315** — docstrings included — it caught **seven** live stale statuses and returned **zero**
      false positives. A PARAMETER status in prose is exact enough to gate.
      **What stays open is everything else**, and it is most of it: *"gate 10 is unbuilt"*, *"the
      check does not exist"*, *"nothing counts this"* name no registry key and have no artefact
      to compare against. Gate 28 is a fourth shape that shipped, not a general answer.
      **The three rejected probes are not re-opened by this** — they were rejected on false-positive
      rates, and this one's rate was measured, not assumed.
      **Still the owner's call** (`AGENTS.md` §14): whether a status claim must name the artefact
      that owns it, the way §10.5 makes a count name its command.
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
      needs journalled trades, ~~of which there are none~~ — **OF WHICH THERE IS NOW ONE.**
      `POS-AIS-2026-09-03` closed **2026-09-04**, entry 65.70 → fill 70.03, the first completed
      trade this system has ever journalled. **The conclusion survives and its reason has
      changed**: the hurdle is still not convertible, not because no trade exists but because
      one is not a sample. Read the count from `positions.duckdb`, never from this line.
      **Deliberately NOT built: the deflated Sharpe itself.** It cannot be evaluated and building it
      would suggest it can. What was missing was the count, and that now exists.

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

- [ ] **`[v]` THE DELISTED-HISTORY ROUTE IS OPEN, RULED FREE-TIER, AND USED BY NOTHING — owner
      rulings 2026-09-05.**
      ```bash
      python tools/probe_alpaca_delisted.py
      ```
      **Ruling 1, and it settles what a probe never could.** Asked whether SIP historical is a
      free-tier entitlement or an attribute of this account, the owner answered that **the account
      is free tier**. An account's tier is not observable in what the account returns, so this was
      never measurable from here — it needed the owner, which is why `EVIDENCE_SUMMARY.md` §3 called
      it *"the first thing to settle before anything is built on this"*. Settled.
      **Ruling 2 is a DEFERRAL and must not be read as a no** (`AGENTS.md` §15): re-deriving the
      survivorship bound and reopening `PR-002` happens **"only if we need to"**. The route stays
      open and unused on purpose.
      **So the honest status is *measurable*, never *measured*.** No study has used it, and every
      historical number in this repository is still optimistic by an unknown amount. A route nobody
      has taken corrects nothing, and the survivorship marker's obligation is unchanged — it reports
      what a result WAS computed on, not what could have been.
      **What is NOT established, and it is not pedantry:** this is ONE free account observed serving
      it, not Alpaca's documented policy for every free account. If the terms change the route closes
      and nothing here would notice. Coverage also begins **2016-01-04**, so a window opening earlier
      is still unserved — `PR-002`'s and `PR-005`'s both open 2016-08-01, inside it.
      **`RISK_REGISTER` D-1 keeps its severity.** Only the word *never* fell.


- [ ] **`[ ]` THE THREE LEVERS THAT WOULD OPEN A WIDER TARGET, AND NONE OF THEM IS THE TARGET —
      owner instruction 2026-09-01 ("a good checkup and research in future, to open bigger
      possibilities and find stoppers and preventers"). `DR-029` §5 names them.**
      **The stopper is arithmetic and it is worth stating once**: the stop is `2.0 x ATR(14)`, so
      one R is about two ATR, and these names travel about **three ATR in twenty sessions**. The
      reachable range is therefore structurally about **1.5R**. A wider target is not available by
      choosing one.
      1. ~~**`[ ]` A TIGHTER STOP - the strongest candidate and never measured.** … **This is the
         one to run first.**~~ **RUN 2026-09-06 AND REFUTED. IT IS THE WORST DIRECTION**
         (`DR-029` §7, `python tools/measure_exit_surface.py --data <store>`). 123,635
         non-overlapping entries over 5,069 names; net expectancy at the 1R target, by stop:
         **0.5 → −0.776R, 1.0 → −0.327R, 2.0 → −0.128R, 3.0 → −0.057R.** Monotone, intervals
         ±0.004–0.016.
         **The mechanism the lever missed, and its own record labelled the table `Gross of costs`.**
         `DR-005` charges a fraction of PRICE and R is a multiple of ATR, so halving the stop
         **doubles what the same slippage costs in R** — 0.170R → 0.340R → 0.679R, an exact
         doubling. Reachability improves and expectancy does not.
         **And no cell of the 25 beats doing nothing.** The grid's null — hold 20 sessions, no stop,
         no target — is **+0.140R gross / −0.030R net**, against a best cell of +0.084R / −0.036R.
         The ratified 2.0/1R cell gives up about **0.10R per trade** against simply holding. That is
         the price of the risk control, now measured rather than assumed.
         **So expectancy cannot come from the exit; it has to come from lever 3.**
      2. **`[ ]` A LONGER HOLD.** Already scheduled separately and bounded at ~40 sessions by owner
         ruling 2026-08-31. **Two independent measurements now say the same thing about 20**: the
         momentum studies found nothing inside it, and the target grid cannot reach past 1.5R inside
         it. One constraint, two symptoms.
      3. **`[ ]` SELECTION.** Every number above is on unselected entries, so the table moves
         wholesale the moment a card raises the hit rate - and only then does the choice between 1R
         and 1.5R mean anything. This is `CARD-001`'s four unset inputs and the `PR-012` redesign,
         and it is the one of the three that needs a PRE-REGISTRATION rather than a decision record
         (`ALLOCATION_SPEC` §3).
      **RE-TESTED 2026-09-05 AND IT HOLDS.** `DR-029` §5 exists, names these same three levers,
      and closes with *"`TODO.md` carries them"* — the link resolves in both directions. The
      arithmetic's inputs are set rather than assumed-in-prose: `exit.atr_stop_multiple` = 2.0
      and `exit.max_holding_period` = 20, both `assumed:DR-012`.
      **Do not run these as a single study.** 1 and 2 are exit-policy thresholds and belong to decision
      records; 3 is an ordering and belongs to a pre-registration. Merging them would let an
      ordering inherit an exit threshold's authority, which is the exact confusion §3 exists to stop.

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

      **AND THAT SPREAD IS LONG-SHORT, WHICH THIS SYSTEM CANNOT TRADE — measured 2026-09-06.**
      `_spread` is top decile MINUS bottom decile; `portfolio.py` says *"this system is long-only
      today"*. A long-only book earns the top decile against the BENCHMARK.
      ```bash
      PYTHONPATH=$PWD/src python tools/measure_long_only_horizon.py --data <store>
      ```
      | horizon | n | top decile − `SPY`, net |
      |---|---|---|
      | 5 | 453 | **−0.393% [−0.623, −0.164]** — significantly negative |
      | 20 (ratified) | 112 | +0.057% [−0.788, +0.893] |
      | 63 | 35 | +1.709% [−0.855, +4.628] |
      | **126** | **17** | **+4.305% [−0.509, +9.625]** |
      **The significant result does not survive the conversion.** Long-short at 126 excludes zero;
      long-only does not — gross lower bound **−0.009%**, zero to three decimals.
      **And the binding constraint is the calendar, not the sample rule.** Seventeen non-overlapping
      126-session windows exist in a decade: the horizon with the largest effect is the one with the
      fewest independent observations, and patience does not change that arithmetic.

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
      declaration, silence is not. Every reported study now carries it, read from each
      pre-registration's own §5 and marked `recorded`; no measurement changed. The census is
      `python tools/verify_study_summary.py`, never this line — it read *seven* until
      2026-09-05 and the record had moved past it.
      **The DATES were never the declaration**, and that is what the gate had to be written around:
      `PR-002` carried a full three-way train/validation/test block from the day it ran while the
      question of what it bought went unasked for the study's whole life. A condition satisfied by
      the presence of a `split` key would have passed `PR-002` and `PR-012` both. A test pins that.
      **THE BLOCKER WAS TESTED 2026-09-05 AND IT IS REAL** — which the first three sweeps could
      not assume, four of their seven "impossible" claims having been false.
      `PREREG_TEMPLATE.md` rule 3: *"An amendment made after seeing data downgrades the study to
      exploratory."* The rest of the entry checks out too — the `split buys` field is in §5's
      form, §7 carries the accounting, rule 7 states it, and gate 25's condition lives in
      `verify_prereg_conformance.py`.
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
      estimates declared in a comparable shape, and the reported studies do not share one
      (`python tools/verify_study_summary.py` for how many there are).
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
      **BOTH GATE FIXES RE-TESTED 2026-09-05 AGAINST THE RUNNERS, not against this line.**
      `verify_studies.py` holds `VERDICTS = ("ACCEPT", "REJECT", "INCONCLUSIVE", "REFUSED")`
      with a comment dating the addition to the day the sample rule fired, and
      `trial_budget.py` reads a study's declared `trials` field. The ceiling's two inputs are
      both ratified as the entry says: `risk.max_concurrent_positions` is `owner`,
      `exit.max_holding_period` `assumed:DR-012`.
      **Open:** pooling the primary window is the honest route to a sample, and §5 fixed the split
      before the run, so it needs a NEW pre-registration rather than an amendment.

- [ ] **`[v]` `a.reproducible` IS MEASURED ON THE REAL UNIVERSE AND NO STORED MANIFEST CAN
      DEMONSTRATE IT — two different claims, and the second is what stays open.**
      ~~`a.reproducible` HAS NEVER BEEN MEASURED ON THE REAL UNIVERSE.~~ **That was the title until
      2026-09-04, and this entry's own body had refuted it since 2026-08-24** — see *RUN 2026-08-24,
      AND IT PASSES* below. A reader who takes a heading as the finding got the opposite of what the
      paragraph says. Originally found 2026-08-24 by reading `journal.duckdb` rather than the
      documents; the reason is still not the one `HANDOFF.md` gives.
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

      **RE-RUN 2026-09-05: THE CRITERION STILL HOLDS AND THE HASH ABOVE IS UNREACHABLE.** Both
      figures moved and only one of them is a claim about the system:

      | | 2026-08-24 | 2026-09-05 |
      |---|---|---|
      | universe | 1,141 | **3,959** |
      | `output_hash`, both passes | `50e1646b933a4a9d` | **`d0e2601777138443`** |
      | wall time, both passes | 11m40s | **~61 min** |

      **`--- reproducible: PASS (full universe, 3959 instruments)`.** Determinism is intact,
      and it is a stronger result than the first one: iteration order, set membership and
      dictionary insertion get three and a half times as many chances to bite.
      **The hash is not comparable and that is not a defect** — the coverage catch-up took the
      admitted universe from 1,141 to 3,959, so the two runs decided over different
      populations. **A different hash here means the UNIVERSE moved, not that determinism
      broke**, and anyone re-running this to check the criterion would meet that first. The
      2026-08-24 figure is kept above because it was the byte-identity evidence for a code
      change, and it is true of its own date and population.
      *(This is the trap `AGENTS.md` §12 names about answering from a proxy, in its numeric
      form: a recorded hash reads as a fingerprint of the CODE and is a fingerprint of the code
      **and** the universe **and** the parameters. Only one of the three was stable.)*
      **The cost row is the one to plan against.** ~61 minutes for both passes against the
      recorded 11m40s — 3.5x the instruments for about 5x the wall clock, because the run also
      makes one live vendor fetch per member. It was already too slow for a merge gate and the
      reason is unchanged (`CI_POLICY` §4 forbids a gate to touch the network); what changed is
      that it is now an hour of somebody's afternoon rather than ten minutes.
      Derive all three with `python tools/verify_reproducible.py --data …`, never from this
      table.

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
      `DR-018`, written 2026-08-24, ~~`proposed`~~ **`accepted` — ratified by the owner
      2026-08-30, corrected here 2026-09-05**. The record's own header says so; this line had
      said `proposed` for six days. Derive every figure with
      `python tools/measure_benchmark.py`, never from this line.

      **AND CHECKING THAT TURNED UP THE THING WORTH KEEPING — 2026-09-05.** `rs.benchmark`
      declared **`read_by: none`** while `pipeline.py:299` reads it:
      `benchmark_id = str(registry.use("rs.benchmark").value)`, inside `_benchmark`. Corrected
      to `swingdesk.application.pipeline:_benchmark`.
      **This is §7's direction REVERSED, and nothing was watching it.** §7 exists because
      parameters carried values no line of code read, so `read_by: none` is the honest answer
      for those and gate 1 accepted it unconditionally. **A parameter that IS read and says
      nobody reads it understates the system**, and it is the more dangerous half: `none` is
      what a reader consults before retiring something, and `CHANGE_MANAGEMENT.md` §5 makes
      `unused` a deletion candidate. A ratified benchmark was one review away from looking
      like dead weight.
      **GATE 1 NOW CHECKS IT, and it was measured before shipping** (`AGENTS.md` §12's habit,
      which rejected three of four mechanisms on 2026-08-25 on their own numbers):
      | | |
      |---|---|
      | parameters declaring `read_by: none` | 75 |
      | whose id appears anywhere in `src/` as a string | 8 |
      | **whose id reaches an actual registry call** | **1** |
      The eight-to-one gap is the whole design: the check matches the CALL
      (`.use` / `.decimal_value` / `.int_value` / `.string_value` / `.bool_value` with a
      literal id), not the literal. The seven near-misses are ids named in refusal text or in
      lists, and a check firing on those would be the noise `CI_POLICY.md` §3 describes.
      **Extended gate 1 rather than adding a gate**, because `read_by` is already gate 1's
      subject and §10.5's argument applies to checks as much as to counts. Two tests; removing
      the branch kills the one that asserts it and nothing else.
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
      `rs.benchmark` = `SPY` (`assumed:DR-018`); ~~`rs.benchmark_form` **`unset`**, because the form
      decides what the card trades and `ALLOCATION_SPEC` §3 sends that to a pre-registration.~~
      **RULED `path` 2026-09-01 (`DR-030`), provenance `owner`** — §3's route was followed to its
      end and closed, and the form is chosen structurally: point-to-point ranks at Spearman
      1.000000 with raw return.
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
      ratified. ~~`rs.benchmark_form` stays `unset` on purpose: having four characterised options
      rather than one guessed one is what `DR-018` was for.~~
      **RULED 2026-09-01 (`DR-030`): value `path`, status `owner`.** The four characterised
      options are still the reason the ruling could be made rather than guessed, which is what
      `DR-018` bought. Corrected 2026-09-05, four days late, and **gate 28 could not see it
      because *"stays"* was on its transition-word list** — a word that asserts the present
      state rather than naming one end of a move. That word is off the list now, and the gate
      reads docstrings as well as markdown, which is where the worse instances were.

- [ ] **`[v]` PR-007** registered, unreported — **checked 2026-08-30 against the files rather than
      the mark**: `docs/prereg/PR-007-base-strategy-measured-costs.md` exists and
      `docs/prereg/results/` holds no report for `PR-007`. It and `PR-009` are the registered
      studies with no report, which is the gap `HANDOFF.md` §2's studies row counts.
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
      ~~New research is also suspended, overridden for `PR-013` only.~~ **Stale — the suspension was
      LIFTED ENTIRELY by the owner on 2026-08-30** (§2 of this file carries the ruling). Re-read
      that entry rather than this line; it is the blocker-expires shape §6 records, three entries
      later.
      Corrected forward in `PR-009` §10, `prereg/README.md`, `DR-006` §18, `ALLOCATION_SPEC.md`,
      `GO_LIVE_GATES.md` and `CI_POLICY.md`.
      ~~**RE-TESTED 2026-09-05 AND IT STILL HOLDS, which is the uncomfortable half.** … The
      registration change this entry called for has not been made in the eleven days since.~~
      **THAT NOTE WAS WRONG AND I WROTE IT THE SAME DAY. THE CHANGE WAS MADE ON 2026-08-25.**
      `docs/prereg/PR-009-drawdown-distribution.md` §10 carries it as a dated **first amendment**,
      and `docs/prereg/README.md` indexes it — *"its subject moved — see its §10 first amendment"*.
      The amendment states the same two facts this entry does and cites the same reconciliation.
      **I read the title and §1, saw −15R nine times, and called an append-only record stale for
      still saying what it was registered saying.** That is the mechanism working:
      `docs/05-validation/PREREG_TEMPLATE.md` §3 — *"appended, dated, never edited in place"*. §1
      MUST still read −15R; the amendment is where the correction lives, and looking only at the
      head of a file whose contract is *append* is a §17 granularity error.
      **What remains open is not a defect and is cheap only while it stays that way.** The study has
      never run, so `PREREG_TEMPLATE.md` rule 3's downgrade-to-exploratory does not bite — §10 says
      so in its own words. **The moment data is drawn, any further correction costs the study its
      confirmatory status.** So the open question is whether to re-register under the live threshold
      BEFORE running, and that is a research decision (`AGENTS.md` §14), not a repair.
- [ ] **`[v]` Reserved prereg ids with nothing written yet:** PR-001b (unblocked, writable now) ·
      PR-003 (needs a daily return series) · PR-004 (needs ~100 journalled trades) · PR-006 (needs a
      forward test). **Checked 2026-08-30 against `docs/prereg/README.md`**, which is the index gate
      3f keeps honest and the only place this belongs; `PR-011` is also unwritten and is tracked in
      its own item two rows down, which is why it is absent here rather than missing.
      **`PR-011b` joined the reserved set on 2026-09-04** — the CLASS half `PR-011` split off,
      exploratory in advance, and the item below records why. Re-derive rather than trusting
      this list, which is a copy of an index and rots the way copies do:
      ```bash
      ls docs/prereg/ && grep -n 'PR-0' docs/prereg/README.md
      ```
      Checked that way 2026-09-04: `PR-011` is now WRITTEN and on disk, so this line's own
      pointer to it is what stayed accurate while the set around it moved.
- [ ] **`[v]` PR-002's registered perturbations were not all run.** §5 registers threshold ±20%,
      1-bar execution delay, and cost stress. Only cost stress (1×/3×) is implemented in the runner.
      **So the original `ACCEPT` rested on one of three registered robustness checks** — a defect
      independent of the country condition, and not fixed by the 2026-08-16 correction. Needs a new
      run, which means a new pre-registration: the runner cannot reproduce the 2026-08-02 sample.
- [ ] **`[v]` Some studies rest on fewer checks than they registered.** Gate 25 names which, on every
      run (permitted — concluding less than you registered is always allowed — but the verdict is
      weaker than its report implies):
      `PR-001` unrun `sma_periods_pm20pct` (`overlap_per_regime` was conditional on a classifier
      that did not exist at run time, so it was not runnable rather than skipped) ·
      `PR-002` unrun `thresholds_pm20pct`, `execution_delay_1bar`.
      Both need new runs, which means new pre-registrations: neither runner can reproduce its
      original sample (both fetch the current directory and current Yahoo history).

      **TESTED 2026-09-05, and the parenthesis is TRUE — checked at the source rather than
      taken on trust** (`AGENTS.md` §15 rule 1: an impossibility names the test that
      established it):
      ```bash
      grep -n 'urlopen\|vendor_yahoo.fetch\|BarStore' tools/run_pr001.py tools/run_pr002.py
      ```
      Both `urlopen` the two directory files and call `vendor_yahoo.fetch` per name. **Neither
      opens the bar store at all**, so neither has a vintage to pin — the `--reproduce` flag
      that `run_pr012` and `run_pr013` gained on 2026-09-05 has nothing to attach to here.
      **But *the runner* cannot is not *nothing* can, and the counter-example is in the same
      directory.** `PR-005` was in this exact position and got `tools/run_pr005_replay.py` — a
      store-backed replay that re-derives the cells and compares them to the published result.
      It is a guard rail rather than a study: it re-derives the SAME statistic, so it spends no
      trial, and it caught a real drift on 2026-09-05.
      **What such a replay could and could not settle here, stated so nobody expects the wrong
      thing.** It could not reproduce the ORIGINAL sample: `PR-002` ran 2026-08-03T02:24 and
      the store held nothing for those names until later that day — `tools/measure_study_drift.py`
      prints `UNAVAILABLE` for exactly this reason, and `PR-002.json` cannot even be asked
      because it records `instruments` as a COUNT rather than a list. It could establish
      whether the headline result survives on today's data, which is what `PR-005`'s replay is
      for and what nothing currently does for `PR-002`.
      **The unrun perturbations still need a new pre-registration and that is unchanged.**
      Running `thresholds_pm20pct` or `execution_delay_1bar` on a different sample is a new
      study whatever the mechanism, so this correction narrows the claim rather than
      overturning the conclusion: what was foreclosed is the cheap check, not the study.

## 6. Code & gates

- [ ] **`[v]` GATE 28 WAS BLIND TO SEVEN LIVE INSTANCES OF THE EXACT DRIFT IT EXISTS FOR, AND BOTH
      BLIND SPOTS WERE INSIDE THE GATE — found and fixed 2026-09-05.**
      ```bash
      python tools/verify_parameter_claims.py
      ```
      **The two defects, each exact rather than general.** `_documents()` globbed `docs/**/*.md` and
      `*.md`, so no docstring was ever read — and a docstring is what somebody reads BEFORE changing
      the thing it describes. And `stays` / `remains` sat on the transition-exclusion list beside
      `was`, `moved` and `from`, though they are that list's inverse: they assert the present state
      continues, which is the claim itself.
      **A third defect surfaced only once code was in scope**: `~~` was matched per line, so a struck
      sentence wrapped at the column limit read as struck on its first line and live on its second.
      That would have reddened `portfolio.py`, a file that is CORRECT, which is the false positive
      `CI_POLICY.md` §3 says gets a gate bypassed.
      **Seven live instances, and the staleness is measured in weeks, not days:**
      | where | parameter | called | registry | stale since |
      |---|---|---|---|---|
      | `pipeline.py`, `exits.py`, `test_pipeline.py`, `track_a_streak.py` | `exit.atr_stop_multiple`, `exit.max_holding_period` | `unset` | `assumed` | 2026-08-17 |
      | `ALLOCATION_SPEC.md`, `PARAMETER_REGISTRY.md` | `risk.per_trade_pct` | `unset` | `owner` | 2026-08-11 |
      | `portfolio.py`, `measure_sector_cap.py` | `rs.ranking_method` | `unset` | `owner` | 2026-09-01 |
      | `TODO.md` | `rs.benchmark_form` | `unset` | `owner` | 2026-09-01 |
      | `test_corporate_actions.py` | `data.revision_epsilon` | `unset` | `owner` | — |
      | the backtest costs module | `costs.slippage_model` (and its commission twin) | `unset` | `assumed` | — |
      **THE SHARPEST ONE IS `DR-012` §8.3, and it is an argument about governance rather than about
      a docstring.** That record did not merely make `ExitPolicy`'s docstring stale — it **named the
      file and ordered the correction in the ratifying commit**, quoting the sentence and saying
      which half survives. It did not happen, and nothing noticed for nineteen days. **A stated
      intention with no check is not a control.**
      **And it is today's §12 trap one carrier further out.** The trap says a refutation reaches the
      SUMMARY and dies before the SPECIFICATION. Here `HANDOFF.md` had it right the same day —
      *"`DR-012` ratified both parameters on 2026-08-17, so that window never opened"* — and the
      CODE never heard. Two of the seven were in files whose own headers already carried the
      correction: `portfolio.py` strikes the claim at line 23 and repeats it at line 379.
      **Mutation-tested**: each of the three changes reverted in turn, each kills its own test.
      **What is NOT claimed.** The gate reads a status word near a parameter id on one line. It does
      not understand a claim spread over a paragraph, and `measure_stale_claims.py`'s null result
      earlier today is the same limit from the other side: a claim nobody struck has nothing to
      compare against. This closes the backtickable form, which is the form that recurs.


- [ ] **`[v]` A BLOCKER EXPIRES AND THE ENTRY THAT NAMED IT DOES NOT — three found in one evening,
      2026-09-04.** Not a hypothesis: three open entries were opened for unrelated reasons and all
      three described a world that had stopped being true.
      | entry | what it claimed | when it stopped being true |
      |---|---|---|
      | §6b `WIRE TECH INTO THE DAILY RUN` | *"the scheduled pass never calls it"*, blocked until the adapter ran for real | `DR-035`, 2026-09-03 — and the pass stopped on `TECH` that evening |
      | §6 `A FILL IS NEVER RECORDED WITHOUT A PERSON` | *"`positions.duckdb` is written only by `open-position` and `respond`"* | `DR-031`, 2026-09-03 — `sync-fills` writes it, before the scan |
      | §6 instrument identity (a) | blocked on a missing symbol directory | the directory holds 13,339 symbols; measured 2026-09-04, fixed the same day |

      **The sample is what it is and is not extrapolated.** 66 items are open and 48 carry `[v]`;
      roughly eight were opened last night and three of those were stale. That is a rate worth
      acting on and not a census — the other forty have not been re-read.
      **Why the `[v]` mark does not catch it.** It records that an item was verified *when written*,
      which is exactly the shape `AGENTS.md` §12 names as this repository's most persistent failure:
      *"a citation that was CORRECT when written, still standing after the fact it cites moved."*
      Every one of the three was correct on its own date.
      **The fix has a precedent in this file.** §10.5 stopped counts rotting by giving each one an
      owner and making every other mention name the command instead. The same move works on a
      blocker: **a sentence saying something is blocked, missing or unwired names the command that
      would show it had changed.** `read_by: none` and `verify_parameters.py` are the working
      example — a parameter's unwired-ness is re-derived on every gate run rather than asserted in
      prose.
      Not built here: whether it can be a gate depends on whether such sentences can be recognised
      exactly, and `AGENTS.md` §12's habit is that a gate over prose needs an exact token or it
      becomes noise. **The cheap version needs no gate at all** — the convention, applied when an
      entry is written.

      **SECOND PASS, 2026-09-04, and it found a sharper shape than the first one.** Five open items
      carrying a blocking claim were re-tested against the tree and the stores rather than re-read.
      Two are still exactly true — `data.staleness_action_threshold` is `unset` with `read_by: none`
      in the registry, and `PR-011` is still unwritten. **Three were wrong, and all three in the
      same way: the TITLE asserted a state the entry's OWN BODY had already struck through.**
      | entry | its title said | its own body already said |
      |---|---|---|
      | `a.reproducible` has never been measured on the real universe | never measured | *"RUN 2026-08-24, AND IT PASSES"*, with the hash |
      | Almost every recorded `Skip` is `RISK / risk.per_trade_pct` | almost every one | *"No such skip has been recorded since the parameter was set"* |
      | Half the journalled runs carry `code_dirty` | half | `HANDOFF.md` §2 owns the count, and the line said so |
      **That is a different failure from an expired blocker and it is cheaper to fix.** No
      measurement is needed to catch it: the contradiction is inside the entry. A reader who takes
      the heading as the finding — which is what a heading is for — carries away the opposite of
      what the paragraph establishes, and every one of these three headings had stood for at least
      ten days over a body that refuted it.
      **One body was wrong too, which is the part that did need a measurement.** *"The dirty era
      ended on 2026-08-17"* — the journal has every scheduled pass from 2026-08-25 19:30 through
      08-27 19:30 dirty.
      **Rule, applied here and cheap enough to keep:** when an entry is corrected, the TITLE is
      corrected with it, and a title carries no numeral. Not proposed as a gate — `AGENTS.md` §12's
      standard is an exact token, and *"a heading contradicted by its own paragraph"* is not one.

- [ ] **`[v]` A FILL IS NEVER RECORDED WITHOUT A PERSON — ~~AND THAT IS NOW WHAT PAUSES THE
      MACHINE~~ CLOSED FOR OUR OWN ORDERS 2026-09-03 (`DR-031`), still true and still correct for
      everything else.** `DR-027` §11.3 names this file, so this is the entry that claim points at.
      ~~**The state today is correct and manual.** `positions.duckdb` is written only by
      `open-position` and `respond`.~~ The submission path writes no position deliberately (`DR-027`
      §6: a `Position` is a thing created from the FILL, and an accepted order is not a fill). So a
      run submits up to the ratified caps, and the NEXT run stops with `TECH` until somebody
      records what filled — which is `DR-027` §11's guard doing its job, not a defect.

      **RE-CHECKED AGAINST THE TREE 2026-09-04, and the struck-through half is a month out of
      date.** `sync-fills` writes `positions.duckdb` — `cli._sync_fills` calls `adoption.adopt` and
      `store.record` — and `tools/daily_run.cmd` runs it **before** the scan, which is `DR-031`'s
      ordering argument: the caps must be measured against what is actually held, not against
      yesterday.
      Evidence rather than a docstring. The three positions this project holds were written in a
      single instant, `2026-09-03 12:45:38.955385-05:00`, which is one programmatic call and not
      three typed commands; and the scheduled log carries the pass doing its job on both runs since:
      ```
      Alpaca paper trading  3 holding(s) at the venue
        nothing to record - the book already describes every holding
      ```
      **What is still open is the part that SHOULD be**, and it is worth keeping the entry for:
      a holding that traces to **no order this system placed** is still `TECH`, still pauses new
      entries, and still needs a person. That is the untraceable case — a hand-placed order, or a
      fill against something this book has no record of asking for — and adopting one automatically
      would be `DR-026`'s refusal reversed by the back door. **The entry's cost sentence is what
      expired, not its argument.**
      **What it costs:** one manual `open-position` per fill, every evening anything fills, or the
      machine stands still. That is the right trade while nothing is validated and the caps allow
      four names; it does not survive contact with a book that turns over.
      **Why it is not just plumbing.** Constructing a `Position` from the venue's answer is what
      `DR-026` refused. `DR-027` §3.2 narrows that argument — *this* system placed the bracket, so
      the venue knows the stop and it is readable from `/v2/orders` — but it does not close it: the
      fill price is the venue's, and the costs figure and the strategy tag are still ours to state.
      `BrokerFill` already carries price, shares and time from the activities feed.
      **Entry criterion, not a date:** the first evening a fill is recorded late enough to stop a
      run that should have proceeded. Until then the guard is what makes the omission loud instead
      of expensive, and loud is cheap.

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
      **RE-MEASURED 2026-09-04 AND STILL OPEN, but narrower than the title reads.** On an
      ordinary day the two passes are fine: `schtasks` reports the daily run at 18:30 and the
      second pass at 19:30 on 2026-09-04, **each with exit 0**, an hour apart as designed.
      ```bash
      SWINGDESK_DATA=C:/PycharmProjects/SwingDesk/data PYTHONPATH=$PWD/src python tools/verify_schedule.py
      ```
      **The collision is a property of the CATCH-UP, not of the schedule**, so a clean day is
      not evidence against it and is not offered as any — it says only that nothing has regressed
      and that the last measured collision is still 2026-08-29's. The decision `DR-019` frames
      is unchanged, and the thing that would settle this item is a day the machine misses its
      trigger, not another clean evening.
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
      **Row 10 stays `to build` deliberately, and the decision survives its own arithmetic being
      wrong.** ~~About twenty documents refer to gate 10 as the thing they are waiting for …
      Retiring the row would make twenty documents stale to save one line.~~
      **RE-DERIVED 2026-09-05: ELEVEN NAME IT, AND EIGHT STATE IT AS UNBUILT** — `REQUIREMENTS.md`,
      `USER_STORIES.md`, `EXPECTATION_MODEL.md`, `CI_POLICY.md`, `KNOWLEDGE_GRAPH.md`, `ROADMAP.md`,
      `HANDOFF.md` and this file. The remaining three name it without asserting a status.
      ```bash
      grep -rlEi "gate[ -]10\b" docs/ AGENTS.md HANDOFF.md TODO.md README.md
      ```
      The rest of the sentence holds: gate 38's vocabulary is the inventory and not the runner, so
      a row marked `to build` keeps every one of those citations legal. **Eight stale documents to
      save one inventory line is still a bad trade, so the row stays** — but the trade was argued
      from a figure two and a half times the tree's, and nothing had derived it.
      **This is `AGENTS.md` §12's *"a number you worked out in your head is still a number"*, and
      it is also the ownerless-claim trap added to §12 today** — `CI_POLICY.md` row 38 carried the
      same *"twenty-odd"*, so correcting only this file would have left it standing. Corrected in
      both.
      **AND THE COUNT FOUND A REAL DEFECT, which is the argument for re-deriving rather than
      re-reading.** One of the eleven does not treat gate 10 as pending at all: `FRD.md`'s preamble
      said the traceability check *"fails on an orphan in either direction"* — present tense, about
      a gate `check_gates.py` does not register. **Fixed at the generator** (`tools/build_frd.py`),
      because the document says *do not edit by hand* (`AGENTS.md` §10.6).
      **What IS verified in this entry**, checked 2026-09-05 rather than carried: `REQUIREMENTS.md`
      §7 exists — *"What enforces each — the linkage §6 has been waiting for"* — and gate 35's
      runner does name it.
      **The original entry, kept because its reasoning is what narrowed this:** **Weighed
      and not built 2026-08-25**, with the reason recorded so it is not re-derived: its three checks
      are *a course id with no requirement row*, *a requirement with no test*, and *a spec id cited
      by no test*. The middle one would fire immediately on requirements that are deliberately
      **NOT met** (`REQ-AI-001`, `REQ-AI-002`, `REQ-EVIDENCE-001`), and the third has one active
      component to range over. What it needs first is the linkage `REQUIREMENTS.md` §6 names — each
      requirement paired with the test or gate that enforces it, or an honest "nothing does", the
      way `INVARIANTS.md` §1 already does for its nine. **That artefact is the work; the gate is the
      easy part after it.**
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
- [ ] **Instrument identity is synthesized instead of resolved — two defects, not one.** Restated
      2026-08-16 after checking each site; the earlier entry named the wrong pair of lines and
      missed (b) entirely. `reference_data/universe.py:159` `to_instrument()` is the *correct*
      construction — `id` from the `DirectoryStore` symbol, `ticker` from `vendor_symbol()` — and
      both sites below bypass it.
      - **(a) — FIXED 2026-09-04.** ~~`cli.py`:29 really does derive `id` from what the user
        typed~~, which the contract
        forbids ("Never derived from the ticker alone"). Typing `BRK-B` mints id `BRK-B`; the
        universe path calls the same instrument `BRK.B`. That is two identities for one instrument
        in a bitemporal store, which cannot be un-split after the fact. **Never triggered**, and
        re-checked 2026-09-05: `bars.duckdb` holds **zero** dashed ids, which is the half that
        carries the argument. ~~12 dotted~~ — that number was 12 when written, is 25 now, and
        this file's own header forbids it holding a count at all (`AGENTS.md` §10.5):
        ```sql
        SELECT count(DISTINCT instrument_id) FROM bars WHERE instrument_id LIKE '%-%';
        ```
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
      **RE-MEASURED 2026-09-04, and two of this entry's four claims have moved.** The entry is from
      2026-08-16 and the world under it changed twice since.
      - **Still not triggered, and that is measured rather than assumed.** `bars.duckdb` holds
        **13 dotted ids and zero dashed** — `BRK.A`, `BF.A`, `AGM.A`, `CRD.A`, `CIG.C`, `BIO.B`,
        `BH.A`, `CNQ.TO` among them — and `positions.duckdb` holds neither form. Nineteen days of
        real trading, and the split has not happened.
      - **The cost of it happening went up.** In August the book was empty; there are open
        positions now, so a second identity would split a book that is being managed rather than
        one that is not there yet.
      - **The directory can now resolve, which is the load-bearing change.** It held zero usable
        rows for this purpose in August; it holds **13,339** symbols today, and every ticker in
        actual use resolves — `AIS`, `BTSG`, `DINO`, `CM`, and `BRK.A` in its dotted, canonical
        form. **`BRK-B` is ABSENT precisely because the canonical form is dotted**, which is the
        defect stated as a lookup: what the user would type is not what the store calls it.
      - **So a fix exists that needs no new source and no ruling.** `_instrument` mints
        `id=base` from what was typed; `universe.vendor_symbol()` already maps canonical → vendor
        (`BRK.B` → `BRK-B`), so the reverse lookup over the directory identifies the one canonical
        symbol a typed ticker means. Resolve when it is unambiguous, refuse when it is not
        (`AGENTS.md` §3, fail closed), and leave today's behaviour where the directory has no row —
        which keeps `.TO` and unknown symbols exactly as they are.
      ~~**Not built in the same pass that measured it, deliberately.**~~ **BUILT 2026-09-04, in
      its own pass, which is what §17 asks for rather than that it never happen.** `_instrument`
      resolves against the directory and returns one of three answers:
      - the directory knows the symbol — by its own name, or as the vendor's form of **exactly
        one** symbol — so typing `BRK-B` now yields `id=BRK.B` with `ticker=BRK-B`, the
        directory's name for it and the vendor's form of it, each in its own field;
      - the vendor's form is **ambiguous** → a refusal naming the candidates. `vendor_symbol` does
        not invert: `AMH$G` and `AMH.PG` both map to `AMH-PG` and neither is spelled that way, so
        choosing would put an invented identity into an append-only store (`AGENTS.md` §3);
      - **no directory row → the old behaviour, minted, and said out loud on stderr.** Refusing
        here would refuse every Canadian instrument over `DR-003` gap 1, which is somebody else's
        open item. The note is what stops that being silent, and it names which of the two reasons
        applies — the first draft blamed Canada for a US ticker's absence.
      **No decision record**, and that is stated rather than omitted: this applies
      `universe.to_instrument()`'s existing construction to a second site and defines nothing.
      **What is still open in this entry is only (b)'s neighbourhood** — the identity work the
      universe path already does correctly, and the Canadian half that waits on `DR-003` gap 1's
      wiring. The split this entry was written about can no longer be minted from the CLI.
      Blocks any historical edge claim; does not block Track-A-only PAPER.
- [ ] **Some journalled runs carry `code_dirty = true`, and a manifest pointing at a dirty tree
      cannot be replayed from its SHA.** `a.reproducible` requires a byte-identical re-run from a
      stored manifest. **`HANDOFF.md` §2 owns the count** — this line read ~~11 of 13~~ until
      2026-08-25 and ~~half~~ until 2026-09-04, both true when written and both a second copy of a
      figure §2 generates (`AGENTS.md` §10.5). The title carries no numeral now, which is the only
      version of this line that cannot rot.
      ~~The dirty era ended on 2026-08-17 and its records are immutable, so the share falls only by
      adding clean runs.~~ **That sentence was wrong, measured against the journal 2026-09-04.** A
      SECOND dirty era ran afterwards — every scheduled pass from 2026-08-25 19:30 through
      2026-08-27 19:30 is dirty, which is the `daily_run.cmd` leftover chain `HANDOFF.md` §8
      describes. **It has stopped:** every scheduled pass since 2026-08-31 is clean. Why it stopped
      is not established here and is marked conjecture (`AGENTS.md` §10.4) — the leftover is a
      property of what the main checkout is carrying at 18:30, not of the code.
      **RE-TESTED 2026-09-05 AND IT HOLDS ON ITS OWN POPULATION — WHICH IS NARROWER THAN IT
      READS.** All **11** scheduled passes since 2026-08-31 are clean. But **4 HAND RUNS in the
      same window are dirty** — 09-02 00:02, 09-02 10:22, 09-03 15:42, 09-03 20:45 — and they sit
      in the same `runs` table `a.reproducible` reads. *"It has stopped"* is true of the
      SCHEDULE and false of the JOURNAL, and a reader takes it for the second.
      **Whether a hand run should be journalled at all is not settled here** and is the more
      useful question: a manifest nobody will replay costs nothing, and one somebody might
      costs the criterion. Re-derive rather than reading any sentence above:
      ```sql
      SELECT started_at, code_dirty FROM runs ORDER BY started_at;
      ```
- [ ] **A large block of the recorded `Skip`s is `RISK / risk.per_trade_pct`, and every one of them
      predates 2026-08-11** — unset-parameter refusals, i.e. a system fault rather than market
      judgment. Any statistic over the decision history must segment them out first.
      ~~Almost every recorded `Skip` is `RISK / risk.per_trade_pct`.~~ **The title said that until
      2026-09-04, and the body below had already refuted it** — which is the shape this file keeps
      producing: a heading asserting a state its own paragraph has struck. Checked against the last
      three runs on 2026-09-04: their `RISK` skips carry NO `parameter_id`, they are the `DR-006`
      book cap, and the same runs record `Trade` decisions. The parameter is `owner`, valued, and
      its `read_by` resolves.
      ~~4,486 of 4,510~~ **— corrected 2026-08-25, and the numerator is the half that cannot move.**
      No such skip has been recorded since the parameter was set, so the count of them is frozen
      while the denominator grows with every evening; quoting the pair makes the ratio look worse
      than it is and it was already stale. Derive both from `data/journal.duckdb`, which
      `HANDOFF.md` §3 names as their owner:
      ```sql
      SELECT reason_code, parameter_id, COUNT(*) FROM decisions WHERE decision = 'Skip'
      GROUP BY 1, 2 ORDER BY 3 DESC;
      ```
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
      **AND MORE THAN IEX, ESTABLISHED 2026-09-05.** `feed=sip` served complete daily paths for
      delisted US names from 2016-01-04 with this project's paper key, and the owner ruled the
      account is **free tier** — so the free tier reaches historical SIP, not only IEX. The
      delisted route in §5 is what that opened; nothing has used it.
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
      ~~**`APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` are not set, so it has NEVER been run
      against the live endpoint** — the field names come from Alpaca's published reference, not
      from an observed response.~~
      **EXPIRED, AND MEASURED RATHER THAN READ — 2026-09-04.** The adapter has been run against
      the live paper endpoint on three separate evenings, and the evidence is the venue's own
      answers in `journal.duckdb`'s `submissions` table rather than a docstring:
      ```sql
      SELECT outcome, min(attempted_at), max(attempted_at), count(*) FROM submissions GROUP BY 1;
      ```
      **eight `sent` rows carry `venue_status = accepted`** — `SPY` on 2026-09-01, then `AIS`,
      `DINO`, `BFH`, `BTSG` on 09-02 and three re-armed on 09-03 — beside eleven `rejected` and
      the stopped majority. A `rejected` row is the strongest evidence of all that the field
      names are right, and the rows carry the venue's OWN error bodies rather than ours —
      *"bracket orders require take_profit.limit_price"*, *"invalid limit_price 66.949997.
      sub-penny increment does not fulfill minimum pricing criteria"* — which is a request
      Alpaca parsed and authenticated. `positions.duckdb` holds the three names that filled.
      The keys stay in the environment and never in a file here — this repository is public
      (`SECURITY.md` §2.1, `tools/verify_secrets.py`).
      **What (a) deliberately does NOT do, and it is not a gap that more code closes.** A broker's
      answer cannot construct a `Position`: the venue knows symbol, quantity and average entry and
      does **not** know the STOP, which is what `RISK_SPEC.md` §2 denominates every R in. Nor can a
      fill be joined to an approved action — the venue carries an order id, and `Fill` settles a
      `position_id` and a `sequence`. So it reconciles and reports; `open-position` and
      `record-fill` still take the owner's judgment. Both close only with a `client_order_id` this
      system sets and a bracket order carrying the stop — which is to say, only with (b).
      ~~**(b) ORDER PLACEMENT — open, and `DR-026` §4 lists the six things it must carry.**~~
      **BUILT AND RUN — 2026-09-01 onward, and this line was the last part of the entry still
      describing August.** `scan --submit` places bracket orders (`DR-027`), journals every
      attempt with a coded outcome, and `DR-037` puts a separate `gtc` OCO on once a position is
      recorded, because `DR-036` measured every bracket leg dead at the first close. The caps,
      the drawdown criterion (`DR-034`) and the venue reconciliation (`DR-035`) all sit in front
      of it.
      **§5's question was PUT AND ANSWERED — yes, on 2026-09-01 — and it took a charter
      amendment rather than an argument.** `DR-027` §1 records the question in this entry's
      own words and **`CHARTER` A-002 is the amendment**, so the line above was right that an
      unapproved order needed one and out of date about whether it had been made. *(Written
      here first as "no amendment was needed", which is exactly the §1 failure — a claim about
      a record I had not opened. `DR-027` §1 says otherwise in one line.)*
      **Arming is still the owner's act** (`DR-027` §8): absent, unreadable or unmarked all
      mean stopped (`broker/armed.py`), so a pass nobody armed submits nothing.
      **What is genuinely still open here is narrower and lives in §6b**: a *disarmed* evening
      returns before it reads the venue, so it reconciles nothing and surfaces no `TECH`.
      **Constraints already binding on this work:** `SECURITY.md` §2.1 — no secret in the repo, env
      vars or an OS keyring only, and this repository is public (`tools/verify_secrets.py` says so).
      `CI_POLICY` §4 — CI must never touch the network, so every Alpaca test runs against a recorded
      fixture. `DR-011` §6 keeps the notice surface send-only and this must not quietly become an
      inbound control channel.

- [ ] **`[v]` WIRE `TECH` INTO THE DAILY RUN — ~~or decide not to~~ HALF BUILT 2026-09-03
      (`DR-035`), and what is left is one narrow case.** `swingdesk broker` reports a
      broker/journal mismatch and Appendix N's prescribed action for that code is *"pause new
      entries"* — ~~but nothing pauses anything today, because the reconciliation is a command the
      owner types and the scheduled pass never calls it.~~
      **The obstacle is real and is a decision, not a wiring task:** making the 18:30 pass reconcile
      means putting the broker network call inside the run that `a.run_completes` counts, so a venue
      outage becomes a failed run. `DR-015`'s staleness machinery is the precedent for how to answer
      that (refuse to DECIDE, do not fail the RUN), and `DR-019` is the precedent for asking whether
      a pass should do a thing at all before teaching it to.
      ~~Blocked behind the owner setting the keys — there is nothing to reconcile against until the
      adapter has been run once for real.~~

      **CORRECTED AGAINST THE TREE, 2026-09-04.** The blocker above expired without anybody
      revisiting the entry: the keys are set, the adapter has run for real many times, and the
      struck-through sentence became false on 2026-09-03. **The scheduled pass DOES reconcile and
      DOES pause**, and the decision the entry frames was answered by `DR-035` in exactly the shape
      it predicted — the venue is read inside the run, an unreadable venue stops the SUBMISSION and
      not the RUN, and the report is still written.
      Not a claim from a docstring — from the evening of 2026-09-04, in `data/daily_run.log`:
      ```
      STOPPED  TECH: 3 open position(s) have no stop standing at Alpaca paper trading ...
               The caps are denominated in a stop, so a book whose stops are not at the
               venue bounds nothing. Restore the protection at the venue before adding to it.
      ```
      That pass had 101 sized and eligible Trade decisions and submitted none of them.

      **WHAT IS ACTUALLY LEFT, and it is one case rather than the whole item.** `cli._submit`
      returns at `if arming.stopped:` **before** it reads the venue, so a **disarmed** evening
      reconciles nothing and would not notice a mismatch at all. Disarmed is the default state
      (`broker/armed.py`: absent, unreadable or unmarked all mean stopped), so this is the ordinary
      evening rather than an edge case.
      **It is harmless in the direction that matters and not in the other.** A disarmed pass submits
      nothing, so a mismatch causes no bad order — but a mismatch is precisely what the owner needs
      to know about *before* arming, and today they learn it only by typing `swingdesk broker`.
      **Still a decision, and a narrower one than the entry originally posed:** should a pass that
      will not submit anything spend a venue call to tell the owner what it would have found? The
      cost is one `GET` on an evening that otherwise makes none; the gain is that `TECH` surfaces on
      the schedule rather than on demand. `DR-019`'s question — should a pass do this at all —
      applies to that call and to nothing else now.

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

- [ ] **3c. Off-desk reach is deliberately NOT built.** If "I'm at the machine at 18:30" stops
      being true, re-open `DR-011` — its §1 preserves the whole Telegram analysis so the next
      session does not redo it. Firebase remains specified in §3.4 and unbuilt.
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
