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

echo. >> "%LOG%"
echo ===== [%DATE% %TIME%] %PASS% starting >> "%LOG%"

pushd "%REPO%"
"%PY%" -X utf8 -m swingdesk.presentation.cli scan --universe --data "%REPO%\data" >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
popd

echo ===== [%DATE% %TIME%] %PASS% finished, exit %RC% >> "%LOG%"

REM Sidecar (DR-008). Placed AFTER `set RC=%ERRORLEVEL%` and before `exit /b %RC%`, so no outcome
REM here can change the run's exit code or the Track A counter. --scheduled honours the local
REM switch and the NYSE calendar; both refuse loudly into this same log.
REM
REM FIRST PASS ONLY. The directory is a once-a-session pull, not a per-run one: DR-008 c3 attributes
REM each pull to the session date the vendor's own `Last-Modified` reports, and a second pull an
REM hour later can only produce a duplicate row or a refusal - noise in the log either way, on the
REM record whose whole value is being auditable.
if "%SECOND%"=="0" (
  "%PY%" -X utf8 "%REPO%\tools\fetch_directory.py" --scheduled --data "%REPO%\data" >> "%LOG%" 2>&1
)

REM State block (AGENTS.md 10.6). Same placement discipline as the sidecar above: after
REM `set RC=%ERRORLEVEL%` and before `exit /b %RC%`, so nothing here can move the run's exit code
REM or the Track A counter. Measured at about 4 seconds, against a pass that takes six minutes.
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
