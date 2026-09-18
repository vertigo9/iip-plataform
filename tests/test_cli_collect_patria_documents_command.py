import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.sources.mziq import MziqDocument
from iip.sources.mziq_harvester import MziqHTTPHarvester


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings, get_settings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body
        self.headers = {"Content-Type": "application/pdf"}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_document(category="lvbi11_relatorio_de_gestao", doc_id="doc-1", url="https://filemanager-cdn.mziq.com/published/x/y.pdf"):
    return MziqDocument(
        id=doc_id,
        company_id="ef0151fe-a22e-456d-8cc4-55ef365d7e3b",
        file_name_original="relatorio.pdf",
        file_title="Relatório Gerencial",
        url=url,
        file_size=1000,
        file_date="2026-08-20",
        file_quarter=None,
        file_year=2026,
        category=category,
        is_published=True,
    )


def test_collect_patria_documents_downloads_and_persists_evidence(monkeypatch, tmp_path):
    monkeypatch.setattr(MziqHTTPHarvester, "fetch_years", lambda self, target: (2026, 2025))
    monkeypatch.setattr(
        MziqHTTPHarvester, "fetch_documents", lambda self, target: (_fake_document(),)
    )
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda request, timeout=30.0: _FakeResponse(b"%PDF-fake")
    )

    runner = CliRunner()
    output_dir = tmp_path / "out"
    result = runner.invoke(
        cli,
        [
            "collect-patria-documents",
            "--ticker",
            "LVBI11",
            "--vault",
            str(tmp_path / "vault"),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "1/1 documento(s)" in result.output

    saved = list((output_dir / "LVBI11" / "2026").iterdir())
    assert len(saved) == 1
    assert saved[0].read_bytes() == b"%PDF-fake"

    evidence_dir = tmp_path / "vault" / "04_Evidence"
    assert evidence_dir.exists()
    assert any(evidence_dir.iterdir())


def test_collect_patria_documents_filters_by_categoria(monkeypatch, tmp_path):
    monkeypatch.setattr(MziqHTTPHarvester, "fetch_years", lambda self, target: (2026,))
    monkeypatch.setattr(
        MziqHTTPHarvester,
        "fetch_documents",
        lambda self, target: (
            _fake_document(category="lvbi11_relatorio_de_gestao", doc_id="a"),
            _fake_document(category="lvbi11_fatos_relevantes", doc_id="b"),
        ),
    )
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda request, timeout=30.0: _FakeResponse(b"%PDF-fake")
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-patria-documents",
            "--ticker",
            "LVBI11",
            "--categoria",
            "lvbi11_relatorio_de_gestao",
            "--vault",
            str(tmp_path / "vault"),
            "--sem-evidencia",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "1/1 documento(s)" in result.output


def test_collect_patria_documents_respects_limite(monkeypatch, tmp_path):
    monkeypatch.setattr(MziqHTTPHarvester, "fetch_years", lambda self, target: (2026,))
    monkeypatch.setattr(
        MziqHTTPHarvester,
        "fetch_documents",
        lambda self, target: tuple(
            _fake_document(doc_id=str(i)) for i in range(5)
        ),
    )
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda request, timeout=30.0: _FakeResponse(b"%PDF-fake")
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-patria-documents",
            "--ticker",
            "LVBI11",
            "--limite",
            "2",
            "--vault",
            str(tmp_path / "vault"),
            "--sem-evidencia",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "2/2 documento(s)" in result.output


def test_collect_patria_documents_rejects_unknown_ticker(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-patria-documents",
            "--ticker",
            "XPML11",
            "--vault",
            str(tmp_path / "vault"),
        ],
    )

    assert result.exit_code != 0
    assert "Sem config MZIQ" in result.output


def test_collect_patria_documents_handles_download_http_error(monkeypatch, tmp_path):
    from urllib.error import HTTPError

    monkeypatch.setattr(MziqHTTPHarvester, "fetch_years", lambda self, target: (2026,))
    monkeypatch.setattr(
        MziqHTTPHarvester, "fetch_documents", lambda self, target: (_fake_document(),)
    )

    def failing_urlopen(request, timeout=30.0):
        raise HTTPError(request.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", failing_urlopen)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-patria-documents",
            "--ticker",
            "LVBI11",
            "--vault",
            str(tmp_path / "vault"),
            "--sem-evidencia",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "0/1 documento(s)" in result.output
    assert "HTTP 404" in result.output
