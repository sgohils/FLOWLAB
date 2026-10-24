@echo off
REM ===========================================================================
REM  FLOWLAB - one command to install, check and run everything on Windows.
REM
REM    run.bat             start the API and the frontend dev server (default)
REM    run.bat install     install backend and frontend dependencies
REM    run.bat lint        ruff over backend\ plus the source encoding check
REM    run.bat test        run the backend test suite
REM    run.bat build       production build of the frontend
REM    run.bat check       the whole gate: ruff, mypy, tests, encoding,
REM                        typecheck, frontend tests and frontend build
REM    run.bat doctor      check the environment only
REM    run.bat /?          this list
REM
REM  Everything runs locally.  The first analysis downloads the YOLO weights once.
REM ===========================================================================
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "SCRIPT_DIR=%CD%"

REM --- 1. Arguments ------------------------------------------------------------
set "CMD=start"
if not "%~1"=="" (
    if /i "%~1"=="/?"       set "CMD=help"
    if /i "%~1"=="--help"  set "CMD=help"
    if /i "%~1"=="help"    set "CMD=help"
    if /i "%~1"=="start"   set "CMD=start"
    if /i "%~1"=="install" set "CMD=install"
    if /i "%~1"=="lint"    set "CMD=lint"
    if /i "%~1"=="test"    set "CMD=test"
    if /i "%~1"=="build"   set "CMD=build"
    if /i "%~1"=="check"   set "CMD=check"
    if /i "%~1"=="doctor"  set "CMD=doctor"
)

if "%CMD%"=="help" goto help

REM --- 2. Find a Python that actually works ------------------------------------
REM "python" on PATH is often the Microsoft Store stub.  A stub answers `-V` and
REM fails at everything else, and in a batch file the failure is invisible, so
REM every candidate is proved by running real code through it: `import sys` must
REM succeed AND pip must answer.  The pip half is what catches the repository's
REM own broken .venv - an empty python.exe with no site-packages that starts
REM happily and then dies with a confusing ImportError three commands later.
set "PY="
set "PYBROKEN="

for %%C in (python py python3) do (
    if not defined PY (
        call :probe "%%C"
        if "!PYOK!"=="1" set "PY=%%C"
    )
)

if not defined PY if exist ".venv\Scripts\python.exe" (
    call :probe ".venv\Scripts\python.exe"
    if "!PYOK!"=="1" (
        set "PY=.venv\Scripts\python.exe"
    ) else (
        set "PYBROKEN=.venv\Scripts\python.exe - run.bat install"
    )
)

if not defined PY (
    for %%V in (313 312 311) do (
        if not defined PY (
            if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
                call :probe "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
                if "!PYOK!"=="1" set "PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
            )
        )
    )
)

if not defined PY (
    if defined PYBROKEN (
        echo.
        echo The virtual environment in this repository is broken: !PYBROKEN!
        echo   It starts, but it has no pip and no installed packages, so every
        echo   command below would fail with a confusing ImportError.
        echo.
        echo Fix it with:            run.bat install
        echo or start over with:     rmdir /s /q .venv
        echo.
    ) else (
        echo.
        echo Python 3.11 or newer was not found.
        echo   - install it from https://www.python.org/downloads/ and tick
        echo     "Add python.exe to PATH", or
        echo   - create a virtual environment:  python -m venv .venv
        echo.
    )
    exit /b 1
)

REM Read the version through a temp file rather than `for /f`: `for /f` mangles
REM a quoted interpreter path, and the path may contain spaces.
set "PYVERFILE=%TEMP%\flowlab_pyver.txt"
set "PYVER="
"%PY%" -c "import sys;print(sys.version.split()[0])" > "%PYVERFILE%" 2>nul
if exist "%PYVERFILE%" set /p PYVER=<"%PYVERFILE%"
if exist "%PYVERFILE%" del /q "%PYVERFILE%" >nul 2>&1
if not defined PYVER set "PYVER=unknown"
echo Using Python !PYVER!  (!PY!)
if defined PYBROKEN echo Ignored broken virtual environment: !PYBROKEN!

REM Node is only required by the commands that touch frontend/.  `doctor` and
REM the backend gates must work when the thing you are diagnosing is Node.
if not "%CMD%"=="doctor" if not "%CMD%"=="lint" if not "%CMD%"=="test" (
    where node >nul 2>&1
    if errorlevel 1 (
        echo.
        echo Node.js was not found on PATH. Install Node 20+ from https://nodejs.org
        exit /b 1
    )
)

REM --- 3. Dispatch -------------------------------------------------------------
if "%CMD%"=="doctor"  goto doctor
if "%CMD%"=="lint"    goto lint
if "%CMD%"=="test"    goto test
if "%CMD%"=="install" goto install
if "%CMD%"=="build"   goto build
if "%CMD%"=="check"   goto check

goto start

