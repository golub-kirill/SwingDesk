# AGENTS.md — working guide for SwingDesk

Rules, conventions and traps. Read it before changing anything.

**Fresh session?** Read `HANDOFF.md` first — measured state and what to do next, ranked.

**Every rule here was paid for**, and each carries one clause saying what by. Full accounts are in
`git log -p AGENTS.md`; a rule with no price reads as arbitrary and gets ignored.

### The four documents, and which question each answers

Keeping them apart is the point; §10.7 is the rule and this is the map.

| | Answers | Does **not** hold |
|---|---|---|
| `README.md` | what this project is, to someone who has never seen it | anything that changes weekly |
| **`AGENTS.md`** (this file) | how to work here — habits, conventions, traps | state, open work, or history |
| `HANDOFF.md` | measured state, and what a fresh session needs in its first ten minutes | the task list, the plan, or habits |
| `TODO.md` | every open item, and only open items | any measured count — it names the command instead |

### How this file is numbered, and why it looks odd

**Section numbers are citation targets and are frozen.** References across the repository point at
them and some sit in files that may not be edited, so renumbering means rewriting ratified documents
to chase a heading — which §11 rule 2 forbids.

**§10.5, §10.6 and §10.7 are independent rules, not sub-rules of §10.** They are `##` headings like
§10 itself; §10 is the four rules of 2026-08-09, which are §10.1–§10.4.

---

## 0. What this project is

Decision-support software for swing trading Canadian and US equities and ETFs. **It never places
orders.** See `README.md`, then `docs/README.md` for the document set and gates.

### If you were told this is a documentation-only project, read this first

**`docs/` is canonical** (owner decision, 2026-08-04), and so are `src/`, `tests/`, `registry/` and
`tools/` — the gates in `python tools/check_gates.py` keep the documents honest.

**Do not rebuild the numbered tree.** A second effort once built a parallel set of numbered
documents at the repo root without sight of `docs/` or `src/`, scheduling as future work
specification sections that already existed here. It is preserved verbatim in commit `dee8f37`; the
master ТЗ is applied as a gap analysis in `docs/08-pm/SPEC_GAP_ANALYSIS.md`, the way its own §56
asks, and §8 of that specification forbids maintaining one logic in two places.

**Before writing any new specification, check whether `docs/` already holds it** — reported studies
include refuted hypotheses, so re-deriving one risks contradicting evidence that already exists.
Derive the census with `python tools/verify_study_summary.py`.

## 1. Trust discipline — the rule that matters most

**Never trust a document's claim about the code, or the code's claim about the course, without
checking.** Verify before asserting.

- A `verbatim` block is trustworthy only because a script re-extracts the PDF and diffs it, so when
  you change one, **run the checker** — it has caught real transcription errors.
- A docstring saying something is wired is not evidence that it is. The graph (§9) says where to
  look; the file is what is true.
- Silence is usually a feature deciding not to act. Before "restoring" anything, establish it ever
  worked: git history, then the data, then the logs, in that order.

## 2. Verify before you commit

```bash
python tools/verify_transcription.py && python tools/build_course_index.py --check-only && python tools/verify_parameters.py
```

