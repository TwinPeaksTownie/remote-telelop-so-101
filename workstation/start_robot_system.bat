@echo off
title Reachy Robot System Launcher
echo ===================================================
echo   Reachy ^& Overlander-4 System Launcher
echo ===================================================
echo.
echo Running full bootstrap sequence...
python i:\start_teleop_services.py
echo.
echo ===================================================
echo Startup complete. Press any key to close this console.
echo ===================================================
pause >nul
