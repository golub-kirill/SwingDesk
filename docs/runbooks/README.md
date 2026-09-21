# RUNBOOKS

**Status:** drafting · **Tier:** 6 (engineering)

<!-- verbatim-sources: Module_33_Skrinery_v5.0.pdf -->

One procedure per row of the fail-closed degradation table (`FAIL_CLOSED_POLICY.md` §2). The course
specifies the manual process **and** the return condition for each; these expand them into steps.

Kept as one file rather than five. They are read under pressure by one person on one machine, and
finding the right section in one document beats finding the right file among five.

**Rule for all of them:** the return condition is not a judgement call. It is the course's, it is
quoted verbatim in each section, and the system stays in its degraded state until the condition is
demonstrably met.

### The interpreter, once, because every command below names it

Every command here is written for **PowerShell, from `C:\PycharmProjects\SwingDesk`**, and names the
interpreter explicitly:

```
.\.venv\Scripts\python.exe -X utf8 …
```

**That is not ceremony, and both halves were measured on this machine on 2026-09-04.** A bare
`python` resolves to the Windows Store alias — which sits *earlier* on `PATH` than the real
Python 3.14 install and exits without running anything — and even once that alias is turned off, the
system interpreter answers `ModuleNotFoundError: No module named 'swingdesk'`. **The package is
installed in the venv and nowhere else.** `tools/daily_run.cmd` has always named the same
interpreter, as `%REPO%\.venv\Scripts\python.exe`; this document now agrees with the wrapper instead
of contradicting it.

**No `PYTHONPATH=` prefix appears here, for two reasons.** It is bash syntax that neither `cmd` nor
PowerShell accepts — the form this file carried until 2026-09-04, in a document read by an operator
on Windows — and it is unnecessary from this checkout, because the venv has the package installed.
`AGENTS.md` §12's `PYTHONPATH` rule is about **worktrees**, where the installed package resolves to
the main checkout and a suite can go green against the wrong tree. Different audience, different
command.

---

## 1. No data, or data in doubt

```verbatim
Остановить новые решения; использовать второй источник и последний валидный snapshot.
Freshness, symbol/currency, corporate actions и event time подтверждены.
```

**Symptoms:** fetch failures, `DATA` refusals across many instruments, staleness beyond the window,
a spike in source conflicts.

**Steps**
1. Stop. No new decisions — the run is already refusing, so do not override it.
2. Identify scope: one instrument, one vendor, or everything. The health report's refusal section
   answers this.
3. Check the second source (Questrade) on a sample. Agreement means the primary is at fault;
   disagreement on both means look upstream.
4. If needed, work from the last valid snapshot — it exists by construction
   (`POINT_IN_TIME_SPEC.md` §5). Mark any output as snapshot-based.
5. **Open positions are still managed.** A data failure must never lock you out of managing risk on
   capital already committed.

**Return:** all four named gates pass — freshness, symbol/currency, corporate actions, event time
(`DATA_QUALITY_SPEC.md` §1). Not three of four.

**An empty or shrinking universe is a coverage symptom, not a market one.** `scan --universe` reads
stored bars; a symbol never fetched cannot be measured and so cannot be admitted. If the member
count drops or reaches zero, check coverage before concluding anything about liquidity:

```bash
.\.venv\Scripts\python.exe -X utf8 tools\fetch_directory.py
```

```bash
.\.venv\Scripts\python.exe -X utf8 tools\refresh_universe.py --budget 500
```

The report prints the coverage fraction on every run precisely so this is visible before it is
mistaken for a finding.

**Every candidate reading `admitted UNCHECKED` in the SECTOR block is the same shape of symptom.**
The sector cap (`DR-006` §2, built 2026-08-23) measures a candidate against the sectors the open
book already holds, and it can only do that for instruments whose classification has been fetched.
Classification is a separate pass for the reason bar coverage is — it is one more vendor round trip
per instrument, on a fact that changes a few times a year:

```bash
.\.venv\Scripts\python.exe -X utf8 tools\refresh_classifications.py --budget 200
```

Until it has run, every candidate is admitted **unchecked** and the report says so on every run.
That is `DR-006` §3 being obeyed and not a fault: a sector cap that refused every unclassified name
would refuse the whole universe on the day the store was created, which stops the system while
looking like risk discipline. What it does mean is that the cap is not protecting anything yet, and
`unchecked` is a coverage number to close rather than a verdict to read past.

### 1b. One-minute bars, and the intraday ladder built from them — `DR-042`, `DR-045`

Minutes come from Alpaca and live in their own store, bitemporal like every bar here. Two ways to
name what to fetch: the ambiguous-bar list `DR-042` needs, or an instrument and a date range, which
is what a study of the intraday ladder needs. The range comes from the exchange calendar, so a
holiday or a weekend is never requested.

```bash
.\.venv\Scripts\python.exe -X utf8 tools\fetch_minutes.py --store data\minutes.duckdb --instrument SPY --from 2016-01-04 --to 2026-09-15
```

It needs `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` in the environment and says UNAVAILABLE without
them. A session already held is skipped unless `--refetch` is passed; a request that failed writes
nothing, so a later run tries it again, while a session the feed served EMPTY is written as a fetch
of zero minutes — that is an answer, not a gap.

**Every rung above a minute is rolled up from those minutes** (`market_data.intraday.roll_up`: 3, 5,
15, 30 and 60 minutes). Nothing above a minute is fetched or stored, and `DR-045` §3 says why that
is safe here and still wrong for the daily bar.

**A candidate can also be unchecked because the vendor lied and was caught.** `DR-006` §8.7: a fund
whose look-through comes back as one sector at exactly 100% with every other at exactly 0% is a
bond fund being described in the only vocabulary the vendor has, and it is refused rather than
consumed. The refresh pass counts these on the way past.

### 1c. Quoted spreads at a moment of the session — `PR-024`

