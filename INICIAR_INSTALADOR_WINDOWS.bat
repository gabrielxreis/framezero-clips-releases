@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Iniciar Instalador FrameZero Windows

REM FrameZero Windows Bootstrap v1.0.91
REM Antes de iniciar o instalador real, limpa TEMP/cache/versoes locais antigas
REM e baixa sempre o instalador Windows mais recente do GitHub.

set "BOOTSTRAP_PS=%TEMP%\FrameZero_PreClean_And_Start.ps1"

> "%BOOTSTRAP_PS%" echo $ErrorActionPreference = 'SilentlyContinue'
>> "%BOOTSTRAP_PS%" echo taskkill /F /IM python.exe 2^> $null
>> "%BOOTSTRAP_PS%" echo taskkill /F /IM pythonw.exe 2^> $null
>> "%BOOTSTRAP_PS%" echo taskkill /F /IM obs64.exe 2^> $null
>> "%BOOTSTRAP_PS%" echo Remove-Item "$env:TEMP\FrameZeroOnlineInstaller" -Recurse -Force -ErrorAction SilentlyContinue
>> "%BOOTSTRAP_PS%" echo Remove-Item "$env:LOCALAPPDATA\Temp\FrameZeroOnlineInstaller" -Recurse -Force -ErrorAction SilentlyContinue
>> "%BOOTSTRAP_PS%" echo Remove-Item "$env:APPDATA\obs-studio\FrameZero\framezero_local_version.json" -Force -ErrorAction SilentlyContinue
>> "%BOOTSTRAP_PS%" echo Remove-Item "$env:APPDATA\obs-studio\FrameZero\version.json" -Force -ErrorAction SilentlyContinue
>> "%BOOTSTRAP_PS%" echo Remove-Item "$env:APPDATA\obs-studio\FrameZero\FrameZero-Update-Check.ps1" -Force -ErrorAction SilentlyContinue
>> "%BOOTSTRAP_PS%" echo $URL = "https://raw.githubusercontent.com/gabrielxreis/framezero-clips-releases/main/installers/FrameZero_Installer_1.0_Windows.bat"
>> "%BOOTSTRAP_PS%" echo $OUT = "$env:USERPROFILE\Downloads\FrameZero_Installer_Atualizado.bat"
>> "%BOOTSTRAP_PS%" echo Invoke-WebRequest -Uri $URL -OutFile $OUT -UseBasicParsing
>> "%BOOTSTRAP_PS%" echo if(Test-Path $OUT){ cmd /c "`"$OUT`""; exit $LASTEXITCODE }
>> "%BOOTSTRAP_PS%" echo exit 1

echo Limpando caches antigos e baixando o instalador atualizado do GitHub...
powershell -NoProfile -ExecutionPolicy Bypass -File "%BOOTSTRAP_PS%"
if errorlevel 1 goto LOCAL
exit /b %ERRORLEVEL%

:LOCAL
echo.
echo [AVISO] Nao foi possivel baixar o instalador novo agora. Abrindo instalador local...
call "%~dp0FrameZero_Installer_1.0_Windows.bat"
exit /b %ERRORLEVEL%
