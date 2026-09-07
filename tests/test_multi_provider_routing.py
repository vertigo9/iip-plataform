from __future__ import annotations

from iip.sources.discovery import MultiProviderDiscovery
from iip.sources.provider import DocumentProvider
from iip.sources.provider_registry import ProviderRegistry
from iip.sources.registry import AssetRef, SourceRef, SourceRegistry
from iip.sources.router import SourceRouter


class FakeProvider(DocumentProvider):
    def __init__(self, name, *, supported=True, result=()):
        self.provider_name = name
        self.supported = supported
        self.result = tuple(result)
        self.calls = 0

    def supports(self, asset):
        return self.supported

    def discover(self, asset, years):
        self.calls += 1
        return self.result


def make_asset():
    return AssetRef(
        ticker="XPML11",
        asset_class="FII",
        asset_subtype="Tijolo",
        segment="Shopping",
        sources=(
            SourceRef(
                "xp_asset",
                "institutional_primary",
                1,
                "https://www.xpasset.com.br/fundos/xp-malls/",
                True,
            ),
            SourceRef(
                "secondary",
                "market_validation",
                2,
                "https://example.com/secondary",
                True,
            ),
            SourceRef(
                "inactive", "regulatory", 3, "https://example.com/inactive", False
            ),
        ),
    )


def registries(*providers):
    source_registry = SourceRegistry()
    source_registry.register(make_asset())
    provider_registry = ProviderRegistry()
    for provider in providers:
        provider_registry.register(provider)
    return source_registry, provider_registry


def test_router_respects_priority_and_skips_inactive():
    first = FakeProvider("xp_asset", result=("xp-1",))
    second = FakeProvider("secondary", result=("secondary-1",))

    sr, pr = registries(first, second)
    routes = SourceRouter(
        source_registry=sr,
        provider_registry=pr,
    ).routes_for(make_asset())

    assert [route.source.provider for route in routes] == ["xp_asset", "secondary"]
    assert [route.source.priority for route in routes] == [1, 2]


def test_primary_route_is_lowest_active_priority():
    first = FakeProvider("xp_asset", result=("xp-1",))
    second = FakeProvider("secondary", result=("secondary-1",))

    sr, pr = registries(first, second)
    route = SourceRouter(
        source_registry=sr,
        provider_registry=pr,
    ).primary_route(make_asset())

    assert route is not None
    assert route.source.provider == "xp_asset"


def test_fallback_routes_exclude_primary():
    first = FakeProvider("xp_asset", result=("xp-1",))
    second = FakeProvider("secondary", result=("secondary-1",))

    sr, pr = registries(first, second)
    routes = SourceRouter(
        source_registry=sr,
        provider_registry=pr,
    ).fallback_routes(make_asset())

    assert len(routes) == 1
    assert routes[0].source.provider == "secondary"


def test_discovery_uses_primary_when_it_returns_documents():
    first = FakeProvider("xp_asset", result=("doc-a",))
    second = FakeProvider("secondary", result=("doc-b",))

    sr, pr = registries(first, second)
    result = MultiProviderDiscovery(
        SourceRouter(source_registry=sr, provider_registry=pr)
    ).discover(make_asset(), range(2026, 2027))

    assert len(result) == 1
    assert result[0].route.source.provider == "xp_asset"
    assert result[0].documents == ("doc-a",)
    assert first.calls == 1
    assert second.calls == 0


def test_discovery_falls_back_when_primary_is_empty():
    first = FakeProvider("xp_asset", result=())
    second = FakeProvider("secondary", result=("doc-b",))

    sr, pr = registries(first, second)
    result = MultiProviderDiscovery(
        SourceRouter(source_registry=sr, provider_registry=pr)
    ).discover(make_asset(), range(2026, 2027))

    assert len(result) == 1
    assert result[0].route.source.provider == "secondary"
    assert result[0].documents == ("doc-b",)
    assert first.calls == 1
    assert second.calls == 1


def test_discovery_falls_back_when_primary_raises():
    class FailingProvider(FakeProvider):
        def discover(self, asset, years):
            self.calls += 1
            raise RuntimeError("provider unavailable")

    first = FailingProvider("xp_asset")
    second = FakeProvider("secondary", result=("doc-b",))

    sr, pr = registries(first, second)
    result = MultiProviderDiscovery(
        SourceRouter(source_registry=sr, provider_registry=pr)
    ).discover(make_asset(), range(2026, 2027))

    assert len(result) == 1
    assert result[0].route.source.provider == "secondary"


def test_discovery_all_keeps_all_successful_routes():
    first = FakeProvider("xp_asset", result=("doc-a",))
    second = FakeProvider("secondary", result=("doc-b",))

    sr, pr = registries(first, second)
    result = MultiProviderDiscovery(
        SourceRouter(source_registry=sr, provider_registry=pr)
    ).discover_all(make_asset(), range(2026, 2027))

    assert [item.route.source.provider for item in result] == ["xp_asset", "secondary"]
    assert [item.documents for item in result] == [("doc-a",), ("doc-b",)]


def test_missing_named_provider_does_not_crash():
    first = FakeProvider("secondary", result=("doc-b",))

    sr, pr = registries(first)
    route = SourceRouter(
        source_registry=sr,
        provider_registry=pr,
    ).primary_route(make_asset())

    assert route is not None
    assert route.source.provider == "xp_asset"
    assert route.provider is first
