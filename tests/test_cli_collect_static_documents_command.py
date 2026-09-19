import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.sources.static_pdf_listing import StaticDocument, StaticListingTarget
from iip.sources.static_pdf_listing_harvester import (
    FetchedListingPage,
    StaticPdfListingHTTPHarvester,
)


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


def _fake_listing(ticker: str, count: int) -> FetchedListingPage:
    target = StaticListingTarget(
        ticker=ticker, url=f"https://example.com/{ticker.lower()}/"
    )
    docs = tuple(
        StaticDocument(
            ticker=ticker,
            url=f"https://example.com/uploads/doc-{i}.pdf",
            title=f"Documento {i}",
        )
        for i in range(count)
    )
    return FetchedListingPage(
        target=target, status_code=200, documents=docs, final_url=target.url
    )


def test_collect_static_documents_downloads_and_persists_evidence(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        StaticPdfListingHTTPHarvester,
        "fetch",
        lambda self, target: _fake_listing("KNRI11", 2),
    )
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=30.0: _FakeResponse(b"%PDF-fake"),
    )

    runner = CliRunner()
    output_dir = tmp_path / "out"
    result = runner.invoke(
        cli,
        [
            "collect-static-documents",
            "--ticker",
            "KNRI11",
            "--vault",
            str(tmp_path / "vault"),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "2/2 documento(s)" in result.output

    saved = list((output_dir / "KNRI11").iterdir())
    assert len(saved) == 2

    evidence_dir = tmp_path / "vault" / "04_Evidence"
    assert evidence_dir.exists()
    assert any(evidence_dir.iterdir())


def test_collect_static_documents_respects_limite(monkeypatch, tmp_path):
    monkeypatch.setattr(
        StaticPdfListingHTTPHarvester,
        "fetch",
        lambda self, target: _fake_listing("RBVA11", 10),
    )
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=30.0: _FakeResponse(b"%PDF-fake"),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-static-documents",
            "--ticker",
            "RBVA11",
            "--limite",
            "3",
            "--vault",
            str(tmp_path / "vault"),
            "--sem-evidencia",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "3/3 documento(s)" in result.output


def test_collect_static_documents_rejects_unknown_ticker(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-static-documents",
            "--ticker",
            "XPML11",
            "--vault",
            str(tmp_path / "vault"),
        ],
    )

    assert result.exit_code != 0
    assert "Sem config de listagem estática" in result.output


def test_collect_static_documents_handles_download_failure_without_aborting(
    monkeypatch, tmp_path
):
    from urllib.error import HTTPError

    monkeypatch.setattr(
        StaticPdfListingHTTPHarvester,
        "fetch",
        lambda self, target: _fake_listing("HGBS11", 2),
    )

    calls = {"n": 0}

    def flaky_urlopen(request, timeout=30.0):
        calls["n"] += 1
        if calls["n"] == 1:
            raise HTTPError(request.full_url, 404, "Not Found", {}, None)
        return _FakeResponse(b"%PDF-fake")

    monkeypatch.setattr("urllib.request.urlopen", flaky_urlopen)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-static-documents",
            "--ticker",
            "HGBS11",
            "--vault",
            str(tmp_path / "vault"),
            "--sem-evidencia",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "1/2 documento(s)" in result.output
    assert "HTTP 404" in result.output
