from pathlib import Path

from iip.sources.sparta_reports import build_target
from iip.sources.sparta_reports_harvester import SpartaReportsHTTPHarvester

# Real PDF downloaded live (17/09/2026) from
# sparta.com.br/uploads/CRAA11_RelatorioMensal_2026_03.pdf -- reused
# here instead of a synthetic fixture so the harvester test exercises
# the actual pypdf extraction against real report content, not a
# hand-crafted stand-in.
_REAL_PDF_PATH = Path(
    r"C:\Users\Administrador\.claude\projects\d--IIP-Obsidian-Integration-v1-0-"
    r"iip-obsidian-integration-v1\64f605b1-8db2-45ed-98ee-b0e81c4fd275"
    r"\tool-results\webfetch-1789692421570-m406ng.pdf"
)


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body
        self.status = 200

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return "https://sparta.com.br/uploads/CRAA11_RelatorioMensal_2026_03.pdf"


def test_harvester_downloads_and_extracts_real_pdf():
    if not _REAL_PDF_PATH.exists():
        import pytest

        pytest.skip("real captured PDF fixture not present in this environment")

    body = _REAL_PDF_PATH.read_bytes()

    def fake_opener(request, timeout):
        assert "CRAA11_RelatorioMensal_2026_03.pdf" in request.full_url
        return _FakeResponse(body)

    harvester = SpartaReportsHTTPHarvester(opener=fake_opener)
    result = harvester.fetch(build_target("CRAA11", 2026, 3))

    assert result.status_code == 200
    assert result.cota_patrimonial == 101.64
    assert result.body == body
