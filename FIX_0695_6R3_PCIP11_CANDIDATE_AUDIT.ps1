# 0695.6R3 - PCIP11 CANDIDATE AUDIT
# Reads 0695.6R2 metric candidates and performs quality controls only.
# No Vault changes. No metric promotion.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repo = 'D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1'
$Input = Join-Path $Repo 'reports\PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv'
$OutDir = Join-Path $Repo 'reports'
$OutCsv = Join-Path $OutDir 'PCIP11_METRIC_CANDIDATE_AUDIT_0695_6R3.csv'
$OutMd = Join-Path $OutDir 'PCIP11_METRIC_CANDIDATE_AUDIT_0695_6R3.md'
function S([object]$v){ if($null -eq $v){return ''}; return ([string]$v).Trim() }
Write-Host ''
Write-Host '============================================================'
Write-Host '0695.6R3 - PCIP11 CANDIDATE AUDIT'
Write-Host '============================================================'
Write-Host ''
Write-Host '[1/7] Loading 0695.6R2 candidates...'
if(-not(Test-Path -LiteralPath $Input)){throw "Input not found: $Input"}
$rows=@(Import-Csv -LiteralPath $Input)
Write-Host ("Rows: {0}" -f $rows.Count)
if($rows.Count -eq 0){throw 'Candidate CSV is empty.'}
Write-Host '[2/7] Schema validation...'
$required=@('Historical_ID','SHA256','FileName','RelativePath','Identity_Class','Document_Role','Metric','Value','Unit','Period','Source_Category','Status','Promotion_Action','Evidence_Text')
$headers=@($rows[0].PSObject.Properties.Name)
$missing=@($required|Where-Object{$_ -notin $headers})
if($missing.Count -gt 0){throw ('Missing fields: '+($missing -join ', '))}
Write-Host 'Schema: PASS'
Write-Host '[3/7] Running semantic controls...'
$out=New-Object System.Collections.Generic.List[object]
foreach($r in $rows){
    $issues=New-Object System.Collections.Generic.List[string]
    $valueText=S $r.Value
    $value=0.0
    $hasValue=[double]::TryParse($valueText,[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$value)
    $identity=S $r.Identity_Class
    $metric=S $r.Metric
    $unit=S $r.Unit
    $period=S $r.Period
    $evidence=S $r.Evidence_Text
    if([string]::IsNullOrWhiteSpace($identity)){$issues.Add('MISSING_IDENTITY')}
    if([string]::IsNullOrWhiteSpace($period)){$issues.Add('MISSING_PERIOD')}
    if([string]::IsNullOrWhiteSpace($evidence)){$issues.Add('MISSING_EVIDENCE')}
    if(-not $hasValue){$issues.Add('NON_NUMERIC_VALUE')}
    if($metric -eq 'UNSTRUCTURED_EVIDENCE'){$issues.Add('UNSTRUCTURED')}
    if($unit -eq 'table_value_pending_unit_scale'){$issues.Add('UNIT_SCALE_PENDING')}
    if($metric -in @('price_to_book')){if($hasValue -and ($value -le 0 -or $value -gt 10)){$issues.Add('Plausibility_PB')}}
    if($metric -in @('dividend_yield_annualized','ltv_average','weighted_average_spread')){if($hasValue -and ($value -lt 0 -or $value -gt 100)){$issues.Add('Plausibility_PERCENT')}}
    if($metric -eq 'weighted_average_term_years'){if($hasValue -and ($value -le 0 -or $value -gt 30)){$issues.Add('Plausibility_TERM')}}
    if($metric -eq 'distribution_per_share'){if($hasValue -and ($value -le 0 -or $value -gt 20)){$issues.Add('Plausibility_DISTRIBUTION')}}
    if($metric -match '(_total$|_result$|income|revenue|expenses)' -and $unit -eq 'table_value_pending_unit_scale'){$issues.Add('ACCOUNTING_SCALE_REVIEW')}
    if($identity -eq 'CVBI11_HISTORICAL'){$issues.Add('HISTORICAL_CVBI11')}
    $class='PASS_REVIEW'
    if($issues.Count -gt 0){$class='REVIEW_FLAGS'}
    $out.Add([pscustomobject][ordered]@{
        Historical_ID=S $r.Historical_ID; SHA256=S $r.SHA256; FileName=S $r.FileName; RelativePath=S $r.RelativePath;
        Identity_Class=$identity; Document_Role=S $r.Document_Role; Metric=$metric; Value=$valueText; Unit=$unit; Period=$period;
        Source_Category=S $r.Source_Category; Audit_Class=$class; Issue_Flags=($issues -join '|'); Promotion_Action='DO_NOT_PROMOTE_YET'; Evidence_Text=$evidence
    })
}
Write-Host '[4/7] Detecting conflicting duplicate values...'
$conflicts=New-Object System.Collections.Generic.HashSet[string]
$groups=$out|Group-Object SHA256,Metric,Period
foreach($g in $groups){
    $vals=@($g.Group|ForEach-Object{$_.Value}|Sort-Object -Unique)
    if($vals.Count -gt 1){[void]$conflicts.Add($g.Name)}
}
foreach($r in $out){
    $key='{0}, {1}, {2}' -f $r.SHA256,$r.Metric,$r.Period
    if($conflicts.Contains($key)){ $r.Audit_Class='REVIEW_FLAGS'; if([string]::IsNullOrWhiteSpace($r.Issue_Flags)){$r.Issue_Flags='CONFLICTING_VALUES'}else{$r.Issue_Flags+='|CONFLICTING_VALUES'} }
}
Write-Host '[5/7] Saving audit matrix...'
$out|Export-Csv -LiteralPath $OutCsv -NoTypeInformation -Encoding UTF8
Write-Host '[6/7] Building report...'
$flagged=@($out|Where-Object{$_.Audit_Class -eq 'REVIEW_FLAGS'})
$pass=@($out|Where-Object{$_.Audit_Class -eq 'PASS_REVIEW'})
$pb=@($out|Where-Object{$_.Issue_Flags -match 'Plausibility_PB'}).Count
$pct=@($out|Where-Object{$_.Issue_Flags -match 'Plausibility_PERCENT'}).Count
$term=@($out|Where-Object{$_.Issue_Flags -match 'Plausibility_TERM'}).Count
$dist=@($out|Where-Object{$_.Issue_Flags -match 'Plausibility_DISTRIBUTION'}).Count
$scale=@($out|Where-Object{$_.Issue_Flags -match 'UNIT_SCALE_PENDING|ACCOUNTING_SCALE_REVIEW'}).Count
$missingPeriod=@($out|Where-Object{$_.Issue_Flags -match 'MISSING_PERIOD'}).Count
$cvbi=@($out|Where-Object{$_.Issue_Flags -match 'HISTORICAL_CVBI11'}).Count
$md=New-Object System.Collections.Generic.List[string]
$md.Add('# 0695.6R3 - PCIP11 Candidate Audit'); $md.Add('');
$md.Add(('- Candidates audited: {0}' -f $out.Count));
$md.Add(('- PASS_REVIEW: {0}' -f $pass.Count));
$md.Add(('- REVIEW_FLAGS: {0}' -f $flagged.Count));
$md.Add(('- Conflicting-value groups: {0}' -f $conflicts.Count));
$md.Add(('- Missing period: {0}' -f $missingPeriod));
$md.Add(('- Unit/scale review: {0}' -f $scale));
$md.Add(('- CVBI11 historical candidates: {0}' -f $cvbi));
$md.Add(('- PB plausibility flags: {0}' -f $pb));
$md.Add(('- Percent plausibility flags: {0}' -f $pct));
$md.Add(('- Term plausibility flags: {0}' -f $term));
$md.Add(('- Distribution plausibility flags: {0}' -f $dist)); $md.Add('');
$md.Add('## Promotion control'); $md.Add('');
$md.Add('No metric is promoted by 0695.6R3. This stage only audits candidate quality.');
$md.Add('Candidates with unit scale, period, identity or conflicting-value issues remain blocked.'); $md.Add('');
$md.Add('## Outputs'); $md.Add('');
$md.Add('- CSV: '+$OutCsv); $md.Add('- MD: '+$OutMd)
[IO.File]::WriteAllLines($OutMd,$md,[Text.UTF8Encoding]::new($false))
Write-Host '[7/7] FINAL'
Write-Host ("Candidates audited      : {0}" -f $out.Count)
Write-Host ("PASS_REVIEW             : {0}" -f $pass.Count)
Write-Host ("REVIEW_FLAGS            : {0}" -f $flagged.Count)
Write-Host ("Conflict groups         : {0}" -f $conflicts.Count)
Write-Host ("Unit/scale review       : {0}" -f $scale)
Write-Host ("Missing period          : {0}" -f $missingPeriod)
Write-Host ("CVBI11 historical       : {0}" -f $cvbi)
Write-Host ''
Write-Host 'CONTROL: NO VAULT CHANGE / NO METRIC PROMOTION'
Write-Host '============================================================'
