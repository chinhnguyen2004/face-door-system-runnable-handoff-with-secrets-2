@echo off
cd /d "%~dp0"
"C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" -m pip install --upgrade pip
"C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" -m pip install -r requirements.txt
pause
