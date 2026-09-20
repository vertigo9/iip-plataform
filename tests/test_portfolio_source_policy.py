from iip.portfolio.source_policy import PortfolioSourcePolicyResolver
from iip.registry.models import AssetClass


def test_xpml11_resolves_to_xp_asset():
    result = PortfolioSourcePolicyResolver().resolve("XPML11")
    assert result is not None
    assert result.policy.asset_class == AssetClass.FUND
    assert result.institutional_provider is not None
    assert result.institutional_provider.name == "xp_asset"


def test_hgru11_resolves_to_patria():
    result = PortfolioSourcePolicyResolver().resolve("HGRU11")
    assert result is not None
    assert result.institutional_provider is not None
    assert result.institutional_provider.name == "patria"


def test_cdii11_resolves_to_sparta():
    result = PortfolioSourcePolicyResolver().resolve("CDII11")
    assert result is not None
    assert result.institutional_provider is not None
    assert result.institutional_provider.name == "sparta"


def test_btc11_resolves_to_btg():
    # BTCI11 is a closed position, so the default (active) resolver skips it, but the
    # knowledge about its provider is preserved for when the user buys it again
    assert PortfolioSourcePolicyResolver().resolve("BTCI11") is None

    from iip.portfolio.registry import ALL_PORTFOLIO_ASSETS

    result = PortfolioSourcePolicyResolver(assets=ALL_PORTFOLIO_ASSETS).resolve(
        "BTCI11"
    )
    assert result is not None
    assert result.institutional_provider is not None
    assert result.institutional_provider.name == "btg"


def test_unknown_asset_returns_none():
    assert PortfolioSourcePolicyResolver().resolve("NAOEXISTE11") is None


def test_policy_keeps_fund_priority():
    result = PortfolioSourcePolicyResolver().resolve("XPML11")
    assert result is not None
    assert result.policy.priority == (
        "cvm",
        "fnet",
        "institutional",
        "b3",
        "market_data",
    )


def test_all_real_portfolio_assets_can_be_resolved():
    results = PortfolioSourcePolicyResolver().resolve_many()

    # DATABASE v3.2: 14 equities + 21 funds + LFTB11 + Daycoval FMP/AXIA3.
    # Total registry records = 37, of which 35 are active (BTCI11 and PVBI11 are closed).
    assert len(results) == 35


def test_selected_assets_have_expected_provider():
    results = PortfolioSourcePolicyResolver().resolve_many(
        ("HGRU11", "CDII11", "CRAA11", "MANA11", "LFTB11")
    )
    mapping = {
        item.asset.ticker: (
            item.institutional_provider.name if item.institutional_provider else None
        )
        for item in results
    }
    assert mapping["HGRU11"] == "patria"
    assert mapping["CDII11"] == "sparta"
    assert mapping["CRAA11"] == "sparta"
    assert mapping["MANA11"] == "manati"
    assert mapping["LFTB11"] is None
