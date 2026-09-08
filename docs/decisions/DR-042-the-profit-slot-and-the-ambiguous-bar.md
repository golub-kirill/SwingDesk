# DR-042: the backtest harness gets the profit slot, and a bar that touches both legs takes the stop

```
date:            2026-09-07
status:          proposed — the tie-break in §4 is the owner's to ratify
parameters:      none. exit.target_r_multiple is already ratified at 1.0 (DR-029); this record
                 does not choose a value, it makes the ratified one simulable
components:      none - swingdesk.trade_management.exits:ExitPolicy decides
supersedes:      nothing. DR-012 and DR-029 stand; this implements the second one
implemented_by:  src/swingdesk/trade_management/exits.py :: ExitPolicy.evaluate, target_for
```

## 1. What made this necessary: the harness could not run the exit the system places

Owner instruction, 2026-09-07 — a backtest of *"доля выигрышей, средний R, форма хвостов на
ратифицированном"*, at the ratified exit, over at least ten years.

**The ratified exit could not be simulated.** `EXIT_MODEL_SPEC` names four slots. `ExitPolicy`
implemented two — protective and time — and said so plainly in its own docstring, which is why this
was a stated limitation rather than a hidden defect. The third slot was ratified on 2026-09-01:

> `exit.target_r_multiple`, value `1.0`, `status: owner`, ruled by the owner (`DR-029`)

and it was implemented on the **live** path only, in `broker/submit.py:target_price`, as a leg of
the OCO bracket. So from 2026-09-01 to 2026-09-07:

| | stop | target | time |
|---|---|---|---|
| a LIVE order | yes | **yes** | yes |
| a BACKTESTED trade | yes | **no** | yes |

Every number this project has published about holding-period outcomes describes an exit the system
does not place. `PR-005`'s 26,351 trades, `PR-012`'s book, `measure_target_reachability` and
`measure_exit_surface` all predate the ratification or deliberately sweep a grid instead. **Nothing
was wrong; the harness was one ratification behind, and the gap opened the day `DR-029` landed.**

## 2. The rule

`ExitPolicy` gains an OPTIONAL `target_r_multiple`. `target_for(entry_price, risk_per_share)` returns
`entry + multiple × risk_per_share`, or `None` when the slot is unused. `evaluate` takes the target
price as a fourth argument, defaulting to `None`.

**Optional, and that is the design rather than politeness to callers.** `PR-002`, `PR-005`, `PR-011`
and `PR-012` published trade logs under the two-slot policy. A default target would silently
re-price all four, and a published trade log that changes when nobody re-ran it is not evidence. A
policy without a target behaves exactly as this file did before — same branches, same order, same
prices — and a test asserts it.

`risk_per_share` is passed in rather than recomputed from `stop_for`. The live path's R includes
costs and the backtest's does not, and a target that recomputed its own denominator would disagree
with the position it belongs to.

## 3. The four ordering rules, and why each is the pessimistic one

A daily bar records four prices and no times. On a bar that touches more than one leg the sequence
is **unknowable** and has to be assumed. Every assumption resolves against the strategy:

| # | case | fill | why |
|---|---|---|---|
| 1 | the session OPENS below the stop | the **open** | the open is the session's first trade, so the sequence is known rather than assumed. The fill is worse than the stop and the loss recorded is the actual loss |
| 2 | the session OPENS above the target | the **target** | a real limit would have filled at the better open. **This does not credit it.** Convention set by `measure_exit_surface.py` on 2026-09-06 and kept |
| 3 | intraday, the low reaches the stop AND the high reaches the target | the **stop** | §4 |
| 4 | the stop and the time exit on one bar | the **stop** | unchanged since the file was written: the opposite order converts some losses into time exits at a usually better price |

Rules 3 and 4 together mean a bar can satisfy the target and still exit at the stop. That is the cost
of daily bars, and it is why the count in §4 is reported.

## 4. What is asked of the owner: the tie-break

**When one session's low reached the stop and its high reached the target, which fired first?**

The rule implemented is **the stop, always**, and the bar is flagged `ambiguous` so the number of
times the assumption bound is counted and printed beside every result.

**Three arguments for it, and the third is the one that matters:**

1. **It is the pessimistic reading.** The stop is the −1R outcome and the target the +1R one, so
   taking the stop is the choice that cannot flatter a result.
