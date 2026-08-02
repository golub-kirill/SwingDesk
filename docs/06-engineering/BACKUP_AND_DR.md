# BACKUP AND DISASTER RECOVERY

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored

---

## 1. What must survive, and what must not be trusted to

Not everything is equally recoverable, and the difference decides the backup strategy.

| Asset | Recoverable from vendor? | Backup priority |
|---|---|---|
| **Journal, decisions, evidence records** | **no** | **critical — irreplaceable** |
| **Revision history / point-in-time record** | **no** | **critical — cannot be rebuilt** |
| `registry/*.yml`, docs, code | yes (git) | covered by git |
| Bar data (current values) | yes, re-fetchable | low |
| Run manifests | no | high |
| Reports | regenerable from manifests | low |

**Two things cannot be recovered from anywhere**, and they are the two the whole design rests on:

1. **The journal** — the record of what was decided and why. No vendor has it.
2. **The revision history** — our own point-in-time record. Re-fetching gives *today's* version of
   the past, not what we knew at the time (`POINT_IN_TIME_SPEC.md` §7). Losing it means every
   backtest silently becomes a backfilled-history backtest, which is a weaker claim, and one that
   would be easy not to notice.

That second point is the non-obvious one: **bar data looks re-fetchable and its history is not.**

## 2. Objectives

From `NFR.md` §5:

| Objective | Value |
|---|---|
| RPO | one trading day |
| RTO | one run |
| Backup frequency | daily, after the run completes |
| Restore test | **required**, scheduled, not assumed |

## 3. The restore test is the actual requirement

An untested backup is a belief, not a control. The test:

1. Restore into a scratch location.
2. Replay a stored run manifest against it.
3. **Compare `output_hash` against the original.**

If it matches, the backup is proven to contain everything a run depends on. If it does not, the
backup is incomplete — and the manifest tells you which input is missing.

This is the same mechanism as `criteria.yml` `a.reproducible`, pointed at the backup instead of the
code. It costs almost nothing extra because determinism was already required, which is a good sign
the design is coherent rather than accumulating separate machinery per concern.

## 4. Scope and placement

- **Local first.** Everything stays on the machine by default (`PRODUCT_SURFACES.md` §3.4).
- A backup leaving the machine is a **data-exposure decision**, not just a durability one: it
  contains positions and decisions. If it goes off-machine it is encrypted, and that is an explicit
  choice rather than a default.
- **Secrets are never in the backup.** They live in the environment or a keyring
  (`SECURITY.md` §2), so a restored backup is inert until credentials are supplied — which is the
  correct property.

## 5. Failure modes this covers

| Scenario | Recovery |
|---|---|
| disk failure | restore, replay, verify hash |
| accidental deletion | same |
| corrupted store | restore to the last verified backup; the append-only design means the loss window is bounded by backup frequency |
| bad migration | restore; append-only storage means the pre-migration state is intact rather than overwritten |

Append-only storage (`AUDIT_AND_IMMUTABILITY.md`) is doing double duty here: it was adopted for
audit integrity, and it also means most "corruption" is an added bad record rather than a destroyed
good one.

## 6. Not covered

- Machine loss with no off-machine copy. If durability past a single disk is wanted, that is an
  explicit decision with the exposure trade-off in §4.
- Vendor disappearance. `ADR-0001` covers the substitution question; no backup helps if Yahoo stops
  serving.

## 7. Open items

- [ ] Backup target and rotation policy.
- [ ] Whether the restore test runs weekly or monthly. Weekly is cheap if it is a scripted replay of
      a small fixture.
- [ ] Whether off-machine backup is wanted at all. It is a real durability gain and a real exposure
      increase, and it is the owner's call rather than a default.
