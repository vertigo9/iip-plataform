Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Repo = 'D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1'
$CandCsv = Join-Path $Repo 'reports\PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv'
$AuditCsv = Join-Path $Repo 'reports\PCIP11_METRIC_CANDIDATE_AUDIT_0695_6R3R1.csv'
$OutDir = Join-Path $Repo 'reports'
$OutCsv = Join-Path $OutDir 'PCIP11_SEMANTIC_RESOLUTION_0695_6R4R4.csv'
$OutMd = Join-Path $OutDir 'PCIP11_SEMANTIC_RESOLUTION_0695_6R4R4.md'
$ConflictCsv = Join-Path $OutDir 'PCIP11_SEMANTIC_CONFLICTS_0695_6R4R4.csv'

function S([object]$v){ if($null -eq $v){ return '' }; return ([string]$v).Trim() }
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
Write-Host '0695.6R4R4 - PCIP11 SEMANTIC EVIDENCE RESOLUTION'
Write-Host '============================================================'
Write-Host ''

if(!(Test-Path -LiteralPath $CandCsv)){ throw "Missing: $CandCsv" }

Write-Host '[1/8] Loading 0695.6R2 candidates...'
$cands = @(Import-Csv -LiteralPath $CandCsv)
Write-Host ("Candidates: {0}" -f $cands.Count)
if($cands.Count -eq 0){ throw 'Candidate CSV is empty.' }

Write-Host '[2/8] Loading optional 0695.6R3R1 audit...'
$aud = @()
if(Test-Path -LiteralPath $AuditCsv){
    $aud = @(Import-Csv -LiteralPath $AuditCsv)
}
Write-Host ("Audit rows: {0}" -f $aud.Count)

Write-Host '[3/8] Schema and evidence lineage setup...'
$headers = @($cands[0].PSObject.Properties.Name)
$required = @('Historical_ID','SHA256','FileName','RelativePath','Identity_Class','Document_Role','Metric','Value','Unit','Period','Evidence_Text')
$missing = @($required | Where-Object { $_ -notin $headers })
if($missing.Count -gt 0){ throw ('Candidate schema missing: ' + ($missing -join ', ')) }

$aByHash = @{}
foreach($a in $aud){ $h=S $a.SHA256; if(Has $h){ $aByHash[$h]=$a } }

Write-Host '[4/8] Resolving lineage, units, and plausibility...'
$out = New-Object System.Collections.Generic.List[object]

