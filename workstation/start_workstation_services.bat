@echo off
title Reachy Workstation Services Launcher
echo ===================================================
echo   Reachy Workstation Services Launcher
echo ===================================================
echo.
echo 🎤 Starting Pocket-TTS Server on port 8057...
start "Pocket-TTS Server" cmd /k "cd /d I:\AI_stuff\pocket-tts && venv\Scripts\python.exe run_server_windows.py"

echo 🌐 Starting ngrok Tunnel for Pi Dashboard...
start "ngrok Tunnel" cmd /k "cd /d i:\ && ngrok.exe http --url=townie.backyard.ngrok.dev 192.168.0.130:8080"

echo.
echo ===================================================
echo Services launched! 
echo Check the new console windows to verify:
echo 1. Pocket-TTS shows "Starting FastAPI server on port 8057..."
echo 2. ngrok shows active status for townie.backyard.ngrok.dev
echo ===================================================
pause
