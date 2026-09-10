$ErrorActionPreference = "Stop"

$Repo = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$InputCsv = Join-Path $Repo "reports\PCIP11_METRIC_EVIDENCE_CANDIDATES_0695_4.csv"
$OutDir = Join-Path $Repo "reports"
$OutputCsv = Join-Path $OutDir "PCIP11_EVIDENCE_VALIDATION_0695_5R1.csv"
$OutputMd = Join-Path $OutDir "PCIP11_EVIDENCE_VALIDATION_0695_5R1.md"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host ""
Write-Host "============================================================"
Write-Host "0695.5R1 - PCIP11 EVIDENCE VALIDATION"
Write-Host "============================================================"
Write-Host ""

# 1. INPUT
Write-Host "[1/7] Loading 0695.4 evidence candidates..."
if (-not (Test-Path -LiteralPath $InputCsv)) {
    throw "Input CSV not found: $InputCsv"
}

$rows = @(Import-Csv -LiteralPath $InputCsv)
if ($rows.Count -eq 0) {
    throw "Input CSV is empty."
}
Write-Host ("Input rows: " + $rows.Count)

# 2. SCHEMA VALIDATION
Write-Host "[2/7] Validating schema..."
$expected = @(
    "Historical_ID","SHA256","FileName","RelativePath","Extension",
    "Original_Ticker","Content_Ticker","CNPJ_Signal","Storage_Year",
    "Document_Year","Content_Periods","Canonical_Type","Priority",
    "Identity_Class","Document_Role","Period_Quality","Confidence",
    "Promotion_Decision","Extraction_Status","Text_Length",
    "Distribution_Evidence","NAV_PL_Evidence","Result_Evidence",
    "Portfolio_Credit_Evidence","Event_Evidence","Error_Type","Error_Message"
)

$propertyNames = @($rows[0].PSObject.Properties.Name)
$missing = @($expected | Where-Object { $_ -notin $propertyNames })
if ($missing.Count -gt 0) {
    throw ("Missing required columns: " + ($missing -join ", "))
}

Write-Host "Schema: PASS"
Write-Host "Evidence fields: Distribution_Evidence, NAV_PL_Evidence, Result_Evidence, Portfolio_Credit_Evidence, Event_Evidence"
Write-Host "Identity field: Identity_Class"
Write-Host "Role field: Document_Role"
Write-Host "Period field: Content_Periods / Period_Quality"
Write-Host "Source field: FileName / RelativePath"

# 3. HELPERS
function Get-Text([object]$Value) {
    if ($null -eq $Value) { return "" }
    return ([string]$Value).Trim()
}

function Has-Value([object]$Value) {
    $t = Get-Text $Value
    return -not [string]::IsNullOrWhiteSpace($t)
}

function Is-TrueSignal([object]$Value) {
    $t = (Get-Text $Value).ToLowerInvariant()
    return ($t -eq "true" -or $t -eq "yes" -or $t -eq "1")
}

function Has-StrongIdentity([string]$IdentityClass) {
    return $IdentityClass -in @(
        "PCIP11_CONFIRMED_CNPJ",
        "PCIP11_CONFIRMED_TICKER",
        "CVBI11_HISTORICAL_CONFIRMED_CNPJ",
        "CVBI11_HISTORICAL",
        "PCIP11_CNPJ_ONLY"
    )
}

function Get-EvidenceKind([object]$Row) {
    $flags = New-Object System.Collections.Generic.List[string]
    if (Is-TrueSignal $Row.Distribution_Evidence) { $flags.Add("DISTRIBUTION") }
    if (Is-TrueSignal $Row.NAV_PL_Evidence) { $flags.Add("NAV_PL") }
    if (Is-TrueSignal $Row.Result_Evidence) { $flags.Add("RESULT") }
    if (Is-TrueSignal $Row.Portfolio_Credit_Evidence) { $flags.Add("PORTFOLIO_CREDIT") }
    if (Is-TrueSignal $Row.Event_Evidence) { $flags.Add("EVENT") }
    return ($flags -join "|")
}

