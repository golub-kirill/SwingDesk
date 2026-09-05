# What Watches the Root Documents Implementation Plan

**Status:** owner-pending · **Tier:** 8 (PM) · **Written:** 2026-09-05

> **For agentic workers:** execute this plan serially, or with
> `subagent-driven-development` only when the owner explicitly authorises delegated execution.
> Track execution in a copied run ledger, not by editing this approved plan — the convention
> `2026-08-12-complex-code-audit.md` sets.

**Goal:** Put `TODO.md` under the two document gates that have never seen it, and record the three
measurements that say a document-retirement finder should not be built.

**Architecture:** `verify_docs.py` and `verify_study_summary.py` both scan `docs/**` plus a
three-entry `ROOT_DOCS` tuple that does not include `TODO.md`. Adding it surfaces twelve findings
immediately, of which three are real defects and one is a **wrong count about the research record**.
The work is: fix the defects first, then widen the scan, so neither gate lands red.

**Tech Stack:** Python 3.14 stdlib plus PyYAML, the project's own gate runner, pytest.

## Global Constraints

- **`AGENTS.md` §4: a document goes in a tier, never in a directory named after the tool that made
  it.** This plan is in `docs/08-pm/plans/` for that reason — the `writing-plans` skill's default
  once produced a top-level directory named after a plugin, and §4 exists because of it.
- **`AGENTS.md` §10.5: a measured count lives in exactly one place**, `HANDOFF.md` §2. Every count
  below names the command that derives it.
- **`AGENTS.md` §11 rule 2: never delete a protected record.** Decisions, ADRs, ratified criteria,
  pre-registrations, reports, journal entries and evidence are corrected forward.
- **`CI_POLICY.md` §3: a check over text needs an exact token** or it becomes noise.
- **Run the gates once, at the end, on the batch** (`AGENTS.md` §17), not after each step.
- Every command is run with the project venv: `PYTHONPATH=$PWD/src` and the interpreter named
  absolutely.

---

## 1. The research, and it killed the obvious design

**The brief was a retirement system for documents: something that finds a document that should go.
Three candidate signals were measured on 2026-09-05 and all three are dead.**

| signal | hits | verdict |
|---|---|---|
| cited by no other file, **by filename** | 42 of 145 | **wrong** — they are decision records and ADRs, cited by **id** |
| cited by neither filename **nor id** | **0** of 145 | there is no orphan document in this repository |
| untouched for 30+ days | 35 of 145 | **wrong** — the repository is ~35 days old; a spec that has not changed is healthy, and the bucket contains published study reports, which must never change |
| `planned` in the manifest and never written | 4 | all Tier 7, all deferred to project gate G7, all recorded in `verify_docs.PLANNED` with a reason |

```bash
PYTHONPATH=$PWD/src python tools/verify_project_manifest.py   # the manifest census
```

**So no document-retirement finder is proposed, and that is the finding rather than a gap.**
`AGENTS.md` §12's habit is explicit — measure the mechanism before shipping it and be willing to
throw it away; three of four were rejected on their own numbers on 2026-08-25. This is the fourth
through seventh.

**What makes documents different from the work list**, which DID need one: every document has a row
in `registry/project_manifest.yml`, a status on a ladder, a tier, and gates 3e and 15 keeping the
index and the tree in step. `TODO.md` had none of that, which is why it grew to 57% finished work.

**Research withdrawal is deliberately out of scope.** `AGENTS.md` §12 states the hole — *"no gate
sees a withdrawn verdict"* — and `docs/prereg/README.md` and `verify_study_summary.py` contain no
`withdraw` or `superseded` vocabulary at all. That is a protected-record mechanism and a separate
plan.

## 2. The hole that does exist

`verify_docs.py:141` and `verify_study_summary.py:38` both read:

```python
ROOT_DOCS = ("README.md", "AGENTS.md", "HANDOFF.md")
```

**`TODO.md` is not there, so neither gate has ever read it.** Measured by patching a copy of each
tool and running it:

| gate | findings in `TODO.md` |
|---|---|
| 3e `verify_docs.py` | 5 |
| 13 `verify_study_summary.py` | 7 |

