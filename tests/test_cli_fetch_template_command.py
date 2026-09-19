import json

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.sources.b3_bolsai import BolsaiFiiData
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester, FetchedFii
from iip.sources.cvm_fii import FiiComplemento
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester, FetchedFiiReport

CNPJ = "11.839.593/0001-09"


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


def make_fake_cvm_fetch():
    complementos = (
        FiiComplemento(
            cnpj_fundo_classe=CNPJ,
            data_referencia="2026-07-01",
            versao="1",
            valores={
                "Patrimonio_Liquido": 7580921710.93,
                "Valor_Patrimonial_Cotas": 15.16,
                "Cotas_Emitidas": 500000000,
                "Percentual_Dividend_Yield_Mes": 0.009476,
            },
        ),
    )

    def fake_fetch(self, target):
        return FetchedFiiReport(
            target=target,
            status_code=200,
            geral=(),
            ativo_passivo=(),
            complemento=complementos,
        )

    return fake_fetch


def test_fetch_template_works_without_bolsai_key(monkeypatch, tmp_path):
    monkeypatch.delenv("IIP_BOLSAI_API_KEY", raising=False)
    monkeypatch.setattr(CvmFiiHTTPHarvester, "fetch", make_fake_cvm_fetch())

    runner = CliRunner()
    out_file = tmp_path / "btlg11.json"
    result = runner.invoke(
        cli,
        [
            "fetch-template",
            "BTLG11",
            "--cnpj",
            CNPJ,
            "--ano",
            "2026",
            "-o",
            str(out_file),
        ],
    )

    assert result.exit_code == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["symbol"] == "BTLG11"
    assert data["price"] is None
    assert data["financials"]["dividend_yield"] != 0


def test_fetch_template_uses_bolsai_price_when_key_present(monkeypatch, tmp_path):
    monkeypatch.setenv("IIP_BOLSAI_API_KEY", "fake-key")
    monkeypatch.setattr(CvmFiiHTTPHarvester, "fetch", make_fake_cvm_fetch())

    def fake_fetch_fii(self, target):
        return FetchedFii(
            target=target,
            status_code=200,
            fii=BolsaiFiiData(
                ticker="BTLG11",
                name="BTG PACTUAL LOGISTICA",
                reference_date="2026-08-01",
                close_price=95.50,
                book_value_per_share=None,
                pvp=None,
                dividend_yield_ttm=None,
                net_asset_value=None,
                shares_outstanding=None,
                total_shareholders=None,
                segment=None,
                management_type=None,
            ),
        )

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch_fii", fake_fetch_fii)

    runner = CliRunner()
    out_file = tmp_path / "btlg11.json"
    result = runner.invoke(
        cli,
        [
            "fetch-template",
            "BTLG11",
            "--cnpj",
            CNPJ,
            "--ano",
            "2026",
            "-o",
            str(out_file),
        ],
    )

    assert result.exit_code == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["price"] == 95.50
    assert data["market_cap"] is not None
    assert data["financials"]["reit_premium_discount"] is not None


def test_fetch_template_continues_when_bolsai_fetch_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("IIP_BOLSAI_API_KEY", "fake-key")
    monkeypatch.setattr(CvmFiiHTTPHarvester, "fetch", make_fake_cvm_fetch())

    def failing_fetch_fii(self, target):
        raise RuntimeError("simulated bolsai outage")

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch_fii", failing_fetch_fii)

    runner = CliRunner()
    out_file = tmp_path / "btlg11.json"
    result = runner.invoke(
        cli,
        [
            "fetch-template",
            "BTLG11",
            "--cnpj",
            CNPJ,
            "--ano",
            "2026",
            "-o",
            str(out_file),
        ],
    )

    # bolsai failing should not abort the whole command — CVM-only data still gets written
    assert result.exit_code == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["price"] is None
    assert data["financials"]["dividend_yield"] != 0


def test_fetch_template_exits_nonzero_on_cvm_error(monkeypatch):
    def failing_fetch(self, target):
        raise RuntimeError("simulated network failure")

    monkeypatch.setattr(CvmFiiHTTPHarvester, "fetch", failing_fetch)

    runner = CliRunner()
    result = runner.invoke(cli, ["fetch-template", "BTLG11", "--cnpj", CNPJ])

    assert result.exit_code != 0


def test_fetch_template_prints_to_console_without_output_flag(monkeypatch):
    monkeypatch.delenv("IIP_BOLSAI_API_KEY", raising=False)
    monkeypatch.setattr(CvmFiiHTTPHarvester, "fetch", make_fake_cvm_fetch())

    runner = CliRunner()
    result = runner.invoke(
        cli, ["fetch-template", "BTLG11", "--cnpj", CNPJ, "--ano", "2026"]
    )

    assert result.exit_code == 0
    assert '"symbol": "BTLG11"' in result.output


def test_fetch_template_output_is_directly_usable_by_analyze(monkeypatch, tmp_path):
    """End-to-end: fetch-template's output must be exactly what `analyze`
    accepts — this is the whole point of building this bridge."""
    monkeypatch.delenv("IIP_BOLSAI_API_KEY", raising=False)
    monkeypatch.setattr(CvmFiiHTTPHarvester, "fetch", make_fake_cvm_fetch())

    runner = CliRunner()
    out_file = tmp_path / "btlg11.json"
    fetch_result = runner.invoke(
        cli,
        [
            "fetch-template",
            "BTLG11",
            "--cnpj",
            CNPJ,
            "--ano",
            "2026",
            "-o",
            str(out_file),
        ],
    )
    assert fetch_result.exit_code == 0

    # sector/industry are placeholders the analyzer requires — fill them
    # in, same as a person would before running analyze for real.
    data = json.loads(out_file.read_text(encoding="utf-8"))
    data["sector"] = "Logística"
    data["industry"] = "Galpões"
    out_file.write_text(json.dumps(data), encoding="utf-8")

    analyze_result = runner.invoke(
        cli, ["analyze", "BTLG11", "--type", "fii", "--data-file", str(out_file)]
    )

    assert analyze_result.exit_code == 0
    assert "Overall score" in analyze_result.output
    assert "Recommendation" in analyze_result.output
