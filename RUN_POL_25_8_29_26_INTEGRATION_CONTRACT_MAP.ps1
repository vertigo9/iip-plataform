
# POL-25.8.29.26 — INTEGRATION & CONTRACT MAP
# READ-ONLY: não altera fontes, Git ou arquivos do projeto.
# A única gravação é o relatório em reports/.

$ErrorActionPreference = "Stop"

$Repo = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ReportDir = Join-Path $Repo "reports"
$Report = Join-Path $ReportDir "POL_25_8_29_26_INTEGRATION_CONTRACT_MAP_$Stamp.txt"

if (-not (Test-Path -LiteralPath $Repo -PathType Container)) {
    throw "Repositório não encontrado: $Repo"
}

New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null

function Add-Section {
    param([string]$Title)
    Add-Content -LiteralPath $Report -Encoding UTF8 -Value ""
    Add-Content -LiteralPath $Report -Encoding UTF8 -Value ("=" * 100)
    Add-Content -LiteralPath $Report -Encoding UTF8 -Value $Title
    Add-Content -LiteralPath $Report -Encoding UTF8 -Value ("=" * 100)
}

function Add-Text {
    param([string]$Text)
    Add-Content -LiteralPath $Report -Encoding UTF8 -Value $Text
}

function Invoke-GitReadOnly {
    param([string[]]$GitArgs)
    $output = & git -C $Repo @GitArgs 2>&1
    Add-Text ("COMMAND: git " + ($GitArgs -join " "))
    Add-Text (($output | Out-String).TrimEnd())
    Add-Text "EXIT_CODE: $LASTEXITCODE"
}

Set-Content -LiteralPath $Report -Encoding UTF8 -Value @(
    "IIP — POL-25.8.29.26"
    "INTEGRATION & CONTRACT MAP"
    "Generated: $(Get-Date -Format o)"
    "Repository: $Repo"
    "Mode: READ-ONLY; output restricted to reports/"
)

