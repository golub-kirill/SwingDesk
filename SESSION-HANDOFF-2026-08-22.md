# Session handoff — 2026-08-22 (evening)

**Read `HANDOFF.md` first, then `TODO.md`.** This covers only what changed in the session that
built the portfolio cap. Delete it once §1 is actioned.

**This file replaces an earlier `SESSION-HANDOFF-2026-08-22.md` written the same morning, whose §1
— wire the portfolio cap — is now done and merged.** That file was deleted rather than edited, as
its own header instructed. Its other sections were migrated first, not dropped: the test-date trap
and the `CREATE TABLE IF NOT EXISTS` trap are in `AGENTS.md` §12, the gate-24 morning-drift friction
is now there too, `DR-006`'s ratification is in that record's §8, and its one item that lived nowhere
else — **`PR-011` is not written** — is now `TODO.md` §5.

---

## 1. The one thing to build next

**Build the sector and correlation caps.** They are `DR-006`'s remaining two, they are the only
items in `TODO.md` §4 that are **not** waiting on an owner ruling, and building them is what lets
the owner rule on numbers whose checks actually run (`DR-006` §8.4's own condition).

Three things are already established and must not be re-derived:

- **Correlation is not blocked.** §3 of that record said *"nothing computes a correlation matrix"* —
  a statement about missing CODE, not missing data. The full 1152 × 1152 matrix over 60 sessions of
  daily returns builds from the existing store in **0.09 s**. Of 662,976 pairs, **1.57%** sit at
  r ≥ 0.70 and p99 is **0.759**, so the threshold is neither vacuous nor over-broad.
- **Sector has a free source**, `yfinance` — already the only bar vendor — including the ETF
  look-through `DR-006` §2 requires. What is genuinely missing is only the **point-in-time**
  classification, which restricts a backtest and not live admission. Do not conflate the two.
- **The vendor fabricates the look-through for bond funds.** `NEAR` → **healthcare 100.0%**, and it
  is a short-maturity bond fund with no equity sectors at all. **A degeneracy guard is a
  precondition of the sector cap, not a refinement** (`DR-006` §8.7).

**The shape to copy is now in the tree.** `trade_management/portfolio.py` is what a cap looks like
here: pure, parameters read once per run, a frozen result carrying its own `reason`, wired at step 6
of `RISK_SPEC.md` §3, and `read_by` in the registry naming the function that consumes it.

## 2. What was built, and what it changed for everyone else

`DR-006`'s book cap is live ([PR #28](https://github.com/golub-kirill/SwingDesk/pull/28)).
`risk.max_open_risk` = 4R and `risk.max_concurrent_positions` = 4 are enforced at step 6, after
sizing. `DR-006` §9 is the full record; four consequences a fresh session will meet:

- **`swingdesk open-position` can now refuse.** Over the cap it exits 2 and needs
  `--acknowledge-over-cap "<reason>"`, which records the reason and the book as it stood into a new
  append-only `cap_overrides` table. Owner ruling — the command records a fill that already happened,
  so the escape hatch is required; what it must never do is record a fifth position as though the
  limit had been met.
- **Candidates are measured against the open book alone.** A `Watch` is not a position. The report
  says so where it shows the room, because "room for 3 more" must never be read as "open the three
  `Watch` names below". Allocating between candidates needs `rs.ranking_method`, which is `unset`.
- **`account.fx_rate_cad` being unset now has a wider blast radius.** The cap is denominated in R and
  R is base currency, so a CAD position's risk has no expression — `open-position` refuses a `.TO`
  entry, and if one were recorded anyway the book becomes untotallable and **every candidate in every
  later run refuses**. The owner has said setting the rate is worth doing when the time is right; it
  needs a source and an as-of date and is not a value an agent may draft.
- **Track A restarted 2026-08-22.** `pipeline.py` is frozen and the change moves decision output.
  The counter already read 0, so it cost nothing — `DR-015` §3's argument, reused.

## 3. Three things a fresh session must not get wrong

- **`PositionStore.open_risk_as_of` is a RAW PER-CURRENCY SUM.** It adds `Position.open_risk` across
  the book with no FX conversion, and it cannot convert — the dependency law lets that module depend
  only on `platform`. It has never been wrong because no CAD position exists. **Anything that
  compares a book to a limit goes through `portfolio.book`**, which converts each position and
  refuses when the rate is unset. Using the store's number for a new check would re-introduce the
  exact defect closed in sizing on 2026-08-16.
- **The book's R excludes round-trip costs; 1R includes them.** `Position.open_risk` is
  `(entry − stop) × shares` while `sizing.allowed_risk` is spent against `entry − stop + costs`, so
  a book measured in R understates by the cost fraction — small, one-directional, and in the
  **permissive** direction. Left uncorrected deliberately: `ALLOCATION_SPEC.md` §6 rule 6 names
  `Position.open_risk` as the quantity, and inventing a cost-inclusive variant at a call site would
  put a second definition of open risk in the tree. It is an open domain question (`DR-006` §10).
- **The report can be right about the book and still misread.** `result.capacity` holds one
  candidate's verdict, and a refusal is deliberately sticky so an admitted candidate evaluated later
  cannot erase it. That rule has a regression test; if you touch the assignment, read
  `test_a_later_admitted_candidate_does_not_erase_an_earlier_refusal` before deciding it is
  redundant. It was a real defect found in review, not a hypothetical.

## 4. A defect worth carrying beyond its own file

**`tools/track_a_streak.py` printed the deliberate-restart line from the wall clock while the streak
count itself read `SWINGDESK_NOW`.** A test pinned to 2026-08-18 went on passing because the printed
line was reading today's date rather than the one the test had pinned — it agreed with the bug.

Same family as `AGENTS.md` §12's fixture trap and worth stating as its own rule: **when a tool takes
an injectable clock, every read of "now" in it must use that clock — including the ones that only
print.** A partially-pinned tool is a tool whose tests measure the calendar.

## 5. Still on the owner

Nothing below is blocked on code; all of it is in `TODO.md` with the full argument.

- **`DR-016`** — `data.revision_epsilon = 0.001`, price only. Proposed. Its precondition (the
  corporate-actions series) is built, so the gate is one ruling away. `TODO.md` §1 ranks this the one
  to read: an unhandled split makes the system decide on *wrong* information while every freshness
  check passes.
- **`DR-017`** — the ADTV lag, 3 sessions. Proposed.
- **`account.fx_rate_cad`** — see §2. Owner said worth doing; needs a source and an as-of.
- **Register the 19:30 task** — one `schtasks` line, `docs/runbooks/README.md` §1a. Until it exists
  the retry inside the run is live and the second pass is not.
- **`data.staleness_action_threshold`** — still `unset`, still read by nothing. Needs a ruling or an
  explicit decision to retire it.

## 6. Before you start

```bash
git worktree list && git branch -a
```

Three worktrees existed at the time of writing and `HANDOFF.md` §2 carries the generated census.
Run the gates with `PYTHONPATH=$PWD/src`; from a worktree, gates 23 and 24 correctly report
`UNAVAILABLE` rather than passing blind, and `python tools/build_state.py` regenerates the blocks a
worktree *can* see.
