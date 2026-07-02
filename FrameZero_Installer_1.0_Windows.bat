@echo off
REM FrameZero Windows Installer v1.0.91
REM Bootstrap no mesmo conceito do Mac: baixa o pacote real, extrai e executa o instalador interno.
REM REGRA ABSOLUTA: nao alterar o desinstalador Windows validado enviado pelo usuario.

if /i not "%FRAMEZERO_KEEP_OPEN_SESSION%"=="1" (
  set "FRAMEZERO_KEEP_OPEN_SESSION=1"
  start "FrameZero Installer" cmd /k ""%~f0" %*"
  exit /b 0
)

setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title FrameZero Installer 1.0.91 - Windows
color 0A

set "CURRENT_INSTALLER_VERSION=1.0.91"
set "VERSION_URL=https://raw.githubusercontent.com/gabrielxreis/framezero-clips-releases/main/latest/version.json"
set "TMP_DIR=%TEMP%\FrameZeroOnlineInstaller"
set "VERSION_FILE=%TMP_DIR%\version.json"
set "CLIPS_ZIP=%TMP_DIR%\clips_windows.zip"
set "CLIPS_DIR=%TMP_DIR%\clips"
set "NATIONS_ZIP=%TMP_DIR%\nations_windows.zip"
set "NATIONS_DIR=%TMP_DIR%\nations"
set "LANGUAGE=pt"
set "LOCAL_UNINSTALLER_1=%~dp0FrameZero_Uninstaller_1.0_Windows.bat"
set "LOCAL_UNINSTALLER_2=%~dp0DESINSTALAR_FRAMEZERO_COMPLETO_WINDOWS.bat"
set "LOCAL_UNINSTALLER_3=%~dp0uninstallers\FrameZero_Uninstaller_1.0_Windows.bat"
set "LOCAL_UNINSTALLER_4=%~dp0win\Windows\DESINSTALAR_FRAMEZERO_COMPLETO.bat"
set "TEMP_UNINSTALLER=%TMP_DIR%\FrameZero_Uninstaller_1.0_Windows.bat"
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%" >nul 2>nul

if /i "%~1"=="--nations-langs-background" (
  call :WELCOME
  call :LOAD_MANIFEST || exit /b 1
  call :INSTALL_NATIONS
  exit /b %ERRORLEVEL%
)

call :WELCOME
call :LOAD_MANIFEST || goto MAIN_MENU
call :SELF_UPDATE_IF_NEEDED
call :MAIN_MENU
goto END

:HEADER
cls
echo ============================================================
echo                 FrameZero Installer 1.0.91 - Windows
echo ============================================================
echo  @gabrielxreis_                         @framezeroai
echo ============================================================
exit /b 0

:WELCOME
call :HEADER
echo Seja bem-vindo ao instalador oficial do FrameZero.
echo.
echo Este instalador e so o bootstrap: ele baixa sempre o instalador real mais recente e prepara tudo automaticamente.
echo Depois que voce escolher instalar, ele segue direto sem perguntas extras.
echo.
exit /b 0

:PAUSE_MENU
echo.
pause
exit /b 0

