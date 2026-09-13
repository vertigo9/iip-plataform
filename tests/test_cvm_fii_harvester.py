from typing import ClassVar

from iip.sources.cvm_fii import build_target
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester, FetchedFiiReport
from tests.test_cvm_fii import make_zip


class FakeResponse:
    status = 200

    def __init__(
        self,
        body=None,
        *,
        content_type="application/zip",
        final_url="https://dados.cvm.gov.br/final/arquivo.zip",
    ):
        self._body = body if body is not None else make_zip()
        self.headers = {"Content-Type": content_type}
        self._final_url = final_url

    def read(self):
        return self._body

    def geturl(self):
        return self._final_url


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


def test_fetch_preserves_transport_metadata():
    body = make_zip()

    def opener(request, timeout):
        return FakeResponse(
            body=body,
            content_type="application/zip; charset=binary",
            final_url="https://dados.cvm.gov.br/final/inf_mensal_fii_2026.zip",
        )

    result = CvmFiiHTTPHarvester(opener=opener).fetch(build_target(2026))

    assert result.body == body
    assert result.content_type == "application/zip"
    assert result.final_url == (
        "https://dados.cvm.gov.br/final/inf_mensal_fii_2026.zip"
    )


def test_fetch_preserves_target_url_when_geturl_is_unavailable():
    class NoGetUrlResponse:
        status = 200
        headers: ClassVar[dict[str, str]] = {"Content-Type": "application/zip"}

        def __init__(self):
            self._body = make_zip()

        def read(self):
            return self._body

    def opener(request, timeout):
        return NoGetUrlResponse()

    target = build_target(2026)
    result = CvmFiiHTTPHarvester(opener=opener).fetch(target)

    assert result.final_url == target.url
    assert result.body != b""


def test_build_target_exposes_atlas_transport_identity():
    target = build_target(2026)

    assert target.provider == "cvm"
    assert target.role == "regulatory"
    assert target.year == 2026
    assert target.ano == 2026
    assert target.ticker == "MULTI"


def test_fetched_report_is_directly_consumable_by_real_atlas_adapter():
    """Diferente de test_atlas_document_adapter.py (que usa um
    SimpleNamespace generico com ticker="XPML11" hardcoded), este teste
    prova que o FetchedFiiReport/CvmFiiTarget REAIS -- nao um fake --
    funcionam com o AtlasDocumentAdapter real. E' esse teste que faltava
    pra fechar CVM->Atlas de verdade (achado ao vivo em 12/09/2026: sem
    ele, o "Atlas adapter test: PASS" do patch dava falsa confianca,
    porque nunca exercitava um CvmFiiTarget real)."""
    from iip.atlas.adapter import AtlasDocumentAdapter

    body = make_zip()

    def opener(request, timeout):
        return FakeResponse(
            body=body,
            content_type="application/zip; charset=binary",
            final_url="https://dados.cvm.gov.br/final/inf_mensal_fii_2026.zip",
        )

    result = CvmFiiHTTPHarvester(opener=opener).fetch(build_target(2026))
    document = AtlasDocumentAdapter().from_fetched(result)

    assert document.ticker == "MULTI"
    assert document.provider == "cvm"
    assert document.role == "regulatory"
    assert document.discovered_year == 2026
    assert document.content_type == "application/zip"
    assert document.body == body
    assert len(document.content_hash) == 64  # SHA-256 hex
    assert document.document_id == f"cvm:MULTI:2026:{document.content_hash[:16]}"


def test_fetched_report_keeps_parsed_data_and_raw_body_consistent():
    body = make_zip()

    def opener(request, timeout):
        return FakeResponse(body=body)

    result = CvmFiiHTTPHarvester(opener=opener).fetch(build_target(2026))

    assert result.body == body
    assert len(result.geral) == 1
    assert len(result.ativo_passivo) == 1
    assert len(result.complemento) == 1
    assert result.complemento[0].data_referencia == "2026-07-01"
