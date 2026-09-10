$ErrorActionPreference = "Stop"

# ============================================================
# IIP - 0687
# UNDERLYING EXPOSURE REGISTRY
# ============================================================

$Repo  = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$Vault = Join-Path $Repo "vault"

$ExposureDir  = Join-Path $Vault "06_Exposures"
$UnderlyingDir = Join-Path $ExposureDir "01_Underlying"
$ArchiveDir   = Join-Path $Repo "archive"

$RegistryFile = Join-Path $UnderlyingDir "00_Underlying_Exposure_Registry.md"

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $ArchiveDir "underlying-exposure-0687-$Timestamp"

New-Item -ItemType Directory -Force -Path $UnderlyingDir | Out-Null
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

# ============================================================
# FUNDOS PRIORITÁRIOS
# ============================================================

$Funds = @(
    [PSCustomObject]@{
        Ticker="PCIP11"
        Family="credit_real_estate_hybrid"
        Priority="P1"
        Documentation="complete_asset_layer"
        Status="ready_for_extraction"
    }

    [PSCustomObject]@{
        Ticker="VGIP11"
        Family="credit_real_estate"
        Priority="P1"
        Documentation="registry_only"
        Status="awaiting_evidence"
    }

    [PSCustomObject]@{
        Ticker="AFHI11"
        Family="credit_real_estate"
        Priority="P1"
        Documentation="registry_only"
        Status="awaiting_evidence"
    }

    [PSCustomObject]@{
        Ticker="HGCR11"
        Family="credit_real_estate"
        Priority="P1"
        Documentation="registry_only"
        Status="awaiting_evidence"
    }

    [PSCustomObject]@{
        Ticker="BTCI11"
        Family="credit_real_estate"
        Priority="P1"
        Documentation="registry_only"
        Status="awaiting_evidence"
    }

    [PSCustomObject]@{
        Ticker="MANA11"
        Family="credit_real_estate"
        Priority="P1"
        Documentation="registry_only"
        Status="awaiting_evidence"
    }

    [PSCustomObject]@{
        Ticker="CDII11"
        Family="infrastructure"
        Priority="P2"
        Documentation="registry_only"
        Status="awaiting_evidence"
    }

    [PSCustomObject]@{
        Ticker="CPTI11"
        Family="infrastructure"
        Priority="P2"
        Documentation="registry_only"
        Status="awaiting_evidence"
    }

    [PSCustomObject]@{
        Ticker="JURO11"
        Family="infrastructure"
        Priority="P2"
        Documentation="registry_only"
        Status="awaiting_evidence"
    }

    [PSCustomObject]@{
        Ticker="HGRU11"
        Family="real_estate_hybrid"
        Priority="P3"
        Documentation="registry_only"
        Status="awaiting_evidence"
    }

    [PSCustomObject]@{
        Ticker="TRXF11"
        Family="real_estate_hybrid"
        Priority="P3"
        Documentation="registry_only"
        Status="awaiting_evidence"
    }

    [PSCustomObject]@{
        Ticker="RBVA11"
        Family="real_estate_hybrid"
        Priority="P3"
        Documentation="registry_only"
        Status="awaiting_evidence"
    }

    [PSCustomObject]@{
        Ticker="ALZR11"
        Family="real_estate_hybrid"
        Priority="P3"
        Documentation="registry_only"
        Status="awaiting_evidence"
    }

    [PSCustomObject]@{
        Ticker="KNRI11"
        Family="real_estate_hybrid"
        Priority="P3"
        Documentation="registry_only"
        Status="awaiting_evidence"
    }
)

# ============================================================
# VALIDAÇÃO
# ============================================================

$ExpectedFunds = 14

if ($Funds.Count -ne $ExpectedFunds) {
    throw "ERRO: esperado $ExpectedFunds fundos prioritários; encontrado $($Funds.Count)."
}

$UniqueFunds = @(
    $Funds |
    Select-Object -ExpandProperty Ticker -Unique
)

if ($UniqueFunds.Count -ne $ExpectedFunds) {
    throw "ERRO: existem tickers duplicados."
}

$PCIP = @(
    $Funds |
    Where-Object { $_.Ticker -eq "PCIP11" }
)

if ($PCIP.Count -ne 1) {
    throw "ERRO: PCIP11 não localizado corretamente."
}

# ============================================================
# BACKUP
# ============================================================

