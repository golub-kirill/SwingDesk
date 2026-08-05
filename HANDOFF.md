# HANDOFF — start here in a fresh session

Written 2026-08-04, after reconciling two parallel documentation efforts. Read this, then
`AGENTS.md`, then `docs/README.md`. Everything below is measured from the tree, not remembered.

---

## 1. What this is

Decision-support software for swing trading Canadian and US equities and ETFs, specified from the
owner's 116-PDF swing-trading course. **It never places orders** — owner decision D1. The human
makes every trading decision; the system prepares, checks and records them.

The project's founding premise: previous attempts failed *upstream of code* — goals, limits and the
algorithm were never frozen first. So documentation is the deliverable and the code exists to prove
the documentation is implementable.

## 2. State, measured

| | |
|---|---|
| Merge gates | **15**, one command, all green |
| Tests | **249**, fully offline |
| Docs | 73 files across 8 tiers |
| Components | 465 registered · 7 `specified` · **0 `active`** |
| Parameters | 96 — 84 `unset`, 9 `assumed`, 2 `owner`, **1 `validated`** |
| Studies | 4 reported — **3 refuted**, 1 accepted and quantifiably fragile |
| Universe | 1,133 members · 3,687 of 13,043 measured · **28.3% coverage** |
| Project gates | G0, G4, G5 closed · G1, G2, G3, G6, G7 open |

```bash
python tools/check_gates.py
```

That must stay green. A gate that is wrong gets **fixed or removed, never skipped**.

## 3. The uncomfortable summary

**The machinery is real and honest. The strategy is not known to work, and what is known is mostly
negative.**

- The base strategy measured **+0.028R per trade before costs** and **−0.123R under 3× cost stress**
  (PR-005). Costs are *assumed*, not measured — so the sign of the result sits inside an
  unvalidated number.
- The one positive finding (PR-002: breadth separates breakout outcomes) is erased by **1.6–2.3% of
  trades missing at −2R**, and Yahoo serves no delisted history, so that exposure can never be
  confirmed on the free tier.
- `CHARTER.md` §4's v1 finish line is a **machinery** target and was reached 2026-08-02. Reaching
  v1 and reporting no validated edge is a **success** against the ratified criteria, not a failure.

Do not write anything that implies more confidence than that. `UX_COPY.md` §3 carries the standing
warning verbatim.

## 4. What just happened (2026-08-04)

Two efforts had been writing into this repo without knowing about each other. A second track built
ten numbered documents at root to master-ТЗ v1.0 §47 — Russian, "documentation only" — having never
opened `docs/`, `src/` or `registry/`. Consequences: its build plan scheduled ~10 specification
sections as future work that was already done, and its README rewrite dropped the "It does not place
orders" line.

Resolved: `docs/` is canonical (owner decision). All of that track's work is preserved verbatim in
commit **`dee8f37`**, its genuinely new material is folded in, and the duplicates are gone.
`docs/08-pm/SPEC_GAP_ANALYSIS.md` is the real §56 analysis: **FULL 28 · PARTIAL 16 · ABSENT 9 ·
DEFERRED 3.**

**Do not rebuild the numbered tree.** Master ТЗ §8 forbids maintaining one logic in two places, and
for a day this repo was doing exactly that.

## 5. What to do next, ranked

Three of these are decisions only the owner can make. They are listed first because they are
overdue, not because they are hard.

### Owner decisions

1. **`k.timebox_review` has fired and is unactioned.** `registry/criteria.yml` is ratified and says:
   trigger *"G5 reached"*, action *"set the Track A time box from measured throughput and issue this
   file as v1.1.0"*. G5 closed 2026-08-02; the file is still v1.0.0. This is the guard against scope
   drift that the project was built to have.
2. **Set the 15 `validation.*` parameters.** All unset, including `go_live_criteria` and
   `max_allowable_drawdown` — which makes the ratified `k.drawdown_pause` inert.
