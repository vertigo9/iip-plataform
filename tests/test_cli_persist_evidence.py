import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_persist_evidence_creates_a_real_file(monkeypatch, tmp_path):
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("IIP_OBSIDIAN_VAULT", str(vault_dir))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "persist-evidence",
            "EV-001",
            "--ticker",
            "BTLG11",
            "--source-type",
            "cvm_fii",
            "--fact",
            "Dividend yield 0.94% no mês",
        ],
    )

    assert result.exit_code == 0
    evidence_file = vault_dir / "04_Evidence" / "EV-001.md"
    assert evidence_file.exists()
    content = evidence_file.read_text(encoding="utf-8")
    assert "evidence_id: EV-001" in content
    assert "ticker: BTLG11" in content
    assert "Dividend yield 0.94% no mês" in content


def test_persist_evidence_rejects_duplicate_id(monkeypatch, tmp_path):
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("IIP_OBSIDIAN_VAULT", str(vault_dir))

    runner = CliRunner()
    runner.invoke(
        cli,
        ["persist-evidence", "EV-DUP", "--ticker", "BTLG11", "--source-type", "manual"],
    )
    result = runner.invoke(
        cli,
        ["persist-evidence", "EV-DUP", "--ticker", "BTLG11", "--source-type", "manual"],
    )

    assert result.exit_code != 0
    assert "já existe" in result.output


def test_persist_evidence_rejects_invalid_date_format(monkeypatch, tmp_path):
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("IIP_OBSIDIAN_VAULT", str(vault_dir))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "persist-evidence",
            "EV-002",
            "--ticker",
            "BTLG11",
            "--source-type",
            "manual",
            "--date",
            "12/08/2026",
        ],
    )

    assert result.exit_code != 0
    assert "YYYY-MM-DD" in result.output


def test_persist_evidence_accepts_explicit_date(monkeypatch, tmp_path):
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("IIP_OBSIDIAN_VAULT", str(vault_dir))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "persist-evidence",
            "EV-003",
            "--ticker",
            "BTLG11",
            "--source-type",
            "manual",
            "--date",
            "2026-08-01",
        ],
    )

    assert result.exit_code == 0
    content = (vault_dir / "04_Evidence" / "EV-003.md").read_text(encoding="utf-8")
    assert "date: 2026-08-01" in content


def test_full_cycle_fetch_evidence_decide_persist_via_cli_only(monkeypatch, tmp_path):
    """O teste que fecha o ciclo: nada de Python direto, só comandos CLI,
    do template ate' a decisao persistida e reconstruivel."""
    import json

    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("IIP_OBSIDIAN_VAULT", str(vault_dir))
    runner = CliRunner()

    data_file = tmp_path / "btlg11.json"
    runner.invoke(cli, ["analyze-template", "--type", "fii", "-o", str(data_file)])
    data = json.loads(data_file.read_text(encoding="utf-8"))
    data["sector"] = "Logística"
    data["industry"] = "Galpões"
    data_file.write_text(json.dumps(data), encoding="utf-8")

    ev_result = runner.invoke(
        cli,
        [
            "persist-evidence",
            "EV-CICLO",
            "--ticker",
            "BTLG11",
            "--source-type",
            "cvm_fii",
            "--fact",
            "Teste de ciclo completo via CLI",
        ],
    )
    assert ev_result.exit_code == 0

    decide_result = runner.invoke(
        cli,
        [
            "analyze",
            "BTLG11",
            "--type",
            "fii",
            "--data-file",
            str(data_file),
            "--decide",
            "--evidence-id",
            "EV-CICLO",
            "--persist",
        ],
    )
    assert decide_result.exit_code == 0
    assert "Decision persistida" in decide_result.output

    from iip.knowledge.bridge import KnowledgeBridge

    ctx = KnowledgeBridge(str(vault_dir)).assemble("BTLG11")
    assert len(ctx.decision_history) == 1
