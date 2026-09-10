$ErrorActionPreference = "Stop"

$Repo = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$InputCsv = Join-Path $Repo "reports\PCIP11_METRIC_EVIDENCE_CANDIDATES_0695_4.csv"
$OutDir = Join-Path $Repo "reports"
$OutputCsv = Join-Path $OutDir "PCIP11_EVIDENCE_VALIDATION_0695_5.csv"
$OutputMd = Join-Path $OutDir "PCIP11_EVIDENCE_VALIDATION_0695_5.md"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host ""
Write-Host "============================================================"
Write-Host "0695.5 - PCIP11 EVIDENCE VALIDATION"
Write-Host "============================================================"
Write-Host ""

Write-Host "[1/6] Loading 0695.4 evidence candidates..."
if (-not (Test-Path -LiteralPath $InputCsv)) {
    throw "Input CSV not found: $InputCsv"
}

$rows = @(Import-Csv -LiteralPath $InputCsv)
if ($rows.Count -eq 0) {
    throw "Input CSV is empty."
}

Write-Host ("Input rows: " + $rows.Count)

# Detect fields without assuming an exact schema.
$headers = @($rows[0].PSObject.Properties.Name)

function Find-Header {
    param([string[]]$Names, [string[]]$Patterns)
    foreach ($name in $Names) {
        foreach ($pattern in $Patterns) {
            if ($name -match $pattern) { return $name }
        }
    }
    return $null
}

$idHeader = Find-Header $headers @('^Historical_ID$','^Evidence_ID$','^Document_ID$','^ID$')
$fileHeader = Find-Header $headers @('^FileName$','^File_Name$','File')
$roleHeader = Find-Header $headers @('Role','Evidence_Type','Metric_Type','Category','Class')
$snippetHeader = Find-Header $headers @('Snippet','Evidence_Text','Evidence_Snippet','Quote','Text')
$periodHeader = Find-Header $headers @('Period','Content_Period','Document_Period','Date')
$identityHeader = Find-Header $headers @('Identity','Ticker','Content_Ticker')
$metricHeader = Find-Header $headers @('Metric','Metric_Name','Candidate_Metric')
$sourceHeader = Find-Header $headers @('Source','RelativePath','Path','Document')

Write-Host "[2/6] Validating schema..."
Write-Host ("Identifier field : " + $idHeader)
Write-Host ("File field       : " + $fileHeader)
Write-Host ("Role field       : " + $roleHeader)
Write-Host ("Snippet field    : " + $snippetHeader)
Write-Host ("Period field     : " + $periodHeader)
Write-Host ("Identity field   : " + $identityHeader)
Write-Host ("Metric field     : " + $metricHeader)
Write-Host ("Source field     : " + $sourceHeader)

function Get-Value {
    param([object]$Row, [string]$Header)
    if ([string]::IsNullOrWhiteSpace($Header)) { return "" }
    $p = $Row.PSObject.Properties[$Header]
    if ($null -eq $p) { return "" }
    return ([string]$p.Value).Trim()
}

function Get-RoleClass {
    param([string]$Value)
    $v = $Value.ToLowerInvariant()
    if ($v -match 'distribution|rendimento|dividend|amortiz') { return 'DISTRIBUTION' }
    if ($v -match 'nav|pl|patrimonial') { return 'NAV_PL' }
    if ($v -match 'result|dre|revenue|receita|despesa') { return 'RESULT' }
    if ($v -match 'portfolio|carteira|credit|cri') { return 'PORTFOLIO_CREDIT' }
    if ($v -match 'event|fato|assembleia|emissao|govern') { return 'EVENT' }
    return 'OTHER'
}

Write-Host "[3/6] Applying evidence rules..."

$validated = New-Object System.Collections.Generic.List[object]
$counter = 0

