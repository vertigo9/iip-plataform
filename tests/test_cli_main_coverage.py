"""
Testes de cobertura para iip.cli.main.

Estratégia: usar click.testing.CliRunner para invocar cada comando de
verdade, mockando as dependências externas (Runtime, ModuleRegistry,
MetricsEngine, ReplicationEngine, VersionManager, ReportExporter, os
health checks e ANALYZERS) — assim testamos a lógica de wiring do CLI
sem depender dos internals reais dessas classes.

Nota: a linha `if __name__ == "__main__": cli()` no fim do arquivo não
é coberta por nenhum teste (só roda ao executar o módulo diretamente).
Isso é normal — se quiser fechar 100%, adicione `# pragma: no cover`
nessa linha no arquivo real.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from iip.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# cli / version
# ---------------------------------------------------------------------------


def test_cli_without_subcommand_prints_help(runner):
    result = runner.invoke(main.cli, [])

    assert result.exit_code == 0
    assert "IIP Platform CLI" in result.output


def test_version_command_prints_version(runner):
    result = runner.invoke(main.cli, ["version"])

    assert result.exit_code == 0
    assert "IIP Platform" in result.output


# ---------------------------------------------------------------------------
# knowledge-status
# ---------------------------------------------------------------------------


def test_knowledge_status_reports_zero_counts_when_vault_missing(
    runner, monkeypatch, tmp_path
):
    fake_vault = tmp_path / "does-not-exist"
    monkeypatch.setattr(
        main, "get_settings", lambda: SimpleNamespace(obsidian_vault=fake_vault)
    )

    result = runner.invoke(main.cli, ["knowledge-status"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["exists"] is False
    assert payload["decisions"] == 0
    assert payload["evidence"] == 0
    assert payload["snapshots"] == 0
    assert payload["exposures"] == 0


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------


def _patch_health_check_classes(monkeypatch):
    for name in (
        "PythonVersionHealthCheck",
        "ModuleCountHealthCheck",
        "VersionCompatibilityHealthCheck",
        "ReplicationStatusHealthCheck",
        "SynchronizationHealthCheck",
    ):
        monkeypatch.setattr(main, name, MagicMock())


def _fake_health_context(healthy: bool):
    check = SimpleNamespace(
        healthy=healthy, name="check", message="ok" if healthy else "boom"
    )
    hs = SimpleNamespace(healthy=healthy, checks=[check])
    health_engine = MagicMock()
    health_engine.run_all.return_value = hs
    return SimpleNamespace(health_engine=health_engine)


def test_health_exits_with_error_when_runtime_not_initialized(runner, monkeypatch):
    monkeypatch.setattr(main.Runtime, "start", staticmethod(lambda: None))
    monkeypatch.setattr(main.Runtime, "get_context", staticmethod(lambda: None))

    result = runner.invoke(main.cli, ["health"])

    assert result.exit_code == 1
    assert "Runtime not initialized" in result.output


def test_health_reports_healthy_system(runner, monkeypatch):
    ctx = _fake_health_context(healthy=True)
    monkeypatch.setattr(main.Runtime, "start", staticmethod(lambda: None))
    monkeypatch.setattr(main.Runtime, "get_context", staticmethod(lambda: ctx))
    _patch_health_check_classes(monkeypatch)

    result = runner.invoke(main.cli, ["health"])

    assert result.exit_code == 0
    assert "HEALTHY" in result.output
    assert ctx.health_engine.register.call_count == 5


def test_health_exits_with_error_when_unhealthy(runner, monkeypatch):
    ctx = _fake_health_context(healthy=False)
    monkeypatch.setattr(main.Runtime, "start", staticmethod(lambda: None))
    monkeypatch.setattr(main.Runtime, "get_context", staticmethod(lambda: ctx))
    _patch_health_check_classes(monkeypatch)

    result = runner.invoke(main.cli, ["health"])

    assert result.exit_code == 1
    assert "UNHEALTHY" in result.output


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_exits_with_error_when_runtime_not_initialized(runner, monkeypatch):
    monkeypatch.setattr(main.Runtime, "start", staticmethod(lambda: None))
    monkeypatch.setattr(main.Runtime, "get_context", staticmethod(lambda: None))

    result = runner.invoke(main.cli, ["status"])

    assert result.exit_code == 1
    assert "Runtime not initialized" in result.output


def test_status_prints_platform_info(runner, monkeypatch):
    fake_ctx = SimpleNamespace(
        settings=SimpleNamespace(
            app_name="IIP",
            version="1.2.3",
            environment=SimpleNamespace(value="production"),
        ),
        started=True,
    )
    monkeypatch.setattr(main.Runtime, "start", staticmethod(lambda: None))
    monkeypatch.setattr(main.Runtime, "get_context", staticmethod(lambda: fake_ctx))
    monkeypatch.setattr(main.VersionManager, "current", staticmethod(lambda: "9.9.9"))

    result = runner.invoke(main.cli, ["status"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["app"] == "IIP"
    assert payload["version"] == "1.2.3"
    assert payload["env"] == "production"
    assert payload["platform_version"] == "9.9.9"


# ---------------------------------------------------------------------------
# modules
# ---------------------------------------------------------------------------


def test_modules_lists_registered_modules(runner, monkeypatch):
    status = {
        "modules": {
            "harvest": {"version": "1.0", "enabled": True, "loaded": True},
            "analysis": {"version": "0.9", "enabled": False, "loaded": False},
        },
        "total": 2,
        "enabled": 1,
        "loaded": 1,
    }
    monkeypatch.setattr(main.ModuleRegistry, "status", staticmethod(lambda: status))

    result = runner.invoke(main.cli, ["modules"])

    assert result.exit_code == 0
    assert "harvest" in result.output
    assert "Total: 2" in result.output


# ---------------------------------------------------------------------------
# metrics / replication
# ---------------------------------------------------------------------------


def test_metrics_prints_summary(runner, monkeypatch):
    monkeypatch.setattr(main.Runtime, "start", staticmethod(lambda: None))
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        main.MetricsEngine, "summary", staticmethod(lambda settings: {"ok": True})
    )

    result = runner.invoke(main.cli, ["metrics"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"ok": True}


def test_replication_prints_status(runner, monkeypatch):
    monkeypatch.setattr(
        main.ReplicationEngine, "status", staticmethod(lambda: {"synced": True})
    )

    result = runner.invoke(main.cli, ["replication"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"synced": True}


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


def test_config_prints_active_configuration(runner, monkeypatch):
    fake_ctx = SimpleNamespace(
        settings=SimpleNamespace(
            environment=SimpleNamespace(value="staging"),
            debug=True,
            app_name="IIP",
            log_level="INFO",
            base_dir="/tmp/iip",
            bolsai_api_key=None,
            brapi_token="fake-token-object",
        )
    )
    monkeypatch.setattr(main.Runtime, "start", staticmethod(lambda: None))
    monkeypatch.setattr(main.Runtime, "get_context", staticmethod(lambda: fake_ctx))

    result = runner.invoke(main.cli, ["config"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["environment"] == "staging"
    assert payload["debug"] is True
    assert payload["credentials"]["bolsai_api_key"] == "não configurada"
    assert payload["credentials"]["brapi_token"] == "configurada"


def test_config_prints_nothing_when_no_context(runner, monkeypatch):
    monkeypatch.setattr(main.Runtime, "start", staticmethod(lambda: None))
    monkeypatch.setattr(main.Runtime, "get_context", staticmethod(lambda: None))

    result = runner.invoke(main.cli, ["config"])

    assert result.exit_code == 0
    assert result.output.strip() == ""


# ---------------------------------------------------------------------------
# _template_financials (usado por analyze-template)
# ---------------------------------------------------------------------------


def test_template_financials_records_defaults_used_by_analyzer():
    class _FakeAnalyzer:
        def analyze(self, asset):
            asset.financials.get("dividend_yield", 0.0)
            asset.financials.get("p_vp", 1.0)
            return "ignored"

    fields = main._template_financials(_FakeAnalyzer)

    assert fields == {"dividend_yield": 0.0, "p_vp": 1.0}


def test_template_financials_recovers_partial_fields_when_analyzer_raises():
    class _FakeAnalyzerThatRaises:
        def analyze(self, asset):
            asset.financials.get("dividend_yield", 0.0)
            raise RuntimeError("boom deep in a branch")

    fields = main._template_financials(_FakeAnalyzerThatRaises)

    assert fields == {"dividend_yield": 0.0}


def test_analyze_template_writes_json_to_output_file(runner, tmp_path):
    output_path = tmp_path / "template.json"

    result = runner.invoke(
        main.cli,
        ["analyze-template", "--type", "equity", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    assert "Template written to" in result.output


def test_analyze_template_without_output_prints_payload_and_tip(runner):
    result = runner.invoke(main.cli, ["analyze-template", "--type", "equity"])

    assert result.exit_code == 0
    assert '"symbol": "TICKER11"' in result.output
    assert "Tip: save this to a file" in result.output


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


def _fake_report(notes: str | None = None):
    pillar = SimpleNamespace(
        pillar=SimpleNamespace(value="Quality"),
        score=8.5,
        weight=0.4,
        weighted_score=lambda: 3.4,
    )
    return SimpleNamespace(
        asset_symbol="PCIP11",
        pillar_scores=[pillar],
        overall_score=82.0,
        recommendation="Buy",
        risk_level="Moderate",
        notes=notes,
        to_dict=lambda: {"asset_symbol": "PCIP11", "overall_score": 82.0},
    )


def test_analyze_table_format_prints_notes_when_present(runner, monkeypatch, tmp_path):
    data_file = tmp_path / "data.json"
    data_file.write_text(
        json.dumps({"sector": "Papel", "industry": "Logistica"}), encoding="utf-8"
    )
    report_with_notes = _fake_report(notes="Concentração setorial elevada")
    fake_analyzer_cls = MagicMock(
        return_value=MagicMock(analyze=MagicMock(return_value=report_with_notes))
    )
    monkeypatch.setitem(main.ANALYZERS, "equity", fake_analyzer_cls)

    result = runner.invoke(
        main.cli,
        ["analyze", "PCIP11", "--type", "equity", "--data-file", str(data_file)],
    )

    assert result.exit_code == 0
    assert "Concentração setorial elevada" in result.output


def test_analyze_reports_invalid_json(runner, tmp_path):
    data_file = tmp_path / "bad.json"
    data_file.write_text("{not valid json", encoding="utf-8")

    result = runner.invoke(
        main.cli,
        ["analyze", "PCIP11", "--type", "equity", "--data-file", str(data_file)],
    )

    assert result.exit_code == 1
    assert "Invalid JSON" in result.output


def test_analyze_reports_missing_required_fields(runner, tmp_path):
    data_file = tmp_path / "data.json"
    data_file.write_text(json.dumps({"sector": "Papel"}), encoding="utf-8")

    result = runner.invoke(
        main.cli,
        ["analyze", "PCIP11", "--type", "equity", "--data-file", str(data_file)],
    )

    assert result.exit_code == 1
    assert "Missing required field" in result.output
    assert "industry" in result.output


def test_analyze_table_format_also_saves_json_when_output_given(
    runner, monkeypatch, tmp_path
):
    data_file = tmp_path / "data.json"
    data_file.write_text(
        json.dumps({"sector": "Papel", "industry": "Logistica"}), encoding="utf-8"
    )
    output_path = tmp_path / "report.json"
    fake_analyzer_cls = MagicMock(
        return_value=MagicMock(analyze=MagicMock(return_value=_fake_report()))
    )
    monkeypatch.setitem(main.ANALYZERS, "equity", fake_analyzer_cls)

    result = runner.invoke(
        main.cli,
        [
            "analyze",
            "PCIP11",
            "--type",
            "equity",
            "--data-file",
            str(data_file),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    assert "Also saved as JSON to" in result.output


def test_analyze_non_table_format_prints_content_when_no_output(
    runner, monkeypatch, tmp_path
):
    data_file = tmp_path / "data.json"
    data_file.write_text(
        json.dumps({"sector": "Papel", "industry": "Logistica"}), encoding="utf-8"
    )
    fake_analyzer_cls = MagicMock(
        return_value=MagicMock(analyze=MagicMock(return_value=_fake_report()))
    )
    monkeypatch.setitem(main.ANALYZERS, "equity", fake_analyzer_cls)
    monkeypatch.setattr(
        main.ReportExporter,
        "to_json",
        staticmethod(lambda report, output: '{"ok": true}'),
    )

    result = runner.invoke(
        main.cli,
        [
            "analyze",
            "PCIP11",
            "--type",
            "equity",
            "--data-file",
            str(data_file),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '{"ok": true}' in result.output


def test_analyze_non_table_format_saves_and_confirms_when_output_given(
    runner, monkeypatch, tmp_path
):
    data_file = tmp_path / "data.json"
    data_file.write_text(
        json.dumps({"sector": "Papel", "industry": "Logistica"}), encoding="utf-8"
    )
    output_path = tmp_path / "report.json"
    fake_analyzer_cls = MagicMock(
        return_value=MagicMock(analyze=MagicMock(return_value=_fake_report()))
    )
    monkeypatch.setitem(main.ANALYZERS, "equity", fake_analyzer_cls)
    monkeypatch.setattr(
        main.ReportExporter,
        "to_json",
        staticmethod(lambda report, output: '{"ok": true}'),
    )

    result = runner.invoke(
        main.cli,
        [
            "analyze",
            "PCIP11",
            "--type",
            "equity",
            "--data-file",
            str(data_file),
            "--format",
            "json",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    # O Rich Console pode quebrar linhas longas na exibição (paths de teste
    # do Windows/temp são compridos) — remove quebras de linha antes de
    # comparar, já que isso é só formatação visual, não o conteúdo real.
    flat_output = result.output.replace("\n", "")
    assert f"Report saved to {output_path}" in flat_output