:DOWNLOAD_FILE
set "DL_URL=%~1"
set "DL_OUT=%~2"
set "DL_LABEL=%~3"
echo %DL_LABEL%
where curl.exe >nul 2>nul
if not errorlevel 1 (
  curl.exe -fL --connect-timeout 10 --max-time 600 --output "%DL_OUT%" "%DL_URL%"
  exit /b %ERRORLEVEL%
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='Continue'; Invoke-WebRequest -UseBasicParsing -Uri '%DL_URL%' -OutFile '%DL_OUT%'"
exit /b %ERRORLEVEL%

:READ_JSON
set "%~2="
for /f "usebackq delims=" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; $j=Get-Content -LiteralPath '%VERSION_FILE%' -Raw ^| ConvertFrom-Json; $v=$j.%~1; if($null -ne $v){[string]$v}" 2^>nul`) do set "%~2=%%A"
exit /b 0

:LOAD_MANIFEST
call :HEADER
echo Seja bem-vindo ao FrameZero.
echo O instalador verifica atualizacoes e prepara o Windows antes de instalar ou abrir o app.
echo.
call :DOWNLOAD_FILE "%VERSION_URL%" "%VERSION_FILE%" "Baixando informacoes de versao"
if errorlevel 1 (
  echo.
  echo [ERRO] Nao consegui baixar as informacoes de versao.
  exit /b 1
)
call :READ_JSON latest_version LATEST_VERSION
call :READ_JSON release_name RELEASE_NAME
call :READ_JSON windows_url WINDOWS_URL
call :READ_JSON nations_available NATIONS_AVAILABLE
call :READ_JSON nations_windows_url NATIONS_URL
call :READ_JSON online_installer_version ONLINE_INSTALLER_VERSION
call :READ_JSON online_installer_windows_url ONLINE_INSTALLER_WINDOWS_URL
call :READ_JSON uninstaller_windows_url UNINSTALLER_URL
if "%WINDOWS_URL%"=="" set "WINDOWS_URL=https://github.com/gabrielxreis/framezero-clips-releases/raw/main/windows/FrameZero_Clips_1.1.8_Windows.zip"
if "%NATIONS_URL%"=="" set "NATIONS_URL=https://github.com/gabrielxreis/framezero-clips-releases/raw/main/nations/windows/FrameZero_Nations_v55_Windows.zip"
if "%UNINSTALLER_URL%"=="" set "UNINSTALLER_URL=https://github.com/gabrielxreis/framezero-clips-releases/raw/main/uninstallers/FrameZero_Uninstaller_1.0_Windows.bat"
exit /b 0

:VERSION_GT
powershell -NoProfile -ExecutionPolicy Bypass -Command "try{ if([version]'%~1' -gt [version]'%~2'){exit 0}else{exit 1} }catch{exit 1}" >nul 2>nul
exit /b %ERRORLEVEL%

:SELF_UPDATE_IF_NEEDED
if /i "%FRAMEZERO_NO_SELF_UPDATE%"=="1" exit /b 0
if "%ONLINE_INSTALLER_VERSION%"=="" exit /b 0
if "%ONLINE_INSTALLER_WINDOWS_URL%"=="" exit /b 0
call :VERSION_GT "%ONLINE_INSTALLER_VERSION%" "%CURRENT_INSTALLER_VERSION%"
if errorlevel 1 exit /b 0
echo.
echo Atualizacao do instalador encontrada: %ONLINE_INSTALLER_VERSION%
echo Baixando o instalador novo do GitHub antes de continuar...
set "NEW_INSTALLER=%TMP_DIR%\FrameZero_Installer_%ONLINE_INSTALLER_VERSION%_Windows.bat"
call :DOWNLOAD_FILE "%ONLINE_INSTALLER_WINDOWS_URL%" "%NEW_INSTALLER%" "Baixando instalador atualizado"
if errorlevel 1 (
  echo [AVISO] Nao consegui atualizar o instalador. Continuando com este mesmo.
  exit /b 0
)
set "FRAMEZERO_NO_SELF_UPDATE=1"
call "%NEW_INSTALLER%"
exit /b %ERRORLEVEL%

:DOWNLOAD_AND_RUN
set "PKG_URL=%~1"
set "ZIP_PATH=%~2"
set "EXTRACT_DIR=%~3"
set "SEARCH_NAME=%~4"
set "LABEL=%~5"
if exist "%ZIP_PATH%" del /f /q "%ZIP_PATH%" >nul 2>nul
if exist "%EXTRACT_DIR%" rmdir /s /q "%EXTRACT_DIR%" >nul 2>nul
mkdir "%EXTRACT_DIR%" >nul 2>nul
echo.
call :DOWNLOAD_FILE "%PKG_URL%" "%ZIP_PATH%" "%LABEL%"
if errorlevel 1 (
  echo.
  echo [ERRO] download failed.
  exit /b 1
)
echo Extraindo pacote...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force -LiteralPath '%ZIP_PATH%' -DestinationPath '%EXTRACT_DIR%'"
if errorlevel 1 (
  echo [ERRO] extract failed.
  exit /b 1
)
set "FOUND_SCRIPT="
for /f "usebackq delims=" %%F in (`dir /b /s "%EXTRACT_DIR%\%SEARCH_NAME%" 2^>nul`) do if not defined FOUND_SCRIPT set "FOUND_SCRIPT=%%F"
if not defined FOUND_SCRIPT (
  echo [ERRO] Nenhum instalador encontrado no pacote baixado.
  exit /b 1
)
echo Executando instalador interno...
call :RUN_BATCH_IN_ITS_FOLDER "%FOUND_SCRIPT%"
exit /b %ERRORLEVEL%

:RUN_BATCH_IN_ITS_FOLDER
set "RUN_SCRIPT=%~1"
set "RUN_DIR="
set "RUN_FILE="
for %%I in ("%RUN_SCRIPT%") do (
  set "RUN_DIR=%%~dpI"
  set "RUN_FILE=%%~nxI"
)
if not exist "%RUN_SCRIPT%" (
  echo [ERRO] Arquivo nao encontrado: %RUN_SCRIPT%
  exit /b 1
)
pushd "%RUN_DIR%" >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Nao consegui abrir a pasta do instalador interno.
  exit /b 1
)
set "FRAMEZERO_CHILD_KEEP_OPEN=1"
set "FRAMEZERO_KEEP_OPEN_SESSION=1"
call "%RUN_FILE%"
set "RUN_RC=%ERRORLEVEL%"
popd >nul 2>nul
exit /b %RUN_RC%

