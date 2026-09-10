from iip.sources.cvm_renda_fixa import build_diario_target, build_perfil_target
from iip.sources.cvm_renda_fixa_harvester import (
    CvmRendaFixaHTTPHarvester,
    FetchedDiario,
    FetchedPerfil,
)
from tests.test_cvm_renda_fixa import make_diario_zip, make_perfil_csv


class FakeDiarioResponse:
    status = 200

    def read(self):
        return make_diario_zip()


class FakePerfilResponse:
    status = 200

    def read(self):
        return make_perfil_csv()


def test_fetch_diario_parses_response():
    def opener(request, timeout):
        return FakeDiarioResponse()

    harvester = CvmRendaFixaHTTPHarvester(opener=opener)
    result = harvester.fetch_diario(build_diario_target(2026, 8))

    assert isinstance(result, FetchedDiario)
    assert result.status_code == 200
    assert len(result.informes) == 1


def test_fetch_perfil_parses_response():
    def opener(request, timeout):
        return FakePerfilResponse()

    harvester = CvmRendaFixaHTTPHarvester(opener=opener)
    result = harvester.fetch_perfil(build_perfil_target(2026, 8))

    assert isinstance(result, FetchedPerfil)
    assert result.status_code == 200
    assert len(result.perfis) == 1


def test_fetch_diario_sends_zip_accept_header():
    captured = {}

    def opener(request, timeout):
        captured["headers"] = request.headers
        return FakeDiarioResponse()

    harvester = CvmRendaFixaHTTPHarvester(opener=opener)
    harvester.fetch_diario(build_diario_target(2026, 8))

    assert captured["headers"]["Accept"] == "application/zip"


def test_fetch_perfil_sends_csv_accept_header():
    captured = {}

    def opener(request, timeout):
        captured["headers"] = request.headers
        return FakePerfilResponse()

    harvester = CvmRendaFixaHTTPHarvester(opener=opener)
    harvester.fetch_perfil(build_perfil_target(2026, 8))

    assert captured["headers"]["Accept"] == "text/csv"


def test_fetch_defaults_status_when_none():
    class NoStatusResponse:
        status = None

        def read(self):
            return make_diario_zip()

    def opener(request, timeout):
        return NoStatusResponse()

    harvester = CvmRendaFixaHTTPHarvester(opener=opener)
    result = harvester.fetch_diario(build_diario_target(2026, 8))
    assert result.status_code == 200
