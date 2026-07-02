param(
  [string]$Stable
)
$ErrorActionPreference = 'Stop'
function Write-FZ([string]$m){ Write-Host $m }
function First-Value($items){ foreach($x in $items){ if($null -ne $x -and -not [string]::IsNullOrWhiteSpace([string]$x)){ return [string]$x } }; return '' }
function Get-VersionParts([string]$v){
  $nums = [regex]::Matches(($v -replace '^v',''), '\d+') | ForEach-Object { [int]$_.Value }
  while($nums.Count -lt 4){ $nums += 0 }
  return $nums[0..3]
}
function Test-VersionGreater([string]$a,[string]$b){
  $aa = Get-VersionParts $a; $bb = Get-VersionParts $b
  for($i=0;$i -lt 4;$i++){ if($aa[$i] -gt $bb[$i]){ return $true }; if($aa[$i] -lt $bb[$i]){ return $false } }
  return $false
}
function Read-JsonFile($path){
  if(Test-Path $path){ try { return Get-Content -Raw -Encoding UTF8 $path | ConvertFrom-Json } catch {} }
  return $null
}
function Copy-TreeSafe([string]$src,[string]$dst){
  if(!(Test-Path $dst)){ New-Item -ItemType Directory -Force -Path $dst | Out-Null }
  $args = @($src, $dst, '/E', '/NFL','/NDL','/NJH','/NJS','/NC','/NS','/NP', '/XD', 'venv', '__pycache__', '.pytest_cache', 'logs', '/XF', '.DS_Store')
  $p = Start-Process -FilePath robocopy.exe -ArgumentList $args -PassThru -Wait -NoNewWindow
  if($p.ExitCode -ge 8){ throw "robocopy falhou com codigo $($p.ExitCode)" }
}
try {
  if([string]::IsNullOrWhiteSpace($Stable)){ $Stable = Join-Path $env:APPDATA 'obs-studio\FrameZero' }
  $App = Join-Path $Stable 'app'
  $VersionUrl = 'https://raw.githubusercontent.com/gabrielxreis/framezero-clips-releases/main/latest/version.json'
  $LocalFile = Join-Path $Stable 'framezero_local_version.json'
  $tmp = Join-Path $env:TEMP ('framezero-update-' + [guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force -Path $tmp | Out-Null
  Write-FZ '============================================================'
  Write-FZ ' VERIFICANDO ATUALIZAÇÃO DO FRAMEZERO NO GITHUB'
  Write-FZ '============================================================'
  $remotePath = Join-Path $tmp 'version.json'
  Invoke-WebRequest -UseBasicParsing -Uri ($VersionUrl + '?ts=' + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) -TimeoutSec 20 -OutFile $remotePath
  $remote = Read-JsonFile $remotePath
  if($null -eq $remote){ throw 'version.json remoto invalido' }
  $local = Read-JsonFile $LocalFile
  $localVer = '0.0.0'
  if($local){ $localVer = First-Value @($local.installer_version,$local.online_installer_version,$local.installer_ui_version,$local.version) }
  $remoteVer = First-Value @($remote.installer_version,$remote.online_installer_version,$remote.installer_ui_version)
  $winUrl = First-Value @($remote.windows_url,$remote.windows_package_url)
  if([string]::IsNullOrWhiteSpace($remoteVer)){ throw 'version.json sem installer_version' }
  if([string]::IsNullOrWhiteSpace($winUrl)){ throw 'version.json sem windows_url' }
  Write-FZ ('Versão local do Core/instalador: ' + $localVer)
  Write-FZ ('Versão disponível no GitHub: ' + $remoteVer)
  $required = @(
    (Join-Path $Stable 'INICIAR-FRAMEZERO-CMD.bat'),
    (Join-Path $Stable 'FrameZero-Update-Check.ps1'),
    (Join-Path $Stable 'FrameZero-Windows-Preflight.bat'),
    (Join-Path $Stable 'FrameZero-Configure-OBS-WebSocket.ps1'),
    (Join-Path $Stable 'FrameZero-Start-OBS.ps1'),
    (Join-Path $App 'servidor.py'),
    (Join-Path $App 'requirements.txt'),
    (Join-Path $App 'venv\Scripts\python.exe')
  )
  $missing = @($required | Where-Object { !(Test-Path $_) })
  $forceRepair = $false
  if($missing.Count -gt 0){
    $forceRepair = $true
    Write-FZ ('Arquivos obrigatórios ausentes. Reparando antes de abrir o Core: ' + ($missing -join '; '))
  }
  if((!(Test-VersionGreater $remoteVer $localVer)) -and -not $forceRepair){
    Write-FZ 'FrameZero já está atualizado e os arquivos principais existem.'
    exit 0
  }
  if($forceRepair){
    Write-FZ 'Baixando pacote Windows para reparar arquivos antes de abrir o Core...'
  } else {
    Write-FZ 'Atualização encontrada. Baixando pacote Windows antes de abrir o Core...'
  }
  $zip = Join-Path $tmp 'FrameZero_Clips_Windows.zip'
  Invoke-WebRequest -UseBasicParsing -Uri ($winUrl + '?ts=' + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) -TimeoutSec 120 -OutFile $zip
  if(!(Test-Path $zip) -or ((Get-Item $zip).Length -lt 10000)){ throw 'pacote Windows vazio/invalido' }
  $extract = Join-Path $tmp 'extract'
  Expand-Archive -Force -Path $zip -DestinationPath $extract
  $payload = Get-ChildItem -Path $extract -Directory -Recurse -Filter 'payload_raw' | Select-Object -First 1
  if($null -eq $payload){
    $payload = Get-ChildItem -Path $extract -Directory -Recurse | Where-Object { Test-Path (Join-Path $_.FullName 'app\servidor.py') } | Select-Object -First 1
  }
  if($null -eq $payload){ throw 'payload do FrameZero não encontrado no pacote baixado' }
  Write-FZ ('Aplicando atualização em: ' + $Stable)
  $cfgBak = $null
  $cfg = Join-Path $App 'config.json'
  if(Test-Path $cfg){ $cfgBak = Join-Path $tmp 'config.json'; Copy-Item -Force $cfg $cfgBak }
  Copy-TreeSafe $payload.FullName $Stable
  if($cfgBak -and (Test-Path $cfgBak)){ New-Item -ItemType Directory -Force -Path $App | Out-Null; Copy-Item -Force $cfgBak $cfg }
  $localOut = [ordered]@{
    app='FrameZero Clips';
    version=(First-Value @($remote.latest_version,$remote.version,'1.1.8'));
    clips_version=(First-Value @($remote.clips_version,$remote.latest_version,'1.1.8'));
    installer_version=$remoteVer;
    online_installer_version=$remoteVer;
    installer_ui_version=$remoteVer;
    updated_from_github=$true;
    updated_at=(Get-Date).ToUniversalTime().ToString('o')
  }
  $localOut | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -Path $LocalFile
  Write-FZ ('Atualização aplicada para v' + $remoteVer + '. Reiniciando launcher atualizado...')
  exit 10
} catch {
  Write-Host ('[ERRO UPDATE] ' + $_.Exception.Message) -ForegroundColor Yellow
  exit 2
} finally {
  if($tmp -and (Test-Path $tmp)){ Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }
}