:INSTALL_CLIPS
call :DOWNLOAD_AND_RUN "%WINDOWS_URL%" "%CLIPS_ZIP%" "%CLIPS_DIR%" "INSTALAR_FRAMEZERO_CLIPS_1.1.8_PLATAFORMA_COMPLETA.bat" "Baixando FrameZero Clips"
exit /b %ERRORLEVEL%

:INSTALL_NATIONS
REM PATCH UNICO v1.0.84: opcao [3] Nations nao depende mais do campo nations_available.
REM O instalador Windows v1.0.80 fica preservado; somente libera o pacote adicional.
if "%NATIONS_URL%"=="" set "NATIONS_URL=https://github.com/gabrielxreis/framezero-clips-releases/raw/main/nations/windows/FrameZero_Nations_v55_Windows.zip"
if "%NATIONS_URL%"=="" (
  echo [NATIONS] Pacote do Nations nao encontrado.
  exit /b 0
)
call :DOWNLOAD_AND_RUN "%NATIONS_URL%" "%NATIONS_ZIP%" "%NATIONS_DIR%" "INSTALAR_FRAMEZERO_NATIONS.bat" "Baixando FrameZero Nations"
exit /b %ERRORLEVEL%

:ENSURE_CLIPS_CORE_AND_COMPONENTS
set "FZ_ROOT=%APPDATA%\obs-studio\FrameZero"
set "FZ_APP=%FZ_ROOT%\app"
if not exist "%FZ_APP%\servidor.py" (
  echo.
  echo Core do FrameZero Clips nao encontrado. Instalando Clips antes do Nations...
  call :INSTALL_CLIPS
  if errorlevel 1 exit /b %ERRORLEVEL%
)
if exist "%FZ_ROOT%\FrameZero-Windows-Preflight.bat" (
  echo.
  echo Verificando VB-CABLE, Aitum Vertical e Aitum Multistream antes do Nations...
  call "%FZ_ROOT%\FrameZero-Windows-Preflight.bat"
) else (
  echo.
  echo Preflight de componentes nao encontrado. Reparando arquivos do Clips antes do Nations...
  call :INSTALL_CLIPS
  if errorlevel 1 exit /b %ERRORLEVEL%
)
exit /b 0

:INSTALL_NATIONS_BACKGROUND
if /i not "%NATIONS_AVAILABLE%"=="true" if /i not "%NATIONS_AVAILABLE%"=="True" exit /b 0
echo.
echo Baixando idiomas do Nations em segundo plano.
echo O FrameZero Clips ja pode ser usado enquanto os idiomas ficam disponiveis.
start "FrameZero Nations" cmd /c ""%~f0" --nations-langs-background"
exit /b 0

