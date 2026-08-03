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
| 3c | `build_components.py --check-only` | a generated component field hand-edited; the registry going stale against the course | **exists** — 465 rows |
| 4 | `ruff` | style, obvious errors | to build |
| 5 | `mypy --strict` | type errors | to build |
| 6 | `lint-imports` | a package importing across a layer or forbidden boundary | **exists** — 4 contracts. Caught a reversed layer order on first run |
| 7 | no-wall-clock check | `datetime.now` / `date.today` / `time.time` in `derived_observations`, `decision_logic`, `trade_management` | **exists** — AST-parsed, not string-matched, so a mention in a docstring does not trip it |
| 7b | `golden.py` | a component's output changing without its version and vectors changing with it | **exists** — 25 vectors, 6 components |
| 8 | `pytest` | unit, property and golden-vector tests | **exists** — 182 tests, fully offline |
| 9 | determinism replay | a stored manifest no longer reproducing its `output_hash` | **exists** — 1 case, 4 instruments covering all four decision branches |
| 10 | traceability | a course id with no requirement row, a requirement with no test, a spec id cited by no test | to build |
| 11 | `verify_components.py` | `implements` not injective; an `active` component missing `implements`/`verification`/`spec`; a dangling parameter reference; an `active` component with an `unset` parameter; an `implements` pointing at a symbol that does not exist; a non-Definition topic with no row | **exists** — caught two components sharing one function on its first run |

Everything except 4, 5 and 10 runs today via `tools/check_gates.py`. Gates 2 and 3 are
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
| 10 | a course requirement being dropped without anyone noticing |
| 11 | two implementations of one component — the thing §3.8 forbids and import analysis cannot see, because both imports are perfectly legal. **Caught `M12-T0201` and `M12-T0202` both claiming `pivots:compute`**, which a linter would never question |

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

Two of these deserve a note. The constant-true-range fixture was the useful kind of failure — the
gate was green, the fixture was wrong, and only trying to make the gate fail on purpose revealed it.
The shared `pivots:compute` is the other kind: a gate finding a real defect the first time it ran,
before anyone had a chance to trust the thing it was checking.

## 7. Open items

- [ ] Choose the runner. GitHub Actions assumes a remote; a local pre-commit hook plus a script
      suits a single-user offline-first project better, and the repo has no remote today.
- [ ] Gate 10 (traceability) blocks once its subject exists. Blocking on a mapping that does not
      yet exist is theatre.
- [ ] Runtime budget. Gates 1–3 take about a minute (dominated by re-extracting 116 PDFs). If that
      becomes friction, cache extraction by file hash rather than weakening the check.
