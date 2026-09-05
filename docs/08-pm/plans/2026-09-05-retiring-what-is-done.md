# Retiring what is done, and re-verifying what is not

**Status:** owner-pending · **Tier:** 8 (PM) · **Written:** 2026-09-05

**The question this answers, from the owner:** *"Looks like we need a gate or better ruling in
`AGENTS.md`. Let's research, plan well and decide how to fix this behaviour and prevent future
reoccurrence. I would run the whole audit at least once a week. This must be the strongest part of
our research, otherwise we are constantly drifting."*

**The short answer: right about the disease, and the weekly audit is the expensive medicine for
it.** The measurements below say why, and what the cheap one is.

---

## 1. What was measured

### 1.1 The file

| | |
|---|---|
| `TODO.md`, 2026-08-15 | **198** lines |
| `TODO.md`, 2026-09-05 | **4,653** lines, 374 KB |
| open items | 63, occupying 1,951 lines |
| **closed items** | **105, occupying 2,669 lines** |
| longest closed entry | 125 lines |
| tool that retires anything | **none exists** |

**More than half the file is finished work**, and `AGENTS.md` §10.7 says `TODO.md` holds *"every
open item, and only open items"*. The rule already forbids what the file already is.

### 1.2 What it would cost to move them

**123 citations of `TODO.md` exist across `docs/`, `AGENTS.md`, `HANDOFF.md`, `src/` and `tools/`,
and every one of them points at a SECTION** — `§1`, `§5`, `§6b` — never at an individual item.
Migrating closed items while leaving the section headings in place therefore breaks no citation.

That was the expensive-looking part and it is not expensive. The reason to check rather than assume
is `AGENTS.md` §11 rule 3: consolidation is permitted only with a migration that moves every unique
obligation and updates every reference.

### 1.3 The audit

`docs/08-pm/plans/2026-08-12-complex-code-audit.md` exists, carries a copy-paste execution prompt,
and **there is no evidence it has ever been run**: no `audit_id`, no report, no evidence vault, no
commit referencing one.

---

## 2. The diagnosis, and it is not laziness

**`TODO.md` is doing two jobs and its contract names one.**

1. **The work list.** §10.7's contract: open items, nothing else.
2. **The place a finding's evidence gets written down while it is fresh** — the *"what paid for
   it"* paragraphs that make this repository's records worth reading.

The second job is why sessions close items **in place** instead of removing them: deleting the
entry would delete the only written account of what the defect cost. That instinct is correct, and
it is the habit `AGENTS.md` was built out of.

**What is missing is the step after it.** A closed finding's lesson has a home already — §12's trap
list, a decision record, or a gate — and the entry's job ends once the lesson is there. Nothing
says so, so nothing happens, and the file grows by roughly 330 lines a day.

**This is `§10.5`'s argument applied to prose instead of numbers.** §10.5 stopped counts rotting by
giving each one exactly one owner and making every other mention name the command. A closed entry
is a second copy of a lesson whose owner is elsewhere.

---

## 3. The proposal — three parts, in this order

The order matters: part 2 is not shippable before part 1, because a gate that fires 105 times on
the day it lands is a gate the operator learns to skip.

### 3.1 Migrate the closed entries — once

Move the 105 closed items to a closed-work document in Tier 8, preserving section structure,
and leave `TODO.md`'s section headings intact so the 123 existing citations keep resolving.

**The destination is deliberately not named here, and the gate is why.** A first draft of this
plan invented a filename for it and registered that name in the manifest and the document index.
Gate 3e refused it, and `verify_docs.PLANNED` carries the reason in its own comment: *"The
remaining absent sections have no agreed filename yet; naming one here would invent it."*
**A proposal that mints a document by mentioning it is how a plan becomes a commitment nobody
made.** The gate then refused the name a second time, in the sentence explaining why it had been
withdrawn — which is the check being exactly as literal as it should be. The name is the owner's
when the migration is approved.

**Before each entry moves, its lesson is promoted or dropped**, and that judgement is the work:

- a lesson that generalises goes to `AGENTS.md` §12's trap list;
- a lesson that is a decision goes to a `DR-NNN`;
- a lesson a check can hold goes to a gate — the best outcome, and the one §12's habit prefers;
- a lesson that is only *"this specific thing was fixed"* is dropped. **Git holds it.**

**Nothing here is a protected record.** §11 rule 2 protects decisions, ADRs, ratified criteria,
pre-registrations, reports, journal entries and evidence. A work list is none of those, and the
"correct forward, never delete" discipline was applied to it by inertia rather than by rule.

### 3.2 A gate, on an exact token

**Subject:** a `- [x] ` line in `TODO.md`.

This is the strongest gate subject available in this repository — stronger than most that exist.
`AGENTS.md` §12's standard for a check over text is *"an exact token, no prose parsed"*, and this is
a five-character literal at the start of a line. No English is interpreted, no judgement is made,
and the false-positive rate is structurally zero.

**Measured before proposing**, as §12's habit requires: 105 hits today, all true positives, and
after 3.1 the expected steady state is zero.

### 3.3 A rule in `AGENTS.md` §10.7

One sentence, and it is what makes the gate legal rather than arbitrary:

> **A closed item does not stay.** When an item closes, its lesson is promoted — to §12, to a
> decision record, or to a gate — and the entry is removed. The closed-work document keeps
> what is worth re-reading and git keeps the rest.

---

## 4. Where the weekly audit fits, and where it does not

**The owner is right that this is the disease.** Every finding of 2026-09-05 was a sentence that
was true when it was written: four expired blockers, a `read_by: none` on a parameter the code
reads, a classification store that stopped bounding its own answer, a coverage tier whose success
broke the sector cap. The `[v]` mark records that an item was verified **when written**, which is
precisely the failure mode it looks like a defence against.

**Three reasons the weekly full audit is the wrong first move.**

1. **It has never been run once.** Choosing a cadence before measuring a cost is the thing
   `AGENTS.md` §12 records rejecting three of four proposed mechanisms for. Run it once, measure
   it, then choose.
2. **§17 is a standing constraint, not a preference.** *"Every merge costs us 10-15-20 minutes"* is
   an owner instruction, and today already spent ~25 minutes on gate runs, ~61 minutes on a
   reproducibility measurement and ~25 on a pinned replay. A weekly audit adds to a bill the
   owner has already objected to.
3. **It is not what caught today's drift.** Every one of those findings came from *running the
   command the entry itself named*. None needed an audit; they needed something to re-run a claim.

**So: run the audit ONCE, on `master`, report-only, and let its measured cost choose the cadence.**
If it is an hour, weekly is cheap. If it is a day, weekly is a fantasy and monthly is the honest
answer.

---

## 5. The cheaper mechanism, and it is the one worth building

**The strongest thing in this repository is not a document; it is `read_by`.** A parameter's
unwired-ness is not asserted in prose — it is re-derived on every gate run, and gate 1 fails when
the assertion and the code disagree. That is why it does not rot.

**Every claim that rots is a claim no tool re-derives.** `tools/blocked_claims.py` already finds the
sentences; what it cannot do is check them, because an entry names its command in English.

**The proposal, and it is deliberately not built here:** an entry that asserts a state carries its
check in a machine-readable form — a fenced block a tool can execute and compare. Then re-verification
stops being a session's discipline and becomes a gate's job, which is the only thing that has ever
worked here.

**That is a design with a real cost and it needs its own measurement**, so it is named as the
direction rather than proposed as work. §12's habit applies to it as much as to anything: measure
the mechanism before shipping it, and be willing to throw it away.

---

## 6. What this plan does NOT propose

- **Deleting anything from `docs/prereg/`, `docs/decisions/`, `docs/adr/`, the journal, or the
  evidence record.** §11 rule 2 stands untouched.
- **Loosening §10.7.** The alternative to enforcing it — amend the rule to bless what the file has
  become — was considered and rejected: it would make the work list unreadable at the exact moment
  a fresh session most needs it, which is the cost §10.7 was written against.
- **A cadence for the audit.** That is the owner's, and it should be chosen from a measured run
  rather than from an estimate.