**And they are not cosmetic.** Three sentences state a number of reported studies that the
record contradicts — a wrong count about the research record, sitting in the open-work list,
and the gate prints both figures when it runs. Two dead citations follow it: one to a study
report that does not exist and one to a deleted dated handoff.

---

## File Structure

| file | responsibility |
|---|---|
| `TODO.md` | fixed: two dead citations, the study counts, two `module.function` spellings, the status line |
| `tools/verify_docs.py` | `ROOT_DOCS` gains `TODO.md`; the status-ladder check learns that a root work list has no tier status |
| `tools/verify_study_summary.py` | `ROOT_DOCS` gains `TODO.md` |
| `tests/test_gates.py` | one test per widening, each proven to fail without it |

---

### Task 1: Fix what gate 3e finds in `TODO.md`

**Files:**
- Modify: `TODO.md`
- Test: none — this task changes prose only, and Task 3 is what pins it

**Interfaces:**
- Consumes: nothing
- Produces: a `TODO.md` that `verify_docs.py` accepts once Task 3 widens its scope

- [ ] **Step 1: See the findings before changing anything**

```bash
PYTHONPATH=$PWD/src python - <<'PY'
PY
```

Do **not** use a heredoc — `AGENTS.md` §12 forbids piping a script into an interpreter, and it has
cost this project a truncated runbook and a gate that could never match. Instead copy
`tools/verify_docs.py` to `tools/_tmp_verify_docs.py`, add `"TODO.md"` to its `ROOT_DOCS`, run it,
and delete the copy:

```bash
PYTHONPATH=$PWD/src python tools/_tmp_verify_docs.py
```

Expected, five lines:

```
TODO.md: cites PR-007-report.md, which does not exist and is not planned
TODO.md: cites SESSION-HANDOFF-2026-08-24.md, which does not exist and is not planned
TODO.md: cites parameter 'universe.to_instrument', absent from the registry
TODO.md: cites parameter 'universe.vendor_symbol', absent from the registry
TODO.md: status 'working' is outside the ladder [...]
```

- [ ] **Step 2: Correct the two dead citations**

The missing study report — check whether it exists under another name before rewriting
anything, using the name the gate printed:

```bash
ls docs/prereg/results/ | grep -i pr-007
```

If it does not exist, the citation is a claim about the research record and must be corrected
forward, not deleted: strike the filename and say what is actually there. If it does, fix the name.

The other is a deleted dated handoff — `AGENTS.md` §10.7 records that those were created and
deleted faster than anything could cite them safely. Keep the provenance fact and drop the
backticks, so the sentence records where the text came from without claiming the file is
there to read:

```markdown
Migrated here from the dated session handoff of 2026-08-24, §N, before that file was deleted
```

- [ ] **Step 3: Write the two function references the way the rest of the repository writes them**

`PARAM_REF` in `verify_docs.py` is `` `([a-z_]+\.[a-z_0-9]+)` `` and cannot tell a backticked
`module.function` from a parameter id like `universe.min_price`. Step 1's output names the two;
they are not repeated here, because writing one in the form the gate reads would make this plan
a document citing a parameter that does not exist. A function written with its parentheses is
both clearer and unambiguous:

```markdown
`universe.to_instrument()`   `universe.vendor_symbol()`
```

- [ ] **Step 4: Re-run and confirm only the status finding remains**

```bash
PYTHONPATH=$PWD/src python tools/_tmp_verify_docs.py
```

Expected: one line, the `status 'working'` one. Task 3 decides that one.

- [ ] **Step 5: Delete the temporary copy and commit**

```bash
rm tools/_tmp_verify_docs.py
git add TODO.md
git commit -m "Two dead citations and two function spellings in the open-work list"
```

---

### Task 2: Fix the study counts gate 13 finds

**Files:**
- Modify: `TODO.md`
- Test: none — Task 3 pins it

**Interfaces:**
- Consumes: nothing
- Produces: a `TODO.md` whose study claims match the record

- [ ] **Step 1: See them**

Copy `tools/verify_study_summary.py` to `tools/_tmp_verify_studies.py`, add `"TODO.md"` to its
`ROOT_DOCS`, and run it:

```bash
PYTHONPATH=$PWD/src python tools/_tmp_verify_studies.py
```

