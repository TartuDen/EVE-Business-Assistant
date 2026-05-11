@echo off
setlocal

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5174"
set "API_BASE=http://127.0.0.1:%BACKEND_PORT%"
set "APP_URL=http://127.0.0.1:%FRONTEND_PORT%"

if not exist "%BACKEND%\.venv\Scripts\python.exe" (
  echo Backend virtual environment was not found.
  echo Expected: %BACKEND%\.venv\Scripts\python.exe
  echo.
  echo Create it first from the backend folder:
  echo   python -m venv .venv
  echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

if not exist "%FRONTEND%\node_modules" (
  echo Frontend dependencies were not found.
  echo Expected: %FRONTEND%\node_modules
  echo.
  echo Install them first from the frontend folder:
  echo   npm install
  pause
  exit /b 1
)

echo Starting EVE Business Assistant...
echo Backend:  %API_BASE%
echo Frontend: %APP_URL%
echo.

start "EVE Business Assistant API" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location '%BACKEND%'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port %BACKEND_PORT%"

start "EVE Business Assistant Web" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location '%FRONTEND%'; $env:VITE_API_BASE='%API_BASE%'; npm run dev -- --port %FRONTEND_PORT%"

timeout /t 4 /nobreak >nul
start "" "%APP_URL%"

echo Started. You can close this window.
endlocal