REM ---------------------------------------------------------------------------
:start
echo.
echo Starting FLOWLAB...
echo   API      http://127.0.0.1:8000  (docs at /docs)
echo   Frontend http://127.0.0.1:5173
echo.
echo Press Ctrl+C in either window to stop it.
echo.
start "FLOWLAB API" cmd /k "!PY! -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
timeout /t 3 /nobreak >nul
start "FLOWLAB UI" cmd /k "cd /d ""%SCRIPT_DIR%\frontend"" && npm run dev"
goto end

REM ---------------------------------------------------------------------------
:lint
call :section "lint - ruff"
"%PY%" -m ruff check backend
if errorlevel 1 goto lintfail
call :section "lint - source encoding"
"%PY%" -m backend.scripts.check_encoding
if errorlevel 1 goto lintfail
echo.
echo Lint passed.
goto end

:lintfail
echo.
echo Lint FAILED.
exit /b 1

REM ---------------------------------------------------------------------------
:test
call :section "test - backend suite"
"%PY%" -m pytest backend\tests
if errorlevel 1 goto testfail
call :section "test - source encoding"
"%PY%" -m backend.scripts.check_encoding
if errorlevel 1 goto testfail
goto end

:testfail
echo.
echo Tests FAILED.
exit /b 1

REM ---------------------------------------------------------------------------
:build
call :section "build - frontend production bundle"
pushd "%SCRIPT_DIR%\frontend"
call npm run build
set "BUILDRC=!ERRORLEVEL!"
popd
if not "!BUILDRC!"=="0" (
    echo.
    echo Frontend build FAILED.
    exit /b !BUILDRC!
)
echo.
echo Built frontend\dist - the API serves it automatically when it exists.
goto end

REM ---------------------------------------------------------------------------
:check
REM mypy is here, not only in CI.  CONTRIBUTING.md promises that `check` runs
REM the same set of checks CI does, and that promise was false while mypy was
REM missing: a type error that fails .github/workflows/ci.yml passed locally.
call :section "check 1/6 - ruff"
"%PY%" -m ruff check backend
if errorlevel 1 goto checkfail
call :section "check 2/6 - mypy"
"%PY%" -m mypy
if errorlevel 1 goto checkfail
call :section "check 3/6 - backend tests"
"%PY%" -m pytest backend\tests
if errorlevel 1 goto checkfail
call :section "check 4/6 - source encoding"
"%PY%" -m backend.scripts.check_encoding
if errorlevel 1 goto checkfail
call :section "check 5/6 - frontend type check and tests"
pushd "%SCRIPT_DIR%\frontend"
call npm run typecheck
if errorlevel 1 (popd & goto checkfail)
call npm test
if errorlevel 1 (popd & goto checkfail)
popd
call :section "check 6/6 - frontend build"
pushd "%SCRIPT_DIR%\frontend"
call npm run build
if errorlevel 1 (popd & goto checkfail)
popd
echo.
echo ============================================================
echo  ALL CHECKS PASSED
echo ============================================================
goto end

:checkfail
echo.
echo ============================================================
echo  CHECKS FAILED - see the output above
echo ============================================================
exit /b 1

REM ---------------------------------------------------------------------------
:install
call :section "install - backend runtime dependencies"
"%PY%" -m pip install -r backend\requirements.txt
if errorlevel 1 goto installfail
call :section "install - backend development dependencies (pytest, ruff, mypy)"
"%PY%" -m pip install -r backend\requirements-dev.txt
if errorlevel 1 goto installfail
call :section "install - frontend dependencies"
pushd "%SCRIPT_DIR%\frontend"
call npm install
if errorlevel 1 (popd & goto installfail)
popd
echo.
echo Installed.  Next: run.bat doctor, then run.bat.
goto end

:installfail
echo.
echo Install FAILED.
exit /b 1

REM ---------------------------------------------------------------------------
:doctor
"%PY%" -m backend.scripts.doctor
goto end

REM ---------------------------------------------------------------------------
:help
echo.
echo   run.bat             start the API and the frontend dev server (default)
echo   run.bat install     install backend and frontend dependencies
echo   run.bat lint        ruff over backend\ plus the source encoding check
echo   run.bat test        run the backend test suite
echo   run.bat build       production build of the frontend
echo   run.bat check       everything: ruff, mypy, backend tests, source
echo                       encoding, frontend typecheck, frontend tests and
echo                       frontend build
echo   run.bat doctor      check the environment only
echo   run.bat /?          this list
echo.
exit /b 0

REM ---------------------------------------------------------------------------
REM Subroutines
REM
REM :probe <interpreter> - sets PYOK to 1 when it runs and has pip, else 0.
:probe
set "PYOK=0"
"%~1" -c "import sys" >nul 2>&1 || goto :probe_end
"%~1" -m pip --version >nul 2>&1 || goto :probe_end
set "PYOK=1"
:probe_end
exit /b 0

REM :section <title> - a visible header so the output stays readable as it scrolls.
:section
echo.
echo ==== %~1 ==========================================================
exit /b 0

:end
endlocal & exit /b 0
