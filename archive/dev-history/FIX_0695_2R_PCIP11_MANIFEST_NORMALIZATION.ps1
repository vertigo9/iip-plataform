$ErrorActionPreference = "Stop"

$Repo = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"

$InputManifest = Join-Path $Repo "reports\PCIP11_EXTRACTION_MANIFEST_0695_2.csv"
$OutDir = Join-Path $Repo "reports"

$OutputManifest = Join-Path $OutDir "PCIP11_EXTRACTION_MANIFEST_0695_2R.csv"
$OutputReport = Join-Path $OutDir "PCIP11_EXTRACTION_MANIFEST_0695_2R.md"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host ""
Write-Host "============================================================"
Write-Host "0695.2R - PCIP11 MANIFEST NORMALIZATION"
Write-Host "============================================================"
Write-Host ""

Write-Host "[1/6] Validating input manifest..."

if (-not (Test-Path $InputManifest)) {
    throw "Input manifest not found: $InputManifest"
}

$inputRows = Import-Csv $InputManifest

Write-Host ("Input rows: " + $inputRows.Count)

function Get-NormalizedFileName {
    param(
        [string]$Name
    )

    if ([string]::IsNullOrWhiteSpace($Name)) {
        return ""
    }

    $n = $Name

    return $n
}

function Get-CanonicalTicker {
    param(
        [string]$Name
    )

    $n = $Name.ToUpper()

    if ($n -match "CVBI11") {
        return "CVBI11"
    }

    if ($n -match "PCIP11") {
        return "PCIP11"
    }

    return ""
}

function Get-DocumentPeriod {
    param(
        [string]$Name
    )

    $n = $Name

    $monthPattern = @(
        "Janeiro",
        "Fevereiro",
        "Marco",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro"
    )

    $monthNumber = @{
        "Janeiro" = "01"
        "Fevereiro" = "02"
        "Marco" = "03"
        "Abril" = "04"
        "Maio" = "05"
        "Junho" = "06"
        "Julho" = "07"
        "Agosto" = "08"
        "Setembro" = "09"
        "Outubro" = "10"
        "Novembro" = "11"
        "Dezembro" = "12"
    }

    foreach ($month in $monthPattern) {

        if ($n -match ($month + "\s+(\d{4})")) {

            $year = $Matches[1]
            $monthNo = $monthNumber[$month]

            return ($year + "-" + $monthNo)
        }
    }

    if ($n -match "([1-4])T(\d{2})") {

        $quarter = $Matches[1]
        $year2 = $Matches[2]

        return ("20" + $year2 + "-T" + $quarter)
    }

    if ($n -match "([1-4])T(\d{2})") {

        return $Matches[0]
    }

    if ($n -match "(\d{4})") {

        return $Matches[1]
    }

    return ""
}

function Get-DocumentYear {
    param(
        [string]$Period,
        [string]$StorageYear
    )

    if ($Period -match "^(\d{4})") {

        return [int]$Matches[1]
    }

    if ($StorageYear -match "^\d{4}$") {

        return [int]$StorageYear
    }

    return ""
}

function Get-CanonicalType {
    param(
        [string]$DocumentClass,
        [string]$FileName
    )

    $n = $FileName.ToLower()

    if ($n -match "rendimentos|amortiza|distribu") {
        return "DISTRIBUTION"
    }

    if ($n -match "informe mensal") {
        return "MONTHLY_REPORT"
    }

    if ($n -match "informe trimestral") {
        return "QUARTERLY_REPORT"
    }

    if ($n -match "relat") {
        return "MANAGEMENT_REPORT"
    }

    if ($n -match "demonstra") {
        return "FINANCIAL_STATEMENTS"
    }

    if ($n -match "fato relevante") {
        return "MATERIAL_EVENT"
    }

    if ($n -match "assembleia|age|ago") {
        return "GOVERNANCE"
    }

    if ($n -match "emiss") {
        return "ISSUE"
    }

    if ($n -match "fundamentos") {
        return "FUNDAMENTALS"
    }

    return $DocumentClass
}

function Get-HistoricalIdentity {
    param(
        [string]$Ticker,
        [string]$CanonicalType,
        [string]$DocumentPeriod,
        [string]$SHA256,
        [string]$NormalizedName
    )

    if (
        -not [string]::IsNullOrWhiteSpace($SHA256) -and
        $SHA256 -ne "HASH_ERROR"
    ) {

        return ("SHA256:" + $SHA256)
    }

    $fallback = (
        $Ticker + "|" +
        $CanonicalType + "|" +
        $DocumentPeriod + "|" +
        $NormalizedName
    ).ToUpper()

    return ("FALLBACK:" + $fallback)
}

