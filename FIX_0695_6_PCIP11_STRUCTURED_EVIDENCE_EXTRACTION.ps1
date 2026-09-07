# 0695.6 - PCIP11 STRUCTURED EVIDENCE EXTRACTION
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = (Get-Location).Path
$Input = Join-Path $Root 'reports\PCIP11_EVIDENCE_VALIDATION_0695_5R2.csv'
$OutCsv = Join-Path $Root 'reports\PCIP11_STRUCTURED_EVIDENCE_0695_6.csv'
$OutMd = Join-Path $Root 'reports\PCIP11_STRUCTURED_EVIDENCE_0695_6.md'
$CandCsv = Join-Path $Root 'reports\PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6.csv'
$CandMd = Join-Path $Root 'reports\PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6.md'

Write-Host ''
Write-Host '============================================================'
Write-Host '0695.6 - PCIP11 STRUCTURED EVIDENCE EXTRACTION'
Write-Host '============================================================'
Write-Host ''
if (-not (Test-Path -LiteralPath $Input)) { throw "Input not found: $Input" }

Write-Host '[1/7] Loading 0695.5R2 validation...'
$rows = @(Import-Csv -LiteralPath $Input)
Write-Host (('Input rows: {0}') -f $rows.Count)

function Clean-Text { param([AllowNull()][string]$Text); if ([string]::IsNullOrWhiteSpace($Text)) { return '' }; return (($Text -replace '\s+',' ').Trim()) }
function Normalize-Number { param([AllowNull()][string]$Value); if ([string]::IsNullOrWhiteSpace($Value)) { return $null }; $v=$Value.Trim() -replace '\.','' -replace ',','.'; $n=0.0; if ([double]::TryParse($v,[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$n)) { return $n }; return $null }
function Get-Period { param([string]$ContentPeriods,[string]$Evidence)
  $p=''
  if ($ContentPeriods -match 'MONTH:(\d{4}-\d{2})') { $p=$Matches[1] }
  elseif ($ContentPeriods -match 'QUARTER:(\d{4}-T[1-4])') { $p=$Matches[1] }
  elseif ($ContentPeriods -match 'YEAR:(\d{4})') { $p=$Matches[1] }
  if ($Evidence -match '(?i)\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z-]*-?(\d{2,4})\b') { $map=@{JAN='01';FEB='02';MAR='03';APR='04';MAY='05';JUN='06';JUL='07';AUG='08';SEP='09';OCT='10';NOV='11';DEC='12'}; $y=$Matches[2]; if($y.Length -eq 2){$y="20$y"}; $p="$y-$($map[$Matches[1].Substring(0,3).ToUpper()])" }
  return $p
}
function Add-EvidenceRecord { param($SourceRow,[string]$Category,[string]$Metric,[string]$Unit,[AllowNull()][double]$Value,[string]$Period,[string]$Evidence,[string]$Method,[string]$Candidate='REVIEW_REQUIRED',[string]$Notes='')
  $e=Clean-Text $Evidence; $valueText=if($null -eq $Value){''}else{$Value.ToString([Globalization.CultureInfo]::InvariantCulture)}
  return [pscustomobject][ordered]@{Historical_ID=$SourceRow.Historical_ID;SHA256=$SourceRow.SHA256;FileName=$SourceRow.FileName;RelativePath=$SourceRow.RelativePath;Identity_Class=$SourceRow.Identity_Class;Document_Role=$SourceRow.Document_Role;Content_Periods=$SourceRow.Content_Periods;Period_Quality=$SourceRow.Period_Quality;Confidence=$SourceRow.Confidence;Category=$Category;Metric=$Metric;Value=$valueText;Unit=$Unit;Period=$Period;Extraction_Method=$Method;Promotion_Decision=$Candidate;Evidence_Text=$e;Source_File=$SourceRow.FileName;Source_Path=$SourceRow.RelativePath;Notes=$Notes}
}
function Emit-MetricMatches { param($SourceRow,[string]$Category,[string]$Evidence,[string]$Period,$Output)
  $text=Clean-Text $Evidence; if([string]::IsNullOrWhiteSpace($text)){return}
  $patterns=@(
    @{Metric='distribution_per_share';Unit='BRL/share';Rx='(?i)(?:foi\s+)?distribu[ií]d[oa].{0,80}?R\$\s*([0-9]+(?:[,.][0-9]+)?)\s*/\s*cota'},
    @{Metric='distribution_per_share';Unit='BRL/share';Rx='(?i)dividendo\s+por\s+cota.{0,80}?R\$\s*([0-9]+(?:[,.][0-9]+)?)'},
    @{Metric='distribution_per_share';Unit='BRL/share';Rx='(?i)rendimento\s+distribu[ií]do\s*\(R\$/cota\).{0,120}?([0-9]+(?:[,.][0-9]+)?)'},
    @{Metric='reserve_per_share';Unit='BRL/share';Rx='(?i)reserva.{0,80}?R\$\s*([0-9]+(?:[,.][0-9]+)?)\s*/\s*cota'},
    @{Metric='dividend_yield_annualized';Unit='percent';Rx='(?i)Dividend\s+Yield\s+anualizado.{0,60}?([0-9]+(?:[,.][0-9]+)?)\s*%'},
    @{Metric='net_asset_value_per_share';Unit='BRL/share';Rx='(?i)Patrim[oô]nio\s+L[ií]quido.{0,100}?R\$\s*([0-9]+(?:[.,][0-9]+)?)\s*/\s*cota'},
    @{Metric='market_price_per_share';Unit='BRL/share';Rx='(?i)Valor\s+de\s+Mercado.{0,110}?R\$\s*([0-9]+(?:[.,][0-9]+)?)\s*/\s*cota'},
    @{Metric='price_to_book';Unit='ratio';Rx='(?i)(?:Price\s+to\s+book|P/?B).{0,30}?([0-9]+(?:[.,][0-9]+)?)\s*x'},
    @{Metric='portfolio_spread_target';Unit='percent';Rx='(?i)Spread\s+alvo.{0,50}?([0-9]+(?:[.,][0-9]+)?)\s*%\s*a\.a\.'},
    @{Metric='ltv_average';Unit='percent';Rx='(?i)LTV\s+m[eé]dio.{0,20}?([0-9]+(?:[.,][0-9]+)?)\s*%'},
    @{Metric='weighted_average_term_years';Unit='years';Rx='(?i)prazo\s+m[eé]dio.{0,30}?([0-9]+(?:[.,][0-9]+)?)\s*anos'},
    @{Metric='weighted_average_spread';Unit='percent';Rx='(?i)spread\s+m[eé]dio.{0,30}?([0-9]+(?:[.,][0-9]+)?)\s*%'}
  )
  foreach($p in $patterns){$m=[regex]::Match($text,$p.Rx);if($m.Success){$v=Normalize-Number $m.Groups[1].Value;if($null -ne $v){$Output.Add((Add-EvidenceRecord $SourceRow $Category $p.Metric $p.Unit $v $Period $text 'regex_semantic_anchor' 'REVIEW_REQUIRED' 'Candidate only. Verify exact table/header context, scale and period before promotion.'))}}}
  $resultPatterns=@(
    @{Metric='total_revenue';Unit='BRL';Rx='(?i)(?:Receita|Receitas)\s*[-–]\s*Total\s+(-?\(?[0-9]+(?:[.,][0-9]+)?\)?)'},
    @{Metric='operating_result';Unit='BRL';Rx='(?i)Resultado\s+Operacional\s+(-?\(?[0-9]+(?:[.,][0-9]+)?\)?)'},
    @{Metric='financial_result';Unit='BRL';Rx='(?i)Resultado\s+Financeiro\s+L[ií]quido\s+(-?\(?[0-9]+(?:[.,][0-9]+)?\)?)'},
    @{Metric='accounting_net_income';Unit='BRL';Rx='(?i)Lucro\s+L[ií]quido\s+Cont[aá]bil\s+(-?\(?[0-9]+(?:[.,][0-9]+)?\)?)'},
    @{Metric='distributable_net_income';Unit='BRL';Rx='(?i)Lucro\s+L[ií]quido\s+Distribu[ií]vel\s+(-?\(?[0-9]+(?:[.,][0-9]+)?\)?)'},
    @{Metric='expenses_total';Unit='BRL';Rx='(?i)Despesas\s*[-–]\s*Total\s+(-?\(?[0-9]+(?:[.,][0-9]+)?\)?)'}
  )
  foreach($p in $resultPatterns){$m=[regex]::Match($text,$p.Rx);if($m.Success){$raw=$m.Groups[1].Value;$neg=$raw -match '^\('; $v=Normalize-Number ($raw -replace '[()]','');if($null -ne $v){if($neg){$v=-1*$v};$Output.Add((Add-EvidenceRecord $SourceRow $Category $p.Metric $p.Unit $v $Period $text 'regex_semantic_anchor' 'REVIEW_REQUIRED' 'Result candidate. Verify whether source column is R$ million, R$ thousand or per share.'))}}}
}

Write-Host '[2/7] Selecting evidence-ready rows...'
$ready=@($rows|Where-Object{$_.Period_Quality -eq 'CONTENT_SUPPORTED' -and $_.Extraction_Status -eq 'EXTRACTED' -and -not [string]::IsNullOrWhiteSpace($_.Identity_Class) -and ((-not [string]::IsNullOrWhiteSpace($_.Distribution_Evidence)) -or (-not [string]::IsNullOrWhiteSpace($_.NAV_PL_Evidence)) -or (-not [string]::IsNullOrWhiteSpace($_.Result_Evidence)) -or (-not [string]::IsNullOrWhiteSpace($_.Portfolio_Credit_Evidence)) -or (-not [string]::IsNullOrWhiteSpace($_.Event_Evidence)))})
Write-Host (('Evidence-ready rows selected: {0}') -f $ready.Count)

Write-Host '[3/7] Extracting structured metric candidates...'
$structured=New-Object System.Collections.Generic.List[object]
$map=@(@{Category='DISTRIBUTION';Field='Distribution_Evidence'},@{Category='NAV_PL';Field='NAV_PL_Evidence'},@{Category='RESULT';Field='Result_Evidence'},@{Category='PORTFOLIO_CREDIT';Field='Portfolio_Credit_Evidence'},@{Category='EVENT';Field='Event_Evidence'})
foreach($row in $ready){$period=Get-Period $row.Content_Periods '';foreach($item in $map){$e=$row.($item.Field);if(-not [string]::IsNullOrWhiteSpace($e)){ $before=$structured.Count; Emit-MetricMatches $row $item.Category $e $period $structured; if($structured.Count -eq $before){$structured.Add((Add-EvidenceRecord $row $item.Category 'UNSTRUCTURED_EVIDENCE' 'text' $null $period $e 'evidence_block_preservation' 'HOLD' 'Evidence preserved for manual semantic extraction; no safe parser matched.'))}}}}

$unique=@{}
foreach($r in $structured){if($r.Metric -eq 'UNSTRUCTURED_EVIDENCE'){continue};$k="{0}|{1}|{2}|{3}|{4}|{5}" -f $r.SHA256,$r.Category,$r.Metric,$r.Period,$r.Value,$r.Unit;if(-not $unique.ContainsKey($k)){$unique[$k]=$r}}
$metricCandidates=New-Object System.Collections.Generic.List[object]
foreach($r in $unique.Values){$metricCandidates.Add([pscustomobject][ordered]@{Historical_ID=$r.Historical_ID;SHA256=$r.SHA256;FileName=$r.FileName;RelativePath=$r.RelativePath;Identity_Class=$r.Identity_Class;Document_Role=$r.Document_Role;Metric=$r.Metric;Value=$r.Value;Unit=$r.Unit;Period=$r.Period;Category=$r.Category;Confidence=$r.Confidence;Status='PROMOTION_CANDIDATE_REVIEW';Promotion_Action='DO_NOT_PROMOTE_YET';Evidence_Text=$r.Evidence_Text;Extraction_Method=$r.Extraction_Method;Notes=$r.Notes})}

Write-Host '[4/7] Saving structured evidence matrix...'
$dir=Split-Path -Parent $OutCsv;if(-not(Test-Path $dir)){New-Item -ItemType Directory -Path $dir|Out-Null}
$structured|Export-Csv -LiteralPath $OutCsv -NoTypeInformation -Encoding UTF8
$metricCandidates|Export-Csv -LiteralPath $CandCsv -NoTypeInformation -Encoding UTF8

Write-Host '[5/7] Building reports...'
$pcip=@($ready|Where-Object{$_.Identity_Class -match '^PCIP11_'})
$cvbi=@($ready|Where-Object{$_.Identity_Class -eq 'CVBI11_HISTORICAL'})
$hold=@($structured|Where-Object{$_.Promotion_Decision -eq 'HOLD'})
$byMetric=@($metricCandidates|Group-Object Metric|Sort-Object Count -Descending)
$byCat=@($metricCandidates|Group-Object Category|Sort-Object Count -Descending)
$md=New-Object System.Collections.Generic.List[string]
$md.Add('# 0695.6 - PCIP11 Structured Evidence Extraction');$md.Add('');$md.Add('Status: extraction completed without Vault promotion.');$md.Add('');$md.Add('## Control totals');$md.Add('');$md.Add((('- Evidence-ready input rows: {0}') -f $ready.Count));$md.Add((('- PCIP11-ready rows: {0}') -f $pcip.Count));$md.Add((('- CVBI11 historical rows: {0}') -f $cvbi.Count));$md.Add((('- Structured evidence rows: {0}') -f $structured.Count));$md.Add((('- Metric candidates: {0}') -f $metricCandidates.Count));$md.Add((('- HOLD/unstructured rows: {0}') -f $hold.Count));$md.Add('');$md.Add('## Metric candidate distribution');$md.Add('');$md.Add('| Metric | Candidates |');$md.Add('|---|---:|');foreach($g in $byMetric){$md.Add(('| {0} | {1} |' -f $g.Name,$g.Count))};$md.Add('');$md.Add('## Category distribution');$md.Add('');$md.Add('| Category | Candidates |');$md.Add('|---|---:|');foreach($g in $byCat){$md.Add(('| {0} | {1} |' -f $g.Name,$g.Count))};$md.Add('');$md.Add('## Promotion control');$md.Add('');$md.Add('All metric candidates are REVIEW_ONLY. No Vault file or Metric Registry file is modified.');$md.Add('Each candidate retains source file, path, period, identity and raw evidence text.');$md.Add('');$md.Add('## Next gate');$md.Add('');$md.Add('Validate semantics, unit scale, exact period, table/header context, duplicate consistency and provenance before promotion.');$md.Add('Never interpolate missing periods.')
[System.IO.File]::WriteAllLines($OutMd,$md,[System.Text.UTF8Encoding]::new($false))
$cand=New-Object System.Collections.Generic.List[string];$cand.Add('# 0695.6 - Metric Promotion Candidates');$cand.Add('');$cand.Add('Review candidates only. No promotion performed.');$cand.Add('');$cand.Add('| Identity | Metric | Value | Unit | Period | Category | Status |');$cand.Add('|---|---|---:|---|---|---|---|');foreach($r in ($metricCandidates|Select-Object -First 200)){$cand.Add(('| {0} | {1} | {2} | {3} | {4} | {5} | {6} |' -f $r.Identity_Class,($r.Metric -replace '\|','/'),$r.Value,$r.Unit,$r.Period,$r.Category,$r.Status))};if($metricCandidates.Count -gt 200){$cand.Add('');$cand.Add((('Showing first 200 of {0} candidates. Full CSV contains all candidates.') -f $metricCandidates.Count))}
[System.IO.File]::WriteAllLines($CandMd,$cand,[System.Text.UTF8Encoding]::new($false))

Write-Host '[6/7] Final validation...'
foreach($p in @($OutCsv,$OutMd,$CandCsv,$CandMd)){if(-not(Test-Path $p)){throw "Output missing: $p"}}
if($metricCandidates.Count -lt 1){throw 'No metric candidates extracted. Stop before promotion.'}
Write-Host '[7/7] 0695.6 COMPLETED'
Write-Host (('Evidence-ready rows     : {0}') -f $ready.Count)
Write-Host (('Structured evidence     : {0}') -f $structured.Count)
Write-Host (('Metric candidates       : {0}') -f $metricCandidates.Count)
Write-Host (('HOLD/unstructured       : {0}') -f $hold.Count)
Write-Host (('PCIP11 input rows       : {0}') -f $pcip.Count)
Write-Host (('CVBI11 historical rows  : {0}') -f $cvbi.Count)
Write-Host ''
Write-Host "CSV : $OutCsv"
Write-Host "MD  : $OutMd"
Write-Host "CSV : $CandCsv"
Write-Host "MD  : $CandMd"
Write-Host ''
Write-Host 'CONTROL: No Vault or Metric Registry promotion performed.'
Write-Host '============================================================'
