@echo off
REM Mantem a janela aberta se o instalador interno for executado direto.
if /i not "%FRAMEZERO_KEEP_OPEN_SESSION%"=="1" if /i not "%FRAMEZERO_CHILD_KEEP_OPEN%"=="1" (
  set "FRAMEZERO_CHILD_KEEP_OPEN=1"
  start "FrameZero Clips Installer" cmd /k ""%~f0" %*"
  exit /b 0
)
chcp 65001 >nul
title FrameZero Clips 1.1.8 - Instalador v1.0.91
color 0E
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "UPDATE_PAYLOAD=%ROOT%Atualizacao_1.1.8\payload_raw"
set "STABLE=%APPDATA%\obs-studio\FrameZero"
set "APP=%STABLE%\app"
set "SITE_URL=https://clips.framezeroai.com.br/obs"
set "CURRENT_VERSION=1.1.8"
set "VERSION_URL=https://raw.githubusercontent.com/gabrielxreis/framezero-clips-releases/main/latest/version.json"
set "OBS_PATH_FILE=%STABLE%\.framezero\obs_path.txt"


REM Limpeza pesada oficial: remove sobras de Nations e versoes antigas antes de instalar.
set "OBSROOT=%APPDATA%\obs-studio"
set "OLD_STABLE=%OBSROOT%\FrameZero"


cls
echo ============================================================
echo  FRAMEZERO CLIPS 1.1.8 - INSTALADOR WINDOWS
echo ============================================================
echo.
echo Preparando o computador e instalando a versao mais recente.
echo A instalacao vai seguir automaticamente sem perguntas extras.
echo O Clips escuta o audio sem precisar iniciar gravacao no OBS.
echo.
set "OP=2"

call :ENSURE_OBS_WINDOWS
if errorlevel 1 call :FAIL "OBS Studio e obrigatorio antes de instalar o FrameZero."
echo.
echo Fechando processos antigos do FrameZero...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq FrameZero*" >nul 2>nul
taskkill /F /IM pythonw.exe /FI "WINDOWTITLE eq FrameZero*" >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765 :8766 :8889"') do taskkill /PID %%a /F >nul 2>nul

echo.
set "TMP_CFG=%TEMP%\framezero_config_backup_118.json"
if exist "%OLD_STABLE%\app\config.json" copy /y "%OLD_STABLE%\app\config.json" "%TMP_CFG%" >nul 2>nul
echo Limpando completamente versoes antigas, Nations e caches...
if exist "%OLD_STABLE%" rmdir /s /q "%OLD_STABLE%" >nul 2>nul
if exist "%OBSROOT%\FrameZero Nations" rmdir /s /q "%OBSROOT%\FrameZero Nations" >nul 2>nul
if exist "%OBSROOT%\FrameZeroNations" rmdir /s /q "%OBSROOT%\FrameZeroNations" >nul 2>nul
if exist "%OBSROOT%\Nations" rmdir /s /q "%OBSROOT%\Nations" >nul 2>nul
for /d %%D in ("%OBSROOT%\*nations*" "%OBSROOT%\*Nations*" "%OBSROOT%\*nation*" "%OBSROOT%\*Nation*") do rmdir /s /q "%%~fD" >nul 2>nul
for /d %%D in ("%USERPROFILE%\Downloads\*nations*" "%USERPROFILE%\Downloads\*Nations*") do rmdir /s /q "%%~fD" >nul 2>nul
echo Limpeza concluida. Instalando somente FrameZero Clips.

echo.
echo Aplicando plataforma 1.1.8 em:
echo %STABLE%
if not exist "%STABLE%" mkdir "%STABLE%"

robocopy "%UPDATE_PAYLOAD%" "%STABLE%" /E /XD "app\venv" "venv" ".framezero" "logs" "__pycache__" ".pytest_cache" /XF ".DS_Store" "config.json" >nul
if errorlevel 8 (
  call :FAIL "ERRO ao copiar arquivos do FrameZero 1.1.8. Verifique se a pasta Atualizacao_1.1.8\payload_raw existe e se o Windows permitiu copiar os arquivos."
)

if exist "%TMP_CFG%" (
  if not exist "%APP%" mkdir "%APP%"
  copy /y "%TMP_CFG%" "%APP%\config.json" >nul 2>nul
  del "%TMP_CFG%" >nul 2>nul
)
> "%STABLE%\framezero_local_version.json" echo {"version":"%CURRENT_VERSION%","installer_version":"1.0.91","online_installer_version":"1.0.91","app":"FrameZero Clips"}

call :PATCH_CONFIG
if errorlevel 1 call :FAIL "Falha ao finalizar a instalacao do FrameZero."
exit /b 0

