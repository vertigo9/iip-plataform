$ErrorActionPreference = "Stop"

$Repo  = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$Vault = Join-Path $Repo "vault"

$AssetsDir    = Join-Path $Vault "01_Assets"
$ExposureDir  = Join-Path $Vault "06_Exposures"
$PortfolioDir = Join-Path $Vault "02_Portfolio"
$ArchiveDir   = Join-Path $Repo "archive"

$AssetRegistryFile    = Join-Path $AssetsDir "00_Asset_Registry.md"
$ExposureRegistryFile = Join-Path $ExposureDir "00_Portfolio_Exposure_Registry.md"
$CurrentFile          = Join-Path $PortfolioDir "Current.md"

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $ArchiveDir "asset-exposure-registry-$Timestamp"

New-Item -ItemType Directory -Force -Path $BackupDir   | Out-Null
New-Item -ItemType Directory -Force -Path $AssetsDir   | Out-Null
New-Item -ItemType Directory -Force -Path $ExposureDir | Out-Null

# ============================================================
# DATASET DOS 46 ATIVOS
# ============================================================

$Assets = @(
    # AÇÕES
    [PSCustomObject]@{ID="BBSE3";Name="BB Seguridade";Class="acao";Category="acao";Bucket="equity";Ticker="BBSE3";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="ISAE4";Name="ISA Energia Brasil";Class="acao";Category="acao";Bucket="equity";Ticker="ISAE4";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="CXSE3";Name="Caixa Seguridade";Class="acao";Category="acao";Bucket="equity";Ticker="CXSE3";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="ABCB4";Name="Banco ABC Brasil";Class="acao";Category="acao";Bucket="equity";Ticker="ABCB4";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="CMIG4";Name="CEMIG";Class="acao";Category="acao";Bucket="equity";Ticker="CMIG4";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="CPFE3";Name="CPFL Energia";Class="acao";Category="acao";Bucket="equity";Ticker="CPFE3";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="ALOS3";Name="ALLOS";Class="acao";Category="acao";Bucket="equity";Ticker="ALOS3";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="CSUD3";Name="CSU Digital";Class="acao";Category="acao";Bucket="equity";Ticker="CSUD3";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="SAUD3";Name="Méliuz Saúde";Class="acao";Category="acao";Bucket="equity";Ticker="SAUD3";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="VBBR3";Name="Vibra Energia";Class="acao";Category="acao";Bucket="equity";Ticker="VBBR3";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="KLBN4";Name="Klabin";Class="acao";Category="acao";Bucket="equity";Ticker="KLBN4";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="FESA4";Name="Ferbasa";Class="acao";Category="acao";Bucket="equity";Ticker="FESA4";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="LEVE3";Name="Mahle Metal Leve";Class="acao";Category="acao";Bucket="equity";Ticker="LEVE3";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="PASS3";Name="Porto Seguro";Class="acao";Category="acao";Bucket="equity";Ticker="PASS3";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}

    # FIIs / FI-INFRA / FIAGRO
    [PSCustomObject]@{ID="LVBI11";Name="LVBI11";Class="fii";Category="Logístico";Bucket="real_estate_logistics";Ticker="LVBI11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="BTLG11";Name="BTLG11";Class="fii";Category="Logístico";Bucket="real_estate_logistics";Ticker="BTLG11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="HGRU11";Name="HGRU11";Class="fii";Category="Híbrido";Bucket="real_estate_hybrid";Ticker="HGRU11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="CDII11";Name="CDII11";Class="fi_infra";Category="Infraestrutura (FI-Infra)";Bucket="infrastructure";Ticker="CDII11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="TRXF11";Name="TRXF11";Class="fii";Category="Híbrido";Bucket="real_estate_hybrid";Ticker="TRXF11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="AFHI11";Name="AFHI11";Class="fii";Category="Títulos e Valores Mobiliários";Bucket="securities";Ticker="AFHI11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="CPTI11";Name="CPTI11";Class="fi_infra";Category="Infraestrutura (FI-Infra)";Bucket="infrastructure";Ticker="CPTI11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="MANA11";Name="MANA11";Class="fii";Category="Títulos e Valores Mobiliários";Bucket="securities";Ticker="MANA11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="VGIP11";Name="VGIP11";Class="fii";Category="Títulos e Valores Mobiliários";Bucket="securities";Ticker="VGIP11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="HSML11";Name="HSML11";Class="fii";Category="Shoppings";Bucket="real_estate_shopping";Ticker="HSML11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="JURO11";Name="JURO11";Class="fi_infra";Category="Infraestrutura (FI-Infra)";Bucket="infrastructure";Ticker="JURO11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="XPML11";Name="XPML11";Class="fii";Category="Shoppings";Bucket="real_estate_shopping";Ticker="XPML11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="PCIP11";Name="PCIP11";Class="fii";Category="Híbrido";Bucket="real_estate_hybrid";Ticker="PCIP11";Indexer="";Issuer="";Evidence="observed";FullAsset="true"}
    [PSCustomObject]@{ID="CRAA11";Name="CRAA11";Class="fiagro";Category="Fiagro";Bucket="fiagro";Ticker="CRAA11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="HGCR11";Name="HGCR11";Class="fii";Category="Títulos e Valores Mobiliários";Bucket="securities";Ticker="HGCR11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="RBVA11";Name="RBVA11";Class="fii";Category="Híbrido";Bucket="real_estate_hybrid";Ticker="RBVA11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="ALZR11";Name="ALZR11";Class="fii";Category="Híbrido";Bucket="real_estate_hybrid";Ticker="ALZR11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="BTCI11";Name="BTCI11";Class="fii";Category="Títulos e Valores Mobiliários";Bucket="securities";Ticker="BTCI11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="KNRI11";Name="KNRI11";Class="fii";Category="Híbrido";Bucket="real_estate_hybrid";Ticker="KNRI11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="HGBS11";Name="HGBS11";Class="fii";Category="Shoppings";Bucket="real_estate_shopping";Ticker="HGBS11";Indexer="";Issuer="";Evidence="observed";FullAsset="false"}

    # RENDA FIXA
    [PSCustomObject]@{ID="RF-NUBANK-120CDI";Name="CDB NuBank 120% CDI";Class="renda_fixa";Category="CDB";Bucket="fixed_income";Ticker="";Indexer="CDI";Issuer="NuBank";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="RF-DIGIMAIS-123CDI";Name="CDB Banco Digimais 123% CDI";Class="renda_fixa";Category="CDB";Bucket="fixed_income";Ticker="";Indexer="CDI";Issuer="Banco Digimais";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="RF-MP-115CDI";Name="CDB Mercado Pago 115% CDI";Class="renda_fixa";Category="CDB";Bucket="fixed_income";Ticker="";Indexer="CDI";Issuer="Mercado Pago";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="RF-JF-CDI2_60";Name="CDB J&F Investimentos CDI + 2,60%";Class="renda_fixa";Category="CDB";Bucket="fixed_income";Ticker="";Indexer="CDI + spread";Issuer="J&F Investimentos";Evidence="observed";FullAsset="false"}
    [PSCustomObject]@{ID="RF-MB-BINVEST03";Name="CDB Mercado Bitcoin BINVEST 03";Class="renda_fixa";Category="CDB";Bucket="fixed_income";Ticker="";Indexer="gap";Issuer="Mercado Bitcoin";Evidence="gap";FullAsset="false"}
    [PSCustomObject]@{ID="RF-MB-JEITTO14";Name="CDB Mercado Bitcoin JEITTO 14";Class="renda_fixa";Category="CDB";Bucket="fixed_income";Ticker="";Indexer="gap";Issuer="Mercado Bitcoin";Evidence="gap";FullAsset="false"}
    [PSCustomObject]@{ID="RF-MB-ROOFTOP04";Name="CDB Mercado Bitcoin ROOFTOP 04";Class="renda_fixa";Category="CDB";Bucket="fixed_income";Ticker="";Indexer="gap";Issuer="Mercado Bitcoin";Evidence="gap";FullAsset="false"}
    [PSCustomObject]@{ID="RF-MB-MULTIPLIKE12";Name="CDB Mercado Bitcoin MULTIPLIKE 12";Class="renda_fixa";Category="CDB";Bucket="fixed_income";Ticker="";Indexer="gap";Issuer="Mercado Bitcoin";Evidence="gap";FullAsset="false"}
    [PSCustomObject]@{ID="RF-MB-JEITTO03";Name="CDB Mercado Bitcoin JEITTO 03";Class="renda_fixa";Category="CDB";Bucket="fixed_income";Ticker="";Indexer="gap";Issuer="Mercado Bitcoin";Evidence="gap";FullAsset="false"}
    [PSCustomObject]@{ID="RF-BMG-IPCA14_50";Name="CDB Banco BMG IPCA + 14,50%";Class="renda_fixa";Category="CDB";Bucket="fixed_income";Ticker="";Indexer="IPCA + spread";Issuer="Banco BMG";Evidence="observed";FullAsset="false"}

    # ETF
    [PSCustomObject]@{ID="LFTB11";Name="LFTB11";Class="etf";Category="ETF";Bucket="etf";Ticker="LFTB11";Indexer="gap";Issuer="";Evidence="observed";FullAsset="false"}

    # FUNDO
    [PSCustomObject]@{ID="FMP-FGTS-DAYCOVAL";Name="DAYCOVAL FUNDO MÚTUO DE PRIVATIZAÇÃO DO FGTS ELETROBRAS (FMP-FGTS)";Class="fundo";Category="FMP-FGTS";Bucket="fund";Ticker="";Indexer="";Issuer="Daycoval";Evidence="observed";FullAsset="false"}
)

