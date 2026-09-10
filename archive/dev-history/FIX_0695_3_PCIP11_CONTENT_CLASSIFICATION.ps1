$ErrorActionPreference = "Stop"

$Repo = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$InputCsv = Join-Path $Repo "reports\PCIP11_MULTIFORMAT_TRIAGE_0695_2R3_FIXED.csv"
$OutDir = Join-Path $Repo "reports"
$OutputCsv = Join-Path $OutDir "PCIP11_CONTENT_CLASSIFICATION_0695_3.csv"
$OutputMd = Join-Path $OutDir "PCIP11_CONTENT_CLASSIFICATION_0695_3.md"
$QueueCsv = Join-Path $OutDir "PCIP11_EVIDENCE_PROMOTION_QUEUE_0695_3.csv"
$QueueMd = Join-Path $OutDir "PCIP11_EVIDENCE_PROMOTION_QUEUE_0695_3.md"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host ""
Write-Host "============================================================"
Write-Host "0695.3 - PCIP11 CONTENT CLASSIFICATION"
Write-Host "============================================================"
Write-Host ""

Write-Host "[1/7] Validating 0695.2R3 output..."
if (-not (Test-Path -LiteralPath $InputCsv)) { throw "Input CSV not found: $InputCsv" }
$rows = @(Import-Csv -LiteralPath $InputCsv)
if ($rows.Count -eq 0) { throw "Input CSV is empty." }
Write-Host ("Input rows: " + $rows.Count)

function Txt { param([object]$v) if ($null -eq $v) { return "" }; return ([string]$v).Trim() }
function Low { param([object]$v) return (Txt $v).ToLowerInvariant() }

function Get-IdentityClass {
    param([string]$ContentTicker,[string]$CnpjSignal,[string]$OriginalTicker,[string]$FileName)
    $ticker = Low $ContentTicker; $orig = Low $OriginalTicker; $name = Low $FileName
    $hasPcip = $ticker.Contains("pcip11"); $hasCvbi = $ticker.Contains("cvbi11")
    $hasCnpj = $CnpjSignal -eq "True"
    $cvbiName = $name.Contains("cvbi11") -or $orig.Contains("cvbi11")
    if ($hasPcip -and $hasCnpj) { return "PCIP11_CONFIRMED_CNPJ" }
    if ($hasPcip) { return "PCIP11_CONFIRMED_TICKER" }
    if ($hasCvbi -and $hasCnpj) { return "CVBI11_HISTORICAL_CONFIRMED_CNPJ" }
    if ($hasCvbi -or $cvbiName) { return "CVBI11_HISTORICAL" }
    if ($hasCnpj) { return "PCIP11_CNPJ_ONLY" }
    return "UNRESOLVED_IDENTITY"
}

function Get-DocumentRole {
    param([string]$CanonicalType,[string]$FileName,[string]$DistributionSignal,[string]$NavSignal,[string]$PortfolioSignal,[string]$ResultSignal,[string]$EventSignal)
    $type = Low $CanonicalType; $name = Low $FileName
    if ($type.Contains("distribution") -or $name.Contains("distribui") -or $name.Contains("rendimento") -or $name.Contains("amortiza") -or $DistributionSignal -eq "True") { return "DISTRIBUTION" }
    if ($type.Contains("financial") -or $name.Contains("demonstra") -or $name.Contains("balan") -or $name.Contains("resultado")) { return "FINANCIAL_STATEMENTS" }
    if ($type.Contains("material") -or $type.Contains("issue") -or $type.Contains("governance") -or $name.Contains("fato relevante") -or $name.Contains("assembleia") -or $name.Contains("edital") -or $name.Contains("emissao") -or $name.Contains("emissão") -or $name.Contains("ato do administrador") -or $EventSignal -eq "True") { return "EVENT_GOVERNANCE_ISSUE" }
    if ($PortfolioSignal -eq "True") { return "PORTFOLIO_CREDIT" }
    if ($ResultSignal -eq "True") { return "RESULT" }
    if ($NavSignal -eq "True") { return "NAV_PL" }
    if ($type.Contains("monthly")) { return "MONTHLY_REPORT" }
    if ($type.Contains("quarterly")) { return "QUARTERLY_REPORT" }
    if ($type.Contains("management")) { return "MANAGEMENT_REPORT" }
    return "OTHER"
}