Write-Host "[2/6] Normalizing document identity..."

$normalizedRows = New-Object System.Collections.Generic.List[object]

foreach ($row in $inputRows) {

    $normalizedName = Get-NormalizedFileName $row.FileName

    $ticker = Get-CanonicalTicker $normalizedName

    $storageYear = $row.Year

    $documentPeriod = Get-DocumentPeriod $normalizedName

    $documentYear = Get-DocumentYear `
        -Period $documentPeriod `
        -StorageYear $storageYear

    $canonicalType = Get-CanonicalType `
        -DocumentClass $row.DocumentClass `
        -FileName $normalizedName

    $historicalId = Get-HistoricalIdentity `
        -Ticker $ticker `
        -CanonicalType $canonicalType `
        -DocumentPeriod $documentPeriod `
        -SHA256 $row.SHA256 `
        -NormalizedName $normalizedName

    $normalizedRows.Add(
        [pscustomobject]@{
            Historical_ID = $historicalId
            Physical_ID = $row.SHA256
            Storage_Year = $storageYear
            Document_Year = $documentYear
            Document_Period = $documentPeriod
            Historical_Ticker = $ticker
            Canonical_Type = $canonicalType
            Priority = $row.Priority
            Structured = $row.Structured
            MetricFamilies = $row.MetricFamilies
            Original_FileName = $row.FileName
            Normalized_FileName = $normalizedName
            RelativePath = $row.RelativePath
            Extension = $row.Extension
            SizeBytes = $row.SizeBytes
            SHA256 = $row.SHA256
        }
    )
}

Write-Host "[3/6] Detecting duplicate physical documents..."

$finalRows = New-Object System.Collections.Generic.List[object]

$hashGroups = $normalizedRows |
    Where-Object {
        $_.SHA256 -and
        $_.SHA256 -ne "HASH_ERROR"
    } |
    Group-Object SHA256

$duplicateHashes = @{}

foreach ($group in $hashGroups) {

    if ($group.Count -gt 1) {

        foreach ($item in $group.Group) {
            $duplicateHashes[$item.Historical_ID] = $true
        }
    }
}

foreach ($row in $normalizedRows) {

    $duplicateStatus = "UNIQUE"

    if ($duplicateHashes.ContainsKey($row.Historical_ID)) {
        $duplicateStatus = "PHYSICAL_DUPLICATE"
    }

    $extractionRole = "LOW_PRIORITY"

    switch ($row.Priority) {

        "P0" {
            $extractionRole = "PRIMARY"
        }

        "P1" {
            $extractionRole = "SECONDARY_PRIMARY"
        }

        "P2" {
            $extractionRole = "CONTEXT"
        }
    }

    $finalRows.Add(
        [pscustomobject]@{
            Historical_ID = $row.Historical_ID
            Physical_ID = $row.Physical_ID
            Storage_Year = $row.Storage_Year
            Document_Year = $row.Document_Year
            Document_Period = $row.Document_Period
            Historical_Ticker = $row.Historical_Ticker
            Canonical_Type = $row.Canonical_Type
            Priority = $row.Priority
            Extraction_Role = $extractionRole
            Structured = $row.Structured
            MetricFamilies = $row.MetricFamilies
            Duplicate_Status = $duplicateStatus
            Original_FileName = $row.Original_FileName
            Normalized_FileName = $row.Normalized_FileName
            RelativePath = $row.RelativePath
            Extension = $row.Extension
            SizeBytes = $row.SizeBytes
            SHA256 = $row.SHA256
        }
    )
}

Write-Host "[4/6] Writing normalized manifest..."

$finalRows |
    Sort-Object Document_Year, Document_Period, Canonical_Type, Normalized_FileName |
    Export-Csv `
        -Path $OutputManifest `
        -NoTypeInformation `
        -Encoding UTF8

Write-Host "[5/6] Building report..."

$total = $finalRows.Count

$unique = @(
    $finalRows |
    Where-Object {
        $_.Duplicate_Status -eq "UNIQUE"
    }
).Count

$physicalDuplicates = @(
    $finalRows |
    Where-Object {
        $_.Duplicate_Status -eq "PHYSICAL_DUPLICATE"
    }
).Count

$cvbiCount = @(
    $finalRows |
    Where-Object {
        $_.Historical_Ticker -eq "CVBI11"
    }
).Count

$pcipCount = @(
    $finalRows |
    Where-Object {
        $_.Historical_Ticker -eq "PCIP11"
    }
).Count

$unknownTicker = @(
    $finalRows |
    Where-Object {
        [string]::IsNullOrWhiteSpace($_.Historical_Ticker)
    }
).Count

$unknownPeriod = @(
    $finalRows |
    Where-Object {
        [string]::IsNullOrWhiteSpace($_.Document_Period)
    }
).Count

$yearMismatch = @(
    $finalRows |
    Where-Object {
        $_.Storage_Year -match "^\d{4}$" -and
        $_.Document_Year -ne "" -and
        [int]$_.Storage_Year -ne [int]$_.Document_Year
    }
).Count

$types = $finalRows |
    Group-Object Canonical_Type |
    Sort-Object Name

$years = $finalRows |
    Group-Object Document_Year |
    Sort-Object Name

$tickers = $finalRows |
    Group-Object Historical_Ticker |
    Sort-Object Name

$reportLines = New-Object System.Collections.Generic.List[string]

$reportLines.Add("# 0695.2R - PCIP11 Manifest Normalization")
$reportLines.Add("")
$reportLines.Add("Status: NORMALIZATION COMPLETED")
$reportLines.Add("Period: 2024-2026")
$reportLines.Add("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
$reportLines.Add("")

$reportLines.Add("## Universe")
$reportLines.Add("")
$reportLines.Add("- Total rows: " + $total)
$reportLines.Add("- Unique physical documents: " + $unique)
$reportLines.Add("- Physical duplicates: " + $physicalDuplicates)
$reportLines.Add("- CVBI11: " + $cvbiCount)
$reportLines.Add("- PCIP11: " + $pcipCount)
$reportLines.Add("- Unknown ticker: " + $unknownTicker)
$reportLines.Add("- Unknown period: " + $unknownPeriod)
$reportLines.Add("- Storage/document year mismatches: " + $yearMismatch)
$reportLines.Add("")

$reportLines.Add("## Historical tickers")
$reportLines.Add("")

foreach ($g in $tickers) {

    $label = $g.Name

    if ([string]::IsNullOrWhiteSpace($label)) {
        $label = "UNKNOWN"
    }

    $reportLines.Add("- " + $label + ": " + $g.Count)
}

$reportLines.Add("")
$reportLines.Add("## Document years")
$reportLines.Add("")

foreach ($g in $years) {

    $label = $g.Name

    if ([string]::IsNullOrWhiteSpace($label)) {
        $label = "UNKNOWN"
    }

    $reportLines.Add("- " + $label + ": " + $g.Count)
}

$reportLines.Add("")
$reportLines.Add("## Canonical types")
$reportLines.Add("")

foreach ($g in $types) {
    $reportLines.Add("- " + $g.Name + ": " + $g.Count)
}

$reportLines.Add("")
$reportLines.Add("## Identity rules")
$reportLines.Add("")
$reportLines.Add("- SHA256 is the physical identity.")
$reportLines.Add("- Storage year is kept separate from document year.")
$reportLines.Add("- CVBI11 is preserved as a historical ticker.")
$reportLines.Add("- PCIP11 is preserved as a current ticker.")
$reportLines.Add("- No metric is promoted during normalization.")
$reportLines.Add("")

$reportLines.Add("## Safety")
$reportLines.Add("")
$reportLines.Add("- No Vault note modified.")
$reportLines.Add("- No asset note modified.")
$reportLines.Add("- No metric promoted.")
$reportLines.Add("")

$reportLines.Add("## Outputs")
$reportLines.Add("")
$reportLines.Add("- Input: " + $InputManifest)
$reportLines.Add("- Manifest: " + $OutputManifest)
$reportLines.Add("- Report: " + $OutputReport)
$reportLines.Add("")

$reportLines.Add("## Status")
$reportLines.Add("")
$reportLines.Add("0695.2R MANIFEST NORMALIZATION COMPLETED")

$reportLines |
    Set-Content `
        -Path $OutputReport `
        -Encoding UTF8

Write-Host "[6/6] Final validation..."
Write-Host ""
Write-Host ("Total rows          : " + $total)
Write-Host ("Unique physical     : " + $unique)
Write-Host ("Physical duplicates : " + $physicalDuplicates)
Write-Host ("CVBI11              : " + $cvbiCount)
Write-Host ("PCIP11              : " + $pcipCount)
Write-Host ("Unknown ticker      : " + $unknownTicker)
Write-Host ("Unknown period      : " + $unknownPeriod)
Write-Host ("Year mismatches     : " + $yearMismatch)
Write-Host ""
Write-Host ("Manifest            : " + $OutputManifest)
Write-Host ("Report              : " + $OutputReport)
Write-Host ""
Write-Host "STATUS: 0695.2R MANIFEST NORMALIZATION COMPLETED"
Write-Host "============================================================"