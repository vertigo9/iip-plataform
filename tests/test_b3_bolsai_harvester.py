import json
from typing import ClassVar

import pytest

from iip.sources.b3_bolsai import build_fii_target, build_target
from iip.sources.b3_bolsai_harvester import (
    BolsaiHTTPHarvester,
    FetchedFii,
    FetchedFundamentals,
)


class FakeResponse:
    status = 200

    def __init__(self, body=None):
        self._body = body or json.dumps(
            {"ticker": "PETR4", "close_price": 45.67, "pl": 5.32}
        ).encode("utf-8")

    def read(self):
        return self._body


class FakeFiiResponse:
    status = 200

    def read(self):
        return json.dumps(
            {"ticker": "HGLG11", "close_price": 162.45, "dividend_yield_ttm": 8.74}
        ).encode("utf-8")


def test_harvester_requires_an_api_key():
    with pytest.raises(ValueError):
        BolsaiHTTPHarvester(api_key="")


def test_fetch_sends_key_only_in_x_api_key_header():
    captured = {}

    def opener(request, timeout):
        captured["headers"] = request.headers
        captured["url"] = request.full_url
        return FakeResponse()

    harvester = BolsaiHTTPHarvester(api_key="my-secret-key", opener=opener)
    harvester.fetch(build_target("petr4"))

    assert captured["headers"]["X-api-key"] == "my-secret-key"
    assert "my-secret-key" not in captured["url"]


def test_fetch_parses_response_into_fundamentals():
    def opener(request, timeout):
        return FakeResponse()

    harvester = BolsaiHTTPHarvester(api_key="key", opener=opener)
    result = harvester.fetch(build_target("petr4"))

    assert isinstance(result, FetchedFundamentals)
    assert result.status_code == 200
    assert result.fundamentals.close_price == 45.67
    assert result.fundamentals.pl == 5.32


def test_fetch_many_preserves_order():
    def opener(request, timeout):
        return FakeResponse()

    harvester = BolsaiHTTPHarvester(api_key="key", opener=opener)
    results = harvester.fetch_many((build_target("petr4"), build_target("mxrf11")))

    assert len(results) == 2
    assert all(isinstance(r, FetchedFundamentals) for r in results)


def test_fetch_defaults_status_when_none():
    class NoStatusResponse:
        status = None

        def read(self):
            return json.dumps({"ticker": "PETR4"}).encode("utf-8")

    def opener(request, timeout):
        return NoStatusResponse()

    harvester = BolsaiHTTPHarvester(api_key="key", opener=opener)
    result = harvester.fetch(build_target("petr4"))

    assert result.status_code == 200
    assert result.fundamentals.close_price is None


def test_fetch_fii_preserves_transport_metadata():
    captured = {}

    def opener(request, timeout):
        captured["request"] = request

        class Response:
            status = 200
            headers: ClassVar[dict[str, str]] = {
                "Content-Type": "application/json; charset=utf-8"
            }

            def read(self):
                return json.dumps(
                    {
                        "ticker": "HGLG11",
                        "reference_date": "2026-09-12",
                        "close_price": 160.0,
                        "book_value_per_share": 150.0,
                        "pvp": 1.0667,
                        "dividend_yield_ttm": 8.5,
                        "net_asset_value": 150.0,
                        "shares_outstanding": 1000000,
                    }
                ).encode()

            def geturl(self):
                return "https://api.usebolsai.com/v2/fii/HGLG11"

        return Response()

    harvester = BolsaiHTTPHarvester(api_key="key", opener=opener)
    result = harvester.fetch_fii(build_fii_target("hglg11"))

    assert result.status_code == 200
    assert result.content_type == "application/json"
    assert result.body
    assert result.body.startswith(b"{")
    assert result.final_url == "https://api.usebolsai.com/v2/fii/HGLG11"
    assert result.target.provider == "b3"
    assert result.target.role == "market_validation"
    assert result.target.year is None


def test_fetch_fii_falls_back_to_target_url_without_geturl():
    def opener(request, timeout):
        class Response:
            status = 200
            headers: ClassVar[dict[str, str]] = {"Content-Type": "application/json"}

            def read(self):
                return b'{"ticker":"HGLG11"}'

        return Response()

    target = build_fii_target("HGLG11")
    harvester = BolsaiHTTPHarvester(api_key="key", opener=opener)
    result = harvester.fetch_fii(target)

    assert result.final_url == target.url
    assert result.content_type == "application/json"
    assert result.body == b'{"ticker":"HGLG11"}'

def test_fetch_fii_uses_the_fii_target_and_parser():
    def opener(request, timeout):
        return FakeFiiResponse()

    harvester = BolsaiHTTPHarvester(api_key="key", opener=opener)
    result = harvester.fetch_fii(build_fii_target("hglg11"))

    assert isinstance(result, FetchedFii)
    assert result.status_code == 200
    assert result.fii.ticker == "HGLG11"
    assert result.fii.dividend_yield_ttm == 8.74


def test_fetch_many_fiis_preserves_order():
    def opener(request, timeout):
        return FakeFiiResponse()

    harvester = BolsaiHTTPHarvester(api_key="key", opener=opener)
    results = harvester.fetch_many_fiis(
        (build_fii_target("hglg11"), build_fii_target("mxrf11"))
    )

    assert len(results) == 2
    assert all(isinstance(r, FetchedFii) for r in results)
