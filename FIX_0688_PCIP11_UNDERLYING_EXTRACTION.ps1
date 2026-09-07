$ErrorActionPreference = "Stop"

# ============================================================
# IIP - 0688
# PCIP11 UNDERLYING EXPOSURE EXTRACTION v0.1
# ============================================================

$Repo  = "D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1"
$Vault = Join-Path $Repo "vault"

$ExposureDir  = Join-Path $Vault "06_Exposures"
$UnderlyingDir = Join-Path $ExposureDir "01_Underlying"
$EvidenceDir  = Join-Path $Vault "04_Evidence"
$PCIPEvidenceDir = Join-Path $EvidenceDir "PCIP11"
$ArchiveDir   = Join-Path $Repo "archive"

$UnderlyingFile = Join-Path $UnderlyingDir "PCIP11 - Underlying Exposure.md"
$EvidenceFile   = Join-Path $PCIPEvidenceDir "EV-PCIP11-RMG-20260731-UNDERLYING.md"

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $ArchiveDir "pcip11-underlying-0688-$Timestamp"

# ============================================================
# DIRETÓRIOS
# ============================================================

New-Item -ItemType Directory -Force -Path $UnderlyingDir | Out-Null
New-Item -ItemType Directory -Force -Path $PCIPEvidenceDir | Out-Null
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

# ============================================================
# FONTE CANÔNICA
# ============================================================

$Source = "PCIP11_rmg_20082026.pdf"
$AsOf = "2026-07-31"

# ============================================================
# DADOS CONSOLIDADOS OBSERVADOS
# ============================================================

$Summary = [PSCustomObject]@{
    PL_Millions = 1572.8
    MarketValue_Millions = 1292.5
    NAV_Per_Share = 92.45
    MarketPrice = 75.98
    PVP = 0.82
    CRI_And_Structured_PctPL = 85.9
    FII_PctPL = 7.3
    Cash_PctPL = 6.8
    TotalAssets_PctPL = 93.2
    CRI_Count = 83
    StructuredOperation_Count = 5
    PortfolioYield = 16.6
    PortfolioIPCAReference = 10.9
    PortfolioDuration = 3.5
    PortfolioSpread = 2.4
}

$Indexers = @(
    [PSCustomObject]@{Indexer="IPCA"; Weight=93; Rate="IPCA + 10,5% a.a."}
    [PSCustomObject]@{Indexer="CDI"; Weight=4; Rate="CDI + 10,5% a.a."}
    [PSCustomObject]@{Indexer="IGP-M"; Weight=3; Rate="IGP-M + 10,9% a.a."}
    [PSCustomObject]@{Indexer="Prefixado"; Weight=1; Rate="14,2% a.a."}
)

$Segments = @(
    [PSCustomObject]@{Segment="Varejo"; Weight=20}
    [PSCustomObject]@{Segment="Pulverizado"; Weight=17}
    [PSCustomObject]@{Segment="Financiamento a Construção"; Weight=13}
    [PSCustomObject]@{Segment="Logística"; Weight=9}
    [PSCustomObject]@{Segment="Loteamento"; Weight=8}
    [PSCustomObject]@{Segment="Shopping"; Weight=7}
    [PSCustomObject]@{Segment="Educacional"; Weight=7}
    [PSCustomObject]@{Segment="Outros"; Weight=19}
)

# ============================================================
# PRINCIPAIS CRIs OBSERVADOS
# ============================================================

