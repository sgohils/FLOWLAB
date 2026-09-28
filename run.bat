@echo off
REM FLOWLAB - one command to start everything on Windows.
REM
REM   run.bat              start the API and the frontend (default)
REM   run.bat doctor       check the environment only
REM   run.bat test         run the backend test suite
REM   run.bat install      install backend and frontend dependencies
REM   run.bat build        production build of the frontend
REM
REM Everything runs locally. The first analysis downloads the YOLO weights once.

setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM --- Find a working Python -------------------------------------------------
REM "python" on PATH is often the Microsoft Store stub, which fails in a batch
REM context, so every candidate is verified by actually running it.
set "PY="
for %%C in (python py python3) do (
    if not defined PY (
        %%C -c "import sys" >nul 2>&1 && set "PY=%%C"
    )
)
if not defined PY if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY (
    for %%V in (313 312 311) do (
        if not defined PY (
            if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
                "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" -c "import sys" >nul 2>&1 && set "PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
            )
        )
    )
)
if not defined PY (
    echo.
    echo Python 3.11 or newer was not found.
    echo   - install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH", or
    echo   - create a virtual environment:  python -m venv .venv
    echo.
    exit /b 1
)
for /f "delims=" %%V in ('%PY% -c "import sys;print(sys.version.split()[0])"') do set "PYVER=%%V"
echo Using Python !PYVER!  (%PY%)

where node >nul 2>&1 || (echo Node.js was not found on PATH. Install Node 18+ from https://nodejs.org & exit /b 1)

if /i "%~1"=="doctor"  goto doctor
if /i "%~1"=="test"    goto test
if /i "%~1"=="install" goto install
if /i "%~1"=="build"   goto build

echo.
echo Starting FLOWLAB...
echo   API      http://127.0.0.1:8000  (docs at /docs)
echo   Frontend http://127.0.0.1:5173
echo.
echo Press Ctrl+C in either window to stop it.
echo.

start "FLOWLAB API" cmd /k "%PY% -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
timeout /t 3 /nobreak >nul
start "FLOWLAB UI" cmd /k "cd /d "%~dp0frontend" && npm run dev"
goto end

:doctor
%PY% -m backend.scripts.doctor
goto end

:test
%PY% -m pytest backend/tests -q
%PY% -m backend.scripts.check_encoding
goto end

:install
%PY% -m pip install -r backend\requirements.txt || exit /b 1
pushd frontend
call npm install
popd
goto end

:build
pushd frontend
call npm run build
popd
goto end

:end
endlocal
