@echo off
title Option Alpha - Dev Servers
echo Starting Option Alpha...
echo.

REM Kill any leftover Option Alpha processes on our ports
REM Only kills node.exe (Vite) and python.exe (uvicorn), not unrelated services
for /f "tokens=2,5" %%a in ('netstat -ano ^| findstr ":5173 " ^| findstr LISTENING') do (
    for /f "tokens=1" %%c in ('tasklist /FI "PID eq %%b" /NH 2^>nul ^| findstr /I "node"') do (
        echo Killing leftover Vite process PID %%b
        taskkill /PID %%b /F >nul 2>&1
    )
)
for /f "tokens=2,5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do (
    for /f "tokens=1" %%c in ('tasklist /FI "PID eq %%b" /NH 2^>nul ^| findstr /I "python"') do (
        echo Killing leftover uvicorn process PID %%b
        taskkill /PID %%b /F >nul 2>&1
    )
)

echo [1/2] Starting FastAPI backend on http://localhost:8000
start /b cmd /c "uv run uvicorn src.Option_Alpha.web.app:create_app --factory --reload"

echo [2/2] Starting Vite frontend on http://localhost:5173
echo.
echo Press Ctrl+C to stop both servers.
echo.

cd web && npm run dev
