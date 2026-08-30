# CI POLICY

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored

An architecture rule that is not executed is decoration (`DEPENDENCY_LAW.md`). This lists every gate
that must pass to merge, and what each one exists to catch.

---

## 1. Gates

Ordered fastest-first, so a cheap failure does not wait behind an expensive suite.

| # | Gate | Catches | Status |
|---|---|---|---|
| 1 | `verify_parameters.py` | a value without provenance; `assumed` without a citation; a parameter with no course reference; a `read_by` that does not resolve | **exists**. Prints two standing measurements it does not fail on: values no code reads, and — added 2026-08-25 — **values resting on a decision record still `proposed`**. Check 5 required the citation to RESOLVE; nothing asked whether the record was ever accepted, and both halves of the cost model were on the second list |
| 2 | `verify_transcription.py` | a `verbatim` block that no longer matches its source; an enum drifting from its spec | **exists** |
| 3 | `build_course_index.py --check-only` | the course index no longer extracting to its known shape | **exists** |
| 3b | `build_frd.py --check-only` | the FRD drifting from the registry it is generated from | **exists** |
| 3c | `build_components.py --check-only` | a generated component field hand-edited; the registry going stale against the course | **exists** — 465 rows |
| 3ci | `build_coverage.py --check-only` | the coverage matrix drifting from the registries it is counted from | **exists** — ТЗ §5, generated rather than authored |
| 3d | `build_checklists.py --check-only` | the checklist registry drifting from the transcription it is parsed from | **exists** — 84 items |
| 3e | `verify_docs.py` | a document citing a spec, parameter or component id that does not exist; a status outside the ladder | **exists** — caught 4 dangling references on its first run, one of them cited by three documents |
| 3f | `verify_studies.py` | a report with no pre-registration; the prereg index disagreeing with the report it points at; a `validated:` parameter citing a study that did not ACCEPT; a `\| Studies \|` row whose numbers do not match the reports on disk | **exists** — caught `the study census, 3 refuted` quoted in five documents against three reports with two REJECTs |
| 3g | `verify_criteria.py` | a criterion in force referencing a parameter with no value; a reference to a parameter or criterion that does not exist; a status outside the ladder | **exists** — the narrow half of `REQ-VALIDATION-001` |
| 4 | `ruff` | unused imports, naive datetimes, blind excepts, import order | **exists** — 10 rule families, chosen deliberately |
| 5 | `mypy --strict` | type errors | **exists** — clean over `src` **and over the checking machinery**: every `verify_*`, every `build_*`, `check_gates.py` and `track_a_streak.py`. **Widened 2026-08-30, and the job was small because of one missing file rather than because anyone annotated a hundred lines**: `src/swingdesk/py.typed` did not exist, so mypy treated this project's own fully-typed package as untyped the moment a tool imported it — the checker was blind at the one boundary where a tool meets the system. The research runners are still out, see §7 |
| 6 | `lint-imports` | a package importing across a layer or forbidden boundary | **exists** — 4 contracts. Caught a reversed layer order on first run |
| 7 | `verify_no_wall_clock.py` | `datetime.now` / `date.today` / `time.time` in `derived_observations`, `decision_logic`, `trade_management`; **and any date literal anywhere in `src/`** — a constructed `date(2026, 8, 25)` or an ISO string constant (`REQ-DATA-001`) | **exists** — AST-parsed, not string-matched, so a mention in a docstring does not trip it. **Moved out of `check_gates.py` into its own tool 2026-08-25**: while it was an inline function it could not be pointed at a fixture, so it was the one gate of this repository's own making with no failure test — and the audit that closed that class derived its list by grepping `tests/` for each `tools/verify_*.py`, which is a list gate 7 could not appear on |
| 7b | `golden.py` | a component's output changing without its version and vectors changing with it | **exists** — count in `HANDOFF.md` §2 |
| 8 | `pytest` | unit, property and golden-vector tests | **exists** — fully offline |
| 9 | determinism replay | a stored manifest no longer reproducing its `output_hash` | **exists** — 1 case, 4 instruments covering all four decision branches |
| 10 | traceability | a course id with no requirement row, a requirement with no test, a spec id cited by no test | to build |
| 11 | `verify_components.py` | `implements` not injective; an `active` component missing `implements`/`verification`/`spec`; a dangling parameter reference; an `active` component with an `unset` parameter; an `implements` pointing at a symbol that does not exist; a non-Definition topic with no row | **exists** — caught two components sharing one function on its first run |
| ~~12~~ | ~~`verify_criteria.py`~~ | **RETIRED — this number was resolved to 3g on 2026-08-09** and the row survived the resolution. `RECONCILIATION_PLAN.md` §4 item 6: three things claimed "Gate 12" — two tool docstrings and this row — and the two prose citations meant *different* gates. Both docstrings were corrected that day; this row was not, and read **exists** for seventeen days over a number nothing runs. `check_gates.py` has never registered a 12. Struck rather than deleted: a row that said a gate existed when it did not is worth more visible than absent (`AGENTS.md` §10.5) | ~~exists~~ — **never registered**; 3g is the gate |
| 13 | `verify_study_summary.py` | a document stating a study count that the result files do not support | **exists** — caught six places overstating both the number of studies run and the number refuted; the census is derived from result files carrying a `prereg` id and a `verdict` |
| 14 | `verify_counts.py` | a hard-coded parameter, component, gate, test, document or vector count that has drifted from the registries | **exists** — caught eight stale counts on its first run, including one conflating 465 catalogued components with 458 `registered` · **Widened 2026-08-30, and the measurement is the reason it is narrow elsewhere**: the component activation states are now read without backticks when the word *component* appears on the line, and `TODO.md` is scanned for the status keys only. Both were measured first — one guarded hit across every tracked document, and it was real drift, against zero false positives. The 2026-08-24 probe that rejected this file outright stands: all of its noise came from the tests/gates family, which stays out of scope here, and a test asserts that it does |
| 17 | `verify_dependencies.py` | a third-party module imported anywhere in `src/` that no declared dependency provides — at any nesting depth, so a function-level import is caught | **exists** — written after `yfinance` survived the whole gate suite undeclared; caught `pandas` on its first run |
| 18 | `build_lock.py --check-only` | `requirements-lock.txt` drifting from what the declarations resolve to | **exists** — the file it replaced held 8 entries against 56 installed, and was referenced by nothing |
| 16 | `verify_branches.py` | a parallel worktree missing from `HANDOFF.md` §2 | **exists** — and until 2026-08-10 it excluded the tree it ran in rather than the main checkout, so it answered differently depending on where it was invoked |
| 15 | `verify_project_manifest.py` | the document index drifting from the tree: a duplicate id or display number, a path that does not exist, a status contradicting the document's own header, a row with no manifest entry, or a document in no index at all | **exists** — caught three specifications marked `planned` that were written, and two never indexed |
| 19 | `verify_secrets.py` | a tracked secret, or a `.gitignore` claiming to exclude a path it does not | **exists** |
| 20 | `verify_decisions.py` | an accepted decision record that names no implementation and does not say `implementation: none` — **caught a false implementation claim on its first run** |
| 21 | `verify_worktree_clean.py` | finished work left uncommitted. Advisory |
| 22 | `verify_directory_policy.py` | the directory collector's network limits living anywhere but the committed policy - a source URL, byte cap, timeout or retry budget as a literal in `tools/fetch_directory.py`, or a policy missing one of the keys `DR-008` names | **exists** - `DR-008` was ratified 2026-08-10 requiring *"one committed machine-readable policy ... merge-gated"*, and both halves were missing until 2026-08-25. Read from the syntax tree, so the gate never imports or runs the collector. **A limit in a literal is changed by editing a line; a limit here is changed by a commit a reviewer sees** - the *new human decision* `DR-008`'s rejected-alternatives table exists to force |
| 23 | `track_a_streak.py` | the `a.run_completes` streak being hand-kept. Advisory, and `UNAVAILABLE` without `data/` — **the counter it replaced read 3 against a computed 4** |
| 24 | `build_state.py --check-only` | `HANDOFF.md` §2 being typed rather than generated. `UNAVAILABLE` for the blocks a given checkout cannot see |
| 25 | `verify_prereg_conformance.py` | a reported verdict that does not conform to its own pre-registration — **caught `PR-002` reaching an affirmative verdict having run only one of the three perturbations it declared** |
| 26 | `verify_schedule.py` | a scheduled task missing, disabled, or whose last COMPLETED run crashed. Advisory, and `UNAVAILABLE` off the scheduling machine — **added after `TODO.md` carried "register the 19:30 task" for five days after it was registered**. `Last Result` carries a `SCHED_S_*` status rather than an exit code while a run is in flight or before the first one; those are reported and not judged, after the gate called a healthy mid-run pass a crash on 2026-08-24. **A known FAILURE code is now named rather than printed as a number** (2026-08-30): `0x80070420` is the second pass finding the first already running on a catch-up day. The verdict is unchanged and still red - naming a cause is not fixing one, and the scheduling decision stays the owner's |
| 27 | `verify_cards.py` | a strategy card claiming more than it has: a component or parameter reference that does not resolve, `Validated` without an evidence id, or an `unset` input missing from `blocked_by` |
| 28 | `verify_parameter_claims.py` | a document stating a parameter status the registry contradicts — **six live on the day it was written, every one a parameter that gained a value while the prose still called it `unset`** |
| 29 | `verify_prereg_ids.py` | a study document missing from its own index, an id reserved by reference only, or two **unmerged** branches numbering different studies the same — `AGENTS.md` §10.2 as a check rather than a habit. **In CI the third check cannot run** (a shallow clone has no other branches) and the gate prints that it did not, so a green 29 on GitHub is not evidence about collisions |
| 30 | `verify_rules_home.py` | a rule recorded anywhere but `AGENTS.md`. A heading declaring an owner instruction outside it must name the section that carries the rule, or mark itself `one-off` — **added after the owner asked whether rules could end up in a second place; they had not, and nothing made it so** |
| 31 | `verify_commands.py` | a document telling a reader to run a command the tool would reject: a tool that does not exist, a flag it does not declare, or a flag it declares `required` that the command omits | **exists** - caught `HANDOFF.md` section 2's own **generated** census naming a command that exits 2, and the two documents that had copied it from there. **A broken command propagates exactly like a stale count**, and neither gate 3e (references) nor gate 24 (numbers) reads a command line. Static - `add_argument` calls are read out of the syntax tree, so a gate about running commands runs none, which is also its limit: it proves the ARGUMENTS are accepted, never that the command succeeds. A line naming a command SHAPE rather than an invocation marks itself with a `partial-command` comment, a claim the author makes on the record rather than one the gate infers |
| 32 | `verify_checklist_blockers.py` | a pre-trade checklist item whose stated blocker has since been supplied. Each `UNAVAILABLE` evaluator pins the registry statuses its reason rests on, and the gate goes red when one moves — **written for `entry.maximum_entry_atr`, which `DR-020` created `unset` and two items (`E08`, `E09`) wait on**. Two reasons rest on a missing capability with no registry row to pin; the gate names those every run rather than passing over them |
| 33 | `verify_sibling_edits.py` | two live branches rewriting the same lines. Overlaps are computed in **merge-base coordinates**, so a hit means both trees changed the same original text rather than merely the same file. Advisory, and **it did not run in CI** — a shallow clone has no sibling branches and it says so — **written the day gate 16 was green and two trees corrected the same two table rows two hours apart** |
| 34 | `verify_invariant_tests.py` | an enforcement the tree CLAIMS that cannot fail. It copies `src/` to a scratch tree, applies one committed mutation per claim, and requires a named test to go red — the mutants are listed in the tool and counted by it, over `INVARIANTS.md` §1 (7 of the 9 invariants) and `REQ-VALIDATION-001` (the 5 vetoes that evaluate on the live path, each forced to admit everything, which is TradAlert's `if is_long: return True`). **Written after the test named for invariant 1 was found to assert `(net / x) * x == net`**, an identity that held whatever the denominator contained. A mutation site that no longer matches is a failure rather than a skip, and what is uncovered is named on every run |
| 35 | `verify_cited_tests.py` | a document naming a test the suite does not define. `INVARIANTS.md` §1 and `REQUIREMENTS.md` §7 both argue enforcement by naming a test, and a reader takes the name as proof; renaming a test is ordinary work no other gate would notice. Gate 28's shape aimed at a different subject. **23 names cited, 0 unresolved on the day it was written** — prevention rather than repair. Append-only stores are excluded and a line marked as history is left alone |
| 36 | `verify_gate_inventory.py` | this table and `check_gates.py` disagreeing about which gates exist. Three exact checks — every registered gate has a row, every row claiming to exist is registered, no number is claimed twice. **Written after row 12 read `exists` for seventeen days over a number that has never been registered**, having survived the 2026-08-09 reconciliation that corrected the same claim in two tool docstrings. A row marked `to build` or struck through claims nothing and is left alone |
| 37 | `verify_rules_index.py` | `AGENTS.md`'s rule index drifting from the rules it lists. Every numbered section has exactly one row, every row points at a real section, and every gate number cited is registered. **Written 2026-08-25 on owner instruction to separate the rules from the prose** — after a session broke two owner instructions it had read while building five gates that catch other things. It does not check that a row DESCRIBES its section: that is prose against behaviour, and the `honour` column is an honest claim rather than a verified one |
| 38 | `verify_gate_citations.py` | a document naming a gate number that neither the runner registers nor this table lists. Gate 36 closes the two places a gate is DEFINED; this closes the ~130 documents that CITE one, which is where a reader actually meets a gate number and reads it as protection. **Written out of row 12**, which said `exists` for seventeen days over a number nothing runs. The vocabulary is deliberately THIS TABLE and not the runner: a row marked `to build` still makes the number citable, which is why the twenty-odd honest references to the unbuilt gate 10 are not findings. Measured before building - 363 citations, 0 unresolved, so prevention rather than repair - after excluding two forms that are not gate ids at all: a four-digit number, and a number followed by a hyphen. Both came from one real false positive, a date |

### Three states, not two

A gate reports `PASS`, `FAIL`, or **`UNAVAILABLE`** — the last meaning its subject is not present
in this environment. Gates 2 and 3 re-extract the owner's 116 course PDFs, which are the
requirements source and are not in the repository, so those two cannot run in GitHub Actions. The
choice was a permanently red CI, a `--skip` flag, or naming the state.

The vocabulary is the project's own: `HANDOFF.md` §8, *a gap in the system and a fact about the
trade are different claims, and collapsing them is the most damaging error this product can make*.
An unavailable gate has **not** passed. The runner counts it separately and never prints
*all gates pass* when one did not run.

Two things stop it becoming a skip flag under another name. Only gates named in
`check_gates.py`'s `MAY_BE_UNAVAILABLE` may report it — any other gate exiting 4 is a `FAIL` —
and the owner's machine has the PDFs, so locally every gate still runs. CI is the weaker
environment and says so, rather than CI and local quietly diverging.

### Inventory

Everything except 10 runs today via `tools/check_gates.py` — the table above is the inventory,
and the count belongs to `HANDOFF.md` §2 rather than to a second hand-maintained sentence here.
Gates 2, 3 and 3f are
stdlib-only; the rest need the project venv (`pip install -e ".[dev]"`).

Gates 7b and 9 are also asserted from `pytest`, so a bare `pytest` run is not silently weaker than
CI. The duplication is deliberate — they are the two gates whose subject is *change over time*, and
they are the ones a developer is most likely to run without.

## 2. What each gate protects

Not busywork — each maps to a specific way this project could quietly go wrong:

| Gate | The failure it prevents |
|---|---|
| 1 | a guessed threshold acquiring the authority of a measurement |
| 2 | documents drifting from the course while still claiming to transcribe it — **already caught two real errors** and two undeclared sources |
| 3 | an extraction change silently altering the component catalogue |
| 6 | a strategy fetching its own facts; an indicator owning a decision; the journal being written from a pure layer — **caught a reversed layer order on its first run, and forced `application` out of `presentation` on its second** |
| 7 | reproducibility breaking invisibly — one hurried commit is enough |
| 7b | a behaviour change slipping in unversioned; and, via the file hashes, the cheaper failure of pasting whatever the code now prints into the expected values |
| 9 | non-determinism entering the decision path — **caught `config_hash` covering only which parameters were set, so a changed threshold would have been reported as a determinism defect** |
| 4 | a wall-clock call or an unused binding surviving review. Both are invisible in a diff and neither is caught by a test that happens to pass |
| 5 | a declared type and the real contract drifting apart. **Caught the `Fetcher` alias describing positional arguments while every call site passed `period` by keyword** |
| 3e | a document asserting something about the system that stopped being true. Every defect of this kind found by hand so far read as correct — a stale claim does not look like a bug |
| 3f | the summary of the evidence drifting from the evidence. Gate 3e cannot see it, because every reference in the wrong sentence resolves; only recomputing from the reports does |
| 3g | a safeguard that cannot fire. A ratified criterion whose threshold is unset reads as protection and provides none, and nobody looks for a second one. **The rationale is not hypothetical** — TradAlert's R:R gate was `if is_long: return True` and passed seven audits; this tree's version was `k.drawdown_pause` ratified against an `unset` threshold. Both are valid, referenced and incapable of ever changing a verdict *(merged here from the retired row 12, 2026-08-25)* |
| 3ci | a coverage claim drifting from what is actually covered. The ТЗ forbids claiming coverage without a formal basis, and a hand-maintained matrix of counts is the most rot-prone document a project can own |
| 10 | a course requirement being dropped without anyone noticing |
| 11 | two implementations of one component — the thing §3.8 forbids and import analysis cannot see, because both imports are perfectly legal. **Caught `M12-T0201` and `M12-T0202` both claiming `pivots:compute`**, which a linter would never question |
| 13 | the evidence base looking larger, or more negative, than it is. The count that prompted this claimed *more* refuted studies than existed and was quoted in `RISK_REGISTER.md` as the project's central risk |
| 14 | a number that was right the day it was written. Counts had been reconciled by hand three times, and each pass found what the last careful read missed — the defect class that does not look like one |
| 15 | the map ceasing to describe the territory. An index is read as an inventory, so a document it calls `planned` is assumed absent and one it omits is assumed not to exist — both were true here, and neither is visible from inside the index |
| 19 | a credential reaching the history, where removing it means rewriting every commit after it |
| 20 | a ratified decision that reaches no code. A decision nobody implemented is a decision that did not happen, and nothing else in the tree can see the difference |
| 21 | work that is finished, green and only on one machine |
| 23 | a hand-kept counter agreeing with itself. The number is the ratified Track A criterion, and the document that owned it was wrong about it |
| 24 | the single owner §10.5 established being typed by hand — which is drift that no second copy is left to contradict |
| 25 | a study's runner drifting from its own registration. `PR-002` reached an affirmative verdict over a declared scope shortfall and every other gate stayed green |
| 26 | a claim about the machine that no gate could check. Two documents here disagreed for five days about whether a scheduled task existed, and the stale one was the one being acted on |
| 27 | a card that reads as runnable while depending on a value nothing has set — the "specified, wired to nothing" shape one layer up from the components it cites |
| 28 | prose drifting from the registry. Gate 1 checks the registry against itself and against the code; nothing checked the SENTENCES, and a stale `unset` is the exact claim a reader acts on |
| 29 | two efforts numbering different studies the same. `POSTMORTEM-2026-08-09.md` root cause A: each tree was internally consistent, so nothing in either could see it |
| 32 | a reason for not knowing something outliving the thing that caused it. `Trade` is unreachable because eight checklist items cannot be answered; the day one of their blockers is supplied and the sentence still says otherwise, the flow stays stalled for a cause that no longer exists and re-reading eight prose strings by hand is what would have caught it |
| 33 | the duplicated-effort half of `POSTMORTEM-2026-08-09.md` root cause A, which gate 16 does not reach. Knowing a sibling worktree EXISTS is not knowing it is rewriting the paragraph you are about to rewrite, and its commit subjects will name its other work |
| 34 | the test suite claiming an enforcement it does not provide. Gate 8 says the tests pass; nothing said they could fail. `INVARIANTS.md` §1 asserted *"seven of nine are enforced by a test that would fail if the invariant broke"* while one of the seven was an identity — and the document, not the test, is what a reader trusts. `REQ-VALIDATION-001` exists because TradAlert's R:R gate was `if is_long: return True` and passed seven audits |
| 35 | the evidence for an enforcement quietly ceasing to exist. Gate 34 proves a named test can fail; nothing proved the name still resolved, and a document that cites a deleted test reads exactly like one that cites a live one |
| 36 | the map of the mechanisms drifting from the mechanisms. Every other gate protects the tree; this one protects the list a reader consults to learn what is protected, which nothing else could see |
| 37 | the one page a working session actually holds in mind going stale. A rule added to the rulebook and not to the index is a rule nobody reading the short list will follow — and the short list exists precisely because nobody re-reads 650 lines mid-task |

## 3. Merge rules

- **All gates pass, or no merge.** No "fix it in the next commit".
- A gate that is wrong gets **fixed or removed**, never skipped. A routinely-bypassed gate is worse
  than no gate: it teaches the operator that red is normal.
- **Golden vectors changing is a blocking failure** unless the commit also contains the decision
  record explaining the behaviour change and a component version bump
  (`COMPONENT_REGISTRY_SPEC.md` §6).
- Adding a `verbatim` document requires its `verbatim-sources` declaration in the same commit,
  otherwise gate 2 silently skips it. **Gate 2 only checks documents that opt in** — that is its one
  weakness and it is worth stating.

## 4. What CI must never do

- **Touch the network.** Vendor responses are recorded fixtures; a suite that fetches is neither
  deterministic nor available offline, and it would hammer a rate-limited free tier.
- **Write to the real data store.** Fixtures only.
- **Depend on the current date.** A suite that passes today and fails in January is a suite that
  will be disabled in January.

That third one deserves emphasis given this project's subject matter: half-days, holidays and
month-end are exactly the conditions where date-dependent tests break, and they are also exactly the
conditions the system must handle correctly.

## 5. Local equivalence

Every gate runs locally with one command, and the CI definition calls the same script it does. If
the two can disagree, the local run stops being trusted and the feedback loop lengthens to a push.

```bash
python tools/check_gates.py
```

There is deliberately no `--skip` flag.

## 6. What the gates have actually caught

Kept as a record, because the argument for a gate is empirical and this is the evidence:

| Gate | Caught |
|---|---|
| 2 | two real transcription errors, and four documents citing sources they had not declared |
| 6 | `reference_data` placed above `market_data`, which would have let calendars import bars |
| 6 | the pipeline sitting in `presentation`, unreachable by the replay harness that needs it |
| 9 | `config_hash` hashing set-ness instead of values |
| 9 | a replay fixture whose bars had constant true range, making it blind to the ATR period |
| 11 | swing high and swing low sharing one function, so `implements` could not say which component a symbol served |
| 4 | **`date.today()` in the pipeline's completeness window.** On the empty-bars branch the run measured completeness against the wall clock instead of its own pinned clock, so a replay of an old manifest would have used the date of the replay. Gate 7 could not see it — `application` is not one of the pure packages it guards |
| 5 | **`ExitDecision(exited=True)` constructible with no price and no reason**, which would have produced a Trade with a None exit price. The invariant now lives in `__post_init__` |
| 5 | the `Fetcher` type declaring four positional arguments while every caller passed `period` by keyword |
| 3e | **`INVARIANTS.md` cited by three documents and never written** — `TEST_STRATEGY.md` described it as "not prose to be read", `RISK_SPEC.md` and `SCREENER_SPEC.md` deferred to it. Writing it surfaced that invariant 4 is enforced by a function signature rather than a test, and that `DETERMINISM_SPEC.md` §7 claimed general shuffle-invariance coverage while testing one component |
| 3e | `RECONCILIATION_SPEC.md`, cited by `FAIL_CLOSED_POLICY.md`'s safety row and never written |
| 3g | **`k.drawdown_pause`, ratified since 2026-08-02 with `validation.max_allowable_drawdown` unset.** Found by hand on 2026-08-03 and closed on 2026-08-08 by the **owner** setting 20 percent of equity, not by `DR-007` — that record proposed −15R and the 2026-08-09 reconciliation superseded it (corrected here 2026-08-25). The gate exists so the next one is not found by hand. Mutation-checked on all three of its checks, including the quiet one — a typo in a criterion's `status` would exempt it from the parameter check, so the ladder is verified before anything else |
| 3f | **`the study census, 3 refuted` in five documents.** The census belongs to `HANDOFF.md` §2 and is derived by `python tools/verify_study_summary.py`; the point here is the failure shape, not the figure. One "study" is a post-hoc survivorship bound carrying no verdict at all. The evidence was right and every summary of it was wrong, in the direction of overstating how much had been tested. **The gate caught this class again on 2026-08-24**, when filing a new pre-registration exposed four documents still quoting the previous total — three of them spelling it in words, which gate 14 cannot see |

Two of these deserve a note. The constant-true-range fixture was the useful kind of failure — the
gate was green, the fixture was wrong, and only trying to make the gate fail on purpose revealed it.
The shared `pivots:compute` is the other kind: a gate finding a real defect the first time it ran,
before anyone had a chance to trust the thing it was checking.

## 7. Open items

- [x] ~~Choose the runner.~~ **DONE 2026-08-10 — GitHub Actions, `.github/workflows/gates.yml`.**
      The argument for staying local was that a single-user offline-first project is well served by
      a script; what settled it against was that the gates then only ever attest to the developer's
      machine. `master` carried **zero commit statuses**, so "all green" described a habit, not the
      published commit — and the first run proved the point by finding a gate-16 crash that cannot
      occur in a working tree, because `git branch --merged master` needs a local `master` and a
      runner checkout has none.

      **`master` is protected as of 2026-08-10**: required check `gates`, `enforce_admins` on, no
      review requirement — there is no second reviewer to require (`RISK_REGISTER.md` B-1) — and
      force-pushes and deletions refused.

      **The workflow consequence, stated plainly:** a new merge commit onto `master` has no check
      yet and will be refused until one reports. Fast-forwarding `master` to a commit that is
      already green passes; so does a pull request, where the check runs on the merge result. This
      binds the owner too, which is the point of `enforce_admins` in a project whose founding
      premise is that the failures happen upstream of the code.
- [ ] **Gate 10 (traceability) is still not wired**, and the reason moved on 2026-08-25.
      ~~It would pass vacuously today. Its strongest available check is "every `active` component
      has a test", and there are **zero** `active` components~~ — derive the count from
      `HANDOFF.md` §2 rather than from here; ATR activated and it is no longer zero. **The current
      reason is different and is recorded in `TODO.md` §6:** the check "a requirement with no test"
      would fire immediately on the requirements that are deliberately NOT met, and what it needs
      first is `REQUIREMENTS.md` §7 — written 2026-08-25 — which pairs each requirement with the
      test or gate that would go red, or states that nothing would. The rest of this item still
      stands — five are blocked on an unset parameter, which is the
      fail-closed design working. A green gate that asserts nothing trains the operator to
      trust it. It lands with the first `active` component.
- [ ] ~~**`mypy --strict` covers `src` only.**~~ **It covers the checking machinery too as of
      2026-08-30** — every `verify_*`, every `build_*`, `check_gates.py`, `track_a_streak.py`.
      What is still out is the research runners (`run_pr*`, `measure_*`, `probe_*`).

      **What made it cheap, and it is the finding rather than the annotation work.**
      `src/swingdesk/py.typed` did not exist. Without that PEP 561 marker mypy treats this
      project's own fully-typed package as UNTYPED the moment it is imported from outside `src/`,
      so every tool got `Any` for every symbol it imported from `swingdesk`. **142 of 247 errors
      were that one fact repeated**, and the count is the least of it: the checker could not see
      the one boundary where a tool meets the system, which is precisely where a wrong argument is
      written. Adding the marker took the total to 113 and raised `arg-type` from 7 to 16 — nine
      real argument errors that had been invisible.

      **It found one thing on its first run that review could not.** `verify_reproducible.py`
      declared `hashes: list[str]` and appended `manifest.output_hash`, which is `str | None`. Two
      passes that produced NOTHING compare `None == None` and would have printed *byte-identical
      output* as evidence for `a.reproducible`. Latent rather than live — `run()` has exactly one
      exit today and always sets the hash — and now guarded, because the comparison was unprotected
      against a state its own type declares.

      **Two sites this row named as worth a look were checked and are not defects**: `run_pr002`'s
      `min(key=...)` and `run_pr005`'s `Decimal` from an `object` are both variable reuse that mypy
      cannot narrow, in runners whose results completed. Recorded so the next session does not
      re-chase them.

      Derive the remaining count, never quote it from here:

      ```bash
      PYTHONPATH=$PWD/src python -m mypy tools/
      ```

      **Kept because it is the reason the count is gone from this row.** This row said 53 from
      2026-08-02 until 2026-08-10, then 100 until 2026-08-30, and `pyproject.toml` carried the same
      figure both times. Nothing recomputed it: gate 5 ran over `src`, so the number describing
      what the gate does *not* cover was the one figure in the policy no gate could check. It was
      the fifth hand-maintained count to drift here, and the answer was never a better habit — the
      row names the command now, and the part of `tools/` that matters is under the gate.
- [ ] Runtime budget. Gates 1–3 take about a minute locally (dominated by re-extracting 116 PDFs).
      If that becomes friction, cache extraction by file hash rather than weakening the check —
      and note it is **not** the CI cost, because 2 and 3 report `UNAVAILABLE` there.

      **The CI budget became live on 2026-08-30 and it was cumulative growth, not one change.** A
      run was **cancelled at 20m05s** against `timeout-minutes: 20` while its twin on the same
      commit passed at **15m10s**. The log locates it exactly: it stopped inside **gate 34**, the
      mutation gate, which copies `src/` once per mutant and is the last heavy thing in the
      sequence. The cap was raised to 35 — a cap the healthy suite brushes against is a coin flip
      rather than a check, and a red `gates` on `master` for no reason is the noise §3 says gets a
      gate bypassed. What the cancellation is *for* — stopping a hung job — is unchanged.

      **What this does not do is make the suite faster**, and the next lever is named here rather
      than left to be rediscovered: gate 34 pays a `src/` copy and a pytest start per mutant, and it
      runs seventeen. Sharing one scratch tree across mutants, or batching the named tests into one
      pytest invocation, would take the largest bite. Neither is done, and neither should be done
      without measuring first — the gate's value is that a mutation site which no longer matches is
      a FAILURE, and a faster version that quietly skips one would be worth less than the minutes.
