$ErrorActionPreference = "Stop"

# ============================================================
# IIP - 0686
# ECONOMIC EXPOSURE + OVERLAP FOUNDATION
# ============================================================

$Repo  = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$Vault = Join-Path $Repo "vault"

$ExposureDir  = Join-Path $Vault "06_Exposures"
$ResearchDir  = Join-Path $Vault "07_Research"
$PortfolioDir = Join-Path $Vault "02_Portfolio"
$ArchiveDir   = Join-Path $Repo "archive"

$ExposureMapFile = Join-Path $ExposureDir "00_Economic_Exposure_Map.md"
$OverlapFile     = Join-Path $ResearchDir "00_Overlap_Foundation.md"

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $ArchiveDir "economic-exposure-0686-$Timestamp"

# ============================================================
# DIRETÓRIOS
# ============================================================

New-Item -ItemType Directory -Force -Path $ExposureDir | Out-Null
New-Item -ItemType Directory -Force -Path $ResearchDir | Out-Null
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

# ============================================================
# DATASET VALIDADO DA CARTEIRA
# ============================================================

$Positions = @(

    # ========================================================
    # AÇÕES
    # ========================================================

    [PSCustomObject]@{
        ID="BBSE3"; Value=36728.89; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="ISAE4"; Value=10952.00; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="CXSE3"; Value=10212.80; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="ABCB4"; Value=9655.48; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="CMIG4"; Value=9554.34; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="CPFE3"; Value=9479.20; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="ALOS3"; Value=6821.06; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="CSUD3"; Value=6542.19; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="SAUD3"; Value=6507.00; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="VBBR3"; Value=6395.84; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="KLBN4"; Value=4369.52; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="FESA4"; Value=3663.33; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="LEVE3"; Value=3505.42; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="PASS3"; Value=1424.40; Class="acao"; Category="acao"
        Bucket="equity"; EconomicRole="equity"
        Credit="unknown"; Indexer=""; Issuer=""; Evidence="observed"
    }

    # ========================================================
    # FIIs / FI-INFRA / FIAGRO
    # ========================================================

    [PSCustomObject]@{
        ID="LVBI11"; Value=13419.12; Class="fii"; Category="Logístico"
        Bucket="real_estate_logistics"; EconomicRole="real_estate"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="BTLG11"; Value=10990.11; Class="fii"; Category="Logístico"
        Bucket="real_estate_logistics"; EconomicRole="real_estate"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="HGRU11"; Value=9925.83; Class="fii"; Category="Híbrido"
        Bucket="real_estate_hybrid"; EconomicRole="real_estate"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="CDII11"; Value=9487.00; Class="fi_infra"
        Category="Infraestrutura (FI-Infra)"
        Bucket="infrastructure"; EconomicRole="infrastructure"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="TRXF11"; Value=8694.00; Class="fii"; Category="Híbrido"
        Bucket="real_estate_hybrid"; EconomicRole="real_estate"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="AFHI11"; Value=8606.60; Class="fii"
        Category="Títulos e Valores Mobiliários"
        Bucket="securities"; EconomicRole="securities"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="CPTI11"; Value=6526.40; Class="fi_infra"
        Category="Infraestrutura (FI-Infra)"
        Bucket="infrastructure"; EconomicRole="infrastructure"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="MANA11"; Value=6373.20; Class="fii"
        Category="Títulos e Valores Mobiliários"
        Bucket="securities"; EconomicRole="securities"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="VGIP11"; Value=5642.24; Class="fii"
        Category="Títulos e Valores Mobiliários"
        Bucket="securities"; EconomicRole="securities"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="HSML11"; Value=5324.80; Class="fii"; Category="Shoppings"
        Bucket="real_estate_shopping"; EconomicRole="real_estate"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="JURO11"; Value=5258.00; Class="fi_infra"
        Category="Infraestrutura (FI-Infra)"
        Bucket="infrastructure"; EconomicRole="infrastructure"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="XPML11"; Value=5132.50; Class="fii"; Category="Shoppings"
        Bucket="real_estate_shopping"; EconomicRole="real_estate"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="PCIP11"; Value=4845.75; Class="fii"; Category="Híbrido"
        Bucket="real_estate_hybrid"; EconomicRole="real_estate"
        Credit="documented"; Indexer="documented"
        Issuer="documented"; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="CRAA11"; Value=4650.00; Class="fiagro"; Category="Fiagro"
        Bucket="fiagro"; EconomicRole="fiagro"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="HGCR11"; Value=4311.00; Class="fii"
        Category="Títulos e Valores Mobiliários"
        Bucket="securities"; EconomicRole="securities"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="RBVA11"; Value=3848.67; Class="fii"; Category="Híbrido"
        Bucket="real_estate_hybrid"; EconomicRole="real_estate"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="ALZR11"; Value=3190.74; Class="fii"; Category="Híbrido"
        Bucket="real_estate_hybrid"; EconomicRole="real_estate"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="BTCI11"; Value=2586.62; Class="fii"
        Category="Títulos e Valores Mobiliários"
        Bucket="securities"; EconomicRole="securities"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="KNRI11"; Value=2479.20; Class="fii"; Category="Híbrido"
        Bucket="real_estate_hybrid"; EconomicRole="real_estate"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="HGBS11"; Value=2366.01; Class="fii"; Category="Shoppings"
        Bucket="real_estate_shopping"; EconomicRole="real_estate"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    # ========================================================
    # RENDA FIXA
    # ========================================================

    [PSCustomObject]@{
        ID="RF-NUBANK-120CDI"; Value=11404.21; Class="renda_fixa"
        Category="CDB"; Bucket="fixed_income"; EconomicRole="fixed_income"
        Credit="issuer_credit"; Indexer="CDI"; Issuer="NuBank"; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="RF-DIGIMAIS-123CDI"; Value=3305.31; Class="renda_fixa"
        Category="CDB"; Bucket="fixed_income"; EconomicRole="fixed_income"
        Credit="issuer_credit"; Indexer="CDI"; Issuer="Banco Digimais"; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="RF-MP-115CDI"; Value=3087.27; Class="renda_fixa"
        Category="CDB"; Bucket="fixed_income"; EconomicRole="fixed_income"
        Credit="issuer_credit"; Indexer="CDI"; Issuer="Mercado Pago"; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="RF-JF-CDI2_60"; Value=454.72; Class="renda_fixa"
        Category="CDB"; Bucket="fixed_income"; EconomicRole="fixed_income"
        Credit="issuer_credit"; Indexer="CDI + spread"; Issuer="J&F Investimentos"; Evidence="observed"
    }

    [PSCustomObject]@{
        ID="RF-MB-BINVEST03"; Value=275.25; Class="renda_fixa"
        Category="CDB"; Bucket="fixed_income"; EconomicRole="fixed_income"
        Credit="issuer_credit"; Indexer="gap"; Issuer="Mercado Bitcoin"; Evidence="gap"
    }

    [PSCustomObject]@{
        ID="RF-MB-JEITTO14"; Value=198.23; Class="renda_fixa"
        Category="CDB"; Bucket="fixed_income"; EconomicRole="fixed_income"
        Credit="issuer_credit"; Indexer="gap"; Issuer="Mercado Bitcoin"; Evidence="gap"
    }

    [PSCustomObject]@{
        ID="RF-MB-ROOFTOP04"; Value=148.29; Class="renda_fixa"
        Category="CDB"; Bucket="fixed_income"; EconomicRole="fixed_income"
        Credit="issuer_credit"; Indexer="gap"; Issuer="Mercado Bitcoin"; Evidence="gap"
    }

    [PSCustomObject]@{
        ID="RF-MB-MULTIPLIKE12"; Value=116.71; Class="renda_fixa"
        Category="CDB"; Bucket="fixed_income"; EconomicRole="fixed_income"
        Credit="issuer_credit"; Indexer="gap"; Issuer="Mercado Bitcoin"; Evidence="gap"
    }

    [PSCustomObject]@{
        ID="RF-MB-JEITTO03"; Value=59.58; Class="renda_fixa"
        Category="CDB"; Bucket="fixed_income"; EconomicRole="fixed_income"
        Credit="issuer_credit"; Indexer="gap"; Issuer="Mercado Bitcoin"; Evidence="gap"
    }

    [PSCustomObject]@{
        ID="RF-BMG-IPCA14_50"; Value=56.63; Class="renda_fixa"
        Category="CDB"; Bucket="fixed_income"; EconomicRole="fixed_income"
        Credit="issuer_credit"; Indexer="IPCA + spread"; Issuer="Banco BMG"; Evidence="observed"
    }

    # ========================================================
    # ETF
    # ========================================================

    [PSCustomObject]@{
        ID="LFTB11"; Value=11718.00; Class="etf"; Category="ETF"
        Bucket="etf"; EconomicRole="etf"
        Credit="unknown"; Indexer="gap"; Issuer=""; Evidence="observed"
    }

    # ========================================================
    # FUNDO
    # ========================================================

    [PSCustomObject]@{
        ID="FMP-FGTS-DAYCOVAL"; Value=6551.93; Class="fundo"
        Category="FMP-FGTS"; Bucket="fund"; EconomicRole="fund"
        Credit="unknown"; Indexer=""; Issuer="Daycoval"; Evidence="observed"
    }
)

# ============================================================
# VALIDAÇÕES
# ============================================================

$ExpectedCount = 46

if ($Positions.Count -ne $ExpectedCount) {
    throw "ERRO: esperado $ExpectedCount posições; encontrado $($Positions.Count)."
}

$UniqueIDs = @(
    $Positions |
    Select-Object -ExpandProperty ID -Unique
)

if ($UniqueIDs.Count -ne $ExpectedCount) {
    throw "ERRO: quantidade de IDs únicos incompatível."
}

$DuplicateIDs = @(
    $Positions |
    Group-Object ID |
    Where-Object { $_.Count -gt 1 }
)

if ($DuplicateIDs.Count -gt 0) {
    throw "ERRO: existem IDs duplicados."
}

$Total = ($Positions | Measure-Object -Property Value -Sum).Sum

if ([math]::Abs($Total - 286845.39) -gt 0.10) {
    throw "ERRO: total divergente. Calculado: $Total"
}

$PCIP = @(
    $Positions |
    Where-Object { $_.ID -eq "PCIP11" }
)

if ($PCIP.Count -ne 1) {
    throw "ERRO: PCIP11 não localizado corretamente."
}

# ============================================================
# BACKUP
# ============================================================

foreach ($File in @($ExposureMapFile, $OverlapFile)) {

    if (Test-Path $File) {

        Copy-Item `
            -LiteralPath $File `
            -Destination (Join-Path $BackupDir (Split-Path $File -Leaf)) `
            -Force
    }
}

# ============================================================
# ECONOMIC EXPOSURE MAP
# ============================================================

$Map = New-Object System.Collections.Generic.List[string]

$Map.Add("---")
$Map.Add("type: economic_exposure_map")
$Map.Add('schema_version: "0.1"')
$Map.Add("scope: portfolio")
$Map.Add("position_count: 46")
$Map.Add("portfolio_value: 286845.39")
$Map.Add("state: current")
$Map.Add("status: active")
$Map.Add("---")
$Map.Add("")
$Map.Add("# Economic Exposure Map v0.1")
$Map.Add("")
$Map.Add("Mapa quantitativo inicial das exposições econômicas reconhecidas na carteira.")
$Map.Add("")
$Map.Add("## Regra metodológica")
$Map.Add("")
$Map.Add("A classificação abaixo utiliza somente categorias explicitamente presentes na base operacional.")
$Map.Add("Ela não representa ainda a exposição econômica final dos ativos subjacentes.")
$Map.Add("")
$Map.Add("## Exposição por Economic Bucket")
$Map.Add("")
$Map.Add("| Bucket | Valor | Peso | Qtde. | Ativos |")
$Map.Add("|---|---:|---:|---:|---|")

$BucketGroups = @(
    $Positions |
    Group-Object Bucket |
    Sort-Object Name
)

foreach ($Group in $BucketGroups) {

    $Value = ($Group.Group | Measure-Object -Property Value -Sum).Sum
    $Weight = ($Value / $Total) * 100

    $ValueText = $Value.ToString("N2")
    $WeightText = $Weight.ToString("N2")

    $IDs = (
        $Group.Group |
        ForEach-Object { $_.ID }
    ) -join ", "

    $Line = "| " +
            $Group.Name +
            " | R$ " +
            $ValueText +
            " | " +
            $WeightText +
            "% | " +
            $Group.Count +
            " | " +
            $IDs +
            " |"

    $Map.Add($Line)
}

$Map.Add("")
$Map.Add("## Exposição por categoria operacional")
$Map.Add("")
$Map.Add("| Classe | Categoria | Valor | Peso | Qtde. |")
$Map.Add("|---|---|---:|---:|---:|")

$CategoryGroups = @(
    $Positions |
    Group-Object Class,Category |
    Sort-Object Name
)

foreach ($Group in $CategoryGroups) {

    $Value = ($Group.Group | Measure-Object -Property Value -Sum).Sum
    $Weight = ($Value / $Total) * 100

    $ValueText = $Value.ToString("N2")
    $WeightText = $Weight.ToString("N2")

    $Parts = $Group.Name -split ", "

    $ClassName = $Parts[0]
    $CategoryName = $Parts[1]

    $Line = "| " +
            $ClassName +
            " | " +
            $CategoryName +
            " | R$ " +
            $ValueText +
            " | " +
            $WeightText +
            "% | " +
            $Group.Count +
            " |"

    $Map.Add($Line)
}

$Map.Add("")
$Map.Add("## Dimensões documentais")
$Map.Add("")
$Map.Add("| Dimensão | Estado atual |")
$Map.Add("|---|---|")
$Map.Add("| Classe | observado |")
$Map.Add("| Categoria operacional | observado |")
$Map.Add("| Economic bucket | classificação operacional |")
$Map.Add("| Indexador | parcial |")
$Map.Add("| Emissor | parcial |")
$Map.Add("| Gestor | gap |")
$Map.Add("| Estratégia detalhada | gap |")
$Map.Add("| Devedor final | gap |")
$Map.Add("| Grupo econômico | gap |")
$Map.Add("| Setor econômico | gap |")
$Map.Add("| Concentração indireta | gap |")

$Map.Add("")
$Map.Add("## Observação sobre PCIP11")
$Map.Add("")
$Map.Add("PCIP11 está classificado no bucket `real_estate_hybrid`.")
$Map.Add("Valor operacional: R$ 4.845,75.")
$Map.Add("Peso na carteira operacional: 1,6893%.")
$Map.Add("Sua exposição econômica detalhada continuará sendo obtida a partir da camada própria do ativo e das respectivas evidências.")

$Map.Add("")
$Map.Add("## Próxima camada")
$Map.Add("")
$Map.Add("A próxima evolução deverá mapear gestores, emissores, devedores, setores, ativos subjacentes e overlap real entre posições.")

Set-Content `
    -LiteralPath $ExposureMapFile `
    -Value $Map `
    -Encoding UTF8

# ============================================================
# OVERLAP FOUNDATION
# ============================================================

$Overlap = New-Object System.Collections.Generic.List[string]

$Overlap.Add("---")
$Overlap.Add("type: overlap_foundation")
$Overlap.Add('schema_version: "0.1"')
$Overlap.Add("scope: portfolio")
$Overlap.Add("position_count: 46")
$Overlap.Add("portfolio_value: 286845.39")
$Overlap.Add("state: current")
$Overlap.Add("status: active")
$Overlap.Add("---")
$Overlap.Add("")
$Overlap.Add("# Overlap Foundation v0.1")
$Overlap.Add("")
$Overlap.Add("Fundação para medir concentração e sobreposição econômica entre as posições.")
$Overlap.Add("")
$Overlap.Add("## O que já pode ser medido")
$Overlap.Add("")
$Overlap.Add("- concentração por classe")
$Overlap.Add("- concentração por economic bucket")
$Overlap.Add("- concentração por categoria operacional")
$Overlap.Add("- concentração por emissor nos instrumentos de renda fixa explicitamente identificados")
$Overlap.Add("")
$Overlap.Add("## O que ainda NÃO deve ser calculado como fato")
$Overlap.Add("")
$Overlap.Add("- sobreposição de imóveis entre FIIs")
$Overlap.Add("- sobreposição de CRIs e devedores")
$Overlap.Add("- concentração por grupo econômico")
$Overlap.Add("- concentração setorial indireta")
$Overlap.Add("- exposição comum a um mesmo devedor")
$Overlap.Add("- overlap entre fundos por ativos subjacentes")
$Overlap.Add("")
$Overlap.Add("Essas métricas exigem evidência documental específica.")
$Overlap.Add("")
$Overlap.Add("## Concentração por Economic Bucket")
$Overlap.Add("")
$Overlap.Add("| Bucket | Valor | Peso |")
$Overlap.Add("|---|---:|---:|")

foreach ($Group in $BucketGroups) {

    $Value = ($Group.Group | Measure-Object -Property Value -Sum).Sum
    $Weight = ($Value / $Total) * 100

    $ValueText = $Value.ToString("N2")
    $WeightText = $Weight.ToString("N2")

    $Line = "| " +
            $Group.Name +
            " | R$ " +
            $ValueText +
            " | " +
            $WeightText +
            "% |"

    $Overlap.Add($Line)
}

$Overlap.Add("")
$Overlap.Add("## Indicadores de risco potencial")
$Overlap.Add("")
$Overlap.Add("| Indicador | Estado |")
$Overlap.Add("|---|---|")
$Overlap.Add("| Concentração acionária | mensurável |")
$Overlap.Add("| Concentração imobiliária | parcialmente mensurável |")
$Overlap.Add("| Concentração em crédito | não consolidada |")
$Overlap.Add("| Concentração por emissor | parcialmente mensurável |")
$Overlap.Add("| Sobreposição FII/FI-Infra | não consolidada |")
$Overlap.Add("| Sobreposição econômica indireta | não consolidada |")

$Overlap.Add("")
$Overlap.Add("## Regra de decisão")
$Overlap.Add("")
$Overlap.Add("Um novo aporte não deve ser avaliado somente pelo peso individual do ativo.")
$Overlap.Add("Deve considerar quanto de exposição nova o ativo realmente acrescenta à carteira.")

$Overlap.Add("")
$Overlap.Add("## Cadeia")
$Overlap.Add("")
$Overlap.Add("Ativo -> Posição -> Bucket -> Exposição Econômica -> Overlap -> Risco -> Retorno -> Decisão")

Set-Content `
    -LiteralPath $OverlapFile `
    -Value $Overlap `
    -Encoding UTF8

# ============================================================
# RESULTADO FINAL
# ============================================================

$PCIPWeight = ($PCIP[0].Value / $Total) * 100

$PCIPValueText = $PCIP[0].Value.ToString("N2")
$PCIPWeightText = $PCIPWeight.ToString("N4")

Write-Host ""
Write-Host "============================================================"
Write-Host "0686 - ECONOMIC EXPOSURE + OVERLAP FOUNDATION"
Write-Host "============================================================"
Write-Host ""

Write-Host "Posições               : $($Positions.Count)"
Write-Host "IDs únicos             : $($UniqueIDs.Count)"

$TotalText = $Total.ToString("N2")

Write-Host "Valor operacional      : R$ $TotalText"
Write-Host "Economic Exposure Map  : PASS"
Write-Host "Overlap Foundation     : PASS"
Write-Host "Backup                 : $BackupDir"

Write-Host ""
Write-Host "CONCENTRAÇÃO POR ECONOMIC BUCKET"
Write-Host "------------------------------------------------------------"

foreach ($Group in $BucketGroups) {

    $Value = ($Group.Group | Measure-Object -Property Value -Sum).Sum
    $Weight = ($Value / $Total) * 100

    $ValueText = $Value.ToString("N2")
    $WeightText = $Weight.ToString("N2")

    $BucketName = $Group.Name.PadRight(28)

    Write-Host "$BucketName R$ $ValueText  $WeightText%"
}

Write-Host ""
Write-Host "PCIP11"
Write-Host "------------------------------------------------------------"
Write-Host "Valor                 : R$ $PCIPValueText"
Write-Host "Peso                  : $PCIPWeightText%"
Write-Host "Bucket                : $($PCIP[0].Bucket)"
Write-Host "Economic Role         : $($PCIP[0].EconomicRole)"
Write-Host "Credit Status         : $($PCIP[0].Credit)"
Write-Host "Indexer Status        : $($PCIP[0].Indexer)"
Write-Host "PCIP11 Mapping        : PASS"

Write-Host ""
Write-Host "ARQUIVOS"
Write-Host "------------------------------------------------------------"
Write-Host "Economic Exposure Map : $ExposureMapFile"
Write-Host "Overlap Foundation    : $OverlapFile"

Write-Host ""
Write-Host "============================================================"
Write-Host "STATUS: 0686 CONCLUIDO"
Write-Host "============================================================"