foreach ($row in $rows) {
    $counter++

    $id = Get-Value $row $idHeader
    $file = Get-Value $row $fileHeader
    $rawRole = Get-Value $row $roleHeader
    $snippet = Get-Value $row $snippetHeader
    $period = Get-Value $row $periodHeader
    $identity = Get-Value $row $identityHeader
    $metric = Get-Value $row $metricHeader
    $source = Get-Value $row $sourceHeader

    $role = Get-RoleClass $rawRole

    $flags = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($id)) { $flags.Add('ID') }
    if (-not [string]::IsNullOrWhiteSpace($file)) { $flags.Add('FILE') }
    if (-not [string]::IsNullOrWhiteSpace($snippet)) { $flags.Add('SNIPPET') }
    if (-not [string]::IsNullOrWhiteSpace($period)) { $flags.Add('PERIOD') }
    if (-not [string]::IsNullOrWhiteSpace($identity)) { $flags.Add('IDENTITY') }
    if (-not [string]::IsNullOrWhiteSpace($source)) { $flags.Add('SOURCE') }
    if (-not [string]::IsNullOrWhiteSpace($metric)) { $flags.Add('METRIC') }

    $decision = 'HOLD'
    $tier = 'GAP'

    # No promotion without a literal evidence snippet and source identity.
    if (-not [string]::IsNullOrWhiteSpace($snippet) -and
        -not [string]::IsNullOrWhiteSpace($source) -and
        -not [string]::IsNullOrWhiteSpace($period) -and
        -not [string]::IsNullOrWhiteSpace($identity)) {
        $tier = 'EVIDENCE_READY'
        $decision = 'REVIEW_FOR_PROMOTION'

        if ($identity -match 'PCIP11') {
            $tier = 'PCIP11_EVIDENCE_READY'
        }
        elseif ($identity -match 'CVBI11') {
            $tier = 'CVBI11_HISTORICAL_EVIDENCE_READY'
        }
    }

    if ($role -eq 'OTHER') {
        $decision = 'HOLD_ROLE'
    }

    if ($snippet.Length -lt 20 -and -not [string]::IsNullOrWhiteSpace($snippet)) {
        $decision = 'HOLD_WEAK_SNIPPET'
        $tier = 'WEAK'
    }

    $validated.Add(
        [pscustomobject]@{
            Row_Number = $counter
            Historical_ID = $id
            FileName = $file
            RelativePath = $source
            Identity = $identity
            Raw_Role = $rawRole
            Role_Class = $role
            Period = $period
            Candidate_Metric = $metric
            Evidence_Snippet = $snippet
            Evidence_Field_Present = (-not [string]::IsNullOrWhiteSpace($snippet))
            Source_Field_Present = (-not [string]::IsNullOrWhiteSpace($source))
            Period_Field_Present = (-not [string]::IsNullOrWhiteSpace($period))
            Identity_Field_Present = (-not [string]::IsNullOrWhiteSpace($identity))
            Evidence_Flags = ($flags -join '|')
            Validation_Tier = $tier
            Promotion_Decision = $decision
        }
    )
}

Write-Host "[4/6] Saving validation matrix..."
$validated |
    Sort-Object Validation_Tier, Role_Class, Identity, FileName |
    Export-Csv -LiteralPath $OutputCsv -NoTypeInformation -Encoding UTF8

Write-Host "[5/6] Building report..."

$total = $validated.Count
$ready = @($validated | Where-Object { $_.Validation_Tier -match 'EVIDENCE_READY' }).Count
$pcipReady = @($validated | Where-Object { $_.Validation_Tier -eq 'PCIP11_EVIDENCE_READY' }).Count
$cvbiReady = @($validated | Where-Object { $_.Validation_Tier -eq 'CVBI11_HISTORICAL_EVIDENCE_READY' }).Count
$weak = @($validated | Where-Object { $_.Validation_Tier -eq 'WEAK' }).Count
$gap = @($validated | Where-Object { $_.Validation_Tier -eq 'GAP' }).Count
$holdRole = @($validated | Where-Object { $_.Promotion_Decision -eq 'HOLD_ROLE' }).Count
$review = @($validated | Where-Object { $_.Promotion_Decision -eq 'REVIEW_FOR_PROMOTION' }).Count

