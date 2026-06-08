@echo off
REM 优先使用 Conda occ 环境（含 pythonOCC）；否则回退到项目 .venv
set OCC_PYTHON=%USERPROFILE%\miniconda3\envs\occ\python.exe
set VENV_PYTHON=%~dp0.venv\Scripts\python.exe

if exist "%OCC_PYTHON%" (
  set PY=%OCC_PYTHON%
  set OCC_PYTHON=%PY%
  echo [run_server] Using Conda occ: %PY%
) else if exist "%VENV_PYTHON%" (
  set PY=%VENV_PYTHON%
  echo [run_server] WARNING: Using .venv without pythonOCC. CAD APIs will return 501.
) else (
  echo [ERROR] No Python found. Run setup_occ_backend.cmd first.
  exit /b 1
)

cd /d "%~dp0backend"
set PYTHONNOUSERSITE=1
"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
