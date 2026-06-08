@echo off
REM Build M-20iA/35M ikfast shared library (Windows, MinGW g++)
setlocal
cd /d "%~dp0"

set OUT_DIR=lib
set OUT_DLL=%OUT_DIR%\m20ia_35m_ik.dll

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

where g++ >nul 2>&1
if errorlevel 1 (
    echo [ERROR] g++ not found. Install: winget install BrechtSanders.WinLibs.POSIX.UCRT
    exit /b 1
)

echo [build] ikfast_export.cpp + M-20iA_35M.cpp -^> %OUT_DLL%
g++ -std=c++11 -O2 -DIKFAST_NO_MAIN -shared ikfast_export.cpp "M-20iA_35M.cpp" -o "%OUT_DLL%" -static-libgcc -static-libstdc++
if errorlevel 1 exit /b 1

echo [OK] %OUT_DLL%
exit /b 0
