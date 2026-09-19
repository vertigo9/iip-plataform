import json

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.knowledge.bridge import KnowledgeBridge
from iip.knowledge.models import Evidence


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def make_data_file(tmp_path):
    runner = CliRunner()
    template_path = tmp_path / "btlg11.json"
    runner.invoke(cli, ["analyze-template", "--type", "fii", "-o", str(template_path)])
    data = json.loads(template_path.read_text(encoding="utf-8"))
    data["sector"] = "Logística"
    data["industry"] = "Galpões"
    data["financials"]["dividend_yield"] = 5.4
    template_path.write_text(json.dumps(data), encoding="utf-8")
    return template_path


def test_decide_without_evidence_id_fails_before_anything_is_generated(tmp_path):
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
            "--decide",
        ],
    )
    assert result.exit_code != 0
    assert "evidence-id" in result.output.lower()


def test_decide_prints_a_real_decision(tmp_path):
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
            "--decide",
            "--evidence-id",
            "EV-QUALQUER",
        ],
    )
    assert result.exit_code == 0
    assert "Decision:" in result.output
    assert any(
        v in result.output
        for v in ("COMPRAR", "MANTER", "AGUARDAR", "REDUZIR", "VENDER")
    )


def test_decide_warns_when_valuation_score_omitted(tmp_path):
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
            "--decide",
            "--evidence-id",
            "EV-QUALQUER",
        ],
    )
    assert "valuation_score não fornecido" in result.output


def test_decide_persist_fails_honestly_without_real_evidence(monkeypatch, tmp_path):
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
            "--decide",
            "--evidence-id",
            "EV-QUE-NAO-EXISTE",
            "--persist",
        ],
    )
    assert result.exit_code == 0  # a analise em si nao falha
    output_sem_quebra = result.output.replace("\n", " ")
    assert "não consegui persistir a decisão" in output_sem_quebra
    assert "Evidence not" in output_sem_quebra
    assert "EV-QUE-NAO-EXISTE" in output_sem_quebra
    decision_dir = vault_dir / "03_Decisions"
    assert not decision_dir.exists() or not list(decision_dir.iterdir())


def test_decide_persist_succeeds_with_real_pre_existing_evidence(monkeypatch, tmp_path):
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("IIP_OBSIDIAN_VAULT", str(vault_dir))
    data_file = make_data_file(tmp_path)

    from datetime import date

    KnowledgeBridge(str(vault_dir)).persist_evidence(
        Evidence(
            evidence_id="EV-REAL-001",
            ticker="BTLG11",
            date=date(2026, 8, 1),
            source_type="cvm_fii",
        )
    )

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
            "--decide",
            "--evidence-id",
            "EV-REAL-001",
            "--persist",
        ],
    )
    assert result.exit_code == 0
    assert "Decision persistida" in result.output

    ctx = KnowledgeBridge(str(vault_dir)).assemble("BTLG11")
    assert len(ctx.decision_history) == 1


def test_decide_accepts_explicit_valuation_score_without_warning(tmp_path):
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
            "--decide",
            "--evidence-id",
            "EV-QUALQUER",
            "--valuation-score",
            "7.5",
        ],
    )
    assert result.exit_code == 0
    assert "valuation_score não fornecido" not in result.output
