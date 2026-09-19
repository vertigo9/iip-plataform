from types import SimpleNamespace

from iip.portfolio.pipeline import IntegratedPortfolioPipeline, ingest_registered_assets
from iip.portfolio.registry import get_asset


class FakeRoute:
    def __init__(self, provider, source):
        self.provider = provider
        self.source = source


class FakeRouted:
    def __init__(self, routes):
        self.routes = tuple(routes)
        self.primary = self.routes[0] if self.routes else None


class FakeRouter:
    def __init__(self, routes):
        self.routes = routes

    def route(self, asset):
        return FakeRouted(self.routes)

    @staticmethod
    def _asset_ref(asset):
        return asset


class FakeAtlas:
    def __init__(self, documents):
        self.documents = documents

    def ingest(self, asset, years):
        return SimpleNamespace(documents=self.documents)


def test_integrated_pipeline_uses_first_successful_route():
    asset = get_asset("XPML11")
    calls = []

    def factory(provider):
        calls.append(provider)
        return FakeAtlas(("xp-document",))

    router = FakeRouter(
        (
            FakeRoute("xp_asset", SimpleNamespace(provider="xp_asset")),
            FakeRoute("b3", SimpleNamespace(provider="b3")),
        )
    )
    result = IntegratedPortfolioPipeline(
        source_router=router,
        atlas_pipeline_factory=factory,
    ).run(asset, range(2026, 2027))

    assert result.discovered == ("xp-document",)
    assert calls == ["xp_asset"]


def test_integrated_pipeline_falls_back_after_provider_failure():
    asset = get_asset("XPML11")
    calls = []

    def factory(provider):
        calls.append(provider)
        if provider == "xp_asset":
            raise RuntimeError("offline")
        return FakeAtlas(("b3-document",))

    router = FakeRouter(
        (
            FakeRoute("xp_asset", SimpleNamespace(provider="xp_asset")),
            FakeRoute("b3", SimpleNamespace(provider="b3")),
        )
    )
    result = IntegratedPortfolioPipeline(
        source_router=router,
        atlas_pipeline_factory=factory,
    ).run(asset, range(2026, 2027))

    assert result.discovered == ("b3-document",)
    assert calls == ["xp_asset", "b3"]
    assert result.errors == ("xp_asset:RuntimeError",)


def test_integrated_pipeline_reports_missing_route():
    asset = get_asset("BBSE3")
    router = FakeRouter(())
    result = IntegratedPortfolioPipeline(
        source_router=router,
        atlas_pipeline_factory=lambda provider: None,
    ).run(asset, range(2026, 2027))

    assert result.discovered == ()
    assert result.errors == ("no_route",)


def test_registered_assets_are_converted_and_sent_to_universal_ingestion():
    class Result:
        def __init__(self, ticker, succeeded):
            self.ticker = ticker
            self.succeeded = succeeded

    class Service:
        def __init__(self):
            self.assets = ()

        def ingest_many(self, assets, years):
            self.assets = tuple(assets)
            return tuple(Result(asset.ticker, asset.ticker == "XPML11") for asset in self.assets)

    service = Service()
    result = ingest_registered_assets(
        service,
        range(2026, 2027),
        (get_asset("XPML11"), get_asset("BBSE3")),
    )

    assert [asset.ticker for asset in service.assets] == ["XPML11", "BBSE3"]
    assert result.succeeded[0].ticker == "XPML11"
    assert result.failed[0].ticker == "BBSE3"
