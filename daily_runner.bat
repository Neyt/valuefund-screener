@echo off
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHON="C:\Program Files\Python310\python.exe"
set SCRIPTS=D:\StockAnalysis\scripts
set LOG=D:\StockAnalysis\logs\daily_%DATE:~-4,4%%DATE:~-7,2%%DATE:~0,2%.txt

if not exist "D:\StockAnalysis\logs" mkdir "D:\StockAnalysis\logs"
echo [%DATE% %TIME%] === valuefund.substack.com Daily Run === > %LOG%

echo [%DATE% %TIME%] Step 1: Running stock analyzer... >> %LOG%
%PYTHON% -X utf8 "%SCRIPTS%\analyzer.py" >> %LOG% 2>&1

echo [%DATE% %TIME%] Step 2: Regenerating dashboard... >> %LOG%
%PYTHON% -X utf8 -c "import sys; sys.path.insert(0,r'D:\StockAnalysis\scripts'); from generate_dashboard import generate_html_index; p=generate_html_index(); print('Dashboard OK:', p)" >> %LOG% 2>&1

echo [%DATE% %TIME%] Step 3: Opening Chrome dashboard... >> %LOG%
start "" "chrome.exe" "D:\StockAnalysis\database\index.html"

echo [%DATE% %TIME%] Done. >> %LOG%
echo COMPLETED >> %LOG%
