@echo off
REM ---------------------------------------------------------------------------
REM deploy_only.bat  --  regenerate the paginated dashboard from the CURRENT
REM database and push it to Vercel, WITHOUT running any analysis.
REM
REM This is steps 2-4 of daily_analysis.bat, extracted so a refreshed database
REM can be published on demand (e.g. after a manual catch-up batch) without
REM burning another analysis run.
REM
REM Exit codes: 0 ok | 2 VERCEL_TOKEN missing | other = paginator/deploy code
REM ---------------------------------------------------------------------------
setlocal enabledelayedexpansion
set LOG=D:\StockAnalysis\logs\daily_runs.log
echo [%date% %time%] deploy_only.bat: paginate + sync + deploy (no analysis) >> %LOG%
cd /d D:\StockAnalysis

set PYTHONIOENCODING=utf-8
D:\PythonEnvironments\miniforge3\python.exe scripts\screener_quality.py >> %LOG% 2>&1
set PAGINATE_RC=%ERRORLEVEL%
if not "%PAGINATE_RC%"=="0" (
    echo [%date% %time%] ERROR: dashboard_paginator.py exited with code !PAGINATE_RC! >> %LOG%
    exit /b !PAGINATE_RC!
)

copy /Y D:\StockAnalysis\database\index_paged.html D:\tools\valuefund-screener\public\screener.html >> %LOG% 2>&1
xcopy /Y /S D:\StockAnalysis\database\data\*.json D:\tools\valuefund-screener\public\data\ >> %LOG% 2>&1

if "%VERCEL_TOKEN%"=="" (
    echo [%date% %time%] ERROR: VERCEL_TOKEN is not set. >> %LOG%
    exit /b 2
)
cd /d D:\tools\valuefund-screener
call vercel deploy --prod --yes --token %VERCEL_TOKEN% >> %LOG% 2>&1
set DEPLOY_RC=%ERRORLEVEL%
if not "%DEPLOY_RC%"=="0" (
    echo [%date% %time%] ERROR: Vercel deploy failed with code !DEPLOY_RC! >> %LOG%
    exit /b !DEPLOY_RC!
)

echo [%date% %time%] deploy_only.bat: complete. >> %LOG%
exit /b 0
