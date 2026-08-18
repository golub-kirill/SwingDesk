# DR-012: The protective stop is 2.0 × ATR(14) and the maximum holding period is 20 sessions

```
date:            2026-08-17
status:          accepted — ratified by the owner 2026-08-17
parameters:      exit.atr_stop_multiple, exit.max_holding_period
components:      none — M48-T0738 and M57-T0866 stay `registered`; this sets their inputs, not their
                 activation
supersedes:      nothing. It removes the hard-coded ExitPolicy(2.0, 20) that PR #9 deletes
implemented_by:  src/swingdesk/application/pipeline.py :: _exit_policy
implementation_note:
                 Was `implementation: none` while this record sat ahead of PR #9, because until #9
                 merged pipeline.py carried the ExitPolicy(2.0, 20) literal and never opened the
                 registry - the values were ratified and INERT. Gate 20 enforced that honestly, by
                 refusing an implementation claim the branch could not support, and section 8.6's
                 single-reset ruling rests on the same fact. Updated in the commit that actually
                 brings `_exit_policy`, so the pointer is never ahead of the code it names.
```

## 1. Why this record exists at all

Two parameters are `unset`, and until 2026-08-16 `application/pipeline.py` carried
`ExitPolicy(Decimal("2.0"), 20)` as a literal in two places. That is a no-silent-default violation in
the production path, and PR #9 removes it.

The moment PR #9 merges, **every candidate Skips with a coded refusal and every open position
PAUSEs**, because the registry has nothing to read. That is the fail-closed design working. It also
means the system produces no Watches until these two values exist — so this record is what stands
between a corrected pipeline and a pipeline that decides nothing.

The values below are the ones that were hard-coded. **Nothing here is new arithmetic.** What is new
is that the choice is written down, attributable, and refutable, instead of being a constant two
functions deep with no provenance.

## 2. Decision

| Parameter | Value | Unit |
|---|---|---|
| `exit.atr_stop_multiple` | **2.0** | multiple of ATR |
| `exit.max_holding_period` | **20** | trading days |

Both take provenance **`assumed:DR-012`**. Precisely:

- **Protective stop** = `entry − 2.0 × ATR(14)` computed at the signal bar, fixed at entry, **no
  trailing**. `exit.atr_trailing_multiple` stays `unset` and is deliberately not set here — trailing
  is a different exit slot and a separate decision.
- **Time exit** = at the close of session 20 after entry, if the stop has not been hit. The stop is
  checked first on a bar that satisfies both, so a bar that breaks the stop *and* completes the
  holding period is a stop-out, never a time exit (`exits.py::ExitPolicy.evaluate`).

**A unit note that is not pedantry.** The registry unit is *trading days*; `ExitPolicy` counts
*bars*. On the daily interval this system runs, one bar is one session and the two coincide exactly.
They would not coincide on any other interval, and `ExitPolicy` takes the number as
`max_holding_bars`. Anything that ever feeds it intraday bars must convert; nothing does today.

## 3. Why these values

**Because they are the only ones any evidence in this project has ever been produced under, and
choosing differently would silently orphan that evidence.**

- `PR-005` §"stop" fixes `entry - 2.0 x ATR(14) at the signal bar. Fixed at entry; no trailing`, and
  its time exit is `close of session 20 after entry`. `PR-007` §"stop" carries the identical two
  lines.
- `docs/prereg/results/PR-005-trades.csv` — **26,351 trades, the only trade log this project has** —
  was generated under exactly these two numbers. A live system running any other pair cannot be
  compared to it.
- `PR-009` is registered to **vary the exit**. A variation needs an incumbent to vary against. Set
  the incumbent to something PR-005 never ran and PR-009's baseline arm becomes a value nothing has
  ever measured.

**What this reasoning is not.** It is continuity of a measurement basis, not evidence that 2.0 and 20
are good. The distinction is the whole point of §4.

## 4. The provenance question, answered explicitly

**`assumed:DR-012`, not `assumed:PR-005`, and never `validated:`.**

It is tempting to cite PR-005, since PR-005 is where the numbers were used. That citation would be
false in a way that matters:

1. **PR-005 held these values fixed as study *conditions*. They were never among its findings.** A
   study's controlled constants are inputs; citing them as output inverts the direction of evidence.
2. **PR-005 was REFUTED.** Its report measured the strategy flat at assumed costs and negative under
   stress. A reader seeing `validated:PR-005` — or even `assumed:PR-005` — on an exit parameter would
   reasonably infer the study had something to say about the exit. It does not. It says the *entry
   gates* do not separate outcomes, holding the exit constant.
