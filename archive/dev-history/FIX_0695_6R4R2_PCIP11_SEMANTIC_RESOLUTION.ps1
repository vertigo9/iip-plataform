# 0695.6R4 - PCIP11 SEMANTIC EVIDENCE RESOLUTION
# Uses 0695.6R2 candidates + 0695.6R3R1 audit.
# Purpose: resolve lineage, unit/scale, duplicates and safe/unsafe promotion state.
# No Vault modification. No metric promotion.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Repo = 'D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1'
$CandCsv = Join-Path $Repo 'reports\PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv'
$OutDir = Join-Path $Repo 'reports'
$AuditCsv = Join-Path $OutDir 'PCIP11_CANDIDATE_AUDIT_0695_6R3R1.csv'
$AuditCandidates = @(
    Get-ChildItem -LiteralPath $OutDir -File -Filter '*0695*6R3R1*.csv' -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'AUDIT|CANDIDATE' } |
        Sort-Object LastWriteTime -Descending
)
if(-not (Test-Path -LiteralPath $AuditCsv) -and $AuditCandidates.Count -gt 0){
    $AuditCsv = $AuditCandidates[0].FullName
}
$OutCsv = Join-Path $OutDir 'PCIP11_SEMANTIC_RESOLUTION_0695_6R4R1.csv'
$OutMd = Join-Path $OutDir 'PCIP11_SEMANTIC_RESOLUTION_0695_6R4R1.md'

