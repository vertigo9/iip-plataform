$ErrorActionPreference = "Stop"

Write-Host "============================================================"
Write-Host " IIP - PORTFOLIO CONTEXT LAYER v0.1 - PCIP11"
Write-Host "============================================================"

$vaultRoot = (Get-Location).Path

$pcipRoot = Join-Path $vaultRoot "01_Assets\FIIs\PCIP11"
$portfolioRoot = Join-Path $vaultRoot "02_Portfolio"
$exposureRoot = Join-Path $vaultRoot "06_Exposures"
$pcipExposureRoot = Join-Path $exposureRoot "PCIP11"

if (-not (Test-Path -LiteralPath $pcipRoot -PathType Container)) {
    Write-Host "FAIL: PCIP11 não encontrado"
    exit 1
}

New-Item -ItemType Directory -Path $pcipExposureRoot -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$backupRoot = Join-Path `
    $vaultRoot `
    "archive\pcip11-portfolio-context-pre-v0.1-$timestamp"

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

Write-Host ""
Write-Host "Backup:"
Write-Host $backupRoot

# ============================================================
# 1. DISCOVERY DOS ATIVOS
# ============================================================

$assetRoot = Join-Path $vaultRoot "01_Assets"

$assetIndexes = @()

if (Test-Path -LiteralPath $assetRoot -PathType Container) {

    $assetIndexes = Get-ChildItem `
        -LiteralPath $assetRoot `
        -Recurse `
        -Filter "00_*_Index.md" `
        -File
}

Write-Host ""
Write-Host "Ativos descobertos: $($assetIndexes.Count)"

$assetLinks = @()