$CRI = @(

    [PSCustomObject]@{
        Rank=1
        Name="CRI Cidade Matarazzo IPCA B"
        MTM=66.4
        PLPct=4.2
        Segment="Varejo"
        UF="SP"
        Issuer="Opea"
        Indexer="IPCA"
        EmissionRate=9.5
        AcquisitionRate=9.5
        MTMRate=11.8
        Duration=4.48
        Maturity="jun-40"
        LTV=50.0
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=2
        Name="CRI Cogna Venâncio"
        MTM=50.6
        PLPct=3.2
        Segment="Educacional"
        UF="DF"
        Issuer="Riza"
        Indexer="IPCA"
        EmissionRate=6.0
        AcquisitionRate=6.3
        MTMRate=11.5
        Duration=3.80
        Maturity="jun-35"
        LTV=77.4
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=3
        Name="CRI MRV Flex"
        MTM=43.4
        PLPct=2.8
        Segment="Pulverizado"
        UF=""
        Issuer="Opea"
        Indexer="IPCA"
        EmissionRate=11.2
        AcquisitionRate=11.2
        MTMRate=11.3
        Duration=5.74
        Maturity="jul-35"
        LTV=88.0
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=4
        Name="CRI Buriti"
        MTM=42.1
        PLPct=2.7
        Segment="Loteamento"
        UF="TO, PA, BA"
        Issuer="Riza"
        Indexer="IPCA"
        EmissionRate=9.0
        AcquisitionRate=9.1
        MTMRate=9.6
        Duration=2.32
        Maturity="nov-31"
        LTV=57.1
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=5
        Name="CRI BARI IPCA Sr."
        MTM=41.8
        PLPct=2.7
        Segment="Pulverizado"
        UF=""
        Issuer="Bari"
        Indexer="IPCA"
        EmissionRate=8.8
        AcquisitionRate=8.8
        MTMRate=9.1
        Duration=2.84
        Maturity="out-40"
        LTV=59.0
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=6
        Name="CRI Yduqs RJ"
        MTM=38.5
        PLPct=2.4
        Segment="Educacional"
        UF="RJ"
        Issuer="Bari"
        Indexer="IPCA"
        EmissionRate=8.2
        AcquisitionRate=8.8
        MTMRate=8.7
        Duration=2.61
        Maturity="fev-32"
        LTV=65.0
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=7
        Name="CRI Airport Town"
        MTM=36.7
        PLPct=2.3
        Segment="Logística"
        UF="SP"
        Issuer="Riza"
        Indexer="IPCA"
        EmissionRate=5.5
        AcquisitionRate=6.3
        MTMRate=9.1
        Duration=5.73
        Maturity="ago-41"
        LTV=61.5
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=8
        Name="CRI Visconde Icaraí B"
        MTM=35.0
        PLPct=2.2
        Segment="Financiamento a Construção"
        UF="SP"
        Issuer="Canal"
        Indexer="IPCA"
        EmissionRate=12.6
        AcquisitionRate=13.3
        MTMRate=12.5
        Duration=0.98
        Maturity="ago-27"
        LTV=65.0
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=9
        Name="CRI Galleria - Sênior"
        MTM=32.8
        PLPct=2.1
        Segment="Pulverizado"
        UF=""
        Issuer="Opea"
        Indexer="IPCA"
        EmissionRate=9.9
        AcquisitionRate=9.9
        MTMRate=10.9
        Duration=6.35
        Maturity="abr-41"
        LTV=50.0
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=10
        Name="CRI Boa Vista"
        MTM=30.2
        PLPct=1.9
        Segment="Shopping"
        UF="PE"
        Issuer="Opea"
        Indexer="IPCA"
        EmissionRate=7.3
        AcquisitionRate=6.8
        MTMRate=11.2
        Duration=2.70
        Maturity="jun-32"
        LTV=37.8
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=11
        Name="CRI GSFI"
        MTM=29.8
        PLPct=1.9
        Segment="Shopping"
        UF="SP, RJ, BA, GO"
        Issuer="Opea"
        Indexer="IPCA"
        EmissionRate=5.0
        AcquisitionRate=5.1
        MTMRate=9.1
        Duration=3.23
        Maturity="jul-32"
        LTV=48.6
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=12
        Name="CRI Cidade Matarazzo IPCA A"
        MTM=26.3
        PLPct=1.7
        Segment="Varejo"
        UF="SP"
        Issuer="Opea"
        Indexer="IPCA"
        EmissionRate=9.5
        AcquisitionRate=9.5
        MTMRate=10.9
        Duration=4.59
        Maturity="jun-40"
        LTV=50.0
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=13
        Name="CRI GTIS"
        MTM=25.4
        PLPct=1.6
        Segment="Logística"
        UF="SP"
        Issuer="Opea"
        Indexer="IPCA"
        EmissionRate=5.9
        AcquisitionRate=5.9
        MTMRate=10.0
        Duration=5.32
        Maturity="mar-40"
        LTV=28.3
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=14
        Name="CRI Invert C"
        MTM=24.5
        PLPct=1.6
        Segment="Financiamento a Construção"
        UF="SP"
        Issuer="Riza"
        Indexer="CDI"
        EmissionRate=6.0
        AcquisitionRate=6.0
        MTMRate=11.5
        Duration=0.55
        Maturity="mai-27"
        LTV=$null
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=15
        Name="CRI Mateus TRX"
        MTM=24.0
        PLPct=1.5
        Segment="Varejo"
        UF="PA"
        Issuer="Bari"
        Indexer="IPCA"
        EmissionRate=6.8
        AcquisitionRate=7.7
        MTMRate=9.9
        Duration=5.37
        Maturity="ago-39"
        LTV=73.2
        Evidence="observed"
    }

    [PSCustomObject]@{
        Rank=16
        Name="CRI New Sun Sr."
        MTM=22.4
        PLPct=1.4
        Segment="Energia"
        UF="SP"
        Issuer="Opea"
        Indexer="IPCA"
        EmissionRate=10.0
        AcquisitionRate=10.0
        MTMRate=12.8
        Duration=5.06
        Maturity="dez-39"
        LTV=53.0
        Evidence="observed"
    }
)

