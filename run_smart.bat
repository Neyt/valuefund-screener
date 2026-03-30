@echo off
:: ============================================================
::  run_smart.bat  --  valuefund.substack.com
::  Smart daily analysis runner (parallel engine + skip registry)
::  Usage:
::    run_smart.bat          -- 1 batch of 50 stocks (default)
::    run_smart.bat all      -- process entire pending queue
::    run_smart.bat N        -- N rounds of 50 (e.g. run_smart.bat 4)
:: ============================================================

set PYTHON=D:\PythonEnvironments\miniforge3\python.exe
set SCRIPTS=D:\StockAnalysis\scripts
set LOGS=D:\StockAnalysis\logs
set PYTHONIOENCODING=utf-8

:: Create logs dir if missing
if not exist "%LOGS%" mkdir "%LOGS%"

:: Timestamped log file
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set dt=%%a
set LOGFILE=%LOGS%\smart_%dt:~0,8%_%dt:~8,6%.log

echo ============================================================ >> "%LOGFILE%"
echo  valuefund.substack.com  Smart Run  %date% %time%           >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"

echo.
echo  [run_smart] Starting Deep-Value Screener...
echo  Log: %LOGFILE%
echo.

:: ── Step 1: Build/refresh universe CSV ──────────────────────────────────────
echo  [1/4] Refreshing universe candidates...
echo [Step 1] universe_builder >> "%LOGFILE%"
%PYTHON% "%SCRIPTS%\universe_builder.py" >> "%LOGFILE%" 2>&1
echo  [1/4] Done.

:: ── Step 2: Run analysis ────────────────────────────────────────────────────
echo  [2/4] Running analysis...
echo [Step 2] parallel_engine >> "%LOGFILE%"

if /I "%~1"=="all" (
    echo  Mode: ALL pending stocks
    %PYTHON% "%SCRIPTS%\parallel_engine.py" --workers 4 --batch 50 --all >> "%LOGFILE%" 2>&1
) else if "%~1"=="" (
    echo  Mode: Single batch ^(50 stocks^)
    %PYTHON% "%SCRIPTS%\parallel_engine.py" --workers 4 --batch 50 >> "%LOGFILE%" 2>&1
) else (
    echo  Mode: %~1 rounds
    for /L %%R in (1,1,%~1) do (
        echo  -- Round %%R of %~1 --
        %PYTHON% "%SCRIPTS%\parallel_engine.py" --workers 4 --batch 50 >> "%LOGFILE%" 2>&1
        if %%R lss %~1 (
            echo  Pausing 3 min before next round...
            timeout /t 180 /nobreak > nul
        )
    )
)
echo  [2/4] Done.

:: ── Step 3: Generate investment theses ──────────────────────────────────────
echo  [3/4] Generating investment theses...
echo [Step 3] generate_thesis >> "%LOGFILE%"
%PYTHON% "%SCRIPTS%\generate_thesis.py" >> "%LOGFILE%" 2>&1
echo  [3/4] Done.

:: ── Step 4: Rebuild dashboard ───────────────────────────────────────────────
echo  [4/4] Rebuilding dashboard...
echo [Step 4] generate_dashboard >> "%LOGFILE%"
%PYTHON% "%SCRIPTS%\generate_dashboard.py" >> "%LOGFILE%" 2>&1
echo  [4/4] Done.

:: ── Summary ─────────────────────────────────────────────────────────────────
echo.
echo  ============================================================
echo  Run complete! Check dashboard:
echo    D:\StockAnalysis\database\index.html
echo  Full log:
echo    %LOGFILE%
echo  ============================================================
echo.

:: Open dashboard in default browser
start "" "D:\StockAnalysis\database\index.html"
