import json

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
