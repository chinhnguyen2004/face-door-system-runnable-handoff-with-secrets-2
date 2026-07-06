@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
"C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" firebase_face_recognition_listener.py --camera 0 --threshold 0.36 --frames 10 --duration 7 --show-camera
pause