function S([object]$v){ if($null -eq $v){return ''}; return ([string]$v).Trim() }
function Has([object]$v){ return -not [string]::IsNullOrWhiteSpace((S $v)) }
function Num([string]$v){
    if([string]::IsNullOrWhiteSpace($v)){ return $null }
    $x = $v.Trim() -replace '\.','' -replace ',','.'
    $n = 0.0
    if([double]::TryParse($x,[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$n)){ return $n }
    return $null
}

Write-Host ''
Write-Host '============================================================'
Write-Host '0695.6R4 - PCIP11 SEMANTIC EVIDENCE RESOLUTION'
Write-Host '============================================================'
Write-Host ''

if(!(Test-Path $CandCsv)){ throw "Missing: $CandCsv" }
if(!(Test-Path $AuditCsv)){
    Write-Host "Audit CSV not found. Proceeding without 0695.6R3R1 audit linkage."
    $AuditCsv = $null
}

Write-Host '[1/8] Loading 0695.6R2 candidates...'
$cands = @(Import-Csv $CandCsv)
Write-Host ("Candidates: {0}" -f $cands.Count)

Write-Host '[2/8] Loading 0695.6R3R1 audit when available...'
$aud = @()
if($null -ne $AuditCsv -and (Test-Path -LiteralPath $AuditCsv)){
    $aud = @(Import-Csv $AuditCsv)
}
Write-Host ("Audit rows: {0}" -f $aud.Count)

$ch = @($cands[0].PSObject.Properties.Name)
foreach($req in @('Historical_ID','SHA256','Metric','Value','Unit','Period','Identity_Class','Evidence_Text')){ if($req -notin $ch){ throw "Candidate schema missing $req" } }
if($aud.Count -gt 0){
    $ah = @($aud[0].PSObject.Properties.Name)
    if('SHA256' -notin $ah){ throw 'Audit schema missing SHA256' }
}
Write-Host 'Schema: PASS'

Write-Host '[3/8] Building audit lookup...'
$aByHash = @{}
foreach($a in $aud){ $h=S $a.SHA256; if(Has $h){$aByHash[$h]=$a} }

function Get-Context($row){
    $t = (S $row.Evidence_Text)
    if($t.Length -gt 220){ return $t.Substring(0,220) }
    return $t
}

Write-Host '[4/8] Resolving ticker lineage...'
# User-established lineage: CVBI11 is the predecessor ticker of PCIP11 after the Patria transaction.
# We preserve the original identity but add a lineage field so historical CVBI11 evidence can feed the PCIP11 timeline.

$out = New-Object System.Collections.Generic.List[object]

foreach($r in $cands){
    $h=S $r.SHA256
    $audit = if($aByHash.ContainsKey($h)){$aByHash[$h]}else{$null}
    $identity = S $r.Identity_Class
    $metric = S $r.Metric
    $unit = S $r.Unit
    $value = Num (S $r.Value)
    $period = S $r.Period
    $text = S $r.Evidence_Text
    $notes = New-Object System.Collections.Generic.List[string]

    $lineage='PCIP11'
    $identityResolved=$identity
    if($identity -eq 'CVBI11_HISTORICAL'){
        $lineage='CVBI11 -> PCIP11'
        $notes.Add('Historical predecessor ticker. Preserve original ticker in evidence; allow continuity in PCIP11 historical timeline.')
    }

    # Unit/scale resolution.
    $resolvedUnit=$unit
    $scale='1'
    $scaleConfidence='HIGH'
    $scaleState='RESOLVED'

    switch -Regex ($metric) {
        '^distribution_per_share$' { $resolvedUnit='BRL/share'; $scale='1'; break }
        '^net_asset_value_per_share$' { $resolvedUnit='BRL/share'; $scale='1'; break }
        '^market_price_per_share$' { $resolvedUnit='BRL/share'; $scale='1'; break }
        '^dividend_yield_annualized$' { $resolvedUnit='percent'; $scale='1'; break }
        '^price_to_book$' { $resolvedUnit='ratio'; $scale='1'; break }
        '^ltv_average$' { $resolvedUnit='percent'; $scale='1'; break }
        '^weighted_average_term_years$' { $resolvedUnit='years'; $scale='1'; break }
        '^weighted_average_spread$' { $resolvedUnit='percent'; $scale='1'; break }
        '^total_revenue$|^operating_result$|^financial_result$|^accounting_net_income$|^distributable_net_income$|^expenses_total$' {
            $resolvedUnit='BRL'
            $scaleState='REVIEW_REQUIRED'
            $scaleConfidence='LOW'
            $notes.Add('Accounting table scale unresolved: extracted number may be R$ million, thousand or another table scale.')
            break
        }
        default {
            $scaleState='REVIEW_REQUIRED'
            $scaleConfidence='LOW'
            $notes.Add('Metric/unit not explicitly resolved.')
        }
    }

    # Semantic plausibility rules.
    $plausibility='PASS'
    if($metric -match 'percent' -or $resolvedUnit -eq 'percent'){
        if($null -eq $value -or $value -lt 0 -or $value -gt 100){ $plausibility='REVIEW_REQUIRED'; $notes.Add('Percent value outside 0-100 range or unparsable.') }
    }
    if($resolvedUnit -eq 'ratio'){
        if($null -eq $value -or $value -le 0 -or $value -gt 10){ $plausibility='REVIEW_REQUIRED'; $notes.Add('P/B ratio outside conservative plausibility range.') }
    }
    if($resolvedUnit -eq 'BRL/share' -and $metric -eq 'distribution_per_share'){
        if($null -eq $value -or $value -le 0 -or $value -gt 20){ $plausibility='REVIEW_REQUIRED'; $notes.Add('Distribution/share outside review range.') }
    }
    if($resolvedUnit -eq 'years'){
        if($null -eq $value -or $value -le 0 -or $value -gt 20){ $plausibility='REVIEW_REQUIRED'; $notes.Add('Term outside review range.') }
    }

    $status='MANUAL_REVIEW'
    $action='DO_NOT_PROMOTE_YET'

    # Conservative auto-resolution only for unambiguous per-share/percent/ratio/time metrics with strong context.
    if($scaleState -eq 'RESOLVED' -and $plausibility -eq 'PASS' -and (Has $period) -and (Has $text) -and ($identityResolved -in @('PCIP11_IDENTITY','PCIP11_HISTORICAL','CVBI11_HISTORICAL'))){
        if($metric -in @('distribution_per_share','net_asset_value_per_share','market_price_per_share','dividend_yield_annualized','price_to_book','ltv_average','weighted_average_term_years','weighted_average_spread')){
            $status='AUTO_RESOLVED_REVIEW_REQUIRED'
            $action='ELIGIBLE_FOR_PROMOTION_GATE'
        }
    }

    if($null -ne $audit){
        $auditFlag=S $audit.Review_Flag
        if(Has $auditFlag -and $auditFlag -match 'CONFLICT'){ $status='MANUAL_REVIEW'; $action='HOLD_CONFLICT'; $notes.Add('Blocked by duplicate/conflict audit.') }
    }

    $out.Add([pscustomobject][ordered]@{
        Historical_ID=S $r.Historical_ID
        SHA256=$h
        FileName=S $r.FileName
        RelativePath=S $r.RelativePath
        Original_Identity=$identity
        Lineage=$lineage
        Document_Role=S $r.Document_Role
        Metric=$metric
        Value=if($null -eq $value){''}else{$value.ToString([Globalization.CultureInfo]::InvariantCulture)}
        Original_Unit=$unit
        Resolved_Unit=$resolvedUnit
        Scale=$scale
        Scale_State=$scaleState
        Scale_Confidence=$scaleConfidence
        Period=$period
        Plausibility=$plausibility
        Resolution_Status=$status
        Promotion_Action=$action
        Audit_Flag=if($null -eq $audit){''}else{S $audit.Review_Flag}
        Evidence_Text=$text
        Context=Get-Context $r
        Notes=($notes -join ' | ')
    })
}

Write-Host '[5/8] Detecting exact duplicate/conflict groups...'
$groups = @($out | Group-Object { "{0}|{1}|{2}" -f $_.Lineage,$_.Metric,$_.Period })
$conflictCount=0
foreach($g in $groups){
    $vals=@($g.Group | Where-Object {Has $_.Value} | Select-Object -ExpandProperty Value -Unique)
    if($vals.Count -gt 1){
        $conflictCount++
        foreach($x in $g.Group){
            $x.Resolution_Status='MANUAL_REVIEW'
            $x.Promotion_Action='HOLD_CONFLICT'
            $x.Notes = ((S $x.Notes) + ' | Same lineage/metric/period has multiple values; resolve source context.').Trim(' ','|')
        }
    }
}

Write-Host '[6/8] Saving resolution matrix...'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$out | Export-Csv $OutCsv -NoTypeInformation -Encoding UTF8

Write-Host '[7/8] Building report...'
$auto=@($out | Where-Object {$_.Resolution_Status -eq 'AUTO_RESOLVED_REVIEW_REQUIRED'}).Count
$manual=@($out | Where-Object {$_.Resolution_Status -eq 'MANUAL_REVIEW'}).Count
$eligible=@($out | Where-Object {$_.Promotion_Action -eq 'ELIGIBLE_FOR_PROMOTION_GATE'}).Count
$scaleReview=@($out | Where-Object {$_.Scale_State -eq 'REVIEW_REQUIRED'}).Count
$cvbi=@($out | Where-Object {$_.Lineage -eq 'CVBI11 -> PCIP11'}).Count
$pcip=@($out | Where-Object {$_.Lineage -eq 'PCIP11'}).Count
$conflicts=@($out | Where-Object {$_.Promotion_Action -eq 'HOLD_CONFLICT'}).Count

$lines=New-Object System.Collections.Generic.List[string]
$lines.Add('# 0695.6R4 - PCIP11 Semantic Evidence Resolution')
$lines.Add('')
$lines.Add('## Control totals')
$lines.Add('')
$lines.Add(("- Candidates: {0}" -f $out.Count))
$lines.Add(("- AUTO_RESOLVED_REVIEW_REQUIRED: {0}" -f $auto))
$lines.Add(("- MANUAL_REVIEW: {0}" -f $manual))
$lines.Add(("- Eligible for promotion gate: {0}" -f $eligible))
$lines.Add(("- Unit/scale still requiring review: {0}" -f $scaleReview))
$lines.Add(("- CVBI11 -> PCIP11 lineage: {0}" -f $cvbi))
$lines.Add(("- Native/current PCIP11 lineage: {0}" -f $pcip))
$lines.Add(("- Conflict/hold candidates: {0}" -f $conflicts))
$lines.Add(("- Conflict groups detected: {0}" -f $conflictCount))
$lines.Add('')
$lines.Add('## Lineage rule')
$lines.Add('')
$lines.Add('CVBI11 historical identity is preserved as the predecessor ticker of PCIP11 for historical continuity. Evidence is not relabeled at source level; lineage is explicit.')
$lines.Add('')
$lines.Add('## Promotion rule')
$lines.Add('')
$lines.Add('No metric is promoted here. Accounting-line metrics remain blocked until table scale is explicitly resolved.')
$lines.Add('Per-share, percent, ratio and term candidates may become eligible for the next promotion gate only after this resolution stage.')
$lines.Add('')
$lines.Add('## Safety')
$lines.Add('')
$lines.Add('- No Vault note modified.')
$lines.Add('- No canonical metric promoted.')
$lines.Add('- Original identity preserved.')
$lines.Add('- SHA256 provenance preserved.')
$lines.Add('')
$lines.Add('CSV: ' + $OutCsv)
[System.IO.File]::WriteAllLines($OutMd,$lines,[System.Text.UTF8Encoding]::new($false))

Write-Host '[8/8] FINAL'
Write-Host ''
Write-Host ("Candidates                : {0}" -f $out.Count)
Write-Host ("Auto-resolved review      : {0}" -f $auto)
Write-Host ("Manual review             : {0}" -f $manual)
Write-Host ("Eligible for next gate    : {0}" -f $eligible)
Write-Host ("Unit/scale review         : {0}" -f $scaleReview)
Write-Host ("CVBI11 -> PCIP11 lineage  : {0}" -f $cvbi)
Write-Host ("Conflict/hold             : {0}" -f $conflicts)
Write-Host ''
Write-Host 'CONTROL: NO VAULT CHANGE / NO METRIC PROMOTION'
Write-Host '============================================================'
