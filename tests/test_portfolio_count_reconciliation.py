from iip.portfolio.registry import (
    ALL_PORTFOLIO_ASSETS,
    CLOSED_ASSETS,
    PORTFOLIO_ASSETS,
    assets_by_class,
)
from iip.portfolio.source_policy import PortfolioSourcePolicyResolver


def test_all_real_portfolio_assets_can_be_resolved():
    results = PortfolioSourcePolicyResolver().resolve_many()

    # DATABASE v3.2 contains 14 equities + 21 fund instruments +
    # LFTB11 + the Daycoval FMP/AXIA3 position outside the rebalance pool.
    # This is 37 registry records, not 40. Two of them (BTCI11 and PVBI11) are closed
    # positions kept in the registry with their data: the ACTIVE portfolio is 35.
    assert len(ALL_PORTFOLIO_ASSETS) == 37
    assert len(CLOSED_ASSETS) == 2
    assert len(PORTFOLIO_ASSETS) == 35
    assert len(results) == 35


def test_registry_count_breakdown_matches_database():
    assert len(assets_by_class("equity")) == 14
    # 21 fund instruments in the DATABASE; 19 are still held (BTCI11 and PVBI11 were closed)
    assert len(assets_by_class("fund")) == 19
    assert len([a for a in ALL_PORTFOLIO_ASSETS if a.asset_class == "fund"]) == 21
    assert len(assets_by_class("etf")) == 1
    assert len(assets_by_class("fixed_income")) == 1
