from typing import ClassVar

from iip.sources.cvm_dfp import build_target
from iip.sources.cvm_dfp_harvester import CvmDfpHTTPHarvester, FetchedDfpYear
from tests.test_cvm_dfp import BANK_CNPJ, NON_FINANCIAL_CNPJ, make_zip


class FakeResponse:
    status = 200

    def __init__(
        self,
        body=None,
        *,
        content_type="application/zip",
        final_url="https://dados.cvm.gov.br/final/dfp_cia_aberta_2025.zip",
    ):
        self._body = body if body is not None else make_zip()
        self.headers = {"Content-Type": content_type}
        self._final_url = final_url

    def read(self):
        return self._body

    def geturl(self):
        return self._final_url


def test_fetch_parses_all_six_statements():
    def opener(request, timeout):
        return FakeResponse()

    harvester = CvmDfpHTTPHarvester(opener=opener)
    result = harvester.fetch(build_target(2025))

    assert isinstance(result, FetchedDfpYear)
    assert result.status_code == 200
    assert len(result.bpa_con) >= 1
    assert len(result.bpa_ind) >= 1
    assert len(result.bpp_con) >= 1
    assert len(result.bpp_ind) >= 1
    assert len(result.dre_con) >= 1
    assert len(result.dre_ind) >= 1
    assert any(r.cnpj_cia == NON_FINANCIAL_CNPJ for r in result.bpa_con)
    assert any(r.cnpj_cia == BANK_CNPJ for r in result.bpa_ind)


def test_fetch_sends_expected_headers():
    captured = {}

    def opener(request, timeout):
        captured["headers"] = request.headers
        captured["timeout"] = timeout
        return FakeResponse()

    harvester = CvmDfpHTTPHarvester(opener=opener, user_agent="test-agent")
    harvester.fetch(build_target(2025))

    assert captured["headers"]["User-agent"] == "test-agent"
    assert captured["headers"]["Accept"] == "application/zip"
    assert captured["timeout"] == 90.0


def test_fetch_defaults_status_when_none():
    class NoStatusResponse:
        status = None

        def read(self):
            return make_zip()

    def opener(request, timeout):
        return NoStatusResponse()

    harvester = CvmDfpHTTPHarvester(opener=opener)
    result = harvester.fetch(build_target(2025))

    assert result.status_code == 200


def test_fetch_preserves_transport_metadata():
    body = make_zip()

    def opener(request, timeout):
        return FakeResponse(
            body=body,
            content_type="application/zip; charset=binary",
            final_url="https://dados.cvm.gov.br/final/dfp_cia_aberta_2025.zip",
        )

    result = CvmDfpHTTPHarvester(opener=opener).fetch(build_target(2025))

    assert result.body == body
    assert result.content_type == "application/zip"
    assert result.final_url == (
        "https://dados.cvm.gov.br/final/dfp_cia_aberta_2025.zip"
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

    target = build_target(2025)
    result = CvmDfpHTTPHarvester(opener=opener).fetch(target)

    assert result.final_url == target.url
    assert result.body != b""


def test_build_target_exposes_atlas_transport_identity():
    target = build_target(2025)

    assert target.provider == "cvm"
    assert target.role == "regulatory"
    assert target.year == 2025
    assert target.ano == 2025
    assert target.ticker == "MULTI"
