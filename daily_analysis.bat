@echo off
setlocal enabledelayedexpansion
set LOG=D:\StockAnalysis\logs\daily_runs.log
set PY=D:\PythonEnvironments\miniforge3\python.exe
echo [%date% %time%] Starting daily stock analysis... >> %LOG%
cd /d D:\StockAnalysis

REM 1. Analyze stocks
REM    parallel_engine.py exit codes: 0=healthy (or queue legitimately empty)
REM    1=unhandled exception, 3=queue had work but analyzed ZERO, 4=below --fail-under
REM
REM    BATCH SIZE: 1200 (was 1000, of which ~933 succeeded).
REM    ~7.5k live tickers / 14-day staleness window = ~535 successful/day needed;
REM    1200 attempts at the observed ~93% yield gives ~1,115/day, so a whole
REM    missed day is absorbed by the next run instead of eating the window.
%PY% scripts\parallel_engine.py --workers 6 --batch 1200 >> %LOG% 2>&1
set ANALYZE_RC=%ERRORLEVEL%

if not "%ANALYZE_RC%"=="0" (
    echo [%date% %time%] ERROR: parallel_engine.py exited with code !ANALYZE_RC! >> %LOG%
    echo [%date% %time%] ERROR: See the RUN HEALTH block above for the reason. >> %LOG%
)

REM 2. Regenerate paginated dashboard
REM    Still run these even if the analysis failed, so the site keeps whatever
REM    good data already exists -- but remember the failure and exit non-zero.
set PYTHONIOENCODING=utf-8
%PY% scripts\screener_quality.py >> %LOG% 2>&1
set PAGINATE_RC=%ERRORLEVEL%
if not "%PAGINATE_RC%"=="0" (
    echo [%date% %time%] ERROR: dashboard_paginator.py exited with code !PAGINATE_RC! >> %LOG%
)

REM 2b. Daily value ranking (FMP first, database fallback, IBKR prices if TWS is open).
REM     Non-fatal: a failure here is logged but never fails the pipeline.
%PY% scripts\value_rank_daily.py --workers 6 --max-seconds 1200 >> %LOG% 2>&1
if not "%ERRORLEVEL%"=="0" echo [%date% %time%] WARNING: value_rank_daily.py exited with code %ERRORLEVEL% >> %LOG%

REM 3. Sync to Vercel project
copy /Y D:\StockAnalysis\database\index_paged.html D:\tools\valuefund-screener\public\screener.html >> %LOG% 2>&1
xcopy /Y /S D:\StockAnalysis\database\data\*.json D:\tools\valuefund-screener\public\data\ >> %LOG% 2>&1

REM 4. Redeploy to Vercel
if "%VERCEL_TOKEN%"=="" (
    echo [%date% %time%] ERROR: VERCEL_TOKEN is not set. >> %LOG%
    set FAIL_RC=2
    set FAIL_STAGE=deploy
    set FAIL_DETAIL=VERCEL_TOKEN env var missing - nothing was published
    goto :alert
)
cd /d D:\tools\valuefund-screener
call vercel deploy --prod --yes --token %VERCEL_TOKEN% >> %LOG% 2>&1
set DEPLOY_RC=%ERRORLEVEL%
cd /d D:\StockAnalysis
if not "%DEPLOY_RC%"=="0" (
    echo [%date% %time%] ERROR: Vercel deploy failed with code !DEPLOY_RC! >> %LOG%
    set FAIL_RC=!DEPLOY_RC!
    set FAIL_STAGE=deploy
    set FAIL_DETAIL=vercel deploy --prod failed - live site still shows yesterday
    goto :alert
)

REM 5. Final verdict -- this is what Task Scheduler's "Last Result" shows.
if not "%ANALYZE_RC%"=="0" (
    echo [%date% %time%] FAILED: daily analysis did no useful work ^(rc=!ANALYZE_RC!^). >> %LOG%
    set FAIL_RC=!ANALYZE_RC!
    set FAIL_STAGE=analyze
    set FAIL_DETAIL=parallel_engine.py reported an unhealthy run
    goto :alert
)
if not "%PAGINATE_RC%"=="0" (
    echo [%date% %time%] FAILED: dashboard pagination failed ^(rc=!PAGINATE_RC!^). >> %LOG%
    set FAIL_RC=!PAGINATE_RC!
    set FAIL_STAGE=paginate
    set FAIL_DETAIL=dashboard_paginator.py failed - JSON pages may be stale
    goto :alert
)

REM 6. Success path: still record status so the daily briefing can read it.
echo [%date% %time%] Daily analysis + deploy complete. >> %LOG%
%PY% scripts\notify.py --rc 0 --stage complete --detail "analysis + paginate + deploy all succeeded" >> %LOG% 2>&1
exit /b 0

REM ---------------------------------------------------------------------------
REM 7. Failure path. notify.py writes logs\last_run_status.json +
REM    logs\RUN_STATUS.txt, raises a Windows toast, and e-mails via Gmail SMTP.
REM    It always exits 0 so it can never mask the real code below.
REM ---------------------------------------------------------------------------
:alert
cd /d D:\StockAnalysis
%PY% scripts\notify.py --rc !FAIL_RC! --stage !FAIL_STAGE! --detail "!FAIL_DETAIL!" >> %LOG% 2>&1
exit /b !FAIL_RC!
