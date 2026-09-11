import json

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def make_data_file(tmp_path, asset_type="fii"):
    runner = CliRunner()
    template_path = tmp_path / "template.json"
    runner.invoke(
        cli, ["analyze-template", "--type", asset_type, "-o", str(template_path)]
    )
    data = json.loads(template_path.read_text(encoding="utf-8"))
    data["sector"] = "Logística"
    data["industry"] = "Galpões"
    template_path.write_text(json.dumps(data), encoding="utf-8")
    return template_path


def test_analyze_without_persist_does_not_touch_the_vault(monkeypatch, tmp_path):
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("IIP_OBSIDIAN_VAULT", str(vault_dir))
    data_file = make_data_file(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["analyze", "BTLG11", "--type", "fii", "--data-file", str(data_file)]
    )

    assert result.exit_code == 0
    assert not vault_dir.exists()


def test_analyze_with_persist_writes_to_the_vault(monkeypatch, tmp_path):
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("IIP_OBSIDIAN_VAULT", str(vault_dir))
    data_file = make_data_file(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "analyze",
            "BTLG11",
            "--type",
            "fii",
            "--data-file",
            str(data_file),
            "--persist",
        ],
    )

    assert result.exit_code == 0
    note_path = vault_dir / "01_Assets" / "FIIs" / "BTLG11" / "BTLG11 - Score e Ranking.md"
    assert note_path.exists()
    assert "IIP:analysis" in note_path.read_text(encoding="utf-8")


def test_analyze_with_persist_works_for_etf(monkeypatch, tmp_path):
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("IIP_OBSIDIAN_VAULT", str(vault_dir))
    data_file = make_data_file(tmp_path, asset_type="etf")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "analyze",
            "BOVA11",
            "--type",
            "etf",
            "--data-file",
            str(data_file),
            "--persist",
        ],
    )

    assert result.exit_code == 0
    note_path = vault_dir / "01_Assets" / "ETFs" / "BOVA11" / "BOVA11 - Score e Ranking.md"
    assert note_path.exists()


def test_analyze_persist_failure_does_not_crash_the_command(monkeypatch, tmp_path):
    # Point the vault at something that can't be created as a directory
    # (a file where a directory is expected) to force a real failure.
    blocked_path = tmp_path / "blocked_file"
    blocked_path.write_text("nao sou uma pasta", encoding="utf-8")
    monkeypatch.setenv("IIP_OBSIDIAN_VAULT", str(blocked_path / "vault"))
    data_file = make_data_file(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "analyze",
            "BTLG11",
            "--type",
            "fii",
            "--data-file",
            str(data_file),
            "--persist",
        ],
    )

    # the analysis itself must still succeed and print, even if persist fails
    assert result.exit_code == 0
    assert "Overall score" in result.output
    assert "Aviso" in result.output
