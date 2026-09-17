
# POL_25_24_PRODUCTION_PATH_TRACE.ps1
# Read-only source trace. Compatible with Windows PowerShell 5.1.
# Does not import project modules, run tests, access the network, or modify source files.

[CmdletBinding()]
param(
    [string]$RepoRoot = (Get-Location).Path,
    [int]$ContextLines = 2,
    [int]$MaxHitsPerCategory = 35
)

$ErrorActionPreference = "Stop"

$SourceRoot = Join-Path $RepoRoot "src\iip"
$TraceDir = Join-Path $RepoRoot "audit_traces"

if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
    throw "Source directory not found: $SourceRoot"
}

New-Item -ItemType Directory -Path $TraceDir -Force | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TracePath = Join-Path $TraceDir "TRACE_POL_25_24_PRODUCTION_PATH_$Stamp.txt"

$ExcludedDirs = @(
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "build", "dist", "site-packages",
    "node_modules", ".venv", "venv", ".iip_backups"
)

$Files = Get-ChildItem -LiteralPath $SourceRoot -Recurse -File -Filter "*.py" |
    Where-Object {
        $Full = $_.FullName
        $Keep = $true
        foreach ($DirName in $ExcludedDirs) {
            if ($Full -match [regex]::Escape("\$DirName\")) {
                $Keep = $false
                break
            }
        }
        $Keep
    } |
    Sort-Object FullName

$Categories = [ordered]@{
    "1. CLI command definitions and dispatch" =
        '(refresh-portfolio|analyze-portfolio|refresh_portfolio|analyze_portfolio|run_portfolio_cycle)'

    "2. Portfolio cycle definition and callers" =
        '(def\s+run_portfolio_cycle|run_portfolio_cycle\s*\(|portfolio_cycle\s*\()'

    "3. Atlas discovery and document production" =
        '(discover\s*\(|fetch_many\s*\(|AtlasDocument|AtlasIngestionReport|\.documents\b)'

    "4. CVM report to metric conversion" =
        '(CvmFiiTarget|FetchedFiiReport|CVM.*(convert|metric)|convert.*Cvm|MetricObservation|metric_observation)'

    "5. Metric persistence entrypoints" =
        '(persist_if_eligible|persist_many|persist_metric|persist_observation|KnowledgeMetricEvidence|PersistenceCandidate)'

    "6. Evidence identity and source association" =
        '(metric_evidence_id|knowledge_evidence_id|MetricObservationIdentity|source_document|document_id|source_ref|source_id|AtlasKnowledgeAdapter)'

    "7. Orchestration and adapter wiring" =
        '(AtlasKnowledgeAdapter|FiiMetric|Metric.*Adapter|Knowledge.*Adapter|gateway|adapter\s*=|pipeline\s*=)'
}

$LinesOut = New-Object System.Collections.Generic.List[string]

function Add-Line {
    param([string]$Text)
    $script:LinesOut.Add($Text)
}

Add-Line "POL 25.24 PRODUCTION PATH TRACE"
Add-Line "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Add-Line "Repository: $RepoRoot"
Add-Line "Source root: $SourceRoot"
Add-Line "Python files scanned: $($Files.Count)"
Add-Line "Context lines: $ContextLines"
Add-Line "Max hits per category: $MaxHitsPerCategory"
Add-Line "Scope: src\iip only; tests excluded; read-only textual scan."
Add-Line "NOTE: Matches are not proof of runtime reachability."
Add-Line ""

foreach ($Category in $Categories.GetEnumerator()) {
    Add-Line ("=" * 90)
    Add-Line $Category.Key
    Add-Line ("=" * 90)

    $Regex = [regex]::new(
        $Category.Value,
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    $Hits = New-Object System.Collections.Generic.List[object]

    foreach ($File in $Files) {
        try {
            $Content = [System.IO.File]::ReadAllLines($File.FullName)
        }
        catch {
            Add-Line "READ ERROR: $($File.FullName) :: $($_.Exception.Message)"
            continue
        }

        for ($Index = 0; $Index -lt $Content.Length; $Index++) {
            if ($Regex.IsMatch($Content[$Index])) {
                $Hits.Add([pscustomobject]@{
                    File = $File.FullName
                    Lines = $Content
                    Index = $Index
                })
            }
        }
    }

    Add-Line "Matching source lines: $($Hits.Count)"

    $Shown = 0
    foreach ($Hit in $Hits) {
        if ($Shown -ge $MaxHitsPerCategory) {
            Add-Line "HIT LIMIT REACHED; additional matches omitted."
            break
        }

        $Relative = $Hit.File.Substring($RepoRoot.TrimEnd('\').Length).TrimStart('\')
        $LineNumber = $Hit.Index + 1
        Add-Line ""
        Add-Line ("FILE: {0} | LINE: {1}" -f $Relative, $LineNumber)

        $Start = [Math]::Max(0, $Hit.Index - $ContextLines)
        $End = [Math]::Min($Hit.Lines.Length - 1, $Hit.Index + $ContextLines)

        for ($J = $Start; $J -le $End; $J++) {
            $Prefix = if ($J -eq $Hit.Index) { ">>" } else { "  " }
            Add-Line ("{0} {1,5}: {2}" -f $Prefix, ($J + 1), $Hit.Lines[$J])
        }

        $Shown++
    }

    Add-Line ""
}

Add-Line ("=" * 90)
Add-Line "END OF TRACE"
Add-Line "This report is a static text scan, not an execution trace."
Add-Line "Confirm call relationships from definitions, imports, and callsites."
Add-Line ("=" * 90)

[System.IO.File]::WriteAllLines(
    $TracePath,
    $LinesOut,
    (New-Object System.Text.UTF8Encoding($true))
)

Write-Host ""
Write-Host "POL 25.24 trace completed."
Write-Host "Python files scanned: $($Files.Count)"
Write-Host "Trace: $TracePath"