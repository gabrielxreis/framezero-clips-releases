$ErrorActionPreference = 'SilentlyContinue'
$stable = $env:FRAMEZERO_STABLE
if ([string]::IsNullOrWhiteSpace($stable)) { $stable = Join-Path $env:APPDATA 'obs-studio\FrameZero' }
$pathFile = Join-Path $stable '.framezero\obs_path.txt'
$paths = New-Object System.Collections.Generic.List[string]
if (Test-Path $pathFile) {
  $p = (Get-Content $pathFile -Raw).Trim()
  if ($p) { $paths.Add($p) }
}
$regKeys = @(
  'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\obs64.exe',
  'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\obs64.exe',
  'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\obs64.exe'
)
foreach ($k in $regKeys) {
  try { $v=(Get-ItemProperty $k).'(default)'; if ($v) { $paths.Add($v) } } catch {}
}
$uninstallKeys = @(
  'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\OBS Studio',
  'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\OBS Studio',
  'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\OBS Studio'
)
foreach ($k in $uninstallKeys) {
  try { $loc=(Get-ItemProperty $k).InstallLocation; if($loc){ $paths.Add((Join-Path $loc 'bin\64bit\obs64.exe')) } } catch {}
}
if ($env:ProgramFiles) { $paths.Add((Join-Path $env:ProgramFiles 'obs-studio\bin\64bit\obs64.exe')) }
$pf86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
if ($pf86) { $paths.Add((Join-Path $pf86 'obs-studio\bin\64bit\obs64.exe')) }
if ($env:LOCALAPPDATA) {
  $paths.Add((Join-Path $env:LOCALAPPDATA 'Programs\obs-studio\bin\64bit\obs64.exe'))
  $paths.Add((Join-Path $env:LOCALAPPDATA 'obs-studio\bin\64bit\obs64.exe'))
}
$obs = $paths | Where-Object { $_ -and (Test-Path $_) -and ((Split-Path $_ -Leaf) -ieq 'obs64.exe') } | Select-Object -First 1
if ($obs) {
  $obs=(Resolve-Path $obs).Path
  $dir=Split-Path $obs -Parent
  New-Item -ItemType Directory -Force -Path (Split-Path $pathFile -Parent) | Out-Null
  Set-Content -Encoding UTF8 $pathFile $obs
  Write-Host ('OBS encontrado: '+$obs)
  Start-Process -FilePath $obs -WorkingDirectory $dir
  exit 0
}
Write-Host 'OBS Studio nao encontrado automaticamente. Rode o instalador novamente.'
exit 1
