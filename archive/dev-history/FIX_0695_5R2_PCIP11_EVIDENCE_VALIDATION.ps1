$ErrorActionPreference = "Stop"

$Repo = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$InputCsv = Join-Path $Repo "reports\PCIP11_METRIC_EVIDENCE_CANDIDATES_0695_4.csv"
$OutDir = Join-Path $Repo "reports"
$OutputCsv = Join-Path $OutDir "PCIP11_EVIDENCE_VALIDATION_0695_5R2.csv"
$OutputMd = Join-Path $OutDir "PCIP11_EVIDENCE_VALIDATION_0695_5R2.md"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function S([object]$v) {
    if ($null -eq $v) { return "" }
    return ([string]$v).Trim()
}

Write-Host ""
Write-Host "============================================================"
Write-Host "0695.5R2 - PCIP11 EVIDENCE VALIDATION"
Write-Host "============================================================"
Write-Host ""

Write-Host "[1/7] Loading 0695.4 evidence candidates..."
if (-not (Test-Path -LiteralPath $InputCsv)) { throw "Input CSV not found: $InputCsv" }
$rows = @(Import-Csv -LiteralPath $InputCsv)
if ($rows.Count -eq 0) { throw "Input CSV is empty." }
Write-Host ("Input rows: " + $rows.Count)

Write-Host "[2/7] Validating schema..."
$required = @(
    "Historical_ID","FileName","RelativePath","Extension",
    "Content_Ticker","CNPJ_Signal","Content_Periods","Canonical_Type",
    "Priority","Identity_Class","Document_Role","Period_Quality",
    "Confidence","Promotion_Decision","Extraction_Status","Text_Length",
    "Distribution_Evidence","NAV_PL_Evidence","Result_Evidence",
    "Portfolio_Credit_Evidence","Event_Evidence"
)
$headers = @($rows[0].PSObject.Properties.Name)
$missing = @($required | Where-Object { $_ -notin $headers })
if ($missing.Count -gt 0) { throw ("Missing fields: " + ($missing -join ", ")) }
Write-Host "Schema: PASS"
Write-Host "Evidence model: field presence + text length + identity + period"

Write-Host "[3/7] Applying evidence rules..."

$result = New-Object System.Collections.Generic.List[object]
$counter = 0

foreach ($r in $rows) {
    $counter++
    $identity = S $r.Identity_Class
    $role = S $r.Document_Role
    $periodQuality = S $r.Period_Quality
    $status = S $r.Extraction_Status
    $ticker = S $r.Content_Ticker
    $cnpj = S $r.CNPJ_Signal
    $textLength = 0L
    [long]::TryParse((S $r.Text_Length), [ref]$textLength) | Out-Null

    $evidenceFields = @()
    if (-not [string]::IsNullOrWhiteSpace((S $r.Distribution_Evidence))) { $evidenceFields += "DISTRIBUTION" }
    if (-not [string]::IsNullOrWhiteSpace((S $r.NAV_PL_Evidence))) { $evidenceFields += "NAV_PL" }
    if (-not [string]::IsNullOrWhiteSpace((S $r.Result_Evidence))) { $evidenceFields += "RESULT" }
    if (-not [string]::IsNullOrWhiteSpace((S $r.Portfolio_Credit_Evidence))) { $evidenceFields += "PORTFOLIO_CREDIT" }
    if (-not [string]::IsNullOrWhiteSpace((S $r.Event_Evidence))) { $evidenceFields += "EVENT" }

    $identityPass = ($identity -ne "UNRESOLVED_IDENTITY")
    $periodPass = ($periodQuality -eq "CONTENT_SUPPORTED")
    $extractionPass = ($status -eq "EXTRACTED")
    $textPass = ($textLength -gt 0)
    $evidencePass = ($evidenceFields.Count -gt 0)
    $rolePass = (-not [string]::IsNullOrWhiteSpace($role))

    $classification = "WEAK"
    $readyClass = ""
    $reason = New-Object System.Collections.Generic.List[string]

    if (-not $extractionPass) { $reason.Add("EXTRACTION_NOT_READY") }
    if (-not $identityPass) { $reason.Add("IDENTITY_UNRESOLVED") }
    if (-not $periodPass) { $reason.Add("PERIOD_NOT_CONTENT_SUPPORTED") }
    if (-not $textPass) { $reason.Add("NO_TEXT") }
    if (-not $evidencePass) { $reason.Add("NO_EVIDENCE_FIELD") }
    if (-not $rolePass) { $reason.Add("NO_ROLE") }

    if ($extractionPass -and $identityPass -and $periodPass -and $textPass -and $evidencePass -and $rolePass) {
        if ($identity -like "CVBI11_*") {
            $classification = "CVBI11_HISTORICAL_EVIDENCE_READY_REVIEW"
            $readyClass = "CVBI11_HISTORICAL"
        }
        else {
            $classification = "PCIP11_EVIDENCE_READY_REVIEW"
            $readyClass = "PCIP11"
        }
        $reason.Clear()
        $reason.Add("IDENTITY_PASS")
        $reason.Add("PERIOD_PASS")
        $reason.Add("TEXT_PASS")
        $reason.Add("EVIDENCE_FIELD_PASS")
        $reason.Add("ROLE_PASS")
    }

    $result.Add([pscustomobject]@{
        Historical_ID = S $r.Historical_ID
        SHA256 = S $r.SHA256
        FileName = S $r.FileName
        RelativePath = S $r.RelativePath
        Extension = S $r.Extension
        Original_Ticker = S $r.Original_Ticker
        Content_Ticker = $ticker
        CNPJ_Signal = $cnpj
        Storage_Year = S $r.Storage_Year
        Document_Year = S $r.Document_Year
        Content_Periods = S $r.Content_Periods
        Canonical_Type = S $r.Canonical_Type
        Priority = S $r.Priority
        Identity_Class = $identity
        Document_Role = $role
        Period_Quality = $periodQuality
        Confidence = S $r.Confidence
        Extraction_Status = $status
        Text_Length = $textLength
        Evidence_Types = ($evidenceFields -join "|")
        Evidence_Type_Count = $evidenceFields.Count
        Identity_Pass = $identityPass
        Period_Pass = $periodPass
        Text_Pass = $textPass
        Evidence_Field_Pass = $evidencePass
        Role_Pass = $rolePass
        Validation_Class = $classification
        Ready_Class = $readyClass
        Validation_Reason = ($reason -join "|")
        Promotion_Status = "NOT_PROMOTED"
    })

    if (($counter % 25) -eq 0) {
        Write-Progress -Activity "0695.5R2 evidence validation" -Status ("Row " + $counter + " / " + $rows.Count) -PercentComplete (($counter / $rows.Count) * 100)
    }
}
Write-Progress -Activity "0695.5R2 evidence validation" -Completed