:GET_OBS_PATH_WINDOWS
set "OBS_EXE="
set "OBS_DIR="
set "OBS_PATH_PS=%TEMP%\framezero_find_obs.ps1"
> "%OBS_PATH_PS%" echo $ErrorActionPreference='SilentlyContinue'
>> "%OBS_PATH_PS%" echo $paths = New-Object System.Collections.Generic.List[string]
>> "%OBS_PATH_PS%" echo $stable = Join-Path $env:APPDATA 'obs-studio\FrameZero'
>> "%OBS_PATH_PS%" echo $pathFile = Join-Path $stable '.framezero\obs_path.txt'
>> "%OBS_PATH_PS%" echo if(Test-Path $pathFile){ $p=(Get-Content $pathFile -Raw).Trim(); if($p){ $paths.Add($p) } }
>> "%OBS_PATH_PS%" echo $regKeys = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\obs64.exe','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\obs64.exe','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\obs64.exe')
>> "%OBS_PATH_PS%" echo foreach($k in $regKeys){ try { $v=(Get-ItemProperty $k).'(default)'; if($v){ $paths.Add($v) } } catch {} }
>> "%OBS_PATH_PS%" echo $uninstall = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\OBS Studio','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\OBS Studio','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\OBS Studio')
>> "%OBS_PATH_PS%" echo foreach($k in $uninstall){ try { $loc=(Get-ItemProperty $k).InstallLocation; if($loc){ $paths.Add((Join-Path $loc 'bin\64bit\obs64.exe')) } } catch {} }
>> "%OBS_PATH_PS%" echo $paths.Add($env:ProgramFiles + '\obs-studio\bin\64bit\obs64.exe')
>> "%OBS_PATH_PS%" echo if(${env:ProgramFiles(x86)}){ $paths.Add(${env:ProgramFiles(x86)} + '\obs-studio\bin\64bit\obs64.exe') }
>> "%OBS_PATH_PS%" echo $paths.Add($env:LOCALAPPDATA + '\Programs\obs-studio\bin\64bit\obs64.exe')
>> "%OBS_PATH_PS%" echo $paths.Add($env:LOCALAPPDATA + '\obs-studio\bin\64bit\obs64.exe')
>> "%OBS_PATH_PS%" echo $desktopLinks=@((Join-Path ([Environment]::GetFolderPath('Desktop')) '*.lnk'),(Join-Path $env:PUBLIC 'Desktop\*.lnk'),(Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs\**\*.lnk'),(Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs\**\*.lnk'))
>> "%OBS_PATH_PS%" echo try { $w=New-Object -ComObject WScript.Shell; foreach($pat in $desktopLinks){ Get-ChildItem $pat -ErrorAction SilentlyContinue ^| Where-Object { $_.Name -match 'OBS' } ^| ForEach-Object { $t=$w.CreateShortcut($_.FullName).TargetPath; if($t){ $paths.Add($t) } } } } catch {}
>> "%OBS_PATH_PS%" echo $obs = $paths ^| Where-Object { $_ -and (Test-Path $_) -and ((Split-Path $_ -Leaf) -ieq 'obs64.exe') } ^| Select-Object -First 1
>> "%OBS_PATH_PS%" echo if($obs){ $obs = (Resolve-Path $obs).Path; $dir=Split-Path $obs -Parent; New-Item -ItemType Directory -Force -Path (Split-Path $pathFile -Parent) ^| Out-Null; Set-Content -Encoding UTF8 $pathFile $obs; Write-Output ('OBS_EXE='+$obs); Write-Output ('OBS_DIR='+$dir) }
for /f "usebackq tokens=1,* delims==" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%OBS_PATH_PS%"`) do (
  if /i "%%A"=="OBS_EXE" set "OBS_EXE=%%B"
  if /i "%%A"=="OBS_DIR" set "OBS_DIR=%%B"
)
if defined OBS_EXE if not exist "%OBS_EXE%" set "OBS_EXE="
exit /b 0