function Get-ValidationDecision([object]$Row) {
    $identity = Get-Text $Row.Identity_Class
    $role = Get-Text $Row.Document_Role
    $periodQuality = Get-Text $Row.Period_Quality
    $confidence = Get-Text $Row.Confidence
    $status = Get-Text $Row.Extraction_Status
    $textLength = 0
    [int]::TryParse((Get-Text $Row.Text_Length), [ref]$textLength) | Out-Null
    $evidenceKind = Get-EvidenceKind $Row

    if ($status -ne "EXTRACTED") {
        return "HOLD_EXTRACTION"
    }

    if (-not (Has-StrongIdentity $identity)) {
        return "HOLD_IDENTITY"
    }

    if ($periodQuality -ne "CONTENT_SUPPORTED") {
        return "HOLD_PERIOD"
    }

    if ([string]::IsNullOrWhiteSpace($evidenceKind)) {
        return "NO_EVIDENCE_SIGNAL"
    }

    if ($textLength -lt 80) {
        return "WEAK_TEXT"
    }

    if ($confidence -eq "HIGH" -and $periodQuality -eq "CONTENT_SUPPORTED") {
        if ($role -in @(
            "DISTRIBUTION",
            "FINANCIAL_STATEMENTS",
            "PORTFOLIO_CREDIT",
            "RESULT",
            "NAV_PL",
            "EVENT_GOVERNANCE_ISSUE",
            "MONTHLY_REPORT",
            "QUARTERLY_REPORT",
            "MANAGEMENT_REPORT"
        )) {
            return "EVIDENCE_READY_REVIEW"
        }
    }

    if ($confidence -in @("MEDIUM-HIGH","MEDIUM")) {
        return "REVIEW_BEFORE_PROMOTION"
    }

    return "WEAK_EVIDENCE"
}

# 4. VALIDATE
Write-Host "[3/7] Applying corrected evidence rules..."
$validated = New-Object System.Collections.Generic.List[object]

foreach ($row in $rows) {
    $evidenceKind = Get-EvidenceKind $row
    $decision = Get-ValidationDecision $row

    $promotionTarget = "NONE"
    if ($decision -eq "EVIDENCE_READY_REVIEW") {
        $identity = Get-Text $row.Identity_Class
        if ($identity -like "PCIP11_*") {
            $promotionTarget = "PCIP11_EVIDENCE_REVIEW"
        }
        elseif ($identity -like "CVBI11_*") {
            $promotionTarget = "CVBI11_HISTORICAL_EVIDENCE_REVIEW"
        }
    }

    $metricCandidates = New-Object System.Collections.Generic.List[string]
    if (Is-TrueSignal $row.Distribution_Evidence) { $metricCandidates.Add("distribution") }
    if (Is-TrueSignal $row.NAV_PL_Evidence) { $metricCandidates.Add("nav_pl") }
    if (Is-TrueSignal $row.Result_Evidence) { $metricCandidates.Add("result") }
    if (Is-TrueSignal $row.Portfolio_Credit_Evidence) { $metricCandidates.Add("portfolio_credit") }
    if (Is-TrueSignal $row.Event_Evidence) { $metricCandidates.Add("event") }

    $validated.Add([pscustomobject]@{
        Historical_ID = Get-Text $row.Historical_ID
        SHA256 = Get-Text $row.SHA256
        FileName = Get-Text $row.FileName
        RelativePath = Get-Text $row.RelativePath
        Extension = Get-Text $row.Extension
        Original_Ticker = Get-Text $row.Original_Ticker
        Content_Ticker = Get-Text $row.Content_Ticker
        CNPJ_Signal = Get-Text $row.CNPJ_Signal
        Storage_Year = Get-Text $row.Storage_Year
        Document_Year = Get-Text $row.Document_Year
        Content_Periods = Get-Text $row.Content_Periods
        Canonical_Type = Get-Text $row.Canonical_Type
        Priority = Get-Text $row.Priority
        Identity_Class = Get-Text $row.Identity_Class
        Document_Role = Get-Text $row.Document_Role
        Period_Quality = Get-Text $row.Period_Quality
        Confidence = Get-Text $row.Confidence
        Extraction_Status = Get-Text $row.Extraction_Status
        Text_Length = Get-Text $row.Text_Length
        Distribution_Evidence = Get-Text $row.Distribution_Evidence
        NAV_PL_Evidence = Get-Text $row.NAV_PL_Evidence
        Result_Evidence = Get-Text $row.Result_Evidence
        Portfolio_Credit_Evidence = Get-Text $row.Portfolio_Credit_Evidence
        Event_Evidence = Get-Text $row.Event_Evidence
        Evidence_Kind = $evidenceKind
        Metric_Candidates = ($metricCandidates -join "|")
        Validation_Decision = $decision
        Promotion_Target = $promotionTarget
    })
}

# 5. SAVE
Write-Host "[4/7] Saving corrected validation matrix..."
$validated | Export-Csv -LiteralPath $OutputCsv -NoTypeInformation -Encoding UTF8

# 6. STATS / REPORT
Write-Host "[5/7] Building report..."
$total = $validated.Count
$ready = @($validated | Where-Object { $_.Validation_Decision -eq "EVIDENCE_READY_REVIEW" }).Count
$pcipReady = @($validated | Where-Object { $_.Promotion_Target -eq "PCIP11_EVIDENCE_REVIEW" }).Count
$cvbiReady = @($validated | Where-Object { $_.Promotion_Target -eq "CVBI11_HISTORICAL_EVIDENCE_REVIEW" }).Count
$weak = @($validated | Where-Object { $_.Validation_Decision -in @("WEAK_EVIDENCE","WEAK_TEXT","NO_EVIDENCE_SIGNAL") }).Count
$hold = @($validated | Where-Object { $_.Validation_Decision -like "HOLD_*" }).Count
$review = @($validated | Where-Object { $_.Validation_Decision -eq "REVIEW_BEFORE_PROMOTION" }).Count

