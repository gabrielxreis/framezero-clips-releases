@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\CONFIGURAR_OBS_FRAMEZERO_WINDOWS.ps1"
pause
