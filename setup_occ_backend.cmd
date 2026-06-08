@echo off
REM 使用已安装 pythonOCC 的 Conda 环境，并安装 FastAPI 后端依赖
set OCC_PYTHON=%USERPROFILE%\miniconda3\envs\occ\python.exe
if not exist "%OCC_PYTHON%" (
  echo [ERROR] 未找到 Conda 环境 occ: %OCC_PYTHON%
  echo 请先执行: conda create -n occ python=3.10 -y ^& conda install -n occ -c conda-forge pythonocc-core -y
  exit /b 1
)
echo Using: %OCC_PYTHON%
"%OCC_PYTHON%" -c "import OCC; print('pythonOCC OK:', OCC.__file__)"
"%OCC_PYTHON%" -m pip install -r "%~dp0backend\requirements.txt"
REM occ 环境 STEP-GLB 走 pythonOCC；cascadio 与 pythonOCC 同进程会 DLL 冲突 (0xC06D007F)
"%OCC_PYTHON%" -m pip uninstall cascadio -y 2>nul
REM 用 conda-forge 的 numpy + OpenBLAS 覆盖 pip numpy，修复 np.dot/np.linalg 崩溃 (0xC06D007F)
call conda install -n occ -c conda-forge "numpy>=2,<3" "libblas=*=*openblas" --force-reinstall -y
"%OCC_PYTHON%" -c "import numpy as np; np.linalg.eigh(np.eye(3)); print('numpy BLAS OK:', np.__version__)"
"%OCC_PYTHON%" -c "import OCC; import trimesh; print('STEP-GLB via pythonOCC OK')"
"%OCC_PYTHON%" -m pip install -r "%~dp0backend\requirements-dev.txt"
echo.
echo Done. In PyCharm: Settings - Project - Python Interpreter - Add - Conda - occ
echo Cursor/VSCode: already points to occ via .vscode/settings.json
pause
