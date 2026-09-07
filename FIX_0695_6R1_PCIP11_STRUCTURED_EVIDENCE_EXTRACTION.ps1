Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = (Get-Location).Path
$Input = Join-Path $Root 'reports\PCIP11_EVIDENCE_VALIDATION_0695_5R2.csv'
$OutCsv = Join-Path $Root 'reports\PCIP11_STRUCTURED_EVIDENCE_0695_6R1.csv'
$OutMd = Join-Path $Root 'reports\PCIP11_STRUCTURED_EVIDENCE_0695_6R1.md'
$CandCsv = Join-Path $Root 'reports\PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R1.csv'
$CandMd = Join-Path $Root 'reports\PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R1.md'

Write-Host ''
Write-Host '============================================================'
Write-Host '0695.6R1 - PCIP11 STRUCTURED EVIDENCE EXTRACTION'
Write-Host '============================================================'
Write-Host ''

if (-not (Test-Path -LiteralPath $Input)) { throw "Input not found: $Input" }

Write-Host '[1/7] Loading 0695.5R2 validation...'
$rows = @(Import-Csv -LiteralPath $Input)
Write-Host ("Input rows: {0}" -f $rows.Count)

$headers = @($rows[0].PSObject.Properties.Name)
$required = @(
    'Historical_ID','SHA256','FileName','RelativePath','Identity_Class','Document_Role',
    'Content_Periods','Period_Quality','Confidence','Extraction_Status','Text_Length',
    'Evidence_Types','Evidence_Type_Count','Identity_Pass','Period_Pass','Text_Pass',
    'Evidence_Field_Pass','Role_Pass','Validation_Class','Ready_Class','Validation_Reason',
    'Promotion_Status'
)
$missing = @($required | Where-Object { $_ -notin $headers })
if ($missing.Count -gt 0) { throw ('0695.5R2 schema mismatch. Missing: ' + ($missing -join ', ')) }
Write-Host 'Schema: PASS'

function S([object]$v) {
    if ($null -eq $v) { return '' }
    return ([string]$v).Trim()
}