:ENSURE_OBS_WINDOWS
echo.
echo ============================================================
echo  VERIFICANDO OBS STUDIO - OBRIGATORIO
echo ============================================================
echo Fonte oficial: https://obsproject.com/download
echo O instalador vai buscar o link atual direto da pagina oficial do OBS.
call :GET_OBS_PATH_WINDOWS
if defined OBS_EXE (
  echo OBS encontrado: %OBS_EXE%
  if not exist "%STABLE%\.framezero" mkdir "%STABLE%\.framezero" >nul 2>nul
  > "%OBS_PATH_FILE%" echo %OBS_EXE%
  exit /b 0
)
echo OBS nao encontrado. Instalando OBS Studio oficial antes do FrameZero...
set "OBS_INSTALLER=%TEMP%\FrameZero-OBS-Studio-Windows-x64-Installer.exe"
set "OBS_PS1=%TEMP%\framezero_download_obs.ps1"
> "%OBS_PS1%" echo $ErrorActionPreference='Stop'
>> "%OBS_PS1%" echo $page=Invoke-WebRequest -UseBasicParsing 'https://obsproject.com/download'
>> "%OBS_PS1%" echo $links=@($page.Links ^| Where-Object { $_.href -match 'OBS-Studio.*Windows.*x64.*Installer.*\.exe' })
>> "%OBS_PS1%" echo if(-not $links){ $links=@($page.Links ^| Where-Object { $_.href -match '\.exe' -and $_.href -match 'OBS-Studio' -and $_.href -match 'Windows' }) }
>> "%OBS_PS1%" echo if(-not $links){ throw 'Nao encontrei o instalador Windows do OBS na pagina oficial.' }
>> "%OBS_PS1%" echo $url=$links[0].href
>> "%OBS_PS1%" echo if($url -notmatch '^https?://'){ $url=[Uri]::new([Uri]'https://obsproject.com/download',$url).AbsoluteUri }
>> "%OBS_PS1%" echo Write-Host ('Baixando OBS oficial pelo link encontrado em obsproject.com/download: '+$url)
>> "%OBS_PS1%" echo Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile '%OBS_INSTALLER%'
powershell -NoProfile -ExecutionPolicy Bypass -File "%OBS_PS1%"
if errorlevel 1 (
  echo ERRO: falha ao localizar/baixar OBS Studio pela pagina oficial.
  exit /b 1
)
echo Executando instalador do OBS. Aguarde...
"%OBS_INSTALLER%" /S
if errorlevel 1 (
  echo AVISO: instalador silencioso retornou erro. Tentando modo normal.
  "%OBS_INSTALLER%"
)
timeout /t 5 >nul
call :GET_OBS_PATH_WINDOWS
if not defined OBS_EXE (
  echo ERRO: OBS ainda nao foi localizado depois da instalacao.
  echo Instale manualmente se necessario: https://obsproject.com/download
  exit /b 1
)
echo OBS instalado em: %OBS_EXE%
if not exist "%STABLE%\.framezero" mkdir "%STABLE%\.framezero" >nul 2>nul
> "%OBS_PATH_FILE%" echo %OBS_EXE%
exit /b 0

:PATCH_CONFIG
call :PATCH_CONFIG_FILE
call :INSTALL_DEPS
call :CREATE_UPDATER
call :CREATE_LAUNCHER
call :INSTALL_VBCABLE_WINDOWS
call :INSTALL_OBS_PLUGINS_WINDOWS
call :CONFIG_OBS_PROFILE
call :CONFIG_OBS_DOCK
call :VERIFY_INSTALL

echo.
echo ============================================================
echo FRAMEZERO CLIPS INSTALADO COM SUCESSO
echo ============================================================
echo.
echo O atalho foi criado na area de trabalho quando permitido.
echo Se nao aparecer, abra por este arquivo:
echo %STABLE%\INICIAR-FRAMEZERO-CMD.bat
echo.
if /i "%FRAMEZERO_CHILD_KEEP_OPEN%"=="1" pause
exit /b 0

:PATCH_CONFIG_FILE
if not exist "%APP%" mkdir "%APP%" >nul 2>nul
if not exist "%APP%\config.json" (
  > "%APP%\config.json" echo {"site_url":"%SITE_URL%","version":"%CURRENT_VERSION%"}
)
call :GET_OBS_PATH_WINDOWS
if defined OBS_EXE (
  if not exist "%STABLE%\.framezero" mkdir "%STABLE%\.framezero" >nul 2>nul
  > "%OBS_PATH_FILE%" echo %OBS_EXE%
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='%APP%\config.json'; $cfg=@{}; if(Test-Path $p){try{$cfg=Get-Content $p -Raw ^| ConvertFrom-Json}catch{$cfg=@{}}}; if($cfg -isnot [hashtable]){$h=@{}; $cfg.psobject.Properties ^| %% { $h[$_.Name]=$_.Value }; $cfg=$h}; $cfg.obs_exe_path='%OBS_EXE%'; $cfg.obs_installed=$true; $cfg ^| ConvertTo-Json -Depth 10 ^| Set-Content -Encoding UTF8 $p" >nul 2>nul
)
exit /b 0

:FIND_PYTHON
set "PYTHON_EXE="
for %%P in ("%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%PROGRAMFILES%\Python312\python.exe" "%PROGRAMFILES(x86)%\Python312\python.exe" "%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe") do (
  if exist "%%~P" if not defined PYTHON_EXE set "PYTHON_EXE=%%~P"
)
if not defined PYTHON_EXE (
  for /f "usebackq delims=" %%P in (`py -3.12 -c "import sys; print(sys.executable)" 2^>nul`) do if exist "%%P" set "PYTHON_EXE=%%P"
)
if not defined PYTHON_EXE (
  for /f "usebackq delims=" %%P in (`py -3 -c "import sys; print(sys.executable)" 2^>nul`) do if exist "%%P" set "PYTHON_EXE=%%P"
)
if not defined PYTHON_EXE (
  for /f "usebackq delims=" %%P in (`python -c "import sys; print(sys.executable)" 2^>nul`) do if exist "%%P" set "PYTHON_EXE=%%P"
)
if defined PYTHON_EXE (
  "%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>&1
  if errorlevel 1 set "PYTHON_EXE="
)
exit /b 0

