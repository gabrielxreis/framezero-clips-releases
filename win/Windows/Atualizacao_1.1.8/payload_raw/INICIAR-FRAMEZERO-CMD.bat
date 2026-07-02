@echo off
chcp 65001 >nul
title FrameZero Clips 1.1.8
color 0A
set "ROOT=%APPDATA%\obs-studio\FrameZero"
set "APP=%ROOT%\app"
set "SITE_URL=https://clips.framezeroai.com.br/obs"
set "FRAMEZERO_STABLE=%ROOT%"

echo Verificando atualizacoes rapidamente...
if not exist "%ROOT%\FrameZero-Update-Check.ps1" (
  echo ERRO: updater obrigatorio nao encontrado: %ROOT%\FrameZero-Update-Check.ps1
  echo Rode o instalador novamente para restaurar o atualizador.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\FrameZero-Update-Check.ps1" -Stable "%ROOT%"
set "UPDATE_RC=%ERRORLEVEL%"
if "%UPDATE_RC%"=="10" (
  echo Atualizacao aplicada. Reabrindo FrameZero Clips...
  start "" "%ROOT%\INICIAR-FRAMEZERO-CMD.bat"
  exit /b 0
)
if not "%UPDATE_RC%"=="0" echo Nao foi possivel verificar/aplicar atualizacao agora. Continuando com a versao instalada.

echo.
echo Verificando arquivos e componentes obrigatorios antes de iniciar o Core...
if exist "%ROOT%\FrameZero-Windows-Preflight.bat" (
  call "%ROOT%\FrameZero-Windows-Preflight.bat"
) else (
  echo AVISO: preflight de componentes nao encontrado. O updater tentara restaurar na proxima abertura.
)

cd /d "%APP%"
if not exist "%APP%\venv\Scripts\python.exe" (
  echo Ambiente Python do FrameZero nao encontrado. Rode o instalador novamente.
  pause
  exit /b 1
)
if exist "%APP%\ffmpeg\bin\ffmpeg.exe" set "PATH=%APP%\ffmpeg\bin;%PATH%"

echo ============================================================
echo  FRAMEZERO CLIPS 1.1.8
echo ============================================================
echo Painel do OBS: %SITE_URL%
echo O painel nao sera aberto automaticamente pelo instalador.
echo Deixe esta janela aberta enquanto usa o FrameZero.
echo.
echo Encerrando servidor antigo nas portas locais...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765 :8766 :8889"') do taskkill /PID %%a /F >nul 2>nul

echo Abrindo OBS...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\FrameZero-Configure-OBS-WebSocket.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\FrameZero-Start-OBS.ps1"
timeout /t 3 >nul

echo.
echo Iniciando servidor local...
if exist "%APP%\venv\Scripts\activate.bat" call "%APP%\venv\Scripts\activate.bat"
python "%APP%\servidor.py"
echo.
echo O servidor FrameZero foi encerrado ou apresentou erro.
echo Esta janela fica aberta para mostrar o motivo.
pause
