$ErrorActionPreference = "Stop"

$Repo = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$DataRoot = Join-Path $Repo "data\patria\PCIP11"
$OutDir = Join-Path $Repo "reports"

$ManifestPath = Join-Path $OutDir "PCIP11_EXTRACTION_MANIFEST_0695_2.csv"
$ReportPath = Join-Path $OutDir "PCIP11_EXTRACTION_MANIFEST_0695_2.md"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host ""
Write-Host "============================================================"
Write-Host "0695.2 - PCIP11 EXTRACTION MANIFEST"
Write-Host "============================================================"
Write-Host ""

Write-Host "[1/4] Localizando documentos..."

$files = Get-ChildItem $DataRoot -Recurse -File |
    Where-Object {
        $_.FullName -match "\\2024\\" -or
        $_.FullName -match "\\2025\\" -or
        $_.FullName -match "\\2026\\"
    }

$rows = New-Object System.Collections.Generic.List[object]

foreach ($f in $files) {

    $name = $f.Name.ToLower()
    $ext = $f.Extension.ToLower()

    $priority = "LOW"
    $documentClass = "OTHER"
    $metricFamilies = ""
    $structured = $false

    # --------------------------------------------------------
    # STRUCTURED SOURCES
    # --------------------------------------------------------

    if ($name -match "fundamentos" -and $ext -eq ".xlsx") {

        $priority = "P0"
        $documentClass = "FUNDAMENTALS_STRUCTURED"
        $metricFamilies = "NAV,PL,QUOTAS,PRICE,PVP,DY,RESULT,DISTRIBUTION"
        $structured = $true
    }

    elseif ($ext -eq ".xml" -and $name -match "informe|fundamento|rendimento|amortiza") {

        $priority = "P0"
        $documentClass = "STRUCTURED_XML"
        $metricFamilies = "DISTRIBUTION,IDENTITY,FINANCIAL"
        $structured = $true
    }

    elseif ($ext -eq ".csv") {

        $priority = "P0"
        $documentClass = "STRUCTURED_CSV"
        $metricFamilies = "MARKET,DISTRIBUTION,FINANCIAL"
        $structured = $true
    }

    # --------------------------------------------------------
    # DISTRIBUTIONS
    # --------------------------------------------------------

    elseif ($name -match "rendimentos|amortiza|distribu") {

        $priority = "P1"
        $documentClass = "DISTRIBUTION"
        $metricFamilies = "COMPETENCE,BASE_DATE,PAYMENT_DATE,INCOME,AMORTIZATION,TOTAL_DISTRIBUTION"
    }

    # --------------------------------------------------------
    # MONTHLY
    # --------------------------------------------------------

    elseif ($name -match "informe mensal") {

        $priority = "P1"
        $documentClass = "MONTHLY_REPORT"
        $metricFamilies = "NAV,PL,QUOTAS,HOLDERS,PORTFOLIO,RESULT,DISTRIBUTION"
    }

    # --------------------------------------------------------
    # QUARTERLY
    # --------------------------------------------------------

    elseif ($name -match "informe trimestral") {

        $priority = "P1"
        $documentClass = "QUARTERLY_REPORT"
        $metricFamilies = "PL,NAV,PORTFOLIO,CREDIT,RESULT,RISK"
    }

    # --------------------------------------------------------
    # MANAGEMENT REPORT
    # --------------------------------------------------------

    elseif ($name -match "relat.*gerencial") {

        $priority = "P1"
        $documentClass = "MANAGEMENT_REPORT"
        $metricFamilies = "PORTFOLIO,RESULT,DISTRIBUTION,RISK,EVENTS"
    }

    # --------------------------------------------------------
    # FINANCIAL STATEMENTS
    # --------------------------------------------------------

    elseif ($name -match "demonstra") {

        $priority = "P1"
        $documentClass = "FINANCIAL_STATEMENTS"
        $metricFamilies = "REVENUE,EXPENSES,RESULT,ASSETS,LIABILITIES"
    }

    # --------------------------------------------------------
    # MATERIAL EVENTS
    # --------------------------------------------------------

    elseif ($name -match "fato relevante") {

        $priority = "P1"
        $documentClass = "MATERIAL_EVENT"
        $metricFamilies = "EVENTS,RESTRUCTURING,GOVERNANCE"
    }

    # --------------------------------------------------------
    # GOVERNANCE
    # --------------------------------------------------------

    elseif ($name -match "assembleia|age|ago") {

        $priority = "P2"
        $documentClass = "GOVERNANCE"
        $metricFamilies = "GOVERNANCE,EVENTS"
    }

    # --------------------------------------------------------
    # ISSUE
    # --------------------------------------------------------

    elseif ($name -match "emiss") {

        $priority = "P2"
        $documentClass = "ISSUE"
        $metricFamilies = "QUOTAS,STRUCTURE,CAPITAL"
    }

    # --------------------------------------------------------
    # OTHER
    # --------------------------------------------------------

    else {

        $priority = "P3"
        $documentClass = "OTHER"
        $metricFamilies = ""
    }

    $hash = ""

    try {
        $hash = (Get-FileHash -Algorithm SHA256 -Path $f.FullName).Hash
    }
    catch {
        $hash = "HASH_ERROR"
    }

    $year = ""

    if ($f.FullName -match "\\(2024|2025|2026)\\") {
        $year = $Matches[1]
    }

    $rows.Add(
        [pscustomobject]@{
            Year = $year
            Priority = $priority
            DocumentClass = $documentClass
            Structured = $structured
            MetricFamilies = $metricFamilies
            FileName = $f.Name
            RelativePath = $f.FullName.Replace($Repo + "\", "")
            Extension = $ext
            SizeBytes = $f.Length
            SHA256 = $hash
        }
    )
}

Write-Host "[2/4] Gravando manifest..."

$rows |
    Sort-Object Priority, Year, DocumentClass, FileName |
    Export-Csv `
        -Path $ManifestPath `
        -NoTypeInformation `
        -Encoding UTF8

Write-Host "[3/4] Consolidando estatisticas..."

$byPriority = $rows |
    Group-Object Priority |
    Sort-Object Name

$byClass = $rows |
    Group-Object DocumentClass |
    Sort-Object Name

$structuredCount = @(
    $rows |
    Where-Object { $_.Structured -eq $true }
).Count

$p0Count = @(
    $rows |
    Where-Object { $_.Priority -eq "P0" }
).Count

$p1Count = @(
    $rows |
    Where-Object { $_.Priority -eq "P1" }
).Count

$p2Count = @(
    $rows |
    Where-Object { $_.Priority -eq "P2" }
).Count

$p3Count = @(
    $rows |
    Where-Object { $_.Priority -eq "P3" }
).Count

Write-Host "[4/4] Gerando relatorio..."

$lines = New-Object System.Collections.Generic.List[string]

$lines.Add("# 0695.2 - PCIP11 Extraction Manifest")
$lines.Add("")
$lines.Add("Status: MANIFEST COMPLETED")
$lines.Add("Period: 2024-2026")
$lines.Add("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
$lines.Add("")

$lines.Add("## Universe")
$lines.Add("")
$lines.Add("- Total documents: " + $rows.Count)
$lines.Add("- Structured documents: " + $structuredCount)
$lines.Add("- P0: " + $p0Count)
$lines.Add("- P1: " + $p1Count)
$lines.Add("- P2: " + $p2Count)
$lines.Add("- P3: " + $p3Count)
$lines.Add("")

$lines.Add("## Priority")
$lines.Add("")

foreach ($g in $byPriority) {
    $lines.Add("- " + $g.Name + ": " + $g.Count)
}

$lines.Add("")
$lines.Add("## Document classes")
$lines.Add("")

foreach ($g in $byClass) {
    $lines.Add("- " + $g.Name + ": " + $g.Count)
}

$lines.Add("")
$lines.Add("## Extraction order")
$lines.Add("")
$lines.Add("1. Structured fundamentals")
$lines.Add("2. Distribution and amortization")
$lines.Add("3. Monthly reports")
$lines.Add("4. Quarterly reports")
$lines.Add("5. Management reports")
$lines.Add("6. Financial statements")
$lines.Add("7. Material events")
$lines.Add("8. Governance and issue documents")
$lines.Add("9. Other documents")
$lines.Add("")

$lines.Add("## Safety")
$lines.Add("")
$lines.Add("No canonical asset note modified.")
$lines.Add("No historical metric promoted.")
$lines.Add("No Vault synchronization performed.")
$lines.Add("")

$lines.Add("## Outputs")
$lines.Add("")
$lines.Add("- Manifest: " + $ManifestPath)
$lines.Add("- Report: " + $ReportPath)
$lines.Add("")

$lines.Add("## Status")
$lines.Add("")
$lines.Add("0695.2 EXTRACTION MANIFEST COMPLETED")

$lines |
    Set-Content `
        -Path $ReportPath `
        -Encoding UTF8

Write-Host ""
Write-Host "Documents total      : " $rows.Count
Write-Host "Structured           : " $structuredCount
Write-Host "P0                   : " $p0Count
Write-Host "P1                   : " $p1Count
Write-Host "P2                   : " $p2Count
Write-Host "P3                   : " $p3Count
Write-Host "Manifest             : " $ManifestPath
Write-Host "Report               : " $ReportPath
Write-Host ""
Write-Host "STATUS: 0695.2 EXTRACTION MANIFEST COMPLETED"
Write-Host "============================================================"