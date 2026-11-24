@echo off
setlocal
pushd "%~dp0.." || exit /b 1

call python ".\main.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

popd
exit /b %EXIT_CODE%