from datetime import date

from iip.sources.bacen import build_target, SELIC
from iip.sources.bacen_harvester import BacenHTTPHarvester, FetchedSeries


class FakeResponse:
    status = 200

    def __init__(self, body=b'[{"data":"01/07/2026","valor":"13.75"}]'):
        self._body = body

    def read(self):
        return self._body


def make_target():
    return build_target(SELIC, date(2026, 7, 1), date(2026, 7, 31))


def test_fetch_parses_response_into_points():
    calls = []

    def opener(request, timeout):
        calls.append((request, timeout))
        return FakeResponse()

    harvester = BacenHTTPHarvester(opener=opener)
    result = harvester.fetch(make_target())

    assert isinstance(result, FetchedSeries)
    assert result.status_code == 200
    assert len(result.points) == 1
    assert result.points[0].value == 13.75
    assert len(calls) == 1
    request, timeout = calls[0]
    assert request.full_url == make_target().url
    assert timeout == 20.0


def test_fetch_sends_expected_headers():
    captured = {}

    def opener(request, timeout):
        captured["headers"] = request.headers
        return FakeResponse()

    harvester = BacenHTTPHarvester(opener=opener, user_agent="test-agent")
    harvester.fetch(make_target())

    assert captured["headers"]["User-agent"] == "test-agent"
    assert captured["headers"]["Accept"] == "application/json"


def test_fetch_many_preserves_order():
    def opener(request, timeout):
        return FakeResponse()

    harvester = BacenHTTPHarvester(opener=opener)
    targets = (make_target(), make_target())

    results = harvester.fetch_many(targets)

    assert len(results) == 2
    assert all(isinstance(r, FetchedSeries) for r in results)


def test_fetch_defaults_status_when_none():
    class NoStatusResponse:
        status = None

        def read(self):
            return b"[]"

    def opener(request, timeout):
        return NoStatusResponse()

    harvester = BacenHTTPHarvester(opener=opener)
    result = harvester.fetch(make_target())

    assert result.status_code == 200
    assert result.points == ()
