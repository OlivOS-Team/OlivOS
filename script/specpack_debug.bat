cd ..\
rd /s/q .\__pycache__
rd /s/q .\OlivOS\__pycache__
rd /s/q .\build
rd /s/q .\dist
del /f/s/q .\OlivOS_debug.exe
pyinstaller .\main_debug.spec
move /y .\dist\main.exe .\dist\OlivOS_debug.exe
copy /y .\dist\OlivOS_debug.exe .\OlivOS_debug.exe
cd .\script
