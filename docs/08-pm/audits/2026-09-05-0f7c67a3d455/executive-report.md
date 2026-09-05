# Audit 2026-09-05-0f7c67a3d455 — executive report

**Status:** drafting · **Tier:** 8 (PM) · **Run:** 2026-09-05, report-only

**Subject.** Commit `0f7c67a3d455c9cd20378b8b2b6106db5c46588e`, tree
`8e3f2c6c80a68069ea6e239eb07e585893973834`, the operator-supplied ref `master`. Frozen at
2026-09-05T22:18:45Z in a detached worktree and verified pristine before every command. No
`TARGET_MOVED`.

**Scope executed.** The audit plan's Tasks 1, 2 (condensed), 3, and the adversarial core of 4–8.
Tasks 9–12 were not run; §5 says which and what it costs.

**The verdict is about this commit under the executed scope**, never about `master` generically.

---

## 1. Domain verdicts

| Domain | Verdict |
|---|---|
| Decision Safety | **ASSURED under the executed scope** — six of seven non-negotiables PASS on an executed oracle; the seventh was a lead that dismissed on evidence |
| Engineering Quality | **ASSURED under the executed scope** — native baseline fully green, subject guard proven to refuse |
| Research Integrity | **NOT_ASSURED** — one finding, `AUD-001`, and it is a claim this repository published about itself |

**Non-compensatory**: the Research Integrity verdict is not offset by the other two, and no count of
passing checks clears it.

## 2. The native baseline, and what it is not

| command | result | seconds |
|---|---|---|
| `python tools/check_gates.py` | **all gates pass** | 212.6 |
| `python -m pytest tests/ --collect-only` | collected clean; the census is `HANDOFF.md` §2's and the ledger preserves this run's | 2.0 |
| `python -m ruff check .` | all checks passed | 0.1 |
| `python -m mypy src` | no issues in 83 source files | 0.5 |

**Green here closes nothing adversarial**, and this repository's own history is the argument: gate 6
reported `6 import contracts PASS` for weeks over a check that never executed, and gate 14 printed
`0 failures` over a pattern that could never match.

## 3. The seven non-negotiables, probed independently

Each has an oracle asserted about the frozen tree, checked by reading or executing it — not by
believing a docstring.

| obligation | status | oracle |
|---|---|---|
| No orders without arming | PASS | no broker module carries an HTTP write verb without consulting the switch |
| Unset is not default | PASS | no `default:` field in the registry; no handler substitutes a value for `ParameterUnset` |
| Records are immutable | **lead → dismissed** | see §4 |
| Money is exact | PASS | no `float(` on a price or amount outside reporting and statistics |
| Time is injected | PASS | no `datetime.now(` in the three domain packages |
| USA and Canada never merged | PASS | the calendar map is venue-keyed |
| Fail closed, exercised | PASS | 223 refusal-related tests executed and passed |

## 4. The lead that dismissed, and the finding it uncovered

**Three `UPDATE`/`DELETE` statements were flagged. All three dismissed, and the dismissal is the
interesting part.**