A study that charges each entry its own spread needs that name's quotes at the moment it traded.
`fetch_entry_quotes.py` reads the same kind of JSON-lines file `fetch_minutes.py` does and stores the
first 25 SIP quotes at three moments of each named session: five seconds after the open, 11:00, and
five minutes before the close (12:55 on a half day). The moments come from the exchange calendar.

```bash
.\.venv\Scripts\python.exe -X utf8 tools\fetch_entry_quotes.py --store data\quotes.duckdb --sessions docs\prereg\results\PR-024-sample.jsonl
```

Same credentials, same rule as the minutes: a failed request writes nothing and is tried again on
the next run, a window served empty is written as an answer, and `--refetch` stores a new version
rather than replacing the old one. `--moment open` (repeatable) fetches only the named moments. Run
it outside 18:30–20:00, when the evening passes need the rate limit.

### 1a. The staleness gate, and the 19:30 second pass — `DR-015`

**What refuses, and why it is not the same as a fetch failure.** A series behind the calendar's last
completed session is stale. Any staleness at all (`sessions_behind > 0`) means the run has already
refetched — the fetch happens before anything reads the store, and since `DR-015` the fetcher retries
a vendor failure **three times, 30 seconds apart**. If the series is still behind after that:

| How far behind | Candidate | Held position |
|---|---|---|
| 0 sessions | proceeds | managed normally |
| 1 session | `DATA` skip | `PAUSE`, marked stale |
| ≥ `data.freshness_window` (2) | `DATA` skip, **dropped** — the run stops trying | `PAUSE`, marked stale |

**A held position is never dropped.** `CHECKLIST_SPEC.md` §4 exists so a data failure cannot lock you
out of managing risk on capital already committed; a position past the window pauses like any other,
and the reason says which case it was.

**Reading it in the log.** A run that had to retry prints one line, and only when something failed:

```
vendor retries  4 retry/retries, 1 instrument(s) failed every attempt, 60s slept of a 90s budget
```

`BUDGET SPENT` on the end of that line means the run stopped paying for retries partway through and
later instruments got one attempt each. That is a vendor outage, not a per-instrument fault — go to
step 2 above and scope it.

**The second pass.** `DR-015` §3 gives a failed evening one more attempt at 19:30 rather than
blocking the 18:30 run for an hour. It is the same wrapper with an argument:

```bash
tools\daily_run.cmd second-pass
```

It is idempotent by construction — the stores are append-only and bitemporal, so a pass that finds
nothing new writes nothing new. It writes `second pass starting` / `second pass finished` to the same
log, deliberately different words from the 18:30 run's, so `tools/track_a_streak.py` can never count
it as the scheduled attempt. **Track A measures the 18:30 run and only that**; a clean second pass
does not rescue a broken evening, and it is not supposed to.

**It waits for the first pass** (owner ruling 2026-09-14). Both passes write the same stores and a
second writer is refused, so before it reads anything the second pass asks the Task Scheduler
whether the daily run is still running and waits up to an hour. The log says which happened:
`second pass: ... is still running; waiting`, then `has finished`, or `second pass skipped, the
daily run was still running`. A scheduler it cannot read does not stop it.

**DONE — registered 2026-08-18.** Confirmed against the machine on 2026-08-23: the task exists, is
`Enabled`, and has been running. **Check before creating it**, because `schtasks /Create` on an
existing name offers to REPLACE it and a wrong keystroke there discards a working registration:

```bash
.\.venv\Scripts\python.exe -X utf8 tools\verify_schedule.py
```

That is gate 26, and it reports both tasks, their last exit code and the two settings that make a
task silently not run. It is `UNAVAILABLE` anywhere but the scheduling machine.

Registering it, if it ever has to be done again, is the owner's step — the repository cannot create
a scheduled task:

```bash
schtasks /Create /TN "SwingDesk second pass" /TR "\"C:\PycharmProjects\SwingDesk\tools\daily_run.cmd\" second-pass" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 19:30
```

**This section read *"until that task exists, the second pass is not live"* for five days after the
task existed**, and `TODO.md` carried the same open item while `AGENTS.md` §12 already described the
19:30 pass running and failing. Two documents in one repository disagreed about a fact neither could
check. Gate 26 exists so the next such claim is checked rather than remembered.

**Two settings only the verbose query shows**, and both make an evening pass silently not happen:

| | |
|---|---|
| `Logon Mode: Interactive only` | both tasks. The run happens only while the user is logged on |
| `Power Management: No Start On Batteries` | the **second pass only**. On battery it does not start |

Neither is a defect this repository can fix — they are the machine's settings — but an evening with
no log line and one of these in force is not the same event as a run that decided nothing.

## 2. Broker or platform failure

```verbatim
Открыть ручной список positions/shares/stops/targets/events; управлять через доступный резервный канал.
Позиции и ордера reconciled; protective orders подтверждены.
```

**Steps**
1. Print the manual position list — instruments, shares, stops, targets, upcoming events. **This
   must work with the system down**, which is why it is generated after every run rather than on
   demand.
2. Manage through whatever channel is available: broker phone, mobile app, alternate terminal.
3. Record every action taken outside the system, with timestamps, for later entry.

**Return:** positions and orders reconciled against the broker, protective orders confirmed live.
**The broker is authoritative for positions**, not the journal (Appendix T) — where they disagree,
the journal is corrected.

## 3. Screener or automation failure

```verbatim
Использовать ограниченный ручной universe и checklist; автоматические сигналы считать недействительными.
Logs проверены, причина устранена, повторный run совпал с контрольным.
```

**Steps**
1. Treat every automated signal from the affected run as **invalid** — not suspect, invalid.
2. Fall back to a small manual universe with the pre-trade checklist (Appendix E, 18 items).
3. Diagnose from the run manifest and logs.

**Return:** the strictest in the set — a **re-run must match a control run**. This is why
`DETERMINISM_SPEC.md` exists as a spec rather than an aspiration; without byte-identical
reproducibility this return condition cannot be satisfied at all.

## 4. Risk or rule unclear

```verbatim
Статус Watch/Skip; новый ордер запрещён.
Полная карточка и risk snapshot заполнены без предположений.
```

