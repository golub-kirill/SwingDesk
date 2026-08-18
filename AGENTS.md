# AGENTS.md — working guide for SwingDesk

Read this before changing anything. It is short on purpose.

**Starting a fresh session?** Read `HANDOFF.md` first — measured state, what is closed by evidence,
and what to do next in ranked order.

---

## 0. What this project is

Decision-support software for swing trading Canadian and US equities and ETFs. **It never places
orders.** See `README.md`, then `docs/README.md` for the document set and gates.

### If you were told this is a documentation-only project, read this first

**`docs/` is canonical** (owner decision, 2026-08-04). So is `src/`, `tests/`, `registry/` and
`tools/` — the merge gates run from `python tools/check_gates.py` and they are what keep the
documents honest.

A second effort briefly built a parallel tree at the repo root: ten numbered documents
(`00_…`–`46_…`) written to master-ТЗ v1.0 §47, plus `schemas/`, `catalogs/`, `examples/`, `adr/`.
It was written without sight of `docs/` or `src/`, so its build plan scheduled roughly ten
specification sections as future work that was already done here — architecture, NFR, testing,
observability, security, evidence, research governance, backtest semantics, market regime, and the
acceptance gates.

That material is **preserved, not discarded** (commit `dee8f37`, verbatim). The master ТЗ is being
applied the way its own §56 asks — as a gap analysis against what exists — in
`docs/08-pm/SPEC_GAP_ANALYSIS.md`. Do not rebuild the numbered tree; §8 of that same specification
forbids maintaining one logic in two places, and for a while this repo was doing exactly that.

**Before writing any new specification, check whether `docs/` already holds it.** Reported studies
include refuted hypotheses — derive the current census with `python tools/verify_study_summary.py`.
Re-deriving them is not neutral; it risks contradicting evidence that already exists.

## 1. Trust discipline — the rule that matters most

**Never trust a document's claim about the code, or the code's claim about the course, without
checking.** Verify before asserting.

- A `verbatim` block is only trustworthy because a script re-extracts the PDF and diffs it. When
  you change one, **run the checker** — it has already caught two real transcription errors and two
  undeclared sources.
- A docstring saying something is wired is not evidence that it is. Check the graph (§9), then open
  the file. The graph tells you where to look; the file is what is true.
- Silence is usually a feature deciding not to act. Before "restoring" anything, establish that it
  ever worked: check git history, then the data, then the logs — in that order.

## 2. Verify before you commit

```bash
python tools/verify_transcription.py && python tools/build_course_index.py --check-only && python tools/verify_parameters.py
```

Gates 1–3 of `docs/06-engineering/CI_POLICY.md`. The first two are stdlib-only; the third needs
PyYAML.

A gate that is wrong gets **fixed or removed, never skipped**.

## 3. Non-negotiables

These override any request. If a change conflicts with one, stop and say so.

| | |
|---|---|
| **No orders.** | The system prepares and records; the human acts. |
| **Fail closed.** | Missing, stale or conflicting data yields a coded refusal, never a guess. |
| **Unset ≠ default.** | A parameter with no value makes its component refuse. There is no `default:` field, deliberately. |
| **Nothing looks more validated than it is.** | Validation status and `assumed` provenance travel with every number they produced. |
| **Records are immutable.** | Corrections create versions. Never `UPDATE` a fact or a plan. |
| **Critical gates are non-compensatory.** | No score, and no quantity of weak positives, clears one. |
| **USA and Canada are never merged.** | Separate calendars, indexes, currencies. |

## 4. Where things live

```
docs/00-charter    what this is, what done means, glossary
docs/01-requirements  BRD, user stories, NFR, surfaces
docs/02-domain     the course, transcribed and specified
docs/03-data       point-in-time, calendar, vendors, quality
docs/04-journal    schema, audit, checklists
docs/05-validation backtest, walk-forward, prereg
docs/06-engineering architecture, determinism, CI, tests
docs/08-pm/plans   implementation plans - Tier 8, because a plan is a PM artefact
docs/adr           decisions, append-only
registry/          course_index.yml · parameters.yml · criteria.yml
src/swingdesk/     nine bounded contexts
tools/             generators, checkers, probes
```