:RUN_LOCKED_UNINSTALLER
call :HEADER
echo DESINSTALAR FRAMEZERO COMPLETO - WINDOWS
echo.
echo Este comando vai abrir o desinstalador validado via PowerShell/admin.
echo O arquivo do desinstalador esta travado e nao foi alterado.
echo.
set "LOCKED_UNINSTALLER="
if exist "%LOCAL_UNINSTALLER_1%" set "LOCKED_UNINSTALLER=%LOCAL_UNINSTALLER_1%"
if not defined LOCKED_UNINSTALLER if exist "%LOCAL_UNINSTALLER_2%" set "LOCKED_UNINSTALLER=%LOCAL_UNINSTALLER_2%"
if not defined LOCKED_UNINSTALLER if exist "%LOCAL_UNINSTALLER_3%" set "LOCKED_UNINSTALLER=%LOCAL_UNINSTALLER_3%"
if not defined LOCKED_UNINSTALLER if exist "%LOCAL_UNINSTALLER_4%" set "LOCKED_UNINSTALLER=%LOCAL_UNINSTALLER_4%"
if not defined LOCKED_UNINSTALLER (
  call :DOWNLOAD_FILE "%UNINSTALLER_URL%" "%TEMP_UNINSTALLER%" "Baixando desinstalador validado do GitHub"
  if exist "%TEMP_UNINSTALLER%" set "LOCKED_UNINSTALLER=%TEMP_UNINSTALLER%"
)
if not defined LOCKED_UNINSTALLER (
  echo [ERRO] Desinstalador validado nao encontrado.
  exit /b 1
)
call "%LOCKED_UNINSTALLER%"
exit /b %ERRORLEVEL%

:MAIN_MENU
call :HEADER
echo Seja bem-vindo ao FrameZero.
echo O instalador verifica atualizacoes e prepara o Windows antes de instalar ou abrir o app.
echo.
echo Versao Clips: %LATEST_VERSION% - %RELEASE_NAME%
echo.
echo O que voce deseja fazer?
echo.
echo [1] Instalar FrameZero Clips + Nations
echo [2] Instalar somente FrameZero Clips
echo [3] Instalar somente o pacote adicional Nations
echo [4] Verificar atualizacoes
echo [5] Desinstalar FrameZero completo
echo [6] Sair
echo.
set /p OPCAO="Opcao: "
if "%OPCAO%"=="1" goto OP_INSTALL_ALL
if "%OPCAO%"=="2" goto OP_INSTALL_CLIPS
if "%OPCAO%"=="3" goto OP_INSTALL_NATIONS
if "%OPCAO%"=="4" goto OP_CHECK_UPDATES
if "%OPCAO%"=="5" goto OP_UNINSTALL
if "%OPCAO%"=="6" exit /b 0
echo Opcao invalida.
call :PAUSE_MENU
goto MAIN_MENU

:OP_INSTALL_ALL
call :INSTALL_CLIPS
if not errorlevel 1 call :INSTALL_NATIONS_BACKGROUND
echo.
echo Acao concluida.
call :PAUSE_MENU
goto MAIN_MENU

:OP_INSTALL_CLIPS
call :INSTALL_CLIPS
echo.
echo Acao concluida.
call :PAUSE_MENU
goto MAIN_MENU

:OP_INSTALL_NATIONS
call :ENSURE_CLIPS_CORE_AND_COMPONENTS
if errorlevel 1 goto OP_INSTALL_NATIONS_DONE
call :INSTALL_NATIONS
:OP_INSTALL_NATIONS_DONE
echo.
echo Acao concluida.
call :PAUSE_MENU
goto MAIN_MENU

:OP_CHECK_UPDATES
call :LOAD_MANIFEST
echo.
echo Acao concluida.
call :PAUSE_MENU
goto MAIN_MENU

:OP_UNINSTALL
call :RUN_LOCKED_UNINSTALLER
echo.
echo Acao concluida.
call :PAUSE_MENU
goto MAIN_MENU

:END
echo.
echo Saindo do instalador FrameZero.
exit /b 0