**Symptoms:** an unset parameter, a component refusing, a strategy card with an incomplete field, a
situation the rules do not cover.

**Steps**
1. The candidate is `Watch` or `Skip`. It is never `Trade`.
2. Record which field or rule is missing — that record is what turns the gap into a work item.
3. If a parameter is unset, it goes in `registry/parameters.yml` with a citation, not into the code
   as a literal.

**Return:** the card and risk snapshot are complete **without assumptions**. A field filled with a
plausible guess does not satisfy this — that is the meaning of `без предположений`.

## 5. Violation or loss of control

```verbatim
Pause или reduced risk по risk-off ladder.
Review завершён и выполнены
формальные критерии возврата.
```

*The return condition is checked as two fragments because the PDF's multi-line row label is
interleaved into this cell by text extraction. The cell reads `Review завершён и выполнены
формальные критерии возврата.`; the extracted stream reads `Review завершён и выполнены` +
`я потеря контроля` + `формальные критерии возврата.` The same splice affects this row wherever it
is quoted.*

**Symptoms:** a `Critical` error code, a loss limit breached, a losing streak, or the honest
recognition of not being in a state to decide well.

**Steps**
1. `Pause`. This is system-wide, not per candidate (`DECISION_STATE_MACHINE.md` §1).
2. Apply the risk-off ladder. **Currently unquantified** — `risk.risk_off_ladder` is `unset`, so
   until it has a value this step is a judgement call and should be recorded as one.
3. Complete the review before anything resumes.

**Return:** review complete and the **formal, pre-recorded** criteria met. Criteria written after
the event do not count — that is the same rule that governs `criteria.yml`.

---

## Standing rules

- **The manual list must always exist.** Generated after every run, printable, valid with the
  system down.
- **A degraded state is recorded**, not remembered. It goes in the journal with its trigger and its
  return condition.
- **Return conditions are demonstrated, not asserted.** Each of the five is a checkable fact.
- **Open-position management survives every scenario.** Every runbook above leaves it reachable.

## Open items

- [ ] `risk.risk_off_ladder` needs values before §5 is executable as written.
- [ ] The manual position list needs a format and a generation step in the daily run.
- [ ] Whether entering a degraded state should notify (`PRODUCT_SURFACES.md` §4 sends `Pause`
      everywhere; the other four states are quieter).

---

## 6. The paper account's credentials

**Not a degradation procedure.** It is here because the alternative is rediscovering it under
pressure, and because the first attempt at it produced a wrong diagnosis that a check disproved.

### 6.1 They persist, they do not expire, and no browser session is involved

**There is no session here at all, and that is the part worth reading.** Alpaca's authentication
documentation describes two mechanisms:

| | What it is | Lifetime |
|---|---|---|
| **API key pair** — what this system uses | `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY` sent as headers on every request | *"These credentials don't expire."* |
| OAuth client-credentials | a bearer token exchanged for the secret | **15 minutes** — and **not available for the Trading API**, only Broker and Market Data |

So the short-lived thing exists, it is what a browser login feels like, and **this system cannot use
it even if it wanted to.** Every request carries the static pair. Closing a tab, closing the
browser, logging out of the dashboard and rebooting are all invisible to it, because none of them
is where the credential lives.

`setx` writes the user's environment, which survives all four. Verified twice on 2026-09-01, hours
apart, from a new console with the browser closed — same account fingerprint, `ACTIVE`, same
balance, and a paper order accepted by the venue.

**Checked rather than assumed** (`AGENTS.md` §15: an impossibility is a claim). Both variables were
confirmed present at `User` scope and `swingdesk broker` was run against the live endpoint.

```
setx APCA_API_KEY_ID "<paper key id>"
setx APCA_API_SECRET_KEY "<paper secret>"
```

**`setx` does not change the console you type it in.** A variable set this way appears in the NEXT
process. Running the command and then testing in the same window reports the key as missing, which
looks exactly like a key that expired.

### 6.2 What actually invalidates a pair, and there are only two things

1. **Regenerating it.** The dashboard shows the secret **once, at creation**. Coming back to read it
   again is not possible — the only way to see a secret is to generate a new pair, **and that kills
   the old one**. So "I looked at my key again and now it does not work" is not an expiry; it is the
   act of looking.
2. **Resetting or deleting the paper account.** A reset rotates the keys, and Alpaca's own forum
   answer as of March 2025 is that a paper balance cannot be reset without deleting the account and
   creating a new one — which issues new keys.

**Neither is a reason to re-enter credentials before a session.** If a key stops working, one of
those two happened, and the fix is `setx` once with the new pair.

### 6.2a How the system says so, and it says which of the two it is

Both failures are coded refusals naming the variables, never a traceback. Demonstrated 2026-09-01
by running the command with each fault deliberately present:

```
broker UNAVAILABLE  Alpaca paper trading refused the credentials in APCA_API_KEY_ID /
                    APCA_API_SECRET_KEY (HTTP 401). Paper keys are distinct from live keys.

broker UNAVAILABLE  APCA_API_KEY_ID, APCA_API_SECRET_KEY not set. ...
```

The first means the pair was rejected — regenerated, or the account was reset. The second means the
variables are absent from this process, which after a `setx` usually means the console predates it.
`swingdesk broker` exits **2** for both: `UNAVAILABLE` is neither a pass nor a failure of the
reconciliation, and the exit code keeps those apart (`AGENTS.md` §12).

### 6.3 Never in this repository

`SECURITY.md` §2.1: environment variables or an OS keyring, never a file here, never a command-line
argument. This repository is public and `tools/verify_secrets.py` is the gate that keeps it so.
Paper keys are distinct from live keys and that does not soften the rule — a secret in a public
repository is a secret published, whatever it unlocks.

**What to check, without ever printing a value:**

```
powershell -Command "'APCA_API_KEY_ID','APCA_API_SECRET_KEY' | ForEach-Object { $v = [Environment]::GetEnvironmentVariable($_,'User'); '{0}: {1}' -f $_, $(if ($v) { 'set, length ' + $v.Length } else { 'absent' }) }"
```

