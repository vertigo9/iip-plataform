
[CmdletBinding()]
param(
    [string]$RepoRoot = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
)

$ErrorActionPreference = "Stop"
$RunId = Get-Date -Format "yyyyMMdd-HHmmss"
$ReportPath = Join-Path $env:TEMP "TRACE_POL_25_15_WIRING_INTEGRATION_$RunId.txt"

if (-not (Test-Path -LiteralPath $RepoRoot -PathType Container)) {
    throw "Repository not found: $RepoRoot"
}

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$Extensions = @(".py", ".ps1", ".psm1", ".psd1", ".toml", ".yaml", ".yml", ".json")
$ExcludedDirs = @(
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    "node_modules", "dist", "build", ".mypy_cache", ".ruff_cache"
)

$Groups = [ordered]@{
    "A - Evidence contract and promotion" = @(
        "HistoricalMetricEvidence",
        "harvest_metrics_to_evidence",
        "promotion",
        "promote",
        "confidence",
        "source_lineage",
        "lineage"
    )
    "B - Portfolio and decision entry points" = @(
        "PortfolioRunner",
        "DecisionEngine",
        "portfolio_runner",
        "decision_engine",
        "refresh_portfolio"
    )
    "C - Bridges and orchestration" = @(
        "bridge",
        "adapter",
        "dispatch",
        "router",
        "orchestrat"
    )
    "D - Legacy ingestion and models" = @(
        "ingest_fii_harvest",
        "MetricObservationIdentity",
        "SemanticDimension",
        "FiiMetricAdapter",
        "FiiComplemento"
    )
    "E - Asset-specific harvesters" = @(
        "fetch_fiagro",
        "fiagro",
        "fixed_income",
        "FI-Infra",
        "CVM"
    )
    "F - Tests and test references" = @(
        "test_.*harvest",
        "test_.*evidence",
        "test_.*portfolio",
        "test_.*promotion",
        "HistoricalMetricEvidence",
        "harvest_metrics_to_evidence"
    )
}

function Add-Section {
    param([string]$Name)

    Add-Content -LiteralPath $ReportPath -Encoding UTF8 -Value ""
    Add-Content -LiteralPath $ReportPath -Encoding UTF8 -Value ("=" * 90)
    Add-Content -LiteralPath $ReportPath -Encoding UTF8 -Value $Name
    Add-Content -LiteralPath $ReportPath -Encoding UTF8 -Value ("=" * 90)
}

$Files = @(
    Get-ChildItem -LiteralPath $RepoRoot -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $Extensions -contains $_.Extension.ToLowerInvariant() -and
            -not ($_.FullName -split '[\\/]' | Where-Object {
                $ExcludedDirs -contains $_
            })
        }
)

@(
    "POL 25.15 - WIRING AND INTEGRATION AUDIT"
    "Run ID: $RunId"
    "Repository: $RepoRoot"
    "Mode: READ-ONLY"
    "Tests executed: NO"
    "Source files modified: NO"
    "Report: $ReportPath"
    "Eligible source/config files: $($Files.Count)"
) | Set-Content -LiteralPath $ReportPath -Encoding UTF8

Add-Section "1 - Git snapshot"

Push-Location $RepoRoot
try {
    $Branch = (& git branch --show-current 2>&1 | Out-String).Trim()
    $Head = (& git rev-parse HEAD 2>&1 | Out-String).Trim()
    $Status = (& git status --short 2>&1 | Out-String).TrimEnd()

    Add-Content $ReportPath -Encoding UTF8 -Value "Branch: $Branch"
    Add-Content $ReportPath -Encoding UTF8 -Value "HEAD: $Head"
    Add-Content $ReportPath -Encoding UTF8 -Value "Git status:"
    Add-Content $ReportPath -Encoding UTF8 -Value $Status
}
catch {
    Add-Content $ReportPath -Encoding UTF8 -Value "Git snapshot warning: $($_.Exception.Message)"
}
finally {
    Pop-Location
}

Add-Section "2 - Candidate source files"

$Files |
    ForEach-Object {
        $_.FullName.Substring($RepoRoot.Length).TrimStart('\', '/')
    } |
    Add-Content -LiteralPath $ReportPath -Encoding UTF8

foreach ($GroupName in $Groups.Keys) {
    Add-Section $GroupName

    $GroupPatterns = $Groups[$GroupName]
    $Matches = @(
        $Files |
            Select-String -Pattern $GroupPatterns -Context 2,2 -ErrorAction SilentlyContinue
    )

    if ($Matches.Count -eq 0) {
        Add-Content -LiteralPath $ReportPath -Encoding UTF8 -Value "NO MATCHES"
        continue
    }

    foreach ($Match in $Matches) {
        $RelativePath = $Match.Path.Substring($RepoRoot.Length).TrimStart('\', '/')

        Add-Content -LiteralPath $ReportPath -Encoding UTF8 -Value ""
        Add-Content -LiteralPath $ReportPath -Encoding UTF8 -Value (
            "FILE: {0}:{1}" -f $RelativePath, $Match.LineNumber
        )
        Add-Content -LiteralPath $ReportPath -Encoding UTF8 -Value (
            "MATCH: " + $Match.Line.Trim()
        )

        if ($Match.Context) {
            foreach ($Line in $Match.Context.PreContext) {
                Add-Content -LiteralPath $ReportPath -Encoding UTF8 -Value (
                    "PREVIOUS: " + $Line
                )
            }
            foreach ($Line in $Match.Context.PostContext) {
                Add-Content -LiteralPath $ReportPath -Encoding UTF8 -Value (
                    "NEXT: " + $Line
                )
            }
        }
    }
}

Add-Section "3 - Wiring candidate inventory"

$WiringTerms = @(
    "PortfolioRunner",
    "DecisionEngine",
    "harvest_metrics_to_evidence",
    "HistoricalMetricEvidence",
    "ingest_fii_harvest",
    "FiiMetricAdapter"
)

$WiringFiles = foreach ($File in $Files) {
    $Hit = Select-String -LiteralPath $File.FullName -Pattern $WiringTerms -List -ErrorAction SilentlyContinue
    if ($Hit) {
        $File.FullName.Substring($RepoRoot.Length).TrimStart('\', '/')
    }
}

if ($WiringFiles) {
    $WiringFiles | Sort-Object -Unique |
        Add-Content -LiteralPath $ReportPath -Encoding UTF8
}
else {
    Add-Content -LiteralPath $ReportPath -Encoding UTF8 -Value "No wiring candidate files found."
}

Add-Section "4 - Limitations"

@(
    "Static text search only; this is not runtime tracing."
    "A match does not prove that a function is active or reachable."
    "No tests or application entry points were executed."
    "No source files were intentionally modified."
    "Review call chains before concluding that integration is complete."
) | Add-Content -LiteralPath $ReportPath -Encoding UTF8

Write-Host ""
Write-Host "POL 25.15 completed - read-only static audit." -ForegroundColor Green
Write-Host "Report: $ReportPath" -ForegroundColor Cyan