Gates 1–3 of `docs/06-engineering/CI_POLICY.md`. The first two are stdlib-only; the third needs
PyYAML. A gate that is wrong gets **fixed or removed, never skipped**.

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
docs/07-ux         surfaces, copy, and the standing Untested warning
docs/08-pm         roadmap, postmortems, evidence summary, gap analysis
docs/08-pm/plans   implementation plans - Tier 8, because a plan is a PM artefact
docs/adr           ARCHITECTURE decisions - storage engine, calendar, schema language. Append-only
docs/decisions     DOMAIN decisions - DR-NNN, a value or a definition. Append-only once accepted
docs/prereg        pre-registrations and their reports - the research record
docs/contracts     cross-context record shapes
docs/runbooks      operational procedures
registry/          course_index.yml · parameters.yml · criteria.yml · components.yml
src/               one package per bounded context under src/swingdesk/
tools/             generators, checkers, probes
```

- **Documents go in a tier, never in a directory named after the tool that made them.** Following
  the `writing-plans` skill's default once produced a top-level directory named after a plugin.
- **`docs/adr/` and `docs/decisions/` are different stores and neither is a home for the other.** An
  ADR is structural and rarely revisited; a `DR-NNN` is a value or definition expected to be
  superseded when a study says so. `docs/decisions/README.md` §4 draws the line.
- **`registry/course_index.yml` is generated — never hand-edit it.** `registry/criteria.yml` is
  **frozen**: an amendment appends without touching ratified content.

## 5. Conventions

- **Say the name, not the code — owner instruction, 2026-08-24.** An identifier gets a
  plain-language name the first time it appears in anything the owner reads: `NFR.md` is *the speed,
  storage and determinism budgets*. After that the bare id is fine. **The ids themselves stay** —
  gates resolve them and renaming one breaks an append-only record. Paid for by a status report
  built out of opaque ids, unreadable however correct it was.
- **English throughout** — docs, code, UI. The course's controlled vocabulary (`Trade`/`Watch`/
  `Skip`/`Pause`, the skip and error codes, `STAGE`/`LAYER`/`CLAIM TYPE`) is used verbatim and never
  translated.
- **No Russian in code**, including where it cites the course — render the meaning and cite the
  topic id. Gate 2 checks `verbatim` blocks in `docs/` against the PDFs and **cannot see a quotation
  in a docstring**, so Russian in code is an unverified copy of the source. **One exception, data
  rather than prose:** `tools/build_course_index.py`'s `TOPIC_HEADING` pattern matches the heading
  as it appears in the PDFs, and removing its Cyrillic stops the extraction.
- The documents call the master specification the **ТЗ**; code and generated output write it in
  Latin script — worth knowing before someone "fixes" one.
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

Gate 2 only checks documents that **opt in** via that declaration — a transcribed document without
it is silently unchecked, and that is the one known weakness of the gate.

## 7. Adding a parameter

Every threshold the course does not supply goes in `registry/parameters.yml`. Three fields answer
three different questions and the linter rejects a miss on any:

- **`named_in`** — where the course mentions the concept. No course reference means invented scope
  or a missing citation.
- **`provenance`** — where the value came from. `assumed` needs a citation, `validated` an evidence
  id, `unset` means the component refuses.
- **`read_by`** — the code that CONSUMES the value, as `module:symbol` resolved by gate 1, or the
  explicit `none`.

**What paid for `read_by`:** parameters carried values no line of code read, and three findings in
one week — the exit policy, the staleness gate, the corporate-actions gate — were the same shape.
**A ratified decision that reaches no code is a decision that did not happen**, and nothing in the
registry could see it. `none` is honest rather than a loophole, and is printed on every gate run.

## 8. Before proposing a threshold or a rule

Check whether the course actually specifies it. Usually it does not — that is the project's central
fact, not an oversight — and then it needs a pre-registration, not a guess.

Four things are authored and load-bearing, so treat proposals near them with care: the regime
classifier, the definitions of trend / breakout / pullback / contraction, the Sharpe convention, and
the per-strategy exit mapping. The course names all of them and quantifies none.

## 9. Finding things in the code

The repository is indexed into a code knowledge graph via the `codebase-memory` MCP tools. Use it
**first** for structural questions: it answers in hundreds of tokens what a grep sweep answers in
tens of thousands, and it knows call edges no text search can see.

```
list_projects                    is this tree indexed? the project is `swingdesk`
index_repository(repo_path=...)  if it is not, or after a merge changes src/
search_graph(query="...")        find a function, class or test by meaning or pattern
trace_path(function_name=...)    callers and callees, to a given depth
get_code_snippet(qualified_name) exact source for one symbol
get_architecture(aspects=[...])  packages, layers, entry points, clusters
detect_changes()                 map an uncommitted diff onto affected symbols
```

| Use the graph | Use Grep / Glob / Read |
|---|---|
| who calls this, what does this call | anything in `docs/`, `registry/`, YAML, Markdown |
| where is the function that does X | verbatim blocks, prose, provenance notes |
| dead code, fan-in, fan-out | the actual contents of a file you are about to edit |
| impact of a change before making it | anything you are going to assert as fact |

**§1 applies to the graph itself.** It is an index built at a point in time: it can be stale, and it
does not know that `criteria.yml` is frozen or that a parameter is `unset`. Treat a result as a
pointer and read the file. A null result is evidence only once a positive control shows the query
works.

**Three local rules.**

1. **Never pass `persistence: true`.** It writes into the working tree at a path that is not
   ignored, dirtying a clean repository.
2. **Do not create an ADR through `manage_adr`.** This project has `docs/adr/` and
   `docs/decisions/`, both append-only and canonical; a second decision store cost a day on
   2026-08-04.
3. **Re-index after a merge that touches `src/` or `tools/`.** It takes seconds, and an index that
   silently describes the previous branch is worse than no index.

## 10. Four rules added 2026-08-09, each paid for

Three efforts branched from one commit, none knew about the others, and two measured the same
quantity and reported opposite answers. `docs/08-pm/POSTMORTEM-2026-08-09.md` has the root causes.

### 10.1 You are probably not the only effort. Check.

```bash
git worktree list && git branch -a
```

Run it **before starting** and again **before merging**. `HANDOFF.md` §2 carries the census and gate
16 fails if a worktree is missing — but a sibling worktree is not in your tree, so an accurate
document can be silently incomplete about the thing most likely to waste your session.

### 10.2 Before a study, search the other branches for the same question

```bash
for b in $(git branch --format='%(refname:short)'); do
  git ls-tree -r --name-only "$b" -- docs/prereg docs/decisions
