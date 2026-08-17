# DR-011: The run notice is a local desktop notification, not Firebase and not Telegram

```
date:            2026-08-16
status:          proposed — mechanism chosen by the owner 2026-08-16; this record is unratified
parameters:      none
components:      none - swingdesk.presentation.notify is a surface, not a measured component
supersedes:      nothing. PRODUCT_SURFACES 3.4's Firebase remains specified and unbuilt
implemented_by:  src/swingdesk/presentation/notify.py :: DR-011
```

## 1. What was asked, and what the ask ran into

`TODO.md` §6b item 3b: nothing actively tells the owner the daily report exists. §3a landed the
report as a dated file; a file still has to be gone and looked at.

The owner's first instruction was to reuse the working Telegram bot from their other project
(TradAlert). Tracing that against this repository turned up four obstacles, three of them verified
by reading the files rather than reasoned about:

1. **`PRODUCT_SURFACES` §4 does not grant Telegram this event.** The matrix reads
   `Daily run complete | CLI ✓ | Report ✓ | Telegram — | Push ✓`. Telegram §3.3 owns the approval
   loop for open positions and nothing else.
2. **§3.4's binding property is retention, not transport.** "Never stores anything — no data leaves
   the machine." Telegram stores: a searchable chat history on a third party's server, outliving
   the repository. A "the constraint is content, not transport" amendment would have been false,
   and a ratified falsehood is worse than no record — it launders the violation for every later
   reader.
3. **`SECURITY.md` §2.1 forbids a secret in the repository** ("Environment variables or an OS
   keyring. **Never a file in the repo**"), and `tools/verify_secrets.py` states the repository is
   public. The obvious "put a `config/secrets.env` in the tree like TradAlert does" would have put
   a bot token into a public repo's working tree, gitignored or not.
4. **One token is one `getUpdates` stream.** TradAlert's bot answers approve/reject callbacks. A
   second consumer of the same token is an unverified interaction with a control surface.

## 2. The decision

**The "daily run complete" notice is a local Windows desktop notification.** Nothing is sent
anywhere. `src/swingdesk/presentation/notify.py` shells out to PowerShell's toast API; the run id
and status reach it through the environment, never interpolated into the script.

This fills the role §3.4 assigned to Firebase (owner decision D4). It is **not** Firebase, and
Firebase stays specified-and-unbuilt.

## 3. Why this is stronger than what §3.4 named, on §3.4's own terms

| §3.4's constraint | Firebase | This |
|---|---|---|
| Carries a title, a short body, a reference id | yes | yes |
| Never carries market data, journal contents, positions, decisions | by rule | by function signature |
| **Never stores anything — no data leaves the machine** | by policy at a third party | **nothing is transmitted at all** |

The third row is the point. Firebase satisfies "no data leaves the machine" by promise; a local
notification satisfies it by construction. No token exists to leak, no dependency is added, no
network call is made, and `CI_POLICY` §4's "CI must never touch the network" is unreachable rather
than merely respected.

## 4. What the notice may say, and why the rule survives locally

**The body is a terminal status and the run id. Nothing else.** No candidate count, no ticker, no
decision word.

§3.4's stated reason for that rule is privacy, and a local toast makes privacy moot. The rule is
kept anyway for a different reason, and that reason is the binding one here:

> A glanceable summary is one the owner can act on **without opening the report** — without its
> component provenance, its parameter validation status, or the standing Untested banner. This
> project has zero `validated` parameters and its own evidence summary says the base strategy is
> negative at measured costs. "3 candidates, 1 Watch" delivered to a lock screen is a decision
> stripped of everything that makes it honest.

So the rule is not inherited from §3.4. It is re-earned on `CHARTER` §4's ground.

Enforced structurally, not by review: `notify.body()` takes `(run_id, outcome)` and has no other
parameter, so no `RunResult` is reachable from inside it. A test pins the rendered string against
a fixed pattern, and a second test asserts the signature itself.

## 5. Failure behaviour

The notice is the last thing a run does, after the report is on disk and on the console. A failure
is **loud on stderr and never fatal**, matching the report write:

- `a.run_completes` counts runs that completed and produced a report. Both were true before the
  notifier was called, so a missing pop-up must not reset a 20-day counter.
- The subprocess carries a timeout, so a hung notifier cannot stall the scheduled run — the failure
  mode `set RC=%ERRORLEVEL%` in `daily_run.cmd` does **not** protect against, because a process
  that never returns never reaches the exit-code capture.
- It never fails silently. Unnoticed non-delivery is the exact defect this item exists to close.

`tools/daily_run.cmd` is untouched — it is a frozen file, and it did not need to change: the notice
is raised inside `scan`, and its outcome lands in the log the wrapper already captures.

## 6. What this deliberately does NOT do

- **No off-desk reach.** The owner confirmed on 2026-08-16 that they are normally at this machine
  at 18:30. That answer is the whole basis for choosing local over Telegram; if it stops being
  true, this record is the thing to re-open, and the Telegram analysis in §1 is preserved above so
  the next session does not have to redo it.
- **No approval channel.** `PRODUCT_SURFACES` §3.3 and `US-010` are untouched. This is send-only:
  the module contains no `getUpdates`, no polling and no inbound path of any kind.
- **No amendment to §4's Telegram column.** Telegram remains "—" for this event, correctly.

## 7. A defect found in §3.4 while writing this

§3.4 states "**Never carries** market data, journal contents, positions, or decisions" and then
gives as its example: *"the daily run finished, 3 candidates"* — a candidate count, which is both
market-derived and a decision summary. **The ratified text bans the thing its own example
demonstrates.**

Left in place, that example is a standing instruction to a future session to reintroduce exactly
what §4 of this record forbids. Corrected in `PRODUCT_SURFACES.md` under `AGENTS.md` §10.5's
strikethrough-and-append convention: the original line is struck through, not deleted, because a
ratified sentence that quietly vanishes is worse than one that was wrong.
