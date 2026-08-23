# Session handoff — 2026-08-23

**Read `HANDOFF.md` first, then `TODO.md`.** This covers only what changed in the session that
built the sector and correlation caps. Delete it once §1 is actioned.

**This file replaces `SESSION-HANDOFF-2026-08-22.md`, whose §1 — build the sector and correlation
caps — is now done.** That file was deleted rather than edited, as its own header instructed, and
its other sections were migrated first: the partially-pinned-clock rule is now `AGENTS.md` §12
(it lived nowhere else), and everything in its §2, §3 and §5 is in `DR-006` §9–§10 or `TODO.md`.

---

## 1. The one thing to do next

**Take the four rulings in `DR-006` §13, or pick the next item from `TODO.md`.** All six of
`DR-006`'s portfolio constraints now reach code, so nothing in that record is blocked on
engineering any more. Two of the four are genuinely the owner's:

- **Should the correlation cap RESIZE rather than refuse?** `RISK_SPEC.md` §4 lists *"correlation
  threshold and its size adjustment"* as one unsupplied input. Only the threshold has a value, so
  the build refuses — the fail-closed reading, and the one `TODO.md` planned. Halving a correlated
  candidate is defensible and needs a number nobody has authored.
- **Is `risk.max_sector_risk` still 2R?** §2 argued it as *one third of the book* against a 6R
  anchor. §8.3 moved the anchor to **4R** and this number did not move, so it is now **half** the
  book. **Measured in §14** at the owner's request: 2R means *at most two of your four in one
  theme* and refuses 11.3% of sampled books, 1.33R means *at most one* and refuses 37.9%, and the
  correlation cap catches only 15% of same-sector pairs — so the two caps are not redundant and
  1.33R would earn most of its refusals from a label rather than a measured relationship. §14.4
  recommends keeping 2R on that argument rather than on §2's. **The ruling is still open.**

The other two are engineering and are small: read `asset_classes` instead of inferring degeneracy
from the weights (one vendor measurement decides it), and decide whether
`tools/refresh_classifications.py` joins the weekend prep task.

## 2. What was built, and the one thing it changes for everyone else

Two caps, in one branch, both at step 6 of `RISK_SPEC.md` §3 and both after sizing.

| | |
|---|---|
| **Correlation** (`DR-006` §11) | `derived_observations/correlation.py` computes it, `portfolio.assess_correlation` spends it. A candidate correlating at or above `risk.correlation_threshold` with any OPEN position gets `Skip` / `RISK` |
| **Sector** (`DR-006` §12) | `reference_data/classification.py` holds and judges the composition, `portfolio.assess_sector` spends it. An ETF consumes its constituents' budget, which is what Appendix C's control cell requires |

**`risk.correlation_lookback_sessions` = 60 is a new parameter**, and finding out why is the most
transferable thing here: `risk.correlation_threshold`'s registry entry carried **two `note:` keys**,
so PyYAML kept the second and silently discarded the first — the one describing the 60-session
window. `DR-006` §7 had asked for the window to get its own entry on principle. It turned out not to
be a principle: the number was not in the loaded registry at all.

**The one thing that changes for a fresh session: the sector cap's input starts EMPTY.**
`swingdesk scan` opens `data/classifications.duckdb`, and nothing fills it until

```bash
python tools/refresh_classifications.py --budget 200
```

has run. Until then every candidate is admitted **unchecked** and the report says so on every run.
That is `DR-006` §3 being obeyed rather than a fault — but the cap protects nothing yet, and
`unchecked` in the SECTOR block is a coverage number to close, not a verdict to read past.

## 3. Four things a fresh session must not get wrong

- **The two failure directions are opposite and look identical from a distance.** An UNSET
  parameter refuses every candidate and names itself. A pair that could not be MEASURED, or an
  instrument that could not be CLASSIFIED, refuses nothing and reports `UNAVAILABLE`. `DR-006` §3
  is explicit that a check the system was never able to perform must not fail closed into a blanket
  refusal, because that stops the system entirely while looking like risk discipline. Both files of
  tests keep the two apart on purpose; if a change makes them behave alike, the tests are what will
  say so.
- **An unclassifiable POSITION is a third thing again, and it is the quiet one.** It refuses
  nothing and makes every per-sector figure an **understatement** — which admits candidates the
  full picture would have refused. `SectorBook.is_complete` and the report's *"the split above
  therefore UNDERSTATES"* line exist for that, and `unmeasured_r` is reported apart from
  `unclassified_r` because they are different gaps.
- **`conftest.make_bars` gives every instrument the SAME closes**, so any two fixture instruments
  correlate at exactly **r = 1.00**. That is convenient for proving a cap bites and useless for
  proving it admits anything. `make_bars(zigzag=True)` is the second path, the two measure about
  **-0.03** apart, and `test_correlation.py` asserts that premise so the admitting tests cannot go
  green for the wrong reason. A test about capacity or ordering that puts a held name on the
  walking path is testing correlation instead, whatever its name says.
- **The degeneracy guard is EXACT, and that is load-bearing.** A fund reporting one sector at
  exactly 1 with every other at exactly 0 is refused — the `NEAR` signature. A tolerance would
  refuse genuine sector ETFs, which are the instruments this cap most needs to see. The known
  weakness is written down in `DR-006` §12.1: a false positive fails toward `unavailable`, which
  ADMITS.

## 4. Still on the owner

Unchanged from yesterday except that `DR-006` has moved off the list and onto §13. All of it is in
`TODO.md` with the full argument.

- **`DR-016`** — `data.revision_epsilon = 0.001`, price only. Proposed; its precondition is built.
  `TODO.md` §1 still ranks this the one to read.
- **`DR-017`** — the ADTV lag, 3 sessions. Proposed.
- **`account.fx_rate_cad`** — needs a source and an as-of. Not a value an agent may draft.
- **Register the 19:30 task** — one `schtasks` line, `docs/runbooks/README.md` §1a.
- **`data.staleness_action_threshold`** — still `unset`, still read by nothing.
- **`DR-006` §13** — the four above.

## 5. Before you start

```bash
git worktree list && git branch -a
```

Run the gates with `PYTHONPATH=$PWD/src`; from a worktree, gates 23 and 24 correctly report
`UNAVAILABLE` rather than passing blind, and `python tools/build_state.py` regenerates the blocks a
worktree *can* see.

**Track A restarted 2026-08-22 and this change moves decision output again.** `pipeline.py` is
frozen under `DR-015` §3, so the counter resets — it already read 0, so this costs nothing, the same
argument `DR-015` §3 made and `DR-006` §9 reused. Derive it with `python tools/track_a_streak.py`
from the MAIN checkout; never from a line in a document.
