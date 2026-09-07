$ErrorActionPreference = "Stop"

# ============================================================
# IIP - 0689
# PORTFOLIO OVERLAP MAPPING v0.1
# ASCII ONLY VERSION
# ============================================================

$Repo  = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$Vault = Join-Path $Repo "vault"

$ResearchDir = Join-Path $Vault "07_Research"
$ArchiveDir  = Join-Path $Repo "archive"

$OverlapFile = Join-Path $ResearchDir "01_Portfolio_Overlap_Mapping.md"

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$BackupDir = Join-Path `
    $ArchiveDir `
    "portfolio-overlap-0689-$Timestamp"

# ============================================================
# DIRECTORIES
# ============================================================

New-Item `
    -ItemType Directory `
    -Force `
    -Path $ResearchDir |
    Out-Null

New-Item `
    -ItemType Directory `
    -Force `
    -Path $BackupDir |
    Out-Null

# ============================================================
# CURRENT PORTFOLIO - 46 POSITIONS
# ============================================================

$Portfolio = @(

    # -------------------- STOCKS --------------------

    [PSCustomObject]@{
        ID="BBSE3"
        Value=36728.89
        Manager=""
    }

    [PSCustomObject]@{
        ID="ISAE4"
        Value=10952.00
        Manager=""
    }

    [PSCustomObject]@{
        ID="CXSE3"
        Value=10212.80
        Manager=""
    }

    [PSCustomObject]@{
        ID="ABCB4"
        Value=9655.48
        Manager=""
    }

    [PSCustomObject]@{
        ID="CMIG4"
        Value=9554.34
        Manager=""
    }

    [PSCustomObject]@{
        ID="CPFE3"
        Value=9479.20
        Manager=""
    }

    [PSCustomObject]@{
        ID="ALOS3"
        Value=6821.06
        Manager=""
    }

    [PSCustomObject]@{
        ID="CSUD3"
        Value=6542.19
        Manager=""
    }

    [PSCustomObject]@{
        ID="SAUD3"
        Value=6507.00
        Manager=""
    }

    [PSCustomObject]@{
        ID="VBBR3"
        Value=6395.84
        Manager=""
    }

    [PSCustomObject]@{
        ID="KLBN4"
        Value=4369.52
        Manager=""
    }

    [PSCustomObject]@{
        ID="FESA4"
        Value=3663.33
        Manager=""
    }

    [PSCustomObject]@{
        ID="LEVE3"
        Value=3505.42
        Manager=""
    }

    [PSCustomObject]@{
        ID="PASS3"
        Value=1424.40
        Manager=""
    }

    # -------------------- FIIs --------------------

    [PSCustomObject]@{
        ID="LVBI11"
        Value=13419.12
        Manager="Patria"
    }

    [PSCustomObject]@{
        ID="BTLG11"
        Value=10990.11
        Manager="BTG Pactual"
    }

    [PSCustomObject]@{
        ID="HGRU11"
        Value=9925.83
        Manager="Patria"
    }

    [PSCustomObject]@{
        ID="CDII11"
        Value=9487.00
        Manager="Sparta"
    }

    [PSCustomObject]@{
        ID="TRXF11"
        Value=8694.00
        Manager="TRX"
    }

    [PSCustomObject]@{
        ID="AFHI11"
        Value=8606.60
        Manager=""
    }

    [PSCustomObject]@{
        ID="CPTI11"
        Value=6526.40
        Manager="Capitania"
    }

    [PSCustomObject]@{
        ID="MANA11"
        Value=6373.20
        Manager="Manati/ICM"
    }

    [PSCustomObject]@{
        ID="VGIP11"
        Value=5642.24
        Manager="Valora"
    }

    [PSCustomObject]@{
        ID="HSML11"
        Value=5324.80
        Manager="HSI"
    }

    [PSCustomObject]@{
        ID="JURO11"
        Value=5258.00
        Manager="Sparta"
    }

    [PSCustomObject]@{
        ID="XPML11"
        Value=5132.50
        Manager="XP Asset"
    }

    [PSCustomObject]@{
        ID="PCIP11"
        Value=4845.75
        Manager="Patria"
    }

    [PSCustomObject]@{
        ID="CRAA11"
        Value=4650.00
        Manager="Sparta"
    }

    [PSCustomObject]@{
        ID="HGCR11"
        Value=4311.00
        Manager="Patria"
    }

    [PSCustomObject]@{
        ID="RBVA11"
        Value=3848.67
        Manager="Rio Bravo"
    }

    [PSCustomObject]@{
        ID="ALZR11"
        Value=3190.74
        Manager="Alianza"
    }

    [PSCustomObject]@{
        ID="BTCI11"
        Value=2586.62
        Manager="BTG Pactual"
    }

    [PSCustomObject]@{
        ID="KNRI11"
        Value=2479.20
        Manager="Kinea"
    }

    [PSCustomObject]@{
        ID="HGBS11"
        Value=2366.01
        Manager="Hedge"
    }

    # -------------------- FIXED INCOME --------------------

    [PSCustomObject]@{
        ID="RF-NUBANK-120CDI"
        Value=11404.21
        Manager=""
    }

    [PSCustomObject]@{
        ID="RF-DIGIMAIS-123CDI"
        Value=3305.31
        Manager=""
    }

    [PSCustomObject]@{
        ID="RF-MP-115CDI"
        Value=3087.27
        Manager=""
    }

    [PSCustomObject]@{
        ID="RF-JF-CDI2_60"
        Value=454.72
        Manager=""
    }

    [PSCustomObject]@{
        ID="RF-MB-BINVEST03"
        Value=275.25
        Manager=""
    }

    [PSCustomObject]@{
        ID="RF-MB-JEITTO14"
        Value=198.23
        Manager=""
    }

    [PSCustomObject]@{
        ID="RF-MB-ROOFTOP04"
        Value=148.29
        Manager=""
    }

    [PSCustomObject]@{
        ID="RF-MB-MULTIPLIKE12"
        Value=116.71
        Manager=""
    }

    [PSCustomObject]@{
        ID="RF-MB-JEITTO03"
        Value=59.58
        Manager=""
    }

    [PSCustomObject]@{
        ID="RF-BMG-IPCA14_50"
        Value=56.63
        Manager=""
    }

    # -------------------- ETF --------------------

    [PSCustomObject]@{
        ID="LFTB11"
        Value=11718.00
        Manager="Investo"
    }

    # -------------------- FUND --------------------

    [PSCustomObject]@{
        ID="FMP-FGTS-DAYCOVAL"
        Value=6551.93
        Manager="Daycoval"
    }
)

