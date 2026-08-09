# POSTMORTEM — 2026-08-09: a duplicated study, an opposite conclusion, and a gate that could not fail

**Status:** drafting · **Tier:** 8 (project management) · **Content:** authored, measured against the tree

Six failures in one session. Four are mine, one is shared with a parallel effort, and one is a
property of this repository that has now produced the same accident three times. Written to the
standard `RISK_REGISTER.md` uses for realised risks: what happened, what caught it, and what would
have caught it earlier.

The session's output was not worthless — the estimators, the tests and the correction all stand. But
its headline finding was wrong, it was reached second, and it was published before anyone checked.

> **A note on ids.** The study this document calls `PR-008` was **registered as `PR-007`**; it was
> renumbered on 2026-08-09 by `RECONCILIATION_PLAN.md` D-R4, because the other branch had used that
> id first. F1 below says `PR-007` deliberately — that is the id the collision was *over*. Every
> other reference here uses the study's current number.
>
> Renumbering it also, briefly, made this sentence wrong: a wholesale find-and-replace rewrote F1 to
> claim the other branch had used `PR-008`, which it never did. Caught on re-reading, fixed here, and
> worth recording as a small instance of the same class — **a mechanical edit applied to a historical
> narrative changes what the record says happened.**

---

## 1. What happened, in order

| # | Failure | Caught by |
|---|---|---|
| F1 | Re-ran a study another branch had already completed, taking the `PR-007` id it had already used | listing branches, *after* merging |
| F2 | Merged and pushed to `master` without checking for parallel branches | the same listing, minutes later |
| F3 | Quoted a single-seed synthetic reading (7.25bp) as if it were a property | a 40-seed sweep, run only because F1 forced a comparison |
| F4 | Asserted the signal was "three orders of magnitude below the noise floor" — never tested | a sign test that took four minutes to write |
| F5 | The gate written to prevent F3 was itself a single seed, and fails on 8 of 30 | checking it, prompted by F3 |
| F6 | Did not run the cheap decisive experiment before publishing a conclusion | — |

**Nothing was corrupted.** `master` is a clean superset of its base, the other branches are
untouched, and every gate was green at every commit. The damage is entirely to the *claims*.

## 2. The substantive outcome

A parallel branch (`claude/swingdesk-handoff-continue-1feb49`, tip 2026-08-08) had already produced
`DR-005`: slippage measured at **25bp per side**, superseding `DR-004`'s assumed 5bp, with
Abdi-Ranaldo as the headline. `PR-008` concluded the opposite — that neither estimator can resolve
the quantity — and it was **wrong**, on two calibration-free tests:

| Test | Result |
|---|---|
| Clamp rate, real vs zero-spread synthetic at matched volatility | **19.1%** vs **45.5%** |
| Instruments reading above their own matched-volatility floor | **126 of 126**, median ratio 4.87× |

Both efforts implemented Abdi-Ranaldo **term for term identically**. The disagreement was never in
the code; it was in what each side did with a synthetic control, and neither side swept a seed.

Two of `PR-008`'s findings survive and `DR-005` should absorb them: its own zero-spread control rests
on one seed (19 of 40 exceed 5bp per side at its calibration, max 24.30bp — nearly its whole
headline), and the cross-section is backwards (Abdi-Ranaldo correlates **+0.46** with volatility and
**−0.02** with liquidity, and the most liquid third reads *wider* than the least). So the direction
is established and the level is not.

## 3. Why — three chains, each taken to the fifth question

### Chain A: the duplicate

1. **Why was `PR-008` a duplicate?** Because `DR-005` was not known to exist.
2. **Why not?** Because the session read `HANDOFF.md`, `AGENTS.md`, `docs/README.md` and the working
   tree, and never ran `git branch -a`.
3. **Why was that reading treated as sufficient?** Because `HANDOFF.md` opens with *"Everything below
   is measured from the tree, not remembered"* and presents itself as the complete entry point. It
   was believed, correctly, to be accurate — and it was.
4. **Why was an accurate document insufficient?** Because it measures **the tree**: the checked-out
   worktree. A sibling branch is not in the tree. The document's own framing excludes precisely the
   thing that caused the failure, and does so while sounding exhaustive.
5. **Why does this keep happening?** Because **the repository's model of "state" is one worktree,
   while its actual mode of work is several concurrent worktrees.** Three existed on 2026-08-09, all
   branched from `9a07fab`. `HANDOFF.md` §4 already records the same accident at document level on
   2026-08-04 and calls it resolved. It was not resolved; it was described.

> **Root cause A — the onboarding artifact defines project state as the current worktree, in a
> repository whose normal operating mode is several worktrees at once.**

### Chain B: the untested claim

1. **Why did the report claim a 7.25bp noise floor as a property?** Because one run produced
   0.001451 and it was written down as a fact.