:INSTALL_DEPS
echo.
echo Verificando Python e dependencias...
call :FIND_PYTHON
if not defined PYTHON_EXE (
  echo Python compatível nao encontrado. Baixando componente necessario...
  curl -fL -o "%TEMP%\python312_framezero.exe" https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe
  if errorlevel 1 call :FAIL "Falha ao baixar o Python necessario. Verifique internet, antivirus ou bloqueio do Windows."
  "%TEMP%\python312_framezero.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0
  if errorlevel 1 call :FAIL "Falha ao instalar o componente Python automaticamente."
  del "%TEMP%\python312_framezero.exe" >nul 2>nul
  set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
)
call :FIND_PYTHON
if not defined PYTHON_EXE call :FAIL "Python foi instalado, mas ainda nao foi localizado pelo instalador. Reinicie o computador e rode o instalador novamente."
echo Python OK: %PYTHON_EXE%
echo Criando ambiente Python do FrameZero...
if not exist "%APP%\venv" "%PYTHON_EXE%" -m venv "%APP%\venv"
if errorlevel 1 call :FAIL "Falha ao criar ambiente virtual Python venv."
if not exist "%APP%\venv\Scripts\activate.bat" call :FAIL "venv criado incompleto. Arquivo activate.bat nao encontrado."
call "%APP%\venv\Scripts\activate.bat"
set "REQ=%APP%\requirements-windows.txt"
if not exist "%REQ%" set "REQ=%APP%\requirements.txt"
echo Atualizando instalador de pacotes Python...
python -m pip install --upgrade pip wheel
if errorlevel 1 call :FAIL "Falha ao atualizar pip/wheel."
echo Instalando componentes base...
python -m pip install "setuptools<82"
if errorlevel 1 call :FAIL "Falha ao instalar setuptools."
echo Instalando dependencias do FrameZero. Esta etapa pode demorar alguns minutos.
echo Nao feche esta janela. O progresso dos pacotes vai aparecer abaixo.
python -m pip install --upgrade --upgrade-strategy only-if-needed -r "%REQ%"
if errorlevel 1 call :FAIL "Falha ao instalar requirements.txt. Pode ser internet, pacote travado ou antivirus."

echo Verificando FFmpeg obrigatorio para cortes...
call :INSTALL_FFMPEG_REQUIRED
if errorlevel 1 exit /b %ERRORLEVEL%
exit /b 0

:INSTALL_FFMPEG_REQUIRED
echo.
echo ============================================================
echo  INSTALANDO FFMPEG - COMPONENTE OBRIGATORIO DE CORTES
echo ============================================================
echo Esta etapa e obrigatoria para gerar cortes.
echo Em instalacao nova, o FFmpeg sera reinstalado para garantir que esta correto.
echo.
if /i "%FRAMEZERO_AUTO_INSTALL%"=="update" (
  if exist "%APP%\ffmpeg\bin\ffmpeg.exe" (
    echo FFmpeg OK: %APP%\ffmpeg\bin\ffmpeg.exe
    exit /b 0
  )
  where ffmpeg >nul 2>&1
  if not errorlevel 1 (
    echo FFmpeg OK: encontrado no sistema.
    exit /b 0
  )
)
if exist "%APP%\ffmpeg" rmdir /s /q "%APP%\ffmpeg" >nul 2>nul

echo Tentando instalar FFmpeg local via pacote Python menor...
python -m pip install --upgrade imageio-ffmpeg
if not errorlevel 1 (
  python -c "import imageio_ffmpeg, os, shutil; app=os.environ['APP']; dest=os.path.join(app,'ffmpeg','bin','ffmpeg.exe'); os.makedirs(os.path.dirname(dest), exist_ok=True); shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), dest); print('FFmpeg local instalado:', dest)"
  if exist "%APP%\ffmpeg\bin\ffmpeg.exe" (
    echo FFmpeg instalado com sucesso.
    exit /b 0
  )
)