Presence and length answer every question worth asking here. The value answers none of them.

---

## 7. Running the paper venue, day to day

**Who this section is for.** Everything above is written for whoever is repairing the system. This
one is for whoever is *operating* it, and it assumes nothing about the code. If you read one
section before letting the scheduler place an order, read this one.

### 7.1 What the system does on its own, once a day

On weekday evenings the scheduled task (`SwingDesk daily run`, 18:30 local) runs three things in
this order, and the order matters:

| step | what it does | writes |
|---|---|---|
| `fetch-directory` | pulls the symbol directory | `directory.duckdb` |
| `sync-fills` | records a position for every entry **we** placed that has since filled | `positions.duckdb` |
| `scan --universe` | decides, reports, and — if armed — submits | `journal.duckdb`, the report |

`sync-fills` runs **before** the scan because the ratified caps are measured against the book: the
book has to describe what is actually held before the run reads it.

**Everything lands in one log**, `data/daily_run.log`, and the report for the evening is written to
`data/reports/`.

### 7.2 The switch — the only control you need day to day

```
data/.paper-trading-armed
```

**Contains the word `ARMED` → the evening pass may submit. Absent → it may not.** Absent is the
default and it is also what unreadable, empty, and anything-else mean. To stop the machine placing
another order, for any reason, at any time:

```
del C:\PycharmProjects\SwingDesk\data\.paper-trading-armed
```

That is the whole procedure. It needs no release, no commit and no restart, which is exactly why
the switch is a file. Re-arm by writing `ARMED` back into it.

**The switch is shared by every checkout on the machine**, because `data/` is. An armed switch is
only ever as safe as the code sitting next to it.

### 7.3 Reading the evening's result

Three lines in the log tell you what happened, and you want all three:

```
submission  114 Trade decision(s) sized and eligible
  110 passed over by the ratified caps; 4 within them
  SENT     AIS        17 sh limit 66.459999 stop 60.96...  accepted  swingdesk-2026-09-02-AIS
```

- **eligible** is how many names the screen picked. It is normally around a hundred and that is
  not alarming — the cutoff picks who is *eligible*, the caps pick who is *taken*.
- **passed over** is the caps working. 4 positions and 4R is the whole book (`DR-006` §8.3).
- **SENT** lines are the orders that actually went. Anything else — `STOPPED`, `REFUSED`,
  `NOT SENT` — names its own reason and is recorded in `journal.duckdb`, including the attempts
  nothing was sent for.

### 7.4 The messages that need you, and there are two of them

**New entries are paused until you deal with either.** The pause is not a fault: the caps are
measured against the book, so a book that does not describe reality cannot bound anything, and
adding to it would be the failure the guard exists to prevent.

**Start by looking**, always. One read-only command shows both directions at once and places
nothing:

```bash
.\.venv\Scripts\python.exe -X utf8 -m swingdesk.presentation.cli broker --data data
```

#### The venue holds something the book does not

```
TECH: the venue holds N symbol(s) this system's book does not carry
```

The account holds something we cannot trace to an order this system sent — bought by hand in the
dashboard, or a fill that `sync-fills` refused for a reason it printed just above. Two ways to
clear it, and both are yours:

1. **Record it**, if it is a real position you want the system to manage:
   ```bash
   python -m swingdesk.presentation.cli open-position AAPL --entry 191.20 --shares 12 --stop 180.00 --data data
   ```
2. **Close it at the venue**, in Alpaca's own dashboard, if it should not be there.

#### The book holds something the venue does not — `book_only`

```
TECH: the book and Alpaca paper trading disagree about 1 position(s) - AIS (book_only)
```

**Most of these close themselves now — `DR-038`, 2026-09-04.** The evening's `sync-fills` step
reads the activities feed, and when a SELL fill traces **by order id** to an order this system sent,
it closes the position with the venue's own price and prints `CLOSED`. So the message below means
one of two things: the exit is not traceable to an order of ours — a hand-sale in the dashboard —
or `sync-fills` refused it and said why, just above. **Neither is a case the machine may decide**,
which is the point of it stopping.

**This is a position that EXITED at the venue and was never recorded here.** Its stop fired
overnight, or it was sold in the dashboard. The book still carries it, so it still holds a slot in
`risk.max_concurrent_positions`, and every pass will keep stopping until the two agree.

Take the exit price from the venue — Alpaca's dashboard, or the account's activities — and record
it. **The date the exit happened and the moment you record it are kept apart on purpose**, so a
close reported the next morning is still dated to the day it occurred:

```bash
.\.venv\Scripts\python.exe -X utf8 -m swingdesk.presentation.cli close-position POS-AIS-2026-09-03 --exit 66.42 --closed-on 2026-09-04 --reason "stop fired at the venue; the book never learned" --data data
```

`--reason` is required and is written to the store rather than printed: a close nobody can audit is
not a close. The command **places, amends and cancels nothing** — like `open-position`, it records
a fact the venue already made. Then re-run `broker`; when it reports no mismatch, the next pass
submits again.

**Until 2026-09-04 there was no way to do this at all**, and that is worth knowing rather than
hiding: `closed_on` was written only for an `EXIT_NOW` the system had proposed from BARS, and the
venue's view never reached that decision. A stopped-out position stayed open in the book for ever.
If you meet a book-only divergence in an older checkout, `close-position` is what is missing.

### 7.5 Checking the account by hand, any time

```
.\.venv\Scripts\python.exe -X utf8 -m swingdesk.presentation.cli broker --data data
```

Prints the account, its positions, whether they agree with the book, **and whether each open
position's stop is still standing at the venue**. **Exit codes are three different answers and none
of them is "fine":** `0` they agree · `2` the venue could not be read · `3` they disagree — which
now includes a position holding no stop. It writes nothing, ever.

**The protection section is the one to read** (`DR-036`). A bracket's stop leg expires with the
session that placed it, while the position can live twenty sessions, so a holding can end up with
no protective order at all:

