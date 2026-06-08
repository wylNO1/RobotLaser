@echo off

setlocal

set VENV_PYTHON=%~dp0.venv\Scripts\python.exe
set UVICORN_ARGS=app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug --access-log

echo [run_server] Working directory: %~dp0backend
echo [run_server] Uvicorn args: %UVICORN_ARGS%

where conda >nul 2>nul

if %errorlevel%==0 (

  echo [run_server] Using Conda env: occ

  cd /d "%~dp0backend"

  set PYTHONNOUSERSITE=1
  set PYTHONUNBUFFERED=1

  conda run --no-capture-output -n occ python -u -m uvicorn %UVICORN_ARGS%

  exit /b %errorlevel%

)


if exist "%VENV_PYTHON%" (

  echo [run_server] WARNING: Using .venv without pythonOCC. CAD APIs will return 501.

  cd /d "%~dp0backend"

  set PYTHONNOUSERSITE=1
  set PYTHONUNBUFFERED=1

  "%VENV_PYTHON%" -u -m uvicorn %UVICORN_ARGS%

  exit /b %errorlevel%

)



echo [ERROR] No Python found. Install conda or create .venv.

exit /b 1