# ============================================================
# VALIDAÇÃO
# ============================================================

if ($Assets.Count -ne 46) {
    throw "ERRO: o dataset deveria possuir 46 ativos. Encontrado: $($Assets.Count)"
}

$UniqueIDs = @($Assets | Select-Object -ExpandProperty ID -Unique)

if ($UniqueIDs.Count -ne 46) {
    throw "ERRO: existem IDs duplicados."
}

$PCIP = @($Assets | Where-Object { $_.ID -eq "PCIP11" })

if ($PCIP.Count -ne 1) {
    throw "ERRO: PCIP11 não foi encontrado corretamente."
}

# ============================================================
# BACKUP DOS ARQUIVOS EXISTENTES
# ============================================================

$FilesToBackup = @(
    $AssetRegistryFile,
    $ExposureRegistryFile,
    $CurrentFile
)

foreach ($File in $FilesToBackup) {
    if (Test-Path $File) {
        Copy-Item -LiteralPath $File -Destination (Join-Path $BackupDir (Split-Path $File -Leaf)) -Force
    }
}

# ============================================================
# ASSET REGISTRY
# ============================================================

$A = New-Object System.Collections.Generic.List[string]

$A.Add("---")
$A.Add("type: asset_registry")
$A.Add('schema_version: "0.1"')
$A.Add("scope: portfolio")
$A.Add("state: current")
$A.Add("asset_count: 46")
$A.Add("status: active")
$A.Add("---")
$A.Add("")
$A.Add("# Asset Registry v0.1")
$A.Add("")
$A.Add("Cadastro mestre das 46 posições atualmente presentes na carteira.")
$A.Add("")
$A.Add("## Evidence Status")
$A.Add("")
$A.Add("- observed = informação explicitamente conhecida na base operacional.")
$A.Add("- gap = informação que ainda necessita de evidência documental.")
$A.Add("")
$A.Add("## Registro")
$A.Add("")
$A.Add("| Position ID | Nome | Classe | Categoria | Economic Bucket | Ticker | Indexador | Emissor | Evidence | Full Asset |")
$A.Add("|---|---|---|---|---|---|---|---|---|---|")