```
protection at the venue (3 open)
  TECH  unprotected  AIS
             the book records a stop at 61.700000 and nothing is resting at the venue for 17 shares.
```

That is the book saying one thing and the market able to see nothing. When the position holds
nothing at all, the next armed run places this system's own `oco` at the book's stop (`DR-037`).
**The system never cancels an order** — `DELETE` is refused — so a stop at the wrong price that is
not this system's has to be moved in the venue's own dashboard, and new entries stay paused until
it is.

**An approved move goes to the venue itself** (`DR-043`, built 2026-09-14). When the switch is
armed, `respond --approve` of a `MOVE_STOP` raises this system's own resting stop to the approved
price in one request, and prints the line starting `venue` with what happened:

```
  applied: POS-1 is now version 2
           stop 290 -> 298
  venue    stop 290.00 -> 298.00 at Alpaca paper trading  accepted  (order ... replaces ...)
```

It touches only a stop this system's journal says it placed, only upward, only `stop_price`. It
leaves alone — and says so on the `venue` line — a stop a person placed, two stops on one name, a
stop already at or above the approval, and everything when the switch is off. For those the
commands below still apply.

**To hand a hand-placed stop back to the system, cancel it DURING the session — near the close, not
after it.** Measured 2026-09-15, and this paragraph said the opposite until that evening: three
cancels sent after the close were accepted and not executed. The venue queued all three as
`pending_cancel`, where the order still holds the shares and protects nothing, and the cancels
would have landed at the next open — putting the gap inside a trading session with the next armed
pass twelve hours away. A cancel sent while the market is open executes at once, and the 18:30 pass
places this system's own `oco` at the book's stop the same evening. `DR-044` is the record; while a
cancel is queued, `swingdesk status` says so and prints no command, because the venue would refuse
one for `insufficient qty`.

**`swingdesk status` prints what to type** (since 2026-09-14): for a position holding nothing, the
`gtc` stop at the book's price rounded UP to the venue's tick; for a stop looser than the book's, the
cancel and then the stop; for a stop TIGHTER than the book's, a note that the next `sync-fills`
adopts it (`DR-041`) and nothing to send. The commands are for `cmd.exe` and carry the key variables
by NAME. **Run a cancel first and wait until `status` no longer shows it**: the venue holds the shares
for the old order until the cancel lands, and a stop placed before that is refused for
`insufficient qty` — measured on a Saturday, when the cancel waited for Monday's open.

```
.\.venv\Scripts\python.exe -X utf8 -m swingdesk.presentation.cli sync-fills --data data --dry-run
```

Says what `sync-fills` would record, and records nothing.

```
.\.venv\Scripts\python.exe -X utf8 tools\verify_submission_guards.py --data data
```

**Runs every guard tonight's pass will run, in its order, and sends nothing.** This is the one to
reach for before arming, or after any change to the risk rules. It prints PASS or STOP for each of
the reconciliation, the venue check, the drawdown criterion and the caps, then builds the actual
order payloads and checks every price against the venue's own increment — so a rejection like the
sub-penny one that stopped the first four real orders is found here rather than at the wire.

Three exit codes: `0` every guard passes and it names what would be sent · `2` a guard would stop
tonight's pass, which is a real answer and often the correct one · `3` the venue or a store could
not be read.

It takes about six minutes, because it runs the real pipeline rather than a fixture.

### 7.6 What the system will never do

Worth knowing before you watch it run, because each is a deliberate absence rather than a gap:

- **It cannot cancel an order.** Every order is `time_in_force: day`, so it expires at the close;
  `DELETE` is absent from the committed policy on purpose. To pull a resting order early, use the
  venue's dashboard.
- **It cannot reach the live venue.** One host is allowlisted and the live one is named as
  forbidden. A merge gate fails the build on a second entry.
- **It cannot short, and it cannot trade fractions.** Both are refused with a reason.
- **It cannot exit a position.** There is no exit card yet. A position that leaves the venue is a
  divergence you resolve, not something it handles.
- **It never claims a probability.** There is no legal source of one in this system, and a number
  displayed would be manufactured.

### 7.7 The thing to say out loud when showing this to anyone

**The machinery is real; the strategy is not known to work.** They are separate claims and this
project keeps them apart on purpose. `docs/08-pm/EVIDENCE_SUMMARY.md` is the standing account, and
it currently reports the base strategy as **negative at measured costs** across the admissible
universe. `CARD-001` ships `Untested`, and `DR-030` §3.1 registers **in advance** that it is
expected to fail its expectancy criterion.

What the paper account is for is putting this system's own machinery in front of a real venue's
fills, rejects and halts instead of a fixture — a measuring instrument that happens to speak a
broker's protocol. Every report this system prints says so, and nothing shown to anybody should
say more than the reports do.


## 8. The coverage pass — the tier that was specified and never scheduled

**Found 2026-09-04.** `tools/refresh_universe.py` opens by describing tiered work: a periodic pass
widens coverage, and the daily `scan --universe` reads whatever is already stored. The daily tier
was registered on 2026-08-12 and has run every evening since. **The periodic tier was never
registered at all** — `schtasks` listed exactly two SwingDesk tasks, the 18:30 run and the 19:30
second pass, and `tools/daily_run.cmd` mentions `refresh_universe` nowhere.

**What it cost, and the report has been printing it every evening.** Every run carries the line:

```
PARTIAL UNIVERSE. This is a subset of what the rule admits, not the rule's answer:
a symbol with no stored bars cannot be measured, so it cannot be admitted.
```

Measured that morning: **3,694 of 13,154 eligible symbols had stored bars — 28.1%**, and **9,460
had never been fetched once**. `CARD-001` ranks the admitted universe by relative strength and
holds the strongest few, so *strongest* meant strongest of a 28% sample. **That is a property of
the schedule rather than of the rule**, and nothing acted on the label for three weeks.

### What it costs to close, measured rather than estimated

45 seconds per 100 symbols, so the ~9,400 never fetched are about **seventy minutes, once**. After
that the queue is oldest-first drift, not a backlog.