echo.
echo Pacote menor falhou. Baixando pacote FFmpeg completo para Windows...
if exist "%TEMP%\ffmpeg_framezero" rmdir /s /q "%TEMP%\ffmpeg_framezero" >nul 2>nul
del /f /q "%TEMP%\ffmpeg_framezero.zip" >nul 2>nul
echo Progresso, velocidade e tempo aparecem abaixo.
curl -fL --progress-bar --retry 3 --connect-timeout 15 --speed-time 120 --speed-limit 2048 -o "%TEMP%\ffmpeg_framezero.zip" https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
if errorlevel 1 call :FAIL "Falha ao baixar FFmpeg. Sem FFmpeg os cortes nao funcionam. Verifique a internet/antivirus e rode novamente."
echo Extraindo FFmpeg...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force '%TEMP%\ffmpeg_framezero.zip' '%TEMP%\ffmpeg_framezero'"
if errorlevel 1 call :FAIL "Falha ao extrair FFmpeg."
for /d %%D in ("%TEMP%\ffmpeg_framezero\*") do (
  if not exist "%APP%\ffmpeg" mkdir "%APP%\ffmpeg"
  xcopy /e /i /y "%%D\bin" "%APP%\ffmpeg\bin" >nul
)
if not exist "%APP%\ffmpeg\bin\ffmpeg.exe" call :FAIL "FFmpeg foi baixado, mas o executavel nao foi encontrado."
rmdir /s /q "%TEMP%\ffmpeg_framezero" >nul 2>nul
del "%TEMP%\ffmpeg_framezero.zip" >nul 2>nul
echo FFmpeg instalado com sucesso.
exit /b 0


