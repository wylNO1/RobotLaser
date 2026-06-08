@echo off
REM Run ikfast demo with project .venv (not system python)
setlocal
cd /d "%~dp0"

set PY=%~dp0.venv\Scripts\python.exe
if not exist "%PY%" (
    echo [ERROR] .venv not found. Create it and install deps:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r backend\requirements.txt
    exit /b 1
)

"%PY%" "%~dp0backend\scripts\run_ikfast_m20ia.py" %*
exit /b %ERRORLEVEL%
