@echo off
cd /d "%~dp0"
echo Monitor Dashboard: http://localhost:8765/monitor.html
start "" "http://localhost:8765/monitor.html"
"C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" -m http.server 8765
pause