Write-Host "[4/7] Saving validation matrix..."
$result | Export-Csv -LiteralPath $OutputCsv -NoTypeInformation -Encoding UTF8

Write-Host "[5/7] Building report..."
$total = $result.Count
$ready = @($result | Where-Object { $_.Validation_Class -like "*_EVIDENCE_READY_REVIEW" }).Count
$pcipReady = @($result | Where-Object { $_.Validation_Class -eq "PCIP11_EVIDENCE_READY_REVIEW" }).Count
$cvbiReady = @($result | Where-Object { $_.Validation_Class -eq "CVBI11_HISTORICAL_EVIDENCE_READY_REVIEW" }).Count
$weak = @($result | Where-Object { $_.Validation_Class -eq "WEAK" }).Count
$dist = @($result | Where-Object { $_.Evidence_Types -match "DISTRIBUTION" }).Count
$nav = @($result | Where-Object { $_.Evidence_Types -match "NAV_PL" }).Count
$res = @($result | Where-Object { $_.Evidence_Types -match "RESULT" }).Count
$port = @($result | Where-Object { $_.Evidence_Types -match "PORTFOLIO_CREDIT" }).Count
$evt = @($result | Where-Object { $_.Evidence_Types -match "EVENT" }).Count

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# 0695.5R2 - PCIP11 Evidence Validation")
$lines.Add("")
$lines.Add("Status: VALIDATION COMPLETED; NO METRIC PROMOTED")
$lines.Add("Source: PCIP11_METRIC_EVIDENCE_CANDIDATES_0695_4.csv")
$lines.Add("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
$lines.Add("")
$lines.Add("## Processing")
$lines.Add("")
$lines.Add("- Evidence rows: " + $total)
$lines.Add("- Evidence-ready for review: " + $ready)
$lines.Add("- PCIP11 evidence-ready: " + $pcipReady)
$lines.Add("- CVBI11 historical evidence-ready: " + $cvbiReady)
$lines.Add("- Weak evidence: " + $weak)
$lines.Add("")
$lines.Add("## Evidence field presence")
$lines.Add("")
$lines.Add("- Distribution: " + $dist)
$lines.Add("- NAV/PL: " + $nav)
$lines.Add("- Result: " + $res)
$lines.Add("- Portfolio/Credit: " + $port)
$lines.Add("- Events: " + $evt)
$lines.Add("")
$lines.Add("## Validation rule")
$lines.Add("")
$lines.Add("A document is evidence-ready for review only when extraction, identity, content-supported period, text, evidence field, and document role all pass.")
$lines.Add("Presence of an evidence field does not by itself promote a metric.")
$lines.Add("Metric value, unit, date/period, and provenance still require metric-level review before promotion.")
$lines.Add("")
$lines.Add("## Safety")
$lines.Add("")
$lines.Add("- No Vault note modified.")
$lines.Add("- No asset note modified.")
$lines.Add("- No metric promoted.")
$lines.Add("- No source document modified.")
$lines.Add("")
$lines.Add("## Outputs")
$lines.Add("")
$lines.Add("- CSV: " + $OutputCsv)
$lines.Add("- Report: " + $OutputMd)
$lines.Add("")
$lines.Add("## Status")
$lines.Add("")
$lines.Add("0695.5R2 EVIDENCE VALIDATION COMPLETED")
$lines | Set-Content -LiteralPath $OutputMd -Encoding UTF8

Write-Host "[6/7] Final validation..."
Write-Host ""
Write-Host ("Evidence rows                : " + $total)
Write-Host ("Evidence-ready for review   : " + $ready)
Write-Host ("PCIP11 evidence-ready       : " + $pcipReady)
Write-Host ("CVBI11 historical ready     : " + $cvbiReady)
Write-Host ("Weak evidence               : " + $weak)
Write-Host ("Distribution                : " + $dist)
Write-Host ("NAV/PL                      : " + $nav)
Write-Host ("Result                      : " + $res)
Write-Host ("Portfolio/Credit            : " + $port)
Write-Host ("Events                      : " + $evt)
Write-Host ""
Write-Host ("CSV : " + $OutputCsv)
Write-Host ("MD  : " + $OutputMd)
Write-Host ""
Write-Host "[7/7] STATUS: 0695.5R2 EVIDENCE VALIDATION COMPLETED"
Write-Host "============================================================"
