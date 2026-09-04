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
python tools/fetch_directory.py
```

```bash
python tools/refresh_universe.py --budget 500
```

The report prints the coverage fraction on every run precisely so this is visible before it is
mistaken for a finding.

**Every candidate reading `admitted UNCHECKED` in the SECTOR block is the same shape of symptom.**
The sector cap (`DR-006` §2, built 2026-08-23) measures a candidate against the sectors the open
book already holds, and it can only do that for instruments whose classification has been fetched.
Classification is a separate pass for the reason bar coverage is — it is one more vendor round trip
per instrument, on a fact that changes a few times a year:

```bash
python tools/refresh_classifications.py --budget 200
```

Until it has run, every candidate is admitted **unchecked** and the report says so on every run.
That is `DR-006` §3 being obeyed and not a fault: a sector cap that refused every unclassified name
would refuse the whole universe on the day the store was created, which stops the system while
looking like risk discipline. What it does mean is that the cap is not protecting anything yet, and
`unchecked` is a coverage number to close rather than a verdict to read past.

**A candidate can also be unchecked because the vendor lied and was caught.** `DR-006` §8.7: a fund
whose look-through comes back as one sector at exactly 100% with every other at exactly 0% is a
bond fund being described in the only vocabulary the vendor has, and it is refused rather than
consumed. The refresh pass counts these on the way past.

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

**DONE — registered 2026-08-18.** Confirmed against the machine on 2026-08-23: the task exists, is
`Enabled`, and has been running. **Check before creating it**, because `schtasks /Create` on an
existing name offers to REPLACE it and a wrong keystroke there discards a working registration:

```bash
python tools/verify_schedule.py
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

### 7.4 The one message that needs you

```
TECH: the venue holds N symbol(s) this system's book does not carry
```

**New entries are paused until you deal with it.** It means the account holds something we cannot
trace to an order this system sent — bought by hand in the dashboard, or a fill that
`sync-fills` refused for a reason it printed just above.

Two ways to clear it, and both are yours:

1. **Record it**, if it is a real position you want the system to manage:
   ```
   python -m swingdesk.presentation.cli open-position AAPL --entry 191.20 --shares 12 --stop 180.00 --data data
   ```
2. **Close it at the venue**, in Alpaca's own dashboard, if it should not be there.

The pause is not a fault. The caps are measured against the book, so a book that does not describe
reality cannot bound anything — and adding to it would be the failure the guard exists to prevent.

### 7.5 Checking the account by hand, any time

```
python -m swingdesk.presentation.cli broker --data data
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

That is the book saying one thing and the market able to see nothing. **The system cannot restore
it** — it has no verb that amends or cancels an order — so a stop that has to go back on has to be
placed in the venue's own dashboard, and new entries stay paused until it is.

```
python -m swingdesk.presentation.cli sync-fills --data data --dry-run
```

Says what `sync-fills` would record, and records nothing.

```
PYTHONPATH=$PWD/src python tools/verify_submission_guards.py --data data
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
python tools/verify_schedule.py
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

### How you know it is working

`HANDOFF.md` §2's universe-coverage row is generated from the store, and every run's report prints
the same figure in its `UNIVERSE` block. **The number to watch is `coverage`, and the day it stops
saying `PARTIAL UNIVERSE` is the day the rule's answer and the stored answer are the same set.**

A held store is not a failure here: an overlapping pass costs a log line rather than a traceback,
which is `AGENTS.md` §12's rule about `ADR-0004`'s single writer.
