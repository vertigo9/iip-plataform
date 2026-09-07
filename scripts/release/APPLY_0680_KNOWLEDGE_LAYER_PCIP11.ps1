$ErrorActionPreference = "Stop"

Write-Host "============================================================"
Write-Host " IIP - KNOWLEDGE LAYER v0.1 - PCIP11"
Write-Host "============================================================"

$vaultRoot = (Get-Location).Path

$pcipRoot = Join-Path $vaultRoot "01_Assets\FIIs\PCIP11"
$evidenceRoot = Join-Path $vaultRoot "04_Evidence\PCIP11"
$eventsRoot = Join-Path $vaultRoot "05_Events\PCIP11"
$researchRoot = Join-Path $vaultRoot "07_Research\PCIP11"

foreach ($dir in @($evidenceRoot, $eventsRoot, $researchRoot)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $vaultRoot "archive\pcip11-knowledge-layer-pre-v0.1-$timestamp"

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

Write-Host ""
Write-Host "Backup:"
Write-Host $backupRoot

function Backup-IfExists {
    param(
        [string]$Path
    )

    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        Copy-Item -LiteralPath $Path `
            -Destination (Join-Path $backupRoot (Split-Path $Path -Leaf)) `
            -Force
    }
}

function Write-NewNote {
    param(
        [string]$Path,
        [string]$Content
    )

    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        Backup-IfExists $Path
        Write-Host "EXISTS: $Path"
        return
    }

    Set-Content `
        -LiteralPath $Path `
        -Value $Content `
        -Encoding UTF8

    Write-Host "CREATED: $Path"
}

# ============================================================
# 1. EVIDENCE REGISTRY
# ============================================================

$evidenceIndex = Join-Path $evidenceRoot "00_PCIP11_Evidence_Index.md"

$evidenceContent = @"
---
type: evidence_registry
asset_id: PCIP11
ticker: PCIP11
asset_class: FII
registry: evidence
schema_version: "0.1"
status: active
evidence_status: observed
---

# PCIP11 — Evidence Registry

## Objetivo

Registro estrutural das evidências utilizadas na reconstrução histórica e nas análises do PCIP11.

## Regra de integridade

Nenhuma evidência financeira deve ser criada por inferência silenciosa.

Cada evidência futura deverá indicar:

- identificação;
- data de observação;
- ativo;
- componente de origem;
- classificação;
- fonte;
- eventualmente localização da informação;
- confiança.

## Classificações permitidas

- observed
- management_statement
- inference
- gap

## Componentes de origem

- [[PCIP11 - Identidade e Estrutura]]
- [[PCIP11 - Performance Histórica]]
- [[PCIP11 - Distribuições]]
- [[PCIP11 - Carteira e Crédito - Jul 2026]]
- [[PCIP11 - Eventos e Reestruturações]]
- [[PCIP11 - Fontes]]

## Estado inicial

O registro estrutural está criado.

As evidências individuais deverão ser promovidas do conteúdo documental para entidades Evidence apenas quando houver suporte suficiente no material de origem.

## Controle

schema_version: 0.1
status: active
"@

Write-NewNote $evidenceIndex $evidenceContent

# ============================================================
# 2. SOURCE REGISTRY
# ============================================================

$sourceRegistry = Join-Path $pcipRoot "PCIP11 - Source Registry.md"

$sourceContent = @"
---
type: source_registry
asset_id: PCIP11
ticker: PCIP11
asset_class: FII
registry: sources
schema_version: "0.1"
status: active
evidence_status: observed
---

# PCIP11 — Source Registry

## Fonte principal atualmente documentada

`PCIP11_rmg_20082026.pdf`

## Fonte canônica no Vault

[[PCIP11 - Fontes]]

## Componentes que referenciam a fonte

- [[PCIP11 - Identidade e Estrutura]]
- [[PCIP11 - Performance Histórica]]
- [[PCIP11 - Distribuições]]
- [[PCIP11 - Carteira e Crédito - Jul 2026]]
- [[PCIP11 - Eventos e Reestruturações]]

## Regra de precedência

Fontes não devem ser sobrescritas silenciosamente.

Quando existirem registros de naturezas diferentes:

- fonte oficial;
- registro pessoal;
- cálculo do IIP;
- informação externa;

cada natureza deverá permanecer identificável.

## Estado

Registry estrutural criado.

A normalização documental detalhada permanece dependente da disponibilidade dos documentos-fonte correspondentes.
"@

Write-NewNote $sourceRegistry $sourceContent

# ============================================================
# 3. EVENT REGISTRY
# ============================================================

$eventRegistry = Join-Path $eventsRoot "00_PCIP11_Event_Index.md"

$eventContent = @"
---
type: event_registry
asset_id: PCIP11
ticker: PCIP11
asset_class: FII
registry: events
schema_version: "0.1"
status: active
evidence_status: observed
---

# PCIP11 — Event Registry

## Objetivo

Índice estrutural dos eventos e reestruturações relevantes do PCIP11.

## Fonte documental

[[PCIP11 - Eventos e Reestruturações]]

## Regra

Eventos deverão ser registrados como fatos temporais independentes.

Cada evento futuro deverá preferencialmente possuir:

- event_id;
- date;
- event_type;
- description;
- evidence_status;
- source_ref;
- materiality;
- consequence;
- confidence.

## Estado inicial

O registro estrutural está criado.

Os eventos já documentados no componente histórico permanecem como fonte-base até serem promovidos individualmente para entidades Event.
"@

Write-NewNote $eventRegistry $eventContent

# ============================================================
# 4. METRIC REGISTRY
# ============================================================

$metricRegistry = Join-Path $researchRoot "00_PCIP11_Metric_Registry.md"

$metricContent = @"
---
type: metric_registry
asset_id: PCIP11
ticker: PCIP11
asset_class: FII
registry: metrics
schema_version: "0.1"
status: active
evidence_status: observed
---

# PCIP11 — Metric Registry

## Objetivo

Registrar métricas financeiras utilizadas pelo IIP, preservando a distinção entre:

1. valor observado em fonte;
2. valor informado pela gestão;
3. cálculo derivado;
4. inferência analítica;
5. lacuna.

## Componentes de origem

### Performance

[[PCIP11 - Performance Histórica]]

### Distribuições

[[PCIP11 - Distribuições]]

### Carteira e Crédito

[[PCIP11 - Carteira e Crédito - Jul 2026]]

## Classes de métrica

- performance;
- distribuição;
- patrimônio;
- valuation;
- crédito;
- carteira;
- risco;
- exposição.

## Regra de integridade

Uma métrica estruturada não deve ser criada apenas porque existe um conceito conhecido pelo IIP.

Ela deverá possuir suporte documental ou ser explicitamente marcada como inferência/cálculo.

## Estado inicial

Registry estrutural criado.

A promoção dos valores históricos para entidades Metric será feita somente quando a origem e a unidade estiverem identificadas de maneira inequívoca.
"@

Write-NewNote $metricRegistry $metricContent

# ============================================================
# 5. KNOWLEDGE READINESS
# ============================================================

$readiness = Join-Path $researchRoot "PCIP11 - Knowledge Readiness.md"

$readinessContent = @"
---
type: knowledge_readiness
asset_id: PCIP11
ticker: PCIP11
asset_class: FII
schema_version: "0.1"
status: active
---

# PCIP11 — Knowledge Readiness

## Camadas concluídas

- Asset Schema v0.1
- Asset Components
- Evidence Registry v0.1
- Source Registry v0.1
- Event Registry v0.1
- Metric Registry v0.1

## Próximas camadas

- promoção de evidências individuais;
- promoção de eventos individuais;
- promoção de métricas históricas;
- avaliação/tese;
- integração com Decision Layer;
- dashboards.

## Regra

Nenhuma lacuna documental deve ser preenchida por interpolação silenciosa.

## Estado atual

READY_FOR_EVIDENCE_EXTRACTION

## Schema

0.1
"@

Write-NewNote $readiness $readinessContent

# ============================================================
# 6. UPDATE ASSET INDEX - NON-DESTRUCTIVE
# ============================================================

$assetIndex = Join-Path $pcipRoot "00_PCIP11_Index.md"

if (Test-Path -LiteralPath $assetIndex -PathType Leaf) {

    $indexContent = Get-Content -LiteralPath $assetIndex -Raw -Encoding UTF8

    Backup-IfExists $assetIndex

    if ($indexContent -notmatch "\[\[PCIP11 - Source Registry\]\]") {

        $section = @"

## Knowledge Layer

- [[PCIP11 - Source Registry]]
- [[00_PCIP11_Evidence_Index]]
- [[00_PCIP11_Event_Index]]
- [[00_PCIP11_Metric_Registry]]
- [[PCIP11 - Knowledge Readiness]]
"@

        $indexContent = $indexContent.TrimEnd() + "`n" + $section + "`n"

        Set-Content `
            -LiteralPath $assetIndex `
            -Value $indexContent `
            -Encoding UTF8

        Write-Host "UPDATED: PCIP11 Index"
    }
    else {
        Write-Host "EXISTS: Knowledge Layer already linked in Index"
    }
}

# ============================================================
# 7. MANIFEST
# ============================================================

$manifestPath = Join-Path $backupRoot "KNOWLEDGE_LAYER_MANIFEST.txt"

$manifest = @"
IIP Knowledge Layer v0.1
Asset: PCIP11
Timestamp: $timestamp

Created:
04_Evidence\PCIP11\00_PCIP11_Evidence_Index.md
01_Assets\FIIs\PCIP11\PCIP11 - Source Registry.md
05_Events\PCIP11\00_PCIP11_Event_Index.md
07_Research\PCIP11\00_PCIP11_Metric_Registry.md
07_Research\PCIP11\PCIP11 - Knowledge Readiness.md
"@

Set-Content `
    -LiteralPath $manifestPath `
    -Value $manifest `
    -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " RESULTADO DA IMPLANTAÇÃO"
Write-Host "============================================================"
Write-Host "RESULTADO: PASS"
Write-Host "Knowledge Layer v0.1 criada"
Write-Host "Backup: $backupRoot"