Roughly **45 of every 100 fail, and that is expected, not a fault**: warrants, units and rights
(`AAC.U`, `ACHR.W`, `AESPW`) map to no vendor symbol — `universe.UNMAPPABLE_SUFFIXES` names them.
The tool reports both counts so the two are never confused.

### Registering it — the owner's step

`tools/widen_universe.cmd` is the wrapper, built to the same discipline as `daily_run.cmd`: a
preflight, a rotated log at `data/widen_universe.log`, a preserved exit code, and a `build_state`
rebuild afterwards because `HANDOFF.md` §2 owns the coverage figure and is generated.

**Check first.** `schtasks /Create` on an existing name offers to REPLACE it, and a wrong keystroke
there discards a working registration:

```bash
.\.venv\Scripts\python.exe -X utf8 tools\verify_schedule.py
```

Then, once:

```bash
schtasks /Create /TN "SwingDesk coverage pass" /TR "C:\PycharmProjects\SwingDesk\tools\widen_universe.cmd" /SC WEEKLY /D SUN /ST 09:00
```

**Sunday morning, and the reason is a constraint rather than a preference.** The stores are
single-writer (`ADR-0004`), so this must not overlap the evening passes — a weekend morning is the
widest gap in the week. It is also the cadence Appendix T uses: a weekly pass sets up the week and
the pre-session pass runs it.

**A bigger catch-up by hand takes a budget:**

```bash
tools\widen_universe.cmd 9400
```

### The classification pass — the second tier, and the coverage pass made it urgent

`tools/refresh_classifications.py` is tiered the same way and says so in its own docstring:
*"this tool, run occasionally, widens sector coverage"*, and then **"Until it has run, every
candidate is admitted UNCHECKED and the report says so."**

**What made it urgent, measured 2026-09-05 from the run's own funnel.** Widening coverage tripled
the admitted universe and the classification store did not move with it, because nothing schedules
it:

| evening | admitted | admitted **UNCHECKED** |
|---|---|---|
| 2026-09-03 | 1,142 | 110 |
| 2026-09-04 | 3,877 | 2,396 |

From roughly one in ten to nearly two in three, in one evening. `DR-006` §3's fail-open is correct
behaviour — a cap that refused every unclassified name would refuse the whole universe — but the
SIZE of the unclassified set is what decides whether the cap is worth anything, and nothing was
watching it.

`tools/widen_classifications.cmd` is the wrapper, built to the same discipline as the other two: a
preflight, a rotated log at `data/widen_classifications.log`, a preserved exit code, and a
`build_state` rebuild afterwards.

**Check first**, for the same reason as above:

```bash
.\.venv\Scripts\python.exe -X utf8 tools\verify_schedule.py
```

Then, once:

```bash
schtasks /Create /TN "SwingDesk classification pass" /TR "C:\PycharmProjects\SwingDesk\tools\widen_classifications.cmd" /SC WEEKLY /D SUN /ST 13:00
```

**Sunday, and AFTER the coverage pass, and that order is a constraint rather than a preference.**
The stores are single-writer (`ADR-0004`), so the two must not overlap each other any more than
they may overlap the evening passes. The coverage pass decides *which* instruments exist to be
classified, so classifying first would leave every newly covered name unclassified for another
week. 13:00 leaves the 11:00 coverage pass room to finish.

**Gate 26 names this task and is therefore RED until the command above is run** — deliberately, on
the coverage pass's own precedent. A catch-up by hand takes a budget:

```bash
tools\widen_classifications.cmd 4000
```

### How you know it is working

`HANDOFF.md` §2's universe-coverage row is generated from the store, and every run's report prints
the same figure in its `UNIVERSE` block. **The number to watch is `coverage`, and the day it stops
saying `PARTIAL UNIVERSE` is the day the rule's answer and the stored answer are the same set.**

A held store is not a failure here: an overlapping pass costs a log line rather than a traceback,
which is `AGENTS.md` §12's rule about `ADR-0004`'s single writer.

### The re-measurement pass — the sequence `AGENTS.md` §19.7 says nothing here produced

**Added 2026-09-13.** A verdict is one draw; *still true* is a property of a SEQUENCE of them, and
until this pass existed nothing in the repository produced one. `tools/remeasure.py` re-runs a
registered study's own construction and decision rule on the 48 months ending at the store's latest
instant and appends one point to `data/remeasure/<study>.jsonl`. The first study is `PR-019b` — the
candidate against `SPY` over the same days, the question that decides whether it is a strategy.

**It spends no trial** (owner ruling 2026-09-08) because of one guard: **it is scheduled, and every
point is appended whatever it says.** Re-running on demand until an answer flips would be a search
in time. The tool also refuses a point earlier than the series' last.

**Check first**, for the same reason as above:

```bash
.\.venv\Scripts\python.exe -X utf8 tools\verify_schedule.py
```

Then, once:

```bash
schtasks /Create /TN "SwingDesk re-measurement pass" /TR "C:\PycharmProjects\SwingDesk\tools\remeasure.cmd" /SC WEEKLY /D SUN /ST 16:00
```

**Sunday 16:00, after both widening passes.** It only READS — through the streamed loader, about
0.75 GB and fifteen minutes — but the stores are single-writer (`ADR-0004`), and a reader holding
`bars.duckdb` is what makes the next writer fail.

**Gate 26 names this task and is therefore RED until the command above is run**, on the coverage
pass's precedent. To read the series:

```bash
.\.venv\Scripts\python.exe -X utf8 tools\remeasure.py PR-019b --report
```

Every point is a RE-OBSERVATION, not a result: it never changes a verdict.


## 9. Standing it up from nothing — the clean-install sequence

**Written 2026-09-04 because the answer was scattered across five sections and nowhere in order.**
The owner asked whether the scheduled-task command would survive a clean install. It would not:
the three `schtasks` lines live in §1, §1a and §8, the credentials in §6, the local config is
mentioned only in `DR-008`, and nothing said which order any of it goes in. **A clone of this
repository is not a working installation, and this is the list of what the clone does not carry.**