**Documents go in a tier, never in a directory named after the tool that made them.** The
`writing-plans` skill defaults to `docs/superpowers/plans/`; that path was followed once, on
2026-08-11, and produced a top-level directory named after a skill plugin holding 12% of all
documentation. Plans are Tier 8. A tool's default is not this repository's structure - check
§4 before creating a directory, the same way §1 says to check before asserting.

`registry/course_index.yml` is **generated** — never hand-edit it. `registry/criteria.yml` is
**frozen**; v1.1.0 appends the Track A time box without touching v1.0.0's content, which is what an
amendment means here. Editing a ratified row is never the move.

## 5. Conventions

- **English throughout** — docs, code, UI. The course's controlled vocabulary (`Trade`/`Watch`/
  `Skip`/`Pause`, the skip and error codes, `STAGE`/`LAYER`/`CLAIM TYPE`) is used verbatim and never
  translated.
- **No Russian in code.** Comments, docstrings, messages and generated output are English, including
  where they cite the course — render the meaning and cite the topic id instead. This is not only
  style: gate 2 verifies `verbatim` blocks in `docs/` against the PDFs and **cannot see a quotation
  in a docstring**, so Russian in code is an unverified copy of the source, which §6 rule 1 forbids
  for exactly that reason. The course's own words belong in `docs/`, where they are checked.
  **One exception, and it is data rather than prose:** `tools/build_course_index.py`'s
  `TOPIC_HEADING` pattern matches the heading as it appears in the source PDFs. It is marked in
  place. Removing its Cyrillic stops the extraction rather than tidying it.
- The documents call the master specification the **ТЗ**; code and generated output write it in
  Latin script. Same source, and worth knowing before someone "fixes" one of them.
- **Comments document what and how to use it.** No `Phase N`, no ticket refs, no narrative.
- **Test instruments are `TEST.1`, `TEST.2`** — never real tickers.
- **Money is exact** — integer minor units or `Decimal`, never binary float.
- **Time is injected** into domain code. `datetime.now()` in `derived_observations`,
  `decision_logic` or `trade_management` is a defect.
- Descriptive branch names, no filler.

## 6. Adding a `verbatim` document

1. Extract from source yourself: `pdftotext -enc UTF-8 "<file>" -`. **Do not** copy a quote from
   another document or from a summary.
