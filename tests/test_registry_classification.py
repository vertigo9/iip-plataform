import pytest

from iip.portfolio.layers import build_layers
from iip.portfolio.registry import ALL_PORTFOLIO_ASSETS, PORTFOLIO_ASSETS, get_asset
from iip.portfolio.target_policy import SnapshotRow
from iip.portfolio_data.valuation_methods import (
    ValuationMethod,
    applicability,
    ordered_methods,
)


def _equities():
    return [a for a in ALL_PORTFOLIO_ASSETS if a.asset_class == "equity"]


# --- CSUD3: B3 classification (Financeiro / Serviços Financeiros Diversos) ------------------


def test_csud3_carries_the_b3_classification_the_user_confirmed():
    asset = get_asset("CSUD3")

    assert asset.sector == "Financeiro"
    assert asset.industry == "Serviços Financeiros Diversos"


def test_no_equity_sector_carries_a_slash_which_used_to_split_one_stock_into_its_own_group():
    offenders = {
        a.ticker: a.sector for a in _equities() if a.sector and "/" in a.sector
    }

    assert offenders == {}


def test_every_equity_has_a_sector_and_an_industry():
    missing = [a.ticker for a in _equities() if not a.sector or not a.industry]

    assert missing == []


def test_the_stock_sector_layer_has_no_leftover_technology_group():
    rows = tuple(
        SnapshotRow(a.ticker, a.ticker, "acao", 1000.0)
        for a in PORTFOLIO_ASSETS
        if a.asset_class == "equity"
    )

    layers = build_layers(rows)

    sectors = {g.label for g in layers.stock_sectors}
    assert "Utilidade Pública / Tecnologia" not in sectors
    csud3 = next(
        g for g in layers.stock_sectors if "CSUD3" in [h.id for h in g.holdings]
    )
    assert csud3.label == "Financeiro"
    segment = next(
        g for g in layers.stock_segments if "CSUD3" in [h.id for h in g.holdings]
    )
    assert (segment.label, segment.parent) == (
        "Serviços Financeiros Diversos",
        "Financeiro",
    )


def test_the_sector_layer_puts_csud3_with_the_other_financials_and_not_with_utilities():
    rows = (
        SnapshotRow("BBSE3", "BBSE3", "acao", 1000.0),
        SnapshotRow("CSUD3", "CSUD3", "acao", 1000.0),
        SnapshotRow("ISAE4", "ISAE4", "acao", 1000.0),
    )

    layers = build_layers(rows)

    financeiro = next(g for g in layers.stock_sectors if g.label == "Financeiro")
    utilidade = next(g for g in layers.stock_sectors if g.label == "Utilidade Pública")
    assert {h.id for h in financeiro.holdings} == {"BBSE3", "CSUD3"}
    assert {h.id for h in utilidade.holdings} == {"ISAE4"}


# --- the classification is not only cosmetic: it drives which valuation methods apply ------


def test_graham_is_no_longer_excluded_for_csud3_by_a_technology_label():
    asset = get_asset("CSUD3")

    result = applicability(
        ValuationMethod.GRAHAM, asset.asset_class, asset.sector, asset.industry
    )

    assert result.applicable is True


def test_the_old_label_did_exclude_graham_and_still_would_for_any_technology_company():
    old = applicability(
        ValuationMethod.GRAHAM,
        "equity",
        "Utilidade Pública / Tecnologia",
        "Processamento de Dados e Serviços",
    )

    assert old.applicable is False and "tecnologia" in old.reason.lower()


def test_the_lead_method_for_csud3_is_graham_since_financial_services_are_not_dividend_led():
    asset = get_asset("CSUD3")

    order = ordered_methods(asset.asset_class, asset.sector, asset.industry)

    assert order[0] is ValuationMethod.GRAHAM and ValuationMethod.BAZIN in order


@pytest.mark.parametrize(
    ("ticker", "lead"),
    [
        ("BBSE3", ValuationMethod.BAZIN),  # seguros: o dividendo é o produto
        ("ISAE4", ValuationMethod.BAZIN),  # energia elétrica regulada
        ("ABCB4", ValuationMethod.BAZIN),  # bancos
        ("KLBN4", ValuationMethod.GRAHAM),
    ],
)
def test_the_lead_method_of_the_other_stocks_did_not_change(ticker, lead):
    asset = get_asset(ticker)

    assert ordered_methods(asset.asset_class, asset.sector, asset.industry)[0] is lead