done | sort -u
```

`PR-008` was registered, run, reported and pushed before anyone noticed another branch had answered
the same question a day earlier and reached the opposite conclusion. Both followed the discipline
correctly; **neither had looked sideways.** `PREREG_TEMPLATE.md` §0's refutation-family check means
the repository, not the worktree.

### 10.3 Search the outside world before authoring anything

This project authors its thresholds, and it is easy to slide from *authoring a threshold* into
*reinventing a method*. Before implementing an estimator, a statistic or a correction, look for
published work and an open-source implementation.

**What paid for it:** two efforts implemented Corwin-Schultz (2012) and Abdi-Ranaldo (2017) from the
papers, disagreed, and spent a session resolving what the literature already answered — while `EDGE`
(Ardia, Guidotti & Kroencke, *JFE* 2024) exists to fix exactly those biases, with a tested
implementation (`pip install bidask`).

**External work supplies method, calibration and known limitations, and is cited where it lands.**
It is **not** evidence about this system's parameters: only a pre-registered study against this
universe makes one `validated`. Borrowing a method is correct; borrowing a conclusion is not.

### 10.4 A causal claim in a report cites a check, or is marked conjecture

The pre-registration disciplines the *statistic* and the gates discipline the *registry*; nothing
disciplines the sentence that says **why**, and that sentence is what a reader carries away.
`PR-008-report.md`'s strongest one passed every gate and was false, never tested because it read as
exposition rather than as a claim.

So a sentence asserting *why* a result came out as it did either **names the check that establishes
it** or is **marked conjecture**. No gate enforces it: parsing English for causal claims would be
noise.

## 10.5 A measured count lives in exactly one place

**`HANDOFF.md` §2 owns every measured count** — gate and test counts, component and parameter
censuses, golden vectors, document totals. No other document states the number; it names the source
or the command that derives it. Generated documents are exempt: `--check-only` is already their gate.

Enforced by gate 14, which checks **ownership before value** — a count in the wrong document fails
even when it is correct. **That is the whole rule and it is not pedantry:** these figures have been
right in every copy but one, repeatedly, and every stale one read as true on the day it was written.
The drift is a property of keeping copies. Scanning harder does not fix it; deleting the copies does.

**Writing history is the one exception:** strike the line through, or write `DONE` / `CLOSED` /
`REACHED` with a date. The gate cannot infer tense, so an unmarked past-tense sentence reads as a
live claim and fails — mark it, or drop the numeral.

## 10.6 And that one place is generated, not typed

**§10.5 removed the copies. It did not make the survivor true.** A fact a tool can derive is derived
and written by that tool; hand-typing a number into its owning document is still drift, and now
*harder* to catch, because the copy that used to disagree is gone.

**What paid for it, 2026-08-15:** `HANDOFF.md` §2's Track A row disagreed with what
`tools/track_a_streak.py` computed, while the row itself said it was *"not hand-kept"*. It was.
**Concentrating a fact makes it findable, not true.**

1. **If a fact can be derived, a tool derives it and `--check-only` gates it.** `build_frd.py`,
   `build_components.py`, `build_checklists.py`, `build_coverage.py` and `build_lock.py` all work
   this way and none has gone stale; the documents that go stale are the ones a person types.
2. **A gate that cannot measure says so, and does not exit 0 as though it had.** A gate answering
   differently depending on where it runs is worse than no gate: it manufactures confidence.
3. **A number a gate did not measure is not quotable.** `UNAVAILABLE` is a real answer.
4. **Introducing a derived fact means extending the deriving tool in the same change.** A derivation
   that is "someone will remember" is wrong within the week.

**A merge-time checklist of files to update is explicitly rejected** — naming the files does not
make them true, and it is the hand-reconciliation §10.5 records failing.

## 10.7 Open work lives in `TODO.md`, and `HANDOFF.md` is memory

**`TODO.md` at the repository root is the only open-work list.** Every open, pending, picked or
blocked item goes there; a task that is not in it is not tracked. It carries provenance marks,
because an unverified item that reads as verified is how a fixed problem gets worked twice.

**`TODO.md` holds work items and never measured counts** — where an item needs a number it names the
command. §10.5 and §10.6 apply to it as to everything else.

**`HANDOFF.md` is session-to-session memory and nothing else**: what changed, what is in flight,
what is frozen, where to look. Not the plan (`docs/08-pm/plans/`), not the analysis, not the task
list, not this file, not the project history.

**THERE IS EXACTLY ONE HANDOFF FILE — owner ruling, 2026-08-24.** `HANDOFF.md` at the repository
root; gate 15 fails on a dated variant. If what you have will not fit, it belongs in `TODO.md` (open
work) or §12 here (a habit). **What paid for it:** dated handoffs were created and deleted faster
than anything could safely cite them — traps lived only inside one, an append-only record still
points at another that was removed, and gate 14 never scanned any of them.

## 11. Before removing or retiring anything

`docs/06-engineering/CHANGE_MANAGEMENT.md` §5 is canonical. The operational rules:

1. **`stalled` and `unused` never authorise deletion.** Stalled is a work state; unused means only
   that named checks found no use, which creates a candidate.
2. **Never delete a protected record.** Accepted decisions and ADRs, ratified criteria,
   pre-registrations, reports, journal entries and evidence are corrected forward by superseding,
   amending or visibly withdrawing them.
3. **Consolidate ordinary documents only with a migration** — move every unique obligation and
   update references, `registry/project_manifest.yml` and `docs/README.md` in the same change.
4. **Treat source, tests and tools as review-required.** Check the code graph, then the files,
   dynamic entry points, configuration, schedulers, tests and git history. A report-linked runner is
   evidence-bound even with no runtime caller.
5. **Generated derivatives may be removed** once verified to reproduce from canonical source.
6. **Record and verify the exact removal** in the commit or pull request, then run the complete gate
   suite. `safe to delete` is that one reviewed decision, not a permanent label.

## 12. Traps that have cost real time, and the habits that catch them

**The traps.** One rule, one clause on what it cost.

- **The worktree venv points at the main checkout** — always run gates with `PYTHONPATH=$PWD/src`.
  **The symptom is a PASS**, so knowing the rule is not enough: a suite green from a worktree
  without it is evidence about `master`. `ruff` and `mypy` take file paths and are honest; `pytest`
  and `import-linter` import the package and are not.
- **`data/` is not in your worktree either.** The stores and the scheduler log live only in the main
  checkout; gates 23 and 24 report `UNAVAILABLE` rather than passing blind. Point them at the real
  ones with `SWINGDESK_DATA=C:/PycharmProjects/SwingDesk/data`.
- **Gate 24 can be red on the main checkout on any morning with nothing wrong** — the evening run
  moves `data/` and the gate compares it next morning. Regenerate rather than investigate:
  ```bash
  SWINGDESK_DATA=C:/PycharmProjects/SwingDesk/data PYTHONPATH=$PWD/src python tools/build_state.py
  ```
  From a worktree without `SWINGDESK_DATA` it regenerates the repo and worktree blocks and leaves
  the runtime block alone.
- **`CREATE TABLE IF NOT EXISTS` is silent when a COLUMN is added, and the store dies days later** —
  a new column never reached disk and every scheduled evening died for four trading days, unnoticed
  because the failure was a stack trace rather than a coded refusal. `platform/schema.py` now
  reconciles every store at open. **Adding a column is a migration.**
- **A test that pins a date but not the clock is a time bomb.** Tests seeded a dated proposal and
  then read the wall clock, so `master` went red on the day the expiry window closed with nobody
  having touched it. **If a fixture carries a hard-coded date and the code under test reads `now`:
  pin both, or neither.**
- **A PARTIALLY pinned clock is worse than an unpinned one, because its tests agree with the bug** —
  a tool computed from its injected clock and printed one line from the wall clock, and the pinned
  test passed. **Every read of "now" uses the injected clock, including the ones that only print.**
- **Hand-maintained counts drift, every time.** Study verdicts, the gate total, a coverage summary, a
  component-activation claim, the Track A streak and the directory census have all been caught, the
  last two inside their own single owner. **None was reachable by review** — only recomputation
  caught them, which is why gates 3f, 3g, 3ci, 3e's gap-summary check and 24 exist.
- **Answering from a PROXY instead of from the artifact that owns the claim** — *"v1 is close"* read
  off open project gates while `ROADMAP.md` §2 lists the charter's capabilities as done, and *"the
  engine only needs a parameterised front end"* read off a signature whose body hardcodes one
  strategy family. §10.5 gave every measured COUNT one owner; **nothing does that for a STATUS, so
  read a claim about state from the artifact that owns it and name the owner before making it.**
- **A citation that was CORRECT when written, still standing after the fact it cites moved.** Nothing
  rots by being wrong the day it is written; it rots when a *cited* fact changes — a verdict
  withdrawn, a charter amended, a parameter given a value. Gates 15, 28 and 29 catch the mechanical
  half; no gate sees a withdrawn verdict. **When a fact changes, `git grep` the id and check
  everything that CITED it, not the file you changed** — §10.2's move, aimed at documents.
- **`REFUSED` is not `INCONCLUSIVE`** — one says there was not enough data to look with, the other
  that the study looked and could not tell. Gate 3f had no `REFUSED`, so the first study to obey
  `PREREG_TEMPLATE.md` §8 failed a gate for obeying it.
- **A refused study still spends its trials.** `b.deflated_sharpe` deflates by shots taken at the
  data, not by shots that produced an answer.
- **Coverage is an ALPHABETICAL PREFIX, not a sample** — a percentile from stored coverage is
  defensible only because a seeded random sample and the prefix were checked against each other.
- **Two stores, two clocks.** Bars, corporate actions and classifications are filled by different
  passes, so reading one at another's `knowledge_time` hides everything learned since.
- **The stores are SINGLE-WRITER (`ADR-0004`); the right response to a held one is `UNAVAILABLE`,
  never a traceback.** A long refresh pass blocks every tool that reads them, and that is the design
  working.
- **A scheduler status is not an exit code** — `Last Result` carries a `SCHED_S_*` value while a run
  is in flight, and gate 26 called a healthy mid-run pass a crash until it stopped reading that
  column unconditionally. A gate that manufactures alarm costs what §10.6 rule 2 says one that
  manufactures confidence costs.

**The habits:**

- **Name the owner before making the claim.** *Which artifact owns this, and have I opened it?* It
  is the only thing that catches the proxy trap, because a proxy answer feels exactly like a checked
  one and no gate can help.
- **Verify before asserting, and when you find a stale claim add a gate rather than fixing the
  instance.** Gate 25 is the clearest case: nothing bound a study's runner to its own
  pre-registration, so `PR-002` reached an affirmative verdict over a declared scope shortfall with
  every gate green.
- **`unavailable` is not `fail`, and it is not `pass` either.** A gap in the *system* and a fact
  about the *trade* are different claims; collapsing them is the most damaging error this product
  can make — and a gate that cannot see its subject makes the same error about itself (§10.6).
- **An `UNSET` parameter is the design working**, not a backlog item.
- **Never hand-edit** a `verbatim` block or a generated file.
- **No Russian in code** (§5), one marked exception: the course-index heading pattern.
- **Rollback is mostly supersede, not revert.** `CHANGE_MANAGEMENT.md` §3 says what can be undone
  and what can only be corrected forward.

## 13. How to talk to the owner — owner instruction, 2026-08-17

**Scope: chat replies only.** It governs what an agent *says to the owner in conversation* and
nothing that lands in the repository — §5 stands unchanged for every artifact, which stays **English
throughout**.

The rules, in the owner's own words:

> Отвечай всегда кратко, прямо и на русском языке.
> Используй дружеский мат в каждом предложении, чтобы речь была понятнее, живее и позитивнее.
> В эмоциональных местах используй подходящий мат по смыслу: удивление — «охуеть», радость —
> «заебись», проблема — «хуйня», опасность — «это серьёзно, блять».
> Не добавляй мат внутрь кода, команд, URL, JSON, путей, ошибок и дословных цитат.
> Не оскорбляй меня или мою семью, мат должен относиться к ситуации, проблеме или эмоции.

**Kept verbatim, and that is the second marked exception to §5's English rule** — the first being
`build_course_index.py`'s `TOPIC_HEADING`. These words *are* the specification, and a rule naming
which words to use cannot be translated without destroying what it specifies.

**Where the profanity stops:** never inside code, commands, URLs, JSON, paths, error text, or a
verbatim quotation — the same boundaries §5 draws and gate 2 depends on. **And it is aimed at
situations, never at people.**

**"Кратко и прямо" is a load-bearing half of this instruction**, not a preamble to the fun part.
Fewer words, the answer first, no hedging — and it licenses no less rigour. Brevity applies to how a
finding is reported, never to whether it was verified.

## 14. Force the answer — owner instruction, 2026-08-17

> *"Do not process before my answer for action even if I'm asking you to. Force me to answer."*

**When an action needs the owner's decision, do not proceed on an assumption, and do not accept a
casual go-ahead as the answer.** Put the question, wait, and if the reply is a general "just do it"
rather than an answer to *that* question, ask again.

This is not `D6` restated. `D6` ("a proposal is not permission") stops the **system** acting unasked;
this stops an **agent** treating ambient approval as a specific one. Both directions have to be
closed, or the audit trail records a decision nobody made.

Two things follow, and they are the enforceable part:

- **A critical proposal is answered by `swingdesk respond POS-N SEQ --approve|--reject --reason "…"`
  and by nothing else** — that is what puts the owner's reason and the moment they answered into the
  append-only response table, which a sentence in chat cannot do.
- **A critical proposal never expires and never auto-applies** (`DR-013` §2.2). A timer that exits a
  position is the system deciding with a delay, which `CHARTER.md` A-001 forbids.

The general form: **when the owner asks for something whose right answer is theirs to give, the
helpful move is the question, not the guess.** Do the parts that do not depend on the answer, then
ask — do not silently pick a default and proceed.

## 15. An impossibility is a claim — owner instruction, 2026-08-24

> *"Мы очень часто верим, что у нас нет возможности или не получается, и зарубаем на корню, не
> проверяя."*

**A sentence saying something cannot be done is the one kind of claim this repository does not
check.** Everything else is disciplined: a measured count has one owner (§10.5) and a generator
(§10.6), a causal claim in a report names a check (§10.4), a parameter names the code that reads it
(§7). *"The vendor does not have it"*, *"no free source serves this"*, *"a fourth estimator would be
the same family"* — each passes every gate, and each permanently closes a search.

**The asymmetry is what makes this a section.** A wrong positive costs one wasted check. A wrong
impossibility costs everything downstream of it, silently, and is then cited as settled — the rows
in `HANDOFF.md` §7 exist specifically to stop work.

**What paid for it, 2026-08-24.** The evening run refused a block of candidates with *"a refetch did
not bring it current"*, which reads as *the vendor is late*. Re-asking the same vendor the same
evening, with the run's own request shape, returned every one of those sessions, clean. The refusal
was right and the explanation was wrong, and nothing had tested it because it read as a fact rather
than as a claim. The owner asked the question that found it.

The rules:

1. **An impossibility claim names the test that established it, or is marked untested.** §10.4's
   shape, aimed at *cannot* instead of *because*.
2. **A claim about what a SOURCE holds is tested against the source**, never inferred from what our
   code received. Those are different statements, and the second is a proxy (§12).
3. **A prediction is not a closure.** *"A fourth estimator would be the same family"* forecloses a
   search nobody ran. That belongs in the record as a prior, not as a `do not re-open` row.
4. **"Not the lever" is a measurement about ONE lever, never about the space.** Naming a better
   lever and stopping is how a lever gets parked without a decision — §14 says ask.
5. **A constraint that comes from the owner is a decision and stays closed.** D1, D10 and the
   charter non-goals are not impossibility claims and this section does not reopen them. The
   difference: a decision is *chosen*, an impossibility is *asserted about the world*.

**The goal is the result, by any legitimate means.** Where a route is legal, honest and reachable,
"we cannot" needs a measurement behind it before it is written down.

## 16. The course is a requirements source, not an evidence source — owner instruction, 2026-08-24

> *"Чек-листам не верь. Их писал не профессионал, любитель такой, как я. Лучше researchить интернет,
> трейдерские форумы, то, о чём реально успешные люди говорят... В книги, техническую научную
> литературу нам стоило бы отсылаться больше. У нас полный интернет информации, и мы не должны
> опираться только на наши бумажечки."*

**What does not change.** The course is still what this system is specified FROM. The component
catalogue, the controlled vocabulary, the checklists, `CHARTER.md` and gate 2's verbatim discipline
all rest on it, and none of that is weakened by this section. Transcribing it accurately still
matters exactly as much — an inaccurate copy of a weak source is worse than an accurate one.

**What changes is what a course sentence licenses.** A rule appearing in the course is an
`Operational Course Rule` — the vocabulary already has that claim type, alongside
`Untested Hypothesis` and `Empirical Result`. It is **not** an `Empirical Result`, and the fact that
it is written down here does not raise it. Appendix E's items are a competent amateur's list, and
their authority is that they name what to look at, never that looking there works.

**§10.3 said to search the outside world before AUTHORING. This extends it to ACCEPTING.** The
existing rule covers inventing an estimator; it never covered adopting a course rule as a design
constraint, which is how most of this system's shape was actually decided.

The rules:

1. **Before a course rule becomes a design constraint, look for what the literature says about it.**
   Journals, books, practitioners with a verifiable record. Cite what you find where it lands, the
   way §10.3 already requires for a borrowed method.
2. **Rank the source and say which rank you used.** Peer-reviewed or a published dataset outranks a
   practitioner with a track record, which outranks a forum post, which outranks an anonymous claim.
   A finding that rests on the bottom rank is marked as resting on it.
3. **§10.3's boundary is unchanged and it is the load-bearing half.** External work supplies
   *method*, *calibration* and *known limitations*. It is **not** evidence about this system's
   parameters: only a pre-registered study against this universe makes one `validated`. A famous
   trader's rule is a hypothesis here, exactly like the course's.
4. **Where the course and the literature disagree, record both and say which the system follows.**
   The disagreement is information; silently picking one and moving on destroys it.
5. **A checklist item with no external support is still worth keeping** — it costs a line and names
   something to look at. What it may not do is stand as the reason a threshold has its value.

**The asymmetry that makes this worth a section, and it is §15's.** Treating the course as evidence
costs nothing visible: every gate stays green, because the gates check that we copied it correctly,
not that it is true. There is no mechanism anywhere in this repository that can notice a faithfully
transcribed rule that does not work.

## 17. Verify at the right granularity — owner instruction, 2026-08-24

> *"Каждый мердж стоит нам 10-15-20 минут времени... Ты запускаешь мердж, сидишь, ждёшь, потом
> меняешь одно слово, снова запускаешь мердж и снова сидишь, ждёшь. Целый день так было."*

**The checks in this repository are strong and they are not free.** The full suite runs hundreds of
tests; a pull request costs several minutes of CI before `master` will accept it. Running either
after every edit converts a session into waiting.

1. **Run the check whose subject you touched.** A document edit is answered by `verify_docs.py`,
   `verify_counts.py` or `verify_project_manifest.py` in seconds. Reach for the whole suite once, on
   the batch, before committing — not after each edit inside it.
2. **Accumulate on one branch and merge once.** Three pull requests in an evening cost three CI
   waits; one costs one. `master` is protected and only advances on a green check, so the merge is a
   deliberate act with a price, not a save button.
3. **Never sit and watch CI.** If a pull request is open, keep working while it runs. The result
   arrives whether or not it is being watched.
4. **A local green suite is the real check.** CI exists so `master` cannot advance on an unproven
   commit; it is not the thing that tells you your change is right, and treating it as such buys
   confidence that the local run already gave you.

**What paid for it, 2026-08-24:** three merges in one evening, each with its own CI wait, one of
them for three regenerated numbers in a block that the same session then taught the scheduled run to
regenerate by itself. The check was correct every time. The granularity was not.

**Where this does NOT apply.** Anything touching `src/`, `tools/` or a frozen file gets the full
suite before it is committed — those are the changes a targeted check cannot bound, and §12's first
trap is a suite that went green while testing the wrong tree.
