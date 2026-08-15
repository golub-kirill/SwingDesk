# SwingDesk Complex Code Audit Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` only when the owner explicitly authorises delegated execution; otherwise execute this plan serially and preserve the same evidence boundaries. Track execution with checkboxes in a copied run ledger, not by editing this approved plan.

**Goal:** Produce a defensible, reproducible audit of any locally available SwingDesk Git ref, with `master` as the default, and determine whether its decision-support behavior, engineering implementation, and research claims are actually assured by evidence.

**Architecture:** Resolve the requested ref once, freeze its full commit and tree hashes, and audit that immutable snapshot in a pristine detached worktree. Keep harnesses, raw evidence, and reports outside the subject worktree. Discover the frozen snapshot's capabilities before selecting applicable tests. Use independent oracles, adversarial fixtures, fault injection, hostile persistence tests, explicit mutants, and recoverability drills. Report findings before any remediation work.

**Tech stack:** The frozen snapshot's declared Python and dependency matrix; Git; PowerShell; the project's own gates and tests; independent Python audit harnesses; disposable database and data copies; static analyzers only as corroborating instruments. Tool paths, versions, hashes, and availability are measured at audit time rather than assumed here.

**Default target:** local `master`. The operator may supply any local branch, tag, or commit expression that resolves to a commit. The audit never fetches, pulls, or silently changes the requested ref.

**Output:** A local-only evidence branch and an external raw-evidence vault keyed by `audit_id`, ending in an executive report, detailed findings, obligation matrix, command ledger, evidence manifest, dismissed-alert ledger, and remediation plan. No audit branch or evidence vault is pushed unless the owner separately authorises publication.

---

## Copy-paste execution prompt

```text
Perform the SwingDesk complex code audit defined in
docs/08-pm/plans/2026-08-12-complex-code-audit.md.

Inputs:
- repository: the current SwingDesk repository
- target_ref: master, unless I explicitly provide another local Git ref
- network_mode: offline by default; public data feeds only when a planned test requires
  them and the run ledger records the opt-in; never use broker credentials
- remediation_mode: report-only; do not fix the audited snapshot

Hard rules:
1. Resolve target_ref locally to a full commit SHA and tree hash at audit start. Never fetch,
   pull, or substitute another ref. If the ref later moves, finish the pinned commit and mark
   TARGET_MOVED; never mix evidence from the new tip.
2. Audit a pristine detached subject worktree. Put harnesses and results in a separate local-only
   evidence worktree/repository and raw vault. Abort a subject command unless cwd, HEAD, tree,
   and tracked cleanliness match the evidence manifest.
3. Treat the current checkout's branch, dirtiness, ahead/behind state, and sibling worktrees as
   context only. They must not change the frozen subject or its verdict.
4. Discover the target's documents, registries, entry points, stores, studies, schedulers,
   adapters, declared runtimes, and supported markets before selecting tests. Mark each audit
   module APPLICABLE, NOT_APPLICABLE with obligation-based justification, or UNAVAILABLE.
5. Use the three non-compensatory verdict domains: Decision Safety, Engineering Quality, and
   Research Integrity. A domain is PASS only when every mapped critical obligation has an
   executed, preserved test. Critical FAIL, ERROR, or UNAVAILABLE means NOT_ASSURED. Do not use
   totals, percentages, coverage numbers, or scanner scores to compensate for a critical defect.
6. Separate observed product FAIL from test-harness ERROR. Preserve exact inputs, stdout,
   stderr, exit code, environment, executable/dependency hashes, and output hashes for every run.
7. Do not accept a scanner alert as a finding. Reproduce it or dismiss it with evidence. Every
   retained finding needs a stable ID, obligation, affected path/symbol, minimal reproducer,
   observed and required behavior, concrete impact, falsification condition, remediation, and
   regression test.
8. Exercise real entry paths and persisted state, not only isolated helpers. Use copies of data
   and databases; never mutate the owner's live data. Do not place orders or add order capability.
9. Audit all studies and research claims discovered in the frozen target; do not rely on a fixed
   list of study IDs. Missing historical evidence is a limitation, not permission to reconstruct it.
10. Complete and self-review all required artifacts before presenting a verdict. Report findings
    first. Put proposed fixes in a separate remediation sequence tied to the frozen SHA.

Return:
- the frozen target SHA/tree and any TARGET_MOVED notice
- the capability and obligation matrices
- the three domain verdicts and overall release recommendation
- findings ordered by decision impact
- exact links/paths to the report, evidence manifest, command ledger, raw-evidence vault,
  dismissed-alert ledger, and remediation plan
- a short list of tests that were UNAVAILABLE and what authority or dependency is needed
```