$roleGroups = @($validated | Group-Object Role_Class | Sort-Object Name)
$tierGroups = @($validated | Group-Object Validation_Tier | Sort-Object Name)
$decisionGroups = @($validated | Group-Object Promotion_Decision | Sort-Object Name)

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('# 0695.5 - PCIP11 Evidence Validation')
$lines.Add('')
$lines.Add('Status: VALIDATION COMPLETED; NO METRIC PROMOTED')
$lines.Add('Source: PCIP11_METRIC_EVIDENCE_CANDIDATES_0695_4.csv')
$lines.Add('Generated: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
$lines.Add('')
$lines.Add('## Processing')
$lines.Add('')
$lines.Add('- Candidate evidence rows: ' + $total)
$lines.Add('- Evidence-ready rows: ' + $ready)
$lines.Add('- PCIP11 evidence-ready: ' + $pcipReady)
$lines.Add('- CVBI11 historical evidence-ready: ' + $cvbiReady)
$lines.Add('- Weak evidence: ' + $weak)
$lines.Add('- GAP: ' + $gap)
$lines.Add('')
$lines.Add('## Roles')
$lines.Add('')
foreach ($g in $roleGroups) { $lines.Add('- ' + $g.Name + ': ' + $g.Count) }
$lines.Add('')
$lines.Add('## Validation tiers')
$lines.Add('')
foreach ($g in $tierGroups) { $lines.Add('- ' + $g.Name + ': ' + $g.Count) }
$lines.Add('')
$lines.Add('## Decisions')
$lines.Add('')
foreach ($g in $decisionGroups) { $lines.Add('- ' + $g.Name + ': ' + $g.Count) }
$lines.Add('')
$lines.Add('## Promotion rule')
$lines.Add('')
$lines.Add('- A metric is not promoted merely because a document contains a signal.')
$lines.Add('- Literal evidence, source identity, period and asset identity must be available for review.')
$lines.Add('- PCIP11 and CVBI11 historical evidence remain distinct identities in the evidence layer.')
$lines.Add('- Validation creates review candidates; it does not write canonical metrics.')
$lines.Add('- Weak or incomplete evidence remains a GAP/HOLD state.')
$lines.Add('')
$lines.Add('## Safety')
$lines.Add('')
$lines.Add('- No Vault note modified.')
$lines.Add('- No asset note modified.')
$lines.Add('- No canonical metric promoted.')
$lines.Add('- No source document modified.')
$lines.Add('')
$lines.Add('## Outputs')
$lines.Add('')
$lines.Add('- Validation CSV: ' + $OutputCsv)
$lines.Add('- Validation report: ' + $OutputMd)
$lines.Add('')
$lines.Add('## Status')
$lines.Add('')
$lines.Add('0695.5 EVIDENCE VALIDATION COMPLETED')

$lines | Set-Content -LiteralPath $OutputMd -Encoding UTF8

Write-Host "[6/6] Final validation..."
Write-Host ""
Write-Host ("Evidence rows                : " + $total)
Write-Host ("Evidence-ready              : " + $ready)
Write-Host ("PCIP11 evidence-ready       : " + $pcipReady)
Write-Host ("CVBI11 historical ready     : " + $cvbiReady)
Write-Host ("Weak evidence               : " + $weak)
Write-Host ("GAP                         : " + $gap)
Write-Host ("Review for promotion        : " + $review)
Write-Host ("Hold role                   : " + $holdRole)
Write-Host ""
Write-Host ("CSV : " + $OutputCsv)
Write-Host ("MD  : " + $OutputMd)
Write-Host ""
Write-Host "STATUS: 0695.5 EVIDENCE VALIDATION COMPLETED"
Write-Host "============================================================"
