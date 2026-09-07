$ErrorActionPreference = "Stop"

Write-Host "============================================================"
Write-Host " IIP - PORTFOLIO POSITION LOAD v0.1"
Write-Host "============================================================"

$vaultRoot = (Get-Location).Path
$portfolioRoot = Join-Path $vaultRoot "02_Portfolio"

New-Item -ItemType Directory -Path $portfolioRoot -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$backupRoot = Join-Path `
    $vaultRoot `
    "archive\portfolio-pre-position-load-v0.1-$timestamp"

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

Write-Host ""
Write-Host "Backup:"
Write-Host $backupRoot

# ============================================================
# DADOS DA CARTEIRA
# ============================================================

$positions = @(

    # ==================== AÇÕES ====================

    [PSCustomObject]@{
        Id="BBSE3"; Nome="BBSE3"; Classe="acao"
        Quantidade=881; PM=33.81; PrecoAtual=41.69; Valor=36728.89
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="ISAE4"; Nome="ISAE4"; Classe="acao"
        Quantidade=400; PM=24.40; PrecoAtual=27.38; Valor=10952.00
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="CXSE3"; Nome="CXSE3"; Classe="acao"
        Quantidade=520; PM=11.25; PrecoAtual=19.64; Valor=10212.80
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="ABCB4"; Nome="ABCB4"; Classe="acao"
        Quantidade=398; PM=25.49; PrecoAtual=24.26; Valor=9655.48
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="CMIG4"; Nome="CMIG4"; Classe="acao"
        Quantidade=867; PM=10.88; PrecoAtual=11.02; Valor=9554.34
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="CPFE3"; Nome="CPFE3"; Classe="acao"
        Quantidade=205; PM=34.86; PrecoAtual=46.24; Valor=9479.20
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="ALOS3"; Nome="ALOS3"; Classe="acao"
        Quantidade=239; PM=28.67; PrecoAtual=28.54; Valor=6821.06
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="CSUD3"; Nome="CSUD3"; Classe="acao"
        Quantidade=463; PM=16.80; PrecoAtual=14.13; Valor=6542.19
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="SAUD3"; Nome="SAUD3"; Classe="acao"
        Quantidade=450; PM=11.32; PrecoAtual=14.46; Valor=6507.00
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="VBBR3"; Nome="VBBR3"; Classe="acao"
        Quantidade=176; PM=22.61; PrecoAtual=36.34; Valor=6395.84
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="KLBN4"; Nome="KLBN4"; Classe="acao"
        Quantidade=1132; PM=3.44; PrecoAtual=3.86; Valor=4369.52
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="FESA4"; Nome="FESA4"; Classe="acao"
        Quantidade=653; PM=8.38; PrecoAtual=5.61; Valor=3663.33
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="LEVE3"; Nome="LEVE3"; Classe="acao"
        Quantidade=106; PM=33.17; PrecoAtual=33.07; Valor=3505.42
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="PASS3"; Nome="PASS3"; Classe="acao"
        Quantidade=60; PM=25.73; PrecoAtual=23.74; Valor=1424.40
        PesoAlvo=""
    },

    # ==================== FIIs ====================

    [PSCustomObject]@{
        Id="LVBI11"; Nome="LVBI11"; Classe="fii"
        Quantidade=136; PM=110.99; PrecoAtual=98.67; Valor=13419.12
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="BTLG11"; Nome="BTLG11"; Classe="fii"
        Quantidade=111; PM=98.47; PrecoAtual=99.01; Valor=10990.11
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="HGRU11"; Nome="HGRU11"; Classe="fii"
        Quantidade=87; PM=118.65; PrecoAtual=114.09; Valor=9925.83
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="CDII11"; Nome="CDII11"; Classe="fi-infra"
        Quantidade=100; PM=101.56; PrecoAtual=94.87; Valor=9487.00
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="TRXF11"; Nome="TRXF11"; Classe="fii"
        Quantidade=115; PM=101.74; PrecoAtual=75.60; Valor=8694.00
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="AFHI11"; Nome="AFHI11"; Classe="fii"
        Quantidade=92; PM=92.49; PrecoAtual=93.55; Valor=8606.60
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="CPTI11"; Nome="CPTI11"; Classe="fi-infra"
        Quantidade=80; PM=97.05; PrecoAtual=81.58; Valor=6526.40
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="MANA11"; Nome="MANA11"; Classe="fii"
        Quantidade=705; PM=8.64; PrecoAtual=9.04; Valor=6373.20
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="VGIP11"; Nome="VGIP11"; Classe="fii"
        Quantidade=76; PM=98.54; PrecoAtual=74.24; Valor=5642.24
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="HSML11"; Nome="HSML11"; Classe="fii"
        Quantidade=65; PM=88.24; PrecoAtual=81.92; Valor=5324.80
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="JURO11"; Nome="JURO11"; Classe="fi-infra"
        Quantidade=55; PM=96.13; PrecoAtual=95.60; Valor=5258.00
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="XPML11"; Nome="XPML11"; Classe="fii"
        Quantidade=50; PM=108.12; PrecoAtual=102.65; Valor=5132.50
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="PCIP11"; Nome="PCIP11"; Classe="fii"
        Quantidade=65; PM=100.01; PrecoAtual=74.55; Valor=4845.75
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="CRAA11"; Nome="CRAA11"; Classe="fiagro"
        Quantidade=50; PM=95.92; PrecoAtual=93.00; Valor=4650.00
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="HGCR11"; Nome="HGCR11"; Classe="fii"
        Quantidade=45; PM=93.00; PrecoAtual=95.80; Valor=4311.00
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="RBVA11"; Nome="RBVA11"; Classe="fii"
        Quantidade=447; PM=9.11; PrecoAtual=8.61; Valor=3848.67
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="ALZR11"; Nome="ALZR11"; Classe="fii"
        Quantidade=321; PM=10.02; PrecoAtual=9.94; Valor=3190.74
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="BTCI11"; Nome="BTCI11"; Classe="fii"
        Quantidade=283; PM=9.21; PrecoAtual=9.14; Valor=2586.62
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="KNRI11"; Nome="KNRI11"; Classe="fii"
        Quantidade=16; PM=145.56; PrecoAtual=154.95; Valor=2479.20
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="HGBS11"; Nome="HGBS11"; Classe="fii"
        Quantidade=127; PM=20.66; PrecoAtual=18.63; Valor=2366.01
        PesoAlvo=""
    },

    # ==================== RENDA FIXA ====================

    [PSCustomObject]@{
        Id="RF-NUBANK-120CDI"; Nome="CDB NuBank 120% CDI"; Classe="renda_fixa"
        Quantidade=""; PM=""; PrecoAtual=""; Valor=11404.21
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="RF-DIGIMAIS-123CDI"; Nome="CDB Banco Digimais 123% CDI"; Classe="renda_fixa"
        Quantidade=""; PM=""; PrecoAtual=""; Valor=3305.31
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="RF-MP-115CDI"; Nome="CDB Mercado Pago 115% CDI"; Classe="renda_fixa"
        Quantidade=""; PM=""; PrecoAtual=""; Valor=3087.27
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="RF-JF-CDI2_60"; Nome="CDB J&F Investimentos CDI + 2,60%"; Classe="renda_fixa"
        Quantidade=""; PM=""; PrecoAtual=""; Valor=454.72
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="RF-MB-BINVEST03"; Nome="CDB Mercado Bitcoin BINVEST 03"; Classe="renda_fixa"
        Quantidade=""; PM=""; PrecoAtual=""; Valor=275.25
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="RF-MB-JEITTO14"; Nome="CDB Mercado Bitcoin JEITTO 14"; Classe="renda_fixa"
        Quantidade=""; PM=""; PrecoAtual=""; Valor=198.23
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="RF-MB-ROOFTOP04"; Nome="CDB Mercado Bitcoin ROOFTOP 04"; Classe="renda_fixa"
        Quantidade=""; PM=""; PrecoAtual=""; Valor=148.29
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="RF-MB-MULTIPLIKE12"; Nome="CDB Mercado Bitcoin MULTIPLIKE 12"; Classe="renda_fixa"
        Quantidade=""; PM=""; PrecoAtual=""; Valor=116.71
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="RF-MB-JEITTO03"; Nome="CDB Mercado Bitcoin JEITTO 03"; Classe="renda_fixa"
        Quantidade=""; PM=""; PrecoAtual=""; Valor=59.58
        PesoAlvo=""
    },
    [PSCustomObject]@{
        Id="RF-BMG-IPCA14_50"; Nome="CDB Banco BMG IPCA + 14,50%"; Classe="renda_fixa"
        Quantidade=""; PM=""; PrecoAtual=""; Valor=56.63
        PesoAlvo=""
    },

    # ==================== ETF ====================

    [PSCustomObject]@{
        Id="LFTB11"; Nome="LFTB11"; Classe="etf"
        Quantidade=93; PM=120.72; PrecoAtual=126.00; Valor=11718.00
        PesoAlvo=""
    },

    # ==================== FUNDO ====================

    [PSCustomObject]@{
        Id="FMP-FGTS-DAYCOVAL"
        Nome="DAYCOVAL FUNDO MÚTUO DE PRIVATIZAÇÃO DO FGTS ELETROBRAS (FMP-FGTS)"
        Classe="fundo"
        Quantidade=3639.96
        PM=1.00
        PrecoAtual=1.80
        Valor=6551.93
        PesoAlvo=""
    }
)