# ============================================================
# BASIC VALIDATION
# ============================================================

$ExpectedCount = 46

if ($Portfolio.Count -ne $ExpectedCount) {
    throw "ERROR: expected $ExpectedCount positions. Found $($Portfolio.Count)."
}

$PortfolioIDs = @(
    $Portfolio |
    Select-Object -ExpandProperty ID -Unique
)

if ($PortfolioIDs.Count -ne $ExpectedCount) {
    throw "ERROR: duplicate portfolio IDs detected."
}

$DuplicateIDs = @(
    $Portfolio |
    Group-Object ID |
    Where-Object {
        $_.Count -gt 1
    }
)

if ($DuplicateIDs.Count -gt 0) {
    throw "ERROR: duplicated IDs detected."
}

$PortfolioTotal = (
    $Portfolio |
    Measure-Object -Property Value -Sum
).Sum

if ([math]::Abs($PortfolioTotal - 286845.39) -gt 0.10) {
    throw "ERROR: portfolio total is inconsistent."
}

$PCIP = @(
    $Portfolio |
    Where-Object {
        $_.ID -eq "PCIP11"
    }
)

if ($PCIP.Count -ne 1) {
    throw "ERROR: PCIP11 not found."
}

# ============================================================
# MANAGER CONCENTRATION
# ============================================================

$ManagerGroups = @(
    $Portfolio |
    Where-Object {
        -not [string]::IsNullOrWhiteSpace($_.Manager)
    } |
    Group-Object Manager |
    Sort-Object Name
)

# ============================================================
# PATRIA
# ============================================================

$PatriaPositions = @(
    $Portfolio |
    Where-Object {
        $_.Manager -eq "Patria"
    }
)

$PatriaValue = (
    $PatriaPositions |
    Measure-Object -Property Value -Sum
).Sum

