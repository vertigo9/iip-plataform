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


# This table deliberately avoids inventing classifications not supported by
# the DATABASE or explicitly supplied by the user.
PORTFOLIO_ASSETS: tuple[PortfolioAsset, ...] = (
    PortfolioAsset("BBSE3", "equity"),
    PortfolioAsset("ISAE4", "equity"),
    PortfolioAsset("CXSE3", "equity"),
    PortfolioAsset("CPFE3", "equity"),
    PortfolioAsset("ABCB4", "equity"),
    PortfolioAsset("CMIG4", "equity"),
    PortfolioAsset("SAUD3", "equity"),
    PortfolioAsset("ALOS3", "equity"),
    PortfolioAsset("CSUD3", "equity"),
    PortfolioAsset("VBBR3", "equity"),
    PortfolioAsset("KLBN4", "equity"),
    PortfolioAsset("FESA4", "equity"),
    PortfolioAsset("LEVE3", "equity"),
    PortfolioAsset("PASS3", "equity"),
    PortfolioAsset(
        "BTLG11",
        "fund",
        subtype="FII",
        structure="Tijolo",
        segment="Logístico",
        manager="BTG Pactual",
        source_url="https://btlg.btgpactual.com",
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="11.839.593/0001-09",  # verificado ao vivo nesta sessão
    ),
    PortfolioAsset(
        "TRXF11",
        "fund",
        subtype="FII",
        structure="Híbrido",
        manager="TRX",
        source_url="https://trxf11.com.br/relatorios-gerenciais-2",
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
        manager="Sparta",
        source_url="https://sparta.com.br/juro11",
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
        classification_provenance=ClassificationProvenance.USER,
        cnpj="09.552.812/0001-14",  # confirmado pelo usuario via extrato real da corretora
    ),
    PortfolioAsset(
        "VGIP11",
        "fund",
        subtype="FII",
        structure="Papel",
        manager="Valora Invest (fonte agregadora)",
        source_url="https://valorainvest.com.br/fundo/vgip11",
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="34.197.811/0001-46",  # verificado via busca (5 fontes concordam)
    ),
    PortfolioAsset(
        "PCIP11",
        "fund",
        subtype="FII",
        structure="Híbrido",
        manager="Pátria",
        source_url="https://realestate.patria.com/tijolo/pcip11",
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
        manager="Capitânia",
        source_url="https://capitaniainfra.com.br/cpti11",
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
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="11.160.521/0001-22",  # verificado via busca
    ),
    PortfolioAsset(
        "RBVA11",
        "fund",
        subtype="FII",
        structure="Híbrido",
        manager="Rio Bravo",
        source_url="https://riobravo.com.br/rbva11",
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
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="35.652.102/0001-76",  # verificado via busca (doc oficial B3/FNET)
    ),
    PortfolioAsset(
        "ALZR11",
        "fund",
        subtype="FII",
        structure="Híbrido",
        manager="Alianza",
        source_url="https://alzr11.alianza.com.br",
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="28.737.771/0001-85",  # verificado via busca (site oficial)
    ),
    PortfolioAsset(
        "KNRI11",
        "fund",
        subtype="FII",
        structure="Híbrido",
        manager="Kinea",
        source_url="https://kinea.com.br/fundos/.../knri11",
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
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="08.431.747/0001-06",  # verificado via busca (muitas fontes concordam)
    ),
    PortfolioAsset(
        "LFTB11",
        "etf",
        subtype="ETF Renda Fixa",
        manager="Investo",
        source_url="https://www.investoetf.com/etf/lftb11/",
        classification_provenance=ClassificationProvenance.DATABASE,
        cnpj="56.176.507/0001-55",  # verificado ao vivo nesta sessão
    ),
    PortfolioAsset(
        "AXIA3",
        "fixed_income",
        subtype="Daycoval FMP FGTS / subjacente AXIA3",
        manager="Daycoval",
        classification_provenance=ClassificationProvenance.DATABASE,
        # CNPJ do FUNDO Daycoval FMP-FGTS Eletrobras (verificado via
        # busca, multiplas fontes concordam, inclusive documento do
        # administrador). NAO confundir com o ticker "AXIA3" em si, que
        # e a propria acao ordinaria da Eletrobras (CNPJ
        # 00.001.180/0001-26) -- um ativo totalmente diferente. O
        # fundo FMP-FGTS nao tem ticker/cotacao propria na B3 (so e
        # acessado via FGTS, nao por corretora) -- por isso o fetch
        # deste ativo busca só patrimonio/cota via CVM, nunca preço via
        # bolsai/brapi (buscar preço usando "AXIA3" pegaria o preço da
        # ação da Eletrobras por engano).
        cnpj="45.121.022/0001-48",
    ),
)


def get_asset(ticker: str) -> PortfolioAsset | None:
    target = ticker.strip().upper()
    return next((asset for asset in PORTFOLIO_ASSETS if asset.ticker == target), None)


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
    """Everything ``iip refresh-portfolio`` can actually fetch today:
    CNPJ-verified fund/ETF/fixed_income positions (see
    ``assets_with_cnpj``) plus every equity position — equities are
    fetched by ticker via bolsai/brapi, not by CNPJ, so they don't need
    one to be refreshable."""
    return tuple(
        a for a in PORTFOLIO_ASSETS if a.cnpj or a.asset_class == "equity"
    )
