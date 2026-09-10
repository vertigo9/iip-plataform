from iip.sources.cvm_fii import build_target
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester, FetchedFiiReport
from tests.test_cvm_fii import make_zip


class FakeResponse:
    status = 200

    def __init__(self, body=None):
        self._body = body if body is not None else make_zip()

    def read(self):
        return self._body


def test_fetch_parses_all_three_reports():
    def opener(request, timeout):
        return FakeResponse()

    harvester = CvmFiiHTTPHarvester(opener=opener)
    result = harvester.fetch(build_target(2026))

    assert isinstance(result, FetchedFiiReport)
    assert result.status_code == 200
    assert len(result.geral) == 1
    assert len(result.ativo_passivo) == 1
    assert len(result.complemento) == 1
    assert result.geral[0].nome_fundo_classe == "BTGP LOGISTICA FII"


def test_fetch_sends_expected_headers():
    captured = {}

    def opener(request, timeout):
        captured["headers"] = request.headers
        captured["timeout"] = timeout
        return FakeResponse()

    harvester = CvmFiiHTTPHarvester(opener=opener, user_agent="test-agent")
    harvester.fetch(build_target(2026))

    assert captured["headers"]["User-agent"] == "test-agent"
    assert captured["headers"]["Accept"] == "application/zip"
    assert captured["timeout"] == 60.0


def test_fetch_defaults_status_when_none():
    class NoStatusResponse:
        status = None

        def read(self):
            return make_zip()

    def opener(request, timeout):
        return NoStatusResponse()

    harvester = CvmFiiHTTPHarvester(opener=opener)
    result = harvester.fetch(build_target(2026))

    assert result.status_code == 200
