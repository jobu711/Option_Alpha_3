@echo off
title Option Alpha - Dev Servers
echo Starting Option Alpha...
echo.

REM Kill any leftover processes on our ports
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173 " ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo [1/2] Starting FastAPI backend on http://localhost:8000
start /b cmd /c "uv run uvicorn src.Option_Alpha.web.app:create_app --factory --reload"

echo [2/2] Starting Vite frontend on http://localhost:5173
echo.
echo Press Ctrl+C to stop both servers.
echo.

cd web && npm run dev