Push-Location $Repo
try {
    Add-Section "1. REPOSITORY IDENTITY AND GIT BASELINE"
    Invoke-GitReadOnly @("rev-parse", "--show-toplevel")
    Invoke-GitReadOnly @("branch", "--show-current")
    Invoke-GitReadOnly @("rev-parse", "HEAD")
    Invoke-GitReadOnly @("status", "--short", "--branch")

    Add-Section "2. TARGETED SOURCE FILE INVENTORY"
    $TargetDirs = @(
        "src\iip\integration",
        "src\iip\decision",
        "src\iip\knowledge",
        "src\iip\operational",
        "src\iip\orchestration",
        "src\iip\intelligence",
        "src\iip\platform",
        "tests"
    )

    foreach ($RelativeDir in $TargetDirs) {
        $FullDir = Join-Path $Repo $RelativeDir
        Add-Text ""
        Add-Text "DIRECTORY: $RelativeDir"

        if (Test-Path -LiteralPath $FullDir -PathType Container) {
            Get-ChildItem -LiteralPath $FullDir -Recurse -File |
                Where-Object {
                    $_.Extension -in @(".py", ".toml", ".yaml", ".yml", ".json")
                } |
                ForEach-Object {
                    $Rel = [IO.Path]::GetRelativePath($Repo, $_.FullName)
                    Add-Text ("  " + $Rel)
                }
        }
        else {
            Add-Text "  MISSING"
        }
    }

    Add-Section "3. INTEGRATION / CONTRACT SYMBOL SEARCH"
    $Patterns = @(
        "PortfolioAssetInput",
        "IntegratedPortfolioDecision",
        "portfolio_composition",
        "decision_to_asset_signal",
        "DecisionEngine",
        "class\s+Decision\b",
        "class\s+Evidence\b",
        "HistoricalMetricEvidence",
        "MetricObservationIdentity",
        "ObsidianRepository",
        "KnowledgeBridge",
        "run_portfolio_cycle",
        "run_asset",
        "def\s+compose\b",
        "def\s+run\b"
    )

    $SearchRoots = @(
        (Join-Path $Repo "src\iip"),
        (Join-Path $Repo "tests")
    ) | Where-Object { Test-Path -LiteralPath $_ }

    $SourceFiles = Get-ChildItem -LiteralPath $SearchRoots -Recurse -File `
        -Filter "*.py" -ErrorAction SilentlyContinue

    foreach ($Pattern in $Patterns) {
        Add-Text ""
        Add-Text "PATTERN: $Pattern"

        $Matches = Select-String -Path $SourceFiles.FullName `
            -Pattern $Pattern -ErrorAction SilentlyContinue

        if ($Matches) {
            foreach ($Match in $Matches) {
                $Rel = [IO.Path]::GetRelativePath($Repo, $Match.Path)
                Add-Text ("{0}:{1}: {2}" -f $Rel, $Match.LineNumber, $Match.Line.Trim())
            }
        }
        else {
            Add-Text "  NO MATCH"
        }
    }

    Add-Section "4. IMPORT / CALL-SITE SEARCH FOR KEY ADAPTERS"
    $AdapterPatterns = @(
        "iip\.integration\.decision_adapter",
        "decision_adapter",
        "iip\.integration\.portfolio_composition",
        "portfolio_composition",
        "harvest_metric_adapter",
        "fii_metric_adapter",
        "thesis_semantic_adapter",
        "PortfolioAssetInput",
        "decision_to_asset_signal"
    )

    foreach ($Pattern in $AdapterPatterns) {
        Add-Text ""
        Add-Text "PATTERN: $Pattern"

        $Matches = Select-String -Path $SourceFiles.FullName `
            -Pattern $Pattern -ErrorAction SilentlyContinue

        if ($Matches) {
            foreach ($Match in $Matches) {
                $Rel = [IO.Path]::GetRelativePath($Repo, $Match.Path)
                Add-Text ("{0}:{1}: {2}" -f $Rel, $Match.LineNumber, $Match.Line.Trim())
            }
        }
        else {
            Add-Text "  NO MATCH"
        }
    }

    Add-Section "5. CONTRACT DECLARATIONS"
    $ContractPatterns = @(
        "^\s*class\s+",
        "^\s*def\s+",
        "^\s*    def\s+",
        "^\s*@dataclass",
        "^\s*class\s+\w+\(Protocol\)"
    )

    $ContractRoots = @(
        "src\iip\integration",
        "src\iip\decision",
        "src\iip\knowledge",
        "src\iip\platform",
        "src\iip\intelligence",
        "src\iip\operational"
    )

    foreach ($RelativeDir in $ContractRoots) {
        $FullDir = Join-Path $Repo $RelativeDir
        Add-Text ""
        Add-Text "ROOT: $RelativeDir"

        if (-not (Test-Path -LiteralPath $FullDir -PathType Container)) {
            Add-Text "  MISSING"
            continue
        }

        $Files = Get-ChildItem -LiteralPath $FullDir -Recurse -File -Filter "*.py"
        $Matches = Select-String -Path $Files.FullName `
            -Pattern $ContractPatterns -ErrorAction SilentlyContinue

        foreach ($Match in $Matches) {
            $Rel = [IO.Path]::GetRelativePath($Repo, $Match.Path)
            Add-Text ("{0}:{1}: {2}" -f $Rel, $Match.LineNumber, $Match.Line.Trim())
        }
    }

    Add-Section "6. DUPLICATE / LEGACY / BACKUP CANDIDATES"
    $CandidateFiles = Get-ChildItem -LiteralPath $Repo -Recurse -File `
        -ErrorAction SilentlyContinue |
        Where-Object {
            $_.FullName -notmatch '[\\/](\.git|\.venv|venv|__pycache__)[\\/]' -and
            $_.Name -match '(?i)(PATCH|FINAL|CURRENT|backup|\.bak|legacy)'
        }

    foreach ($File in $CandidateFiles) {
        $Rel = [IO.Path]::GetRelativePath($Repo, $File.FullName)
        Add-Text $Rel
    }

    Add-Section "7. PYTHON TEST DISCOVERY — NO TEST EXECUTION"
    $PyProject = Join-Path $Repo "pyproject.toml"
    $PytestIni = Join-Path $Repo "pytest.ini"
    $SetupCfg = Join-Path $Repo "setup.cfg"

    foreach ($Config in @($PyProject, $PytestIni, $SetupCfg)) {
        if (Test-Path -LiteralPath $Config -PathType Leaf) {
            Add-Text "CONFIG: $([IO.Path]::GetRelativePath($Repo, $Config))"
            Select-String -LiteralPath $Config `
                -Pattern "pytest|testpaths|python_files|addopts" `
                -ErrorAction SilentlyContinue |
                ForEach-Object {
                    Add-Text ("  {0}: {1}" -f $_.LineNumber, $_.Line.Trim())
                }
        }
    }

    Add-Text ""
    Add-Text "TEST FILES:"
    Get-ChildItem -LiteralPath (Join-Path $Repo "tests") -Recurse -File `
        -Filter "test_*.py" -ErrorAction SilentlyContinue |
        ForEach-Object {
            Add-Text ([IO.Path]::GetRelativePath($Repo, $_.FullName))
        }

    Add-Section "8. SOURCE FILE HASHES — TARGETED"
    foreach ($RelativeDir in $TargetDirs | Where-Object { $_ -like "src\*" }) {
        $FullDir = Join-Path $Repo $RelativeDir
        if (Test-Path -LiteralPath $FullDir -PathType Container) {
            Get-ChildItem -LiteralPath $FullDir -Recurse -File -Filter "*.py" |
                ForEach-Object {
                    $Rel = [IO.Path]::GetRelativePath($Repo, $_.FullName)
                    $Hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
                    Add-Text "$Hash  $Rel"
                }
        }
    }

    Add-Section "9. END OF REPORT"
    Add-Text "Read-only diagnostic completed."
    Add-Text "No source files were intentionally modified."
    Add-Text "No tests were executed."
    Add-Text "No Git write operations were executed."
    Add-Text "Report: $Report"
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "POL-25.8.29.26 concluído — somente leitura." -ForegroundColor Green
Write-Host "Relatório: $Report"