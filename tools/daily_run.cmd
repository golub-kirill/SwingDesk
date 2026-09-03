@echo off
REM ---------------------------------------------------------------------------
REM The scheduled daily run. Registered with Windows Task Scheduler as
REM "SwingDesk daily run" - see docs/runbooks/ and HANDOFF section 5.
REM
REM Why a wrapper and not schtasks calling python directly: the task needs a
REM working directory, a UTF-8 console, and a log. A scheduled command whose
REM output goes nowhere fails silently, and `a.run_completes` counts CONSECUTIVE
REM days - so a silent failure does not just lose a day, it resets the counter
REM and nobody finds out for three weeks.
REM
REM Exit code is preserved so the Task Scheduler's own Last Result column is
REM meaningful. 0 = the run completed. 2 = it refused, which is a real outcome
REM and not a crash (FAIL_CLOSED_POLICY).
REM
REM ---------------------------------------------------------------------------
REM THE SECOND PASS (DR-015 section 3)
REM ---------------------------------------------------------------------------
REM   tools\daily_run.cmd                the 18:30 scheduled run
REM   tools\daily_run.cmd second-pass    the 19:30 retry pass
REM
REM DR-015 rules that a fetch failure retries three times inside the run and
REM then gets ONE more pass at 19:30. The owner chose a second scheduled run
REM over blocking the first, and that is the right call: a run that sleeps for
REM an hour still "completes", so `a.run_completes` would read clean while the
REM evening was held hostage, and the notice would arrive at 19:35 carrying a
REM report an hour stale at birth.
REM
REM One wrapper, two invocations, because the preflight, the log, the rotation
REM and the exit-code discipline are the same job - and specification section 8
REM forbids maintaining one logic in two places.
REM
REM WHY THE SECOND PASS WRITES DIFFERENT MARKER LINES, and this is the part that
REM must not be "tidied" later: `tools/track_a_streak.py` parses this log for
REM `daily run starting` / `daily run finished`, and counts the attempt whose
REM start falls within +-30 minutes of 18:30 as THE scheduled attempt. A second
REM pass writing the same words would be a second parseable attempt on the same
REM date. The 19:30 start is 60 minutes out and would be excluded by the window
REM today - but that is an accident of two numbers agreeing, not a guarantee,
REM and a tolerance widened for an unrelated reason would silently start
REM counting the wrong run. `second pass starting` / `second pass finished`
REM cannot be mistaken for the scheduled attempt by any parser, present or
REM future. Track A measures the 18:30 run, and only that.
REM
REM The second pass is idempotent by construction (DR-015 section 3): the stores
REM are append-only and bitemporal, so a 19:30 run that finds nothing new writes
REM nothing new, and `output_hash` makes two runs that decided the same thing
REM visibly the same run.
REM ---------------------------------------------------------------------------

setlocal
set REPO=%~dp0..
set PY=%REPO%\.venv\Scripts\python.exe
set LOG=%REPO%\data\daily_run.log

set PASS=daily run
set SECOND=0
if /I "%~1"=="second-pass" (
  set PASS=second pass
  set SECOND=1
)

if not exist "%PY%" (
  echo [%DATE% %TIME%] FATAL: no interpreter at %PY% >> "%LOG%"
  exit /b 3
)

REM Preflight. An interpreter that exists is not an environment that works: on
REM 2026-08-10 `yfinance` was imported by the default fetcher and declared in no
REM dependency list, so a clean install succeeded and only broke at the first
REM fetch - inside this run. Checking here turns a lost day of the Track A clock
REM into a log line at 18:30. Exit 3, same as a missing interpreter: the run is
REM not attempted, and that is deliberately NOT a refusal (2), which is a real
REM outcome. Stdlib only, so it still reports on a broken environment.
"%PY%" -X utf8 "%REPO%\tools\preflight.py" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [%DATE% %TIME%] FATAL: preflight failed, %PASS% not attempted >> "%LOG%"
  exit /b 3
)

REM Rotate at 50MB. MEASURED: a full-universe run writes ~2.4MB and takes ~5
REM minutes, so this holds about a month. The first estimate here said 650KB,
REM taken from a --limit 5 test run - a limited run is not a small version of a
REM full one, it is a different thing. Two passes a day roughly halves the
REM window this holds, which is still comfortably over a fortnight.
for %%F in ("%LOG%") do if %%~zF GTR 50000000 move /Y "%LOG%" "%LOG%.1" >nul 2>&1

