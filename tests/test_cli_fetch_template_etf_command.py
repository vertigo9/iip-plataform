import json

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.sources.b3_brapi import BrapiQuote
from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester, FetchedQuotes
from iip.sources.cvm_renda_fixa import InformeDiario
from iip.sources.cvm_renda_fixa_harvester import (
    CvmRendaFixaHTTPHarvester,
    FetchedDiario,
)

CNPJ = "04.828.276/0001-00"


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    # monkeypatch.delenv only clears os.environ -- pydantic-settings
    # ALSO reads directly from a real .env file on disk regardless of
    # os.environ state. Without this, a machine with a populated .env
    # (e.g. configured for the scheduled task) would leak real
    # credentials into these "without credential" tests.
    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()



def make_fake_diario_fetch():
    informes = (
        InformeDiario(
            tipo_fundo_classe="FUNDO DE INDICE",
            cnpj_fundo_classe=CNPJ,
            id_subclasse=None,
            data_competencia="2026-08-05",
            valor_total=15_150_000_000.0,
            valor_cota=111.0,
            patrimonio_liquido=15_100_000_000.0,
            captacao_dia=0.0,
            resgate_dia=0.0,
            numero_cotistas=100,
        ),
    )

    def fake_fetch_diario(self, target):
        return FetchedDiario(target=target, status_code=200, informes=informes)

    return fake_fetch_diario


def test_fetch_template_etf_works_without_brapi_token(monkeypatch, tmp_path):
    monkeypatch.delenv("IIP_BRAPI_TOKEN", raising=False)
    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", make_fake_diario_fetch())

    runner = CliRunner()
    out_file = tmp_path / "bova11.json"
    result = runner.invoke(
        cli,
        [
            "fetch-template",
            "BOVA11",
            "--type",
            "etf",
            "--cnpj",
            CNPJ,
            "--ano",
            "2026",
            "--mes",
            "8",
            "-o",
            str(out_file),
        ],
    )

    assert result.exit_code == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["symbol"] == "BOVA11"
    assert data["price"] is None
    assert data["financials"]["assets_under_management_millions"] != 100


def test_fetch_template_etf_uses_brapi_price_when_token_present(monkeypatch, tmp_path):
    monkeypatch.setenv("IIP_BRAPI_TOKEN", "fake-token")
    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", make_fake_diario_fetch())

    def fake_fetch(self, target):
        return FetchedQuotes(
            target=target,
            status_code=200,
            quotes=(
                BrapiQuote(
                    symbol="BOVA11",
                    short_name="ISHARES BOVA",
                    currency="BRL",
                    regular_market_price=112.30,
                    regular_market_change_percent=0.5,
                ),
            ),
        )

    monkeypatch.setattr(BrapiHTTPHarvester, "fetch", fake_fetch)

    runner = CliRunner()
    out_file = tmp_path / "bova11.json"
    result = runner.invoke(
        cli,
        [
            "fetch-template",
            "BOVA11",
            "--type",
            "etf",
            "--cnpj",
            CNPJ,
            "--ano",
            "2026",
            "--mes",
            "8",
            "-o",
            str(out_file),
        ],
    )

    assert result.exit_code == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["price"] == 112.30
    assert data["market_cap"] is not None


def test_fetch_template_etf_continues_when_brapi_fetch_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("IIP_BRAPI_TOKEN", "fake-token")
    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", make_fake_diario_fetch())

    def failing_fetch(self, target):
        raise RuntimeError("simulated brapi outage")

    monkeypatch.setattr(BrapiHTTPHarvester, "fetch", failing_fetch)

    runner = CliRunner()
    out_file = tmp_path / "bova11.json"
    result = runner.invoke(
        cli,
        [
            "fetch-template",
            "BOVA11",
            "--type",
            "etf",
            "--cnpj",
            CNPJ,
            "--ano",
            "2026",
            "--mes",
            "8",
            "-o",
            str(out_file),
        ],
    )

    assert result.exit_code == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["price"] is None


def test_fetch_template_etf_exits_nonzero_on_cvm_error(monkeypatch):
    def failing_fetch(self, target):
        raise RuntimeError("simulated network failure")

    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", failing_fetch)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["fetch-template", "BOVA11", "--type", "etf", "--cnpj", CNPJ]
    )

    assert result.exit_code != 0


def test_fetch_template_etf_output_is_directly_usable_by_analyze(monkeypatch, tmp_path):
    monkeypatch.delenv("IIP_BRAPI_TOKEN", raising=False)
    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", make_fake_diario_fetch())

    runner = CliRunner()
    out_file = tmp_path / "bova11.json"
    fetch_result = runner.invoke(
        cli,
        [
            "fetch-template",
            "BOVA11",
            "--type",
            "etf",
            "--cnpj",
            CNPJ,
            "--ano",
            "2026",
            "--mes",
            "8",
            "-o",
            str(out_file),
        ],
    )
    assert fetch_result.exit_code == 0

    data = json.loads(out_file.read_text(encoding="utf-8"))
    data["sector"] = "Renda Variável"
    data["industry"] = "Índice Amplo"
    out_file.write_text(json.dumps(data), encoding="utf-8")

    analyze_result = runner.invoke(
        cli, ["analyze", "BOVA11", "--type", "etf", "--data-file", str(out_file)]
    )

    assert analyze_result.exit_code == 0
    assert "Overall score" in analyze_result.output
