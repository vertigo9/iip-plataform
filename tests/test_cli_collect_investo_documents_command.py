import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.sources import investo_mziq
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


def _fake_document(category="LFTB11_Regulamento", doc_id="doc-1"):
    return MziqDocument(
        id=doc_id,
        company_id="02c0bf8f-2988-419f-9a6f-4e116a4bf822",
        file_name_original="regulamento.pdf",
        file_title="Regulamento",
        url="https://filemanager-cdn.mziq.com/published/x/regulamento.pdf",
        file_size=1000,
        file_date="2024-10-15",
        file_quarter=None,
        file_year=2024,
        category=category,
        is_published=True,
    )


def test_lftb11_config_covers_the_seven_document_categories():
    fund = investo_mziq.fund_for_ticker(" lftb11 ")

    assert fund is not None
    assert fund.company_id == "02c0bf8f-2988-419f-9a6f-4e116a4bf822"
    assert len(fund.category_internal_names) == 7
    assert all(name.startswith("LFTB11_") for name in fund.category_internal_names)


def test_targets_reject_unregistered_ticker():
    with pytest.raises(ValueError):
        investo_mziq.build_years_target("BOVA11")
    with pytest.raises(ValueError):
        investo_mziq.build_documents_target("BOVA11", 2024)


def test_collect_investo_documents_downloads_and_persists_evidence(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        MziqHTTPHarvester, "fetch_years", lambda self, target: (2025, 2024)
    )
    seen_targets = []

    def fake_fetch_documents(self, target):
        seen_targets.append(target)
        return (_fake_document(),)

    monkeypatch.setattr(MziqHTTPHarvester, "fetch_documents", fake_fetch_documents)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=30.0: _FakeResponse(b"%PDF-fake"),
    )

    result = CliRunner().invoke(
        cli,
        [
            "collect-investo-documents",
            "--ticker",
            "LFTB11",
            "--ano",
            "2024",
            "--vault",
            str(tmp_path / "vault"),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "1/1 documento(s)" in result.output
    assert len(seen_targets) == 1
    saved = list((tmp_path / "out" / "LFTB11" / "2024").iterdir())
    assert saved[0].read_bytes() == b"%PDF-fake"
    assert any((tmp_path / "vault" / "04_Evidence").iterdir())


def test_collect_investo_documents_rejects_unknown_ticker(tmp_path):
    result = CliRunner().invoke(
        cli,
        [
            "collect-investo-documents",
            "--ticker",
            "BOVA11",
            "--vault",
            str(tmp_path / "vault"),
        ],
    )

    assert result.exit_code != 0
    assert "Sem config MZIQ" in result.output
    assert "LFTB11" in result.output