REM ---------------------------------------------------------------------------
REM THE SECOND PASS IS CONDITIONAL - owner instruction, 2026-08-24
REM ---------------------------------------------------------------------------
REM It ran unconditionally from DR-015 section 3 until here, and MEASURED across
REM every evening that ran both passes, it never once changed an outcome: the two
REM runs carry the same output_hash every time. The failure it insures against -
REM a fetch erroring - has not been observed here in ~11,200 instrument-fetches.
REM
REM So it now asks the journal first: did tonight's run refuse anything a later
REM attempt could plausibly repair? A DATA refusal is that class. RISK, STOP and
REM LIQ are decisions about the trade and no amount of waiting moves them.
REM
REM UNAVAILABLE RUNS THE PASS. If the journal cannot be read, the condition is
REM unmeasured - and an unmeasured condition must not silently suppress a pass.
REM AGENTS.md section 12: unavailable is not fail, and it is not pass either.
REM
REM WHY GOTO AND NOT AN IF BLOCK: `set X=%ERRORLEVEL%` inside a parenthesised
REM block needs delayed expansion and silently reads the wrong value without it.
REM Flat, descending errorlevel tests avoid the whole trap.
REM
REM TRACK A IS UNAFFECTED. Its parser counts only the attempt starting within
REM +-30 minutes of 18:30, and this branch is reachable only when the wrapper was
REM invoked with `second-pass`.
if not "%SECOND%"=="1" goto :attempt
"%PY%" -X utf8 "%REPO%\tools\retry_needed.py" --data "%REPO%\data" >> "%LOG%" 2>&1
if errorlevel 4 goto :attempt
if errorlevel 1 goto :nothing_to_retry
goto :attempt

:nothing_to_retry
echo ===== [%DATE% %TIME%] second pass skipped, nothing to retry >> "%LOG%"
exit /b 0

:attempt
echo. >> "%LOG%"
echo ===== [%DATE% %TIME%] %PASS% starting >> "%LOG%"

REM Directory pull (DR-008), BEFORE the pipeline (DR-023). It used to sit after the scan, and that
REM is what made the two evening passes decide on different universes: 18:30 read YESTERDAY's symbol
REM directory and 19:30 read today's, because the pull that produced today's ran between them.
REM Measured 2026-08-24 to 08-27, decision by decision rather than by hash: not one decision ever
REM differed between the passes, and `output_hash` diverged anyway because 1-3 instruments left the
REM universe each evening. The directory is an INPUT to the decision, so it is pulled before the
REM decision reads it. DR-023 carries the measurement.
REM
REM FIRST PASS ONLY. The directory is a once-a-session pull, not a per-run one: DR-008 c3 attributes
REM each pull to the session date the vendor's own `Last-Modified` reports, and a second pull an
REM hour later can only produce a duplicate row or a refusal - noise in the log either way, on the
REM record whose whole value is being auditable.
REM
REM IT MUST NOT FAIL THE RUN, and that used to be structural rather than stated: sitting after
REM `set RC=%ERRORLEVEL%` put it out of the exit code's reach entirely. Here it is in that path, so
REM the guarantee is made explicit instead. A failed pull is logged and the pass proceeds on the
REM directory already stored - which is what every pass did before this move anyway. `ver > nul`
REM clears the errorlevel afterwards so nothing between here and `set RC` can read this one's.
REM
REM WHY GOTO AND NOT A PARENTHESISED BLOCK: the same trap the second-pass condition above avoids.
REM Flat, and it keeps `if errorlevel` out of a block where a future `set` would need delayed
REM expansion to read the right value.
if not "%SECOND%"=="0" goto :directory_done
"%PY%" -X utf8 "%REPO%\tools\fetch_directory.py" --scheduled --data "%REPO%\data" >> "%LOG%" 2>&1
if errorlevel 1 echo ===== [%DATE% %TIME%] directory pull failed; the pass continues on the stored directory >> "%LOG%"
:directory_done
ver > nul

pushd "%REPO%"