2. **It is what the field does.** `backtesting.py` (kernc), the most widely used Python backtest
   library, resolves the same tie the same way and states the reason as *an adversarial rather than
   an optimistic stance* — an authored import (`AGENTS.md` §10.3), and it settles that this is a
   convention rather than an invention.
3. **The live venue's answer is not knowable from a daily bar either.** A real OCO sends both legs
   and the venue fills whichever prints first. This system cannot see which, so the harness must
   assume — and an assumption that can only ever understate is the one a research instrument should
   carry.

**What the owner might rule instead, and what it would cost.** A 50/50 split of ambiguous bars, or
the optimistic reading, are both defensible on the grounds that the true frequency is somewhere
between. Either would raise every future win rate and every future mean R. The count is reported
precisely so that choice can be made on a number rather than on taste: if ambiguous bars are 2% of
exits the ruling barely matters, and if they are 20% it is the single largest assumption in the
study.

**Until it is ruled, the conservative rule stands** — a study that cannot start is worse than one
that understates, and understating is the direction `FAIL_CLOSED_POLICY` points.

### 4a. The owner has ruled on the FORM of the question, 2026-09-07

Asked whether this is a **policy** (the stop wins for ever, whatever the true split is) or a
**calibration** (rule on the measured share), the owner chose calibration:

> *"(b) Покажи долю, потом решу"*

**Three things follow, and they bind.**

1. **The rule in §4 is TEMPORARY.** It stands only until the share is measured, and this record may
   not be closed by an agent deciding the number is small enough.
2. **Every result produced under it is PRELIMINARY**, and must say so where it is published —
   `PR-016`'s report and result file included. A number carrying an unruled assumption is not a
   final number, and labelling it afterwards is not the same as labelling it now.
3. **The measurement is owed before the ruling, not after it.** `tools/probe_ambiguous_bar.py` is
   what settles it: the store holds daily bars only — measured 2026-09-07, `interval` is `1d` and
   nothing else, 12.0M rows across 13,010 instruments — so the intraday sequence has to come from
   outside it. `probe_alpaca_delisted.py` established on 2026-09-05 that Alpaca `feed=sip` serves
   history from 2016-01-04 on this project's existing credentials, which is the same route and the
   same read-only boundary.

**What the agent said would change its own recommendation, recorded before the number exists so it
cannot be adjusted afterwards: an ambiguous share above ~15%.** Below that the conservative rule is
a small conservatism; above it, it is a systematic distortion of the sample and the measured split
should be used instead.

## 5. Where it runs

`ExitPolicy` lives in `trade_management` and is the one implementation both paths use
(Production Rules 3.8). Three callers:

* `validation/backtest/engine.py` — computes the target once at entry, stores it on the position,
  passes it to every `evaluate`, and accumulates `ambiguous_exits`;
* `validation/backtest/book.py` — the same, so a future book study at the ratified exit cannot
  silently run two slots;
* `trade_management/manage.py` — the live path, which passes **no** target and is unchanged. The
  venue holds the take-profit leg there; the book does not simulate it.

## 6. What it does not do

* It does not touch `exit.target_r_multiple`'s value, status or provenance. `DR-029` owns those.
* It does not add the **contextual** slot. Three of four, and the fourth is still absent.
* It does not re-run any published study. `PR-005`, `PR-011` and `PR-012` keep their policies and
  their logs, which is what the optional default protects.
* It does not model partial fills, borrow, or a target that moves after a partial
  (`exit.partial_trigger` and `exit.stop_move_after_partial` remain unset).

## 7. Evidence that the rules bite

Seven mutations applied to `evaluate` on 2026-09-07, each run against
`tests/test_exit_target.py` and `tests/test_backtest.py`:

| mutation | outcome |
|---|---|
| intraday, check the target before the stop | **died** — 1 failure |
| credit the favourable gap at the open | **died** — 1 failure |
| check the clock before the target | **died** — 1 failure |
| require a strict break of the target (`>` not `>=`) | **died** — 1 failure |
| default the profit slot to on | **died** — 4 failures |
| never set the ambiguity flag | **died** — 1 failure |
| fill a gap through the stop AT the stop | **died** — 3 failures |

Seven of seven. A green suite is not evidence (`AGENTS.md` §12); this is.

## 8. The ruling

**Open.** §4a records the owner's ruling on the FORM of the question — measure first — and
§4's tie-break itself is unruled. Nothing here may be reported as final until it is.