$PatriaWeight = (
    $PatriaValue /
    $PortfolioTotal
) * 100

# ============================================================
# SPARTA
# ============================================================

$SpartaPositions = @(
    $Portfolio |
    Where-Object {
        $_.Manager -eq "Sparta"
    }
)

$SpartaValue = (
    $SpartaPositions |
    Measure-Object -Property Value -Sum
).Sum

$SpartaWeight = (
    $SpartaValue /
    $PortfolioTotal
) * 100

# ============================================================
# BTG PACTUAL
# ============================================================

$BTGPositions = @(
    $Portfolio |
    Where-Object {
        $_.Manager -eq "BTG Pactual"
    }
)

$BTGValue = (
    $BTGPositions |
    Measure-Object -Property Value -Sum
).Sum

$BTGWeight = (
    $BTGValue /
    $PortfolioTotal
) * 100

# ============================================================
# PCIP11 UNDERLYING FIIs
# ============================================================

$PCIPUnderlyingFIIs = @(

    [PSCustomObject]@{
        Ticker="MVBI11"
        PCIPWeight=3.2
    }

    [PSCustomObject]@{
        Ticker="GARE11"
        PCIPWeight=1.2
    }

    [PSCustomObject]@{
        Ticker="VRTM11"
        PCIPWeight=0.9
    }

    [PSCustomObject]@{
        Ticker="MCRE11"
        PCIPWeight=0.8
    }

    [PSCustomObject]@{
        Ticker="HREC11"
        PCIPWeight=0.7
    }

    [PSCustomObject]@{
        Ticker="RECD11"
        PCIPWeight=0.3
    }

    [PSCustomObject]@{
        Ticker="SPXS11"
        PCIPWeight=0.2
    }

    [PSCustomObject]@{
        Ticker="CYCR11"
        PCIPWeight=0.04
    }
)

# ============================================================
# DIRECT FII OVERLAP TEST
# ============================================================

$DirectFIIOverlap = @()

foreach ($Underlying in $PCIPUnderlyingFIIs) {

    $Found = @(
        $Portfolio |
        Where-Object {
            $_.ID -eq $Underlying.Ticker
        }
    )

    if ($Found.Count -gt 0) {

        $DirectFIIOverlap += [PSCustomObject]@{
            Ticker = $Underlying.Ticker
            PCIPWeight = $Underlying.PCIPWeight
            PortfolioValue = $Found[0].Value
        }
    }
}

# ============================================================
# ECONOMIC ADJACENCY
# ============================================================

$Adjacency = @(

    [PSCustomObject]@{
        Theme="Retail"
        PCIPExposure="20 percent of CRI portfolio"
        PortfolioAssets="ALOS3"
        Relationship="economic_adjacency"
        Evidence="partial"
    }

    [PSCustomObject]@{
        Theme="Shopping"
        PCIPExposure="7 percent of CRI portfolio"
        PortfolioAssets="ALOS3;HSML11;XPML11;HGBS11"
        Relationship="economic_adjacency"
        Evidence="partial"
    }

    [PSCustomObject]@{
        Theme="Energy"
        PCIPExposure="energy segment exists in CRI portfolio"
        PortfolioAssets="ISAE4;CMIG4;CPFE3"
        Relationship="economic_adjacency"
        Evidence="partial"
    }

    [PSCustomObject]@{
        Theme="Logistics"
        PCIPExposure="9 percent of CRI portfolio"
        PortfolioAssets="LVBI11;BTLG11"
        Relationship="economic_adjacency"
        Evidence="partial"
    }

    [PSCustomObject]@{
        Theme="Construction Finance"
        PCIPExposure="13 percent of CRI portfolio"
        PortfolioAssets="none directly identified"
        Relationship="economic_adjacency"
        Evidence="observed"
    }
)

# ============================================================
# BACKUP
# ============================================================