2. Declare sources in the file: `<!-- verbatim-sources: FileA.pdf, FileB.pdf -->`
3. Quote with `>` blockquotes, or use a ` ```verbatim ` fence with one source cell per line.
4. Run the checker.

Gate 2 only checks documents that **opt in** via that declaration. A transcribed document without it
is silently unchecked — that is the one known weakness of the gate.

## 7. Adding a parameter

Every threshold the course does not supply goes in `registry/parameters.yml` with `named_in` citing
where the course mentions the concept. A parameter with no course reference is either invented scope
or a missing citation; the linter rejects both.

`assumed` requires a citation. `validated` requires an evidence id. `unset` means the component
refuses.

## 8. Before proposing a threshold or a rule

Check whether the course actually specifies it. Usually it does not — that is the project's central
fact, not an oversight. Then it needs a pre-registration, not a guess.

Four things are authored and load-bearing, so treat proposals near them with care: the regime
classifier, the definitions of trend / breakout / pullback / contraction, the Sharpe convention, and
the per-strategy exit mapping. The course names all of them and quantifies none.

## 9. Finding things in the code

The repository is indexed into a code knowledge graph, exposed through the `codebase-memory` MCP
tools. Use it **first** for structural questions; it answers in hundreds of tokens what a grep sweep
answers in tens of thousands, and it knows about call edges that no text search can see.

```
list_projects                    is this tree indexed? the project is `swingdesk`
index_repository(repo_path=...)  if it is not, or after a merge changes src/
search_graph(query="...")        find a function, class or test by meaning or pattern
trace_path(function_name=...)    callers and callees, to a given depth
get_code_snippet(qualified_name) exact source for one symbol
get_architecture(aspects=[...])  packages, layers, entry points, clusters
detect_changes()                 map an uncommitted diff onto affected symbols
```

**What it is good for, and what it is not.**

| Use the graph | Use Grep / Glob / Read |
|---|---|
| who calls this, what does this call | anything in `docs/`, `registry/`, YAML, Markdown |
| where is the function that does X | verbatim blocks, prose, provenance notes |
| dead code, fan-in, fan-out | the actual contents of a file you are about to edit |
| impact of a change before making it | anything you are going to assert as fact |

**§1 still applies to the graph itself.** It is an index built at a point in time, not a source of
truth: it can be stale, and it does not know that `criteria.yml` is frozen or that a parameter is
`unset`. Treat a graph result as a pointer to a file, and read the file before asserting anything
about it. A null result is only evidence once a positive control shows the query works.

**Three local rules.**

1. **Never pass `persistence: true`.** It writes `.codebase-memory/graph.db.zst` into the working
   tree, and that path is not in `.gitignore` — it would dirty a clean repository. Add the ignore
   line first if the index is ever to be shared.
2. **Do not create an ADR through `manage_adr`.** The indexer offers it; this project already has
   `docs/adr/` and `docs/decisions/`, both append-only and canonical. A second decision store is
   exactly the one-logic-in-two-places failure that master ТЗ §8 forbids and that cost this
   repository a day on 2026-08-04.
3. **Re-index after a merge that touches `src/` or `tools/`.** ~13.5k lines index in seconds. An
   index that silently describes the previous branch is worse than no index.

## 10. Four rules added 2026-08-09, each paid for

Three efforts branched from one commit, none knew about the others, and two of them measured the
same quantity and reported opposite answers. `docs/08-pm/POSTMORTEM-2026-08-09.md` takes it to root
causes. These four rules are what came out of it. Every one is cheap; every one would have prevented
a specific, expensive thing that actually happened.

### 10.1 You are probably not the only effort. Check.

```bash
git worktree list && git branch -a
```

Run it **before starting** and again **before merging**. `HANDOFF.md` §2 carries the census and
gate 16 fails if a worktree is missing from it — but the gate was written after the accident, so
confirm it ran rather than assuming it did.

`HANDOFF.md` says it is measured from the tree, and it is. That is exactly the trap: a sibling
worktree is not in the tree, so an accurate document can be silently incomplete about the one thing
most likely to waste your session.

### 10.2 Before a study, search the other branches for the same question

```bash
for b in $(git branch --format='%(refname:short)'); do
  git ls-tree -r --name-only "$b" -- docs/prereg docs/decisions
