@echo off
echo ========================================================
echo   Multimodal Video Forensics ^& OSINT Engine - Starting
echo ========================================================
echo.

echo [1/2] Starting Backend (FastAPI on port 8000)...
start "Backend - FastAPI" cmd /k "set PYTHONIOENCODING=utf-8 && cd /d "%~dp0backend" && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 2 /nobreak > nul

echo [2/2] Starting Frontend (Next.js on port 3000)...
start "Frontend - Next.js" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ========================================================
echo   Both servers are starting up!
echo   Open: http://localhost:3000
echo ========================================================
pause
