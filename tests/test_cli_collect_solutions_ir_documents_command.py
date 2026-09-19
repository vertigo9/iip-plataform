import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.sources.solutions_ir import SolutionsIrDocument
from iip.sources.solutions_ir_harvester import (
    FetchedSolutionsIrDocuments,
    SolutionsIrHTTPHarvester,
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


def _fake_docs(count=2):
    return tuple(
        SolutionsIrDocument(
            ticker="BTCI11",
            category_sigla="RM" if i % 2 == 0 else "ATA",
            category_name="RELATORIO MENSAL" if i % 2 == 0 else "ATAS",
            year="2026" if i < 2 else "2025",
            date="01/01/2026",
            title=f"doc-{i}.pdf",
            url=f"https://static.btgpactual.com/doc-{i}.pdf",
        )
        for i in range(count)
    )


def test_collect_solutions_ir_documents_downloads_and_persists_evidence(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        SolutionsIrHTTPHarvester,
        "fetch",
        lambda self, target: FetchedSolutionsIrDocuments(
            target=target, status_code=200, documents=_fake_docs(2)
        ),
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
            "collect-solutions-ir-documents",
            "--ticker",
            "BTCI11",
            "--vault",
            str(tmp_path / "vault"),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "2/2 documento(s)" in result.output

    saved = list((output_dir / "BTCI11").iterdir())
    assert len(saved) == 2

    evidence_dir = tmp_path / "vault" / "04_Evidence"
    assert evidence_dir.exists()
    assert any(evidence_dir.iterdir())


def test_collect_solutions_ir_documents_filters_by_categoria(monkeypatch, tmp_path):
    monkeypatch.setattr(
        SolutionsIrHTTPHarvester,
        "fetch",
        lambda self, target: FetchedSolutionsIrDocuments(
            target=target, status_code=200, documents=_fake_docs(4)
        ),
    )
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=30.0: _FakeResponse(b"%PDF-fake"),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-solutions-ir-documents",
            "--ticker",
            "BTCI11",
            "--categoria",
            "RM",
            "--vault",
            str(tmp_path / "vault"),
            "--sem-evidencia",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "2/2 documento(s)" in result.output


def test_collect_solutions_ir_documents_filters_by_ano(monkeypatch, tmp_path):
    monkeypatch.setattr(
        SolutionsIrHTTPHarvester,
        "fetch",
        lambda self, target: FetchedSolutionsIrDocuments(
            target=target, status_code=200, documents=_fake_docs(4)
        ),
    )
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=30.0: _FakeResponse(b"%PDF-fake"),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-solutions-ir-documents",
            "--ticker",
            "BTCI11",
            "--ano",
            "2025",
            "--vault",
            str(tmp_path / "vault"),
            "--sem-evidencia",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "2/2 documento(s)" in result.output


def test_collect_solutions_ir_documents_rejects_unknown_ticker(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-solutions-ir-documents",
            "--ticker",
            "ALZR11",
            "--vault",
            str(tmp_path / "vault"),
        ],
    )

    assert result.exit_code != 0
    assert "Sem config Solutions IR" in result.output
    assert "BTCI11" in result.output