foreach($r in $cands){
    $identity = S $r.Identity_Class
    $metric = S $r.Metric
    $value = Num (S $r.Value)
    $period = S $r.Period
    $unit = S $r.Unit
    $text = S $r.Evidence_Text
    $lineage = if($identity -eq 'CVBI11_HISTORICAL'){'CVBI11 -> PCIP11'}else{'PCIP11'}
    $notes = New-Object System.Collections.Generic.List[string]
    if($identity -eq 'CVBI11_HISTORICAL'){
        $notes.Add('Historical predecessor ticker preserved; lineage CVBI11 -> PCIP11.')
    }

    $resolvedUnit = $unit
    $scale = '1'
    $scaleState = 'REVIEW_REQUIRED'
    $scaleConfidence = 'LOW'

    switch -Regex ($metric) {
        '^distribution_per_share$' { $resolvedUnit='BRL/share'; $scaleState='RESOLVED'; $scaleConfidence='HIGH'; break }
        '^net_asset_value_per_share$' { $resolvedUnit='BRL/share'; $scaleState='RESOLVED'; $scaleConfidence='HIGH'; break }
        '^market_price_per_share$' { $resolvedUnit='BRL/share'; $scaleState='RESOLVED'; $scaleConfidence='HIGH'; break }
        '^dividend_yield_annualized$' { $resolvedUnit='percent'; $scaleState='RESOLVED'; $scaleConfidence='HIGH'; break }
        '^price_to_book$' { $resolvedUnit='ratio'; $scaleState='RESOLVED'; $scaleConfidence='HIGH'; break }
        '^ltv_average$' { $resolvedUnit='percent'; $scaleState='RESOLVED'; $scaleConfidence='HIGH'; break }
        '^weighted_average_term_years$' { $resolvedUnit='years'; $scaleState='RESOLVED'; $scaleConfidence='HIGH'; break }
        '^weighted_average_spread$' { $resolvedUnit='percent'; $scaleState='RESOLVED'; $scaleConfidence='HIGH'; break }
        '^(total_revenue|operating_result|financial_result|accounting_net_income|distributable_net_income|expenses_total)$' {
            $resolvedUnit='BRL'; $scaleState='REVIEW_REQUIRED'; $scaleConfidence='LOW'
            $notes.Add('Accounting scale unresolved; table column/scale must be reviewed.')
            break
        }
        default { $notes.Add('Metric/unit not safely auto-resolved.') }
    }

    $plausibility='PASS'
    if($resolvedUnit -eq 'percent' -and ($null -eq $value -or $value -lt 0 -or $value -gt 100)){
        $plausibility='REVIEW_REQUIRED'; $notes.Add('Percent outside 0-100 range.')
    }
    if($resolvedUnit -eq 'ratio' -and ($null -eq $value -or $value -le 0 -or $value -gt 10)){
        $plausibility='REVIEW_REQUIRED'; $notes.Add('Ratio outside conservative range.')
    }
    if($metric -eq 'distribution_per_share' -and ($null -eq $value -or $value -le 0 -or $value -gt 20)){
        $plausibility='REVIEW_REQUIRED'; $notes.Add('Distribution/share outside conservative range.')
    }
    if($resolvedUnit -eq 'years' -and ($null -eq $value -or $value -le 0 -or $value -gt 20)){
        $plausibility='REVIEW_REQUIRED'; $notes.Add('Term outside conservative range.')
    }

    $status='MANUAL_REVIEW'
    $action='DO_NOT_PROMOTE_YET'
    if($scaleState -eq 'RESOLVED' -and $plausibility -eq 'PASS' -and (Has $period) -and (Has $text) -and (Has $identity)){
        if($metric -in @('distribution_per_share','net_asset_value_per_share','market_price_per_share','dividend_yield_annualized','price_to_book','ltv_average','weighted_average_term_years','weighted_average_spread')){
            $status='AUTO_RESOLVED_REVIEW_REQUIRED'
            $action='ELIGIBLE_FOR_PROMOTION_GATE'
        }
    }

    if($metric -match '^(total_revenue|operating_result|financial_result|accounting_net_income|distributable_net_income|expenses_total)$'){
        $status='MANUAL_REVIEW'
        $action='HOLD_UNIT_SCALE'
    }

    $auditFlag=''
    if($aByHash.ContainsKey((S $r.SHA256))){ $auditFlag=S $aByHash[(S $r.SHA256)].Review_Flag }

    $out.Add([pscustomobject][ordered]@{
        Historical_ID=S $r.Historical_ID
        SHA256=S $r.SHA256
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
        Audit_Flag=$auditFlag
        Evidence_Text=$text
        Notes=($notes -join ' | ')
    })
}

Write-Host '[5/8] Conservative conflict detection...'
# Important correction:
# A differing value across separate reports is NOT automatically a conflict.
# A conflict requires the same lineage + metric + period + normalized unit,
# and at least two distinct documents whose evidence explicitly anchors the same period.
# To avoid false conflicts from mixed monthly/12M tables, we only block when the
# candidate evidence itself contains a direct period anchor matching the candidate period.

$periodStrong = @{}
foreach($r in $out){
    $t=S $r.Evidence_Text
    $p=S $r.Period
    $strong=$false
    if(Has $p){
        $ym = $p -match '^20\d{2}-\d{2}$'
        if($ym){
            $year=$p.Substring(0,4); $month=$p.Substring(5,2)
            $strong = $t -match ([regex]::Escape($year) + '.{0,40}' + [regex]::Escape($month)) -or
                      $t -match ('(?i)\b' + @{'01'='jan';'02'='fev|feb';'03'='mar';'04'='abr|apr';'05'='mai|may';'06'='jun';'07'='jul';'08'='ago|aug';'09'='set|sep';'10'='out|oct';'11'='nov';'12'='dez|dec'}[$month] + '.{0,8}' + $year.Substring(2))
        }
    }
    $periodStrong[$r.Historical_ID] = $strong
}

$conflictRows = New-Object System.Collections.Generic.List[object]
$conflictGroups = 0

$groups = @($out | Where-Object { $periodStrong[$_.Historical_ID] -eq $true } | Group-Object { "{0}|{1}|{2}|{3}" -f $_.Lineage,$_.Metric,$_.Period,$_.Resolved_Unit })
foreach($g in $groups){
    $docs=@($g.Group | Select-Object -ExpandProperty SHA256 -Unique)
    $vals=@($g.Group | Where-Object { Has $_.Value } | Select-Object -ExpandProperty Value -Unique)
    if($docs.Count -gt 1 -and $vals.Count -gt 1){
        $conflictGroups++
        foreach($x in $g.Group){
            $x.Resolution_Status='MANUAL_REVIEW'
            $x.Promotion_Action='HOLD_CONFLICT'
            $x.Notes=((S $x.Notes)+' | Confirmed same-lineage/same-metric/same-period conflict across distinct documents.').Trim()
            $conflictRows.Add([pscustomobject][ordered]@{
                Lineage=$x.Lineage
                Metric=$x.Metric
                Period=$x.Period
                Unit=$x.Resolved_Unit
                SHA256=$x.SHA256
                FileName=$x.FileName
                Value=$x.Value
                Document_Role=$x.Document_Role
            })
        }
    }
}

