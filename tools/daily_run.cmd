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
REM ---------------------------------------------------------------------------

setlocal
set REPO=%~dp0..
set PY=%REPO%\.venv\Scripts\python.exe
set LOG=%REPO%\data\daily_run.log

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
  echo [%DATE% %TIME%] FATAL: preflight failed, run not attempted >> "%LOG%"
  exit /b 3
)

REM Rotate at 50MB. MEASURED: a full-universe run writes ~2.4MB and takes ~5
REM minutes, so this holds about a month. The first estimate here said 650KB,
REM taken from a --limit 5 test run - a limited run is not a small version of a
REM full one, it is a different thing.
for %%F in ("%LOG%") do if %%~zF GTR 50000000 move /Y "%LOG%" "%LOG%.1" >nul 2>&1

echo. >> "%LOG%"
echo ===== [%DATE% %TIME%] daily run starting >> "%LOG%"

pushd "%REPO%"
"%PY%" -X utf8 -m swingdesk.presentation.cli scan --universe --data "%REPO%\data" >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
popd

echo ===== [%DATE% %TIME%] daily run finished, exit %RC% >> "%LOG%"

REM The directory pull is the project's only irreversible clock: departures()
REM accumulates forward only and a gap is lost permanently. It is NOT run here,
REM by owner decision 2026-08-09 (keep it manual). Uncomment to reverse that -
REM it costs about five seconds and it is the same schedule.
REM "%PY%" "%REPO%\tools\fetch_directory.py" --data "%REPO%\data" >> "%LOG%" 2>&1

exit /b %RC%
