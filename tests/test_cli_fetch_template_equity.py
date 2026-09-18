import json

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.sources.b3_bolsai import BolsaiFundamentals
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester, FetchedFundamentals
from iip.sources.cvm_dfp_harvester import CvmDfpHTTPHarvester
from tests.test_cvm_dfp import (
    BANK_CNPJ,
    NON_FINANCIAL_CNPJ,
    ZERO_DEBT_CNPJ,
    make_zip,
)

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


def _run_equity_template(monkeypatch, tmp_path, cnpj):
    monkeypatch.setenv("IIP_BOLSAI_API_KEY", "fake-key")
    monkeypatch.setattr(
        BolsaiHTTPHarvester,
        "fetch",
        lambda self, target: FetchedFundamentals(
            target=target, status_code=200, fundamentals=fake_fundamentals()
        ),
    )
    out_file = tmp_path / "out.json"
    result = CliRunner().invoke(
        cli,
        ["fetch-template", "KLBN4", "--type", "equity", "--cnpj", cnpj,
         "--ano", "2025", "-o", str(out_file)],
    )
    assert result.exit_code == 0, result.output
    return json.loads(out_file.read_text(encoding="utf-8")), result.output


def test_fetch_template_equity_fills_resilience_ratios(monkeypatch, tmp_path):
    data, _ = _run_equity_template(monkeypatch, tmp_path, CNPJ)
    fin = data["financials"]
    assert fin["current_ratio"] == pytest.approx(18049685 / 8767398, abs=1e-4)
    assert fin["debt_to_equity"] == pytest.approx(36721042 / 14401101, abs=1e-4)
    assert fin["interest_coverage"] == pytest.approx(4480349 / 2628543, abs=1e-4)


def test_fetch_template_equity_keeps_defaults_for_unavailable_ratios(
    monkeypatch, tmp_path
):
    from iip.cli.fetch_template import _equity_defaults

    defaults = _equity_defaults()
    for cnpj in (BANK_CNPJ, ZERO_DEBT_CNPJ):
        data, _ = _run_equity_template(monkeypatch, tmp_path, cnpj)
        fin = data["financials"]
        # bank: nothing derivable; ZERO_DEBT: real current ratio and
        # coverage, but the zero debt total must NOT become debt_to_equity=0.
        assert fin["debt_to_equity"] == defaults["debt_to_equity"]
        if cnpj == BANK_CNPJ:
            assert fin["current_ratio"] == defaults["current_ratio"]
            assert fin["interest_coverage"] == defaults["interest_coverage"]
        else:
            assert fin["current_ratio"] == pytest.approx(3316531 / 1284420, abs=1e-4)


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
