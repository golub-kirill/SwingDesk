@echo off
REM ---------------------------------------------------------------------------
REM The classification pass. THE SECOND TIER THAT WAS SPECIFIED AND NEVER
REM SCHEDULED, and the one the coverage tier's own success made urgent.
REM ---------------------------------------------------------------------------
REM `tools/refresh_classifications.py` says it in its own docstring:
REM
REM   * this tool, run occasionally, widens sector coverage
REM   * `swingdesk scan`, run daily, reads what is already stored
REM
REM   "Until it has run, every candidate is admitted UNCHECKED and the report
REM    says so."
REM
REM That is `DR-006` section 3 being obeyed rather than a gap - a sector cap that
REM refused every unclassified name would refuse the whole universe on the day
REM the store was created. But it makes the SIZE of the unclassified set the
REM thing that decides how much the cap is worth, and nothing was watching it.
REM
REM WHAT PAID FOR THIS WRAPPER, measured 2026-09-05 from the run's own funnel.
REM The coverage catch-up tripled the admitted universe on 2026-09-04 and the
REM classification store did not move with it, because nothing schedules it:
REM
REM   evening      admitted    admitted UNCHECKED
REM   2026-09-03      1142                   110
REM   2026-09-04      3877                  2396
REM
REM From roughly one in ten to nearly two in three, in one evening. The council
REM that called a fail-open cap "not a cap" was looking at the tenth.
REM
REM WHY A SEPARATE TASK, and it is `refresh_universe.py`'s reason unchanged: one
REM classification is one more vendor round trip per instrument, against a
REM 45-minute daily budget in `NFR.md` on a rate-limited free tier, to refresh a
REM fact that changes a few times a year.
REM
REM WHY SUNDAY, LATER THAN THE COVERAGE PASS. The stores are single-writer
REM (`ADR-0004`), so these two must not overlap each other any more than they
REM may overlap the evening passes. The coverage pass runs first by design: it
REM decides WHICH instruments exist to be classified, so classifying before it
REM would leave every newly covered name unclassified for another week.
REM
REM   tools\widen_classifications.cmd            the weekly pass, default budget
REM   tools\widen_classifications.cmd 4000       a bigger catch-up, by hand
REM
REM Exit code is preserved: 0 fetched something or had nothing to do, 3 the
REM environment is not usable. A vendor refusing an individual name is NOT a
REM failure of this pass - the tool reports its own counts.
REM ---------------------------------------------------------------------------

setlocal
set REPO=%~dp0..
set PY=%REPO%\.venv\Scripts\python.exe
set LOG=%REPO%\data\widen_classifications.log

REM The default covers a Sunday comfortably at the measured rate and leaves the
REM store free long before the evening passes. A budget that does not reach the
REM end simply resumes next week - the tool takes the unclassified first.
set BUDGET=%~1
if "%BUDGET%"=="" set BUDGET=2000

if not exist "%PY%" (
  echo [%DATE% %TIME%] FATAL: no interpreter at %PY% >> "%LOG%"
  exit /b 3
)

REM Same preflight and the same reason as the other two wrappers: an interpreter
REM that exists is not an environment that works, and this pass talks to the
REM vendor.
"%PY%" -X utf8 "%REPO%\tools\preflight.py" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [%DATE% %TIME%] FATAL: preflight failed, classification pass not attempted >> "%LOG%"
  exit /b 3
)

REM Rotate at 50MB, the same ceiling the other logs use.
for %%F in ("%LOG%") do if %%~zF GTR 50000000 move /Y "%LOG%" "%LOG%.1" >nul 2>&1

echo. >> "%LOG%"
echo ===== [%DATE% %TIME%] classification pass starting, budget %BUDGET% >> "%LOG%"

"%PY%" -X utf8 "%REPO%\tools\refresh_classifications.py" --data "%REPO%\data" --universe --budget %BUDGET% >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%

echo ===== [%DATE% %TIME%] classification pass finished, exit %RC% >> "%LOG%"

REM `HANDOFF.md` section 2 owns the classification census and is generated
REM (`AGENTS.md` 10.6), so the pass that CHANGES it rebuilds it. A held store is
REM not a failure: `build_state.py` reports the runtime block UNAVAILABLE and
REM leaves it alone.
"%PY%" -X utf8 "%REPO%\tools\build_state.py" >> "%LOG%" 2>&1

exit /b %RC%