# ============================================================
# OPERAÇÕES ESTRUTURADAS / FIIs
# ============================================================

$Structured = @(

    [PSCustomObject]@{
        Name="FII Renda Preferencial GPA"
        MTM=85.8
        PLPct=5.5
        Segment="Varejo"
        Indexer="IPCA"
        Rate="9,3%"
        Duration=6.69
        Maturity="dez-37"
        LTV=60.3
        Evidence="observed"
    }

    [PSCustomObject]@{
        Name="FII CTA"
        MTM=60.1
        PLPct=3.8
        Segment="Multiestratégia"
        Indexer="IPCA"
        Rate="n/a"
        Duration=3.00
        Maturity="n/a"
        LTV=$null
        Evidence="observed"
    }

    [PSCustomObject]@{
        Name="Brasil Incorporação FII"
        MTM=32.4
        PLPct=2.1
        Segment="Estoque"
        Indexer="IPCA"
        Rate="12,5%"
        Duration=3.00
        Maturity="dez-28"
        LTV=60.0
        Evidence="observed"
    }

    [PSCustomObject]@{
        Name="Tranche Senior FII Patria Health"
        MTM=20.8
        PLPct=1.3
        Segment="Saúde"
        Indexer="IPCA"
        Rate="9,3%"
        Duration=5.00
        Maturity="dez-32"
        LTV=10.0
        Evidence="observed"
    }

    [PSCustomObject]@{
        Name="Valora CRI Infra FII"
        MTM=15.2
        PLPct=1.0
        Segment="Infraestrutura"
        Indexer="IPCA"
        Rate="8,0%"
        Duration=5.00
        Maturity="n/a"
        LTV=$null
        Evidence="observed"
    }
)

# ============================================================
# CORTE DE CRÉDITO / WATCHLIST
# ============================================================

$CreditEvents = @(
    "Sem novos CRI adicionados ao Watchlist em julho/2026.",
    "CRI Cortel está em processo de reestruturação.",
    "Posições Cortel foram integralizadas no FII CTA com deságio durante maio e junho de 2026.",
    "A gestão afirma que a operação no FII CTA não alterou a exposição econômica do PCIP11.",
    "Foi realizado ajuste nos spreads de risco das posições Cortel.",
    "A gestão espera recuperação de valor no processo de reestruturação e não antecipa novas provisões relevantes adicionais neste momento."
)

# ============================================================
# VALIDAÇÕES
# ============================================================

if ($CRI.Count -ne 16) {
    throw "ERRO: esperado 16 CRIs prioritários; encontrado $($CRI.Count)."
}

if ($Structured.Count -ne 5) {
    throw "ERRO: esperado 5 operações estruturadas; encontrado $($Structured.Count)."
}

if ($Summary.CRI_Count -ne 83) {
    throw "ERRO: quantidade consolidada de CRIs divergente."
}

if ($Summary.StructuredOperation_Count -ne 5) {
    throw "ERRO: quantidade consolidada de operações estruturadas divergente."
}

$IndexerTotal = ($Indexers | Measure-Object -Property Weight -Sum).Sum

if ($IndexerTotal -ne 101) {
    throw "ERRO: a soma dos pesos dos indexadores deve refletir o arredondamento reportado de 101%."
}

