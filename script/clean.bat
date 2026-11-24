@echo off
setlocal
pushd "%~dp0.." || exit /b 1

set "EXIT_CODE=0"

call :remove_dir "__pycache__"
call :remove_dir "OlivOS\__pycache__"
call :remove_dir "script\__pycache__"
call :remove_dir "build"
call :remove_dir "dist"
call :remove_dir "main.build"
call :remove_dir "main.dist"
call :remove_dir "main.onefile-build"
call :remove_file "main.spec"
call :remove_file "OlivOS.exe"
call :remove_file "OlivOS_debug.exe"

popd
exit /b %EXIT_CODE%

:remove_dir
if exist "%~1" (
    rd /s /q "%~1"
    if exist "%~1" set "EXIT_CODE=1"
)
exit /b 0

:remove_file
if exist "%~1" (
    del /f /q "%~1"
    if exist "%~1" set "EXIT_CODE=1"
)
exit /b 0
