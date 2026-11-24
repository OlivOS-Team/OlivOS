@echo off
setlocal
pushd "%~dp0.." || exit /b 1

call "%~dp0clean.bat"
if errorlevel 1 (
    popd
    exit /b 1
)

call python -m PyInstaller ".\OlivOS.spec"
set "EXIT_CODE=%ERRORLEVEL%"

if "%EXIT_CODE%"=="0" (
    if exist ".\dist\OlivOS.exe" (
        copy /y ".\dist\OlivOS.exe" ".\OlivOS.exe" >nul
        if errorlevel 1 set "EXIT_CODE=1"
    ) else (
        echo [pack] PyInstaller succeeded but dist\OlivOS.exe is missing.>&2
        set "EXIT_CODE=1"
    )
)

popd
exit /b %EXIT_CODE%