3. `docs/decisions/README.md` §3 rule 5 is explicit: **`assumed` is where a DR leaves a parameter,
   never `validated`.** Only a pre-registered study moves a value to `validated`, and a decision
   record is not evidence. This project has **zero** `validated` parameters and this record must not
   appear to change that.

So the citation points here, and this record says out loud what it rests on: a constant carried
forward for comparability, chosen by no measurement.

## 5. The course supplies nothing to transcribe

Checked rather than assumed, because a course value would outrank this decision.
`EXIT_MODEL_SPEC.md` §4 — an audit of all 92 topics in M52–M58 — concludes **"Not one exit carries a
parameter."** Its own table names the two gaps at issue:

| Policy | Missing |
|---|---|
| `Trailing stop по ATR` | ATR period, multiplier |
| `Максимальный срок удержания` | days or bars |

`M48-T0738` ("ATR stop"), `M57-T0866` and `M71-T1067` ("Максимальный срок удержания") are titles with
no body defining the number. `AGENTS.md` states the same thing for the risk modules: they *name* every
concept and *quantify* none.

There is therefore no transcription to prefer over this decision, and no `verbatim` block that
contradicts it.

## 6. Alternatives rejected

- **Leave both `unset`.** The honest option, and it was the status quo for one day. Rejected because
  it is not neutral: the system then refuses every candidate forever, and — this is the sharp part —
  `tools/track_a_streak.py`'s `CLEAN_EXIT_CODES = (0, 2)` counts a coded refusal as a clean run. Track
  A would bank a 20-day streak proving a system that decided nothing. The idle-day line added
  2026-08-16 makes that visible; it does not make it acceptable as a resting state.
- **Pick better values now.** No evidence in this repository distinguishes 2.0 from 1.5 or 2.5, or 20
  sessions from 15 or 30. Choosing a *different* unmeasured number would cost the comparability of
  §3 and buy nothing. Rejected as motion mistaken for progress.
- **Wait for `PR-009` to report first.** Circular. PR-009 varies the exit against a baseline, so it
  cannot register against a parameter that has no value. Research is also suspended by the
  2026-08-16 council decision until one end-to-end cycle has run — and that cycle is exactly what
  these two values unblock.
- **Keep the literal in `pipeline.py` and skip the registry.** What the tree did until PR #9. It puts
  a number the owner cannot see or change into the decision path with no provenance, no `ui_editable`
  surface, and no way for the report to disclose it as assumed. This is the defect, not the fallback.
- **Set only the stop multiple and leave the holding period unset.** `_exit_policy()` refuses on
  either, so a half-ratification produces exactly the fully-unset behaviour. There is no partial
  state worth having.

## 7. What would overturn this

**`PR-009`** — registered, unreported, and unblocked as of 2026-08-16. It is the study that varies the
exit, and it is the only thing that can move either parameter off `assumed`.

One constraint on it, carried from the replay's provenance file so it is not rediscovered: **PR-009
must register against the replay's vintage, not against PR-005's published aggregate.** They are known
not to be the same thing — the whole `primary` period and 16 of 20 cells reproduce exactly, and
`ABOVE_LONG_MA` / `STRUCTURE` differ in the holdout by ≤0.00052 mean R because PR-005 read bytes that
exist nowhere.

A second, weaker trigger: if the live path ever produces a stop at or below zero at this multiple —
which `size_long` now refuses outright — that is evidence 2.0 is too wide for the cheap, volatile end
of the admissible universe, and the multiple should become price- or volatility-aware rather than one
constant.

## 8. Consequences

1. **`registry/parameters.yml`** gains two values; `parameters:unset` falls from 63 to 61. Gate 1
   requires the `assumed:DR-012` provenance form, which it accepts because a decision record is a
   citation.
2. **PR #9 stops being a fail-closed no-op and starts deciding.** Merged with these unset, it
   refuses everything; merged with them set, it sizes candidates against `policy.stop_for()` — the
   same distance management and the checklist use, which is the disagreement PR #9 fixes.
