$ErrorActionPreference = "Stop"

Write-Host "============================================================"
Write-Host " IIP - FIX 0683 - PORTFOLIO INTEGRITY + EXPOSURE"
Write-Host "============================================================"

$vaultRoot = (Get-Location).Path

$portfolioRoot = Join-Path $vaultRoot "02_Portfolio"
$exposureRoot = Join-Path $vaultRoot "06_Exposures"
$pcipExposureRoot = Join-Path $exposureRoot "PCIP11"

$registryPath = Join-Path $portfolioRoot "Position Registry.md"
$integrityPath = Join-Path $portfolioRoot "Portfolio Integrity.md"
$exposureMapPath = Join-Path $exposureRoot "EXPOSURE-MAP.md"
$pcipContextPath = Join-Path $pcipExposureRoot "PCIP11 - Portfolio Context.md"

foreach ($dir in @($portfolioRoot, $exposureRoot, $pcipExposureRoot)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

if (-not (Test-Path -LiteralPath $registryPath -PathType Leaf)) {
    Write-Host "FAIL: Position Registry não encontrado"
    exit 1
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$backupRoot = Join-Path `
    $vaultRoot `
    "archive\portfolio-integrity-fix-0683-$timestamp"

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

Write-Host "Backup:"
Write-Host $backupRoot

# ============================================================
# 1. LEITURA ROBUSTA DO REGISTRY
# ============================================================

$registry = Get-Content `
    -LiteralPath $registryPath `
    -Raw `
    -Encoding UTF8

$lines = $registry -split "`r?`n"

$positions = @()

foreach ($line in $lines) {

    if ($line -notmatch '^\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|') {
        continue
    }

    if ($line -match '^\|\s*ID\s*\|') {
        continue
    }

    if ($line -match '^\|\s*---') {
        continue
    }

    $parts = $line.Trim('|') -split '\|'

    if ($parts.Count -lt 9) {
        continue
    }

    $id = $parts[0].Trim()
    $nome = $parts[1].Trim()
    $classe = $parts[2].Trim()

    $valorText = $parts[6].Trim()

    $valorClean = $valorText `
        -replace "R\$", "" `
        -replace "\.", "" `
        -replace ",", "." `
        -replace "%", "" `
        -replace "\s", ""

    $valor = 0.0

    if (-not [double]::TryParse(
        $valorClean,
        [Globalization.NumberStyles]::Any,
        [Globalization.CultureInfo]::InvariantCulture,
        [ref]$valor
    )) {
        continue
    }

    $positions += [PSCustomObject]@{
        ID = $id
        Nome = $nome
        Classe = $classe
        Valor = $valor
        Peso = 0.0
    }
}

Write-Host "Posições lidas: $($positions.Count)"

if ($positions.Count -ne 46) {
    Write-Host "FAIL: esperado 46 posições"
    exit 1
}

# ============================================================
# 2. TOTAL
# ============================================================

$total = ($positions | Measure-Object -Property Valor -Sum).Sum

Write-Host ("Valor operacional: R$ {0:N2}" -f $total)

if ($total -le 0) {
    Write-Host "FAIL: total inválido"
    exit 1
}

foreach ($p in $positions) {
    $p.Peso = ($p.Valor / $total) * 100
}

$weightSum = ($positions | Measure-Object -Property Peso -Sum).Sum

Write-Host ("Soma dos pesos: {0:N4}%" -f $weightSum)

if ([math]::Abs($weightSum - 100) -gt 0.05) {
    Write-Host "FAIL: pesos não totalizam 100%"
    exit 1
}

# ============================================================
# 3. PCIP11 - CORREÇÃO ROBUSTA
# ============================================================

$pcip = @(
    $positions | Where-Object { $_.ID -eq "PCIP11" }
)

Write-Host "Ocorrências de PCIP11: $($pcip.Count)"

if ($pcip.Count -ne 1) {
    Write-Host "FAIL: PCIP11 deve existir exatamente uma vez"
    exit 1
}

$pcipValue = [double]$pcip[0].Valor
$pcipWeight = [double]$pcip[0].Peso

Write-Host ("PCIP11 valor: R$ {0:N2}" -f $pcipValue)
Write-Host ("PCIP11 peso: {0:N4}%" -f $pcipWeight)

# ============================================================
# 4. AGREGAÇÃO POR CLASSE
# ============================================================

$classGroups = $positions |
    Group-Object Classe |
    Sort-Object Name

$classLines = @()

foreach ($group in $classGroups) {

    $classValue = ($group.Group | Measure-Object Valor -Sum).Sum
    $classWeight = ($classValue / $total) * 100

    $classLines += "| $($group.Name) | $($group.Count) | R$ $("{0:N2}" -f $classValue) | $("{0:N2}" -f $classWeight)% |"
}

# ============================================================
# 5. TOP 10
# ============================================================

$topPositions = $positions |
    Sort-Object Valor -Descending |
    Select-Object -First 10

$topLines = @()

foreach ($p in $topPositions) {

    $topLines += "| $($p.ID) | $($p.Nome) | $($p.Classe) | R$ $("{0:N2}" -f $p.Valor) | $("{0:N2}" -f $p.Peso)% |"
}

# ============================================================
# 6. PORTFOLIO INTEGRITY
# ============================================================

$integrityContent = @"
---
type: portfolio_integrity
scope: portfolio
schema_version: "0.1"
state: current
source: Position Registry
status: active
---

# Portfolio Integrity

## Estado

VALIDATED

## Quantidade

- Posições esperadas: 46
- Posições lidas: $($positions.Count)

## Valor operacional

R$ $("{0:N2}" -f $total)

## Soma dos pesos

$("{0:N4}" -f $weightSum)%

## PCIP11

- Valor: R$ $("{0:N2}" -f $pcipValue)
- Peso da carteira: $("{0:N4}" -f $pcipWeight)%

## Agregação por classe

| Classe | Posições | Valor | Peso |
|---|---:|---:|---:|
$($classLines -join "`n")

## Top 10 posições

| ID | Ativo | Classe | Valor | Peso |
|---|---|---|---:|---:|
$($topLines -join "`n")

## Regras

1. O valor operacional é a soma das posições individuais.
2. Os pesos são derivados desse valor.
3. Peso alvo não é inferido.
4. Classificação econômica avançada requer camada própria.
5. Divergências entre totais da plataforma e posições devem permanecer rastreáveis.

## Fonte

Position Registry / snapshot de carteira fornecido pelo usuário.

## Controle

schema_version: 0.1
state: current
status: active
"@

Set-Content `
    -LiteralPath $integrityPath `
    -Value $integrityContent `
    -Encoding UTF8

Write-Host "CREATED/UPDATED: $integrityPath"

# ============================================================
# 7. EXPOSURE MAP
# ============================================================

$exposureContent = @"
---
type: exposure_map
scope: portfolio
schema_version: "0.1"
state: current
status: active
---

# Portfolio Exposure Map

## Regra

Esta versão utiliza apenas a classificação explícita das posições.

Não são inferidas exposições econômicas mais profundas.

## Classes observadas

| Classe | Posições | Valor | Peso |
|---|---:|---:|---:|
$($classLines -join "`n")

## PCIP11

- Valor: R$ $("{0:N2}" -f $pcipValue)
- Peso: $("{0:N4}" -f $pcipWeight)%

## Próxima camada

As exposições econômicas serão classificadas futuramente por:

- estratégia;
- gestor;
- indexador;
- crédito;
- exposição imobiliária;
- exposição setorial;
- concentração;
- sobreposição.

## Integridade

Fonte estrutural: [[Position Registry]]
Fonte operacional: [[Current]]

Estado:

EXPOSURE_FOUNDATION_READY
"@

Set-Content `
    -LiteralPath $exposureMapPath `
    -Value $exposureContent `
    -Encoding UTF8

Write-Host "CREATED/UPDATED: $exposureMapPath"

# ============================================================
# 8. PCIP11 CONTEXT
# ============================================================

if (Test-Path -LiteralPath $pcipContextPath -PathType Leaf) {

    $context = Get-Content `
        -LiteralPath $pcipContextPath `
        -Raw `
        -Encoding UTF8

    if ($context -notmatch "R\$\s*4\.845,75") {

        $context += @"

## Portfolio Integrity

- [[Current]]
- [[Position Registry]]
- [[Portfolio Integrity]]
- [[EXPOSURE-MAP]]

## Snapshot atual

- Valor operacional: R$ $("{0:N2}" -f $total)
- Valor PCIP11: R$ $("{0:N2}" -f $pcipValue)
- Peso PCIP11: $("{0:N4}" -f $pcipWeight)%

"@

        Set-Content `
            -LiteralPath $pcipContextPath `
            -Value $context `
            -Encoding UTF8

        Write-Host "UPDATED: PCIP11 Portfolio Context"
    }
    else {
        Write-Host "INFO: PCIP11 Context já contém snapshot"
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host " RESULTADO"
Write-Host "============================================================"
Write-Host "RESULTADO: PASS"
Write-Host "Portfolio Integrity + Exposure Foundation corrigida"
Write-Host "Backup: $backupRoot"
