import json

import pytest

from iip.sources.b3_brapi import build_target
from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester, FetchedQuotes


class FakeResponse:
    status = 200

    def __init__(self, body=None):
        self._body = body or json.dumps(
            {"results": [{"symbol": "PETR4", "regularMarketPrice": 38.42}]}
        ).encode("utf-8")

    def read(self):
        return self._body


def test_harvester_requires_a_token():
    with pytest.raises(ValueError):
        BrapiHTTPHarvester(token="")


def test_fetch_sends_token_only_in_authorization_header():
    captured = {}

    def opener(request, timeout):
        captured["headers"] = request.headers
        captured["url"] = request.full_url
        return FakeResponse()

    harvester = BrapiHTTPHarvester(token="my-secret-token", opener=opener)
    harvester.fetch(build_target(("petr4",)))

    assert captured["headers"]["Authorization"] == "Bearer my-secret-token"
    assert "my-secret-token" not in captured["url"]


def test_fetch_parses_response_into_quotes():
    def opener(request, timeout):
        return FakeResponse()

    harvester = BrapiHTTPHarvester(token="tok", opener=opener)
    result = harvester.fetch(build_target(("petr4",)))

    assert isinstance(result, FetchedQuotes)
    assert result.status_code == 200
    assert result.quotes[0].regular_market_price == 38.42


def test_fetch_many_preserves_order():
    def opener(request, timeout):
        return FakeResponse()

    harvester = BrapiHTTPHarvester(token="tok", opener=opener)
    results = harvester.fetch_many(
        (build_target(("petr4",)), build_target(("aapl34",)))
    )

    assert len(results) == 2
    assert all(isinstance(r, FetchedQuotes) for r in results)


def test_fetch_defaults_status_when_none():
    class NoStatusResponse:
        status = None

        def read(self):
            return json.dumps({"results": []}).encode("utf-8")

    def opener(request, timeout):
        return NoStatusResponse()

    harvester = BrapiHTTPHarvester(token="tok", opener=opener)
    result = harvester.fetch(build_target(("petr4",)))

    assert result.status_code == 200
    assert result.quotes == ()