Write-Host '[6/8] Saving matrices...'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$out | Export-Csv -LiteralPath $OutCsv -NoTypeInformation -Encoding UTF8
$conflictRows | Export-Csv -LiteralPath $ConflictCsv -NoTypeInformation -Encoding UTF8

Write-Host '[7/8] Building report...'
$auto=@($out | Where-Object {$_.Resolution_Status -eq 'AUTO_RESOLVED_REVIEW_REQUIRED'}).Count
$manual=@($out | Where-Object {$_.Resolution_Status -eq 'MANUAL_REVIEW'}).Count
$eligible=@($out | Where-Object {$_.Promotion_Action -eq 'ELIGIBLE_FOR_PROMOTION_GATE'}).Count
$scaleReview=@($out | Where-Object {$_.Scale_State -eq 'REVIEW_REQUIRED'}).Count
$cvbi=@($out | Where-Object {$_.Lineage -eq 'CVBI11 -> PCIP11'}).Count
$pcip=@($out | Where-Object {$_.Lineage -eq 'PCIP11'}).Count
$holds=@($out | Where-Object {$_.Promotion_Action -eq 'HOLD_CONFLICT'}).Count

$lines=New-Object System.Collections.Generic.List[string]
$lines.Add('# 0695.6R4R4 - PCIP11 Semantic Evidence Resolution')
$lines.Add('')
$lines.Add('## Control totals')
$lines.Add('')
$lines.Add(("- Candidates: {0}" -f $out.Count))
$lines.Add(("- Auto-resolved review: {0}" -f $auto))
$lines.Add(("- Manual review: {0}" -f $manual))
$lines.Add(("- Eligible for promotion gate: {0}" -f $eligible))
$lines.Add(("- Unit/scale review: {0}" -f $scaleReview))
$lines.Add(("- CVBI11 -> PCIP11 lineage: {0}" -f $cvbi))
$lines.Add(("- Native/current PCIP11 lineage: {0}" -f $pcip))
$lines.Add(("- Confirmed conflict/hold rows: {0}" -f $holds))
$lines.Add(("- Confirmed conflict groups: {0}" -f $conflictGroups))
$lines.Add('')
$lines.Add('## Conflict policy')
$lines.Add('')
$lines.Add('Different values across reports are not automatically conflicts. A conflict requires same lineage, same metric, same period, same normalized unit, distinct documents and explicit period anchoring in the evidence.')
$lines.Add('')
$lines.Add('## Historical lineage')
$lines.Add('')
$lines.Add('CVBI11 remains the original historical identity and is linked to PCIP11 through explicit lineage CVBI11 -> PCIP11. Source documents are not relabeled.')
$lines.Add('')
$lines.Add('## Promotion safety')
$lines.Add('')
$lines.Add('No Vault note modified. No canonical metric promoted. Accounting scale remains blocked until source table context resolves the unit scale.')
$lines.Add('')
$lines.Add('CSV: ' + $OutCsv)
$lines.Add('Conflict CSV: ' + $ConflictCsv)
[System.IO.File]::WriteAllLines($OutMd,$lines,[System.Text.UTF8Encoding]::new($false))

Write-Host '[8/8] FINAL'
Write-Host ''
Write-Host ("Candidates                : {0}" -f $out.Count)
Write-Host ("Auto-resolved review      : {0}" -f $auto)
Write-Host ("Manual review             : {0}" -f $manual)
Write-Host ("Eligible for next gate    : {0}" -f $eligible)
Write-Host ("Unit/scale review         : {0}" -f $scaleReview)
Write-Host ("CVBI11 -> PCIP11 lineage  : {0}" -f $cvbi)
Write-Host ("Confirmed conflict/hold   : {0}" -f $holds)
Write-Host ("Confirmed conflict groups : {0}" -f $conflictGroups)
Write-Host ''
Write-Host 'CONTROL: NO VAULT CHANGE / NO METRIC PROMOTION'
Write-Host '============================================================'
