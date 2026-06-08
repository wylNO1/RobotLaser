@echo off
REM Build ikfast DLL for FANUC M-20iA/35M (from repo root)
REM Requires MinGW g++ on PATH (install: winget install BrechtSanders.WinLibs.POSIX.UCRT)
cd /d "%~dp0backend\app\ikfast\m20ia_35m"
call build.cmd
if errorlevel 1 (
    echo.
    echo If g++ is missing, install MinGW then reopen terminal:
    echo   winget install BrechtSanders.WinLibs.POSIX.UCRT
    exit /b 1
)
echo.
echo Test: python backend\scripts\run_ikfast_m20ia.py status
exit /b 0
