@echo off
REM ---------------------------------------------------------------------------
REM The re-measurement pass. `AGENTS.md` 19.7: a verdict is one draw, and
REM "still true" is a property of a SEQUENCE of them. This pass appends one
REM point a week to that sequence for each registered question it covers.
REM ---------------------------------------------------------------------------
REM WHY SCHEDULED, and it is the whole point: the owner ruled on 2026-09-08 that
REM a re-observation of a registered question spends no trial, and 19.7 names
REM the guard that ruling needs. Consecutive rolling windows overlap heavily, so
REM re-running on demand until an answer flips is a search in time. A point that
REM arrives on a schedule and is appended whatever it says cannot be one.
REM
REM WHY SUNDAY, AFTER BOTH WIDENING PASSES. The stores are single-writer
REM (`ADR-0004`): this pass must not overlap the coverage pass (09:00), the
REM classification pass (13:00) or the evening runs. It only READS - through the
REM streamed loader, PR-019b about 0.75 GB and 15 minutes, PR-016 about 1.7 GB and
REM 17 (measured 2026-09-13 beside another run, so an upper bound) - so the
REM ordering is about the store's lock, not about what it writes.
REM
REM   tools\remeasure.cmd            the weekly pass
REM
REM Exit code is preserved: 0 a point was appended, 3 the environment is not
REM usable, anything else the tool's own refusal - which the log says in words.
REM No preflight: this pass never talks to the vendor.
REM ---------------------------------------------------------------------------

setlocal
set REPO=%~dp0..
set PY=%REPO%\.venv\Scripts\python.exe
set LOG=%REPO%\data\remeasure.log

if not exist "%PY%" (
  echo [%DATE% %TIME%] FATAL: no interpreter at %PY% >> "%LOG%"
  exit /b 3
)

REM Rotate at 50MB, the same ceiling the other logs use.
for %%F in ("%LOG%") do if %%~zF GTR 50000000 move /Y "%LOG%" "%LOG%.1" >nul 2>&1

echo. >> "%LOG%"
echo ===== [%DATE% %TIME%] re-measurement pass starting >> "%LOG%"

REM DAILY TRIGGER, WEEKLY POINTS (2026-09-26), asked PER STUDY: a pass killed after
REM PR-019b's point landed must not append a second PR-019b point this week when it
REM retries - a point per scheduled week is what AGENTS.md 19.7's guard rests on.
REM Only the codes each study returns are aggregated; a study already done this week
REM contributes 0. See tools\weekly_pass.py.
set RC=0
"%PY%" -X utf8 "%REPO%\tools\weekly_pass.py" due remeasure-PR-019b --data "%REPO%\data" >> "%LOG%" 2>&1
if errorlevel 10 goto :pr016
"%PY%" -X utf8 "%REPO%\tools\remeasure.py" PR-019b --data "%REPO%\data" >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
if %RC%==0 "%PY%" -X utf8 "%REPO%\tools\weekly_pass.py" done remeasure-PR-019b --data "%REPO%\data" >> "%LOG%" 2>&1
REM PR-016 runs whatever PR-019b returned: a point skipped because another failed is a point the
REM series never gets back. The first failure is the exit code either way.
:pr016
"%PY%" -X utf8 "%REPO%\tools\weekly_pass.py" due remeasure-PR-016 --data "%REPO%\data" >> "%LOG%" 2>&1
if errorlevel 10 goto :pr040
"%PY%" -X utf8 "%REPO%\tools\remeasure.py" PR-016 --data "%REPO%\data" >> "%LOG%" 2>&1
set STUDY=%ERRORLEVEL%
if %STUDY%==0 "%PY%" -X utf8 "%REPO%\tools\weekly_pass.py" done remeasure-PR-016 --data "%REPO%\data" >> "%LOG%" 2>&1
if %RC%==0 set RC=%STUDY%
REM PR-040 - the main hypothesis, DR-055 - re-observed on the trailing 48 months. It reads
REM IJR, VB and SPY with their dividends, which the paper passes fetch every session.
:pr040
"%PY%" -X utf8 "%REPO%\tools\weekly_pass.py" due remeasure-PR-040 --data "%REPO%\data" >> "%LOG%" 2>&1
if errorlevel 10 goto :finished
"%PY%" -X utf8 "%REPO%\tools\remeasure.py" PR-040 --data "%REPO%\data" >> "%LOG%" 2>&1
set STUDY=%ERRORLEVEL%
if %STUDY%==0 "%PY%" -X utf8 "%REPO%\tools\weekly_pass.py" done remeasure-PR-040 --data "%REPO%\data" >> "%LOG%" 2>&1
if %RC%==0 set RC=%STUDY%
:finished

echo ===== [%DATE% %TIME%] re-measurement pass finished, exit %RC% >> "%LOG%"

exit /b %RC%