Expected, seven lines. Three of them have the same shape — a spelled-out number of reported
studies against the number the record actually holds, with both figures printed. The line is
not reproduced here for the reason Task 1 Step 3 gives: quoting it verbatim would make this
plan carry the wrong count it exists to remove.

- [ ] **Step 2: Derive the truth, never copy it from the gate's message**

```bash
PYTHONPATH=$PWD/src python tools/verify_study_summary.py
```

The line reading `studies: registered=N reported=N refuted=N accepted=N` is the record.

- [ ] **Step 3: Replace each count with the command that derives it**

`AGENTS.md` §10.5: a measured count lives in exactly one place and every other mention names the
source. So the fix is **not** to write `eight` — that rots the same way. Each sentence becomes:

```markdown
the reported studies (`python tools/verify_study_summary.py` prints the census)
```

**Striking the line through does NOT work here, and finding that out cost this plan a gate
run.** `verify_counts.py` (gate 14) has a `HISTORICAL` pattern that accepts `~~…~~` or
`DONE`/`CLOSED`/`REACHED` with a date; **gate 13 has no such concept** and matches the phrase
wherever it appears — including inside a fenced block, and including in a sentence explaining
that it is history. Two gates over the same kind of subject with different escape hatches is
worth knowing before you try the wrong one.

So for a sentence that is genuinely about a past state, the numeral goes and the date stays:

```markdown
the reported studies as they stood on 2026-08-24 (`python tools/verify_study_summary.py`)
```

- [ ] **Step 4: Re-run and confirm zero**

```bash
PYTHONPATH=$PWD/src python tools/_tmp_verify_studies.py
```

Expected: no line mentioning `TODO.md`.

- [ ] **Step 5: Delete the copy and commit**

```bash
rm tools/_tmp_verify_studies.py
git add TODO.md
git commit -m "The open-work list carried a wrong count of the research record"
```

---

### Task 3: Widen both gates, with the status-ladder decision made explicitly

**Files:**
- Modify: `tools/verify_docs.py:141`, `tools/verify_study_summary.py:38`
- Test: `tests/test_gates.py`

**Interfaces:**
- Consumes: a `TODO.md` cleaned by Tasks 1 and 2
- Produces: `ROOT_DOCS = ("README.md", "AGENTS.md", "HANDOFF.md", "TODO.md")` in both tools

- [ ] **Step 1: Write the failing test**

Append to `tests/test_gates.py`:

```python
def test_gate_3e_reads_the_open_work_list(tmp_path) -> None:
    """`TODO.md` was outside both document gates until 2026-09-05, and 2,557 lines of it had
    never been checked by either. A dead citation there is the same defect as one in a spec."""
    (tmp_path / "docs").mkdir()
    absent = "MISSING_SPEC.md"          # built, not written literally: a plan that spells
    tick = chr(96)                      # out a dead citation IS a document with one
    (tmp_path / "TODO.md").write_text(
        f"**Status:** working document\n\nSee {tick}{absent}{tick}.\n", encoding="utf-8"
    )
    (tmp_path / "registry").mkdir()

    code, out = run_gate("verify_docs.py", tmp_path)

    assert absent in out
    assert code == 1
```

- [ ] **Step 2: Run it and watch it fail**

```bash
PYTHONPATH=$PWD/src python -m pytest tests/test_gates.py -q -k open_work_list
```

Expected: FAIL — the gate never opens `TODO.md`, so the citation is not reported.

- [ ] **Step 3: Widen `ROOT_DOCS` in both tools**

In `tools/verify_docs.py` and `tools/verify_study_summary.py`:

```python
#: `TODO.md` joined on 2026-09-05. It had been outside both gates since they were written, so
#: 2,557 lines of the open-work list were unchecked - and the first run found two dead citations
#: and three claims about the number of reported studies that the record contradicted.
ROOT_DOCS = ("README.md", "AGENTS.md", "HANDOFF.md", "TODO.md")
```

- [ ] **Step 4: Decide the status ladder, and record the decision inline**

`TODO.md`'s header reads `**Status:** working document`, which is not on the ladder
`['drafting', 'frozen', 'generated', 'owner-pending', 'planned']`. Two honest options, and the
second is recommended:

