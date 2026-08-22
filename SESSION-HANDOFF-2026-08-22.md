# Session handoff — 2026-08-22

**Read `HANDOFF.md` first, then `TODO.md`.** This covers only what changed on 2026-08-18 and
2026-08-22. Delete it once §1 is actioned.

Replaces `SESSION-HANDOFF-2026-08-19.md`, whose §1 — build `DR-015` — is **done and merged**
([PR #24](https://github.com/golub-kirill/SwingDesk/pull/24)).

---

## 1. The one thing to build next

**Wire the portfolio cap.** `risk.max_open_risk = 4R` and `risk.max_concurrent_positions = 4` were
ratified by the owner on 2026-08-22 and are **`read_by: none`**. `positions.open_risk_as_of` already
computes the number and `report.py` already prints it; nothing compares it to a limit.

**It is not one control among six — it is the only one that acts on the failure mode that actually
occurs.** Measured over PR-005's 26,351 trades: 89 sessions hold **52% of all 3,003 gap exits**, the
worst produced **87 simultaneous** gap-outs, and those days are **not forecastable** from anything
this project holds (`DR-006` §8.6 — day-of-week refuted, prior volatility refuted *and inverted*,
lift 0.59× i.e. worse than random). A per-trade stop cannot defend against a gap; a bound on
simultaneous exposure can.

Build it fail-closed and coded, same shape as the freshness gate. `TODO.md` §4 carries the rest.

## 2. What was ratified, and the number that moved

`DR-006` **partially ratified**, provenance `owner`:

| | |
|---|---|
| `risk.max_open_risk` | **4R** — was 6R |
| `risk.max_concurrent_positions` | **4** — was 6 |
| `risk.max_position_value` | 2,500 |
| `risk.liquidity_cap_order_to_adtv_pct` | 1.0% |

**Why 6R fell.** §1 anchored it on "a catastrophic session costs roughly the whole open risk, so
about 6R … two and a half such days reach the pause". The trade log says a gap exit loses **−1.692R**,
not 1R — so a whole-book gap session costs **10.15R** and −15R is **1.5 sessions** away. Four
positions restores the record's own intent (6.77R → 2.2 sessions). Free consistency: 4 × 2,500 =
`account.equity`, so four max-size positions is exactly fully invested.

## 3. Three things a fresh session must not re-inherit

- **`DR-006` §3's "unevaluable" claim is WRONG and §8.4/§8.7 correct it.** Correlation is not blocked
  at all — the 1152 × 1152 matrix builds from the store in **0.09 s**. Sector has a free source, and
  so does the **ETF look-through** (`funds_data.sector_weightings`). What is genuinely missing is
  only the **point-in-time** sector, which restricts a backtest and not live admission.
- **The vendor fabricates the look-through for bond funds.** `NEAR` → **healthcare 100.0%**, and it
  is a short-maturity bond fund with no equity sectors. A degeneracy guard is a **precondition** of
  the sector cap, not a refinement.
- **The gap rate is not a general property of holding overnight.** It splits hard by instrument
  class — bond ETFs **27.4%**, foreign-market ETFs **23.3%**, US single names **7.5%** — and both bad
  classes have a mechanical cause: a bond ETF's 2×ATR stop is 0.57% of price while round-trip costs
  eat 88% of it, and a foreign ETF's underlying trades while the US market is shut, so the stop is
  unenforceable by construction. **`PR-011` is the pre-registration for screening them out, and it is
  not yet written.** The sign flip that exclusion produces (−0.0691 → +0.0362 mean net R) is
  **post-hoc on fitted data and must not be adopted as a finding.**

## 4. `master` went red on its own, and the trap is now in `AGENTS.md` §12

CI failed gate 8 on the PR, and the four failures reproduced on an **untouched `master`**.
`test_cli.py` seeded a proposal dated 2026-08-16 and four tests let `pending` / `respond` read the
wall clock; `management.proposal_expiry_days` is 3 sessions, so **on 2026-08-20 the window closed and
the gate began failing on a tree nobody had touched.** The symptom pointed nowhere near the cause —
the failures surfaced in tests about approval and rejection, neither of which is about expiry.

**The rule:** if a fixture carries a hard-coded date and the code under test reads `now`, the test is
asserting something about today. Pin both, or neither.

## 4b. The scheduled run was DEAD for four days, and is fixed

**Found 2026-08-22 while checking whether the tree was ready to hand over.** Exit 1 on every evening
from 2026-08-18 to 08-21, both passes, ~45 seconds each instead of the usual 5-12 minutes.

**Cause:** `PR #9` added `initial_costs_per_share` to the `positions` table on 08-17.
`CREATE TABLE IF NOT EXISTS` does nothing to a table that already exists, so the column never
appeared on disk, and `positions.open_as_of` - which `run()` calls before any candidate - died on
`BinderException: Referenced column ... not found`.

**Fixed structurally, not patched.** `platform/schema.py` reconciles every store at open: an empty
drifted table is re-created from its own declared SQL, a populated one refuses and names the drift.
The live `positions.duckdb` is healed (it held 0 rows) and a real `scan --universe --limit 5` now
completes and writes a report. Backup kept beside the store.

**What it cost:** Track A reads 0 with its most recent break on 2026-08-21, and the journal carries
**7 incomplete runs**. Those are real and stay in the record.

## 5. Still on the owner

- **`DR-016`** — `data.revision_epsilon = 0.001`, price only. Proposed.
- **`DR-017`** — the ADTV lag, 3 sessions. Proposed, and §3.1 asks whether the parameter belongs in
  the registry at all given `AGENTS.md` §7 wants a course citation the course does not supply.
- **Register the 19:30 task** — one `schtasks` line, `docs/runbooks/README.md` §1a. Until it exists
  the retry inside the run is live and the second pass is not.
- **`data.staleness_action_threshold`** — still `unset`, still read by nothing.
