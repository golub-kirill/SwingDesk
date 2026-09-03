# DR-034: The only ratified `live` criterion could not fire, and a book now exists

```
date:            2026-09-03
status:          accepted — closes TODO.md §1's blocking finding of 2026-08-24
parameters:      none set. Two existing owner values gain a consumer:
                 validation.max_allowable_drawdown (20) and account.equity (10000).
                 risk.risk_off_ladder stays UNSET and stays the owner's
components:      none new
implemented_by:  src/swingdesk/presentation/cli.py :: def _drawdown_now
                 the sequence-preserving read it needs is
                 src/swingdesk/journal_evidence/positions.py :: def action_kinds_for
built:           2026-09-03
```

## 1. What was true until now

`k.drawdown_pause` is ratified in `registry/criteria.yml`, **scope `live`** — the only criterion
this project has with that scope, so this was not one of several. Its threshold is owner-set at 20
percent. `criteria.yml` v1.1.2 settled what its one load-bearing word means. The measurement was
built on 2026-08-30, tested, and **called by nothing**: `trade_management.drawdown` had no caller
anywhere in `src/`, and the only two matches for the word were prose in a study's docstring.

`TODO.md` §1 states the consequence exactly: *"Harmless today and only today. The moment a position
is opened, the project's own kill switch is decorative."*

**Today ended on 2026-09-02**, when `run-20260903T044052Z-84cbe591` had four bracket orders accepted
at the venue. They fill or they expire; either way the book stops being empty on the next session
this system decides on.

## 2. What now happens

`_drawdown_now` assembles the run's stores into the pure measurement's arguments and `_submit`
evaluates it **on every armed submission**, before the caps and after the venue reconciliation. The
percentage is printed either way, because *"no answer"* and *"0.00%"* are very different things to
show beside a ratified kill switch.

**A breach pauses new entries and nothing else.** The criterion's action is *"Pause — not kill.
Reduce size per the risk-off ladder and review."* Submission is the only outward action this system
has, so refusing to add is the whole of *pause* that is available to it. It is also the mapping this
codebase already uses: `TECH`'s prescribed action is *pause new entries* and `DR-027` §11 implements
it as a submission stop.

**The size-reduction half is NOT automated and NOT approximated.** `risk.risk_off_ladder` is `unset`
and stays `unset`; the refusal says so in the text an operator reads, so nobody can mistake a paused
run for a laddered one. Making a kill switch measurable is not the same as making it automatic, and
`criteria.yml` v1.1.2 said so before this record existed.

## 3. Unmeasurable is stopped, and a test caught the inverse in this record's own code

A drawdown that cannot be computed **stops submission**. A kill switch that admitted when it could
not read the book is `DR-006` §3's admit-on-unavailable inversion on the highest-consequence surface
this project has — the item `HANDOFF.md` calls the deepest one still open.

**The first implementation had exactly that bug.** Sessions were collected from the bars each
position actually had, so a position with **no** bars contributed none, dropped silently out of the
union, and the curve was built from the positions that *could* be priced — reporting a tidy `0.00%`
for an account holding something nobody could value. The test written for this section failed on the
first run and named it. A position with no session in the store is now `Unavailable`, carrying the
instrument and the date it has been held since.

### 3.1 A position opened in the session still running is not an unpriced one

**Amendment, 2026-09-03, and it was found on the first evening a real position existed.** The store
refuses an unclosed bar (`CALENDAR_SPEC` §5), so a position opened in the session currently running
has no bar and never should have one yet. §3's first implementation read that as *unpriced* and
halted every submission — on the evening of the first fill, which is the evening this guard was
built for.

**The calendar is the only thing that can tell the two apart**, and it already answers exactly this:
`last_completed_session`. A position opened after the last close has lived through no completed
session, contributes no curve point, and is not a gap. One held THROUGH a closed session with no bar
stored still refuses — that is a book which genuinely cannot be valued, and both halves are asserted
separately because an exemption that swallowed the second would undo §3 entirely.

Measured on the real book the same evening: at 13:00 New York with 2026-09-03 still open, the three
positions opened that morning report **0.00%** instead of halting. After the close, with the day's
bars not yet fetched, the same call correctly reports UNAVAILABLE — the scheduled pass fetches held
instruments before it submits, so the run that matters sees the bar.

## 4. `actions_for` could not serve this, and says so itself

`drawdown._exit_fills` joins a `Fill.sequence` to the kind of action that settles it. `actions_for`
returns actions in sequence order **but not the sequences**, and its own docstring records why that
matters: they are monotonic, not contiguous, so pairing them with `enumerate` is an off-by-one
waiting for a gap. Booking a realised gain against an action that never transacted would land
straight in the equity curve this criterion is measured on, so `action_kinds_for` reads the column
instead of inferring it.

## 5. What this does NOT do

- **It sets no number.** Both values it reads were already owner-set; what was missing was a caller.
  `TODO.md` §1's standing warning — *"Do not set a number to make a gate green"* — is untouched.
- **It does not move a decision.** The measurement runs in `presentation`, on the submission path.
  The pipeline, `output_hash` and the funnel are unchanged.
- **It does not reduce size, and it does not kill.** Both are the owner's, and one of them needs a
  ladder nobody has written.
- **It reports 0.00% today**, against a book that is still empty. That is the point: the criterion
  stops being unevaluable *before* the book fills, not after.

## 6. What would overturn this

- **`risk.risk_off_ladder` being set.** Then *pause* stops being the whole of the action and this
  becomes the first half of a larger response.
- **A drawdown measured per strategy rather than per account.** `positions.strategy` exists, so the
  split is computable the day one matters; today the book holds one strategy at most.
- **A position whose instrument leaves the universe.** Its bars stop being refreshed, and this would
  report `Unavailable` and pause the machine on a stale mark rather than a fallen one — correct, and
  it will look like a fault to whoever meets it first.
