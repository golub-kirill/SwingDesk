# CI POLICY

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored

An architecture rule that is not executed is decoration (`DEPENDENCY_LAW.md`). This lists every gate
that must pass to merge, and what each one exists to catch.

---

## 1. Gates

Ordered fastest-first, so a cheap failure does not wait behind an expensive suite.

| # | Gate | Catches | Status |
|---|---|---|---|
| 1 | `verify_parameters.py` | a value without provenance; `assumed` without a citation; a parameter with no course reference | **exists** |
| 2 | `verify_transcription.py` | a `verbatim` block that no longer matches its source; an enum drifting from its spec | **exists** |
| 3 | `build_course_index.py --check-only` | the course index no longer extracting to its known shape | **exists** |
| 3b | `build_frd.py --check-only` | the FRD drifting from the registry it is generated from | **exists** |
| 4 | `ruff` | style, obvious errors | to build |
| 5 | `mypy --strict` | type errors | to build |
| 6 | `lint-imports` | a package importing across a layer or forbidden boundary | **config exists**, runner to wire |
| 7 | no-wall-clock grep | `datetime.now` / `date.today` / `time.time` in `derived_observations`, `decision_logic`, `trade_management` | to build |
| 8 | `pytest` | unit, property and golden-vector tests | to build |
| 9 | determinism replay | a stored manifest no longer reproducing its `output_hash` | to build |
| 10 | traceability | a course id with no requirement row, a requirement with no test, a spec id cited by no test | to build |
| 11 | component registry checks | `implements` not injective; an `active` component with an `unset` parameter | to build, needs `components.yml` |

Gates 1–3 run today and are stdlib-only except `verify_parameters`, which needs PyYAML.

## 2. What each gate protects

Not busywork — each maps to a specific way this project could quietly go wrong:

| Gate | The failure it prevents |
|---|---|
| 1 | a guessed threshold acquiring the authority of a measurement |
| 2 | documents drifting from the course while still claiming to transcribe it — **already caught two real errors** and two undeclared sources |
| 3 | an extraction change silently altering the component catalogue |
| 6 | a strategy fetching its own facts; an indicator owning a decision; the journal being written from a pure layer |
| 7 | reproducibility breaking invisibly — one hurried commit is enough |
| 9 | non-determinism entering the decision path |
| 10 | a course requirement being dropped without anyone noticing |
| 11 | two implementations of one component — the thing §3.8 forbids and import analysis cannot see |

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
python tools/verify_transcription.py && python tools/build_course_index.py --check-only && python tools/verify_parameters.py
```

## 6. Open items

- [ ] Choose the runner. GitHub Actions assumes a remote; a local pre-commit hook plus a script
      suits a single-user offline-first project better, and the repo has no remote today.
- [ ] Decide whether gates 8–11 block from the start or are added as their subjects come into
      existence. Blocking on a test suite that does not yet exist is theatre.
- [ ] Runtime budget. Gates 1–3 take about a minute (dominated by re-extracting 116 PDFs). If that
      becomes friction, cache extraction by file hash rather than weakening the check.
