from iip.sources.cvm_fiagro import build_target
from iip.sources.cvm_fiagro_harvester import CvmFiagroHTTPHarvester, FetchedFiagroReport
from tests.test_cvm_fiagro import make_zip


class FakeResponse:
    status = 200

    def __init__(self, body=None):
        self._body = body if body is not None else make_zip()

    def read(self):
        return self._body


def test_fetch_parses_informe_and_subclasse():
    def opener(request, timeout):
        return FakeResponse()

    harvester = CvmFiagroHTTPHarvester(opener=opener)
    result = harvester.fetch(build_target(2026, 8))

    assert isinstance(result, FetchedFiagroReport)
    assert result.status_code == 200
    assert len(result.informes) == 1
    assert len(result.subclasses) == 1
    assert result.informes[0].nome_gestor == "RIZA GESTORA DE RECURSOS LTDA."


def test_fetch_sends_expected_headers():
    captured = {}

    def opener(request, timeout):
        captured["headers"] = request.headers
        captured["timeout"] = timeout
        return FakeResponse()

    harvester = CvmFiagroHTTPHarvester(opener=opener, user_agent="test-agent")
    harvester.fetch(build_target(2026, 8))

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

    harvester = CvmFiagroHTTPHarvester(opener=opener)
    result = harvester.fetch(build_target(2026, 8))

    assert result.status_code == 200
