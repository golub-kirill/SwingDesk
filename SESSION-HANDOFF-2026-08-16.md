# Session handoff — 2026-08-16

**Read `HANDOFF.md` first, then `TODO.md`.** This file covers only what changed in this session and
what the next one needs to decide. Delete it once §1 below is actioned.

---

## 1. The one decision that gates everything

**Ratify `exit.atr_stop_multiple` and `exit.max_holding_period`.** Both are `unset` in
`registry/parameters.yml`.

Today `application/pipeline.py` lines 289 and 369 carry a hard-coded `ExitPolicy(Decimal("2.0"), 20)`
— a silent default for two unset parameters, which is a no-silent-default violation sitting in the
production path. **PR #9 removes it.** The moment PR #9 merges, every candidate Skips with a coded
refusal and every open position PAUSEs, because the registry has nothing to read.

That is the fail-closed design working, and it is correct. But it means the system produces no
Watches until those two values are ratified.

Material for the decision already exists: `PR-005` and `PR-007` both fixed **2.0 × ATR** and
**20 bars** — the same values now hard-coded. But PR-005 **refuted** the strategy, so the honest
provenance is `assumed:PR-005`, never `validated:`. What is missing is a decision record that says
so out loud.

**Suggested order:** Monday's 18:30 run reaches streak 5 → freeze lifts → ratify the two exit
parameters → merge PR #9 (counter resets, deliberately) → merge `claude/open-position-command`.

---

## 2. What is open

| PR / branch | State |
|---|---|
| [PR #9](https://github.com/golub-kirill/SwingDesk/pull/9) | **DRAFT, behind the freeze.** 5 correctness fixes to `pipeline.py` / `sizing.py`. CI green. |
| `claude/open-position-command` | Ready, **not** a PR. Branched from PR #9 because it needs `Position.initial_costs_per_share`. Rebase onto master after #9 lands, then open. |

Merged branches still on the remote and prunable: `approval-loop`, `dated-report-artifact`,
`fill-recording`, `local-run-notification`, `pr005-trade-log-replay`, `wire-scan-to-positions`,
`track-a-restart-and-idle-diagnostic`.

**Freeze status:** Track A streak is **4/20**, last clean 2026-08-14. Monday 2026-08-17's 18:30 run
makes 5 and lifts the freeze on `tools/daily_run.cmd`, `application/pipeline.py`,
`trade_management/sizing.py`.

**New rule this session (`HANDOFF.md` §5):** a merge to a frozen file that changes decision output
**resets the counter to zero from the merge date**. Cosmetic changes do not. PR #9 is its first
trigger.

---

## 3. Owner decisions still waiting

- **5b — proposal expiry.** `ActionStatus.EXPIRED` exists and is never written. A stop move computed
  on week-old bars stays answerable indefinitely. Needs a rule for how long a proposal stands.
- **DR-006** — six `risk.*` parameters; every portfolio cap cites `assumed:DR-006`. Must land on
  evaluated values, not a rubber stamp.
- **DR-011** — status `proposed`. The mechanism was chosen by the owner; the record is unratified.
- **A TSX symbol directory.** `DR-003` gap 1. Blocks instrument identity (`cli.py:29` mints an `id`
  from typed input, which a bitemporal store cannot un-split) and the Canadian half of the universe.

---

## 4. What was built

**The operational chain is complete** (`TODO.md` §6b). Before this session the loop had never closed
outside a test fixture; it now runs end to end on a real store.

| # | What | PR |
|---|---|---|
| 1 | `swingdesk open-position` — position entry | on the blocked branch |
| 2 | `scan` opens a `PositionStore` and passes it to `run()` | #11 |
| 3a | Dated report at `<data>/reports/<run_id>.txt` | #12 |
| 3b | Local desktop notice (`DR-011`) | #13 |
| 4+5 | `swingdesk pending` / `respond` — approval recorded and applied | #14 |
| 6 | `swingdesk record-fill` — US-011 | #15 |

Also: Track A restart rule + idle-day diagnostic (#10), and the PR-005 trade-log replay (#16).

### Consequences a fresh session should not rediscover

- **`scan` notifies by default.** `--no-notify` suppresses it. Tests must stub `cli.notify.notify`;
  `tests/test_cli.py` has an autouse fixture that does.
- **The approval response is a separate append-only table**, not a status column. `management.status`
  stays as what the *run* proposed, forever. `pending` is the *absence of a response*, never
  `status = 'proposed'`.
- **`record-fill` refuses to compute slippage on a time exit.** A maximum-holding-period exit is at
  market and names no reference price; `0.00` would be manufactured. `slippage_per_share` returns
  `None`.

---

## 5. PR-005 — closed, and what the next study must know

`docs/prereg/results/PR-005-trades.csv` — 26,351 trades — is published, with
`PR-005-trades-provenance.json` beside it.

**It is not a reproduction of PR-005's inputs, and the artifact says so.** The whole `primary`
period and 16 of 20 cells reproduce exactly. `ABOVE_LONG_MA` (A) and `STRUCTURE` (D) differ in the
holdout by ≤0.00052 mean R at identical trade counts — the two gates that turn on a single margin,
where a revised close flips the verdict without changing which triggers fired.

**This cannot be fixed.** PR-005 fetched live at 02:02 UTC on 2026-08-03; the store's earliest
`knowledge_time` for the sample is later. Proven rather than argued: the pre-refetch state already
differed by +0.177R (A) and +0.339R (D) while holding one *fewer* trade.

> **`PR-009` must register against this replay's vintage, not against PR-005's published aggregate.**
> They are known not to be the same thing.

Standing data-quality fact found on the way: **`LEG` and `NDSN` have no 2026-07-31 bar and the
vendor does not supply one**, while 60 other instruments in the same sample do. Affects no trade.

---

## 6. Research is suspended (council decision, unanimous)

No new pre-registrations; UDR-004 and the PR-001/PR-002 re-registrations are paused. **Not**
suspended: DR-006 ratification and PR-005 (now done). Resume once one real end-to-end cycle has run
and been observed.

---

## 7. The habit that actually caught things

Four times this session a test was written that **could not fail** — `Outcome.REFUSED` defined and
never constructed; a lock test that reopened database files (DuckDB permits that from one process);
two `pytest.raises(SystemExit)` that passed on an unknown command. Every one was caught by the same
ritual and by nothing else:

```bash
git stash push -- src/     # revert the implementation, keep the tests
python -m pytest tests/...  # they must go RED
git stash pop
```

The replay tool did the same thing at a larger scale: it reported **"MISMATCH in 20 cells"** with
complete confidence because of a transposed dict nesting, and would have published a false
accusation that PR-005 does not reproduce. It was caught only because zero replayed trades in
*every* cell was too clean to be true.

**A green check proves nothing until it has been seen red.**