if (Test-Path $RegistryFile) {
    Copy-Item `
        -LiteralPath $RegistryFile `
        -Destination (Join-Path $BackupDir "00_Underlying_Exposure_Registry.md") `
        -Force
}

# ============================================================
# REGISTRY
# ============================================================

$Lines = New-Object System.Collections.Generic.List[string]

$Lines.Add("---")
$Lines.Add("type: underlying_exposure_registry")
$Lines.Add('schema_version: "0.1"')
$Lines.Add("scope: portfolio")
$Lines.Add("fund_count: 14")
$Lines.Add("state: current")
$Lines.Add("status: active")
$Lines.Add("---")
$Lines.Add("")
$Lines.Add("# Underlying Exposure Registry v0.1")
$Lines.Add("")
$Lines.Add("Registro mestre das posições prioritárias para decomposição de exposição econômica.")
$Lines.Add("")
$Lines.Add("## Regra metodológica")
$Lines.Add("")
$Lines.Add("Este registro não inventa composição de carteira.")
$Lines.Add("Os campos de exposição subjacente somente deverão ser preenchidos quando houver evidência documental.")
$Lines.Add("")
$Lines.Add("## Fundos prioritários")
$Lines.Add("")
$Lines.Add("| Ticker | Família | Prioridade | Documentação | Status |")
$Lines.Add("|---|---|---|---|---|")

foreach ($Fund in $Funds) {

    $Lines.Add(
        "| " +
        $Fund.Ticker +
        " | " +
        $Fund.Family +
        " | " +
        $Fund.Priority +
        " | " +
        $Fund.Documentation +
        " | " +
        $Fund.Status +
        " |"
    )
}

$Lines.Add("")
$Lines.Add("## Estrutura de exposição")
$Lines.Add("")
$Lines.Add("| Fundo | Tipo de exposição | Identificador subjacente | Valor / % PL | Indexador | Contraparte / Devedor | Setor | Evidência |")
$Lines.Add("|---|---|---|---:|---|---|---|---|")

foreach ($Fund in $Funds) {

    $Lines.Add(
        "| " +
        $Fund.Ticker +
        " | gap | gap | gap | gap | gap | gap | gap |"
    )
}

$Lines.Add("")
$Lines.Add("## Status da decomposição")
$Lines.Add("")
$Lines.Add("| Camada | Estado |")
$Lines.Add("|---|---|")
$Lines.Add("| Estratégia | parcial |")
$Lines.Add("| Ativos subjacentes | gap |")
$Lines.Add("| Devedores | gap |")
$Lines.Add("| Contrapartes | gap |")
$Lines.Add("| Imóveis | gap |")
$Lines.Add("| Setores | gap |")
$Lines.Add("| Indexadores | parcial |")
$Lines.Add("| Gestores | gap |")
$Lines.Add("| Duration / prazo | gap |")
$Lines.Add("| Overlap econômico | gap |")

$Lines.Add("")
$Lines.Add("## Prioridade analítica")
$Lines.Add("")
$Lines.Add("P1 = impacto direto na análise de crédito e substituição entre FIIs.")
$Lines.Add("P2 = impacto na diversificação entre FI-Infra.")
$Lines.Add("P3 = impacto na sobreposição imobiliária com fundos híbridos.")

$Lines.Add("")
$Lines.Add("## PCIP11")
$Lines.Add("")
$Lines.Add("PCIP11 é o primeiro ativo a ser decomposto, pois já possui camada documental própria.")
$Lines.Add("A extração deverá preservar Observed, Management Statement, Inference e Gap.")
$Lines.Add("")
$Lines.Add("## Regra de decisão")
$Lines.Add("")
$Lines.Add("Nenhuma posição deverá ser considerada economicamente diversificada apenas porque possui um ticker diferente.")
$Lines.Add("A diversificação efetiva será determinada pelos ativos, devedores, setores, imóveis e demais exposições subjacentes.")

Set-Content `
    -LiteralPath $RegistryFile `
    -Value $Lines `
    -Encoding UTF8

# ============================================================
# RESULTADO
# ============================================================

Write-Host ""
Write-Host "============================================================"
Write-Host "0687 - UNDERLYING EXPOSURE REGISTRY"
Write-Host "============================================================"
Write-Host ""

Write-Host "Fundos prioritários : $($Funds.Count)"
Write-Host "IDs únicos          : $($UniqueFunds.Count)"
Write-Host "PCIP11              : PASS"
Write-Host "Registry            : PASS"
Write-Host "Arquivo             : $RegistryFile"
Write-Host "Backup              : $BackupDir"

Write-Host ""
Write-Host "DISTRIBUICAO POR PRIORIDADE"
Write-Host "------------------------------------------------------------"

$P1 = @($Funds | Where-Object { $_.Priority -eq "P1" })
$P2 = @($Funds | Where-Object { $_.Priority -eq "P2" })
$P3 = @($Funds | Where-Object { $_.Priority -eq "P3" })

Write-Host "P1 - Crédito / Papel : $($P1.Count)"
Write-Host "P2 - Infraestrutura   : $($P2.Count)"
Write-Host "P3 - Imobiliário      : $($P3.Count)"

Write-Host ""
Write-Host "============================================================"
Write-Host "STATUS: 0687 CONCLUIDO"
Write-Host "============================================================"