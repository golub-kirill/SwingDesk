# NFR — non-functional requirements

**Status:** drafting · **Tier:** 1 (requirements) · **Content:** authored

Numbers, not adjectives. Where a figure is an estimate it says so and shows its arithmetic, because
an unstated estimate becomes a fact the moment someone quotes it.

---

## 1. Scale

Sizing assumption: **~1,500 instruments** in the A-tier universe across US and Canada. The liquidity
thresholds are unset, so this is an estimate for capacity planning, not a target.

| Series | Bars per instrument | Rows at 1,500 instruments |
|---|---|---|
| `1d` (30 years) | ~7,560 | ~11.3 M |
| `1h` (~725 trading days) | ~5,075 | ~7.6 M |
| `30m` (60 trading days) | ~780 | ~1.2 M |
| **Total** | | **~20 M bar rows** |

At ~50 bytes per row that is ~1 GB raw, and a few hundred MB in a columnar format. **Bar volume is
not a constraint.**

## 2. The real storage constraint is revisions, not bars

Point-in-time correctness requires that we never overwrite. The naive reading of that — snapshot
everything daily — is unworkable: 20 M rows × 252 days = **~5 billion rows per year** for a dataset
whose informative content is a few thousand new bars a day.

**Requirement:** store **revision deltas**, not snapshots. A fetch writes a row only where a value
differs from the current known value, plus the genuinely new bars.

Expected steady state:

| Event | Rows written |
|---|---|
| A normal day | ~1,500 new daily bars + ~1,500 new intraday sets |
| A corporate action on one instrument | its full adjusted history rewritten (~7,560 rows) |
| A vendor-wide re-adjustment | worst case, a full rewrite |

That last row is why the delta must be computed, not assumed: Yahoo rewrites adjusted history on
every refetch, so a naive "append what came back" would write 20 M rows daily. **Compare before
writing.**

Budget: **≤ 5 GB after one year** of daily operation, including revision history.

## 3. Latency

The post-close window is ~17.5 hours (16:00 ET close → 09:30 ET next open), so the wall-clock
constraint is not the market — it is the owner's evening.

| Stage | Budget | Notes |
|---|---|---|
| Incremental daily refresh | **≤ 20 min** | ~1,500 instruments, 3 intervals, vendor rate-limited. I/O-bound; concurrency applies here. |
| Full historical refresh | ≤ 4 h | Rare. Backfill or vendor change. |
| Derived observations | ≤ 5 min | Vectorised over ~20 M rows. |
| Decision path | **≤ 5 min** | Single-threaded and deterministic by construction (`ARCHITECTURE.md` §3). Not a place to optimise with concurrency. |
| Report generation | ≤ 30 s | |
| **End-to-end daily run** | **≤ 45 min** | |
| Backtest, one card, 30 years, full universe | ≤ 2 h | Process-parallel. The only genuinely expensive operation. |

## 4. Determinism

| Requirement | Value |
|---|---|
| Re-run from manifest | **byte-identical** output |
| Wall clock in domain packages | **zero occurrences** — time is injected |
| RNG | seeded, seed recorded in the manifest |
| Iteration order feeding output | canonically sorted at every merge point |
| Dependency versions | pinned |

Not an engineering preference: the fail-closed table's return condition after a screener failure is
`повторный run совпал с контрольным` — a re-run matching a control run — so determinism is an
operating procedure.

## 5. Availability and recovery

Single-user, one scheduled run per day. **There is no uptime requirement**, which removes a whole
class of complexity — and saying so explicitly stops it being re-added later.

| Objective | Value |
|---|---|
| RPO | one trading day — the last completed snapshot |
| RTO | one run — re-fetch and re-run |
| Acceptable consecutive missed runs | 1, with a visible warning; ≥2 blocks new decisions on staleness |
| Backup | daily, with a **tested** restore |

The manual fallback is not a nice-to-have: `FAIL_CLOSED_POLICY.md` row 2 requires a printable list
of positions, stops, targets and events that works **with the system down**.

## 6. Cost

| Item | Ceiling |
|---|---|
| Market data | **$0/month** (free tier, D8) |
| Infrastructure | **$0/month** — local machine, local database |
| Firebase | free tier, push only |
| **Total** | **$0/month** |

Consequence, stated plainly: point-in-time correctness and delisted history **cannot be bought at
this ceiling** — measured on two vendors. Raising the ceiling is the only path to either.

## 7. Correctness properties

Non-negotiable, and each testable:

| Property | Enforcement |
|---|---|
| R denominator is always the initial planned risk | property test |
| Open risk is recomputed, never decremented | property test |
| Shares always round down | property test |
| Stop is set before size | ordering test |
| A stop change increasing risk is rejected | write-time invariant |
| No decision is produced from data whose knowledge time exceeds the decision time | property test on the bitemporal layer |
| The same inputs always yield the same classification | property test — the course's `Два наблюдателя дают одинаковый статус` |

## 8. Observability

| Requirement | Value |
|---|---|
| Every run writes a manifest | mandatory |
| Every refusal is logged with its code and failing input | mandatory |
| Structured logs | one schema, machine-parseable |
| Secrets in logs | **zero** — vendor keys and tokens masked at the handler |

## 9. Open items

- [ ] Universe size firms up once the liquidity thresholds are set. Every figure in §1–§3 scales
      roughly linearly with it.
- [ ] Backtest budget in §3 is an estimate with no measurement behind it. Re-derive after the
      walking skeleton, when one real bar-by-bar pass has been timed.
- [ ] Whether the second source (Questrade) is fetched daily for corroboration or only on conflict.
      Daily doubles fetch time; on-conflict cannot detect a conflict it has not looked for. Decide
      in `DATA_QUALITY_SPEC.md`.
