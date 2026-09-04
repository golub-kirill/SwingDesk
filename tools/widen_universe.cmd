@echo off
REM ---------------------------------------------------------------------------
REM The coverage pass. The TIER THAT WAS SPECIFIED AND NEVER SCHEDULED.
REM ---------------------------------------------------------------------------
REM `tools/refresh_universe.py` opens by saying the work is tiered:
REM
REM   * this tool, run periodically, widens coverage - the universe converges
REM     on the rule's answer
REM   * `swingdesk scan --universe`, run daily, reads what is already stored
REM
REM The daily tier was registered on 2026-08-12 and has run every evening since.
REM The periodic tier was never registered at all. MEASURED 2026-09-04:
REM `schtasks` lists exactly two SwingDesk tasks, the 18:30 run and the 19:30
REM second pass, and `grep refresh_universe tools\daily_run.cmd` returns zero.
REM
REM The consequence is not cosmetic and the report has been printing it every
REM evening: 3,694 of 13,154 eligible symbols had stored bars - 28.1% - and a
REM symbol with no bars cannot be measured, so it cannot be admitted. CARD-001
REM ranks the admitted universe by relative strength and holds the strongest
REM few, so "strongest" meant strongest of a 28% sample. That is a property of
REM the SCHEDULE, not of the rule, and every report labelled itself
REM PARTIAL UNIVERSE while nothing acted on it.
REM
REM WHY A SEPARATE TASK RATHER THAN A STEP IN daily_run.cmd. The tool's own
REM docstring answers it: the full set does not fit the 45-minute daily budget
REM in NFR.md, and fetching everything every day never will on a free tier.
REM Measured 2026-09-04 at 45 seconds per 100 symbols, so the ~9,400 never
REM fetched are about seventy minutes - once, and then only the drift.
REM
REM WHY SUNDAY. The stores are single-writer (ADR-0004), so this must not
REM overlap the evening passes; a weekend morning is the widest gap in the
REM week. It is also the cadence Appendix T uses - a weekly pass sets up the
REM week and the pre-session pass runs it.
REM
REM   tools\widen_universe.cmd            the weekly pass, default budget
REM   tools\widen_universe.cmd 2000       a bigger catch-up, by hand
REM
REM Exit code is preserved: 0 fetched something or had nothing to do, 3 the
REM environment is not usable. A vendor refusing individual symbols is NOT a
REM failure of this pass - warrants, units and rights map to no vendor symbol
REM and are expected to fail, which is why the tool reports both counts.
REM ---------------------------------------------------------------------------

setlocal
set REPO=%~dp0..
set PY=%REPO%\.venv\Scripts\python.exe
set LOG=%REPO%\data\widen_universe.log

REM The default is about THIRTY MINUTES at the measured rate - 45 seconds per
REM 100 symbols, so 4,000 is 1,800 seconds. (The first draft of this comment
REM said an hour, which is the arithmetic done in somebody's head that
REM AGENTS.md 12 warns about; 4000 * 0.45s is half that.)
REM
REM It finishes inside any weekend morning and needs no supervision. The queue
REM is oldest-first, so a budget that does not reach the end simply resumes
REM there next week rather than restarting.
set BUDGET=%~1
if "%BUDGET%"=="" set BUDGET=4000

if not exist "%PY%" (
  echo [%DATE% %TIME%] FATAL: no interpreter at %PY% >> "%LOG%"
  exit /b 3
)

REM Same preflight and the same reason as the daily wrapper: an interpreter that
REM exists is not an environment that works, and this pass is the one that talks
REM to the vendor.
"%PY%" -X utf8 "%REPO%\tools\preflight.py" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [%DATE% %TIME%] FATAL: preflight failed, coverage pass not attempted >> "%LOG%"
  exit /b 3
)

REM Rotate at 50MB, the same ceiling the daily log uses. This pass writes one
REM line per symbol attempted plus the vendor's own refusals, so a 4,000-symbol
REM budget is a few hundred KB.
for %%F in ("%LOG%") do if %%~zF GTR 50000000 move /Y "%LOG%" "%LOG%.1" >nul 2>&1

echo. >> "%LOG%"
echo ===== [%DATE% %TIME%] coverage pass starting, budget %BUDGET% >> "%LOG%"

"%PY%" -X utf8 "%REPO%\tools\refresh_universe.py" --data "%REPO%\data" --budget %BUDGET% >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%

echo ===== [%DATE% %TIME%] coverage pass finished, exit %RC% >> "%LOG%"

REM HANDOFF section 2 carries the coverage figure and is generated (AGENTS 10.6),
REM so the pass that CHANGES coverage rebuilds it. A held store is not a failure:
REM build_state.py reports the runtime block UNAVAILABLE and leaves it alone.
"%PY%" -X utf8 "%REPO%\tools\build_state.py" >> "%LOG%" 2>&1

exit /b %RC%
