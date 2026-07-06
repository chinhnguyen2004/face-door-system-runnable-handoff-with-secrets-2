@echo off
cd /d "%~dp0"
echo Dashboard: http://localhost:8765/dashboard.html
start "" "http://localhost:8765/dashboard.html"
"C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" -m http.server 8765
pause