---

## Audit contract

### Subject identity

The operator supplies:

```text
repo_root  = local SwingDesk repository root
target_ref = any local ref resolving to a commit; default master
audit_root = external writable directory for raw evidence
```

Resolve and record:

```text
target_sha  = git rev-parse --verify <target_ref>^{commit}
tree_hash   = git rev-parse <target_sha>^{tree}
audit_id    = <UTC-date>-<target_sha first unambiguous prefix>
target_name = the exact operator-supplied ref string
```

The report's verdict is always phrased as “commit `<target_sha>` is … under the executed audit scope.” It must never claim that `master` is generically safe after the ref has moved.

### What is allowed to vary

Any of these states are valid audit inputs rather than reasons to weaken the audit:

- the requested ref is ahead, behind, divergent, or unrelated to the current checkout;
- the current checkout is dirty or on another branch;
- native tests or gates fail;
- code, documentation, studies, adapters, or operational tooling are incomplete;
- optional dependencies or external services are absent;
- the target uses a different supported runtime or dependency set;
- the target ref moves after it is frozen.

Abort only when the requested ref does not resolve locally, the object cannot be materialized, subject integrity cannot be established, or the evidence store cannot preserve trustworthy output. Record the condition as an audit ERROR.

### Snapshot and evidence separation

Use three physically distinct locations:

```text
subject worktree    detached, pristine, read-only by policy, exactly target_sha
evidence worktree   local branch for harness code and reviewable reports
raw evidence vault  external, access-restricted, not committed to Git
```

The subject command wrapper must refuse execution unless all of these are true:

- current directory resolves under the recorded subject root;
- `HEAD` equals `target_sha`;
- `HEAD^{tree}` equals `tree_hash`;
- `git status --porcelain --untracked-files=no` is empty;
- the command and environment are written to the ledger before execution;
- stdout, stderr, exit code, start/end UTC times, and output hashes are written after execution.

Harnesses may import or invoke the subject, but must not be stored inside the subject. Tests that require mutations run against a fresh disposable copy of the subject and label every resulting artifact `MUTANT`, never as evidence of the pristine tree's bytes.

### Verdict domains

The audit has three non-compensatory domains:

| Domain | Question |
|---|---|
| Decision Safety | Can the software expose an incorrect, stale, cross-market, unauditable, or unsafe trading-support conclusion as current or actionable? |
| Engineering Quality | Is the system correct, deterministic, secure, maintainable, operable, and recoverable under its declared conditions? |
| Research Integrity | Are requirements, parameters, studies, validation labels, and causal claims traceable to preserved evidence without leakage or unsupported inference? |

Check status is one of:

| Status | Meaning |
|---|---|
| PASS | The obligation was exercised and the preserved result meets its oracle. |
| FAIL | The product was exercised and violated the oracle. |
| ERROR | The audit instrument could not produce a trustworthy observation. |
| UNAVAILABLE | A required capability, dependency, service, or historical artifact was unavailable. |
| NOT_APPLICABLE | The obligation does not apply to the frozen snapshot, with exact evidence and rationale. |

A domain is `PASS` only when every mapped critical obligation has an executed PASS result. Any critical FAIL, ERROR, or UNAVAILABLE makes the domain `NOT_ASSURED`. NOT_APPLICABLE cannot be used merely because implementation is missing: if the snapshot claims or requires the capability, absence is FAIL or UNAVAILABLE according to the oracle. There is no weighted score and no quantity of weaker positives can clear a critical failure.

### Finding quality gate

Every finding must contain:

```text
finding_id
domain and severity
exact obligation and source
target_sha and affected path/symbol
preconditions and minimal reproducer
preserved evidence identifiers
observed behavior
required behavior / independent oracle
decision, operational, or research impact
scope and exploitability/reachability
what evidence would falsify the finding
recommended remediation
required regression test
```

Static-analysis output, test counts, line coverage, complexity values, mutation percentages, and dependency alerts are leads. They become findings only after reachability and concrete impact are established. Preserve rejected leads in `dismissed-alerts.md` with the dismissal evidence.

