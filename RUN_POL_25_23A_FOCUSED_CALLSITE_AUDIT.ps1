
[CmdletBinding()]
param(
    [string]$RepoRoot = (Get-Location).Path,
    [string]$OutputDir = ".\_audit_traces",
    [int]$ContextLines = 8
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot)
$OutputDir = [System.IO.Path]::GetFullPath(
    (Join-Path $RepoRoot $OutputDir)
)

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outFile = Join-Path $OutputDir "TRACE_POL_25_23A_FOCUSED_CALLSITES_$stamp.txt"

$excludedDirs = @(
    ".git", ".venv", "venv", "node_modules",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    "dist", "build", ".iip_backups", ".iip_patch_backups",
    "archives", "archive", "backups", "backup"
)

$extensions = @(".py", ".ps1", ".psm1")

$patterns = [ordered]@{
    "CLI refresh entrypoints" =
        'refresh-portfolio|refresh_portfolio|def\s+refresh\b'
    "Atlas discovery and fetch" =
        'discover\s*\(|fetch_many\s*\(|class\s+\w*Harvester\b'
    "Atlas document and report construction" =
        'AtlasDocument\s*\(|AtlasIngestionReport\s*\(|class\s+AtlasDocument\b'
    "Knowledge adapter calls" =
        'AtlasKnowledgeAdapter|\.ingest\s*\(|\.persist\s*\(|persist_if_eligible\s*\('
    "FII metric conversion and persistence" =
        'CVM|HistoricalMetricEvidence|MetricObservationIdentity|FII.*metric|metric.*FII'
    "Evidence identity and deduplication" =
        'evidence_id|evidence_key|stable_id|fingerprint|dedup|source_document'
    "Relevant orchestration functions" =
        'run_portfolio_cycle|run_asset|def\s+compose\b|def\s+run\b|def\s+main\b'
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$report = New-Object 'System.Collections.Generic.List[string]'
$report.Add("POL 25.23A - FOCUSED CALLSITE AUDIT")
$report.Add("Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
$report.Add("Repository: $RepoRoot")
$report.Add("Mode: READ-ONLY; no imports, tests, CLI, or network")
$report.Add("")

$roots = @(
    [pscustomobject]@{ Name = "src\iip"; Path = (Join-Path $RepoRoot "src\iip") },
    [pscustomobject]@{ Name = "tests";  Path = (Join-Path $RepoRoot "tests") }
)

$files = New-Object 'System.Collections.Generic.List[System.IO.FileInfo]'

foreach ($root in $roots) {
    $report.Add("ROOT: $($root.Name)")
    $report.Add("Path: $($root.Path)")

    if (-not (Test-Path -LiteralPath $root.Path -PathType Container)) {
        $report.Add("STATUS: MISSING")
        $report.Add("")
        continue
    }

    $rootFiles = @(
        Get-ChildItem -LiteralPath $root.Path -Recurse -File |
        Where-Object {
            $relative = $_.FullName.Substring($RepoRoot.Length).TrimStart([char[]]"\/")
            $parts = $relative -split '[\\/]'

            ($extensions -contains $_.Extension.ToLowerInvariant()) -and
            -not ($parts | Where-Object { $excludedDirs -contains $_ })
        }
    )

    $report.Add("STATUS: EXISTS")
    $report.Add("Eligible files: $($rootFiles.Count)")

    foreach ($f in $rootFiles) {
        $files.Add($f)
    }

    $report.Add("")
}

$files = @($files | Sort-Object FullName -Unique)
$report.Add("TOTAL UNIQUE FILES: $($files.Count)")
$report.Add("")

foreach ($entry in $patterns.GetEnumerator()) {
    $category = [string]$entry.Key
    $pattern = [string]$entry.Value
    $count = 0
    $readErrors = 0

    $report.Add(("=" * 80))
    $report.Add("CATEGORY: $category")
    $report.Add("REGEX: $pattern")
    $report.Add(("=" * 80))

    foreach ($file in $files) {
        try {
            $content = @(Get-Content -LiteralPath $file.FullName -ErrorAction Stop)
        }
        catch {
            $readErrors++
            $relative = $file.FullName.Substring($RepoRoot.Length).TrimStart([char[]]"\/")
            $report.Add("[READ_ERROR] $relative :: $($_.Exception.Message)")
            continue
        }

        for ($i = 0; $i -lt $content.Count; $i++) {
            if ($content[$i] -match $pattern) {
                $count++

                $start = [Math]::Max(0, $i - $ContextLines)
                $end = [Math]::Min($content.Count - 1, $i + $ContextLines)
                $relative = $file.FullName.Substring($RepoRoot.Length).TrimStart([char[]]"\/")

                $report.Add("")
                $report.Add("[MATCH] $relative : line $($i + 1)")

                for ($j = $start; $j -le $end; $j++) {
                    $prefix = if ($j -eq $i) { ">>" } else { "  " }
                    $report.Add(("{0} {1,6}: {2}" -f $prefix, ($j + 1), $content[$j]))
                }
            }
        }
    }

    $report.Add("")
    $report.Add("MATCH COUNT: $count")
    $report.Add("READ ERRORS: $readErrors")
    $report.Add("")
}

$report.Add("NOTE: textual matches only; reachability/runtime behavior unverified.")

[System.IO.File]::WriteAllLines(
    $outFile,
    $report,
    (New-Object System.Text.UTF8Encoding($true))
)

Write-Host ""
Write-Host "Auditoria concluída." -ForegroundColor Green
Write-Host "Arquivos examinados: $($files.Count)"
Write-Host "Linhas do relatório: $($report.Count)"
Write-Host "Relatório: $outFile"
Write-Host "Código-fonte do projeto não foi alterado."