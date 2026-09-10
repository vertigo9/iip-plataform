import json

from iip.sources.receita_federal import build_target
from iip.sources.receita_federal_harvester import (
    FetchedCnpj,
    ReceitaFederalHTTPHarvester,
)


class FakeResponse:
    status = 200

    def __init__(self, body=None):
        self._body = body or json.dumps(
            {"cnpj": "06990590000123", "razao_social": "GOOGLE BRASIL INTERNET LTDA."}
        ).encode("utf-8")

    def read(self):
        return self._body


def test_fetch_parses_response_into_record():
    calls = []

    def opener(request, timeout):
        calls.append((request, timeout))
        return FakeResponse()

    harvester = ReceitaFederalHTTPHarvester(opener=opener)
    result = harvester.fetch(build_target("06990590000123"))

    assert isinstance(result, FetchedCnpj)
    assert result.status_code == 200
    assert result.record.razao_social == "GOOGLE BRASIL INTERNET LTDA."
    assert len(calls) == 1


def test_fetch_sends_expected_headers_and_no_auth_needed():
    captured = {}

    def opener(request, timeout):
        captured["headers"] = request.headers
        return FakeResponse()

    harvester = ReceitaFederalHTTPHarvester(opener=opener, user_agent="test-agent")
    harvester.fetch(build_target("06990590000123"))

    assert captured["headers"]["User-agent"] == "test-agent"
    assert captured["headers"]["Accept"] == "application/json"
    assert "Authorization" not in captured["headers"]
    assert "X-api-key" not in captured["headers"]


def test_fetch_many_preserves_order():
    def opener(request, timeout):
        return FakeResponse()

    harvester = ReceitaFederalHTTPHarvester(opener=opener)
    results = harvester.fetch_many(
        (build_target("06990590000123"), build_target("00000000000191"))
    )

    assert len(results) == 2
    assert all(isinstance(r, FetchedCnpj) for r in results)


def test_fetch_defaults_status_when_none():
    class NoStatusResponse:
        status = None

        def read(self):
            return json.dumps({"cnpj": "06990590000123"}).encode("utf-8")

    def opener(request, timeout):
        return NoStatusResponse()

    harvester = ReceitaFederalHTTPHarvester(opener=opener)
    result = harvester.fetch(build_target("06990590000123"))

    assert result.status_code == 200
    assert result.record.razao_social is None
