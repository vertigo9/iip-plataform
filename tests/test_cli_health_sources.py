from click.testing import CliRunner

from iip.cli.main import cli
from iip.health import DataSourceReachabilityCheck


def test_health_without_sources_flag_skips_data_source_checks():
    runner = CliRunner()
    result = runner.invoke(cli, ["health"])

    assert result.exit_code == 0
    assert "source_cvm" not in result.output


def test_health_with_sources_flag_includes_data_source_checks(monkeypatch):
    class FakeResponse:
        status = 200

    def fake_opener(request, timeout):
        return FakeResponse()

    monkeypatch.setattr(
        "iip.health.default_data_source_checks",
        lambda: (
            DataSourceReachabilityCheck(
                "cvm", "https://dados.cvm.gov.br", opener=fake_opener
            ),
        ),
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["health", "--sources"])

    assert result.exit_code == 0
    assert "source_cvm" in result.output
