$ErrorActionPreference = "Stop"

$Repo = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$DataRoot = Join-Path $Repo "data\patria\PCIP11"
$OutDir = Join-Path $Repo "reports"

$ManifestPath = Join-Path $OutDir "PCIP11_HIST_0695.csv"
$ReportPath = Join-Path $OutDir "PCIP11_HIST_0695.md"
$ProbePath = Join-Path $OutDir "PCIP11_PROBE_0695.txt"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host ""
Write-Host "============================================================"
Write-Host "0695 - PCIP11 HISTORICAL POPULATION PILOT"
Write-Host "============================================================"
Write-Host ""

# ============================================================
# 1. INVENTARIO
# ============================================================

Write-Host "[1/5] Inventariando documentos..."

$files = @()

if (Test-Path $DataRoot) {

    $files = Get-ChildItem $DataRoot -Recurse -File |
        Where-Object {
            $_.FullName -match "\\2024\\" -or
            $_.FullName -match "\\2025\\" -or
            $_.FullName -match "\\2026\\"
        }
}
else {
    throw "Data root nao encontrado: $DataRoot"
}

$rows = New-Object System.Collections.Generic.List[object]

foreach ($f in $files) {

    $year = ""

    if ($f.FullName -match "\\(2024|2025|2026)\\") {
        $year = $Matches[1]
    }

    $type = "OTHER"

    switch -Regex ($f.Name.ToLower()) {

        "informe mensal" {
            $type = "MONTHLY_REPORT"
            break
        }

        "informe trimestral" {
            $type = "QUARTERLY_REPORT"
            break
        }

        "relat.*gerencial" {
            $type = "MANAGEMENT_REPORT"
            break
        }

        "rendimentos|amortiza" {
            $type = "DISTRIBUTION"
            break
        }

        "fundamentos" {
            $type = "FUNDAMENTALS"
            break
        }

        "demonstra" {
            $type = "FINANCIAL_STATEMENTS"
            break
        }

        "fato relevante" {
            $type = "MATERIAL_EVENT"
            break
        }

        "assembleia|age|ago" {
            $type = "GOVERNANCE"
            break
        }

        "emiss" {
            $type = "ISSUE"
            break
        }

        "\.xml$" {
            $type = "STRUCTURED_XML"
            break
        }

        "\.xlsx$" {
            $type = "STRUCTURED_XLSX"
            break
        }

        "\.csv$" {
            $type = "STRUCTURED_CSV"
            break
        }

        "\.zip$" {
            $type = "ARCHIVE"
            break
        }
    }

    $hash = "HASH_ERROR"

    try {
        $hash = (Get-FileHash -Algorithm SHA256 -Path $f.FullName).Hash
    }
    catch {
        $hash = "HASH_ERROR"
    }

    $rows.Add(
        [pscustomobject]@{
            Year         = $year
            Type         = $type
            FileName     = $f.Name
            RelativePath = $f.FullName.Replace($Repo + "\", "")
            SizeBytes    = $f.Length
            SHA256       = $hash
        }
    )
}

$rows |
    Sort-Object Year, Type, FileName |
    Export-Csv `
        -Path $ManifestPath `
        -NoTypeInformation `
        -Encoding UTF8

$duplicateGroups = @(
    $rows |
    Group-Object SHA256 |
    Where-Object { $_.Count -gt 1 }
)

$byType = $rows |
    Group-Object Type |
    Sort-Object Name

$byYear = $rows |
    Group-Object Year |
    Sort-Object Name

# ============================================================
# 2. FORCAR PYTHON NO REPOSITORIO ATUAL
# ============================================================

Write-Host "[2/5] Validando ambiente Python..."

$pythonCommand = Get-Command python -ErrorAction Stop

$env:PYTHONPATH = Join-Path $Repo "src"

$PythonExe = $pythonCommand.Source

$ProbeScript = @'
import inspect
import sys

print("PYTHON VERSION:")
print(sys.version)
print("")

print("PYTHON EXECUTABLE:")
print(sys.executable)
print("")

print("SYS.PATH:")
for item in sys.path:
    print(item)

print("")

modules = [
    ("iip", None),
    ("iip.atlas.batch", "HistoricalAtlasIngestion"),
    ("iip.atlas.history", "AtlasHistoryProcessor"),
    ("iip.portfolio_data.market_data", "MarketQuote"),
    ("iip.portfolio_data.yield_metrics", "yield_on_price"),
    ("iip.portfolio_data.valuation", "ValuationSnapshot"),
]

for module_name, object_name in modules:

    print("=" * 70)
    print(module_name)
    print("=" * 70)

    try:

        module = __import__(module_name, fromlist=["*"])

        print("MODULE FILE:")
        print(getattr(module, "__file__", "N/A"))
        print("")

        if object_name:

            obj = getattr(module, object_name, None)

            print("OBJECT:")
            print(object_name)

            if obj:

                try:
                    print("SIGNATURE:")
                    print(inspect.signature(obj))
                except Exception:
                    print("SIGNATURE: unavailable")

                try:
                    print("SOURCE:")
                    print(inspect.getsourcefile(obj))
                except Exception:
                    print("SOURCE: unavailable")

            else:
                print("OBJECT NOT FOUND")

    except Exception as exc:

        print("ERROR:")
        print(type(exc).__name__, str(exc))

    print("")
'@

$TempPython = Join-Path $env:TEMP "probe_0695.py"

Set-Content `
    -Path $TempPython `
    -Value $ProbeScript `
    -Encoding UTF8

python $TempPython 2>&1 |
    Out-File `
        -FilePath $ProbePath `
        -Encoding UTF8

Remove-Item $TempPython -Force

# ============================================================
# 3. LEITURA DO PROBE
# ============================================================

Write-Host "[3/5] Verificando origem do pacote iip..."

$probeText = Get-Content $ProbePath -Raw -Encoding UTF8

$currentRepoMarker = ($Repo + "\src").ToLower()
$oldRepoMarker = "iip_obsidian_integration_v1.0a".ToLower()

$currentSourceDetected = $probeText.ToLower().Contains($currentRepoMarker)
$oldSourceDetected = $probeText.ToLower().Contains($oldRepoMarker)

# ============================================================
# 4. RELATORIO
# ============================================================

Write-Host "[4/5] Gerando relatorio..."

$ReportLines = New-Object System.Collections.Generic.List[string]

$ReportLines.Add("# 0695 - PCIP11 Historical Population Pilot")
$ReportLines.Add("")
$ReportLines.Add("Status: PILOT INVENTORY COMPLETED")
$ReportLines.Add("Period: 2024-2026")
$ReportLines.Add("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
$ReportLines.Add("")

$ReportLines.Add("## Document universe")
$ReportLines.Add("")
$ReportLines.Add("- Files found: " + $rows.Count)
$ReportLines.Add("- Duplicate SHA256 groups: " + $duplicateGroups.Count)
$ReportLines.Add("")

$ReportLines.Add("## By year")
$ReportLines.Add("")

foreach ($g in $byYear) {
    $ReportLines.Add("- " + $g.Name + ": " + $g.Count)
}

$ReportLines.Add("")
$ReportLines.Add("## By document type")
$ReportLines.Add("")

foreach ($g in $byType) {
    $ReportLines.Add("- " + $g.Name + ": " + $g.Count)
}

$ReportLines.Add("")
$ReportLines.Add("## Python environment")
$ReportLines.Add("")
$ReportLines.Add("- Python executable: " + $PythonExe)
$ReportLines.Add("- Current repository source detected: " + $currentSourceDetected)
$ReportLines.Add("- Legacy v1.0a source detected: " + $oldSourceDetected)
$ReportLines.Add("- Probe: " + $ProbePath)
$ReportLines.Add("")

$ReportLines.Add("## Safety")
$ReportLines.Add("")
$ReportLines.Add("No canonical asset note was modified.")
$ReportLines.Add("No Vault note was modified.")
$ReportLines.Add("No historical metric was promoted.")
$ReportLines.Add("")

$ReportLines.Add("## Outputs")
$ReportLines.Add("")
$ReportLines.Add("- Manifest: " + $ManifestPath)
$ReportLines.Add("- Report: " + $ReportPath)
$ReportLines.Add("- Probe: " + $ProbePath)
$ReportLines.Add("")

$ReportLines.Add("## Status")
$ReportLines.Add("")
$ReportLines.Add("0695 PILOT INVENTORY COMPLETED")

$ReportLines |
    Set-Content `
        -Path $ReportPath `
        -Encoding UTF8

# ============================================================
# 5. RESULTADO
# ============================================================

Write-Host "[5/5] Validacao final..."
Write-Host ""

Write-Host ("Documents 2024-2026 : " + $rows.Count)
Write-Host ("Duplicate hash groups: " + $duplicateGroups.Count)
Write-Host ("Manifest             : " + $ManifestPath)
Write-Host ("Report               : " + $ReportPath)
Write-Host ("Probe                : " + $ProbePath)
Write-Host ("Current src detected : " + $currentSourceDetected)
Write-Host ("Legacy v1.0a detect. : " + $oldSourceDetected)
Write-Host ""

if (-not $currentSourceDetected) {
    Write-Host "STATUS: FAIL - CURRENT REPOSITORY SOURCE NOT DETECTED"
    exit 1
}

Write-Host "STATUS: 0695 PILOT INVENTORY COMPLETED"
Write-Host "============================================================"