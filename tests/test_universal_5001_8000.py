from iip.universal.concentration import all_concentrations, concentration
from iip.universal.contribution_policy import ContributionRule, evaluate
from iip.universal.cross_asset import normalize_signal
from iip.universal.fund_segments import known_segment
from iip.universal.portfolio_state import PortfolioState, PositionState
from iip.universal.risk_model import RiskFactors, RiskLevel, assess_overall
from iip.universal.snapshot_diff import diff
from iip.universal.taxonomy import (
    AssetClass,
    FundStructure,
    classify_fund,
    classify_non_fund,
)
from iip.universal.universal_pipeline import build_view


def make_state():
    positions = (
        PositionState(
            "HGRU11",
            100,
            1000,
            0.25,
            "fund",
            "Tijolo",
            "Renda Urbana",
            "Patria",
            "Baixo",
        ),
        PositionState(
            "LVBI11", 100, 1000, 0.25, "fund", "Tijolo", "Logística", "Patria", "Baixo"
        ),
        PositionState("CPFE3", 50, 1000, 0.25, "equity"),
        PositionState("SCHD", 20, 1000, 0.25, "etf"),
    )
    return PortfolioState("2026-08-29", positions, 4000)


def test_fund_classification_examples():
    hgru = classify_fund(
        "hgru11", FundStructure.TIJOLO, "Renda Urbana", manager="Patria"
    )
    cdii = classify_fund(
        "cdii11",
        FundStructure.PAPEL,
        "Infraestrutura",
        indexers=("CDI",),
        credit_type="Debêntures incentivadas",
        risk_profile="Baixo",
    )
    afhi = classify_fund(
        "afhi11",
        FundStructure.PAPEL,
        "Crédito Imobiliário",
        indexers=("CDI", "IPCA"),
        credit_type="CRI",
        risk_profile="Médio",
    )
    craa = classify_fund(
        "craa11",
        FundStructure.PAPEL,
        "Crédito Agrícola",
        indexers=("CDI", "IPCA"),
        credit_type="CRA",
        risk_profile="Alto",
    )
    mana = classify_fund(
        "mana11",
        FundStructure.HEDGE,
        "Hedge Fund",
        indexers=("Multi-indexador",),
        risk_profile="Médio",
    )
    assert hgru.segment == "Renda Urbana"
    assert cdii.indexers == ("CDI",)
    assert afhi.credit_type == "CRI"
    assert craa.credit_type == "CRA"
    assert mana.structure == "Hedge Fund"


def test_known_segment_map():
    assert known_segment("HGRU11") == (FundStructure.TIJOLO, "Renda Urbana")
    assert known_segment("MANA11")[0] == FundStructure.HEDGE


def test_non_fund_taxonomy():
    equity = classify_non_fund("CPFE3", AssetClass.EQUITY)
    etf = classify_non_fund("SCHD", AssetClass.ETF)
    bdr = classify_non_fund("AAPL34", AssetClass.BDR)
    adr = classify_non_fund("AAPL", AssetClass.ADR)
    assert equity.asset_class == AssetClass.EQUITY
    assert etf.asset_class == AssetClass.ETF
    assert bdr.asset_class == AssetClass.BDR
    assert adr.asset_class == AssetClass.ADR


def test_risk_assessment():
    result = assess_overall(RiskFactors(credit=RiskLevel.ALTO, market=RiskLevel.BAIXO))
    assert result == RiskLevel.ALTO
    assert assess_overall(RiskFactors(credit=RiskLevel.BAIXO)) == RiskLevel.BAIXO


def test_portfolio_state_filters():
    state = make_state()
    assert len(state.by_asset_class("fund")) == 2
    assert len(state.by_manager("patria")) == 2


def test_concentration_by_manager():
    state = make_state()
    result = concentration(state.positions, "manager", 0.20)
    assert len(result) == 1
    assert result[0].value == "Patria"
    assert result[0].weight == 0.50


def test_all_concentration_dimensions():
    state = make_state()
    result = all_concentrations(state.positions)
    assert any(item.dimension == "manager" for item in result)
    assert any(item.dimension == "asset_class" for item in result)


def test_contribution_policy():
    rule = ContributionRule(8.0, 0.70, 0.30)
    assert evaluate("CPFE3", 8.5, 0.8, 0.20, rule).eligible
    assert not evaluate("CPFE3", 7.5, 0.8, 0.20, rule).eligible
    assert not evaluate("CPFE3", 8.5, 0.5, 0.20, rule).eligible
    assert not evaluate("CPFE3", 8.5, 0.8, 0.30, rule).eligible


def test_cross_asset_signal():
    signal = normalize_signal(
        "schd", AssetClass.ETF, 12, income_role="dividend", currency_exposure="USD"
    )
    assert signal.ticker == "SCHD"
    assert signal.score == 10.0


def test_snapshot_diff():
    previous = make_state()
    current = PortfolioState(
        "2026-09-01",
        previous.positions[:2] + (PositionState("CPFE3", 50, 800, 0.20, "equity"),),
        4000,
    )
    result = diff(previous, current)
    cpfe = next(item for item in result if item.ticker == "CPFE3")
    schd = next(item for item in result if item.ticker == "SCHD")
    assert cpfe.change == -0.05
    assert schd.current_weight is None


def test_universal_pipeline():
    state = make_state()
    taxonomies = (
        classify_fund("HGRU11", FundStructure.TIJOLO, "Renda Urbana", manager="Patria"),
        classify_non_fund("CPFE3", AssetClass.EQUITY),
        classify_non_fund("SCHD", AssetClass.ETF),
    )
    signals = (
        normalize_signal("HGRU11", AssetClass.FUND, 9),
        normalize_signal("CPFE3", AssetClass.EQUITY, 8),
        normalize_signal("SCHD", AssetClass.ETF, 7),
    )
    view = build_view(state, taxonomies, signals)
    assert len(view.taxonomies) == 3
    assert len(view.signals) == 3