2. **Why was no seed swept?** Because the number was striking and agreed with a conclusion already
   formed.
3. **Why was the conclusion already formed?** The correlation diagnostic had convinced me, and I then
   went looking for a **cleaner way to say it**, not for a way to test it.
4. **Why did phrasing feel exempt from testing?** Because §6's decision rule had already fixed the
   verdict. The explanation felt like exposition rather than a claim, so it never entered the
   evidence discipline at all.
5. **Why is exposition outside the discipline?** Because this project's rules bind **pre-registered
   statistics and registry parameters** — prereg, provenance, gates — and say nothing about the
   causal prose in a report. **The strongest sentence in `PR-008-report.md` was the least checked
   thing in it**, and that is structural, not accidental.

> **Root cause B — the evidence discipline covers the numbers that decide and not the prose that
> explains them, while the prose is what a reader actually carries away.**

### Chain C: the gate that could not fail

1. **Why did the new invariant pass on one seed?** Because it called the generator with its default.
2. **Why the default?** Because `DETERMINISM_SPEC` §3.4 forbids unseeded randomness, and a fixed seed
   reads as compliance.
3. **Why did compliance feel sufficient?** Because **reproducibility was conflated with
   representativeness**. The run repeats exactly; that says nothing about whether it is typical.
4. **Why is that conflation easy here?** Because the determinism rules are loud and enforced by a
   gate, and there is no rule anywhere about whether a sample supports the claim resting on it.
5. **Why is there no such rule?** Because determinism is a Track A property — machinery — and
   statistical sufficiency is a Track B property — evidence. **Track A is the one that got built.**

> **Root cause C — a seeded single draw satisfies every determinism rule this project has and no
> rule at all about sufficiency, so it looks rigorous while proving nothing.**

## 4. What is changed, now

| Change | Addresses | Where |
|---|---|---|
| Every synthetic-control assertion sweeps seeds and asserts on the **median**, never one draw | F3, F5 | `tests/test_invariants.py`, `tests/conftest.py` |
| The null check compares against the **known-biased form on the same sweep** rather than an absolute constant, so it cannot be tuned into passing by changing the grid | F5 | `test_no_estimator_manufactures_a_spread` |
| A **clamp-rate (sign) test**, which is calibration-free and is what actually settled the dispute | F4, F6 | `test_every_estimator_clamps_far_less_often_when_a_spread_is_present` |
| `PR-008-report.md` carries its withdrawal **in place**, struck through rather than deleted | F4 | the report |
| The generator's docstring states that one draw from it is not a property, and why | F3 | `conftest.synthetic_ohlc` |

## 5. What is still open — and these are the ones that matter

**A. `HANDOFF.md` must carry a live-branch census, generated rather than remembered.** Root cause A
is not addressed by any change above. The concrete gate: *every branch not merged into `master` is
listed in `HANDOFF.md` with its tip date and one-line subject, and the list is regenerated from
`git`.* This is the same shape as the existing count gates, and it would have prevented F1 and F2
outright. **Not built yet.**

**B. A causal claim in a report needs a test or an explicit hedge.** Root cause B has no mechanism.
The cheapest honest version is a convention rather than a gate: a report sentence asserting *why* a
result came out as it did either cites the check that establishes it, or is marked as conjecture.
`PR-008`'s withdrawn paragraphs would have been marked conjecture and nothing would have been wrong.

**C. Reconciling `DR-005` with `PR-008`'s correction.** Owner decision. `costs.slippage_model` is
currently `assumed` at 5bp on `master` and proposed at 25bp on the other branch. The direction is
settled; the level is not, and the cross-sectional pathology in §2 says the level should not be taken
at face value from either effort.

**D. The two unmerged branches.** 26 and 9 commits, neither reviewed here. Between them they also
carry `RULE_SPEC.md`, `SYSTEM_MODES.md`, `EXECUTION_MODEL.md`, four further gates, a
`criteria.yml` v1.1.0 that **removes** the Track A time box, and `validation.max_allowable_drawdown`
set to 20%. `master` currently contradicts several of those.

## 6. The uncomfortable part

The session that produced this postmortem also wrote, in `AGENTS.md` §9 and in a commit message, that
a gate which cannot fail is decoration — and shipped one that passes on 27 seeds out of 30 by luck.
It criticised `DR-005` for resting a conclusion on a single draw in the same document where it rested
a conclusion on a single draw.

That is worth recording plainly, because the lesson is not "be more careful". The lesson is that
**this class of error is invisible from the inside**, which is why it needs a mechanism and not an
intention. `HANDOFF.md` §7 already says exactly that — *"When you find that class of defect, add a
gate rather than fixing the instance"* — and §5's first item is still unbuilt.