function Normalize-Number([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
    $v = $Value.Trim()
    $v = $v -replace '[()]',''
    $v = $v -replace '\.',''
    $v = $v -replace ',','.'
    $num = 0.0
    if ([double]::TryParse($v,[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$num)) { return $num }
    return $null
}

function Get-Period([string]$ContentPeriods,[string]$Text) {
    $p = ''
    if ($ContentPeriods -match 'MONTH:(\d{4}-\d{2})') { $p = $Matches[1] }
    elseif ($ContentPeriods -match 'QUARTER:(\d{4}-T[1-4])') { $p = $Matches[1] }
    elseif ($ContentPeriods -match 'YEAR:(\d{4})') { $p = $Matches[1] }
    elseif ($Text -match '(?i)\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z-]*-?(\d{2,4})\b') {
        $map = @{JAN='01';FEB='02';MAR='03';APR='04';MAY='05';JUN='06';JUL='07';AUG='08';SEP='09';OCT='10';NOV='11';DEC='12'}
        $m = $Matches[0].Substring(0,3).ToUpper()
        $y = $Matches[1]
        if ($y.Length -eq 2) { $y = '20' + $y }
        $p = $y + '-' + $map[$m]
    }
    return $p
}

function Add-Rec($r,$Category,$Metric,$Unit,$Value,$Period,$Evidence,$Method,$Status,$Notes) {
    $v = ''
    if ($null -ne $Value) { $v = $Value.ToString([Globalization.CultureInfo]::InvariantCulture) }
    [pscustomobject][ordered]@{
        Historical_ID = S $r.Historical_ID
        SHA256 = S $r.SHA256
        FileName = S $r.FileName
        RelativePath = S $r.RelativePath
        Identity_Class = S $r.Identity_Class
        Document_Role = S $r.Document_Role
        Period = S $Period
        Period_Quality = S $r.Period_Quality
        Confidence = S $r.Confidence
        Category = $Category
        Metric = $Metric
        Value = $v
        Unit = $Unit
        Status = $Status
        Evidence_Text = (S $Evidence)
        Extraction_Method = $Method
        Source_File = S $r.FileName
        Source_Path = S $r.RelativePath
        Notes = $Notes
    }
}

function Extract-FromEvidence($r,$Category,$Evidence,$Out) {
    $text = S $Evidence
    if ([string]::IsNullOrWhiteSpace($text)) { return }
    $period = Get-Period (S $r.Content_Periods) $text

    $patterns = @()
    switch ($Category) {
        'DISTRIBUTION' {
            $patterns = @(
                @{M='distribution_per_share';U='BRL/share';R='(?i)distribu[ií]d[oa].{0,100}?R\$\s*([0-9]+(?:[,.][0-9]+)?)\s*/\s*cota'},
                @{M='dividend_per_share';U='BRL/share';R='(?i)dividendo\s+por\s+cota.{0,80}?R\$\s*([0-9]+(?:[,.][0-9]+)?)'},
                @{M='distribution_yield_annualized';U='percent';R='(?i)Dividend\s+Yield\s+anualizado.{0,70}?([0-9]+(?:[,.][0-9]+)?)\s*%'},
                @{M='reserve_per_share';U='BRL/share';R='(?i)reserva.{0,100}?R\$\s*([0-9]+(?:[,.][0-9]+)?)\s*/\s*cota'}
            )
        }
        'NAV_PL' {
            $patterns = @(
                @{M='net_asset_value_total';U='BRL';R='(?i)Patrim[oô]nio\s+L[ií]quido\s+R\$\s*([0-9]+(?:[.,][0-9]+)?)\s*(milh[oõ]es|milhões)'},
                @{M='net_asset_value_per_share';U='BRL/share';R='(?i)Patrim[oô]nio\s+L[ií]quido.{0,100}?R\$\s*([0-9]+(?:[.,][0-9]+)?)\s*/\s*cota'},
                @{M='market_value_total';U='BRL';R='(?i)Valor\s+de\s+Mercado\s+R\$\s*([0-9]+(?:[.,][0-9]+)?)\s*(milh[oõ]es|milhões)'},
                @{M='market_value_per_share';U='BRL/share';R='(?i)Valor\s+de\s+Mercado.{0,100}?R\$\s*([0-9]+(?:[.,][0-9]+)?)\s*/\s*cota'},
                @{M='price_to_book';U='ratio';R='(?i)Price\s+to\s+book.{0,20}?([0-9]+(?:[.,][0-9]+)?)\s*x'}
            )
        }
        'RESULT' {
            $patterns = @(
                @{M='total_revenue';U='R$ million or R$ thousand';R='(?i)(?:Receita|Receitas)\s*[-–]\s*Total\s+(-?\(?[0-9]+(?:[.,][0-9]+)?\)?)'},
                @{M='operating_result';U='R$ million or R$ thousand';R='(?i)Resultado\s+Operacional\s+(-?\(?[0-9]+(?:[.,][0-9]+)?\)?)'},
                @{M='net_financial_result';U='R$ million or R$ thousand';R='(?i)Resultado\s+Financeiro\s+L[ií]quido\s+(-?\(?[0-9]+(?:[.,][0-9]+)?\)?)'},
                @{M='accounting_net_income';U='R$ million or R$ thousand';R='(?i)Lucro\s+L[ií]quido\s+Cont[aá]bil\s+(-?\(?[0-9]+(?:[.,][0-9]+)?\)?)'},
                @{M='distributable_net_income';U='R$ million or R$ thousand';R='(?i)Lucro\s+L[ií]quido\s+Distribu[ií]vel\s+(-?\(?[0-9]+(?:[.,][0-9]+)?\)?)'},
                @{M='total_expenses';U='R$ million or R$ thousand';R='(?i)Despesas\s*[-–]\s*Total\s+(-?\(?[0-9]+(?:[.,][0-9]+)?\)?)'}
            )
        }
        'PORTFOLIO_CREDIT' {
            $patterns = @(
                @{M='spread_target';U='percent';R='(?i)Spread\s+alvo.{0,50}?([0-9]+(?:[.,][0-9]+)?)\s*%\s*a\.a\.'},
                @{M='average_ltv';U='percent';R='(?i)LTV\s+m[eé]dio.{0,30}?([0-9]+(?:[.,][0-9]+)?)\s*%'},
                @{M='average_term_years';U='years';R='(?i)prazo\s+m[eé]dio.{0,40}?([0-9]+(?:[.,][0-9]+)?)\s*anos'},
                @{M='average_spread';U='percent';R='(?i)spread\s+m[eé]dio.{0,40}?([0-9]+(?:[.,][0-9]+)?)\s*%'},
                @{M='ipca_linked_share';U='percent';R='(?i)([0-9]+(?:[.,][0-9]+)?)\s*%\s+da\s+carteira.{0,40}?indexados\s+ao\s+IPCA'},
                @{M='cdi_linked_share';U='percent';R='(?i)([0-9]+(?:[.,][0-9]+)?)\s*%\s+indexados\s+ao\s+CDI'}
            )
        }
    }

    $matched = $false
    foreach ($p in $patterns) {
        $m = [regex]::Match($text,$p.R)
        if ($m.Success) {
            $val = Normalize-Number $m.Groups[1].Value
            if ($null -ne $val) {
                if ($p.M -eq 'net_asset_value_total' -or $p.M -eq 'market_value_total') { $val = $val * 1000000 }
                $Out.Add((Add-Rec $r $Category $p.M $p.U $val $period $text 'semantic_regex' 'REVIEW_REQUIRED' 'Candidate only. Verify exact table/header, scale and period before promotion.'))
                $matched = $true
            }
        }
    }

    if (-not $matched -and $Category -ne 'EVENT') {
        $Out.Add((Add-Rec $r $Category 'UNSTRUCTURED_EVIDENCE' 'text' $null $period $text 'evidence_block_preservation' 'HOLD' 'Evidence preserved because no safe semantic metric parser matched.'))
    }
}

Write-Host '[2/7] Selecting only 0695.5R2 evidence-ready rows...'
$ready = @($rows | Where-Object {
    (S $_.Ready_Class) -match 'EVIDENCE_READY' -and
    (S $_.Promotion_Status) -eq 'NOT_PROMOTED'
})
Write-Host ("Evidence-ready rows: {0}" -f $ready.Count)
if ($ready.Count -eq 0) { throw 'No rows classified as evidence-ready by 0695.5R2.' }

Write-Host '[3/7] Extracting metric candidates from evidence types...'
$structured = New-Object System.Collections.Generic.List[object]
$categories = @('DISTRIBUTION','NAV_PL','RESULT','PORTFOLIO_CREDIT','EVENT')

foreach ($r in $ready) {
    foreach ($cat in $categories) {
        if ((S $r.Evidence_Types) -match [regex]::Escape($cat)) {
            $sourceField = switch ($cat) {
                'DISTRIBUTION' {'DISTRIBUTION'}
                'NAV_PL' {'NAV_PL'}
                'RESULT' {'RESULT'}
                'PORTFOLIO_CREDIT' {'PORTFOLIO_CREDIT'}
                'EVENT' {'EVENT'}
            }
            # 0695.5R2 intentionally does not carry evidence text blocks; use the 0695.4 source CSV for text.
            # This preserves the validation layer as an independent gate.
        }
    }
}

$SourceCand = Join-Path $Root 'reports\PCIP11_METRIC_EVIDENCE_CANDIDATES_0695_4.csv'
if (-not (Test-Path -LiteralPath $SourceCand)) { throw "Source candidates missing: $SourceCand" }
$sourceRows = @(Import-Csv -LiteralPath $SourceCand)
$bySha = @{}
foreach ($s in $sourceRows) { if (-not $bySha.ContainsKey((S $s.SHA256))) { $bySha[(S $s.SHA256)] = $s } }

foreach ($r in $ready) {
    $sha = S $r.SHA256
    if (-not $bySha.ContainsKey($sha)) {
        $structured.Add((Add-Rec $r 'SYSTEM' 'SOURCE_ROW_NOT_FOUND' 'text' $null '' '' 'join_by_sha256' 'GAP' 'Validated row has no matching 0695.4 source row by SHA256.'))
        continue
    }
    $s = $bySha[$sha]
    foreach ($cat in $categories) {
        $field = switch ($cat) {
            'DISTRIBUTION' {'Distribution_Evidence'}
            'NAV_PL' {'NAV_PL_Evidence'}
            'RESULT' {'Result_Evidence'}
            'PORTFOLIO_CREDIT' {'Portfolio_Credit_Evidence'}
            'EVENT' {'Event_Evidence'}
        }
        if ((S $r.Evidence_Types) -match [regex]::Escape($cat)) {
            Extract-FromEvidence $r $cat $s.$field $structured
        }
    }
}

# Deduplicate exact same source/metric/value/unit/period/category.
$unique = @{}
foreach ($x in $structured) {
    $key = '{0}|{1}|{2}|{3}|{4}|{5}' -f $x.SHA256,$x.Category,$x.Metric,$x.Value,$x.Unit,$x.Period
    if (-not $unique.ContainsKey($key)) { $unique[$key] = $x }
}
$structuredFinal = @($unique.Values)
$metricCandidates = @($structuredFinal | Where-Object { $_.Metric -ne 'UNSTRUCTURED_EVIDENCE' -and $_.Metric -notlike 'SOURCE_ROW_*' -and $_.Status -eq 'REVIEW_REQUIRED' })

Write-Host '[4/7] Saving structured evidence and promotion candidates...'
$structuredFinal | Sort-Object FileName,Category,Metric | Export-Csv -LiteralPath $OutCsv -NoTypeInformation -Encoding UTF8
$metricCandidates | Sort-Object FileName,Category,Metric | Export-Csv -LiteralPath $CandCsv -NoTypeInformation -Encoding UTF8

Write-Host '[5/7] Building reports...'
$metricGroups = @($metricCandidates | Group-Object Metric | Sort-Object Count -Descending)
$catGroups = @($metricCandidates | Group-Object Category | Sort-Object Count -Descending)
$holdCount = @($structuredFinal | Where-Object {$_.Status -eq 'HOLD'}).Count
$gapCount = @($structuredFinal | Where-Object {$_.Status -eq 'GAP'}).Count

$md = New-Object System.Collections.Generic.List[string]
$md.Add('# 0695.6R1 - PCIP11 Structured Evidence Extraction')
$md.Add('')
$md.Add('Status: extraction only; NO metric promotion; NO Vault modification.')
$md.Add('')
$md.Add('## Control totals')
$md.Add('')
$md.Add(('- 0695.5R2 evidence-ready rows: {0}' -f $ready.Count))
$md.Add(('- Structured evidence rows: {0}' -f $structuredFinal.Count))
$md.Add(('- Metric promotion candidates: {0}' -f $metricCandidates.Count))
$md.Add(('- HOLD/unstructured evidence rows: {0}' -f $holdCount))
$md.Add(('- GAP rows: {0}' -f $gapCount))
$md.Add('')
$md.Add('## Candidate distribution by metric')
$md.Add('')
$md.Add('| Metric | Count |')
$md.Add('|---|---:|')
foreach ($g in $metricGroups) { $md.Add('| {0} | {1} |' -f $g.Name,$g.Count) }
$md.Add('')
$md.Add('## Candidate distribution by category')
$md.Add('')
$md.Add('| Category | Count |')
$md.Add('|---|---:|')
foreach ($g in $catGroups) { $md.Add('| {0} | {1} |' -f $g.Name,$g.Count) }
$md.Add('')
$md.Add('## Safety controls')
$md.Add('')
$md.Add('- No Vault note modified.')
$md.Add('- No asset note modified.')
$md.Add('- No canonical metric promoted.')
$md.Add('- All candidates remain REVIEW_REQUIRED.')
$md.Add('- Source evidence is preserved by SHA256 join to 0695.4.')
$md.Add('- Unit scale and exact table context remain subject to the next gate.')
[System.IO.File]::WriteAllLines($OutMd,$md,[Text.UTF8Encoding]::new($false))

$candMd = New-Object System.Collections.Generic.List[string]
$candMd.Add('# 0695.6R1 - Metric Promotion Candidates')
$candMd.Add('')
$candMd.Add('Review candidates only. No promotion performed.')
$candMd.Add('')
$candMd.Add('| File | Identity | Metric | Value | Unit | Period | Category | Status |')
$candMd.Add('|---|---|---|---:|---|---|---|---|')
foreach ($x in ($metricCandidates | Select-Object -First 250)) {
    $candMd.Add('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} |' -f (($x.FileName -replace '\|','/')), $x.Identity_Class,$x.Metric,$x.Value,$x.Unit,$x.Period,$x.Category,$x.Status)
}
if ($metricCandidates.Count -gt 250) { $candMd.Add(''); $candMd.Add(('First 250 of {0} candidates shown; CSV contains all.' -f $metricCandidates.Count)) }
[System.IO.File]::WriteAllLines($CandMd,$candMd,[Text.UTF8Encoding]::new($false))

Write-Host '[6/7] Final validation...'
foreach ($p in @($OutCsv,$OutMd,$CandCsv,$CandMd)) { if (-not (Test-Path -LiteralPath $p)) { throw "Output not created: $p" } }
if ($metricCandidates.Count -eq 0) { throw 'No safe metric candidates extracted. Stop before promotion.' }

Write-Host '[7/7] STATUS: 0695.6R1 COMPLETED'
Write-Host ''
Write-Host ("0695.5R2 evidence-ready rows : {0}" -f $ready.Count)
Write-Host ("Structured evidence rows      : {0}" -f $structuredFinal.Count)
Write-Host ("Metric candidates             : {0}" -f $metricCandidates.Count)
Write-Host ("HOLD/unstructured             : {0}" -f $holdCount)
Write-Host ("GAP                           : {0}" -f $gapCount)
Write-Host ''
Write-Host "CSV : $OutCsv"
Write-Host "MD  : $OutMd"
Write-Host "CSV : $CandCsv"
Write-Host "MD  : $CandMd"
Write-Host ''
Write-Host 'CONTROL: No Vault or Metric Registry promotion performed.'
Write-Host '============================================================'
