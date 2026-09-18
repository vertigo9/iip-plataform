import json

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.sources.b3_bolsai import BolsaiFundamentals
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester, FetchedFundamentals
from iip.sources.cvm_dfp_harvester import CvmDfpHTTPHarvester
from tests.test_cvm_dfp import NON_FINANCIAL_CNPJ, make_zip

CNPJ = NON_FINANCIAL_CNPJ


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _mock_cvm_dfp(monkeypatch):
    """Every test in this file exercises the real `fetch-template
    --type equity` CLI path end-to-end, which now also hits CVM DFP
    (see fetch_equity_template_live) -- mocked here the same way the
    other fetch-template CLI tests mock their CVM harvester, so these
    tests never make a real network call."""

    def fake_fetch(self, target):
        import iip.sources.cvm_dfp_harvester as mod

        body = make_zip()
        return mod.FetchedDfpYear(
            target=target,
            status_code=200,
            bpa_con=mod.parse_bpa_con(body),
            bpa_ind=mod.parse_bpa_ind(body),
            bpp_con=mod.parse_bpp_con(body),
            bpp_ind=mod.parse_bpp_ind(body),
            dre_con=mod.parse_dre_con(body),
            dre_ind=mod.parse_dre_ind(body),
        )

    monkeypatch.setattr(CvmDfpHTTPHarvester, "fetch", fake_fetch)


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


def test_fetch_template_equity_requires_cnpj():
    runner = CliRunner()
    result = runner.invoke(cli, ["fetch-template", "BBSE3", "--type", "equity"])
    assert result.exit_code != 0


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
        cli,
        [
            "fetch-template",
            "BBSE3",
            "--type",
            "equity",
            "--cnpj",
            CNPJ,
            "--ano",
            "2025",
            "-o",
            str(out_file),
        ],
    )

    assert result.exit_code == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["price"] == 39.62
    assert data["financials"]["dividend_yield"] == 17.18


def test_fetch_template_equity_fills_real_dfp_fundamentals(monkeypatch, tmp_path):
    monkeypatch.setenv("IIP_BOLSAI_API_KEY", "fake-key")

    def fake_fetch(self, target):
        return FetchedFundamentals(
            target=target, status_code=200, fundamentals=fake_fundamentals()
        )

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch", fake_fetch)

    runner = CliRunner()
    out_file = tmp_path / "klbn4.json"
    result = runner.invoke(
        cli,
        [
            "fetch-template",
            "KLBN4",
            "--type",
            "equity",
            "--cnpj",
            CNPJ,
            "--ano",
            "2025",
            "-o",
            str(out_file),
        ],
    )

    assert result.exit_code == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["financials"]["equity"] == 14401101.0
    assert data["financials"]["net_income"] == 1678211.0
    assert data["financials"]["revenue"] == 20697507.0


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
        cli,
        [
            "fetch-template",
            "BBSE3",
            "--type",
            "equity",
            "--cnpj",
            CNPJ,
            "--ano",
            "2025",
            "-o",
            str(out_file),
        ],
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
