@echo off
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

if "%DISCORD_WEBHOOK_URL%"=="" (
  set "DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/1523248671448109076/t56ns5o9CaJki4ebL08RlsAA7E8dd-dpYOxnVRKE6z_9lKEYTrrBzUGf6tL4n_xHbOaY"
)

:menu
cls
echo =========================================================
echo       FACE RECOGNITION DOOR SYSTEM - AI O TY
echo =========================================================
echo.
echo   1. Start Main Listener (Recognition + Discord)
echo   2. Capture New Face
echo   3. Train Model
echo   4. Test Webcam
echo   5. Exit
echo.
choice /C 12345 /N /M "=^> Choose an option (1-5): "

if errorlevel 5 goto end
if errorlevel 4 goto run_test
if errorlevel 3 goto run_train
if errorlevel 2 goto run_capture
if errorlevel 1 goto run_listener

goto menu

:run_listener
cls
echo [MAIN SYSTEM] Starting face recognition and Discord...
"C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" -u firebase_face_recognition_listener.py --camera 0 --threshold 0.42 --frames 5 --discord-webhook "%DISCORD_WEBHOOK_URL%" --notify-known
pause
goto menu

:run_capture
cls
echo [CAPTURE FACE] Starting camera... (Enter Student ID and Name)
"C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" capture_known_face.py
echo.
choice /C YN /N /M "Do you want to Train the model now? (y/n): "
if errorlevel 2 goto menu
if errorlevel 1 goto run_train
goto menu

:run_train
cls
echo [TRAIN MODEL] Training model from captured images...
"C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" train_known_faces.py
echo.
echo Training complete!
pause
goto menu

:run_test
cls
echo [TEST WEBCAM] Starting Test Camera... (Press Q or ESC to exit)
"C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" test_face_recognition_webcam.py
pause
goto menu

:end
exit
