.\Python\scripts\pyinstaller -F -i .\resource\favoricon.ico .\main.py --additional-hooks-dir=.\hook
move /y .\dist\main.exe .\dist\OlivOS.exe
copy /y .\dist\OlivOS.exe .\OlivOS.exe