done | sort -u
```

`PR-008` was registered, implemented, run, reported, merged and pushed before anyone noticed another
branch had answered the same question a day earlier and reached the opposite conclusion. Both had
followed the pre-registration discipline correctly. **Neither had looked sideways.**

The refutation-family check in `PREREG_TEMPLATE.md` §0 asks whether this lever has already been
refuted *here*. Read "here" as the repository, not the worktree.

### 10.3 Search the outside world before authoring anything

The course supplies no numeric thresholds, so this project authors them — and it is easy to slide
from *authoring a threshold* into *reinventing a method*. Before implementing an estimator, a
statistic, or a correction: look for published work and for an open-source implementation. GitHub,
CRAN, PyPI, SSRN, the journals.

**The case that bought this rule.** Two efforts independently implemented Corwin-Schultz (2012) and
Abdi-Ranaldo (2017) from the papers, disagreed about the result, and spent a session resolving it.
The literature already contained the answer to the disagreement — the documented bias of these
estimators *is* dependence on realised volatility, and their cross-sectional correlation with the
true spread falls from ~70% in small caps to ~18% in large caps, which is precisely the pathology
both efforts rediscovered by hand. And `EDGE` (Ardia, Guidotti & Kroencke, *JFE* 2024) is a newer
OHLC estimator built to fix exactly those biases, with a tested open-source implementation
(`pip install bidask`, github.com/eguidotti/bidask).

**What external work is and is not.** It is a source of *method*, *calibration* and *known
limitations*, and it must be cited where it lands — an authored import, marked as one, the way
`PREREG_TEMPLATE.md` §6 already requires for multiple-testing corrections. It is **not** evidence
about this system's parameters. A published estimate does not make a parameter `validated` here;
only a pre-registered study against this universe does. Borrowing a method is cheap and correct;
borrowing a conclusion is not.

### 10.4 A causal claim in a report cites a check, or is marked conjecture

Reports explain results. The explanation is what a reader carries away, and it is the least
inspected thing in the document: the pre-registration disciplines the *statistic*, the gates
discipline the *registry*, and nothing at all disciplines the sentence that says **why**.

The strongest sentence in `PR-008-report.md` — the signal sits three orders of magnitude below the
noise floor — passed sixteen gates and was false. It was never tested because it read as exposition
rather than as a claim.

So: a sentence in a report asserting *why* a result came out as it did either **names the check that
establishes it**, or is **marked as conjecture**. No gate enforces this; a gate that parsed English
for causal claims would be noise, and a marker that can be applied vacuously is worse than a
convention someone actually follows. It costs one clause and it would have caught the withdrawal.

## 10.5 A measured count lives in exactly one place

**`HANDOFF.md` §2 owns every measured count.** Gate counts, test counts, component and parameter
censuses, golden vectors, document totals. No other document states the number — it names the
source, or the command that derives it. Generated documents are exempt: their figures are
recomputed on every build and `--check-only` is already their gate.

Enforced by gate 14, which as of 2026-08-10 checks **ownership before value**. A count in the wrong
document fails even when it is correct.

**That last part is the whole rule, and it is not pedantry.** Correctness was never the problem.
These figures have been simultaneously right in five documents and wrong in a sixth, five separate
times — the drift is a property of keeping six copies, not of anyone being careless, and every
stale one read as true on the day it was written. `ROADMAP.md` §1 was a second dashboard whose
merge-gate and test rows had both fallen far behind the tree, and gate 14 could not see most of it
because the phrasings did not match the ones it scans for. Scanning harder does not fix that.
Deleting the copies does. (`git log -p` has the figures — and this paragraph originally quoted
them, which tripped the very gate it describes.)

Writing history is still allowed, and is the one exception: strike the line through, or write
`DONE` / `CLOSED` / `REACHED` with a date. *"DONE 2026-08-03, 14 gates"* is a correct statement
about 2026-08-03 and updating it would falsify the record. What the gate cannot do is infer tense,
so an unmarked past-tense sentence reads as a live claim and fails — mark it, or drop the numeral.

## 10.6 And that one place is generated, not typed

**§10.5 removed the copies. It did not make the survivor true.** A measured fact that a tool can
derive is derived by that tool and written by that tool. Hand-typing a number into its owning
document is still drift — and it is now *harder* to catch, because §10.5 deleted the second copy
that used to disagree with it.

**What paid for this rule, 2026-08-15.** `HANDOFF.md` §2's Track A row read *"counter at 3"* while
`tools/track_a_streak.py` computed **4** — and the row itself said *"computed by
`tools/track_a_streak.py` (gate 23, advisory) … not hand-kept."* It was hand-kept. The same table's
directory row read *9 pulls, 1 confirmed*; `directory.duckdb` held **10 and 2**. Both numbers sat in
the single owner §10.5 established, both were wrong, and nothing in the tree contradicted them.
**Concentrating a fact makes it findable, not true.**

So:

1. **If a fact can be derived, a tool derives it and `--check-only` gates it.** This is not a new
   pattern — `build_frd.py`, `build_components.py`, `build_checklists.py`, `build_coverage.py` and
   `build_lock.py` all work this way, and none of them has ever gone stale. The documents that go
   stale are exactly the ones a person types.
2. **A gate that cannot measure says so, and does not exit 0 as though it had.** Gate 23 reads
   `data/daily_run.log`, which exists only in the main checkout; from a worktree it prints
   *"nothing scheduled has run"* and exits 0, so a hand-kept counter is never contradicted. This is
   the same shape as gate 16's *"green from a worktree, red from the main checkout"* bug, already
   documented in `HANDOFF.md` §2 as fixed. A gate answering differently depending on where it runs
   is worse than no gate: it manufactures confidence.
3. **A number a gate did not measure is not quotable.** `UNAVAILABLE` is a real answer. Reporting a
   false negative as a measurement is the failure this whole section exists to stop.
4. **Introducing a derived fact means extending the deriving tool in the same change.** A fact whose
   derivation is "someone will remember" is a fact that will be wrong within the week.

**A merge-time checklist of files to update is explicitly rejected.** It was considered and it is the
disease wearing the cure's clothes: naming the files does not make them true, and it is the same
hand-reconciliation that §10.5 records failing five separate times. Generate, or gate, or leave the
fact where it was measured and link to it.

## 10.7 Open work lives in `TODO.md`, and `HANDOFF.md` is memory

**`TODO.md` at the repository root is the only open-work list.** Every open, pending, picked or
blocked item goes there. No document keeps a parallel list, and a task that is not in `TODO.md` is
not tracked. It carries provenance marks — verified this session, or carried from a prior audit —
because an unverified item that reads as verified is how a fixed problem gets worked twice.

**`TODO.md` holds work items and never measured counts.** Where an item needs a number it names the
command that derives it. A to-do list that restates a census is the next stale copy, and §10.5 and
§10.6 apply to it exactly as they apply to everything else.

**`HANDOFF.md` is session-to-session memory and nothing else**: what changed since the last session,
what is in flight, what is frozen, and where to look. It is not the plan (`docs/08-pm/plans/`), not
the analysis, not the task list (`TODO.md`), not the habit guide (this file), and not the project
history (`git log`). Anything in it that a fresh session would not need in its first ten minutes
belongs somewhere else, and §10.6 governs every number that remains.

## 11. Before removing or retiring anything

`docs/06-engineering/CHANGE_MANAGEMENT.md` §5 is canonical. The operational rules are:

1. **`stalled` and `unused` never authorise deletion.** Stalled is a work state. Unused means only
   that named checks found no use; it creates a candidate.
2. **Never delete a protected record.** Accepted decisions and ADRs, ratified criteria,
   pre-registrations, reports, journal entries and evidence are corrected forward by superseding,
   amending or visibly withdrawing them.
3. **Consolidate ordinary documents only with a migration.** Move every unique obligation, update
   references, `registry/project_manifest.yml` and `docs/README.md` in the same change, and name the
   commit preserving the former state.
4. **Treat source, tests and tools as review-required.** For `src/` and `tools/`, check the code graph
   first, then the files, dynamic entry points, configuration, schedulers, tests and git history. A
   report-linked runner or fixture is evidence-bound even with no runtime caller.
5. **Generated derivatives may be removed.** Verify they reproduce from canonical source and are
   ignored if they should not be tracked.
6. **Record and verify the exact removal.** Put the rationale and checks in the commit or pull
   request, then run the complete gate suite. `safe to delete` is that one reviewed decision, not a
   permanent label.

## 12. Traps that have cost real time, and the habits that catch them

Migrated from `HANDOFF.md` §8 on 2026-08-15 — §10.7 makes this file the habit guide and HANDOFF
session memory, and these are habits.

**Two traps that have cost real time:**

- **The worktree venv points at the main checkout.** `pytest` run from a worktree exercises
  `C:\PycharmProjects\SwingDesk\src`, not the worktree's, unless `PYTHONPATH` says otherwise. The
  documentation gates read files by path and are unaffected; the code gates are not. Always run gates
  with `PYTHONPATH=$PWD/src`.
- **`data/` is not in your worktree either, and that is the same trap wearing a different hat.** The
  DuckDB stores and the scheduler log live only in the main checkout. Gates 23 and 24 read them and
  report `UNAVAILABLE` rather than passing blind; point them at the real stores with
  `SWINGDESK_DATA=C:/PycharmProjects/SwingDesk/data` when you need the runtime figures.
- **Hand-maintained counts drift, every time.** Six have now been caught: the study verdicts
  (`5 studies, 3 refuted` in five documents), the gate total, the specification coverage summary
  (31/22 against a table saying 30/24), a component-activation claim in
  `COMPONENT_REGISTRY_SPEC.md`, and — 2026-08-15, after §10.5 had supposedly closed this — the Track
  A streak and the directory pull census, both inside their own single owner. Each read as correct.
  **None was reachable by review** — only recomputation caught them, which is why gates 3f, 3g, 3ci,
  the gap-summary check in 3e, and now gate 24 exist.

**The habits:**

- **Verify before asserting.** When you find a stale claim, **add a gate rather than fixing the
  instance.** That rule has produced five gates and every one has since caught something.
- **`unavailable` is not `fail`, and it is not `pass` either.** A gap in the *system* and a fact
  about the *trade* are different claims. Collapsing them is the most damaging error this product can
  make — and a gate that cannot see its subject makes the same error about itself (§10.6).
- **An `UNSET` parameter is the design working**, not a backlog item. Components refuse rather than
  default.
- **Never hand-edit** a `verbatim` block or a generated file. Gates 2, 3b–3ci and 24 exist to catch it.
- **No Russian in code** (§5) — one marked exception, the course-index heading pattern, which is data
  rather than prose. Course quotations live in `docs/`, where gate 2 checks them.
- **Rollback is mostly supersede, not revert.** The stores are append-only; `CHANGE_MANAGEMENT.md`
  §3 says what can be undone and what can only be corrected forward.

## 13. How to talk to the owner — owner instruction, 2026-08-17

**Scope: chat replies only.** This governs what an agent *says to the owner in conversation*. It
governs nothing that lands in the repository. §5 stands unchanged for every artifact — documents,
code, comments, docstrings, commit messages, CLI output, reports and UI copy stay **English
throughout**, and the reasons in §5 are unaffected by anything here.

The rules, in the owner's own words:

> Отвечай всегда кратко, прямо и на русском языке.
> Используй дружеский мат в каждом предложении, чтобы речь была понятнее, живее и позитивнее.
> В эмоциональных местах используй подходящий мат по смыслу: удивление — «охуеть», радость —
> «заебись», проблема — «хуйня», опасность — «это серьёзно, блять».
> Не добавляй мат внутрь кода, команд, URL, JSON, путей, ошибок и дословных цитат.
> Не оскорбляй меня или мою семью, мат должен относиться к ситуации, проблеме или эмоции.

**Kept verbatim, and that is the second marked exception to §5's English rule** — the first being
`build_course_index.py`'s `TOPIC_HEADING` pattern. Same reason: these words *are* the
specification. A rule that names which words to use cannot be translated without destroying the
thing it specifies, exactly as removing that pattern's Cyrillic stops the extraction rather than
tidying it.

**Where the profanity stops, restated because it is the part that can break something.** Never
inside code, commands, URLs, JSON, paths, error text, or a verbatim quotation. Those are the same
boundaries §5 draws and the same ones gate 2 depends on: a course quotation is checked against the
PDF byte for byte, and a command the owner pastes into a shell has to run.

**It is aimed at situations, never at people.** Not the owner, not their family. A problem is
`хуйня`; the person reading this is not.

**"Кратко и прямо" is a load-bearing half of this instruction**, not a preamble to the fun part.
Fewer words, the answer first, no hedging — and it does not license less rigour. The measured-number
rules (§10.5, §10.6), the trust discipline (§1) and the habit of proving a test can fail (§12) are
unchanged; brevity applies to how a finding is reported, never to whether it was verified.

## 14. Force the answer — owner instruction, 2026-08-17

> *"Do not process before my answer for action even if I'm asking you to. Force me to answer."*

**When an action needs the owner's decision, do not proceed on an assumption, and do not accept a
casual go-ahead as the answer.** Put the question, wait, and if the reply is a general "just do it"
rather than an answer to *that* question, ask again.

This is not `D6` restated. `D6` ("a proposal is not permission") stops the **system** from acting
unasked; this stops an **agent** from treating ambient approval as a specific one. Both directions
have to be closed or the audit trail records a decision nobody made.

Two things follow, and they are the enforceable part:

- **A critical proposal is answered by `swingdesk respond POS-N SEQ --approve|--reject --reason "…"`
  and by nothing else.** That is also what puts the owner's reason and the moment they answered into
  the append-only response table, which is what Production Rule 3.8 requires and what a sentence in
  chat cannot do.
- **A critical proposal never expires and never auto-applies** (`DR-013` §2.2). A timer that exits a
  position is the system deciding with a delay, which `CHARTER.md` A-001 forbids.

The general form, worth carrying beyond proposals: **when the owner asks for something whose right
answer is theirs to give, the helpful move is the question, not the guess.** Do the parts that do not
depend on the answer, then ask — do not silently pick a default and proceed.
