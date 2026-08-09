# AGENTS.md — working guide for SwingDesk

Read this before changing anything. It is short on purpose.

**Starting a fresh session?** Read `HANDOFF.md` first — measured state, what is closed by evidence,
and what to do next in ranked order.

---

## 0. What this project is

Decision-support software for swing trading Canadian and US equities and ETFs, built from the
owner's 116-PDF course. **It never places orders.** See `README.md`, then `docs/README.md` for the
document set and gates.

The course is the requirements source. It supplies a complete governance and taxonomy specification
and **zero numeric thresholds**. Every threshold here is authored and carries its provenance.

### If you were told this is a documentation-only project, read this first

**`docs/` is canonical** (owner decision, 2026-08-04). So is `src/`, `tests/`, `registry/` and
`tools/` — 16 merge gates run from `python tools/check_gates.py` and they are what keep the
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

**Before writing any new specification, check whether `docs/` already holds it.** Five studies are
reported: three refuted, one inconclusive, one accepted and fragile — re-deriving them is not
neutral, it risks contradicting evidence that already exists.

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
docs/adr           decisions, append-only
registry/          course_index.yml · parameters.yml · criteria.yml
src/swingdesk/     nine bounded contexts
tools/             generators, checkers, probes
```

`registry/course_index.yml` is **generated** — never hand-edit it. `registry/criteria.yml` is
**frozen** at v1.0.0; changing it is an amendment, not an edit.

## 5. Conventions

- **English throughout** — docs, code, UI. The course's controlled vocabulary (`Trade`/`Watch`/
  `Skip`/`Pause`, the skip and error codes, `STAGE`/`LAYER`/`CLAIM TYPE`) is used verbatim and never
  translated.
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