foreach ($asset in $assetIndexes) {

    $relative = $asset.FullName.Substring($vaultRoot.Length).TrimStart("\")
    Write-Host "ASSET: $relative"

    $content = Get-Content `
        -LiteralPath $asset.FullName `
        -Raw `
        -Encoding UTF8

    if ($content -match "(?m)^ticker:\s*([A-Z0-9]+)\s*$") {

        $ticker = $matches[1]

        if ($ticker -ne "PCIP11") {
            $assetLinks += "- [$ticker]($relative)"
        }
    }
}

# Remove duplicates
$assetLinks = $assetLinks | Sort-Object -Unique

# ============================================================
# 2. DISCOVERY DOS PORTFOLIO SNAPSHOTS
# ============================================================

$portfolioFiles = @()

if (Test-Path -LiteralPath $portfolioRoot -PathType Container) {

    $portfolioFiles = Get-ChildItem `
        -LiteralPath $portfolioRoot `
        -Recurse `
        -File `
        -Filter "*.md"
}

Write-Host ""
Write-Host "Notas de Portfolio descobertas: $($portfolioFiles.Count)"

$portfolioLinks = @()

foreach ($file in $portfolioFiles) {

    $relative = $file.FullName.Substring($vaultRoot.Length).TrimStart("\")
    Write-Host "PORTFOLIO: $relative"

    if ($file.Name -match "snapshot|carteira|portfolio|posição|posicao") {
        $portfolioLinks += "- $relative"
    }
}

$portfolioLinks = $portfolioLinks | Sort-Object -Unique

# ============================================================
# 3. DISCOVERY DAS EXPOSURES
# ============================================================

$exposureFiles = @()

if (Test-Path -LiteralPath $exposureRoot -PathType Container) {

    $exposureFiles = Get-ChildItem `
        -LiteralPath $exposureRoot `
        -Recurse `
        -File `
        -Filter "*.md"
}

Write-Host ""
Write-Host "Notas de Exposure descobertas: $($exposureFiles.Count)"

$exposureLinks = @()

foreach ($file in $exposureFiles) {

    $relative = $file.FullName.Substring($vaultRoot.Length).TrimStart("\")
    Write-Host "EXPOSURE: $relative"

    if ($file.FullName -notlike "*\PCIP11\*") {
        $exposureLinks += "- $relative"
    }
}

$exposureLinks = $exposureLinks | Sort-Object -Unique

# ============================================================
# 4. CRIAÇÃO DO PORTFOLIO CONTEXT
# ============================================================

$contextPath = Join-Path `
    $pcipExposureRoot `
    "PCIP11 - Portfolio Context.md"

if (Test-Path -LiteralPath $contextPath -PathType Leaf) {

    Copy-Item `
        -LiteralPath $contextPath `
        -Destination (Join-Path $backupRoot (Split-Path $contextPath -Leaf)) `
        -Force
}

$context = @"
---
type: portfolio_context
asset_id: PCIP11
ticker: PCIP11
asset_class: FII
schema_version: "0.1"
status: active
context_scope: portfolio
decision_scope: portfolio_adjusted
---

# PCIP11 — Portfolio Context

## Objetivo

Avaliar o PCIP11 não como ativo isolado, mas como posição integrante da carteira global.

A qualidade individual do ativo não determina sozinha a decisão de aporte.

A decisão deverá considerar:

- qualidade intrínseca;
- valuation;
- sustentabilidade de distribuição;
- risco de crédito;
- concentração;
- exposição da carteira;
- sobreposição com outros ativos;
- custo de oportunidade;
- prioridade relativa de aporte.

## Ativos da carteira

$($assetLinks -join "`n")

## Portfolio snapshots

$($portfolioLinks -join "`n")

## Exposures existentes

$($exposureLinks -join "`n")

## Eixos de análise de carteira

### Concentração

- peso do PCIP11;
- peso agregado da classe;
- peso por gestor;
- peso por indexador;
- peso por estratégia;
- concentração de risco de crédito.

### Sobreposição

Avaliar sobreposição econômica entre PCIP11 e outros ativos da carteira.

Especial atenção para:

- FIIs de papel;
- fundos de crédito;
- fundos com exposição aos mesmos devedores;
- fundos com os mesmos indexadores;
- gestores com exposições semelhantes;
- ativos concorrentes para o mesmo capital.

### Custo de oportunidade

A decisão de aporte deverá comparar PCIP11 com alternativas disponíveis na carteira ou no universo monitorado.

### Objetivo da decisão

A decisão futura deverá expressar:

- decisão sobre PCIP11;
- impacto na carteira;
- alternativa sacrificada;
- justificativa;
- grau de confiança;
- gatilhos de revisão.

## Estado

PORTFOLIO_CONTEXT_READY

## Regra de integridade

Não preencher pesos, concentrações, correlações ou prioridades sem fonte ou cálculo explicitamente identificado.

Nenhuma decisão de carteira deve tratar PCIP11 isoladamente quando houver informação suficiente para análise relativa.
"@

Set-Content `
    -LiteralPath $contextPath `
    -Value $context `
    -Encoding UTF8

Write-Host ""
Write-Host "CREATED/UPDATED:"
Write-Host $contextPath

# ============================================================
# 5. CONEXÃO COM O ASSET INDEX
# ============================================================

$assetIndex = Join-Path $pcipRoot "00_PCIP11_Index.md"

if (Test-Path -LiteralPath $assetIndex -PathType Leaf) {

    $indexContent = Get-Content `
        -LiteralPath $assetIndex `
        -Raw `
        -Encoding UTF8

    if ($indexContent -notmatch "\[\[PCIP11 - Portfolio Context\]\]") {

        Copy-Item `
            -LiteralPath $assetIndex `
            -Destination (Join-Path $backupRoot (Split-Path $assetIndex -Leaf)) `
            -Force

        $section = @"

## Portfolio Context

- [[PCIP11 - Portfolio Context]]
"@

        $indexContent = `
            $indexContent.TrimEnd() + `
            "`n" + `
            $section + `
            "`n"

        Set-Content `
            -LiteralPath $assetIndex `
            -Value $indexContent `
            -Encoding UTF8

        Write-Host "UPDATED: PCIP11 Index"
    }
    else {
        Write-Host "EXISTS: Portfolio Context já vinculado"
    }
}

# ============================================================
# 6. MANIFEST
# ============================================================

$manifestPath = Join-Path `
    $backupRoot `
    "PORTFOLIO_CONTEXT_MANIFEST.txt"

$manifest = @"
IIP Portfolio Context Layer v0.1
Asset: PCIP11
Timestamp: $timestamp

Asset indexes discovered: $($assetIndexes.Count)
Portfolio markdown notes discovered: $($portfolioFiles.Count)
Exposure markdown notes discovered: $($exposureFiles.Count)

Created/updated:
06_Exposures\PCIP11\PCIP11 - Portfolio Context.md
01_Assets\FIIs\PCIP11\00_PCIP11_Index.md
"@

Set-Content `
    -LiteralPath $manifestPath `
    -Value $manifest `
    -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " RESULTADO"
Write-Host "============================================================"
Write-Host "RESULTADO: PASS"
Write-Host "Portfolio Context Layer v0.1 implantada"
Write-Host "Backup: $backupRoot"