REM ---------------------------------------------------------------------------
REM SYNC FIRST, THEN DECIDE (DR-031). The order is load-bearing, not tidy.
REM ---------------------------------------------------------------------------
REM `positions.duckdb` is what the ratified caps are measured against, and until
REM `sync-fills` existed it was written only by a person. So an evening whose fills
REM nobody recorded left the book reading EMPTY and DR-027 section 11 stopped every
REM entry after the first night - correctly, and it made the machine one that ran once.
REM
REM This records what filled BEFORE the scan reads the book, so the caps are measured
REM against what is actually held. Running it after the scan would measure them
REM against yesterday, which is the DR-023 mistake in a more expensive place.
REM
REM IT MUST NOT FAIL THE RUN, and exit 3 in particular is not a failure: it means the
REM venue holds something that traces to no order this system sent, which is TECH and
REM belongs to a person. The scan still runs, still decides, still reports - and
REM DR-027 section 11 stops the submission by itself, which is the guard doing its job
REM rather than this wrapper second-guessing it. `ver > nul` clears the errorlevel so
REM nothing between here and `set RC` reads this one's.
"%PY%" -X utf8 -m swingdesk.presentation.cli sync-fills --data "%REPO%\data" >> "%LOG%" 2>&1
if errorlevel 3 echo ===== [%DATE% %TIME%] sync-fills: venue holds something untraceable; new entries stay paused until a person records or closes it >> "%LOG%"
ver > nul

REM ---------------------------------------------------------------------------
REM --submit: the evening pass places this run's Trade decisions (CHARTER A-002).
REM ---------------------------------------------------------------------------
REM Owner instruction, 2026-09-02. A-002 authorises submission with no per-order
REM approval on a venue holding no owner capital, and DR-027 says what may be sent.
REM
REM THIS FLAG IS NOT THE ARMING. `--submit` only asks; the kill switch
REM (data\.paper-trading-armed, DR-027 section 4.2) decides, and it defaults to STOPPED.
REM Deleting that file disarms every pass without touching this wrapper, which is why
REM the switch is a file and not a flag: a flag is only ever as available as the next
REM release.
REM
REM SECOND PASS TOO. DR-015 section 3 provides for the 19:30 retry, and DR-027 section 5
REM keys idempotency on the SESSION rather than the run - so the retry derives the same
REM client_order_id and the VENUE refuses the duplicate. Submitting on one pass and not
REM the other would make the retry a different decision from the run it retries.
"%PY%" -X utf8 -m swingdesk.presentation.cli scan --universe --submit --data "%REPO%\data" >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
popd

echo ===== [%DATE% %TIME%] %PASS% finished, exit %RC% >> "%LOG%"

REM State block (AGENTS.md 10.6). After `set RC=%ERRORLEVEL%` and before `exit /b %RC%`, so nothing
REM here can move the run's exit code or the Track A counter. Measured at about 4 seconds, against a
REM pass that takes six minutes. The DR-008 sidecar used to keep this placement discipline company;
REM DR-023 moved it above the pipeline, because unlike this block it is an INPUT to the decision.
REM
REM WHY THE MACHINE AND NOT A PERSON. HANDOFF section 2's runtime block is derived from data/, and
REM this pass is what moves data/ - so every evening the schedule ran left gate 24 red the next
REM morning, on a document that had been correct when it was written, and the fix was a person
REM noticing and running the tool by hand. AGENTS.md 10.6 rule 1 says a fact a tool can derive is
REM derived AND written by that tool; the tool already existed and calling it was the last hand step.
REM
REM BOTH PASSES, unlike the directory pull above. The 19:30 pass writes journal rows and decisions
REM too, so rebuilding only after the first one reproduces the same staleness an hour later.
REM
REM THE COST, recorded rather than left to be discovered: this leaves HANDOFF.md modified and
REM uncommitted in the main checkout most evenings. Gate 21 reports uncommitted governed files and
REM is ADVISORY, so that is a standing note rather than a red gate - the cheaper of the two, since
REM gate 24 was blocking and red every morning for a reason nobody needed to investigate.
REM
REM A HELD STORE IS NOT A FAILURE HERE. build_state.py catches duckdb.IOException, reports the
REM runtime block UNAVAILABLE and leaves it alone (AGENTS.md 12), so an overlapping refresh pass
REM costs a log line rather than a traceback.
"%PY%" -X utf8 "%REPO%\tools\build_state.py" >> "%LOG%" 2>&1

exit /b %RC%
