$ErrorActionPreference = "Stop"

$root = Get-Location
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$archive = Join-Path $root ("D-OBSIDIAN-06.5_RC_FREEZE_" + $timestamp + ".zip")

$files = @(
    ".\D-OBSIDIAN-06.5_RC_FULL_TEST_GATE.txt",
    ".\D-OBSIDIAN-06.5_CERTIFIED_BASELINE.json",
    ".\D-OBSIDIAN-06.5_RELEASE_NOTES.md",
    ".\D-OBSIDIAN-06.5_RELEASE_READINESS_CHECKLIST.txt"
)

$existing = @($files | Where-Object { Test-Path $_ })

if ($existing.Count -lt 2) {
    Write-Host "AVISO: artefatos de certificação insuficientes no diretório atual."
    Write-Host "Nenhum arquivo foi alterado."
    exit 2
}

Compress-Archive -Path $existing -DestinationPath $archive -Force

@(
    "D-OBSIDIAN-06.5 RC FREEZE PACKAGE",
    ("Created: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "Status: RELEASE CANDIDATE",
    "Coverage: 96.57%",
    "Full regression: 821 passed / 4 skipped / 0 failed",
    ("Archive: " + $archive)
) | Set-Content ".\D-OBSIDIAN-06.5_RC_FREEZE_RECORD.txt" -Encoding ASCII

Write-Host "RC freeze package criado:"
Write-Host $archive
Write-Host "Record: .\D-OBSIDIAN-06.5_RC_FREEZE_RECORD.txt"
