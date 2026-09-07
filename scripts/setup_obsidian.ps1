param(
  [Parameter(Mandatory=$true)]
  [string]$VaultPath
)

$ErrorActionPreference = 'Stop'
$resolved = [System.IO.Path]::GetFullPath($VaultPath)
New-Item -ItemType Directory -Force -Path $resolved | Out-Null

$folders = @(
  '00_System','01_Assets/Equities','01_Assets/FIIs','01_Assets/FIInfra','01_Assets/FIAgro',
  '02_Portfolio/Snapshots','03_Decisions','04_Evidence','05_Events','06_Exposures','07_Research','08_Dashboards'
)
foreach ($f in $folders) { New-Item -ItemType Directory -Force -Path (Join-Path $resolved $f) | Out-Null }

$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) '.env'
"IIP_OBSIDIAN_VAULT=$resolved" | Add-Content -Path $envFile -Encoding utf8

Write-Host "IIP Obsidian vault configured:" -ForegroundColor Green
Write-Host $resolved
Write-Host "Open this exact folder in Obsidian: $resolved"
