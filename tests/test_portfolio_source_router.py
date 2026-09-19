from __future__ import annotations

from typing import ClassVar

import pytest
from pydantic import SecretStr

from iip.atlas import build_configured_portfolio_ingestion
from iip.config import IIPSettings
from iip.portfolio.registry import get_asset
from iip.portfolio.source_router import PortfolioSourceRouter
from iip.sources.adapter_catalog import (
    AdapterKind,
    AdapterReadiness,
    adapter_descriptor,
)
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester
from iip.sources.b3_brapi import build_target as build_brapi_target
from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester
from iip.sources.b3_brapi_provider import BrapiMarketProvider, adapt_quotes
from iip.sources.b3_equity_provider import BolsaiEquityProvider, adapt_fundamentals
from iip.sources.cvm_fii import build_target as build_cvm_target
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester
from iip.sources.cvm_fii_provider import adapt_fii_report
from iip.sources.registry import AssetRef
from tests.test_cvm_fii import make_zip


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


def test_equity_without_institutional_url_uses_b3_market_source():
    asset = get_asset("BBSE3")
    assert asset is not None

    ref = PortfolioSourceRouter._asset_ref(asset)

    assert ref.sources[0].provider == "b3"
    assert ref.sources[0].role == "market_validation"


def test_portfolio_manager_alias_is_normalized_to_canonical_provider():
    asset = get_asset("HGRU11")
    assert asset is not None

    ref = PortfolioSourceRouter.asset_ref(asset)

    assert ref.sources[0].provider == "patria"


def test_bolsai_equity_adapter_preserves_raw_response_for_atlas():
    asset = AssetRef("BBSE3", "equity", "stock")
    target = BolsaiEquityProvider().discover(asset, range(2026, 2027))[0]

    class Response:
        status = 200
        headers: ClassVar[dict[str, str]] = {
            "Content-Type": "application/json; charset=utf-8"
        }

        def read(self):
            return b'{"ticker":"BBSE3","close_price":41.69}'

        def geturl(self):
            return target.url

    fetched = BolsaiHTTPHarvester(
        api_key="test-key", opener=lambda request, timeout: Response()
    ).fetch(target)
    document = adapt_fundamentals(fetched)

    assert document.ticker == "BBSE3"
    assert document.provider == "b3"
    assert document.body == b'{"ticker":"BBSE3","close_price":41.69}'
    assert document.content_hash


def test_configured_ingestion_enables_b3_only_with_real_credential(tmp_path):
    without_key = build_configured_portfolio_ingestion(
        str(tmp_path / "without"),
        settings=IIPSettings(
            obsidian_vault=tmp_path / "without",
            bolsai_api_key=SecretStr(""),
            brapi_token=SecretStr(""),
        ),
    )
    with_key = build_configured_portfolio_ingestion(
        str(tmp_path / "with"),
        settings=IIPSettings(
            obsidian_vault=tmp_path / "with",
            bolsai_api_key=SecretStr("test-key"),
            brapi_token=SecretStr(""),
        ),
    )

    assert "b3" not in without_key.transports
    assert "b3" in with_key.transports


def test_configured_ingestion_enables_brapi_independently(tmp_path):
    service = build_configured_portfolio_ingestion(
        str(tmp_path / "brapi"),
        settings=IIPSettings(
            obsidian_vault=tmp_path / "brapi",
            bolsai_api_key=SecretStr(""),
            brapi_token=SecretStr("brapi-token"),
        ),
    )

    assert "b3" not in service.transports
    assert "b3_brapi" in service.transports


def test_adapter_catalog_distinguishes_ready_configured_and_mapped_providers():
    xp = adapter_descriptor("xp_asset")
    b3 = adapter_descriptor("b3")
    btg = adapter_descriptor("btg")

    assert xp is not None
    assert xp.readiness == AdapterReadiness.READY
    assert xp.kind == AdapterKind.DOCUMENT
    assert b3 is not None
    assert b3.readiness == AdapterReadiness.CONFIGURATION_REQUIRED
    assert btg is not None
    assert btg.readiness == AdapterReadiness.MAPPED


def test_cvm_fii_adapter_filters_bulk_report_by_cnpj():
    target = build_cvm_target(2026)
    target = target.__class__(
        **{**target.__dict__, "ticker": "BTLG11", "cnpj": "11839593000109"}
    )

    class Response:
        status = 200
        headers: ClassVar[dict[str, str]] = {"Content-Type": "application/zip"}

        def read(self):
            return make_zip()

        def geturl(self):
            return target.url

    report = CvmFiiHTTPHarvester(opener=lambda request, timeout: Response()).fetch(
        target
    )
    document = adapt_fii_report(report)

    assert document.ticker == "BTLG11"
    assert document.provider == "cvm"
    assert document.content_type == "application/zip"
    assert document.content_hash


def test_cvm_fii_adapter_rejects_unmatched_cnpj():
    target = build_cvm_target(2026)
    target = target.__class__(
        **{**target.__dict__, "ticker": "BTLG11", "cnpj": "00000000000000"}
    )

    class Response:
        status = 200
        headers: ClassVar[dict[str, str]] = {"Content-Type": "application/zip"}

        def read(self):
            return make_zip()

        def geturl(self):
            return target.url

    report = CvmFiiHTTPHarvester(opener=lambda request, timeout: Response()).fetch(
        target
    )
    with pytest.raises(ValueError, match="CNPJ not found"):
        adapt_fii_report(report)


def test_brapi_adapter_preserves_quote_payload():
    target = build_brapi_target(("AAPL34",))

    class Response:
        status = 200
        headers: ClassVar[dict[str, str]] = {"Content-Type": "application/json"}

        def read(self):
            return b'{"results":[{"symbol":"AAPL34","regularMarketPrice":10}]}'

        def geturl(self):
            return target.url

    captured = {}

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.headers["Authorization"]
        return Response()

    fetched = BrapiHTTPHarvester(token="secret", opener=opener).fetch(target)
    document = adapt_quotes(fetched)

    assert BrapiMarketProvider().supports(AssetRef("AAPL34", "bdr", ""))
    assert "secret" not in captured["url"]
    assert captured["authorization"] == "Bearer secret"
    assert document.ticker == "AAPL34"
    assert document.provider == "b3_brapi"
    assert document.body.startswith(b'{"results"')


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
