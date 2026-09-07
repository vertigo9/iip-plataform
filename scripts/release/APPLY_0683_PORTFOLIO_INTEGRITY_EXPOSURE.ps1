$ErrorActionPreference = "Stop"

Write-Host "============================================================"
Write-Host " IIP - PORTFOLIO INTEGRITY + EXPOSURE FOUNDATION v0.1"
Write-Host "============================================================"

$vaultRoot = (Get-Location).Path
$portfolioRoot = Join-Path $vaultRoot "02_Portfolio"
$exposureRoot = Join-Path $vaultRoot "06_Exposures"
$pcipExposureRoot = Join-Path $exposureRoot "PCIP11"

$currentPath = Join-Path $portfolioRoot "Current.md"
$registryPath = Join-Path $portfolioRoot "Position Registry.md"
$integrityPath = Join-Path $portfolioRoot "Portfolio Integrity.md"
$exposureMapPath = Join-Path $exposureRoot "EXPOSURE-MAP.md"

foreach ($dir in @($portfolioRoot, $exposureRoot, $pcipExposureRoot)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

if (-not (Test-Path -LiteralPath $currentPath -PathType Leaf)) {
    Write-Host "FAIL: Current.md não encontrado"
    exit 1
}

if (-not (Test-Path -LiteralPath $registryPath -PathType Leaf)) {
    Write-Host "FAIL: Position Registry.md não encontrado"
    exit 1
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$backupRoot = Join-Path `
    $vaultRoot `
    "archive\portfolio-integrity-pre-v0.1-$timestamp"

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

Write-Host ""
Write-Host "Backup:"
Write-Host $backupRoot

foreach ($path in @($integrityPath, $exposureMapPath)) {

    if (Test-Path -LiteralPath $path -PathType Leaf) {

        Copy-Item `
            -LiteralPath $path `
            -Destination (Join-Path $backupRoot (Split-Path $path -Leaf)) `
            -Force
    }
}

# ============================================================
# 1. LEITURA DO POSITION REGISTRY
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
    $quantidadeText = $parts[3].Trim()
    $pmText = $parts[4].Trim()
    $precoText = $parts[5].Trim()
    $valorText = $parts[6].Trim()
    $pesoText = $parts[7].Trim()

    $valor = 0.0

    $valorClean = $valorText `
        -replace "R\$", "" `
        -replace "\.", "" `
        -replace ",", "." `
        -replace "%", "" `
        -replace "\s", ""

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

Write-Host ""
Write-Host "Posições lidas do Registry: $($positions.Count)"

if ($positions.Count -ne 46) {
    Write-Host "FAIL: esperado 46 posições"
    exit 1
}

# ============================================================
# 2. TOTAL OPERACIONAL
# ============================================================

$total = ($positions | Measure-Object -Property Valor -Sum).Sum

Write-Host ""
Write-Host ("Valor operacional recalculado: R$ {0:N2}" -f $total)

if ($total -le 0) {
    Write-Host "FAIL: total operacional inválido"
    exit 1
}

# ============================================================
# 3. PESOS
# ============================================================

foreach ($p in $positions) {
    $p.Peso = ($p.Valor / $total) * 100
}

$weightSum = ($positions | Measure-Object -Property Peso -Sum).Sum

Write-Host ("Soma dos pesos: {0:N4}%" -f $weightSum)

if ([math]::Abs($weightSum - 100) -gt 0.05) {
    Write-Host "FAIL: soma dos pesos fora da tolerância"
    exit 1
}

# ============================================================
# 4. CONFERÊNCIA ESPECÍFICA DO PCIP11
# ============================================================

$pcip = $positions |
    Where-Object { $_.ID -eq "PCIP11" }

if ($pcip.Count -ne 1) {
    Write-Host "FAIL: PCIP11 não encontrado exatamente uma vez"
    exit 1
}

$pcipWeight = $pcip.Peso
$pcipValue = $pcip.Valor

Write-Host ""
Write-Host ("PCIP11 valor: R$ {0:N2}" -f $pcipValue)
Write-Host ("PCIP11 peso: {0:N4}%" -f $pcipWeight)

# ============================================================
# 5. AGREGAÇÃO POR CLASSE
# ============================================================

$classGroups = $positions |
    Group-Object Classe |
    Sort-Object Name

$classLines = @()

foreach ($group in $classGroups) {

    $classValue = ($group.Group | Measure-Object -Property Valor -Sum).Sum
    $classWeight = ($classValue / $total) * 100

    $classLines += "| $($group.Name) | $($group.Count) | R$ $("{0:N2}" -f $classValue) | $("{0:N2}" -f $classWeight)% |"
}

# ============================================================
# 6. POSITION CONCENTRATION
# ============================================================

$topPositions = $positions |
    Sort-Object Valor -Descending |
    Select-Object -First 10

$topLines = @()

foreach ($p in $topPositions) {
    $topLines += "| $($p.ID) | $($p.Nome) | $($p.Classe) | R$ $("{0:N2}" -f $p.Valor) | $("{0:N2}" -f $p.Peso)% |"
}

# ============================================================
# 7. PORTFOLIO INTEGRITY
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
$classLines

## Top 10 posições por valor

| ID | Ativo | Classe | Valor | Peso |
|---|---|---|---:|---:|
$topLines

## Regras

1. O valor operacional é calculado pela soma das posições individuais.
2. Os pesos são derivados desse valor operacional.
3. Pesos alvo não são inferidos nesta camada.
4. Classificações econômicas mais sofisticadas dependem de camada própria de exposição.
5. Diferenças entre totais da fonte e soma das posições devem permanecer rastreáveis.

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

Write-Host ""
Write-Host "CREATED/UPDATED: $integrityPath"

# ============================================================
# 8. EXPOSURE MAP
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

## Objetivo

Mapa inicial das exposições da carteira derivado exclusivamente da classificação atual das posições.

## Regra

Esta versão não presume classificação econômica além da classe registrada.

## Classes observadas

$classLines

## PCIP11

- Posição atual: R$ $("{0:N2}" -f $pcipValue)
- Peso da carteira: $("{0:N4}" -f $pcipWeight)%

## Próxima camada

A classificação econômica deverá posteriormente adicionar:

- estratégia;
- gestor;
- indexador;
- crédito;
- exposição imobiliária;
- exposição setorial;
- concentração;
- sobreposição.

Essas dimensões não devem ser inferidas automaticamente nesta versão.

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
# 9. ATUALIZA PORTFOLIO CONTEXT DO PCIP11
# ============================================================

$pcipContextPath = Join-Path `
    $pcipExposureRoot `
    "PCIP11 - Portfolio Context.md"

if (Test-Path -LiteralPath $pcipContextPath -PathType Leaf) {

    $context = Get-Content `
        -LiteralPath $pcipContextPath `
        -Raw `
        -Encoding UTF8

    if ($context -notmatch "\[\[EXPOSURE-MAP\]\]") {

        $context += @"

## Portfolio Integrity

- [[Current]]
- [[Position Registry]]
- [[Portfolio Integrity]]
- [[EXPOSURE-MAP]]

## Snapshot atual

- Valor operacional da carteira: R$ $("{0:N2}" -f $total)
- Peso PCIP11: $("{0:N4}" -f $pcipWeight)%
- Valor PCIP11: R$ $("{0:N2}" -f $pcipValue)

"@

        Set-Content `
            -LiteralPath $pcipContextPath `
            -Value $context `
            -Encoding UTF8

        Write-Host "UPDATED: PCIP11 Portfolio Context"
    }
}

# ============================================================
# 10. MANIFEST
# ============================================================

$manifest = Join-Path `
    $backupRoot `
    "PORTFOLIO_INTEGRITY_MANIFEST.txt"

@"
IIP Portfolio Integrity + Exposure Foundation v0.1

Positions: $($positions.Count)
Operational value: R$ $("{0:N2}" -f $total)
Weight sum: $("{0:N4}" -f $weightSum)%
PCIP11 value: R$ $("{0:N2}" -f $pcipValue)
PCIP11 weight: $("{0:N4}" -f $pcipWeight)%

Created/updated:
02_Portfolio\Portfolio Integrity.md
06_Exposures\EXPOSURE-MAP.md
06_Exposures\PCIP11\PCIP11 - Portfolio Context.md
"@ |
Set-Content -LiteralPath $manifest -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " RESULTADO"
Write-Host "============================================================"
Write-Host "RESULTADO: PASS"
Write-Host "Portfolio Integrity + Exposure Foundation v0.1 concluída"
Write-Host "Backup: $backupRoot"