# ============================================================
# BACKUPS
# ============================================================

foreach ($File in @($UnderlyingFile,$EvidenceFile)) {

    if (Test-Path -LiteralPath $File) {

        Copy-Item `
            -LiteralPath $File `
            -Destination (Join-Path $BackupDir (Split-Path $File -Leaf)) `
            -Force
    }
}

# ============================================================
# UNDERLYING EXPOSURE
# ============================================================

$Lines = New-Object System.Collections.Generic.List[string]

$Lines.Add("---")
$Lines.Add("type: underlying_exposure")
$Lines.Add("asset_id: PCIP11")
$Lines.Add("ticker: PCIP11")
$Lines.Add("asset_class: FII")
$Lines.Add('schema_version: "0.1"')
$Lines.Add("as_of: 2026-07-31")
$Lines.Add("source_ref: PCIP11_rmg_20082026.pdf")
$Lines.Add("extraction_status: partial_structured")
$Lines.Add("evidence_status: observed")
$Lines.Add("status: active")
$Lines.Add("---")
$Lines.Add("")
$Lines.Add("# PCIP11 - Underlying Exposure")
$Lines.Add("")
$Lines.Add("Extração estruturada da exposição econômica do PCIP11 com data-base em 31/07/2026.")
$Lines.Add("")
$Lines.Add("## 1. Identidade econômica")
$Lines.Add("")
$Lines.Add("| Campo | Dado |")
$Lines.Add("|---|---|")
$Lines.Add("| Nome | FII Patria Crédito Índice de Preços |")
$Lines.Add("| Tipo ANBIMA | Papel Híbrido Gestão Ativa, Multicategoria |")
$Lines.Add("| Gestor | Patria - VBI Securities Ltda. |")
$Lines.Add("| Administrador | Apex Group Distribuidora de Títulos e Valores Mobiliários S.A. |")
$Lines.Add("| Objetivo | Renda e ganho de capital |")
$Lines.Add("| Início | setembro/2019 |")

$Lines.Add("")
$Lines.Add("## 2. Estrutura patrimonial")
$Lines.Add("")
$Lines.Add("| Métrica | Valor |")
$Lines.Add("|---|---:|")
$Lines.Add("| Patrimônio líquido | R$ 1.572,8 milhões |")
$Lines.Add("| Valor de mercado | R$ 1.292,5 milhões |")
$Lines.Add("| Cota patrimonial | R$ 92,45 |")
$Lines.Add("| Cota de mercado | R$ 75,98 |")
$Lines.Add("| P/VP | 0,82x |")
$Lines.Add("| Ativos / PL | 93,2% |")
$Lines.Add("| CRI + operações estruturadas / PL | 85,9% |")
$Lines.Add("| FII / PL | 7,3% |")
$Lines.Add("| Caixa / PL | 6,8% |")

$Lines.Add("")
$Lines.Add("## 3. Perfil da carteira de crédito")
$Lines.Add("")
$Lines.Add("| Métrica | Dado |")
$Lines.Add("|---|---:|")
$Lines.Add("| Quantidade de CRIs | 83 |")
$Lines.Add("| Operações estruturadas | 5 |")
$Lines.Add("| Rentabilidade média ponderada | 16,6% a.a. |")
$Lines.Add("| Referência IPCA | IPCA + 10,9% a.a. |")
$Lines.Add("| Prazo médio | 3,5 anos |")
$Lines.Add("| Spread médio | 2,4% a.a. |")
$Lines.Add("| LTV médio ponderado | 58% |")

$Lines.Add("")
$Lines.Add("## 4. Indexadores")
$Lines.Add("")
$Lines.Add("| Indexador | Peso reportado |")
$Lines.Add("|---|---:|")

foreach ($I in $Indexers) {
    $Lines.Add("| $($I.Indexer) | $($I.Weight)% |")
}

$Lines.Add("")
$Lines.Add("Observação: os percentuais reportados somam 101% por efeito de arredondamento da apresentação do relatório.")

$Lines.Add("")
$Lines.Add("## 5. Segmentos econômicos")
$Lines.Add("")
$Lines.Add("| Segmento | Peso reportado |")
$Lines.Add("|---|---:|")

foreach ($S in $Segments) {
    $Lines.Add("| $($S.Segment) | $($S.Weight)% |")
}

$Lines.Add("")
$Lines.Add("## 6. Principais CRIs")
$Lines.Add("")
$Lines.Add("| # | Ativo | MTM R$ mm | % PL | Segmento | UF | Emissor | Indexador | Taxa MTM | Prazo | Vencimento | LTV |")
$Lines.Add("|---:|---|---:|---:|---|---|---|---|---:|---:|---|---:|")

foreach ($C in $CRI) {

    $LTVText = ""

    if ($null -ne $C.LTV) {
        $LTVText = "$($C.LTV)%"
    }

    $Lines.Add(
        "| $($C.Rank) | $($C.Name) | $($C.MTM) | $($C.PLPct)% | $($C.Segment) | $($C.UF) | $($C.Issuer) | $($C.Indexer) | $($C.MTMRate)% | $($C.Duration) | $($C.Maturity) | $LTVText |"
    )
}

$Lines.Add("")
$Lines.Add("## 7. Operações estruturadas / FIIs")
$Lines.Add("")
$Lines.Add("| Ativo | MTM R$ mm | % PL | Segmento | Indexador | Taxa | Prazo | Vencimento | LTV |")
$Lines.Add("|---|---:|---:|---|---|---:|---:|---|---:|")

foreach ($O in $Structured) {

    $LTVText = ""

    if ($null -ne $O.LTV) {
        $LTVText = "$($O.LTV)%"
    }

    $Lines.Add(
        "| $($O.Name) | $($O.MTM) | $($O.PLPct)% | $($O.Segment) | $($O.Indexer) | $($O.Rate) | $($O.Duration) | $($O.Maturity) | $LTVText |"
    )
}

$Lines.Add("")
$Lines.Add("## 8. Crédito / Watchlist")
$Lines.Add("")

foreach ($Event in $CreditEvents) {
    $Lines.Add("- $Event")
}

$Lines.Add("")
$Lines.Add("## 9. Consolidação estratégica")
$Lines.Add("")
$Lines.Add("A gestão informa que concluiu as medidas prévias para iniciar o processo de consolidação dos fundos de crédito imobiliário high grade sob gestão do Patria: PCIP, VCJR, RBRR e RPRI.")
$Lines.Add("")
$Lines.Add("A tese apresentada pela gestão é de convergência entre fundos com características semelhantes, incluindo CRIs high grade indexados ao IPCA, garantias imobiliárias robustas e carteiras diversificadas.")
$Lines.Add("")
$Lines.Add("A consolidação depende de aprovação em assembleia de cada fundo.")

$Lines.Add("")
$Lines.Add("## 10. Limitações da extração")
$Lines.Add("")
$Lines.Add("A fonte contém 83 CRIs e 5 operações estruturadas.")
$Lines.Add("Esta versão estruturou individualmente os 16 maiores CRIs apresentados nas páginas de detalhamento e as 5 operações estruturadas/FIIs identificadas.")
$Lines.Add("Os demais CRIs permanecem reconhecidos no agregado da carteira, mas ainda não foram promovidos individualmente a entidades no registro.")
$Lines.Add("Não são inferidos devedor final, grupo econômico, overlap com outros fundos ou exposição indireta sem evidência específica.")

Set-Content `
    -LiteralPath $UnderlyingFile `
    -Value $Lines `
    -Encoding UTF8

# ============================================================
# EVIDENCE NOTE
# ============================================================

$Evidence = New-Object System.Collections.Generic.List[string]

$Evidence.Add("---")
$Evidence.Add("type: evidence")
$Evidence.Add("evidence_id: EV-PCIP11-RMG-20260731-UNDERLYING")
$Evidence.Add("asset_id: PCIP11")
$Evidence.Add("ticker: PCIP11")
$Evidence.Add('schema_version: "0.1"')
$Evidence.Add("evidence_status: observed")
$Evidence.Add("source_ref: PCIP11_rmg_20082026.pdf")
$Evidence.Add("as_of: 2026-07-31")
$Evidence.Add("status: active")
$Evidence.Add("---")
$Evidence.Add("")
$Evidence.Add("# Evidência - PCIP11 Underlying Exposure")
$Evidence.Add("")
$Evidence.Add("## Fonte")
$Evidence.Add("")
$Evidence.Add("Relatório Gerencial PCIP11 - Julho/2026.")
$Evidence.Add("")
$Evidence.Add("## Conteúdo observado")
$Evidence.Add("")
$Evidence.Add("- PL: R$ 1.572,8 milhões.")
$Evidence.Add("- Valor de mercado: R$ 1.292,5 milhões.")
$Evidence.Add("- 93,2% do PL alocado.")
$Evidence.Add("- 85,9% do PL em CRI e operações estruturadas.")
$Evidence.Add("- 7,3% do PL em FIIs.")
$Evidence.Add("- 6,8% do PL em caixa.")
$Evidence.Add("- 83 CRIs e 5 operações estruturadas.")
$Evidence.Add("- 93% IPCA, 4% CDI, 3% IGP-M e 1% prefixado.")
$Evidence.Add("- Rentabilidade média ponderada da carteira de CRI e operações estruturadas de 16,6% a.a.")
$Evidence.Add("- LTV médio ponderado de 58%.")
$Evidence.Add("- Varejo, pulverizado e financiamento a construção são os três maiores segmentos reportados.")
$Evidence.Add("")
$Evidence.Add("## Crédito relevante")
$Evidence.Add("")
$Evidence.Add("A documentação de julho registra a reestruturação dos ativos Cortel e sua transferência para o FII CTA sem alteração da exposição econômica do PCIP11.")
$Evidence.Add("")
$Evidence.Add("## Uso")
$Evidence.Add("")
$Evidence.Add("Esta evidência alimenta o Underlying Exposure Registry, o Metric Registry e a análise de overlap do PCIP11.")

Set-Content `
    -LiteralPath $EvidenceFile `
    -Value $Evidence `
    -Encoding UTF8

# ============================================================
# RESULTADO
# ============================================================

Write-Host ""
Write-Host "============================================================"
Write-Host "0688 - PCIP11 UNDERLYING EXPOSURE EXTRACTION"
Write-Host "============================================================"
Write-Host ""

Write-Host "Fonte                 : $Source"
Write-Host "Data-base             : $AsOf"
Write-Host "CRIs totais           : $($Summary.CRI_Count)"
Write-Host "Operacoes estruturadas: $($Summary.StructuredOperation_Count)"
Write-Host "CRIs estruturados     : $($CRI.Count)"
Write-Host "Operacoes estruturadas: $($Structured.Count)"
Write-Host "Evidence              : PASS"
Write-Host "Underlying Profile    : PASS"
Write-Host "Backup                : $BackupDir"

Write-Host ""
Write-Host "ESTRUTURA PATRIMONIAL"
Write-Host "------------------------------------------------------------"
Write-Host "PL                    : R$ $($Summary.PL_Millions) milhões"
Write-Host "Valor de mercado      : R$ $($Summary.MarketValue_Millions) milhões"
Write-Host "P/VP                  : $($Summary.PVP)x"
Write-Host "CRI + Estruturadas    : $($Summary.CRI_And_Structured_PctPL)% do PL"
Write-Host "FIIs                  : $($Summary.FII_PctPL)% do PL"
Write-Host "Caixa                 : $($Summary.Cash_PctPL)% do PL"

Write-Host ""
Write-Host "INDEXADORES"
Write-Host "------------------------------------------------------------"

foreach ($I in $Indexers) {
    Write-Host "$($I.Indexer.PadRight(12)) $($I.Weight)%"
}

Write-Host ""
Write-Host "TOP CRIs ESTRUTURADOS: $($CRI.Count)"
Write-Host "OPERACOES ESTRUTURADAS/FIIs: $($Structured.Count)"

Write-Host ""
Write-Host "PCIP11"
Write-Host "------------------------------------------------------------"
Write-Host "Extraction status     : partial_structured"
Write-Host "Evidence status       : observed"
Write-Host "Economic Role         : real_estate_credit"
Write-Host "Underlying Mapping    : PASS"

Write-Host ""
Write-Host "ARQUIVOS"
Write-Host "------------------------------------------------------------"
Write-Host "Underlying            : $UnderlyingFile"
Write-Host "Evidence              : $EvidenceFile"

Write-Host ""
Write-Host "============================================================"
Write-Host "STATUS: 0688 CONCLUIDO"
Write-Host "============================================================"