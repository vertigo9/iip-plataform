from __future__ import annotations

from iip.portfolio.registry import get_asset
from iip.portfolio.source_router import PortfolioSourceRouter


class FakeProvider:
    def __init__(self, name):
        self.provider_name = name

    def supports(self, asset):
        return True


class FakeRouter:
    def __init__(self):
        self.calls = []

    def routes_for(self, asset):
        self.calls.append(asset)
        return ()


def test_portfolio_asset_is_adapted_to_asset_ref():
    asset = get_asset("XPML11")
    assert asset is not None

    ref = PortfolioSourceRouter._asset_ref(asset)

    assert ref.ticker == "XPML11"
    assert ref.asset_class == "fund"
    assert ref.sources
    assert ref.sources[0].role == "institutional_primary"
    assert ref.sources[0].url == asset.source_url


def test_asset_without_institutional_url_has_empty_source_list():
    asset = get_asset("BBSE3")
    assert asset is not None

    ref = PortfolioSourceRouter._asset_ref(asset)

    assert ref.sources == ()


def test_router_bridge_delegates_to_existing_router():
    asset = get_asset("XPML11")
    fake_router = FakeRouter()
    bridge = PortfolioSourceRouter(fake_router)

    result = bridge.route(asset)

    assert result.asset is asset
    assert fake_router.calls
    assert fake_router.calls[0].ticker == "XPML11"
    assert result.routes == ()


def test_routed_asset_primary_and_fallback_helpers():
    class Router:
        def routes_for(self, asset):
            class R:
                def __init__(self, provider):
                    self.source = type("S", (), {"provider": provider})()
                    self.provider = provider

            return (R("xp_asset"), R("b3"))

    asset = get_asset("XPML11")
    result = PortfolioSourceRouter(Router()).route(asset)

    assert result.primary.provider == "xp_asset"
    assert result.fallbacks[0].provider == "b3"