### What the repository does NOT carry

Everything below is gitignored or lives outside the tree. Nothing here is a secret this project
stores — `tools/verify_secrets.py` is gate 19 and it fails on a tracked one.

| | what it is | rebuilt by |
|---|---|---|
| `.venv/` | the interpreter and dependencies | `pyproject.toml` |
| `data/*.duckdb` | bars, directory, classifications, journal, positions | the passes below |
| `data/.paper-trading-armed` | the kill switch. **Absent means STOPPED**, which is its value | the owner, deliberately |
| `.swingdesk-local.json` | the directory pull's enable flag | step 4 |
| `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` | paper credentials, environment only | Alpaca's dashboard, §6 |
| five scheduled tasks | the daily pass, the second pass, the coverage pass, the classification pass, the re-measurement pass | step 7 |
| the course PDFs + `pdftotext` | gate 2 re-extracts and diffs them | outside the repo entirely |

### The sequence

**1. The environment.**

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -X utf8 tools/preflight.py
```

`preflight.py` is what the scheduled wrapper runs before every pass, and an interpreter that exists
is not an environment that works — `yfinance` was importable and undeclared for a day in August, and
this is the check that ends.

**2. The credentials.** Two environment variables, named by `registry/broker_policy.yml` and never
by the code:

```bash
setx APCA_API_KEY_ID "<paper key>"
setx APCA_API_SECRET_KEY "<paper secret>"
```

§6 covers what invalidates a pair and how the system says which of the two it is. **Paper keys are
distinct from live keys and are still secrets**: the allowlist in `broker_policy.yml` is the only
thing separating the two accounts, because a brokerage account object carries no field that says
which it is.

**3. The symbol directory**, which everything else is selected from:

```bash
.\.venv\Scripts\python.exe -X utf8 tools\fetch_directory.py --data data
```

**4. The local config**, or step 3's scheduled mode refuses — by design, so an unattended pass
cannot start pulling on a machine nobody meant it to:

```json
{"directory_pull_enabled": true}
```

at the repository root, as `.swingdesk-local.json`. Gitignored, and `DR-008` explains why it is not
in the committed policy: the policy says what this project may ask of a server, and this says
whether *this machine* is the one that asks.

**5. The bars.** This is the long step and the only one that is:

```bash
tools\widen_universe.cmd 13500
```

**About an hour**, measured after the batched-insert fix of 2026-09-04 — the network is roughly a
quarter-second a symbol and the writing is no longer the cost. Before that fix the same work took
five. About 45 in every 1,000 fail and that is expected: warrants, units and rights map to no vendor
symbol.

**6. The classifications**, which the sector cap is measured through:

```bash
.\.venv\Scripts\python.exe -X utf8 tools\refresh_classifications.py --data data --universe --budget 2000
```

**The budget is not optional here.** It defaults to 100 instruments a pass, which is right for a
top-up and wrong for an empty store. `--universe` queues only the names the liquidity rule can
actually nominate rather than every symbol with bars.

**7. The five scheduled tasks.** Check before creating — `schtasks /Create` on an existing name
offers to REPLACE it, and a wrong keystroke discards a working registration:

```bash
.\.venv\Scripts\python.exe -X utf8 tools\verify_schedule.py
```

```bash
schtasks /Create /TN "SwingDesk daily run" /TR "C:\PycharmProjects\SwingDesk\tools\daily_run.cmd" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 18:30
schtasks /Create /TN "SwingDesk second pass" /TR "\"C:\PycharmProjects\SwingDesk\tools\daily_run.cmd\" second-pass" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 19:30
schtasks /Create /TN "SwingDesk coverage pass" /TR "C:\PycharmProjects\SwingDesk\tools\widen_universe.cmd" /SC WEEKLY /D SUN /ST 09:00
schtasks /Create /TN "SwingDesk classification pass" /TR "C:\PycharmProjects\SwingDesk\tools\widen_classifications.cmd" /SC WEEKLY /D SUN /ST 13:00
schtasks /Create /TN "SwingDesk re-measurement pass" /TR "C:\PycharmProjects\SwingDesk\tools\remeasure.cmd" /SC WEEKLY /D SUN /ST 16:00
```

**The first of those lines was recorded NOWHERE until 2026-09-04.** The runbook carried the
second pass's command and, after that date, the coverage pass's — and nothing at all for the daily
run, which is the one that actually places orders. It is reconstructed above by reading the live
task off the machine (`Get-ScheduledTask`), whose action is that path and whose trigger is 18:30 on
a `DaysOfWeek` mask of 62 — Monday through Friday. **That is exactly the gap this section exists
for**: the installation worked, so nobody noticed that it could not be rebuilt.

Gate 26 names all five and reports two hazards it cannot fix: they run only while the user is
logged on, and some do not start on battery. Those are settings on the task, not on this
repository.

**The fourth was added 2026-09-05 and the gate is RED until it is registered**, deliberately
and on the coverage pass's own precedent. The two widening passes are a PAIR: coverage decides
which instruments exist, classification decides which of them the sector cap can see. Running
only the first is what took candidates admitted UNCHECKED from 110 to 2,396 in one evening.

**The fifth was added 2026-09-13 and the gate is RED until it is registered**, on the same
precedent. It is the re-measurement pass — §8's last subsection has why it must be scheduled
rather than run by hand.

**8. Arming, and it is deliberately last.** Submission is stopped until a file exists carrying one
word. Absent means stopped, unreadable means stopped, present-but-unmarked means stopped — only the
marker arms it, and the remedy for a machine submitting something it should not is deleting one
file:

```bash
echo ARMED > data\.paper-trading-armed
```

**Do not do this until step 9 passes.**

**9. Proving the installation, before it is armed.**

```bash
.\.venv\Scripts\python.exe -X utf8 tools\check_gates.py
.\.venv\Scripts\python.exe -X utf8 tools\verify_submission_guards.py --data data
```

The first runs every gate. **Gate 2 will report `UNAVAILABLE` without the course PDFs and
`pdftotext` on PATH** — that is honest rather than passing, and it is the one gate a clean install
cannot satisfy from the repository alone.

The second runs every guard the evening pass runs, against the live account, **and sends nothing**.
It is the last thing to read before arming: it names what would be submitted and which guard would
stop it.

### What is deliberately NOT scripted

There is no `setup.cmd` and no `bootstrap.py`, and that is a choice rather than an omission. Two of
these steps are irreversible in the direction that matters — arming the switch, and registering a
task that will place orders on a schedule — and a script that does both is a script somebody runs
by accident. The sequence above is short enough to read.


## 10. Updating the main checkout

**Found 2026-09-13, when the owner's `git pull --ff-only` failed.** The evening run's last step
regenerates `HANDOFF.md` §2 from `data/`, so most mornings that file is modified — and every merged
change rewrites the same blocks, so git refuses the pull to protect a change that is only derived
paperwork. The pull is one command instead:

```bash
.\.venv\Scripts\python.exe -X utf8 tools\update_checkout.py
```

It discards `HANDOFF.md` **only when every difference lies between generated markers**, pulls
`--ff-only`, and runs `build_state.py` again so the blocks describe `data/` as before. Any other
local change — a hand edit to the prose, another modified file, something staged — and it refuses,
names it, and changes nothing. `--dry-run` says what it would do.

**It refuses while an evening pass is running, and since 2026-09-15 that is enforced rather than
asked.** It reads the Task Scheduler's `Status` for both run tasks; a pass running means it changes
nothing, and a scheduler it cannot read means the same, because not knowing is not the same as
knowing the machine is idle. `--anyway` skips the check for an operator who knows better.

**What paid for it, 2026-09-15.** The pull landed a few minutes into the 18:30 pass. `cmd.exe` reads
a batch file AS IT RUNS, by byte offset, so when the pull made `daily_run.cmd` sixteen lines longer
the running pass resumed in the middle of a comment and died on `'approval' is not recognized`. It
died before the step that restores protection, on an evening when a stop had just been cancelled by
hand, and that position stood with nothing at the venue. The Python half broke the same way from the
other side: the already-running process held the old `broker.policy` module and read the new
`broker_policy.yml`, which it refused — `submit REFUSED ... permits PATCH`. One command, two kinds of
mixed version, and a warning in prose was all that stood between them and the operator.


## 11. `CARD-002`'s twenty sessions — what the owner runs, and when

**Why the owner runs it by hand at all.** `DR-048` §1: the paper copy is submitted by this system,
and the REAL orders are typed by the owner, order by order, so `CHARTER` A-001 §1 holds without an
amendment. `DR-048` §6: this system cannot see the real fills either, because the live host is not
on gate 39's allowlist. So the owner types two orders and hands two prices back.

**What the twenty sessions are for**, stated once so nobody optimises the wrong thing: they measure
**the fill**, not the return. `PR-034` priced the auctions at half a cent and a whole cent a share
and could observe neither, and `PR-036` then made the difference decisive — over 2004-2015 the night
is an effect at half a cent and nothing at a whole one.

**Every command here is shell-agnostic**: absolute paths, one command, no `cd`, no `&&`. They run
the same in `cmd.exe` and in the app's PowerShell panel.

### 11.1 Before the close — about 15:35 ET

The plan pass reads the store, and the store is only as current as last evening's fetch. Fetch the
two funds first, or a fund will be refused for a reason a two-second request removes:

```bash
C:\PycharmProjects\SwingDesk\.venv\Scripts\python.exe -X utf8 C:\PycharmProjects\SwingDesk\tools\fetch_history.py --data C:\PycharmProjects\SwingDesk\data IJR VB
```

```bash
C:\PycharmProjects\SwingDesk\.venv\Scripts\python.exe -X utf8 C:\PycharmProjects\SwingDesk\tools\card002_plan.py --shares 1
```

The second prints the card to type from. **Exit 2 means a fund refused** — it names which and why,
and the other fund still trades. Enter the `MOC` buys it lists **before 15:50 ET**; the venue
rejects a `cls` order after that, and a rejected order is not a late one.

### 11.2 After 19:00 ET, or before 09:28 the next morning

Enter the `MOO` sells the same printout lists, for the whole position. **That order IS the
protection** (`DR-048` §5): there is no stop, because nothing can execute while the exchange is
shut, and the opening auction is when the card sells anyway. **A night held with no exit order
lodged is a defect and stops the trial** (`CARD-002` §5).

### 11.3 After the open — hand the two fills back

One command a fund a night, with the prices the broker actually reported:

```bash
C:\PycharmProjects\SwingDesk\.venv\Scripts\python.exe -X utf8 C:\PycharmProjects\SwingDesk\tools\card002_journal.py record --session 2026-09-22 --fund IJR --entry 138.92 --exit 139.40
```

`--session` is the session whose CLOSE the entry filled at, not the morning of the exit. The record
is append-only: a correction is another `record` with the right numbers, never an edit.

### 11.4 Reading it

```bash
C:\PycharmProjects\SwingDesk\.venv\Scripts\python.exe -X utf8 C:\PycharmProjects\SwingDesk\tools\card002_journal.py report
```

| what it prints | what it means |
|---|---|
| `PENDING` on a night | the next session's open is not stored yet — it prices itself tomorrow evening |
| **MEAN COST A SIDE** | the number the whole trial exists to produce. The model charges 0.50 cents |
| `TRIP-WIRE FIRED` (exit 2) | above **1.00 cent** a side after 20 priced nights. `CARD-002` §5 stops the trial: at that cost `PR-034`'s own edge is gone |
| `ALERT` | the book is 25% below its peak. That is the market, not a defect — `PR-034` measured −31.6% |
| `NO JUDGEMENT YET` | under 60 priced nights. The daily noise is about ±0.8% against a mean of +0.055% |

**What is NOT yet built**, so nobody waits for it: the close and evening passes that submit the
paper copy. The owner's side of the trial is complete without them, and they are tracked in `TODO`.