foreach ($Item in $Assets) {
    $A.Add("| $($Item.ID) | $($Item.Name) | $($Item.Class) | $($Item.Category) | $($Item.Bucket) | $($Item.Ticker) | $($Item.Indexer) | $($Item.Issuer) | $($Item.Evidence) | $($Item.FullAsset) |")
}

$A.Add("")
$A.Add("## Documentação estrutural existente")
$A.Add("")
$A.Add("- PCIP11: [[FIIs/PCIP11/00_PCIP11_Index]]")
$A.Add("")
$A.Add("## Regra")
$A.Add("")
$A.Add("Classificações detalhadas de gestor, estratégia, devedor, setor, duration, crédito e overlap serão adicionadas somente quando houver evidência.")

Set-Content -LiteralPath $AssetRegistryFile -Value $A -Encoding UTF8

# ============================================================
# EXPOSURE REGISTRY
# ============================================================

$E = New-Object System.Collections.Generic.List[string]

$E.Add("---")
$E.Add("type: portfolio_exposure_registry")
$E.Add('schema_version: "0.1"')
$E.Add("scope: portfolio")
$E.Add("position_count: 46")
$E.Add("state: current")
$E.Add("status: active")
$E.Add("---")
$E.Add("")
$E.Add("# Portfolio Exposure Registry v0.1")
$E.Add("")
$E.Add("Mapa inicial das exposições econômicas reconhecidas na carteira.")
$E.Add("")
$E.Add("## Buckets")
$E.Add("")
$E.Add("| Economic Bucket | Quantidade | Ativos |")
$E.Add("|---|---:|---|")

