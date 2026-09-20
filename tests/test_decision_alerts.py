from datetime import date

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.portfolio import batch_decide
from iip.portfolio.batch_decide import DecisionOutcome, DecisionRunResult
from iip.portfolio.decision_alerts import (
    change_of,
    decision_changes,
    write_alert_file,
)

TODAY = date(2026, 9, 20)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _ok(ticker, verdict, previous=None):
    return DecisionOutcome(
        ticker,
        "ok",
        verdict,
        asset_class="equity",
        verdict=verdict,
        score=5.0,
        confidence=0.5,
        previous_verdict=previous,
        analysis_score=50.0,
    )


def _result(*outcomes):
    return DecisionRunResult(tuple(outcomes), "nota", TODAY)


def test_a_worse_verdict_is_a_piora_and_a_better_one_a_melhora():
    assert change_of(_ok("A3", "REDUZIR", "MANTER")).direction == "piora"
    assert change_of(_ok("B3", "MANTER", "AGUARDAR")).direction == "melhora"
    assert change_of(_ok("C3", "VENDER", "AGUARDAR")).direction == "piora"
    assert change_of(_ok("D3", "COMPRAR", "MANTER")).direction == "melhora"


def test_no_change_no_previous_or_not_decided_is_not_a_change():
    assert change_of(_ok("A3", "MANTER", "MANTER")) is None
    assert change_of(_ok("A3", "MANTER", None)) is None
    assert change_of(DecisionOutcome("A3", "erro", "bolsai 429")) is None
    assert change_of(DecisionOutcome("A3", "pulado", "sem evidência")) is None


def test_a_verdict_outside_the_known_scale_is_a_change_without_a_direction():
    change = change_of(_ok("A3", "MANTER", "TALVEZ"))

    assert change.direction == "muda"


def test_worsenings_come_first_then_by_ticker():
    result = _result(
        _ok("Z3", "MANTER", "AGUARDAR"),
        _ok("B3", "REDUZIR", "MANTER"),
        _ok("A3", "MANTER", "AGUARDAR"),
        _ok("C3", "AGUARDAR", "MANTER"),
    )

    assert [c.ticker for c in decision_changes(result)] == ["B3", "C3", "A3", "Z3"]


def test_the_alert_file_has_one_line_per_change(tmp_path):
    path = tmp_path / "logs" / "alertas.txt"
    result = _result(
        _ok("PASS3", "REDUZIR", "MANTER"), _ok("XPML11", "MANTER", "AGUARDAR")
    )

    changes = write_alert_file(path, result)

    assert len(changes) == 2
    assert path.read_text(encoding="utf-8").splitlines() == [
        "PASS3: MANTER -> REDUZIR (piora)",
        "XPML11: AGUARDAR -> MANTER (melhora)",
    ]


def test_a_run_without_changes_removes_yesterdays_alert_file(tmp_path):
    path = tmp_path / "alertas.txt"
    path.write_text("VELHO: MANTER -> REDUZIR (piora)\n", encoding="utf-8")

    assert write_alert_file(path, _result(_ok("A3", "MANTER", "MANTER"))) == ()
    assert not path.exists()


def test_no_alert_file_and_no_changes_is_fine(tmp_path):
    assert write_alert_file(tmp_path / "alertas.txt", _result()) == ()


def _patch_run(monkeypatch, result):
    monkeypatch.setattr(batch_decide, "decide_portfolio", lambda **kw: result)


def test_command_writes_the_alert_file_and_prints_the_direction(monkeypatch, tmp_path):
    _patch_run(monkeypatch, _result(_ok("PASS3", "REDUZIR", "MANTER")))
    alert = tmp_path / "alertas.txt"

    out = CliRunner().invoke(
        cli, ["decide-portfolio", "--vault", str(tmp_path), "--alert-file", str(alert)]
    )

    assert out.exit_code == 0, out.output
    assert "PASS3: MANTER -> REDUZIR (piora)" in out.output
    assert alert.read_text(encoding="utf-8") == "PASS3: MANTER -> REDUZIR (piora)\n"


def test_command_clears_a_stale_alert_file_when_nothing_changed(monkeypatch, tmp_path):
    _patch_run(monkeypatch, _result(_ok("A3", "MANTER", "MANTER")))
    alert = tmp_path / "alertas.txt"
    alert.write_text("VELHO\n", encoding="utf-8")

    out = CliRunner().invoke(
        cli, ["decide-portfolio", "--vault", str(tmp_path), "--alert-file", str(alert)]
    )

    assert out.exit_code == 0, out.output
    assert not alert.exists()


def test_command_without_the_option_writes_no_file(monkeypatch, tmp_path):
    _patch_run(monkeypatch, _result(_ok("PASS3", "REDUZIR", "MANTER")))

    CliRunner().invoke(cli, ["decide-portfolio", "--vault", str(tmp_path)])

    assert not list(tmp_path.rglob("*.txt"))
