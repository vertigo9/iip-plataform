# 0695.6R4R3 - PCIP11 SEMANTIC EVIDENCE RESOLUTION
# Robust version: does not require a 6R3R1 CSV filename.
# Inputs:
#   reports\PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv
# Uses explicit CVBI11 -> PCIP11 lineage and semantic rules.
# No Vault modification. No metric promotion.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Repo = 'D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1'
$CandCsv = Join-Path $Repo 'reports\PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv'
$OutDir = Join-Path $Repo 'reports'
$OutCsv = Join-Path $OutDir 'PCIP11_SEMANTIC_RESOLUTION_0695_6R4R3.csv'
$OutMd = Join-Path $OutDir 'PCIP11_SEMANTIC_RESOLUTION_0695_6R4R3.md'

function S([object]$v) {
    if ($null -eq $v) { return '' }
    return ([string]$v).Trim()
}
function Has([object]$v) {
    return -not [string]::IsNullOrWhiteSpace((S $v))
}
function Num([string]$v) {
    if ([string]::IsNullOrWhiteSpace($v)) { return $null }
    $x = $v.Trim() -replace '\.','' -replace ',','.'
    $n = 0.0
    if ([double]::TryParse($x,[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$n)) {
        return $n
    }
    return $null
}

Write-Host ''
Write-Host '============================================================'
Write-Host '0695.6R4R3 - PCIP11 SEMANTIC EVIDENCE RESOLUTION'
Write-Host '============================================================'
Write-Host ''

if (-not (Test-Path -LiteralPath $CandCsv)) {
    throw "Missing: $CandCsv"
}

Write-Host '[1/7] Loading 0695.6R2 metric candidates...'
$cands = @(Import-Csv -LiteralPath $CandCsv)
Write-Host ("Candidates: {0}" -f $cands.Count)

if ($cands.Count -eq 0) { throw 'Candidate CSV is empty.' }

$headers = @($cands[0].PSObject.Properties.Name)
$required = @(
    'Historical_ID','SHA256','FileName','RelativePath',
    'Identity_Class','Document_Role','Metric','Value','Unit',
    'Period','Evidence_Text','Notes'
)
$missing = @($required | Where-Object { $_ -notin $headers })
if ($missing.Count -gt 0) {
    throw ("Candidate schema missing: " + ($missing -join ', '))
}
Write-Host 'Schema: PASS'

Write-Host '[2/7] Resolving CVBI11 -> PCIP11 lineage and semantic units...'

$out = New-Object System.Collections.Generic.List[object]

foreach ($r in $cands) {
    $identity = S $r.Identity_Class
    $metric = S $r.Metric
    $value = Num (S $r.Value)
    $period = S $r.Period
    $unit = S $r.Unit
    $text = S $r.Evidence_Text
    $notes = New-Object System.Collections.Generic.List[string]

    $lineage = 'PCIP11'
    if ($identity -eq 'CVBI11_HISTORICAL') {
        $lineage = 'CVBI11 -> PCIP11'
        $notes.Add('Historical predecessor ticker preserved; lineage allows continuity in the PCIP11 historical timeline.')
    }

    $resolvedUnit = $unit
    $scaleState = 'REVIEW_REQUIRED'
    $scaleConfidence = 'LOW'
    $scale = '1'

    switch -Regex ($metric) {
        '^distribution_per_share$' {
            $resolvedUnit = 'BRL/share'
            $scaleState = 'RESOLVED'
            $scaleConfidence = 'HIGH'
            break
        }
        '^net_asset_value_per_share$' {
            $resolvedUnit = 'BRL/share'
            $scaleState = 'RESOLVED'
            $scaleConfidence = 'HIGH'
            break
        }
        '^market_price_per_share$' {
            $resolvedUnit = 'BRL/share'
            $scaleState = 'RESOLVED'
            $scaleConfidence = 'HIGH'
            break
        }
        '^dividend_yield_annualized$' {
            $resolvedUnit = 'percent'
            $scaleState = 'RESOLVED'
            $scaleConfidence = 'HIGH'
            break
        }
        '^price_to_book$' {
            $resolvedUnit = 'ratio'
            $scaleState = 'RESOLVED'
            $scaleConfidence = 'HIGH'
            break
        }
        '^ltv_average$' {
            $resolvedUnit = 'percent'
            $scaleState = 'RESOLVED'
            $scaleConfidence = 'HIGH'
            break
        }
        '^weighted_average_term_years$' {
            $resolvedUnit = 'years'
            $scaleState = 'RESOLVED'
            $scaleConfidence = 'HIGH'
            break
        }
        '^weighted_average_spread$' {
            $resolvedUnit = 'percent'
            $scaleState = 'RESOLVED'
            $scaleConfidence = 'HIGH'
            break
        }
        '^total_revenue$|^operating_result$|^financial_result$|^accounting_net_income$|^distributable_net_income$|^expenses_total$' {
            $resolvedUnit = 'BRL'
            $scaleState = 'REVIEW_REQUIRED'
            $scaleConfidence = 'LOW'
            $notes.Add('Accounting-line scale unresolved; verify table scale and column before promotion.')
            break
        }
        default {
            $resolvedUnit = $unit
            $scaleState = 'REVIEW_REQUIRED'
            $scaleConfidence = 'LOW'
            $notes.Add('Metric/unit not safely auto-resolved.')
        }
    }

    $plausibility = 'PASS'

    if ($resolvedUnit -eq 'percent') {
        if ($null -eq $value -or $value -lt 0 -or $value -gt 100) {
            $plausibility = 'REVIEW_REQUIRED'
            $notes.Add('Percent value outside 0-100 range or invalid.')
        }
    }

    if ($resolvedUnit -eq 'ratio') {
        if ($null -eq $value -or $value -le 0 -or $value -gt 10) {
            $plausibility = 'REVIEW_REQUIRED'
            $notes.Add('Ratio outside conservative plausibility range.')
        }
    }

    if ($metric -eq 'distribution_per_share') {
        if ($null -eq $value -or $value -le 0 -or $value -gt 20) {
            $plausibility = 'REVIEW_REQUIRED'
            $notes.Add('Distribution/share outside conservative review range.')
        }
    }

    if ($resolvedUnit -eq 'years') {
        if ($null -eq $value -or $value -le 0 -or $value -gt 20) {
            $plausibility = 'REVIEW_REQUIRED'
            $notes.Add('Term outside conservative review range.')
        }
    }

    $status = 'MANUAL_REVIEW'
    $action = 'DO_NOT_PROMOTE_YET'

    if (
        $scaleState -eq 'RESOLVED' -and
        $plausibility -eq 'PASS' -and
        (Has $period) -and
        (Has $text) -and
        (Has $identity)
    ) {
        if ($metric -in @(
            'distribution_per_share',
            'net_asset_value_per_share',
            'market_price_per_share',
            'dividend_yield_annualized',
            'price_to_book',
            'ltv_average',
            'weighted_average_term_years',
            'weighted_average_spread'
        )) {
            $status = 'AUTO_RESOLVED_REVIEW_REQUIRED'
            $action = 'ELIGIBLE_FOR_PROMOTION_GATE'
        }
    }

    # Accounting metrics never become eligible at this stage.
    if ($metric -match '^(total_revenue|operating_result|financial_result|accounting_net_income|distributable_net_income|expenses_total)$') {
        $status = 'MANUAL_REVIEW'
        $action = 'HOLD_UNIT_SCALE'
    }

    $out.Add([pscustomobject][ordered]@{
        Historical_ID = S $r.Historical_ID
        SHA256 = S $r.SHA256
        FileName = S $r.FileName
        RelativePath = S $r.RelativePath
        Original_Identity = $identity
        Lineage = $lineage
        Document_Role = S $r.Document_Role
        Metric = $metric
        Value = if ($null -eq $value) { '' } else { $value.ToString([Globalization.CultureInfo]::InvariantCulture) }
        Original_Unit = $unit
        Resolved_Unit = $resolvedUnit
        Scale = $scale
        Scale_State = $scaleState
        Scale_Confidence = $scaleConfidence
        Period = $period
        Plausibility = $plausibility
        Resolution_Status = $status
        Promotion_Action = $action
        Evidence_Text = $text
        Notes = ($notes -join ' | ')
    })
}

Write-Host '[3/7] Detecting conflicts by lineage + metric + period...'

$grouped = @($out | Group-Object { "{0}|{1}|{2}" -f $_.Lineage,$_.Metric,$_.Period })
$conflictGroups = 0
$conflictRows = 0

foreach ($g in $grouped) {
    $vals = @(
        $g.Group |
        Where-Object { Has $_.Value } |
        Select-Object -ExpandProperty Value -Unique
    )

    if ($vals.Count -gt 1) {
        $conflictGroups++
        foreach ($x in $g.Group) {
            $x.Resolution_Status = 'MANUAL_REVIEW'
            $x.Promotion_Action = 'HOLD_CONFLICT'
            $x.Notes = ((S $x.Notes) + ' | Multiple values found for same lineage/metric/period; source context must be resolved.').Trim()
            $conflictRows++
        }
    }
}

Write-Host '[4/7] Saving semantic resolution matrix...'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$out | Export-Csv -LiteralPath $OutCsv -NoTypeInformation -Encoding UTF8

Write-Host '[5/7] Building report...'

$auto = @($out | Where-Object { $_.Resolution_Status -eq 'AUTO_RESOLVED_REVIEW_REQUIRED' }).Count
$manual = @($out | Where-Object { $_.Resolution_Status -eq 'MANUAL_REVIEW' }).Count
$eligible = @($out | Where-Object { $_.Promotion_Action -eq 'ELIGIBLE_FOR_PROMOTION_GATE' }).Count
$scaleReview = @($out | Where-Object { $_.Scale_State -eq 'REVIEW_REQUIRED' }).Count
$cvbi = @($out | Where-Object { $_.Lineage -eq 'CVBI11 -> PCIP11' }).Count
$pcip = @($out | Where-Object { $_.Lineage -eq 'PCIP11' }).Count
$holdConflict = @($out | Where-Object { $_.Promotion_Action -eq 'HOLD_CONFLICT' }).Count

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('# 0695.6R4R3 - PCIP11 Semantic Evidence Resolution')
$lines.Add('')
$lines.Add('## Control totals')
$lines.Add('')
$lines.Add(("- Candidates: {0}" -f $out.Count))
$lines.Add(("- AUTO_RESOLVED_REVIEW_REQUIRED: {0}" -f $auto))
$lines.Add(("- MANUAL_REVIEW: {0}" -f $manual))
$lines.Add(("- Eligible for promotion gate: {0}" -f $eligible))
$lines.Add(("- Unit/scale requiring review: {0}" -f $scaleReview))
$lines.Add(("- CVBI11 -> PCIP11 lineage: {0}" -f $cvbi))
$lines.Add(("- Native/current PCIP11 lineage: {0}" -f $pcip))
$lines.Add(("- Conflict/hold rows: {0}" -f $holdConflict))
$lines.Add(("- Conflict groups: {0}" -f $conflictGroups))
$lines.Add('')
$lines.Add('## Historical identity rule')
$lines.Add('')
$lines.Add('CVBI11 is preserved as original historical identity. The lineage CVBI11 -> PCIP11 enables a continuous historical timeline without relabeling source documents.')
$lines.Add('')
$lines.Add('## Promotion rule')
$lines.Add('')
$lines.Add('No canonical metric is promoted by this stage.')
$lines.Add('Accounting-line metrics remain blocked until table scale is explicitly resolved.')
$lines.Add('Eligible candidates still require the 0695.7 promotion gate.')
$lines.Add('')
$lines.Add('## Safety')
$lines.Add('')
$lines.Add('- No Vault note modified.')
$lines.Add('- No canonical metric promoted.')
$lines.Add('- SHA256 provenance preserved.')
$lines.Add('- Original ticker identity preserved.')

[System.IO.File]::WriteAllLines($OutMd, $lines, [System.Text.UTF8Encoding]::new($false))

Write-Host '[6/7] Final validation...'
if (-not (Test-Path -LiteralPath $OutCsv)) { throw 'Output CSV missing.' }
if (-not (Test-Path -LiteralPath $OutMd)) { throw 'Output MD missing.' }

Write-Host '[7/7] FINAL'
Write-Host ''
Write-Host ("Candidates                : {0}" -f $out.Count)
Write-Host ("Auto-resolved review      : {0}" -f $auto)
Write-Host ("Manual review             : {0}" -f $manual)
Write-Host ("Eligible for next gate    : {0}" -f $eligible)
Write-Host ("Unit/scale review         : {0}" -f $scaleReview)
Write-Host ("CVBI11 -> PCIP11 lineage  : {0}" -f $cvbi)
Write-Host ("Conflict/hold rows        : {0}" -f $holdConflict)
Write-Host ("Conflict groups           : {0}" -f $conflictGroups)
Write-Host ''
Write-Host 'CONTROL: NO VAULT CHANGE / NO METRIC PROMOTION'
Write-Host '============================================================'
