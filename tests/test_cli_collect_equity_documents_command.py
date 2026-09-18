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


def _fake_document(category="central-resultados-earnings-release", doc_id="doc-1", url="https://filemanager-cdn.mziq.com/published/x/y.pdf"):
    return MziqDocument(
        id=doc_id,
        company_id="6298ef6f-2b75-43f8-b2ab-99e3fe33e809",
        file_name_original="release.pdf",
        file_title="Earnings Release",
        url=url,
        file_size=1000,
        file_date="2026-08-20",
        file_quarter=None,
        file_year=2026,
        category=category,
        is_published=True,
    )


def test_collect_equity_documents_downloads_and_persists_evidence(monkeypatch, tmp_path):
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
            "collect-equity-documents",
            "--ticker",
            "ABCB4",
            "--vault",
            str(tmp_path / "vault"),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "1/1 documento(s)" in result.output

    saved = list((output_dir / "ABCB4" / "2026").iterdir())
    assert len(saved) == 1

    evidence_dir = tmp_path / "vault" / "04_Evidence"
    assert evidence_dir.exists()
    assert any(evidence_dir.iterdir())


def test_collect_equity_documents_rejects_unknown_ticker(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-equity-documents",
            "--ticker",
            "BBSE3",
            "--vault",
            str(tmp_path / "vault"),
        ],
    )

    assert result.exit_code != 0
    assert "Sem config MZIQ" in result.output
    assert "ABCB4" in result.output
