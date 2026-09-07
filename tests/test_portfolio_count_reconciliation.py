from iip.portfolio.registry import PORTFOLIO_ASSETS, assets_by_class
from iip.portfolio.source_policy import PortfolioSourcePolicyResolver


def test_all_real_portfolio_assets_can_be_resolved():
    results = PortfolioSourcePolicyResolver().resolve_many()

    # DATABASE v3.2 contains 14 equities + 21 fund instruments +
    # LFTB11 + the Daycoval FMP/AXIA3 position outside the rebalance pool.
    # This is 37 registry records, not 40.
    assert len(PORTFOLIO_ASSETS) == 37
    assert len(results) == 37


def test_registry_count_breakdown_matches_database():
    assert len(assets_by_class("equity")) == 14
    assert len(assets_by_class("fund")) == 21
    assert len(assets_by_class("etf")) == 1
    assert len(assets_by_class("fixed_income")) == 1
