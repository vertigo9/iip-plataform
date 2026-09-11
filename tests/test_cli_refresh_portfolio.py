import json

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.sources.b3_bolsai import BolsaiFiiData
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester, FetchedFii
from iip.sources.cvm_fii import FiiComplemento
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester, FetchedFiiReport
from iip.sources.cvm_renda_fixa import InformeDiario
from iip.sources.cvm_renda_fixa_harvester import CvmRendaFixaHTTPHarvester, FetchedDiario


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def fake_cvm_fii_fetch(self, target):
    complementos = (
        FiiComplemento(
            cnpj_fundo_classe="11.839.593/0001-09",
            data_referencia="2026-07-01",
            versao="1",
            valores={
                "Patrimonio_Liquido": 7580921710.93,
                "Percentual_Dividend_Yield_Mes": 0.009476,
            },
        ),
    )
    return FetchedFiiReport(
        target=target, status_code=200, geral=(), ativo_passivo=(), complemento=complementos
    )


def fake_cvm_diario_fetch(self, target):
    informes = (
        InformeDiario(
            tipo_fundo_classe="FUNDO DE INDICE",
            cnpj_fundo_classe="56.176.507/0001-55",
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
    return FetchedDiario(target=target, status_code=200, informes=informes)


def test_refresh_portfolio_runs_without_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("IIP_BOLSAI_API_KEY", raising=False)
    monkeypatch.delenv("IIP_BRAPI_TOKEN", raising=False)
    monkeypatch.setattr(CvmFiiHTTPHarvester, "fetch", fake_cvm_fii_fetch)
    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", fake_cvm_diario_fetch)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["refresh-portfolio", "--output-dir", str(tmp_path), "--ano", "2026", "--mes", "8"]
    )

    assert result.exit_code == 0
    assert "BTLG11" in result.output
    assert "LFTB11" in result.output


def test_refresh_portfolio_writes_real_snapshot_files(monkeypatch, tmp_path):
    monkeypatch.delenv("IIP_BOLSAI_API_KEY", raising=False)
    monkeypatch.delenv("IIP_BRAPI_TOKEN", raising=False)
    monkeypatch.setattr(CvmFiiHTTPHarvester, "fetch", fake_cvm_fii_fetch)
    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", fake_cvm_diario_fetch)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["refresh-portfolio", "--output-dir", str(tmp_path), "--ano", "2026", "--mes", "8"]
    )

    assert result.exit_code == 0
    snapshot_dirs = list(tmp_path.iterdir())
    assert len(snapshot_dirs) == 1
    snapshot_files = {p.name for p in snapshot_dirs[0].iterdir()}
    assert "BTLG11.json" in snapshot_files
    assert "LFTB11.json" in snapshot_files

    btlg_data = json.loads((snapshot_dirs[0] / "BTLG11.json").read_text(encoding="utf-8"))
    assert btlg_data["financials"]["dividend_yield"] != 0


def test_refresh_portfolio_uses_bolsai_and_brapi_when_credentials_present(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("IIP_BOLSAI_API_KEY", "fake-key")
    monkeypatch.setenv("IIP_BRAPI_TOKEN", "fake-token")
    monkeypatch.setattr(CvmFiiHTTPHarvester, "fetch", fake_cvm_fii_fetch)
    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", fake_cvm_diario_fetch)

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
    result = runner.invoke(
        cli, ["refresh-portfolio", "--output-dir", str(tmp_path), "--ano", "2026", "--mes", "8"]
    )

    assert result.exit_code == 0
    snapshot_dirs = list(tmp_path.iterdir())
    btlg_data = json.loads((snapshot_dirs[0] / "BTLG11.json").read_text(encoding="utf-8"))
    assert btlg_data["price"] == 95.50


def test_refresh_portfolio_exits_nonzero_when_a_position_fails(monkeypatch, tmp_path):
    monkeypatch.delenv("IIP_BOLSAI_API_KEY", raising=False)
    monkeypatch.delenv("IIP_BRAPI_TOKEN", raising=False)

    def failing_fetch(self, target):
        raise RuntimeError("CVM indisponível")

    monkeypatch.setattr(CvmFiiHTTPHarvester, "fetch", failing_fetch)
    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", fake_cvm_diario_fetch)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["refresh-portfolio", "--output-dir", str(tmp_path), "--ano", "2026", "--mes", "8"]
    )

    assert result.exit_code == 1