3. **`UDR-004`: which regime ontology is canonical** — the ТЗ's eight or the course's eleven? Only
   the course list has evidence behind it (`REGIME_SPEC.md`).

### Work, highest leverage first

4. **Schedule `tools/fetch_directory.py`.** The only irreversible clock in the project:
   `departures()` accumulates *forward only*, and it is the sole survivorship evidence a free tier
   can ever produce. Every day without it is permanently lost. ~5 seconds/day.
5. **Measure costs instead of assuming them.** Corwin–Schultz (2012) and Abdi–Ranaldo (2017)
   estimate effective spread from daily OHLC — no new data needed. This is the highest-value study
   available, because the base-strategy verdict currently flips on an assumed 5bps.
6. **Unify the trigger before the live path gets one.** `validation/backtest/engine.py` owns
   `breakout_high` and the entry decision; `application/pipeline.py` has none. No divergence yet
   *only* because live implements no strategy — see `REQUIREMENTS.md` §3. Cheap now, expensive later.
7. **Wire the regime classifier into the daily run.** PR-002 is the only validated finding in the
   project and it is not used; checklist item E04 reports `unavailable`.
8. **A mutation gate for `REQ-VALIDATION-001`.** The narrow version — every ratified criterion's
   referenced parameters are set — is cheap and would have caught `k.drawdown_pause`.
9. **Finish universe coverage** — ~5 more `tools/refresh_universe.py` passes to 100%, then re-check
   DR-003's liquidity plateau against the full population.
10. **Fill the ranked gaps** in `SPEC_GAP_ANALYSIS.md` §4: `RULE_SPEC.md` first (seed draft in
    `dee8f37`), then `SYSTEM_MODES.md`, then `EXECUTION_MODEL.md`.

## 6. Closed by evidence — do not re-open

| | Why |
|---|---|
| Trend-definition family | PR-001 (definitions select different instruments) and PR-005 (those populations then behave the same) both refuted. `screen.trend_definition` stays `unset` |
| Paid market data | Owner decision D10, taken with the survivorship cost known |
| Tuning the current parameters | PR-005 measured the strategy flat before costs and negative under stress |
| New entry filters | Same family, same evidence |
| Order placement, automation, multi-user | `CHARTER.md` §3 non-goals — reopening needs a charter amendment |

## 7. The habits that matter here

- **Verify before asserting.** Three documentation defects were found on 2026-08-03, and all three
  read as correct: a stale count, a claim that a transcribed appendix was untranscribed, and a
  framing that made a Berkshire-sized exclusion sound like a rounding error. A careful read did not
  catch them; gates did. When you find that class of defect, add a gate rather than fixing the
  instance.
- **`unavailable` is not `fail`.** A gap in the *system* and a fact about the *trade* are different
  claims. Collapsing them is the most damaging error this product can make.
- **An `UNSET` parameter is the design working**, not a backlog item. Components refuse rather than
  default.
- **Never hand-edit** a `verbatim` block or a generated registry field. Gates 2, 3b–3e exist to
  catch it, which is the point.
- Docs **are** committed here. Every threshold is authored and carries its provenance.

## 8. Where things live

```
docs/00-charter     what this is, what done means, glossary, kill criteria
docs/01-requirements BRD, user stories, NFR, surfaces, REQ registry
docs/02-domain      the course, transcribed and specified
docs/03-data        point-in-time, calendar, vendors, quality
docs/04-journal     audit, checklists, journal schema, evidence records
docs/05-validation  backtest protocol, walk-forward, prereg template, go-live gates
docs/06-engineering architecture, dependency law, determinism, CI policy, invariants
docs/07-ux          task flows, controlled vocabulary
docs/08-pm          roadmap, risk register, gap analysis, definition of done
docs/prereg         four pre-registrations and their reports
registry/           parameters, components, course index, checklists, criteria
src/swingdesk/      the reference implementation — the vertical slice ТЗ §50 requires
tools/              the 15 gates, plus network tools that never run in CI
```
