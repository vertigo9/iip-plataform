import json

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.sources.b3_bolsai import BolsaiFundamentals
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester, FetchedFundamentals


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def fake_fundamentals(**overrides):
    defaults = {
        "ticker": "BBSE3",
        "close_price": 39.62,
        "market_cap": 25_000_000_000.0,
        "pl": 8.37,
        "pvp": 7.06,
        "ev_ebitda": None,
        "roe": None,
        "roic": None,
        "net_margin": None,
        "gross_margin": None,
        "dividend_yield": 17.18,
        "net_debt_ebitda": None,
        "lpa": None,
        "vpa": None,
        "ebitda": None,
    }
    defaults.update(overrides)
    return BolsaiFundamentals(**defaults)


def test_fetch_template_equity_does_not_require_cnpj(monkeypatch, tmp_path):
    monkeypatch.delenv("IIP_BOLSAI_API_KEY", raising=False)
    monkeypatch.delenv("IIP_BRAPI_TOKEN", raising=False)

    runner = CliRunner()
    out_file = tmp_path / "bbse3.json"
    result = runner.invoke(
        cli, ["fetch-template", "BBSE3", "--type", "equity", "-o", str(out_file)]
    )

    assert result.exit_code == 0
    assert out_file.exists()


def test_fetch_template_equity_fills_price_and_dividend_yield_with_credential(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("IIP_BOLSAI_API_KEY", "fake-key")

    def fake_fetch(self, target):
        return FetchedFundamentals(
            target=target, status_code=200, fundamentals=fake_fundamentals()
        )

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_fetch)

    runner = CliRunner()
    out_file = tmp_path / "bbse3.json"
    result = runner.invoke(
        cli, ["fetch-template", "BBSE3", "--type", "equity", "-o", str(out_file)]
    )

    assert result.exit_code == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["price"] == 39.62
    assert data["financials"]["dividend_yield"] == 17.18


def test_fetch_template_fii_still_requires_cnpj(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["fetch-template", "BTLG11", "--type", "fii"])
    assert result.exit_code != 0


def test_fetch_template_equity_output_is_directly_usable_by_analyze(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("IIP_BOLSAI_API_KEY", "fake-key")

    def fake_fetch(self, target):
        return FetchedFundamentals(
            target=target, status_code=200, fundamentals=fake_fundamentals()
        )

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_fetch)

    runner = CliRunner()
    out_file = tmp_path / "bbse3.json"
    fetch_result = runner.invoke(
        cli, ["fetch-template", "BBSE3", "--type", "equity", "-o", str(out_file)]
    )
    assert fetch_result.exit_code == 0

    data = json.loads(out_file.read_text(encoding="utf-8"))
    data["sector"] = "Financeiro"
    data["industry"] = "Seguros"
    out_file.write_text(json.dumps(data), encoding="utf-8")

    analyze_result = runner.invoke(
        cli, ["analyze", "BBSE3", "--type", "equity", "--data-file", str(out_file)]
    )

    assert analyze_result.exit_code == 0
    assert "Overall score" in analyze_result.output