Write-Host ""
Write-Host "Posições carregadas no script: $($positions.Count)"

# ============================================================
# BACKUP DOS ARQUIVOS EXISTENTES
# ============================================================

$currentPath = Join-Path $portfolioRoot "Current.md"
$registryPath = Join-Path $portfolioRoot "Position Registry.md"

foreach ($path in @($currentPath, $registryPath)) {

    if (Test-Path -LiteralPath $path -PathType Leaf) {

        Copy-Item `
            -LiteralPath $path `
            -Destination (Join-Path $backupRoot (Split-Path $path -Leaf)) `
            -Force

        Write-Host "BACKUP: $path"
    }
}

# ============================================================
# CALCULO DOS PESOS
# ============================================================

$totalValue = ($positions | Measure-Object -Property Valor -Sum).Sum

Write-Host ""
Write-Host "Valor operacional calculado a partir das posições:"
Write-Host ("R$ {0:N2}" -f $totalValue)

foreach ($position in $positions) {

    $position | Add-Member `
        -NotePropertyName Peso `
        -NotePropertyValue (($position.Valor / $totalValue) * 100)
}

# ============================================================
# CURRENT.MD
# ============================================================

$lines = @()

$lines += "---"
$lines += "type: portfolio"
$lines += "state: current"
$lines += "schema_version: `"0.1`""
$lines += "snapshot_basis: position_values"
$lines += "source: Investidor10"
$lines += "---"
$lines += ""
$lines += "# Carteira Atual"
$lines += ""
$lines += "> Snapshot operacional da carteira. Não substitui o histórico."
$lines += ""
$lines += "## Resumo"
$lines += ""
$lines += "- Posições: $($positions.Count)"
$lines += "- Valor operacional calculado: R$ $("{0:N2}" -f $totalValue)"
$lines += "- Peso alvo: não informado nesta carga"
$lines += "- Fonte: Investidor10"
$lines += ""
$lines += "| Ativo | Classe | Quantidade | PM | Preço atual | Valor | Peso | Peso alvo | Status |"
$lines += "|---|---|---:|---:|---:|---:|---:|---:|---|"

foreach ($p in $positions) {

    $qtd = if ($p.Quantidade -eq "") { "" } else { "{0:N4}" -f [double]$p.Quantidade }
    $pm = if ($p.PM -eq "") { "" } else { "R$ {0:N2}" -f [double]$p.PM }
    $preco = if ($p.PrecoAtual -eq "") { "" } else { "R$ {0:N2}" -f [double]$p.PrecoAtual }

    $lines += "| $($p.Nome) | $($p.Classe) | $qtd | $pm | $preco | R$ $("{0:N2}" -f $p.Valor) | $("{0:N2}" -f $p.Peso)% | | active |"
}

Set-Content `
    -LiteralPath $currentPath `
    -Value ($lines -join "`r`n") `
    -Encoding UTF8

Write-Host "CREATED/UPDATED: $currentPath"

# ============================================================
# POSITION REGISTRY
# ============================================================

$registry = @()

$registry += "---"
$registry += "type: position_registry"
$registry += "scope: portfolio"
$registry += "schema_version: `"0.1`""
$registry += "state: current"
$registry += "source: Investidor10"
$registry += "---"
$registry += ""
$registry += "# Portfolio Position Registry"
$registry += ""
$registry += "Registro estruturado das posições atuais."
$registry += ""
$registry += "A coluna Peso é calculada pelo IIP usando o valor individual da posição dividido pelo valor operacional total calculado a partir das posições."
$registry += ""
$registry += "## Posições"
$registry += ""
$registry += "| ID | Nome | Classe | Quantidade | PM | Preço atual | Valor | Peso | Peso alvo |"
$registry += "|---|---|---|---:|---:|---:|---:|---:|---:|"

foreach ($p in $positions) {

    $qtd = if ($p.Quantidade -eq "") { "" } else { "{0:N4}" -f [double]$p.Quantidade }
    $pm = if ($p.PM -eq "") { "" } else { "{0:N2}" -f [double]$p.PM }
    $preco = if ($p.PrecoAtual -eq "") { "" } else { "{0:N2}" -f [double]$p.PrecoAtual }

    $registry += "| $($p.Id) | $($p.Nome) | $($p.Classe) | $qtd | $pm | $preco | $("{0:N2}" -f $p.Valor) | $("{0:N2}" -f $p.Peso)% | |"
}

$registry += ""
$registry += "## Regras"
$registry += ""
$registry += "1. Peso alvo permanece vazio enquanto não existir política formal de alocação."
$registry += "2. Valores da posição individual prevalecem sobre totais resumidos da fonte."
$registry += "3. Diferenças entre totais da categoria e soma das posições devem permanecer rastreáveis."
$registry += "4. Não transformar esta fotografia em histórico imutável; snapshots futuros serão adicionados separadamente."

Set-Content `
    -LiteralPath $registryPath `
    -Value ($registry -join "`r`n") `
    -Encoding UTF8

Write-Host "CREATED/UPDATED: $registryPath"

# ============================================================
# MANIFEST
# ============================================================

$manifest = Join-Path $backupRoot "POSITION_LOAD_MANIFEST.txt"

@"
IIP Portfolio Position Load v0.1

Posições: $($positions.Count)
Valor operacional calculado: R$ $("{0:N2}" -f $totalValue)
Fonte: Investidor10

Arquivos:
02_Portfolio\Current.md
02_Portfolio\Position Registry.md
"@ |
Set-Content -LiteralPath $manifest -Encoding UTF8

Write-Host ""
Write-Host "============================================================"
Write-Host " RESULTADO"
Write-Host "============================================================"
Write-Host "RESULTADO: PASS"
Write-Host "Portfolio Position Load v0.1 concluído"
Write-Host "Backup: $backupRoot"
