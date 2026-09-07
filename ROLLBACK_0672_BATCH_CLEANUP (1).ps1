$ErrorActionPreference = "Stop"

$Archive = ".\archive"
$manifests = Get-ChildItem $Archive -File -Filter "D-OBSIDIAN-06.7_CLEANUP_MOVE_MANIFEST_*.csv" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending

if (-not $manifests) {
    throw "Nenhum manifest de cleanup encontrado em .\archive"
}

$manifest = $manifests | Select-Object -First 1
Write-Host "Rollback usando: $($manifest.FullName)"

Import-Csv $manifest.FullName | ForEach-Object {
    if ($_.Class -eq "generated") { return }
    if (-not (Test-Path $_.Destination -PathType Leaf)) { return }

    $targetDir = Split-Path $_.Source -Parent
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

    if (Test-Path $_.Source) {
        Write-Warning "Destino original já existe; mantendo: $($_.Source)"
        return
    }

    Move-Item -LiteralPath $_.Destination -Destination $_.Source
}

Write-Host "Rollback concluido."
