cd ..\
rd /s/q .\__pycache__
rd /s/q .\OlivOS\__pycache__
rd /s/q .\build
rd /s/q .\dist
del /f/s/q .\main.spec
del /f/s/q .\OlivOS.exe
pyinstaller -F -i .\resource\favoricon.ico .\main.py --additional-hooks-dir=.\hook
move /y .\dist\main.exe .\dist\OlivOS.exe
copy /y .\dist\OlivOS.exe .\OlivOS.exe
cd .\script