1. Change `TODO.md`'s header to `drafting`. Cheap, and wrong: `TODO.md` is not a tier deliverable
   and has no lifecycle to be on the ladder.
2. Skip the status check for `ROOT_DOCS`. The ladder is a property of a **tier document**, and
   `README.md`, `AGENTS.md` and `HANDOFF.md` are already exempt only by accident — they happen to
   carry no `**Status:**` line.

Implement option 2 in `verify_docs.py`, at the status check:

```python
        # The ladder is a property of a TIER document. A root file - the readme, the rulebook, the
        # handoff, the work list - has no tier and no lifecycle, and `TODO.md` is the first one to
        # carry a `**Status:**` line at all, which is how this surfaced.
        if rel not in {name for name in ROOT_DOCS}:
            for status in STATUS_LINE.findall(body):
                ...
```

- [ ] **Step 5: Run the test and watch it pass**

```bash
PYTHONPATH=$PWD/src python -m pytest tests/test_gates.py -q -k open_work_list
```

Expected: PASS.

- [ ] **Step 6: Mutate and prove the test dies**

Revert `ROOT_DOCS` to the three-entry tuple, re-run, confirm the new test fails and nothing else
does, then restore it. `AGENTS.md` §18 step 4: a test that passes with the fix removed is
decoration.

- [ ] **Step 7: Run the whole suite once, then commit**

```bash
SWINGDESK_DATA=C:/PycharmProjects/SwingDesk/data PYTHONPATH=$PWD/src python tools/check_gates.py
```

Expected: every gate green except any already red for its own reason. Then:

```bash
git add tools/verify_docs.py tools/verify_study_summary.py tests/test_gates.py
git commit -m "The open-work list was outside both document gates"
```

---

### Task 4: Record the three dead signals so nobody re-derives them

**Files:**
- Modify: `AGENTS.md` §12
- Test: `PYTHONPATH=$PWD/src python tools/verify_rules_index.py`

**Interfaces:**
- Consumes: the measurements in §1 of this plan
- Produces: one trap in §12

- [ ] **Step 1: Add the trap**

Insert into §12's trap list, before `**The habits:**`:

```markdown
- **A document nobody cites is not a retirement candidate here, and the measurement is why.**
  Searching for a document no other file mentions returns **42 of 145** — and they are almost all
  decision records and ADRs, which everything cites by **id** (`DR-012`, `ADR-0004`) and nothing
  cites by filename. Counting ids too returns **zero**. The staleness signal is worse than useless:
  35 documents are 30+ days untouched in a repository about 35 days old, and the bucket holds
  published study reports, which must never change. **Three signals, no true positives** — a
  document-retirement finder was measured and not built (2026-09-05).
```

- [ ] **Step 2: Confirm the rules index still balances**

```bash
PYTHONPATH=$PWD/src python tools/verify_rules_index.py
```

Expected: `27 section(s), 27 row(s), 0 failure(s)` — §12 is one row, and adding a bullet does not
change the index.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "Three signals for a document-retirement finder, all measured dead"
```

---

## Self-review

**Spec coverage.** The brief asked for a mechanism that finds a retirement candidate and the
discipline for retiring one. §1 answers the first with three measurements saying no such candidate
exists; the discipline already exists in `CHANGE_MANAGEMENT.md` §5 and `AGENTS.md` §11 and is
untouched. Research withdrawal is excluded and says so.

**Placeholders.** None: every step carries the command or the text to write, and Task 1's step 1
names the forbidden heredoc explicitly rather than leaving the engineer to discover §12's rule.

**Type consistency.** `ROOT_DOCS` is the same tuple name in both tools. The test defined in
Task 3 Step 1 is selected in Steps 2, 5 and 6 by the same `-k open_work_list` argument, and its
name appears only inside the code block that defines it — a plan may not backtick a test that
does not exist yet, which is gate 35 refusing an earlier draft of this very sentence.

**One risk worth naming.** Task 3 widens two gates over a 2,146-line file that no gate has read.
The twelve findings above were measured on the file as it stands, so Tasks 1 and 2 bound the work —
but a future edit to `TODO.md` now lands in scope, which is the point and also a cost.
