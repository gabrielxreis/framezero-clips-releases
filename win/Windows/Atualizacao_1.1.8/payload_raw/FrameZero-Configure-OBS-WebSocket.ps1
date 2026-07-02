$ErrorActionPreference = 'SilentlyContinue'
$obsRoot = Join-Path $env:APPDATA 'obs-studio'
New-Item -ItemType Directory -Force -Path $obsRoot | Out-Null
$g = Join-Path $obsRoot 'global.ini'
if (!(Test-Path $g)) { New-Item -ItemType File -Force -Path $g | Out-Null }
$txt = Get-Content $g -Raw -ErrorAction SilentlyContinue
if ($txt -notmatch '\[OBSWebSocket\]') { $txt += "`r`n[OBSWebSocket]" }
$pairs = @('ServerEnabled=true','ServerPort=4455','AuthRequired=false','AlertsEnabled=false','FirstLoad=false')
foreach ($pair in $pairs) {
  $k = $pair.Split('=')[0]
  $pattern = '(?m)^' + [regex]::Escape($k) + '=.*'
  if ($txt -match $pattern) { $txt = [regex]::Replace($txt,$pattern,$pair) } else { $txt += "`r`n$pair" }
}
Set-Content -Encoding UTF8 $g $txt
Write-Host 'OK: OBS WebSocket configurado automaticamente.'
