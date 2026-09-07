$ErrorActionPreference = "Stop"

$Base = (Get-Location).Path
$target = Join-Path $Base "POST95_RELEASE_CHECKPOINT.json"

Write-Host "D-OBSIDIAN-06.7 RESTORE RELEASE CHECKPOINT"
Write-Host "Restoring only the compatibility artifact required by the certified regression."
Write-Host ""

if (Test-Path $target) {
    Write-Host "POST95_RELEASE_CHECKPOINT.json already exists. Nothing to restore."
    exit 0
}

$manifest = Get-ChildItem (Join-Path $Base "archive") -File -Filter "D-OBSIDIAN-06.7_CLEANUP_MOVE_MANIFEST_*.csv" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $manifest) {
    throw "Cleanup manifest not found under .\archive"
}

Write-Host ("Using manifest: " + $manifest.FullName)

$entry = Import-Csv $manifest.FullName |
    Where-Object { (Split-Path $_.Source -Leaf) -eq "POST95_RELEASE_CHECKPOINT.json" -or $_.Source -like "*\POST95_RELEASE_CHECKPOINT.json" } |
    Select-Object -First 1

if (-not $entry) {
    throw "POST95_RELEASE_CHECKPOINT.json was not found in cleanup manifest."
}

if (-not (Test-Path $entry.Destination)) {
    throw "Archived checkpoint not found: $($entry.Destination)"
}

Copy-Item -LiteralPath $entry.Destination -Destination $target -Force

Write-Host ""
Write-Host ("Restored: " + $target)
Write-Host ("From archive: " + $entry.Destination)
Write-Host "No other files were restored."