:INSTALL_VBCABLE_WINDOWS
echo.
echo ============================================================
echo  VERIFICANDO VB-AUDIO VB-CABLE - WINDOWS
echo ============================================================
echo O VB-CABLE ajuda o FrameZero a ouvir a saida/loopback do Windows para transcricao.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$names=@(); try{$names += (Get-PnpDevice -Class MEDIA -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FriendlyName)}catch{}; try{$names += (Get-CimInstance Win32_SoundDevice -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)}catch{}; $txt=($names -join ' '); if($txt -match 'VB-Audio|VB Audio|VB-CABLE|CABLE Input|CABLE Output|VBCABLE'){ exit 0 } else { exit 1 }" >nul 2>nul
if not errorlevel 1 (
  echo OK: VB-CABLE detectado.
  exit /b 0
)
echo VB-CABLE nao detectado. Baixando instalador oficial VB-Audio...
set "VB_TMP=%TEMP%\framezero_vbcable"
if exist "%VB_TMP%" rmdir /s /q "%VB_TMP%" >nul 2>nul
mkdir "%VB_TMP%" >nul 2>nul
set "VB_ZIP=%VB_TMP%\VBCABLE_Driver_Pack45.zip"
curl.exe -fL --retry 2 --connect-timeout 20 --progress-bar -o "%VB_ZIP%" "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip"
if errorlevel 1 (
  echo Aviso: nao consegui baixar VB-CABLE agora. Continuando a instalacao do FrameZero.
  exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force -LiteralPath '%VB_ZIP%' -DestinationPath '%VB_TMP%'"
set "VB_SETUP="
for /f "usebackq delims=" %%F in (`dir /b /s "%VB_TMP%\VBCABLE_Setup_x64.exe" 2^>nul`) do if not defined VB_SETUP set "VB_SETUP=%%F"
if not defined VB_SETUP for /f "usebackq delims=" %%F in (`dir /b /s "%VB_TMP%\VBCABLE_Setup.exe" 2^>nul`) do if not defined VB_SETUP set "VB_SETUP=%%F"
if not defined VB_SETUP (
  echo Aviso: instalador do VB-CABLE nao encontrado no pacote baixado. Continuando.
  exit /b 0
)
echo Abrindo instalador VB-CABLE com permissao de administrador...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%VB_SETUP%' -Verb RunAs -Wait -ArgumentList '-i'" >nul 2>nul
if errorlevel 1 echo Aviso: o Windows bloqueou ou cancelou o instalador VB-CABLE. Continuando.
echo VB-CABLE: etapa concluida. Se o dispositivo ainda nao aparecer, reinicie o Windows uma vez.
exit /b 0

:DOWNLOAD_GITHUB_ASSET_WINDOWS
set "GH_REPO=%~1"
set "GH_REGEX=%~2"
set "GH_DEST=%~3"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $repo='%GH_REPO%'; $regex='%GH_REGEX%'; $dest='%GH_DEST%'; $headers=@{'Accept'='application/vnd.github+json';'User-Agent'='FrameZeroInstaller'}; $r=Invoke-RestMethod -Headers $headers -Uri ('https://api.github.com/repos/'+$repo+'/releases/latest'); $asset=$r.assets | Where-Object { $_.name -match $regex } | Select-Object -First 1; if(-not $asset){ exit 2 }; Write-Host ('Baixando componente OBS: '+$asset.name); curl.exe -L --fail --retry 2 --connect-timeout 20 --progress-bar -o $dest $asset.browser_download_url"
exit /b %ERRORLEVEL%

:INSTALL_OBS_PLUGINS_WINDOWS
 echo.
 echo ============================================================
 echo  INSTALANDO PLUGINS AUXILIARES DO OBS
 echo ============================================================
 echo O Clips escuta o audio sem precisar iniciar gravacao no OBS.
 echo Instalando/verificando Aitum Vertical e Aitum Multistream quando possivel.
 set "PLUG_TMP=%TEMP%\DEFINA_FZ_VPS_TOKEN"
 if not exist "%PLUG_TMP%" mkdir "%PLUG_TMP%" >nul 2>nul
 call :DOWNLOAD_GITHUB_ASSET_WINDOWS "Aitum/obs-vertical-canvas" "vertical.*windows.*installer.*\.exe$" "%PLUG_TMP%\aitum-vertical.exe"
 if not errorlevel 1 (
   echo Instalando Aitum Vertical...
   start /wait "" "%PLUG_TMP%\aitum-vertical.exe" /S
 ) else (
   echo Aviso: Aitum Vertical nao foi baixado agora. Continuando.
 )
 call :DOWNLOAD_GITHUB_ASSET_WINDOWS "Aitum/obs-aitum-multistream" "(multistream|multi).*windows.*installer.*\.exe$" "%PLUG_TMP%\aitum-multistream.exe"
 if not errorlevel 1 (
   echo Instalando Aitum Multistream...
   start /wait "" "%PLUG_TMP%\aitum-multistream.exe" /S
 ) else (
   echo Aviso: Aitum Multistream nao foi baixado agora. Continuando.
 )
 echo Plugins OBS: etapa concluida.
 exit /b 0

:CREATE_FFMPEG_BACKGROUND
echo Criando baixador de FFmpeg em segundo plano...
(
echo @echo off
echo chcp 65001 ^>nul
echo title FrameZero - preparando componente de cortes
echo color 0A
echo set "APP=%APP%"
echo if exist "%%APP%%\ffmpeg\bin\ffmpeg.exe" exit /b 0
echo echo ============================================================
echo echo FRAMEZERO - COMPONENTE DE CORTES
echo echo ============================================================
echo echo Baixando FFmpeg em segundo plano. O Clips ja pode ser usado.
echo echo Quando terminar, os cortes finais ficam habilitados automaticamente.
echo echo.
echo curl -fL --retry 2 --connect-timeout 10 --speed-time 30 --speed-limit 2048 -o "%%TEMP%%\ffmpeg_framezero.zip" https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
echo if errorlevel 1 ^(echo Falha ao baixar FFmpeg. Rode o instalador novamente depois. ^& pause ^& exit /b 1^)
echo if exist "%%TEMP%%\ffmpeg_framezero" rmdir /s /q "%%TEMP%%\ffmpeg_framezero" ^>nul 2^>nul
echo powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force '%%TEMP%%\ffmpeg_framezero.zip' '%%TEMP%%\ffmpeg_framezero'"
echo if errorlevel 1 ^(echo Falha ao extrair FFmpeg. ^& pause ^& exit /b 1^)
echo for /d %%%%D in ^("%%TEMP%%\ffmpeg_framezero\*"^) do ^(
echo   if not exist "%%APP%%\ffmpeg" mkdir "%%APP%%\ffmpeg"
echo   xcopy /e /i /y "%%%%D\bin" "%%APP%%\ffmpeg\bin" ^>nul
echo ^)
echo rmdir /s /q "%%TEMP%%\ffmpeg_framezero" ^>nul 2^>nul
echo del "%%TEMP%%\ffmpeg_framezero.zip" ^>nul 2^>nul
echo echo.
echo echo FFmpeg instalado. Os cortes finais ja estao liberados.
echo timeout /t 5 ^>nul
) > "%STABLE%\BAIXAR-FFMPEG-BACKGROUND.bat"
exit /b 0


:CREATE_UPDATER
echo.
echo Criando verificador automatico de atualizacao...
if not exist "%STABLE%" mkdir "%STABLE%" >nul 2>nul
if exist "%STABLE%\FrameZero-Update-Check.ps1" (
  echo OK: verificador automatico de atualizacao instalado.
  exit /b 0
) else (
  echo ERRO: FrameZero-Update-Check.ps1 nao foi copiado para a pasta do FrameZero.
  echo Este arquivo e obrigatorio para o Core atualizar pelo GitHub antes de abrir.
  exit /b 1
)

:VERIFY_INSTALL
echo.
echo ============================================================
echo  VERIFICANDO INSTALACAO DO FRAMEZERO
echo ============================================================
set "VERIFY_ERRORS=0"
if exist "%APP%\servidor.py" (echo OK: servidor local instalado.) else (echo ERRO: servidor.py nao encontrado. & set /a VERIFY_ERRORS+=1)
if exist "%APP%\venv\Scripts\python.exe" (echo OK: ambiente Python instalado.) else (echo ERRO: Python venv nao encontrado. & set /a VERIFY_ERRORS+=1)
if exist "%APP%\config.json" (echo OK: config.json encontrado.) else (echo ERRO: config.json nao encontrado. & set /a VERIFY_ERRORS+=1)
if exist "%APP%\ffmpeg\bin\ffmpeg.exe" (
  echo OK: FFmpeg local instalado.
) else (
  where ffmpeg >nul 2>&1
  if not errorlevel 1 (echo OK: FFmpeg encontrado no sistema.) else (echo ERRO: FFmpeg nao encontrado. & set /a VERIFY_ERRORS+=1)
)
if exist "%STABLE%\INICIAR-FRAMEZERO-CMD.bat" (echo OK: inicializador criado.) else (echo ERRO: inicializador nao encontrado. & set /a VERIFY_ERRORS+=1)
if exist "%STABLE%\framezero_local_version.json" (echo OK: versao local registrada.) else (echo ERRO: versao local nao registrada. & set /a VERIFY_ERRORS+=1)
if exist "%APPDATA%\obs-studio\basic\profiles\FrameZero Clips\basic.ini" (echo OK: perfil/config OBS instalado.) else (echo AVISO: perfil/config OBS nao encontrado; o dock ainda foi tentado.)
if not "%VERIFY_ERRORS%"=="0" call :FAIL "A verificacao final encontrou problemas. Veja os itens marcados como ERRO acima."
echo Verificacao final OK. Tudo pronto para uso.
exit /b 0

:FAIL
echo.
echo ============================================================
echo  ERRO NA INSTALACAO DO FRAMEZERO
echo ============================================================
echo %~1
echo.
echo A janela vai ficar aberta para voce copiar o erro ou mandar print.
pause
exit /b 1

:CREATE_LAUNCHER
echo.
echo Conferindo inicializador do FrameZero copiado pelo payload...
if not exist "%STABLE%\INICIAR-FRAMEZERO-CMD.bat" call :FAIL "Inicializador INICIAR-FRAMEZERO-CMD.bat nao foi copiado para a pasta do FrameZero."
if not exist "%STABLE%\FrameZero-Configure-OBS-WebSocket.ps1" call :FAIL "Script de configuracao do OBS WebSocket nao foi copiado."
if not exist "%STABLE%\FrameZero-Start-OBS.ps1" call :FAIL "Script de abertura do OBS nao foi copiado."
call :CREATE_WINDOWS_SHORTCUTS
exit /b 0

:CREATE_WINDOWS_SHORTCUTS
echo.
echo Criando atalhos do FrameZero no Windows...
set "SHORTCUT_PS=%TEMP%\framezero_create_shortcuts.ps1"
> "%SHORTCUT_PS%" echo $ErrorActionPreference='SilentlyContinue'
>> "%SHORTCUT_PS%" echo $stable = $env:FRAMEZERO_STABLE
>> "%SHORTCUT_PS%" echo if([string]::IsNullOrWhiteSpace($stable)){ $stable = Join-Path $env:APPDATA 'obs-studio\FrameZero' }
>> "%SHORTCUT_PS%" echo $launcher = Join-Path $stable 'INICIAR-FRAMEZERO-CMD.bat'
>> "%SHORTCUT_PS%" echo $icon = Join-Path $stable 'assets\FrameZero.ico'
>> "%SHORTCUT_PS%" echo if(!(Test-Path $icon)){ $icon = Join-Path $stable 'framezero_icon.ico' }
>> "%SHORTCUT_PS%" echo $W = New-Object -ComObject WScript.Shell
>> "%SHORTCUT_PS%" echo $desktop = [Environment]::GetFolderPath('Desktop')
>> "%SHORTCUT_PS%" echo $startMenu = Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs\FrameZero'
>> "%SHORTCUT_PS%" echo foreach($old in @((Join-Path $desktop 'FrameZero Clips.lnk'),(Join-Path $desktop 'FrameZero Clips.bat'),(Join-Path $startMenu 'FrameZero Clips.lnk'),(Join-Path $startMenu 'FrameZero Clips.bat'))){ try { if(Test-Path $old){ Remove-Item -Force $old } } catch {} }
>> "%SHORTCUT_PS%" echo function New-FrameZeroShortcut($folder){
>> "%SHORTCUT_PS%" echo   if([string]::IsNullOrWhiteSpace($folder)){ return }
>> "%SHORTCUT_PS%" echo   New-Item -ItemType Directory -Force -Path $folder ^| Out-Null
>> "%SHORTCUT_PS%" echo   $lnk = Join-Path $folder 'FrameZero Clips.lnk'
>> "%SHORTCUT_PS%" echo   $s = $W.CreateShortcut($lnk)
>> "%SHORTCUT_PS%" echo   $s.TargetPath = $env:ComSpec
>> "%SHORTCUT_PS%" echo   $s.Arguments = '/k "' + $launcher + '"'
>> "%SHORTCUT_PS%" echo   $s.WorkingDirectory = $stable
>> "%SHORTCUT_PS%" echo   if(Test-Path $icon){ $s.IconLocation = $icon }
>> "%SHORTCUT_PS%" echo   $s.Description = 'Abrir FrameZero Clips com OBS e CMD visivel'
>> "%SHORTCUT_PS%" echo   $s.Save()
>> "%SHORTCUT_PS%" echo   Write-Host ('Atalho criado: ' + $lnk)
>> "%SHORTCUT_PS%" echo }
>> "%SHORTCUT_PS%" echo New-FrameZeroShortcut $desktop
>> "%SHORTCUT_PS%" echo New-FrameZeroShortcut $startMenu
set "FRAMEZERO_STABLE=%STABLE%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SHORTCUT_PS%"
if errorlevel 1 (
  echo Aviso: o Windows bloqueou a criacao automatica de atalho .lnk.
) else (
  echo OK: atalhos .lnk criados na Area de Trabalho e no Menu Iniciar do usuario.
)
REM Fallback .bat sem apagar o .lnk.
set "USER_DESKTOP=%USERPROFILE%\Desktop"
if not exist "%USER_DESKTOP%" mkdir "%USER_DESKTOP%" >nul 2>nul
if exist "%USER_DESKTOP%\FrameZero Clips.bat" del /f /q "%USER_DESKTOP%\FrameZero Clips.bat" >nul 2>nul
copy /y "%STABLE%\INICIAR-FRAMEZERO-CMD.bat" "%USER_DESKTOP%\FrameZero Clips.bat" >nul 2>nul
set "USER_START=%APPDATA%\Microsoft\Windows\Start Menu\Programs\FrameZero"
if not exist "%USER_START%" mkdir "%USER_START%" >nul 2>nul
if exist "%USER_START%\FrameZero Clips.bat" del /f /q "%USER_START%\FrameZero Clips.bat" >nul 2>nul
copy /y "%STABLE%\INICIAR-FRAMEZERO-CMD.bat" "%USER_START%\FrameZero Clips.bat" >nul 2>nul
if exist "%USER_DESKTOP%\FrameZero Clips.bat" echo OK: atalho fallback criado na Area de Trabalho.
if exist "%USER_START%\FrameZero Clips.bat" echo OK: atalho fallback criado no Menu Iniciar.
del "%SHORTCUT_PS%" >nul 2>nul
exit /b 0

:CONFIG_OBS_PROFILE
echo.
echo Instalando arquivo de configuracao/perfil do OBS...
set "OBS_PROFILE_DIR=%APPDATA%\obs-studio\basic\profiles\FrameZero Clips"
if not exist "%OBS_PROFILE_DIR%" mkdir "%OBS_PROFILE_DIR%" >nul 2>nul
if exist "%STABLE%\config\perfil-obs" (
  xcopy /e /i /y "%STABLE%\config\perfil-obs\*" "%OBS_PROFILE_DIR%\" >nul 2>nul
  if exist "%OBS_PROFILE_DIR%\basic.ini" (
    echo OK: perfil OBS instalado em %OBS_PROFILE_DIR%
  ) else (
    echo Aviso: tentei copiar o perfil OBS, mas o basic.ini nao apareceu.
  )
) else (
  echo Aviso: pasta config\perfil-obs nao encontrada no pacote.
)
exit /b 0

:CONFIG_OBS_DOCK
echo.
echo Configurando dock do OBS para o painel web...
if exist "%STABLE%\tools\configure_obs_dock.py" (
  "%APP%\venv\Scripts\python.exe" "%STABLE%\tools\configure_obs_dock.py"
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$obs=Join-Path $env:APPDATA 'obs-studio'; $targets=@(Join-Path $obs 'user.ini', Join-Path $obs 'global.ini'); foreach($p in $targets){ if(!(Test-Path $p)){ New-Item -ItemType File -Force -Path $p | Out-Null }; $txt=Get-Content $p -Raw -ErrorAction SilentlyContinue; if($txt -notmatch '\[BasicWindow\]'){ Add-Content $p "`n[BasicWindow]" }; $dock='ExtraBrowserDocks=[{""title"":""FrameZero Clips"",""url"":""https://clips.framezeroai.com.br/obs""}]'; $txt=Get-Content $p -Raw; if($txt -match 'ExtraBrowserDocks='){ $txt=[regex]::Replace($txt,'ExtraBrowserDocks=.*',$dock); Set-Content -Encoding UTF8 $p $txt } else { Add-Content $p $dock } }; $g=Join-Path $obs 'global.ini'; $txt=Get-Content $g -Raw; if($txt -notmatch '\[OBSWebSocket\]'){ Add-Content $g "`n[OBSWebSocket]" }; $txt=Get-Content $g -Raw; foreach($pair in @('ServerEnabled=true','ServerPort=4455','AuthRequired=false','AlertsEnabled=false','FirstLoad=false')){ $k=$pair.Split('=')[0]; if($txt -match ('(?m)^'+$k+'=')){ $txt=[regex]::Replace($txt,('(?m)^'+$k+'.*'),$pair) } else { $txt += "`r`n$pair" } }; Set-Content -Encoding UTF8 $g $txt; Write-Host 'OK: dock e OBS WebSocket conferidos.'" 2>nul
exit /b 0