---

## Required artifact layout

Create paths from `audit_id`; do not reuse an earlier audit directory.

```text
<raw-evidence-vault>/<audit_id>/
  manifest.json
  commands.jsonl
  environment/
  raw/
  fixtures/
  outputs/
  hashes/
  sensitive/

<evidence-worktree>/docs/08-pm/audits/<audit_id>/
  README.md
  executive-report.md
  capability-matrix.md
  obligation-matrix.md
  findings.md
  dismissed-alerts.md
  unavailable-tests.md
  remediation-plan.md
  evidence-index.json

<evidence-worktree>/tools/audit/
  guard_subject.py
  run_ledger.py
  discover_capabilities.py
  build_obligation_matrix.py
  domain_oracles.py
  fault_harness.py
  persistence_model.py
  determinism_harness.py
  research_harness.py
  mutation_harness.py
  recoverability_harness.py
  verify_evidence.py
```

The exact harness modules may be consolidated when the target makes that clearer, but each required responsibility must remain independently identifiable and tested. Raw evidence stays outside Git. Reviewable reports contain only redacted excerpts and content hashes.

Sensitive secret-scan results go under `sensitive/`. Store only redacted paths and an HMAC fingerprint in the report; never commit a discovered secret or its reversible hash. The HMAC key stays outside both worktrees.

---

## Task 1: Establish the local audit boundary

**Inputs:** `repo_root`, optional `target_ref`, external `audit_root`.

**Creates in the evidence worktree:** `manifest.json` schema, subject guard, command ledger, evidence verifier.

**Procedure:**

- [ ] Run `git worktree list --porcelain`, `git branch -a`, and `git status --short --branch` in the ambient checkout. Preserve output as context, not subject evidence.
- [ ] Resolve the exact operator-supplied ref locally. Default only an omitted value to `master`; never reinterpret an invalid value as `master`.
- [ ] Record the full commit SHA, tree hash, commit parents, commit timestamp, exact ref string, and whether the ref is symbolic.
- [ ] Create a detached subject worktree at that SHA and verify its tracked tree is pristine.
- [ ] Create a separate `codex/audit-<audit_id>` evidence branch/worktree. Remove or disable its push remote if practical; record the result.
- [ ] Create the external raw vault and initialize its append-only command ledger.
- [ ] Capture OS, architecture, locale, timezone, shell, Git, executable paths, executable hashes, environment-variable names, and redacted dependency metadata.
- [ ] Implement and test the subject guard. Include negative tests for wrong cwd, wrong HEAD, dirty tracked file, mismatched tree, and missing manifest.
- [ ] Hash the manifest and initial ledger. Make evidence verification fail on a changed byte, missing output, reordered command record, or unredacted secret fixture.

PowerShell reference commands:

