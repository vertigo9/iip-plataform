import json

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.sources.cvm_renda_fixa import InformeDiario
from iip.sources.cvm_renda_fixa_harvester import (
    CvmRendaFixaHTTPHarvester,
    FetchedDiario,
)

CNPJ = "45.121.022/0001-48"


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def fake_fetch_diario(self, target):
    informes = (
        InformeDiario(
            tipo_fundo_classe="CLASSE FIF/FAPI",
            cnpj_fundo_classe=CNPJ,
            id_subclasse=None,
            data_competencia="2026-08-05",
            valor_total=15_000_000.0,
            valor_cota=1.89,
            patrimonio_liquido=14_800_000.0,
            captacao_dia=0.0,
            resgate_dia=0.0,
            numero_cotistas=4970,
        ),
    )
    return FetchedDiario(target=target, status_code=200, informes=informes)


def test_fetch_template_fixed_income_requires_cnpj():
    runner = CliRunner()
    result = runner.invoke(cli, ["fetch-template", "AXIA3", "--type", "fixed_income"])
    assert result.exit_code != 0


def test_fetch_template_fixed_income_never_fills_price(monkeypatch, tmp_path):
    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", fake_fetch_diario)

    runner = CliRunner()
    out_file = tmp_path / "axia3.json"
    result = runner.invoke(
        cli,
        [
            "fetch-template",
            "AXIA3",
            "--type",
            "fixed_income",
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
    assert data["financials"]["assets_under_management_millions"] != 100


def test_fetch_template_fixed_income_output_is_directly_usable_by_analyze(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", fake_fetch_diario)

    runner = CliRunner()
    out_file = tmp_path / "axia3.json"
    fetch_result = runner.invoke(
        cli,
        [
            "fetch-template",
            "AXIA3",
            "--type",
            "fixed_income",
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
    data["sector"] = "Financeiro"
    data["industry"] = "FMP-FGTS"
    out_file.write_text(json.dumps(data), encoding="utf-8")

    analyze_result = runner.invoke(
        cli,
        ["analyze", "AXIA3", "--type", "fixed_income", "--data-file", str(out_file)],
    )

    assert analyze_result.exit_code == 0
    assert "Overall score" in analyze_result.output
