@echo off
chcp 65001 >nul
setlocal EnableExtensions

echo.
echo ============================================================
echo  FRAMEZERO WINDOWS - VERIFICACAO DE COMPONENTES
echo ============================================================
echo Verificando VB-CABLE, Aitum Vertical e Aitum Multistream antes de iniciar...

call :INSTALL_VBCABLE_WINDOWS
call :INSTALL_AITUM_VERTICAL_WINDOWS
call :INSTALL_AITUM_MULTISTREAM_WINDOWS
call :ENSURE_FRAMEZERO_PYTHON_DEPS

echo Verificacao de componentes concluida.
exit /b 0


:ENSURE_FRAMEZERO_PYTHON_DEPS
echo.
echo Verificando dependencias Python do FrameZero...
set "FZ_APP=%APPDATA%\obs-studio\FrameZero\app"
set "FZ_PY=%FZ_APP%\venv\Scripts\python.exe"
if not exist "%FZ_PY%" (
  echo Aviso: venv Python ainda nao existe. O instalador de Clips vai preparar depois.
  exit /b 0
)
"%FZ_PY%" -c "import websockets, sounddevice, soundcard, numpy, requests; import obsws_python; print('OK')" >nul 2>nul
if not errorlevel 1 (
  echo OK: dependencias Python principais instaladas.
  exit /b 0
)
echo Instalando/reparando dependencias Python principais...
"%FZ_PY%" -m ensurepip --upgrade >nul 2>nul
"%FZ_PY%" -m pip install --upgrade pip
"%FZ_PY%" -m pip install "websockets>=12.0" "sounddevice>=0.4.6" "soundcard>=0.4.3" "numpy>=1.24.0" "requests>=2.31.0" "obsws-python>=1.7.0" "faster-whisper>=1.0.3" "scipy>=1.13.0"
if errorlevel 1 echo Aviso: alguma dependencia Python nao instalou agora. O Core tentara iniciar mesmo assim.
exit /b 0

:DOWNLOAD_GITHUB_ASSET_WINDOWS
set "GH_REPO=%~1"
set "GH_REGEX=%~2"
set "GH_DEST=%~3"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $repo='%GH_REPO%'; $regex='%GH_REGEX%'; $dest='%GH_DEST%'; $headers=@{'Accept'='application/vnd.github+json';'User-Agent'='FrameZeroInstaller'}; $r=Invoke-RestMethod -Headers $headers -Uri ('https://api.github.com/repos/'+$repo+'/releases/latest'); $asset=$r.assets | Where-Object { $_.name -match $regex } | Select-Object -First 1; if(-not $asset){ exit 2 }; Write-Host ('Baixando componente OBS: '+$asset.name); curl.exe -L --fail --retry 2 --connect-timeout 20 --progress-bar -o $dest $asset.browser_download_url"
exit /b %ERRORLEVEL%

:DETECT_AITUM_VERTICAL_WINDOWS
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; $roots=@($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:APPDATA, $env:LOCALAPPDATA) | Where-Object { $_ }; $patterns=@('*vertical*canvas*.dll','*aitum*vertical*.dll','*obs-vertical-canvas*.dll'); foreach($root in $roots){ $obs=Join-Path $root 'obs-studio'; if(Test-Path $obs){ foreach($pat in $patterns){ $hit=Get-ChildItem -LiteralPath $obs -Recurse -File -Filter $pat -ErrorAction SilentlyContinue | Select-Object -First 1; if($hit){ exit 0 } } } }; exit 1" >nul 2>nul
exit /b %ERRORLEVEL%

:DETECT_AITUM_MULTISTREAM_WINDOWS
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; $roots=@($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:APPDATA, $env:LOCALAPPDATA) | Where-Object { $_ }; $patterns=@('*multistream*.dll','*multi*stream*.dll','*aitum*multi*.dll','*obs-aitum-multistream*.dll'); foreach($root in $roots){ $obs=Join-Path $root 'obs-studio'; if(Test-Path $obs){ foreach($pat in $patterns){ $hit=Get-ChildItem -LiteralPath $obs -Recurse -File -Filter $pat -ErrorAction SilentlyContinue | Select-Object -First 1; if($hit){ exit 0 } } } }; exit 1" >nul 2>nul
exit /b %ERRORLEVEL%

:INSTALL_VBCABLE_WINDOWS
echo.
echo Verificando VB-Audio VB-CABLE...
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
  echo Aviso: nao consegui baixar VB-CABLE agora. Continuando.
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

:INSTALL_AITUM_VERTICAL_WINDOWS
echo.
echo Verificando Aitum Vertical / OBS Vertical Canvas...
call :DETECT_AITUM_VERTICAL_WINDOWS
if not errorlevel 1 (
  echo OK: Aitum Vertical Canvas ja detectado. Nao vou reinstalar.
  exit /b 0
)
set "PLUG_TMP=%TEMP%\DEFINA_FZ_VPS_TOKEN"
if not exist "%PLUG_TMP%" mkdir "%PLUG_TMP%" >nul 2>nul
call :DOWNLOAD_GITHUB_ASSET_WINDOWS "Aitum/obs-vertical-canvas" "vertical.*windows.*installer.*\.exe$" "%PLUG_TMP%\aitum-vertical.exe"
if not errorlevel 1 (
  echo Instalando/verificando Aitum Vertical...
  start /wait "" "%PLUG_TMP%\aitum-vertical.exe" /S
) else (
  echo Aviso: Aitum Vertical nao foi baixado agora. Continuando.
)
exit /b 0

:INSTALL_AITUM_MULTISTREAM_WINDOWS
echo.
echo Verificando Aitum Multistream...
call :DETECT_AITUM_MULTISTREAM_WINDOWS
if not errorlevel 1 (
  echo OK: Aitum Multistream ja detectado. Nao vou reinstalar.
  exit /b 0
)
set "PLUG_TMP=%TEMP%\DEFINA_FZ_VPS_TOKEN"
if not exist "%PLUG_TMP%" mkdir "%PLUG_TMP%" >nul 2>nul
call :DOWNLOAD_GITHUB_ASSET_WINDOWS "Aitum/obs-aitum-multistream" "(multistream|multi).*windows.*installer.*\.exe$" "%PLUG_TMP%\aitum-multistream.exe"
if not errorlevel 1 (
  echo Instalando/verificando Aitum Multistream...
  start /wait "" "%PLUG_TMP%\aitum-multistream.exe" /S
) else (
  echo Aviso: Aitum Multistream nao foi baixado agora. Continuando.
)
exit /b 0
