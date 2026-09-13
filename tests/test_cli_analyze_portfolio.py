import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.portfolio.registry import PortfolioAsset


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_analyze_portfolio_runs_and_reports_summary(monkeypatch, tmp_path):
    from iip.cli.fetch_template import FetchResult

    def fake_fetch_equity(symbol, bolsai_api_key, brapi_token):
        return (
            {"price": 33.81, "financials": {"dividend_yield": 7.5}},
            FetchResult(fetched_fields=("price",)),
        )

    monkeypatch.setattr(
        "iip.portfolio.batch_analyze.assets_refreshable_now",
        lambda: (
            PortfolioAsset(
                "BBSE3", "equity", sector="Financeiro", industry="Previdência e Seguros"
            ),
        ),
    )

    import iip.cli.fetch_template as ft

    monkeypatch.setattr(ft, "fetch_equity_template_live", fake_fetch_equity)

    vault_dir = tmp_path / "vault"
    runner = CliRunner()
    result = runner.invoke(
        cli, ["analyze-portfolio", "--vault", str(vault_dir)]
    )

    assert result.exit_code == 0
    assert "Resumo: 1 ok, 0 erro, 0 pulado" in result.output
    assert (vault_dir / "01_Assets" / "Equities" / "BBSE3").exists()