function Get-PeriodQuality {
    param([string]$ContentPeriods,[string]$ContentDates,[string]$ContentQuarters,[string]$ContentMonths,[string]$ManifestPeriod,[string]$DocumentYear)
    $hasContent = (-not [string]::IsNullOrWhiteSpace($ContentPeriods)) -or (-not [string]::IsNullOrWhiteSpace($ContentDates)) -or (-not [string]::IsNullOrWhiteSpace($ContentQuarters)) -or (-not [string]::IsNullOrWhiteSpace($ContentMonths))
    $hasManifest = -not [string]::IsNullOrWhiteSpace($ManifestPeriod)
    $year = 0; $validYear = [int]::TryParse((Txt $DocumentYear), [ref]$year) -and $year -ge 1900 -and $year -le 2100
    if ($hasContent) { return "CONTENT_SUPPORTED" }
    if ($hasManifest -or $validYear) { return "MANIFEST_ONLY" }
    return "NO_PERIOD_EVIDENCE"
}

function Get-PromotionDecision {
    param([string]$IdentityClass,[string]$DocumentRole,[string]$PeriodQuality,[string]$ExtractionStatus,[string]$Priority)
    if ($ExtractionStatus -ne "EXTRACTED") { return "HOLD_EXTRACTION" }
    if ($IdentityClass -eq "UNRESOLVED_IDENTITY") { return "HOLD_IDENTITY" }
    if ($PeriodQuality -eq "NO_PERIOD_EVIDENCE") { return "HOLD_PERIOD" }
    $pcip = $IdentityClass.StartsWith("PCIP11"); $cvbi = $IdentityClass.StartsWith("CVBI11"); $p = Txt $Priority
    $roles = @("DISTRIBUTION","FINANCIAL_STATEMENTS","PORTFOLIO_CREDIT","RESULT","NAV_PL","EVENT_GOVERNANCE_ISSUE")
    if ($roles -contains $DocumentRole -and ($pcip -or $cvbi)) {
        if ($PeriodQuality -eq "CONTENT_SUPPORTED") {
            if ($p -eq "P0" -or $p -eq "P1") { return "PROMOTION_CANDIDATE_HIGH" }
            return "PROMOTION_CANDIDATE"
        }
        return "REVIEW_PERIOD"
    }
    return "REVIEW"
}

Write-Host "[2/7] Classifying documents..."
$classified = New-Object System.Collections.Generic.List[object]
$counter = 0
foreach ($row in $rows) {
    $counter++
    $contentTicker = Txt $row.Content_Ticker
    $cnpjSignal = Txt $row.CNPJ_Signal
    $originalTicker = Txt $row.Original_Ticker
    $fileName = Txt $row.FileName
    $identity = Get-IdentityClass $contentTicker $cnpjSignal $originalTicker $fileName
    $role = Get-DocumentRole (Txt $row.Canonical_Type) $fileName (Txt $row.Distribution_Signal) (Txt $row.NAV_Signal) (Txt $row.Portfolio_Signal) (Txt $row.Result_Signal) (Txt $row.Event_Signal)
    $periodQuality = Get-PeriodQuality (Txt $row.Content_Periods) (Txt $row.Content_Dates) (Txt $row.Content_Quarters) (Txt $row.Content_Months) (Txt $row.Document_Period_Manifest) (Txt $row.Document_Year)
    $decision = Get-PromotionDecision $identity $role $periodQuality (Txt $row.Extraction_Status) (Txt $row.Priority)

    $flags = New-Object System.Collections.Generic.List[string]
    if ($identity -ne "UNRESOLVED_IDENTITY") { $flags.Add("IDENTITY") }
    if ($periodQuality -eq "CONTENT_SUPPORTED") { $flags.Add("PERIOD") }
    if ((Txt $row.Distribution_Signal) -eq "True") { $flags.Add("DISTRIBUTION_SIGNAL") }
    if ((Txt $row.NAV_Signal) -eq "True") { $flags.Add("NAV_SIGNAL") }
    if ((Txt $row.Portfolio_Signal) -eq "True") { $flags.Add("PORTFOLIO_SIGNAL") }
    if ((Txt $row.Result_Signal) -eq "True") { $flags.Add("RESULT_SIGNAL") }
    if ((Txt $row.Event_Signal) -eq "True") { $flags.Add("EVENT_SIGNAL") }

    $confidence = "LOW"
    if ($identity -eq "PCIP11_CONFIRMED_CNPJ" -and $periodQuality -eq "CONTENT_SUPPORTED") { $confidence = "HIGH" }
    elseif (($identity -like "PCIP11_*" -or $identity -like "CVBI11_*") -and $periodQuality -eq "CONTENT_SUPPORTED") { $confidence = "MEDIUM-HIGH" }
    elseif ($identity -ne "UNRESOLVED_IDENTITY") { $confidence = "MEDIUM" }

    $classified.Add([pscustomobject]@{
        Historical_ID=Txt $row.Historical_ID; SHA256=Txt $row.SHA256; FileName=$fileName; RelativePath=Txt $row.RelativePath; Extension=Txt $row.Extension
        Original_Ticker=$originalTicker; Content_Ticker=$contentTicker; CNPJ_Signal=$cnpjSignal; Storage_Year=Txt $row.Storage_Year; Document_Year=Txt $row.Document_Year
        Document_Period_Manifest=Txt $row.Document_Period_Manifest; Content_Periods=Txt $row.Content_Periods; Content_Dates=Txt $row.Content_Dates; Content_Quarters=Txt $row.Content_Quarters; Content_Months=Txt $row.Content_Months
        Canonical_Type=Txt $row.Canonical_Type; Priority=Txt $row.Priority; Extraction_Status=Txt $row.Extraction_Status; Text_Length=Txt $row.Text_Length
        Distribution_Signal=Txt $row.Distribution_Signal; NAV_Signal=Txt $row.NAV_Signal; Portfolio_Signal=Txt $row.Portfolio_Signal; Result_Signal=Txt $row.Result_Signal; Event_Signal=Txt $row.Event_Signal
        Identity_Class=$identity; Document_Role=$role; Period_Quality=$periodQuality; Evidence_Flags=($flags -join "|"); Confidence=$confidence; Promotion_Decision=$decision
    })
    if (($counter % 25) -eq 0) { Write-Progress -Activity "0695.3 Content classification" -Status ("Document " + $counter + " / " + $rows.Count) -PercentComplete (($counter / $rows.Count) * 100) }
}
Write-Progress -Activity "0695.3 Content classification" -Completed

