"""Portfolio-backed asset registry bootstrap.

Source of the records: IIP DATABASE da Carteira v3.2.
Classification fields are marked by provenance:
- database: directly represented in the portfolio database;
- user: classification explicitly supplied in the IIP discussion;
- pending: intentionally not inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ClassificationProvenance(StrEnum):
    DATABASE = "database"
    USER = "user"
    PENDING = "pending"


@dataclass(frozen=True)
class PortfolioAsset:
    ticker: str
    asset_class: str
    subtype: str | None = None
    structure: str | None = None
    segment: str | None = None
    manager: str | None = None
    source_url: str | None = None
    indexation: tuple[str, ...] = ()
    risk_profile: str | None = None
    strategy: str | None = None
    classification_provenance: ClassificationProvenance = (
        ClassificationProvenance.PENDING
    )
    # CNPJ do fundo, necessário para os providers da CVM (cvm_fii,
    # cvm_renda_fixa). Deliberadamente None para a maioria das posições
    # — só preenchido onde foi verificado ao vivo (ver notas por
    # posição abaixo). Nunca adivinhado: um CNPJ errado buscaria dados
    # de outro fundo silenciosamente.
    cnpj: str | None = None
    # Nomes iguais aos que `iip analyze --data-file` espera literalmente
    # (``sector``/``industry``), pra mapear direto sem ambiguidade num
    # comando de análise em lote. Deliberadamente separado de
    # ``segment``/``structure`` (que são termos de fundo, não de ação) —
    # só preenchido quando o usuário confirma o valor real, nunca
    # adivinhado a partir do ticker ou de conhecimento geral.
    sector: str | None = None
    industry: str | None = None
    # Posição ENCERRADA: data (AAAA-MM-DD) em que o usuário zerou a posição. O ativo continua
    # aqui, com todos os dados, para poder voltar (sair de um ativo e comprá-lo de novo depois
    # é normal): reativar é só apagar ``closed_on``. Enquanto estiver preenchido, o ativo fica
    # FORA de ``PORTFOLIO_ASSETS`` e o job diário não o atualiza, avalia nem decide.
    closed_on: str | None = None
    closure_note: str = ""


# This table deliberately avoids inventing classifications not supported by
# the DATABASE or explicitly supplied by the user. Todas as posições que o projeto já teve,
# inclusive as encerradas; ``PORTFOLIO_ASSETS`` (abaixo) é só o subconjunto ativo.
ALL_PORTFOLIO_ASSETS: tuple[PortfolioAsset, ...] = (
    # CNPJs abaixo verificados ao vivo em 18/09/2026 contra o cadastro
    # aberto da CVM (dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/
    # cad_cia_aberta.csv), cruzando razão social/nome comercial com cada
    # ticker (nunca adivinhado) -- usados para localizar cada empresa no
    # dataset de DFP (ver iip.sources.cvm_dfp).
    PortfolioAsset(
        "BBSE3",
        "equity",
        sector="Financeiro",
        industry="Previdência e Seguros",
        cnpj="17.344.597/0001-94",
    ),
    PortfolioAsset(
        "ISAE4",
        "equity",
        sector="Utilidade Pública",
        industry="Energia Elétrica",
        cnpj="02.998.611/0001-04",
    ),
    PortfolioAsset(
        "CXSE3",
        "equity",
        sector="Financeiro",
        industry="Previdência e Seguros",
        cnpj="22.543.331/0001-00",
    ),
    PortfolioAsset(
        "CPFE3",
        "equity",
        sector="Utilidade Pública",
        industry="Energia Elétrica",
        cnpj="02.429.144/0001-93",
    ),
    PortfolioAsset(
        "ABCB4",
        "equity",
        sector="Financeiro",
        industry="Intermediários Financeiros (Bancos)",
        cnpj="28.195.667/0001-06",
    ),
    PortfolioAsset(
        "CMIG4",
        "equity",
        sector="Utilidade Pública",
        industry="Energia Elétrica",
        cnpj="17.155.730/0001-64",
    ),
    PortfolioAsset(
        "SAUD3",
        "equity",
        sector="Saúde",
        industry="Serviços Médico-Hospitalares, Analíticos e Diagnósticos",
        cnpj="13.270.520/0001-66",
    ),
    PortfolioAsset(
        "ALOS3",
        "equity",
        sector="Financeiro",
        industry="Exploração de Imóveis",
        cnpj="05.878.397/0001-32",
    ),
    PortfolioAsset(
        "CSUD3",
        "equity",
        # Classificação B3 (informada pelo usuário em 20/09/2026): Financeiro / Serviços
        # Financeiros Diversos. Antes estava "Utilidade Pública / Tecnologia" (uma barra dentro
        # do setor, que criava um setor à parte nas camadas e ainda fazia o valuation excluir o
        # Graham por "tecnologia" e o Bazin liderar por "utilidade pública").
        sector="Financeiro",
        industry="Serviços Financeiros Diversos",
        cnpj="01.896.779/0001-38",
    ),
    PortfolioAsset(
        "VBBR3",
        "equity",
        sector="Petróleo, Gás e Biocombustíveis",
        industry="Comércio Varejista e Atacadista",
        cnpj="34.274.233/0001-02",
    ),
    PortfolioAsset(
        "KLBN4",
        "equity",
        sector="Materiais Básicos",
        industry="Madeiras e Papel",
        cnpj="89.637.490/0001-45",
    ),
    PortfolioAsset(
        "FESA4",
        "equity",
        sector="Materiais Básicos",
        industry="Siderurgia e Metalurgia",
        cnpj="15.141.799/0001-03",
    ),
    PortfolioAsset(
        "LEVE3",
        "equity",
        sector="Bens Industriais",
        industry="Material de Transporte",
        cnpj="60.476.884/0001-87",
    ),
    PortfolioAsset(
        "PASS3",
        "equity",
        sector="Utilidade Pública",
        industry="Gás",
        cnpj="21.389.501/0001-81",
    ),
    PortfolioAsset(
        "BTLG11",
        "fund",
        subtype="FII",
        structure="Tijolo",
        segment="Logístico",
        manager="BTG Pactual",
        source_url="https://btlg.btgpactual.com",
        indexation=(
            "IPCA",
        ),  # confirmado via busca (site oficial + agregador concordam; parte dos contratos)
        strategy="Logística",
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada em fonte confiável (apenas linguagem vaga de volatilidade).
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="11.839.593/0001-09",  # verificado ao vivo nesta sessão
    ),
    PortfolioAsset(
        "TRXF11",
        "fund",
        subtype="FII",
        structure="Tijolo",
        segment="Híbrido (Renda Urbana/Logística)",
        manager="TRX",
        source_url="https://trxf11.com.br/relatorios-gerenciais-2",
        indexation=(
            "IPCA",
            "IGP-M",
        ),  # confirmado via busca (agregador; site oficial confirma mandato híbrido)
        strategy="Tijolo/Híbrido",
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada em fonte confiável.
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="28.548.288/0001-52",  # verificado via busca (multiplas fontes concordam)
    ),
    PortfolioAsset(
        "HGRU11",
        "fund",
        subtype="FII",
        structure="Tijolo",
        segment="Renda Urbana",
        manager="Pátria",
        source_url="https://realestate.patria.com/tijolo/hgru",
        indexation=(
            "IPCA",
        ),  # confirmado via busca (2 fontes independentes, uma com percentual preciso: 99,36% dos contratos)
        strategy="Renda Urbana",
        risk_profile="Médio",  # confirmado via busca (baixa confiança: blog agregador descreve como "perfil moderado", não é doc formal da gestora)
        classification_provenance=ClassificationProvenance.USER,
        cnpj="29.641.226/0001-53",  # verificado via busca
    ),
    PortfolioAsset(
        "CDII11",
        "fund",
        subtype="FI-Infra",
        structure="Papel",
        segment="Infraestrutura",
        manager="Sparta",
        source_url="https://sparta.com.br/sparta-cdii11",
        indexation=("CDI",),
        risk_profile="Baixo",
        strategy="Crédito / Debêntures incentivadas",
        classification_provenance=ClassificationProvenance.USER,
        cnpj="48.973.783/0001-16",  # verificado via busca (multiplas fontes concordam)
    ),
    PortfolioAsset(
        "JURO11",
        "fund",
        subtype="FI-Infra",
        structure="Papel (Crédito Privado)",
        segment="Infraestrutura (Debêntures Incentivadas)",
        manager="Sparta",
        source_url="https://sparta.com.br/juro11",
        indexation=(
            "IPCA",
            "CDI",
        ),  # confirmado via busca (agregador; site oficial confirma referência ao IMA-B 5)
        strategy="FI-Infra",
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada em fonte confiável.
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="42.730.834/0001-00",  # verificado via busca (multiplas fontes concordam)
    ),
    PortfolioAsset(
        "CRAA11",
        "fund",
        subtype="FI-Agro",
        structure="Papel",
        segment="Crédito Agrícola",
        manager="Sparta",
        source_url="https://sparta.com.br/craa11",
        indexation=("CDI", "IPCA"),
        risk_profile="Alto",
        strategy="CRA",
        classification_provenance=ClassificationProvenance.USER,
        cnpj="48.903.610/0001-21",  # verificado via busca (multiplas fontes concordam)
    ),
    PortfolioAsset(
        "BTCI11",
        "fund",
        subtype="FII",
        structure="Papel",
        segment="Crédito Imobiliário",
        manager="BTG Pactual",
        source_url="https://btgpactual.com/asset-management/.../BTCI11",
        indexation=(
            "IPCA",
            "CDI",
        ),  # confirmado via busca (2 fontes agregadoras concordam: IPCA predominante, CDI secundário)
        strategy="Papel/Crédito Imobiliário",
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada em fonte confiável ("high grade" descreve o crédito
        # subjacente, não um tier baixo/médio/alto a nível de fundo).
        classification_provenance=ClassificationProvenance.USER,
        cnpj="09.552.812/0001-14",  # confirmado pelo usuario via extrato real da corretora
        closed_on="2026-09-18",
        closure_note="posição zerada, informado pelo usuário em 20/09/2026",
    ),
    PortfolioAsset(
        "VGIP11",
        "fund",
        subtype="FII",
        structure="Papel",
        segment="Títulos e Valores Mobiliários (CRI - IPCA)",
        manager="Valora Invest (fonte agregadora)",
        source_url="https://valorainvest.com.br/fundo/vgip11",
        indexation=(
            "IPCA",
        ),  # confirmado via busca (site oficial: benchmark ligado a índices de inflação)
        strategy="CRI",
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada em fonte confiável.
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="34.197.811/0001-46",  # verificado via busca (5 fontes concordam)
    ),
    PortfolioAsset(
        "PCIP11",
        "fund",
        subtype="FII",
        # Classificação mudou de "Híbrido"/High Grade para "Papel"/Middle
        # Risk (confirmado pelo usuário em 12/09/2026) -- não foi erro de
        # digitação nem de fonte: o fundo incorporou outros fundos, o que
        # mudou seu perfil de risco de verdade. A URL antiga
        # (.../tijolo/pcip11) também estava errada e foi corrigida junto.
        structure="Papel",
        segment="Títulos e Valores Mobiliários (CRI - Middle Risk)",
        manager="Pátria",
        source_url="https://realestate.patria.com/papel/pcip11/",
        indexation=(
            "IPCA",
        ),  # confirmado via busca (fonte oficial: "CRI indexado a IPCA")
        strategy="CRI",
        risk_profile="Médio",  # confirmado via busca (relatório XP: carteira de crédito descrita como "moderate risk"/perfil mais conservador)
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="28.729.197/0001-13",  # verificado via busca (2 fontes concordam)
    ),
    PortfolioAsset(
        "LVBI11",
        "fund",
        subtype="FII",
        structure="Tijolo",
        segment="Logístico",
        manager="Pátria",
        source_url="https://realestate.patria.com/tijolo/lvbi11",
        # indexation deliberadamente vazio: pesquisado, mas fundo de tijolo com
        # mistura de IPCA/IGP-M que varia por contrato/período (ex.: 62% IGP-M
        # em 2021 vs. 53% IPCA em relatório mais recente) -- sem indexador único
        # declarado a nível de fundo, diferente dos fundos de papel/crédito.
        strategy="Tijolo/Renda (Logística)",
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada em fonte confiável.
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="30.629.603/0001-18",  # verificado via busca (3 fontes concordam)
    ),
    PortfolioAsset(
        "AFHI11",
        "fund",
        subtype="FII",
        structure="Papel",
        segment="Crédito Imobiliário",
        source_url="https://afhi11.com.br/documentos",
        indexation=("CDI", "IPCA"),
        risk_profile="Médio",
        strategy="CRI",
        classification_provenance=ClassificationProvenance.USER,
        cnpj="36.642.293/0001-58",  # verificado via busca (muitas fontes concordam)
    ),
    PortfolioAsset(
        "CPTI11",
        "fund",
        subtype="FI-Infra",
        structure="Papel (Crédito Privado)",
        segment="Infraestrutura (Debêntures Incentivadas)",
        manager="Capitânia",
        source_url="https://capitaniainfra.com.br/cpti11",
        indexation=(
            "IPCA",
        ),  # confirmado via busca (site oficial + relatório mensal: "carrego bruto de IPCA + 8,56%")
        strategy="Debêntures Incentivadas",
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada em fonte confiável (apenas fatores de risco genéricos
        # de crédito/mercado/liquidez, comuns a qualquer FI-Infra).
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="38.065.012/0001-77",  # verificado via busca (docs oficiais CVM/B3)
    ),
    PortfolioAsset(
        "MANA11",
        "fund",
        subtype="FII",
        structure="Multiestratégia",
        segment="Multiestratégia",
        manager="Manati/ICM",
        source_url="https://manaticm.com/fundo/mana11",
        indexation=("Multi-indexador",),
        risk_profile="Médio",
        strategy="Hedge Fund",
        classification_provenance=ClassificationProvenance.USER,
        cnpj="42.888.583/0001-89",  # verificado via busca
    ),
    PortfolioAsset(
        "HSML11",
        "fund",
        subtype="FII",
        structure="Tijolo",
        segment="Shopping",
        manager="HSI",
        source_url="https://hsml.hsifii.com",
        # indexation deliberadamente vazio: pesquisado (relatórios gerenciais
        # FNET/CVM + agregadores), sem indexador único declarado a nível de
        # fundo -- típico de tijolo, contratos variam por locatário/período.
        strategy="Tijolo/Renda (Shopping)",
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada em fonte confiável (fontes contraditórias: "perfil
        # moderado e arrojado" vs. "fundo defensivo" no mesmo período).
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="32.892.018/0001-31",  # verificado via busca (muitas fontes concordam)
    ),
    PortfolioAsset(
        "XPML11",
        "fund",
        subtype="FII",
        structure="Tijolo",
        segment="Shopping",
        manager="XP Asset",
        source_url="https://xpasset.com.br/fundos/xp-malls",
        # indexation deliberadamente vazio: pesquisado (fiisimplificado.com.br +
        # XP Asset), contratos de shopping distribuídos entre IPCA, IGP-M e CDI
        # por propriedade/locatário, sem indexador único declarado a nível de
        # fundo -- mesmo padrão de LVBI11/HSML11. (O "IPCA+6% a.a." que aparece
        # em materiais da XP Malls é benchmark de taxa de performance, não
        # indexador de contrato de locação -- não confundir.)
        strategy="Shopping Centers (aluguel mínimo + percentual sobre vendas)",
        risk_profile="Médio",  # confirmado via busca (confiança média: agregador Rico aos Poucos, não é doc formal da gestora)
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="28.757.546/0001-00",  # verificado via busca (muitas fontes concordam)
    ),
    PortfolioAsset(
        "HGCR11",
        "fund",
        subtype="FII",
        structure="Papel",
        segment="Crédito Imobiliário",
        manager="Pátria",
        source_url="https://realestate.patria.com/tijolo/hgcr11",
        indexation=(
            "CDI",
            "IPCA",
        ),  # confirmado via busca (relatório XP: carteira 53% IPCA / 46% CDI)
        risk_profile="Médio",  # relatório institucional XP: "perfil de risco moderado" (confiança média, não é doc formal da gestora)
        strategy="CRI (Recebíveis Imobiliários) — mandato flexível entre indexadores",
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="11.160.521/0001-22",  # verificado via busca
    ),
    PortfolioAsset(
        "RBVA11",
        "fund",
        subtype="FII",
        structure="Tijolo",
        segment="Varejo / Renda Urbana",
        manager="Rio Bravo",
        source_url="https://riobravo.com.br/rbva11",
        # indexation de baixa/média confiança: múltiplas buscas independentes
        # sobre o relatório gerencial da Rio Bravo concordam na composição
        # IPCA + IGP-M (sem CDI/IGP-DI), mas o PDF primário é digitalizado
        # (não extraível) e os percentuais variam entre buscas e no tempo
        # (~93% IGP-M/7% IPCA em 2021 vs. ~39% IPCA/61% IGP-M em set/2024) --
        # por isso só a composição de dois índices é registrada, não a
        # proporção. Revisão humana do PDF recomendada antes de usar em cálculo.
        indexation=("IPCA", "IGP-M"),
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada em fonte confiável.
        strategy="Varejo de rua / Agências bancárias (Buy-to-Lease e Built-to-Suit)",
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="15.576.907/0001-70",  # verificado via busca (site oficial)
    ),
    PortfolioAsset(
        "PVBI11",
        "fund",
        subtype="FII",
        structure="Tijolo",
        segment="Lajes",
        manager="Pátria",
        source_url="https://realestate.patria.com/tijolo/pvbi11",
        indexation=(
            "IPCA",
            "IGP-M",
        ),  # confirmado via busca (2 fontes concordam: 84% IPCA / 16% IGP-M)
        strategy="Lajes Corporativas AAA (contratos típicos, Faria Lima/Itaim/Vila Olímpia)",
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada em fonte confiável.
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="35.652.102/0001-76",  # verificado via busca (doc oficial B3/FNET)
        closed_on="2026-08-14",
        closure_note="posição zerada, informado pelo usuário em 20/09/2026",
    ),
    PortfolioAsset(
        "ALZR11",
        "fund",
        subtype="FII",
        structure="Tijolo",
        segment="Híbrido / Multicategoria (Renda Urbana/Logística)",
        manager="Alianza",
        source_url="https://alzr11.alianza.com.br",
        indexation=(
            "IPCA",
        ),  # confirmado via busca (relatórios gerenciais oficiais, IPCA em múltiplos imóveis; % do total não confirmado)
        strategy="Renda Urbana — contratos atípicos de longo prazo",
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada em fonte confiável.
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="28.737.771/0001-85",  # verificado via busca (site oficial)
    ),
    PortfolioAsset(
        "KNRI11",
        "fund",
        subtype="FII",
        structure="Tijolo",
        segment="Misto / Híbrido (Escritórios e Logística)",
        manager="Kinea",
        source_url="https://kinea.com.br/fundos/.../knri11",
        indexation=(
            "IPCA",
            "IGP-M",
        ),  # confirmado via busca (site oficial Kinea: "reajuste anual pela inflação, IGPM ou IPCA")
        strategy="Renda",
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada em fonte confiável (relatório XP usa "perfil defensivo"
        # no título, mas "moderado a arrojado" no corpo -- inconsistente).
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="12.005.956/0001-65",  # verificado via busca
    ),
    PortfolioAsset(
        "HGBS11",
        "fund",
        subtype="FII",
        structure="Tijolo",
        segment="Shopping",
        manager="Hedge Investments",
        source_url="https://hedgeinvest.com.br/fundos/hgbs",
        # indexation pesquisado, sem fonte fundo-nível confiável: os
        # relatórios de gestão/informe trimestral da Hedge Investments (FNET)
        # são digitalizados (não extraíveis por texto) e buscas independentes
        # retornaram números inconsistentes entre si (IGP-DI dominante vs.
        # IPCA 59% vs. sem percentuais) -- provável mistura heterogênea como
        # LVBI11/HSML11 (mesmo perfil de shopping/tijolo), mas não confirmado.
        strategy="Renda",
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada em fonte confiável.
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="08.431.747/0001-06",  # verificado via busca (muitas fontes concordam)
    ),
    PortfolioAsset(
        "LFTB11",
        "etf",
        subtype="ETF Renda Fixa",
        structure="Renda Fixa (Títulos Públicos)",
        segment="Pós-fixado (Selic com Duration Alvo / IPCA)",
        manager="Investo",
        source_url="https://www.investoetf.com/etf/lftb11/",
        indexation=(
            "Selic",
            "IPCA",
        ),  # confirmado via busca (site oficial: cesta Tesouro Selic/LFT + Tesouro IPCA+/NTN-B)
        strategy="Gestão passiva — réplica de cesta de títulos públicos (Tesouro Selic/LFT + Tesouro IPCA+/NTN-B)",
        risk_profile="Baixo",  # confirmado via busca (confiança média: réplica de títulos públicos, agregadores descrevem como baixa volatilidade/baixo risco; emissora não usa rótulo explícito)
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="56.176.507/0001-55",  # verificado ao vivo nesta sessão
    ),
    PortfolioAsset(
        "AXIA3",
        "fixed_income",
        subtype="Daycoval FMP FGTS / subjacente AXIA3",
        # structure/segment/strategy confirmados via busca (blog oficial
        # Daycoval + 2 agregadores concordantes: faixa 90%-100% do PL em
        # ações ON Eletrobras, 0%-10% em titulos publicos federais).
        structure="Fundo Mútuo de Privatização (FMP-FGTS), condomínio aberto",
        segment="Ações — Privatização (Axia Energia, ex-Eletrobras, ON), mín. 90% a máx. 100% do PL em AXIA3 + até 10% em títulos públicos federais",
        strategy="Privatização (FGTS) — concentração mínima de 90% do patrimônio em ações ordinárias da Axia Energia (AXIA3, ex-Eletrobras/ELET3)",
        sector="Utilities",
        industry="Electric Utilities / Renewable",
        manager="Daycoval",
        # risk_profile pesquisado, sem classificação explícita de risco
        # encontrada para o fundo em si (apenas boilerplate genérico de
        # fatores de risco de FMP-FGTS: mercado, juros, liquidez,
        # concentração; "renda variável é considerada de alto risco" é
        # categoria geral, não classificação específica deste fundo).
        classification_provenance=ClassificationProvenance.DATABASE,
        # CNPJ do FUNDO Daycoval FMP-FGTS Eletrobras (verificado via
        # busca, multiplas fontes concordam, inclusive documento do
        # administrador). NAO confundir a COTA do fundo com o ticker
        # "AXIA3", a acao ordinaria da Axia Energia (ex-Eletrobras,
        # CNPJ 00.001.180/0001-26): o fundo carrega essas acoes (99,8%
        # do PL na CDA de 08/2026), mas a cota e outro ativo, com NAV
        # proprio. O fundo FMP-FGTS nao tem ticker/cotacao propria na B3 (so e
        # acessado via FGTS, nao por corretora) -- por isso o fetch
        # deste ativo busca só patrimonio/cota via CVM, nunca preço via
        # bolsai/brapi (buscar preço usando "AXIA3" pegaria o preço da
        # ação da Eletrobras por engano).
        cnpj="45.121.022/0001-48",
    ),
)


# As posições ATIVAS: é o que o job diário e os comandos de carteira percorrem.
PORTFOLIO_ASSETS: tuple[PortfolioAsset, ...] = tuple(
    a for a in ALL_PORTFOLIO_ASSETS if a.closed_on is None
)
# As posições encerradas, com os dados e a data de encerramento preservados.
CLOSED_ASSETS: tuple[PortfolioAsset, ...] = tuple(
    a for a in ALL_PORTFOLIO_ASSETS if a.closed_on is not None
)


def get_asset(ticker: str, *, include_closed: bool = False) -> PortfolioAsset | None:
    """O ativo do registro. Por padrão só as posições ativas; ``include_closed=True`` também
    acha as encerradas (para reconhecer uma posição que voltou ao snapshot)."""
    target = ticker.strip().upper()
    pool = ALL_PORTFOLIO_ASSETS if include_closed else PORTFOLIO_ASSETS
    return next((asset for asset in pool if asset.ticker == target), None)


def assets_by_class(asset_class: str) -> tuple[PortfolioAsset, ...]:
    target = asset_class.strip().lower()
    return tuple(a for a in PORTFOLIO_ASSETS if a.asset_class == target)


def assets_with_cnpj() -> tuple[PortfolioAsset, ...]:
    """Positions with a verified CNPJ — the ones ``iip refresh-portfolio``
    can actually fetch from the CVM today. Most FII/ETF positions in
    ``PORTFOLIO_ASSETS`` don't have one yet (never guessed, only
    populated after live verification) — this makes that gap visible
    rather than silently skipping without explanation."""
    return tuple(a for a in PORTFOLIO_ASSETS if a.cnpj)


def assets_refreshable_now() -> tuple[PortfolioAsset, ...]:
    """Everything ``iip refresh-portfolio`` can actually fetch today —
    same set as ``assets_with_cnpj`` now that every refreshable class
    (fund/ETF/fixed_income/fiagro via their own CVM datasets, equity
    via CVM DFP) is looked up by CNPJ. Kept as a separate function
    since the two questions ("has a CNPJ" vs. "is refreshable today")
    are conceptually distinct even though they resolve to the same set
    for the current portfolio — before 18/09/2026, equities were
    fetched by ticker only (bolsai/brapi price data) and didn't need
    one; CVM DFP-based fundamentals changed that."""
    return tuple(a for a in PORTFOLIO_ASSETS if a.cnpj)