`journal.py`'s `UPDATE runs SET output_hash = ?, completed_at = ? WHERE run_id = ? AND output_hash
IS NULL` can only ever fill a NULL — the `WHERE` clause makes a second write find no row. The two
`DELETE FROM` statements clear and re-insert **at one `knowledge_time`**, which is `INSERT OR
REPLACE` semantics spelled out, and appends a version at any later instant.

**Chasing that dismissal overturned a finding this repository published earlier the same day.**

### AUD-001 — a replay pins the data and not the code

| | |
|---|---|
| **domain** | Research Integrity |
| **severity** | material — it changed a published conclusion about the system |
| **obligation** | `AGENTS.md` §10.4 — a causal claim names its check or is marked conjecture |
| **affected** | `TODO.md` §6's PR-005/PR-012 entry, merged in `c1e4601` |

**Observed.** `TODO.md` claimed *"one store's own clock does not bound its own answer"* and *"no
study reading classifications can be reproduced"*, on the evidence that `PR-012` pinned to its own
snapshot reported `classified: 1036` where the study recorded 1,013.

**Required.** The cause of a moved number is established, not inferred.

**Reproducer.** Load the pre-study `classification.py` from `61f6d6e~1` beside today's, and judge
the same rows at the same pinned clock:

```
instruments classified at the pinned clock        1148
usable under the code as it was when PR-012 ran   1023
usable under today's code, SAME rows, SAME clock  1046
verdicts FLIPPED                                    23
```

**23 is the entire discrepancy.** Two commits — `61f6d6e` on how the sector guard decides a fund
holds equity, `d67b931` on the look-through's shape — changed the verdict on stored rows without
touching a row.

**Impact.** The published claim indicts a store that is behaving correctly, and it hides the real
property: **a replay pins the DATA and not the CODE**, so any study whose interpretation logic has
moved will fail to reproduce *and will look exactly like the data moving*. That applies to every
replay in the repository, not to one store.

**Falsification.** If the flip count were not 23, or if rows existed at the pinned clock that were
absent on 2026-08-24, the store would be implicated after all.

**Remediation** (report-only; not applied): correct the entry forward — done in this change — and
consider recording the code version a study was interpreted under. `RunManifest` already carries
`code_hash`; a study result does not.

**Regression test.** A test that pins two versions of an interpreting function over one stored row
and asserts the replay reports which version it used.

## 5. What was not run, and what it would cost

| task | status | why | what already covers part of it |
|---|---|---|---|
| 9 — persistence and recoverability drills | **OUT OF SCOPE** | owner ruling 2026-09-05 | **nothing** |
| 10 — fault injection against adapters | **OUT OF SCOPE** | owner ruling 2026-09-05 | `tests/test_broker.py` runs the adapter against recorded responses |
| 11 — mutation testing beyond gate 34 | **OUT OF SCOPE** | owner ruling 2026-09-05 | gate 34 mutates the tests `INVARIANTS.md` names |
| 12 — secret-scan under `sensitive/` | **OUT OF SCOPE** | owner ruling 2026-09-05 | gate 19 checks the committed tree and the ignore rules |

**The owner ruled these four out of scope on 2026-09-05**, and the ruling is recorded here rather
than left as an omission — an audit whose gaps are undocumented reads as complete, which is the
failure this whole report is about.

**Three of the four have a partial substitute already under a gate**, which is why the ruling is
reasonable rather than a hole: the adapter is exercised against recorded responses, the invariant
tests are mutated on every run, and the committed tree is scanned.

**Task 9 has none, and that is the one to know about.** Measured while recording this ruling: there
is no backup tool, no restore tool and no recoverability tool in `tools/`, and no restore rehearsal
on record anywhere. Backups have been taken by hand — the 2026-08-18 unclosed-bar deletion kept one
beside the store — but **nobody has ever demonstrated that this project's stores can be restored
from one.** That is not a finding of this audit, because the audit did not test it; it is the
standing exposure the ruling leaves in place, stated so the next reader does not have to rediscover
it.

## 6. The cost, which is why this ran

**Wall clock: about 70 minutes**, of which roughly 25 was the audit's own instruments — the guard,
its eleven negative tests, the oracle harness and the reproducer — and the rest was waiting on the
native baseline and the reproduction.

**A second run costs less**, because the instruments now exist and are in the vault: the marginal
run is the baseline (~4 minutes) plus the oracles (~2) plus whatever the session chases.

**So weekly is affordable, and the plan's caution was right for a different reason than expected.**
The expensive part was never the machinery — it was chasing one lead to the bottom, which is the
part that produced the only finding. A weekly audit that runs the harness and stops at the first
green summary would have reported *all gates pass* and missed `AUD-001` entirely.

## 7. Evidence

Raw vault, outside git, not committed:
`C:/Users/User/AppData/Local/Temp/claude/audit/2026-09-05-0f7c67a3d455/`

```
vault/commands.jsonl     append-only ledger, before and after every subject command
vault/outputs/<label>/   preserved stdout and stderr per command
vault/oracles.json       the seven obligations and their evidence
guard.py                 subject guard and ledger, 11 negative tests, all passing
oracles.py               the seven oracles
reproducer.py            AUD-001's first attempt, which the source refuted
code_vs_data.py          AUD-001's reproducer, which settled it
```

Evidence verification passes: every preserved output still hashes to what the ledger recorded, and
tampering with one byte is detected.