Write-Host "[3/7] Saving classification matrix..."
$classified | Sort-Object Storage_Year,Identity_Class,Document_Role,Priority,FileName | Export-Csv -LiteralPath $OutputCsv -NoTypeInformation -Encoding UTF8

Write-Host "[4/7] Building evidence promotion queue..."
$queue = @($classified | Where-Object { $_.Promotion_Decision -like "PROMOTION_CANDIDATE*" })
$queue | Export-Csv -LiteralPath $QueueCsv -NoTypeInformation -Encoding UTF8

$total = $classified.Count
$pcip = @($classified | Where-Object { $_.Identity_Class -like "PCIP11_*" }).Count
$cvbi = @($classified | Where-Object { $_.Identity_Class -like "CVBI11_*" }).Count
$unresolved = @($classified | Where-Object { $_.Identity_Class -eq "UNRESOLVED_IDENTITY" }).Count
$contentPeriods = @($classified | Where-Object { $_.Period_Quality -eq "CONTENT_SUPPORTED" }).Count
$high = @($classified | Where-Object { $_.Promotion_Decision -eq "PROMOTION_CANDIDATE_HIGH" }).Count
$normal = @($classified | Where-Object { $_.Promotion_Decision -eq "PROMOTION_CANDIDATE" }).Count
$holdIdentity = @($classified | Where-Object { $_.Promotion_Decision -eq "HOLD_IDENTITY" }).Count
$holdPeriod = @($classified | Where-Object { $_.Promotion_Decision -eq "HOLD_PERIOD" }).Count
$review = @($classified | Where-Object { $_.Promotion_Decision -eq "REVIEW" }).Count
$roles = @($classified | Group-Object Document_Role | Sort-Object Name)
$identities = @($classified | Group-Object Identity_Class | Sort-Object Name)
$decisions = @($classified | Group-Object Promotion_Decision | Sort-Object Name)
$confidence = @($classified | Group-Object Confidence | Sort-Object Name)

