@echo off
title MarketPulse AI - Local Launcher
color 0A
echo ======================================================================
echo           MARKETPULSE AI - LOCAL LAUNCHER
echo ======================================================================
echo.
echo Starting Backend API Server (Uvicorn on port 8000)...
start "MarketPulse Backend" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo Starting Frontend UI Dev Server (Vite on port 5173)...
start "MarketPulse Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev -- --host 127.0.0.1 --port 5173"

echo.
echo Waiting 4 seconds for servers to initialize...
timeout /t 4 /nobreak >nul

echo Opening MarketPulse AI in your default web browser...
start http://localhost:5173

echo.
echo ======================================================================
echo  Servers are running!
echo  Credentials:
echo    Email:    demo@marketpulse.ai
echo    Password: DemoPassword123!
echo ======================================================================
pause