$dist = @($validated | Where-Object { Is-TrueSignal $_.Distribution_Evidence }).Count
$nav = @($validated | Where-Object { Is-TrueSignal $_.NAV_PL_Evidence }).Count
$result = @($validated | Where-Object { Is-TrueSignal $_.Result_Evidence }).Count
$portfolio = @($validated | Where-Object { Is-TrueSignal $_.Portfolio_Credit_Evidence }).Count
$events = @($validated | Where-Object { Is-TrueSignal $_.Event_Evidence }).Count

$decisionGroups = @($validated | Group-Object Validation_Decision | Sort-Object Name)

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# 0695.5R1 - PCIP11 Evidence Validation")
$lines.Add("")
$lines.Add("Status: CORRECTED VALIDATION COMPLETED")
$lines.Add("Source: PCIP11_METRIC_EVIDENCE_CANDIDATES_0695_4.csv")
$lines.Add("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
$lines.Add("")
$lines.Add("## Core validation")
$lines.Add("")
$lines.Add("- Evidence rows: " + $total)
$lines.Add("- Evidence-ready for review: " + $ready)
$lines.Add("- PCIP11 evidence-ready: " + $pcipReady)
$lines.Add("- CVBI11 historical evidence-ready: " + $cvbiReady)
$lines.Add("- Review before promotion: " + $review)
$lines.Add("- Weak evidence: " + $weak)
$lines.Add("- Holds: " + $hold)
$lines.Add("")
$lines.Add("## Evidence signals")
$lines.Add("")
$lines.Add("- Distribution: " + $dist)
$lines.Add("- NAV/PL: " + $nav)
$lines.Add("- Result: " + $result)
$lines.Add("- Portfolio/Credit: " + $portfolio)
$lines.Add("- Events: " + $events)
$lines.Add("")
$lines.Add("## Decisions")
$lines.Add("")
foreach ($g in $decisionGroups) {
    $lines.Add("- " + $g.Name + ": " + $g.Count)
}
$lines.Add("")
$lines.Add("## Corrected schema mapping")
$lines.Add("")
$lines.Add("- Identity: Identity_Class")
$lines.Add("- Role: Document_Role")
$lines.Add("- Period: Content_Periods + Period_Quality")
$lines.Add("- Evidence: Distribution_Evidence / NAV_PL_Evidence / Result_Evidence / Portfolio_Credit_Evidence / Event_Evidence")
$lines.Add("- Source locator: FileName + RelativePath")
$lines.Add("- Text availability: Text_Length")
$lines.Add("")
$lines.Add("## Promotion policy")
$lines.Add("")
$lines.Add("- This phase does not promote metrics into canonical Vault notes.")
$lines.Add("- EVIDENCE_READY_REVIEW means the document is eligible for metric-level human/rule review.")
$lines.Add("- PCIP11 and historical CVBI11 evidence remain distinct.")
$lines.Add("- Content-supported periods are required.")
$lines.Add("- Source locator is preserved for auditability.")
$lines.Add("")
$lines.Add("## Safety")
$lines.Add("")
$lines.Add("- No Vault note modified.")
$lines.Add("- No asset note modified.")
$lines.Add("- No metric promoted.")
$lines.Add("- No source document modified.")
$lines.Add("")
$lines.Add("## Status")
$lines.Add("")
$lines.Add("0695.5R1 CORRECTED EVIDENCE VALIDATION COMPLETED")

$lines | Set-Content -LiteralPath $OutputMd -Encoding UTF8

# 7. FINAL
Write-Host "[6/7] Final validation..."
Write-Host ""
Write-Host ("Evidence rows                : " + $total)
Write-Host ("Evidence-ready for review   : " + $ready)
Write-Host ("PCIP11 evidence-ready       : " + $pcipReady)
Write-Host ("CVBI11 historical ready     : " + $cvbiReady)
Write-Host ("Review before promotion     : " + $review)
Write-Host ("Weak evidence               : " + $weak)
Write-Host ("Holds                       : " + $hold)
Write-Host ("Distribution                : " + $dist)
Write-Host ("NAV/PL                      : " + $nav)
Write-Host ("Result                      : " + $result)
Write-Host ("Portfolio/Credit            : " + $portfolio)
Write-Host ("Events                      : " + $events)
Write-Host ""
Write-Host ("CSV : " + $OutputCsv)
Write-Host ("MD  : " + $OutputMd)
Write-Host ""
Write-Host "[7/7] STATUS: 0695.5R1 CORRECTED EVIDENCE VALIDATION COMPLETED"
Write-Host "============================================================"
