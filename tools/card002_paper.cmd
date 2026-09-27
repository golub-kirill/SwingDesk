@echo off
REM ---------------------------------------------------------------------------
REM CARD-002 on the paper account - DR-054. Two scheduled tasks call this:
REM
REM   tools\card002_paper.cmd close    "SwingDesk night close", 14:35 Central
REM                                    (15:35 ET), weekdays
REM   tools\card002_paper.cmd exit     "SwingDesk night exit",  18:10 Central
REM                                    (19:10 ET), weekdays
REM   tools\card002_paper.cmd morning  "SwingDesk day protect", 08:40 Central
REM                                    (09:40 ET), weekdays - DR-056's day leg
REM
REM The close mode fetches the two funds FIRST: the pass sizes from the prior
REM session's close, and on 2026-09-20 the store held VB a session behind, so
REM a pass that trusted it refused a fund a two-second request would have
REM brought current (runbook section 11.1). The store refuses an unclosed bar,
REM so a fetch during the session never writes today's partial print.
REM
REM Exit codes are the pass's own and travel to the Task Scheduler's Last
REM Result column: 0 done, 2 refused (outside the window, no session, the
REM switch stopped - clean for gate 26), 3 ALERT (a night still held, or a
REM filled buy with no exit lodged), 4 unavailable. A 3 is the machinery being
REM wrong and gate 26 reports it as a failed run, which is the point.
REM ---------------------------------------------------------------------------

setlocal
set REPO=%~dp0..
set PY=%REPO%\.venv\Scripts\python.exe
set LOG=%REPO%\data\card002_paper.log
set MODE=%~1

if not exist "%PY%" (
  echo [%DATE% %TIME%] FATAL: no interpreter at %PY% >> "%LOG%"
  exit /b 4
)
if not "%MODE%"=="close" if not "%MODE%"=="exit" if not "%MODE%"=="morning" (
  echo [%DATE% %TIME%] FATAL: mode must be close, exit or morning, got "%MODE%" >> "%LOG%"
  exit /b 4
)

for %%F in ("%LOG%") do if %%~zF GTR 20000000 move /Y "%LOG%" "%LOG%.1" >nul 2>&1

echo. >> "%LOG%"
echo ===== [%DATE% %TIME%] card002 %MODE% pass starting >> "%LOG%"

if "%MODE%"=="close" "%PY%" -X utf8 "%REPO%\tools\fetch_history.py" --data "%REPO%\data" IJR VB SPY >> "%LOG%" 2>&1
REM The exit pass values the night it sells and sizes the day leg from this session's closes,
REM and at 19:10 ET the evening run has not fetched them yet (DR-056 section 2).
if "%MODE%"=="exit" "%PY%" -X utf8 "%REPO%\tools\fetch_history.py" --data "%REPO%\data" IJR VB SPY >> "%LOG%" 2>&1

"%PY%" -X utf8 "%REPO%\tools\card002_paper.py" %MODE% --data "%REPO%\data" >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%

echo ===== [%DATE% %TIME%] card002 %MODE% pass finished, exit %RC% >> "%LOG%"
exit /b %RC%
