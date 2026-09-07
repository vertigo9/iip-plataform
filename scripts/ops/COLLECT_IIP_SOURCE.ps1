
$ErrorActionPreference = "Stop"

$project = Get-Location
$outDir = Join-Path $project "IIP_source_snapshot_tmp"
$outZip = Join-Path $project "IIP_source_snapshot.zip"

if (Test-Path $outDir) { Remove-Item $outDir -Recurse -Force }
if (Test-Path $outZip) { Remove-Item $outZip -Force }

New-Item -ItemType Directory -Path $outDir | Out-Null
New-Item -ItemType Directory -Path (Join-Path $outDir "src") | Out-Null

# Copy source tree while excluding secrets, caches and VCS data.
robocopy (Join-Path $project "src") (Join-Path $outDir "src") /E `
  /XD __pycache__ .pytest_cache .mypy_cache .ruff_cache `
  /XF *.pyc *.pyo .env .env.* `
  | Out-Null

foreach ($name in @("pyproject.toml","pytest.ini","setup.cfg","tox.ini")) {
    $src = Join-Path $project $name
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $outDir $name)
    }
}

# Safety check: never package common credential/config secret files.
Get-ChildItem $outDir -Recurse -Force -File |
    Where-Object { $_.Name -match '(^\.env|secret|credential|token|password|key)' } |
    Remove-Item -Force

Compress-Archive -Path (Join-Path $outDir "*") -DestinationPath $outZip -Force
Remove-Item $outDir -Recurse -Force

Write-Host ""
Write-Host "Snapshot criado:"
Write-Host $outZip
