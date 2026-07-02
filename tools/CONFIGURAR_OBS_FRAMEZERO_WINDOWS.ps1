$ErrorActionPreference = "SilentlyContinue"
Write-Host "============================================================"
Write-Host " FRAMEZERO - CONFIGURAR OBS COM CENA PADRAO"
Write-Host "============================================================"

$Root = Split-Path -Parent $PSScriptRoot
$SceneSource = Join-Path $Root "obs\framezero clips.json"
if (!(Test-Path $SceneSource)) {
  $SceneSource = Join-Path $Root "obs\framezero_clips.json"
}
if (!(Test-Path $SceneSource)) {
  Write-Host "ERRO: arquivo obs\framezero clips.json nao encontrado."
  exit 1
}

$ObsRoot = Join-Path $env:APPDATA "obs-studio"
$ScenesDir = Join-Path $ObsRoot "basic\scenes"
$ProfilesDir = Join-Path $ObsRoot "basic\profiles\FrameZero Clips"
$GlobalIni = Join-Path $ObsRoot "global.ini"
$BasicIni = Join-Path $ProfilesDir "basic.ini"

New-Item -ItemType Directory -Force -Path $ScenesDir | Out-Null
New-Item -ItemType Directory -Force -Path $ProfilesDir | Out-Null
Copy-Item -Force $SceneSource (Join-Path $ScenesDir "framezero clips.json")

$basic = @"
[General]
Name=FrameZero Clips

[Video]
BaseCX=1920
BaseCY=1080
OutputCX=1920
OutputCY=1080
FPSType=0
FPSCommon=30

[Output]
Mode=Simple

[SimpleOutput]
RecFormat2=mp4
VBitrate=6000
ABitrate=160
UseAdvanced=false
"@
Set-Content -Encoding UTF8 -Path $BasicIni -Value $basic

if (!(Test-Path $GlobalIni)) { New-Item -ItemType File -Force -Path $GlobalIni | Out-Null }
$txt = Get-Content $GlobalIni -Raw -ErrorAction SilentlyContinue
if ([string]::IsNullOrWhiteSpace($txt)) { $txt = "[Basic]`r`n" }
if ($txt -notmatch "(?m)^\[Basic\]") { $txt += "`r`n[Basic]`r`n" }
$pairs = [ordered]@{
  Profile = "FrameZero Clips"
  ProfileDir = "FrameZero Clips"
  SceneCollection = "framezero clips"
  SceneCollectionFile = "framezero clips"
}
foreach ($k in $pairs.Keys) {
  $line = "$k=$($pairs[$k])"
  if ($txt -match ("(?m)^" + [regex]::Escape($k) + "=")) {
    $txt = [regex]::Replace($txt, ("(?m)^" + [regex]::Escape($k) + ".*"), $line)
  } else {
    $txt += "`r`n$line"
  }
}
Set-Content -Encoding UTF8 -Path $GlobalIni -Value $txt
Write-Host "OK: cena 'framezero clips' copiada e perfil 'FrameZero Clips' configurado."
Write-Host "Abra/reinicie o OBS para carregar o perfil."
