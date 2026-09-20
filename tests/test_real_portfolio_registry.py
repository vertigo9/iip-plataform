from iip.portfolio.registry import ClassificationProvenance, assets_by_class, get_asset


def test_portfolio_contains_14_equities_from_database():
    equities = assets_by_class("equity")
    assert len(equities) == 14


def test_portfolio_contains_21_funds_from_database():
    funds = assets_by_class("fund")
    assert len(funds) == 19  # 21 no DATABASE; BTCI11 e PVBI11 foram encerrados
    from iip.portfolio.registry import ALL_PORTFOLIO_ASSETS

    assert len([a for a in ALL_PORTFOLIO_ASSETS if a.asset_class == "fund"]) == 21


def test_hgru11_user_classification_is_preserved():
    asset = get_asset("hgru11")
    assert asset.structure == "Tijolo"
    assert asset.segment == "Renda Urbana"
    assert asset.manager == "Pátria"
    assert asset.classification_provenance == ClassificationProvenance.USER


def test_cdii11_user_classification_is_preserved():
    asset = get_asset("CDII11")
    assert asset.subtype == "FI-Infra"
    assert asset.structure == "Papel"
    assert asset.segment == "Infraestrutura"
    assert asset.indexation == ("CDI",)
    assert asset.risk_profile == "Baixo"


def test_afhi11_user_classification_is_preserved():
    asset = get_asset("AFHI11")
    assert asset.structure == "Papel"
    assert asset.strategy == "CRI"
    assert asset.indexation == ("CDI", "IPCA")
    assert asset.risk_profile == "Médio"


def test_craa11_user_classification_is_preserved():
    asset = get_asset("CRAA11")
    assert asset.subtype == "FI-Agro"
    assert asset.structure == "Papel"
    assert asset.strategy == "CRA"
    assert asset.risk_profile == "Alto"


def test_mana11_multistrategy_is_not_forced_into_tijolo_or_papel():
    asset = get_asset("MANA11")
    assert asset.structure == "Multiestratégia"
    assert asset.strategy == "Hedge Fund"
    assert asset.indexation == ("Multi-indexador",)


def test_xpml11_source_is_xp_asset():
    asset = get_asset("XPML11")
    assert asset.manager == "XP Asset"
    assert asset.source_url == "https://xpasset.com.br/fundos/xp-malls"


def test_lftb11_is_separate_from_fund_taxonomy():
    asset = get_asset("LFTB11")
    assert asset.asset_class == "etf"
    assert asset.subtype == "ETF Renda Fixa"
