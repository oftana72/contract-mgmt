@echo off
title Contract Management App
cd /d "C:\Users\oftan\AppData\Local\Temp\opencode\contract-mgmt"
set DATABASE_URL=mysql+pymysql://root:@localhost:3306/contract_mgmt
set PYTHON="C:\Users\oftan\AppData\Local\Programs\Python\Python312\python.exe"

echo [1/3] Checking MySQL...
netstat -ano 2>nul | findstr ":3306" >nul
if errorlevel 1 (
    net start wampmysqld64 2>nul
    timeout /t 5 /nobreak >nul
)
echo        MySQL OK

echo [2/3] Starting Flask app...
start /B "" %PYTHON% app.py
timeout /t 6 /nobreak >nul

echo [3/3] Opening browser...
start http://10.1.38.177:5000/
echo.
echo App running at http://10.1.38.177:5000/
echo Close this window to stop the app.
pause