3. **`ExitPolicy`'s docstring becomes half-stale and must be corrected in the same commit.** It
   currently reads: *"study constants pinned by the caller, not registry reads — `exit.atr_stop_multiple`
   and `exit.max_holding_period` are both `unset` and a study that inherited them would change
   meaning the day they were ratified."* The *rule* survives and matters more after this record than
   before: **a study still pins its own constants and never inherits the registry**, or its meaning
   moves under it the next time an owner edits a value. Only the parenthetical reason ("both are
   unset") stops being true.
4. **Golden vectors may move.** Any vector whose stop was computed at 1×ATR by the old candidate path
   changes; PR #9 already re-recorded the replay baseline `78732401bd216ae2` → `4751a227d2a14884` for
   the `output_hash` widening, and gate 7b will name anything further.
5. **The report must keep disclosing these as assumed.** They are `assumed`, so they count toward the
   run's "assumed inputs" line and the standing Untested banner. A ratified parameter is not a
   validated one, and the report is where that distinction reaches the owner.
6. **The Track A counter — ONE reset. Owner ruling, 2026-08-17.** `registry/parameters.yml` is **not**
   one of the three frozen files (`tools/daily_run.cmd`, `application/pipeline.py`,
   `trade_management/sizing.py`), so on the letter of the 2026-08-16 amendment this record does not
   itself reset the streak. But it plainly changes decision output, and PR #9 — which does touch two
   frozen files — resets it already.

   **Ruled: PR #9 and this ratification are one change to the decision path and cost one reset, not
   two.** The reset attaches to PR #9's merge date. Splitting them across two evenings would reset the
   counter twice for a single transition, which makes the counter a penalty for landing a correctness
   fix carefully rather than a measurement of operational stability.

   Worth stating for whoever reads this next: on `master` as it stands, setting these two values
   changes nothing at all, because `pipeline.py` still carries the `ExitPolicy(2.0, 20)` literal and
   never reads the registry. The values only take effect when PR #9 lands. So this record can merge
   ahead of #9 with no operational consequence whatsoever — which is why the single reset lands
   naturally on #9 rather than here.

## 9. Measured, not argued — both halves of §1 were run

Run on the post-PR-#9 pipeline (`6e85e54`), against a **copy** of the real bar store, pinned with
`--as-of 2026-08-14T21:00:00Z`, same three instruments both times. The live stores were never opened
for write.

| | Both parameters `unset` | Both set to 2.0 / 20 |
|---|---|---|
| Trade / Watch / Skip / Pause | 0 / **0** / **3** / 0 | 0 / **3** / **0** / 0 |
| skip cause | `RISK [exit.atr_stop_multiple]` ×3 | none |
| `output_hash` | `a441a15e`-run | `2e54048bd923a549` |

**Unset**, each candidate carried the coded refusal in full:

> `Skip [RISK]` — no exit policy: the ATR stop multiple and the maximum holding period are what turn
> an observation into a stop, and sizing against an assumed one is the silent-default this registry
> exists to prevent

The funnel printed `skip causes: RISK [exit.atr_stop_multiple] 3`, and the checklist reported `E17`
FAIL rather than a silent gap. So the fail-closed path §1 predicts is not a prediction — it is
observed, and it is legible in the report rather than merely correct.

**Set**, all three sized and reached `Watch — sized; awaiting a trigger`. Two things worth checking
in the numbers, both of which hold:

- The stop is the ratified distance. AAPL: entry `305.589996`, stop `290.3167903…` — exactly
  `305.589996 − 2.0 × 7.6366`. Not `1 × ATR`, which is what the candidate path used before PR #9.
- **The R denominator includes costs.** AAPL's `risk per share` reads `16.8011…`, not the
  `15.2732` that `entry − stop` alone gives. The difference is `1.5279` = 50bp × 305.59, DR-010's
  proportional term. `planned risk 84.01 <- R denominator, frozen`.

This is what ratification buys and what it costs, on real bars, before anyone signs it.

## 10. What the owner was asked, and answered — 2026-08-17

1. **Ratify 2.0 and 20** — **ratified as proposed.** The values are now in `registry/parameters.yml`
   carrying `assumed:DR-012`, and this record is `accepted`. Per `docs/decisions/README.md` §3 rule 2
   it is not edited again; a change needs a new record naming this one.
2. **Confirm the single-reset reading in §8.6** — **confirmed: one reset.** See §8.6.
3. **`exit.atr_trailing_multiple` and `exit.stagnation_threshold` stay `unset`** — noted, unchanged.
   They are separate exit slots; PR-005 and PR-007 both ran with no trailing at all, so there is not
   even a hard-coded constant to inherit for them.

**What ratification does NOT mean, restated once more because this is the record people will cite.**
The provenance is `assumed`, not `validated`. This project still has **zero** `validated` parameters,
and `EVIDENCE_SUMMARY.md` still says the base strategy is negative at measured costs across the whole
admissible universe. Ratifying the exit constants makes the system able to decide; it does not make
the decisions good. Only `PR-009` can move either value off `assumed`.
