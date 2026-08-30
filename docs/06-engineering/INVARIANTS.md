# INVARIANTS

**Status:** drafting · **Tier:** 6 (engineering) · **Content:** authored, audited against `tests/`

`TEST_STRATEGY.md` §2 names nine invariants and says each one is a property test rather than prose.
`RISK_SPEC.md` and `SCREENER_SPEC.md` both defer to this file. It did not exist until 2026-08-03 —
three documents cited an authority that was never written, and gate 3e now catches that class of
reference.

This is the audit those citations implied: **for each invariant, the test that enforces it, or the
honest statement that nothing does.**

---

## 1. The nine, and what enforces each

| # | Invariant | Enforced by | Kind |
|---|---|---|---|
| 1 | R denominator is always the **initially planned** risk, across stop moves and partials | `test_r_denominator_is_the_planned_risk` · `test_r_denominator_survives_a_stop_move` | property + example |
| 2 | Open risk is recomputed, never decremented | `test_open_risk_is_recomputed_and_may_go_negative` | example |
| 3 | Shares always round **down** | `test_shares_never_round_up` | property |
| 4 | Stop is set before size | **the function signature** — see §2 | structural |
| 5 | A stop change that increases risk is rejected | `test_a_stop_below_the_initial_one_is_refused` · `test_a_proposed_stop_move_downward_is_refused` · `test_a_stop_is_only_ever_proposed_upward` | example ×3 |
| 6 | No decision uses data whose `knowledge_time` exceeds the decision time | `test_as_of_ignores_later_knowledge` | example |
| 7 | Identical inputs always yield an identical classification | `test_atr_is_deterministic` | property — **per component, not general** |
| 8 | Shuffled input order yields identical output | `test_breadth_is_invariant_to_member_order` | example — and see §3 |
| 9 | An unset parameter yields a coded refusal, never a value | `test_unset_parameter_refuses_and_names_itself` · `test_an_unfitted_classifier_refuses_rather_than_inventing_a_threshold` | example ×2 |

**Seven of nine are enforced by a test that would fail if the invariant broke.** The two that are
not are §2 and §3, and both are defensible — but they are defensible for stated reasons rather than
by assumption, which is the difference this document exists to make.

**That sentence was an assumption until 2026-08-25, and it was false.** The test named for
invariant 1 asserted `r_multiple(net, sized) * sized.planned_risk == net` — `(net / x) * x == net`,
an identity true for every non-zero `x`, so it held whatever the denominator contained. Measured
2026-08-17: replacing `planned_risk` with `Decimal("42")` left it green. The test is rewritten and
**gate 34 now checks the claim instead of restating it** — it breaks each invariant in a scratch
copy of `src/` and requires the named test to go red. **Every mutant is killed today, and how
many there are is the tool's output rather than this page's** - the sentence this replaced named
a number and then told the reader not to quote it, which had already drifted twice:

```bash
python tools/verify_invariant_tests.py
```

The two uncovered invariants are 4 and 7, and the gate names them on every run for the reasons §2
gives and because a mutation that made a pure function non-deterministic would be testing Python
rather than this code.

## 2. Invariant 4 is structural, not tested

`RISK_SPEC.md` §3 fixes the order: invalidation → stop → risk per share → allowed risk → shares.
Narrowing the stop to obtain a larger position reverses steps 1 and 4, and the course names that as
a prohibited move.

Nothing tests the *ordering*, and nothing needs to: `size_long(entry, stop, registry)` takes the
stop as an **input**. There is no code path that sizes first and derives a stop afterwards, because
the function cannot be called without one. The invariant is carried by the signature.

That is stronger than a test, not weaker — a test can be deleted, and a caller that tried to invert
the order would not compile into anything meaningful. It is recorded here so nobody "adds the
missing test" and concludes the invariant was previously unenforced.

The nearest test, `test_stop_at_or_above_entry_always_refuses`, guards a *consequence* of the
ordering rather than the ordering itself.

## 3. Invariant 8 covers one component, and that is the whole surface

`DETERMINISM_SPEC.md` §7 lists "shuffled input order → identical output" as the strongest of its
four checks. It runs, and it runs on exactly one component.

That is not a gap, for a reason worth stating: **`breadth` is the only component whose input is an
unordered collection.** It takes a mapping of members. Every other component takes a `BarSeries`,
and `BarSeries` **rejects unordered input at the boundary** (`test_bar_series_rejects_unordered_input`)
— so downstream code can rely on ordering rather than defensively re-sorting, and there is no
shuffle to be invariant to.

Two places take unordered input and sort it explicitly rather than relying on a caller:

- `reference_data.universe.members` sorts admitted ids
- `application.universe.select` sorts members by id, and records a cap separately when one is
  applied, so truncation cannot silently become a ranking

**What is not covered:** if a future component takes an unordered input, nothing forces a matching
invariance test. That is the real gap here, and it is a gate-11 shaped problem rather than a test
one — the component registry knows a component's inputs and could require the test.

## 4. Invariant 7 is per-component

`test_atr_is_deterministic` proves it for ATR. Nothing proves it for the others, and the general
form — *any* component, *any* input — is not testable as a single property.

What covers the gap in practice is **gate 7b, the golden vectors**: 25 frozen input→output pairs
across 6 components, with a SHA-256 manifest. A component that became non-deterministic would move
its vectors and fail the gate. That is a different mechanism from a property test and it catches the
same defect, which is why this is listed as partial rather than missing.

## 5. Where these come from

Not invented here. Each traces to a source that predates the code:

| # | Source |
|---|---|
| 1, 2, 4 | `RISK_SPEC.md` §2–3 — transcribed from Appendix C |
| 3 | Appendix C, `floor(allowed risk / risk per share)` |
| 5 | `CODES.md` `WIDE_STOP`, severity `Critical` |
| 6 | `POINT_IN_TIME_SPEC.md` §2 |
| 7 | M32/M33 — `Два наблюдателя дают одинаковый статус` |
| 8 | `DETERMINISM_SPEC.md` §7 |
| 9 | `PARAMETER_REGISTRY.md` §4 |

Invariant 7 deserves its note repeated from `TEST_STRATEGY.md`: the course's own acceptance
criterion for a setup detector is that two observers reach the same status. Restated as a property,
it forbids any classifier whose output depends on anything outside its declared inputs — which is a
much stronger constraint than it first reads as.

## 6. Open items

- [ ] **Nothing forces a new unordered-input component to carry an invariance test.** §3. The
      component registry knows the inputs; gate 11 could require it.
- [ ] Invariants 2, 5, 6 and 9 are example tests rather than property tests. Example tests prove the
      case they encode; property tests search for the case nobody thought of. Worth promoting 6 in
      particular, since look-ahead is the failure this project is least able to detect after the
      fact.