if (Test-Path -LiteralPath $OverlapFile) {

    Copy-Item `
        -LiteralPath $OverlapFile `
        -Destination (
            Join-Path `
                $BackupDir `
                "01_Portfolio_Overlap_Mapping.md"
        ) `
        -Force
}

# ============================================================
# BUILD MARKDOWN
# ============================================================

$Lines = New-Object System.Collections.Generic.List[string]

$Lines.Add("---")
$Lines.Add("type: portfolio_overlap_mapping")
$Lines.Add('schema_version: "0.1"')
$Lines.Add("scope: portfolio")
$Lines.Add("portfolio_value: 286845.39")
$Lines.Add("position_count: 46")
$Lines.Add("state: current")
$Lines.Add("status: active")
$Lines.Add("---")

$Lines.Add("")
$Lines.Add("# Portfolio Overlap Mapping v0.1")
$Lines.Add("")

$Lines.Add(
    "Mapa inicial de sobreposicoes documentais e candidatos de sobreposicao economica."
)

$Lines.Add("")
$Lines.Add("## Regra metodologica")
$Lines.Add("")

$Lines.Add(
    "Overlap confirmado exige uma identidade comum comprovada."
)

$Lines.Add(
    "Adjacency representa exposicao a uma atividade economica semelhante, mas nao prova o mesmo ativo, devedor, emissor ou grupo economico."
)

# ============================================================
# MANAGER TABLE
# ============================================================

$Lines.Add("")
$Lines.Add("## 1. Concentracao por gestora")
$Lines.Add("")

$Lines.Add(
    "| Gestora | Posicoes | Valor | Peso |"
)

$Lines.Add(
    "|---|---|---:|---:|"
)

foreach ($Group in $ManagerGroups) {

    $Value = (
        $Group.Group |
        Measure-Object -Property Value -Sum
    ).Sum

    $Weight = (
        $Value /
        $PortfolioTotal
    ) * 100

    $IDs = (
        $Group.Group |
        ForEach-Object {
            $_.ID
        }
    ) -join ", "

    $ValueText = $Value.ToString("N2")
    $WeightText = $Weight.ToString("N2")

    $Lines.Add(
        "| $($Group.Name) | $IDs | R$ $ValueText | $WeightText% |"
    )
}

$Lines.Add("")
$Lines.Add("A concentracao por gestora representa concentracao operacional/gerencial. Ela nao equivale a concentracao economica dos ativos subjacentes.")

# ============================================================
# PCIP11
# ============================================================

$PCIPWeight = (
    $PCIP[0].Value /
    $PortfolioTotal
) * 100

$Lines.Add("")
$Lines.Add("## 2. PCIP11 dentro da carteira")
$Lines.Add("")

$Lines.Add(
    "| Metrica | Valor |"
)

$Lines.Add(
    "|---|---:|"
)

$Lines.Add(
    "| Valor da posicao | R$ $($PCIP[0].Value.ToString("N2")) |"
)

$Lines.Add(
    "| Peso na carteira | $($PCIPWeight.ToString("N4"))% |"
)

$Lines.Add(
    "| Gestora | Patria |"
)

$Lines.Add(
    "| Peso sob Patria | $($PatriaWeight.ToString("N2"))% |"
)

# ============================================================
# DIRECT FII OVERLAP
# ============================================================

$Lines.Add("")
$Lines.Add("## 3. Sobreposicao direta de FIIs")
$Lines.Add("")

$Lines.Add(
    "| FII subjacente do PCIP11 | Peso no PCIP11 | Presente na carteira |"
)

$Lines.Add(
    "|---|---:|---|"
)

if ($DirectFIIOverlap.Count -eq 0) {

    $Lines.Add(
        "| Nenhum overlap direto identificado | N/A | N/A |"
    )

}
else {

    foreach ($Item in $DirectFIIOverlap) {

        $Lines.Add(
            "| $($Item.Ticker) | $($Item.PCIPWeight)% | R$ $($Item.PortfolioValue.ToString("N2")) |"
        )
    }
}

$Lines.Add("")
$Lines.Add(
    "O relatorio de julho/2026 identifica oito FIIs na carteira do PCIP11. Nesta carteira atual nenhum desses oito tickers foi encontrado como posicao direta."
)

# ============================================================
# ECONOMIC ADJACENCY
# ============================================================

$Lines.Add("")
$Lines.Add("## 4. Candidatos de sobreposicao economica")
$Lines.Add("")

$Lines.Add(
    "| Tema | Exposicao PCIP11 | Ativos da carteira | Relacao | Status |"
)

$Lines.Add(
    "|---|---|---|---|---|"
)

foreach ($Item in $Adjacency) {

    $Lines.Add(
        "| $($Item.Theme) | $($Item.PCIPExposure) | $($Item.PortfolioAssets) | $($Item.Relationship) | $($Item.Evidence) |"
    )
}

# ============================================================
# NOT CONFIRMED
# ============================================================

$Lines.Add("")
$Lines.Add("## 5. Dimensoes ainda nao confirmadas")
$Lines.Add("")

$Lines.Add("- mesmo devedor")
$Lines.Add("- mesma operacao de credito")
$Lines.Add("- mesmo imovel")
$Lines.Add("- mesmo grupo economico")
$Lines.Add("- mesmo emissor de CRI")
$Lines.Add("- mesma contraparte")
$Lines.Add("- exposicao economica identica")

$Lines.Add("")
$Lines.Add(
    "Estas dimensoes somente serao elevadas de candidato para overlap confirmado quando houver evidencia especifica."
)

# ============================================================
# NEXT STEP
# ============================================================

$Lines.Add("")
$Lines.Add("## 6. Proxima evolucao")
$Lines.Add("")

$Lines.Add(
    "Mapear devedores, emissores, indexadores e ativos subjacentes dos fundos de credito da carteira."
)

$Lines.Add(
    "Prioridade: VGIP11, AFHI11, HGCR11, BTCI11 e MANA11."
)

$Lines.Add("")
$Lines.Add("## 7. Regra de decisao")
$Lines.Add("")

$Lines.Add(
    "Um novo aporte deve ser avaliado pela exposicao nova que acrescenta a carteira, e nao apenas pelo seu peso nominal."
)

# ============================================================
# WRITE FILE
# ============================================================

Set-Content `
    -LiteralPath $OverlapFile `
    -Value $Lines `
    -Encoding UTF8

# ============================================================
# FINAL OUTPUT
# ============================================================

Write-Host ""
Write-Host "============================================================"
Write-Host "0689 - PORTFOLIO OVERLAP MAPPING"
Write-Host "============================================================"
Write-Host ""

Write-Host "Positions             : $($Portfolio.Count)"
Write-Host "Unique IDs            : $($PortfolioIDs.Count)"

$PortfolioTotalText = $PortfolioTotal.ToString("N2")

Write-Host "Portfolio value       : R$ $PortfolioTotalText"
Write-Host "Overlap Mapping       : PASS"
Write-Host "Output file           : $OverlapFile"
Write-Host "Backup                : $BackupDir"

Write-Host ""
Write-Host "MANAGER CONCENTRATION"
Write-Host "------------------------------------------------------------"

Write-Host "Patria positions      : $($PatriaPositions.Count)"
Write-Host "Patria value          : R$ $($PatriaValue.ToString("N2"))"
Write-Host "Patria weight         : $($PatriaWeight.ToString("N2"))%"

Write-Host ""

Write-Host "Sparta positions      : $($SpartaPositions.Count)"
Write-Host "Sparta value          : R$ $($SpartaValue.ToString("N2"))"
Write-Host "Sparta weight         : $($SpartaWeight.ToString("N2"))%"

Write-Host ""

Write-Host "BTG positions         : $($BTGPositions.Count)"
Write-Host "BTG value             : R$ $($BTGValue.ToString("N2"))"
Write-Host "BTG weight            : $($BTGWeight.ToString("N2"))%"

Write-Host ""
Write-Host "PCIP11"
Write-Host "------------------------------------------------------------"

Write-Host "Portfolio weight      : $($PCIPWeight.ToString("N4"))%"
Write-Host "Manager               : Patria"
Write-Host "Direct FII overlap    : $($DirectFIIOverlap.Count)"

Write-Host ""
Write-Host "ECONOMIC ADJACENCY"
Write-Host "------------------------------------------------------------"

foreach ($Item in $Adjacency) {

    Write-Host (
        "$($Item.Theme.PadRight(24)) -> $($Item.PortfolioAssets)"
    )
}

Write-Host ""
Write-Host "============================================================"
Write-Host "STATUS: 0689 COMPLETED"
Write-Host "============================================================"