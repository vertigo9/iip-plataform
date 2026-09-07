$ErrorActionPreference = "Stop"

$Base = (Get-Location).Path
$Archive = Join-Path $Base "archive"
$ScriptsOps = Join-Path $Base "scripts\ops"
$ScriptsRelease = Join-Path $Base "scripts\release"
$ScriptsDiag = Join-Path $Base "scripts\diagnostics"
$Logs = Join-Path $Base ".logs"
$BackupRoot = Join-Path $Archive "backups"
$LegacyRoot = Join-Path $Archive "legacy"
$Reports = Join-Path $Archive "reports"

foreach ($d in @($ScriptsOps,$ScriptsRelease,$ScriptsDiag,$Logs,$BackupRoot,$LegacyRoot,$Reports)) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Manifest = Join-Path $Archive ("D-OBSIDIAN-06.7_CLEANUP_MOVE_MANIFEST_" + $stamp + ".csv")

$rows = New-Object System.Collections.Generic.List[object]

function Move-Safe {
    param(
        [string]$Source,
        [string]$DestinationDir,
        [string]$Class
    )

    if (-not (Test-Path $Source -PathType Leaf)) { return }

    $name = Split-Path $Source -Leaf
    $dest = Join-Path $DestinationDir $name

    if (Test-Path $dest) {
        $baseName = [IO.Path]::GetFileNameWithoutExtension($name)
        $ext = [IO.Path]::GetExtension($name)
        $dest = Join-Path $DestinationDir ($baseName + "_migrated_" + $stamp + $ext)
    }

    Move-Item -LiteralPath $Source -Destination $dest
    $rows.Add([pscustomobject]@{
        Source = $Source
        Destination = $dest
        Class = $Class
    }) | Out-Null
}

Write-Host "D-OBSIDIAN-06.7 BATCH CLEANUP APPLY"
Write-Host "Baseline protected: 96.64%"
Write-Host "This migration is reversible through the generated CSV manifest."
Write-Host ""

# 1) Operational scripts
Get-ChildItem $Base -File -Force |
    Where-Object { $_.Name -match '^(APPLY_.*\.(ps1|py)|RUN_.*\.ps1)$' } |
    Where-Object { $_.Name -notmatch '^RUN_0671_BATCH_CLEANUP_INVENTORY\.ps1$' } |
    ForEach-Object {
        if ($_.Name -match '^RUN_0670_') {
            Move-Safe $_.FullName $ScriptsDiag "diagnostics"
        } elseif ($_.Name -match '^RUN_06(3|4|5|6|7|3[0-9])') {
            Move-Safe $_.FullName $ScriptsRelease "release"
        } else {
            Move-Safe $_.FullName $ScriptsOps "ops"
        }
    }

# 2) Explicit operational tools
foreach ($name in @(
    "COLLECT_IIP_SOURCE.ps1",
    "PATCH_CSV_TEST.ps1",
    "PATCH_REGISTRY_TEST.py",
    "setup_iip.py",
    "diagnostico_mziq.py",
    "diagnostico_mziq_requests_v13.py",
    "auditoria_patria.py"
)) {
    $p = Join-Path $Base $name
    if (Test-Path $p) { Move-Safe $p $ScriptsOps "ops-tools" }
}

# 3) Root backups
Get-ChildItem $Base -File -Force |
    Where-Object { $_.Name -match '(\.bak\d*|\.bak-|_old$)' } |
    ForEach-Object { Move-Safe $_.FullName $BackupRoot "root-backup" }

# 4) Source-tree backup files -> archive, preserving relative path in the manifest
Get-ChildItem (Join-Path $Base "src") -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '(\.bak\d*|\.bak-|backup|_old$)' } |
    ForEach-Object {
        # Keep package source intact; only move files that are clearly backups.
        $rel = $_.FullName.Substring((Join-Path $Base "src").Length).TrimStart("\")
        $destDir = Join-Path $BackupRoot (Split-Path $rel -Parent)
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        Move-Safe $_.FullName $destDir "source-backup"
    }

# 5) Patch artifacts at root -> archive/legacy
Get-ChildItem $Base -File -Force |
    Where-Object { $_.Name -match '^(apply_patria_patch.*|patria_corrigido_v.*|patria_harvester_patch.*)$' } |
    ForEach-Object { Move-Safe $_.FullName $LegacyRoot "patch-artifact" }

# 6) Historical operational logs/reports -> .logs
$logPatterns = @(
    'audit_v21\.txt$',
    '^cobertura.*\.(log|txt)$',
    '^compileall\.log$',
    '^coverage_resultado\.log$',
    '^diagnostico\.txt$',
    '^error\.txt$',
    '^health\.txt$',
    '^health_test\.txt$',
    '^git-(log|status|tag)-v.*\.txt$',
    '^modulos_0pct\.log$',
    '^resultado.*\.log$',
    '^resultado_leitura\.txt$',
    '^resumo_testes\.txt$',
    '^teste_detalhado.*\.(log|txt)$',
    '^test-v2\.1-output\.txt$',
    '^sync_.*\.txt$',
    '^state-v2\.1\.txt$',
    '^setup_iip_leitura\.txt$',
    '^xp_asset_mz_sites\.txt$'
)
foreach ($pattern in $logPatterns) {
    Get-ChildItem $Base -File -Force |
        Where-Object { $_.Name -match $pattern } |
        ForEach-Object { Move-Safe $_.FullName $Logs "log" }
}

# 7) Release/gate artifacts -> archive/reports
Get-ChildItem $Base -File -Force |
    Where-Object { $_.Name -match '^D-OBSIDIAN-.*\.(txt|json|zip|md)$' } |
    ForEach-Object { Move-Safe $_.FullName $Reports "release-artifact" }

foreach ($name in @(
    "IIP_source_snapshot.zip",
    "patria_harvester_patch.zip",
    "patria_harvester_patch_v3.zip",
    "POST95_RELEASE_CHECKPOINT.json"
)) {
    $p = Join-Path $Base $name
    if (Test-Path $p) { Move-Safe $p $Reports "artifact" }
}

# 8) Clearly generated caches
foreach ($p in @(
    (Join-Path $Base ".coverage"),
    (Join-Path $Base ".pytest_cache")
)) {
    if (Test-Path $p) {
        $rows.Add([pscustomobject]@{
            Source = $p
            Destination = "<deleted-generated>"
            Class = "generated"
        }) | Out-Null
        Remove-Item -LiteralPath $p -Recurse -Force
    }
}

$rows | Export-Csv -Path $Manifest -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host ("Moved/deleted items: " + $rows.Count)
Write-Host ("Manifest: " + $Manifest)
Write-Host ""
Write-Host "IMPORTANT: knowledge_bridge and data were NOT modified."
Write-Host "Run the final regression before deleting archive material."