$Groups = @($Assets | Group-Object Bucket | Sort-Object Name)

foreach ($Group in $Groups) {
    $IDs = ($Group.Group | ForEach-Object { $_.ID }) -join ", "
    $E.Add("| $($Group.Name) | $($Group.Count) | $IDs |")
}

$E.Add("")
$E.Add("## Dimensões pendentes")
$E.Add("")
$E.Add("| Dimensão | Status |")
$E.Add("|---|---|")
$E.Add("| Gestor | gap |")
$E.Add("| Estratégia detalhada | gap |")
$E.Add("| Exposição a crédito | gap |")
$E.Add("| Devedor final | gap |")
$E.Add("| Setor econômico | gap |")
$E.Add("| Concentração por grupo econômico | gap |")
$E.Add("| Overlap entre ativos | gap |")
$E.Add("")
$E.Add("## Cadeia de decisão")
$E.Add("")
$E.Add("Ativo -> Posição -> Portfólio -> Exposição -> Evidência/Métricas -> Decisão")

Set-Content -LiteralPath $ExposureRegistryFile -Value $E -Encoding UTF8

# ============================================================
# VALIDAÇÃO FINAL
# ============================================================

Write-Host ""
Write-Host "============================================================"
Write-Host "0684 / 0685 - ASSET + EXPOSURE REGISTRY"
Write-Host "============================================================"
Write-Host ""

Write-Host "Ativos registrados : $($Assets.Count)"
Write-Host "IDs únicos         : $($UniqueIDs.Count)"
Write-Host "PCIP11             : PASS"
Write-Host "PCIP11 Full Asset  : $($PCIP[0].FullAsset)"
Write-Host "Asset Registry     : PASS"
Write-Host "Exposure Registry  : PASS"
Write-Host "Backup             : $BackupDir"

Write-Host ""
Write-Host "DISTRIBUICAO POR ECONOMIC BUCKET"
Write-Host "------------------------------------------------------------"

foreach ($Group in $Groups) {
    Write-Host ("{0,-28} {1,2}" -f $Group.Name, $Group.Count)
}

Write-Host ""
Write-Host "============================================================"
Write-Host "STATUS: 0684/0685 CONCLUIDO"
Write-Host "============================================================"