```powershell
$TargetRef = if ($env:SWINGDESK_AUDIT_REF) { $env:SWINGDESK_AUDIT_REF } else { 'master' }
$TargetSha = (git -C $RepoRoot rev-parse --verify "$TargetRef`^{commit}").Trim()
$TreeHash = (git -C $RepoRoot rev-parse "$TargetSha`^{tree}").Trim()
git -C $RepoRoot cat-file -e "$TargetSha`^{commit}"
git -C $RepoRoot worktree add --detach $SubjectRoot $TargetSha
git -C $SubjectRoot status --porcelain --untracked-files=no
```

**Acceptance:** The guard demonstrably prevents a command from running on anything except the pinned clean subject. The manifest can recreate the subject identity without relying on a branch name. Evidence tampering is detected.

**Movement rule:** Check the original `target_ref` again at every phase boundary. If it resolves to another SHA, add `TARGET_MOVED` with both SHAs and time; continue only against the original pinned SHA.

---

## Task 2: Discover capabilities and build the obligation map

**Reads from the subject:** `AGENTS.md`, `HANDOFF.md`, root README, document index, canonical requirements, architecture, policies, registries, source, tests, tools, wrappers, configuration, schedulers, data schemas, dependency declarations, and Git history reachable from `target_sha`.

**Produces:** `capability-matrix.md`, `obligation-matrix.md`, machine-readable discovery JSON, and an initial test manifest.

- [ ] Discover canonical sources rather than assuming current paths exist. Resolve duplicate or conflicting documents by the target's own governance rules and flag unresolved authority.
- [ ] Enumerate application entry points: CLI commands, batch/PowerShell wrappers, scheduled paths, callable APIs, backtest/study runners, migration utilities, and manual operational procedures.
- [ ] Enumerate bounded contexts, state stores, external adapters, clocks/calendars, configuration/parameter loaders, decision objects, position-management paths, logging, backup/restore, and output surfaces.
- [ ] Enumerate all registered, preregistered, reported, withdrawn, superseded, or referenced studies dynamically. Do not start from hardcoded study IDs.
- [ ] Enumerate declared Python/runtime versions and dependency locks. The test matrix is derived from the frozen snapshot plus the detected operational runtime.
- [ ] Trace each critical requirement to implementation, tests, runtime path, and evidence. Use the code knowledge graph as a pointer when available, then verify every assertion in the actual file.
- [ ] Classify every audit module APPLICABLE, NOT_APPLICABLE, or UNAVAILABLE with exact evidence.
- [ ] Mark missing or contradictory canonical requirements as `NOT_ASSESSABLE`; do not invent an oracle.
- [ ] Map every non-negotiable obligation, including no order placement, fail closed, unset is not default, validation labels travel with outputs, immutability/versioning, non-compensatory critical gates, and market separation.

**Acceptance:** Every critical obligation has an oracle, planned test, evidence destination, and domain owner. Every discovered entry path and study appears in at least one row. No row is closed by a document claim alone.

---

## Task 3: Establish the native baseline without mistaking it for assurance

**Produces:** native command results, declared-runtime matrix, baseline failures, and coverage-to-obligation mapping.

- [ ] Install or select dependencies exactly as declared by the frozen snapshot in isolated environments. Record executable/dependency hashes and lock resolution.
- [ ] Run every native verifier, generated-file check, linter, type checker, unit/integration suite, and build command discoverable from canonical policy.
- [ ] Run under every runtime version declared or supported by the target, plus the actual operational runtime when detectable.
- [ ] Preserve complete output and separate product FAIL from environment/harness ERROR.
- [ ] Map native tests to obligations and entry paths. Identify critical obligations that have only structural, mocked, or helper-level coverage.
- [ ] Treat missing tools and unsupported environments as UNAVAILABLE; never silently omit them or convert them into PASS.
- [ ] Record flaky or order-dependent behavior by repeating failures from pristine environments with fixed and varied seeds.

**Acceptance:** A reviewer can reproduce the native baseline with the recorded environment. Native green status is described as baseline evidence only; it cannot close adversarial obligations by itself.

---

## Task 4: Audit architecture, reachability, and decision attack surface

**Produces:** verified call/entry graph, trust-boundary diagram, state-transition inventory, and dead/bypassed-control findings.

- [ ] Trace each real entry path from wrapper or CLI through configuration, stores, data adapters, screening, open-position management, decision construction, persistence, reports, logs, and exit code.
- [ ] Compare documented architecture to import/call/runtime reality. Confirm with file reads and executable smoke traces.
- [ ] Locate duplicated decision logic, hidden defaults, global state, direct clock access, binary-float money, unversioned configuration, and code that bypasses validation or persistence.
- [ ] Identify code that appears unused, but check dynamic entry points, schedulers, tests, report-linked runners, configuration, and Git history before classifying it.
- [ ] Prove no reachable path can place an order or communicate order instructions to a broker. Search configuration, dependencies, network adapters, CLI surfaces, and dormant code.
- [ ] Build state machines for candidate decisions, open positions, refusals/pauses, run lifecycle, study lifecycle, and record correction/versioning.
- [ ] Identify each place where one market, currency, calendar, benchmark, breadth series, or universe could contaminate another.

**Acceptance:** Every critical runtime and research path is either reached by a later dynamic test or explicitly UNAVAILABLE. Architecture mismatches are findings only when their behavioral or maintenance impact is demonstrated.

---

## Task 5: Build independent domain oracles

**Creates:** pure audit-side reference calculations and golden/adversarial fixtures; never copies subject implementation.

- [ ] Derive each oracle from canonical requirements, cited external method definitions, exchange rules, or a deliberately tiny hand-computable fixture.
- [ ] Cover all discovered decision-relevant calculations: indicators, trend/pattern eligibility, completeness, freshness, risk sizing, exact money/currency arithmetic, transaction costs, reward/risk, stop/gap/time-exit priority, portfolio constraints, calendar/session behavior, and universe membership.
- [ ] Use Decimal or integer minor units for money and injected clocks for time.
- [ ] Include boundary, tie, zero, negative, missing, stale, malformed, duplicated, out-of-order, revised, cross-currency, and overflow/extreme fixtures.
- [ ] For authored/unset parameters, verify provenance and refusal behavior rather than supplying a convenient value.
- [ ] Compare whole decision objects and traces, not only final labels.
- [ ] Prove each oracle can reject a known bad implementation through a targeted synthetic mutant.

**Acceptance:** Oracles are implementation-independent, cite their authority, detect targeted bad behavior, and have preserved fixtures. An oracle copied from the product does not count.

---

## Task 6: Exercise the real daily and open-position paths

**Produces:** seeded-copy end-to-end traces and a fault matrix covering all discovered operational entry paths.

- [ ] Run the actual scheduled wrapper and CLI path against a disposable seeded data directory and databases.
- [ ] Seed open positions plus candidates. Prove positions are loaded, evaluated before new candidates, proposed, reported, journaled, and persisted through the real path.
- [ ] Confirm wrapper exit codes, environment propagation, encoding, working-directory assumptions, and log destination.
- [ ] Inject vendor failure for one held position with valid cache, stale cache, truncated latest session, malformed data, calendar error, no cache, and mixed success across several positions.
- [ ] Inject configuration conflict, unset critical parameter, store-open failure, journal-write failure, output-write failure, and interruption between lifecycle transitions.
- [ ] Require every unevaluable position to remain visible with a coded PAUSE/refusal/manual-reconciliation record. Candidate work must never erase, precede, or mask position risk.
- [ ] Verify stale facts are never presented as current and a fallback states its source, age, and limitation.
- [ ] Confirm no real user data or broker endpoint is touched by inspecting paths and network destinations before and after each run.

**Acceptance:** The real operational entry path satisfies fail-closed and open-position priority behavior. Helper-only success does not compensate for missing CLI or scheduler wiring.

---

## Task 7: Attack point-in-time, availability, and market-time semantics

**Produces:** adversarial as-of fixtures, query results, full decision traces, and leakage findings.

- [ ] Test event time, source publication/session-close time, ingestion/knowledge time, query as-of time, and later revision time independently.
- [ ] Request a past decision while the store contains future bars, post-decision directory pulls, later revisions, and future session closes.
- [ ] Exercise every discovered live-as-of or fresh-fetch mode. A retrieval performed later must never be backdated as known at the requested instant.
- [ ] Test late-arriving bars, corrected bars, duplicated timestamps, non-session timestamps, timezone/DST boundaries, half-days, holidays, and calendar-package failure or version drift.
- [ ] Require prefix invariance: adding facts unavailable at decision time cannot change the earlier decision trace.
- [ ] Require point-in-time universe membership: later listings, delistings, symbol changes, and directory revisions cannot leak backward.
- [ ] Test identical ticker text across USA/Canada, wrong exchange/currency pairs, one-market holidays, noncoincident half-days, cross-market benchmark/breadth inputs, missing sessions, and attempted forward-fill/index alignment.
- [ ] Verify live and backtest semantics against identical ordered bars, versioned config, injected clock, stop/gap/time-exit cases, and complete decision objects. If one path is genuinely not implemented, mark the obligation UNAVAILABLE/NOT_ASSURED rather than inferring equivalence from helpers.

**Acceptance:** No fact unavailable at the decision instant influences output. Market identity is semantic, not merely an enum or row-count check. Invalid identity refuses rather than coercing or merging.

---

## Task 8: Model-test persistence, immutability, and audit trails

**Produces:** state-machine model, operation histories, database snapshots/hashes, and hostile-storage results.

- [ ] Build a small independent model for bars, directory snapshots, positions, journal/run lifecycle, decisions, corrections, and versions.
- [ ] Generate valid and invalid operation sequences: duplicate keys with changed payloads, out-of-order knowledge times, same-time collisions, skipped versions, repeated completion, retry after interruption, and partial transaction failure.
- [ ] Attempt direct and API-mediated mutation, overwrite, delete, replace, and correction of protected facts.
- [ ] Verify old bytes remain queryable, corrections append, position versions are monotone and as-of correct, and identifiers are collision-resistant.
- [ ] Where the specification allows a lifecycle completion mutation, prove it is atomic, restricted to the documented transition, and idempotent; every other mutation must refuse.
- [ ] Crash between store and journal writes, reopen the database, and identify whether any partially authoritative decision can appear complete.
- [ ] Test database lock, malformed/corrupt copy, write denial, disk-full simulation where safely available, and concurrent writers.
- [ ] Preserve pre/post database hashes, logical dumps, and query outputs. Never run destructive probes on the owner's live stores.

**Acceptance:** Every protected record is append-only/versioned as required, as-of queries are correct, and incomplete transactions cannot masquerade as authoritative decisions.

---

## Task 9: Prove determinism and replay completeness

**Produces:** canonical full-trace schema, replay bundles, perturbation matrix, and mismatch reductions.

- [ ] Define a canonical decision trace including input manifest, config/provenance, clock/calendar version, candidates, open positions, refusals/pauses, indicators, risk/share outputs, costs, checklists, completeness/freshness details, decisions, persistence identifiers, and terminal run state.
- [ ] Hash canonical serialized traces; do not rely on an existing minimal output hash until its field coverage is proved.
- [ ] Repeat from pristine state under input permutation, varied `PYTHONHASHSEED`, supported worker counts, locale, timezone, cache state, interrupted prior run, dependency/runtime matrix, and repeated process launches.
- [ ] Perturb every decision-relevant manifest/input field independently. Require the trace hash or decision to change, or document why the field is provably non-decision metadata.
- [ ] Replay successful decisions, refusals, pauses, open-position management, and failed/incomplete runs from preserved bundles.
- [ ] Reduce every mismatch to the smallest fixture and classify it as product FAIL, environment sensitivity, or harness ERROR.
- [ ] Confirm logs and nondeterministic identifiers are either normalized outside the decision trace or generated deterministically where they are decision evidence.

**Acceptance:** Equivalent decision inputs yield byte-stable canonical traces across supported conditions; relevant perturbations cannot be silently omitted from the trace.

---

## Task 10: Audit research integrity study by study

**Produces:** dynamic study census, evidence-chain matrix, chronology, independent aggregate checks, statistical-oracle results, and causal-claim ledger.

- [ ] Enumerate studies and claims from registries, preregistration documents, reports, result files, decision records, parameter evidence, roadmap/handoff claims, tools, and reachable Git history.
- [ ] For each study, verify preregistration existed before results and compare frozen hypotheses, data window, universe, exclusions, metrics, corrections, seeds, stopping rules, acceptance rules, and amendments to execution.
- [ ] Trace Git chronology for preregistration, runner, inputs, results, report, registry status, and downstream decisions. Preserve commit IDs and content hashes.
- [ ] Require an evidence chain containing input snapshot hash, runner commit, environment/dependencies, seeds, exclusions, per-observation or per-trade output, aggregates, report, and downstream registry/decision references.
- [ ] Never reconstruct missing historical membership, prices, exclusions, or trade logs and then label them original evidence. Mark the limitation and affected claims NOT_ASSURED.
- [ ] Independently recompute aggregates from per-observation/trade evidence. Check exits, costs, missing data, duplicate observations, censoring, selection, survivorship, multiple testing, dependence, overlapping samples, and look-ahead leakage.
- [ ] Test imported statistical methods against primary literature and a trusted reference implementation when available. Borrowing a method does not validate this system's parameter.
- [ ] Use synthetic null simulations appropriate to the dependence structure to measure whether the study procedure controls false positives. Do not assume an IID formula is adequate for overlapping financial observations.
- [ ] Test prefix invariance and point-in-time membership for every historical study, not just the live application.
- [ ] Build an independent trade ledger for every claim involving entries, exits, stops, time exits, costs, or returns. Reconcile row-level data before accepting aggregates.
- [ ] Audit every causal explanation. It must cite a check establishing the cause or be marked conjecture. Trace corrections transitively into registries, decisions, handoff, roadmap, and validation labels.
- [ ] Search reachable sibling/local branches for duplicate studies or conflicting results before authoring any new audit experiment; record conflicts without merging evidence across snapshots.

**Acceptance:** Every retained research claim is reproducible from preserved point-in-time evidence and matches its preregistration, or is downgraded/withdrawn explicitly. A report narrative cannot outrank missing row-level evidence.

---

## Task 11: Audit security, privacy, and supply-chain controls

**Produces:** redacted security findings, dependency provenance, attack fixtures, and confirmed reachability.

- [ ] Build a trust-boundary and data-flow inventory for local files, databases, environment variables, network requests, vendor responses, logs, reports, and generated artifacts.
- [ ] Scan current tree and reachable history for secrets. Store raw results only in the sensitive vault; use redacted path plus HMAC fingerprint elsewhere.
- [ ] Inspect dependency declarations/locks for unpinned, ambiguous, abandoned, or vulnerable components. Confirm actual reachability and exploit preconditions before retaining a finding.
- [ ] Test untrusted CSV/YAML/JSON/text/vendor inputs for path traversal, unsafe deserialization, injection into shells/SQL/logs/spreadsheets, oversized response, decompression/resource exhaustion, Unicode confusion, and malformed encodings.
- [ ] Inspect subprocess construction, temporary-file handling, file permissions, log redaction, database paths, backup contents, and cleanup behavior.
- [ ] Verify network destinations, timeouts, response caps, TLS defaults, user-agent requirements, retry behavior, and fail-closed behavior. Use offline fixtures first.
- [ ] Confirm the system has no order-placement integration or stored broker credential path. Any public-feed network run requires explicit ledgered opt-in.
- [ ] Corroborate scanner leads with a minimal reachable reproducer; dismiss false positives in the ledger.

**Acceptance:** Security findings describe a reachable failure with concrete impact. Sensitive material never enters Git or ordinary audit output.

---

## Task 12: Challenge tests and gates with explicit mutants

**Produces:** targeted mutant patches, clean-copy outcomes, control coverage map, and undetected-control findings.

Use explicit patches in disposable copies; do not assume a mutation framework supports the target platform.

- [ ] Select one targeted mutant per critical control, based on the obligation map rather than mutation percentage.
- [ ] Include mutants that allow a hidden default, turn a refusal into a candidate, backdate knowledge, admit a future bar, merge markets, change exact-money semantics, overwrite an immutable fact, omit open positions from the daily path, reverse stop/time priority, allow same-bar entry/exit leakage, remove provenance, weaken a critical gate, or exclude a trace field.
- [ ] Apply exactly one mutant to a fresh copy, record the patch/hash, and run the smallest expected detecting test followed by the relevant native gate.
- [ ] Prove the mutant exhibits the exact prohibited behavior when the detecting test is removed or isolated; avoid credit for compilation failures or unrelated crashes.
- [ ] If no test detects it, retain a finding tied to the missed obligation and specify the regression test.
- [ ] Restore by discarding the disposable copy, never by altering the pristine subject.

**Acceptance:** Each critical control has evidence that the test/gate suite rejects a concrete bad behavior. Percent killed is not a verdict.

---

## Task 13: Exercise operations, recovery, performance, and maintainability

**Produces:** recovery drill logs, restore hashes, bounded performance profiles, hotspot evidence, and operational findings.

- [ ] Exercise preflight failure, process kill after run start, interruption between store/journal writes, concurrent scheduled invocation, database lock/corruption on a copy, write denial/disk-full simulation, missing calendar/dependency drift, log rotation, and nonzero CLI exit codes.
- [ ] Restore a disposable backup, compare content/logical hashes, and replay the interrupted run deterministically.
- [ ] Simulate a missed scheduler run and verify it becomes unmistakable without fabricating historical evidence.
- [ ] Require an incomplete-run/alert state, no partially authoritative decision, preserved last-valid snapshot/manual position export where specified, deterministic rerun, and verified restore. A log line alone is not recovery.
- [ ] Measure representative tiny, normal, and stress fixtures discovered from the target. Record wall/CPU/memory/I/O with warm/cold cache separated. Use budgets only when the target has an authoritative budget; otherwise report evidence without inventing pass thresholds.
- [ ] Profile before labeling a performance defect. Connect any hotspot to an operational budget or concrete scale failure.
- [ ] Assess complexity, coupling, fan-in/fan-out, duplication, exception handling, typing, documentation drift, and dead code. Retain maintainability findings only with a concrete change-risk, defect history, bypass, or testability impact.
- [ ] Verify backup/restore, runbooks, monitoring, and operator messages against actual executable behavior.

**Acceptance:** The snapshot either demonstrates recoverable, observable operation under its declared conditions or receives evidence-backed limitations/findings. Maintainability metrics alone are not findings.

---

## Task 14: Synthesize, independently challenge, and publish the verdict

**Produces:** final evidence index, reports, findings, dismissed alerts, unavailable tests, and remediation sequence.

- [ ] Run `verify_evidence.py` over the manifest, ledger, raw outputs, fixtures, hashes, redactions, and report references. Any broken chain is ERROR, never silently excluded.
- [ ] Check evidence closure: every critical obligation has exactly one final status and links to executed evidence or justified NOT_APPLICABLE.
- [ ] Reproduce each retained critical/high finding from a clean subject and the documented command. Non-reproducible findings move to unresolved leads.
- [ ] Challenge each finding's oracle, reachability, severity, and falsification condition. Challenge each PASS for missing negative cases or self-confirming implementation reuse.
- [ ] Check for target movement and record the final ref tip separately from the audited SHA.
- [ ] Assign Decision Safety, Engineering Quality, and Research Integrity verdicts using the non-compensatory rule.
- [ ] Give an overall release recommendation derived from the worst critical domain and explicit owner risk decisions, not arithmetic.
- [ ] Order findings by potential for unsafe decisions, corrupted evidence, irrecoverable state, security impact, and operational failure; then by maintainability.
- [ ] Write remediation as a separate dependency-ordered plan. Each item names the frozen finding, affected paths, acceptance oracle, regression test, and re-audit scope. Do not edit the subject during this audit.
- [ ] Self-review the executive report for unsupported causality, ambiguous branch wording, hidden counts/scores, missing limitations, and unredacted content.

**Acceptance:** A reviewer can identify exactly what commit was audited, what was and was not exercised, reproduce every retained finding, verify every PASS closure, and understand what prevents assurance without reading raw scanner output.

---

## Full audit versus delta audit

Run the full plan when there is no trusted prior full audit, the prior evidence manifest fails verification, the target history diverged or was rewritten, the prior audited SHA is not an ancestor, critical requirements changed, or the changed surface cannot be bounded confidently.

A delta audit is permitted only when:

- the previous full-audit SHA is an ancestor of `target_sha`;
- the previous evidence manifest and report verify byte-for-byte;
- the diff and affected-symbol analysis are preserved;
- all changed obligations and transitive consumers are re-exercised;
- all critical non-negotiables, real daily/open-position path, point-in-time leakage, persistence integrity, determinism, and evidence-closure checks are rerun regardless of diff;
- any new or changed study receives the full research-integrity procedure;
- the final report names both base and target SHAs and does not inherit a PASS across an unavailable test.

If any condition fails during a delta audit, promote it to a full audit and preserve the reason.

---

## Exit criteria

The audit is complete only when:

- the frozen target and final target-ref state are recorded;
- subject/evidence separation and tamper verification pass;
- capability and obligation maps close every discovered critical surface;
- the native matrix and all applicable adversarial workstreams executed;
- every study and downstream claim is classified;
- retained findings reproduce from preserved fixtures;
- every critical obligation has PASS, FAIL, ERROR, UNAVAILABLE, or justified NOT_APPLICABLE;
- the three domain verdicts follow the non-compensatory rule;
- sensitive output is redacted and raw evidence stays outside Git;
- the remediation plan is separate from the audited subject;
- the report makes no generic claim about a branch beyond the frozen SHA.

An incomplete audit is reported as incomplete. It is never converted into a favorable verdict by summarizing tests, coverage, issue counts, or tool scores.

---

## Plan self-review

This plan is intentionally independent of the current `master` condition. It does not assume a specific commit, branch topology, study list, runtime version, gate count, test count, module layout, or working-tree cleanliness. Stable SwingDesk obligations remain mandatory; target-specific surfaces are discovered from the frozen snapshot. Missing capabilities produce explicit FAIL, UNAVAILABLE, NOT_APPLICABLE, or NOT_ASSESSABLE outcomes instead of disappearing from scope.

The principal anti-self-confirmation controls are the detached subject boundary, external raw vault, independent domain/statistical/persistence oracles, real-entry-path exercises, targeted mutants, preserved dismissed-alert ledger, evidence-closure rule, and report-before-fix boundary. The resulting artifact is a decision audit, not a scoreboard.
