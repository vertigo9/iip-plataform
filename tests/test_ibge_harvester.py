import json

from iip.sources.ibge import build_target
from iip.sources.ibge_harvester import FetchedAggregate, IbgeHTTPHarvester


def make_body():
    return json.dumps(
        [
            {
                "id": "63",
                "variavel": "IPCA - Variação mensal",
                "unidade": "%",
                "resultados": [
                    {
                        "classificacoes": [],
                        "series": [
                            {
                                "localidade": {"id": "1", "nome": "Brasil"},
                                "serie": {"202607": "0.83"},
                            }
                        ],
                    }
                ],
            }
        ]
    ).encode("utf-8")


class FakeResponse:
    status = 200

    def __init__(self, body=None):
        self._body = body if body is not None else make_body()

    def read(self):
        return self._body


def make_target():
    return build_target(1705, 63)


def test_fetch_parses_response_into_points():
    calls = []

    def opener(request, timeout):
        calls.append((request, timeout))
        return FakeResponse()

    harvester = IbgeHTTPHarvester(opener=opener)
    result = harvester.fetch(make_target())

    assert isinstance(result, FetchedAggregate)
    assert result.status_code == 200
    assert len(result.points) == 1
    assert result.points[0].value == 0.83
    assert len(calls) == 1


def test_fetch_sends_expected_headers():
    captured = {}

    def opener(request, timeout):
        captured["headers"] = request.headers
        return FakeResponse()

    harvester = IbgeHTTPHarvester(opener=opener, user_agent="test-agent")
    harvester.fetch(make_target())

    assert captured["headers"]["User-agent"] == "test-agent"
    assert captured["headers"]["Accept"] == "application/json"


def test_fetch_many_preserves_order():
    def opener(request, timeout):
        return FakeResponse()

    harvester = IbgeHTTPHarvester(opener=opener)
    results = harvester.fetch_many((make_target(), make_target()))

    assert len(results) == 2
    assert all(isinstance(r, FetchedAggregate) for r in results)


def test_fetch_defaults_status_when_none():
    class NoStatusResponse:
        status = None

        def read(self):
            return b"[]"

    def opener(request, timeout):
        return NoStatusResponse()

    harvester = IbgeHTTPHarvester(opener=opener)
    result = harvester.fetch(make_target())

    assert result.status_code == 200
    assert result.points == ()