Write-Host "[5/7] Writing reports..."
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# 0695.3 - PCIP11 Content Classification")
$lines.Add(""); $lines.Add("Status: CLASSIFICATION COMPLETED"); $lines.Add("Source: PCIP11_MULTIFORMAT_TRIAGE_0695_2R3_FIXED.csv"); $lines.Add("Period: 2024-2026"); $lines.Add("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")); $lines.Add("")
$lines.Add("## Processing"); $lines.Add(""); $lines.Add("- Input rows: " + $total); $lines.Add("- PCIP11 identity classes: " + $pcip); $lines.Add("- Historical CVBI11 classes: " + $cvbi); $lines.Add("- Unresolved identity: " + $unresolved); $lines.Add("- Content-supported period: " + $contentPeriods); $lines.Add("")
$lines.Add("## Document roles"); $lines.Add(""); foreach ($g in $roles) { $lines.Add("- " + $g.Name + ": " + $g.Count) }; $lines.Add("")
$lines.Add("## Identity classes"); $lines.Add(""); foreach ($g in $identities) { $lines.Add("- " + $g.Name + ": " + $g.Count) }; $lines.Add("")
$lines.Add("## Confidence"); $lines.Add(""); foreach ($g in $confidence) { $lines.Add("- " + $g.Name + ": " + $g.Count) }; $lines.Add("")
$lines.Add("## Promotion decisions"); $lines.Add(""); $lines.Add("- High-priority promotion candidates: " + $high); $lines.Add("- Promotion candidates: " + $normal); $lines.Add("- Hold identity: " + $holdIdentity); $lines.Add("- Hold period: " + $holdPeriod); $lines.Add("- Review: " + $review); $lines.Add(""); foreach ($g in $decisions) { $lines.Add("- " + $g.Name + ": " + $g.Count) }; $lines.Add("")
$lines.Add("## Evidence policy"); $lines.Add(""); $lines.Add("- Classification does not promote a metric."); $lines.Add("- CVBI11 historical identity is preserved."); $lines.Add("- PCIP11 identity is strengthened by CNPJ when present."); $lines.Add("- Content-derived periods are preferred over invalid manifest years."); $lines.Add("- Signals identify documents for metric-level extraction."); $lines.Add("- Promotion candidates still require metric-level evidence and source citation."); $lines.Add("")
$lines.Add("## Safety"); $lines.Add(""); $lines.Add("- No Vault note modified."); $lines.Add("- No asset note modified."); $lines.Add("- No metric promoted."); $lines.Add("- No source document modified."); $lines.Add("")
$lines.Add("## Outputs"); $lines.Add(""); $lines.Add("- Classification CSV: " + $OutputCsv); $lines.Add("- Promotion queue CSV: " + $QueueCsv); $lines.Add("- Promotion queue Markdown: " + $QueueMd); $lines.Add(""); $lines.Add("## Status"); $lines.Add(""); $lines.Add("0695.3 CONTENT CLASSIFICATION COMPLETED")
$lines | Set-Content -LiteralPath $OutputMd -Encoding UTF8

$queueLines = New-Object System.Collections.Generic.List[string]
$queueLines.Add("# PCIP11 Evidence Promotion Queue - 0695.3"); $queueLines.Add(""); $queueLines.Add("Status: QUEUE GENERATED; NO METRIC PROMOTED"); $queueLines.Add("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")); $queueLines.Add("")
$queueLines.Add("## Queue"); $queueLines.Add(""); $queueLines.Add("- High-priority candidates: " + $high); $queueLines.Add("- Other candidates: " + $normal); $queueLines.Add(""); $queueLines.Add("## Rule"); $queueLines.Add(""); $queueLines.Add("Each candidate requires metric-level extraction and source citation before promotion."); $queueLines.Add(""); $queueLines.Add("## Candidate records"); $queueLines.Add(""); $queueLines.Add("| Priority | Identity | Role | Period | Confidence | File | Decision |"); $queueLines.Add("|---|---|---|---|---|---|---|")
foreach ($item in ($queue | Sort-Object Priority,Identity_Class,Document_Role,FileName)) {
    $safeFile = ($item.FileName -replace "\|", "/")
    $queueLines.Add("| " + $item.Priority + " | " + $item.Identity_Class + " | " + $item.Document_Role + " | " + $item.Period_Quality + " | " + $item.Confidence + " | " + $safeFile + " | " + $item.Promotion_Decision + " |")
}
$queueLines | Set-Content -LiteralPath $QueueMd -Encoding UTF8

Write-Host "[6/7] Final validation..."
Write-Host ("Input rows                : " + $total)
Write-Host ("PCIP11 identity           : " + $pcip)
Write-Host ("Historical CVBI11         : " + $cvbi)
Write-Host ("Unresolved identity       : " + $unresolved)
Write-Host ("Content-supported periods : " + $contentPeriods)
Write-Host ("Promotion high            : " + $high)
Write-Host ("Promotion normal          : " + $normal)
Write-Host ("Hold identity             : " + $holdIdentity)
Write-Host ("Hold period               : " + $holdPeriod)
Write-Host ("Review                    : " + $review)
Write-Host ""
Write-Host ("Classification CSV        : " + $OutputCsv)
Write-Host ("Promotion queue CSV       : " + $QueueCsv)
Write-Host ("Promotion queue MD        : " + $QueueMd)
Write-Host ""
Write-Host "[7/7] STATUS: 0695.3 CONTENT CLASSIFICATION COMPLETED"
Write-Host "============================================================"
