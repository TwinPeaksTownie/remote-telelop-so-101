@echo off
setlocal
set TARGET=user@192.168.0.130

if "%~1"=="" goto restart

if "%~1"=="status" goto status
if "%~1"=="start" goto start
if "%~1"=="stop" goto stop
if "%~1"=="restart" goto restart
if "%~1"=="logs" goto logs

echo Usage: %~nx0 [status ^| start ^| stop ^| restart ^| logs]
goto end

:status
ssh %TARGET% "systemctl --user status rover-web-control.service"
goto end

:start
ssh %TARGET% "systemctl --user start rover-web-control.service"
goto end

:stop
ssh %TARGET% "systemctl --user stop rover-web-control.service"
goto end

:restart
ssh %TARGET% "systemctl --user restart rover-web-control.service"
goto end

:logs
ssh %TARGET% "tail -n 100 -f /tmp/rover_web.log"
goto end

:end
endlocal
