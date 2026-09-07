from iip.registry.models import *


def test_hgru11():
    fund = FundClassification(
        FundClass.FII, FundStructure.TIJOLO, "Renda Urbana", "Renda Urbana"
    )
    asset = UniversalAsset(
        AssetIdentity("HGRU11"),
        AssetClassification(AssetClass.FUND, segment="Renda Urbana", fund=fund),
    )
    assert asset.classification.fund.structure == FundStructure.TIJOLO
    assert asset.classification.fund.segment == "Renda Urbana"


def test_cdii11():
    fund = FundClassification(
        FundClass.FI_INFRA,
        FundStructure.PAPEL,
        "Debêntures incentivadas",
        "Infraestrutura",
        ("CDI",),
        RiskLevel.BAIXO,
    )
    assert fund.fund_class == FundClass.FI_INFRA
    assert fund.indexation == ("CDI",)


def test_afhi11():
    fund = FundClassification(
        FundClass.FII,
        FundStructure.PAPEL,
        "CRI",
        "Crédito Imobiliário",
        ("CDI", "IPCA"),
        RiskLevel.MEDIO,
    )
    assert fund.indexation == ("CDI", "IPCA")
    assert fund.risk_profile == RiskLevel.MEDIO


def test_craa11():
    fund = FundClassification(
        FundClass.FI_AGRO,
        FundStructure.PAPEL,
        "CRA",
        "Crédito Agrícola",
        ("CDI", "IPCA"),
        RiskLevel.ALTO,
    )
    assert fund.subtype == "CRA"
    assert fund.risk_profile == RiskLevel.ALTO


def test_mana11():
    fund = FundClassification(
        FundClass.FII,
        FundStructure.MULTIESTRATEGIA,
        "Hedge Fund",
        "Multiestratégia",
        ("Multi-indexador",),
        RiskLevel.MEDIO,
        "Hedge Fund",
        ("Ações", "CRIs", "Imóveis físicos"),
    )
    assert fund.strategy == "Hedge Fund"
    assert "Ações" in fund.investment_scope


def test_non_fund_asset():
    asset = UniversalAsset(
        AssetIdentity("CPFE3"),
        AssetClassification(AssetClass.EQUITY, sector="Utilities"),
    )
    assert asset.classification.fund is None


def test_other_asset_classes_are_first_class():
    assert {AssetClass.ETF, AssetClass.BDR, AssetClass.ADR} == {
        AssetClass.ETF,
        AssetClass.BDR,
        AssetClass.ADR,
    }
