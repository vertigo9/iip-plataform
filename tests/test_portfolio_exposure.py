from datetime import date

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.obsidian.exposure_report import render_exposure_report, write_exposure_report
from iip.portfolio.exposure import (
    SEM_CLASSIFICACAO,
    build_exposure,
)
from iip.portfolio.registry import get_asset
from iip.universal.portfolio_state import PortfolioState, PositionState

TODAY = date(2026, 9, 20)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _position(ticker, value, asset_class="equity"):
    return PositionState(
        ticker=ticker,
        quantity=1.0,
        market_value=value,
        weight=0.0,
        asset_class=asset_class,
    )


def _state(*positions, as_of="2026-09-12"):
    return PortfolioState(
        as_of=as_of,
        positions=tuple(positions),
        total_value=sum(p.market_value for p in positions),
    )


def _dimension(report, name):
    return next(d for d in report.dimensions if d.name == name)


def _row(dimension, label):
    return next(r for r in dimension.rows if r.label == label)


def test_weights_are_position_value_over_the_total_and_sum_to_one():
    state = _state(
        _position("BBSE3", 600.0), _position("CMIG4", 300.0), _position("HGRU11", 100.0)
    )

    report = build_exposure(state, today=TODAY)

    classe = _dimension(report, "Classe")
    assert sum(r.weight for r in classe.rows) == pytest.approx(1.0)
    assert _row(classe, "Ações").weight == pytest.approx(0.9)
    assert _row(classe, "FII").weight == pytest.approx(0.1)
    assert report.total_value == 1000.0 and report.position_count == 3


def test_groups_use_the_registry_classification():
    state = _state(_position("HGRU11", 500.0), _position("LVBI11", 500.0))
    manager = get_asset("HGRU11").manager

    report = build_exposure(state, today=TODAY)

    row = _row(_dimension(report, "Gestora"), manager)
    assert row.count == 2 and row.weight == pytest.approx(1.0)
    assert row.tickers == ("HGRU11", "LVBI11")


def test_what_the_registry_does_not_classify_is_shown_as_such_not_hidden():
    state = _state(
        _position("BBSE3", 500.0),
        _position("RF-XYZ", 500.0, asset_class="fixed_income"),
    )

    report = build_exposure(state, today=TODAY)

    classe = _dimension(report, "Classe")
    assert _row(classe, "Renda fixa bancária").weight == pytest.approx(0.5)
    gestora = _dimension(report, "Gestora")
    assert gestora.rows[-1].label == SEM_CLASSIFICACAO
    assert gestora.classified_weight == pytest.approx(0.0)
    assert gestora.low_coverage


def test_the_unclassified_group_is_never_a_concentration_flag():
    state = _state(_position("RF-A", 900.0, "fixed_income"), _position("BBSE3", 100.0))

    report = build_exposure(state, today=TODAY, position_limit=1.0)

    assert not any(f.label == SEM_CLASSIFICACAO for f in report.flags)


def test_a_heavy_position_and_a_heavy_group_are_flagged_worst_first():
    state = _state(
        _position("BBSE3", 300.0),
        _position("CMIG4", 100.0),
        _position("HGRU11", 100.0),
        _position("LVBI11", 100.0),
        _position("CPFE3", 100.0),
        _position("ISAE4", 100.0),
        _position("CXSE3", 100.0),
        _position("ALOS3", 100.0),
    )

    report = build_exposure(state, today=TODAY, group_limit=0.30, position_limit=0.25)

    assert report.flags[0].weight >= report.flags[-1].weight
    assert any(f.kind == "posição" and f.label == "BBSE3" for f in report.flags)
    assert all(f.weight > (0.25 if f.kind == "posição" else 0.30) for f in report.flags)


def test_the_class_and_risk_views_are_shown_but_never_flagged():
    state = _state(_position("BBSE3", 1000.0))

    report = build_exposure(state, today=TODAY, position_limit=1.0)

    assert {f.dimension for f in report.flags}.isdisjoint({"Classe", "Perfil de risco"})
    assert _row(_dimension(report, "Classe"), "Ações").weight == pytest.approx(1.0)


def test_the_snapshot_age_and_staleness_come_from_its_date():
    state = _state(_position("BBSE3", 100.0), as_of="2026-09-12")

    old = build_exposure(state, today=TODAY)
    fresh = build_exposure(state, today=date(2026, 9, 14))

    assert old.age_days == 8 and old.stale
    assert fresh.age_days == 2 and not fresh.stale


def test_an_unreadable_snapshot_date_is_unknown_not_guessed():
    report = build_exposure(
        _state(_position("BBSE3", 100.0), as_of="sem data"), today=TODAY
    )

    assert report.as_of is None and report.age_days is None and not report.stale


def test_registry_assets_missing_from_the_snapshot_are_reported():
    report = build_exposure(_state(_position("BBSE3", 100.0)), today=TODAY)

    assert "HGRU11" in report.missing_from_snapshot
    assert "BBSE3" not in report.missing_from_snapshot


def test_the_fgts_fund_id_is_recognised_as_the_registry_ticker():
    state = _state(_position("FMP-FGTS-DAYCOVAL", 100.0, "fixed_income"))

    report = build_exposure(state, today=TODAY)

    assert "AXIA3" not in report.missing_from_snapshot
    assert _row(_dimension(report, "Classe"), "FMP-FGTS").count == 1


def test_a_snapshot_without_value_is_an_error():
    with pytest.raises(ValueError):
        build_exposure(_state(_position("BBSE3", 0.0)), today=TODAY)


def test_the_report_states_the_limits_of_the_reading():
    state = _state(_position("BBSE3", 600.0), _position("RF-A", 400.0, "fixed_income"))

    text = render_exposure_report(build_exposure(state, today=TODAY))

    assert "Snapshot de 12/09/2026" in text and "Defasado" in text
    assert "Fora do snapshot" in text and "HGRU11" in text
    assert "Cobertura baixa" in text
    assert "BBSE3" in text and "60.0%" in text
    assert "alocação, não concentração" in text
    assert "R$ 1.000,00" in text


def test_the_report_is_written_to_the_portfolio_folder(tmp_path):
    report = build_exposure(_state(_position("BBSE3", 100.0)), today=TODAY)

    path = write_exposure_report(tmp_path, report)

    assert path == tmp_path / "02_Portfolio" / "Exposicao.md"
    assert path.read_text(encoding="utf-8").startswith("---\ntype: portfolio_exposure")


# --- CLI ------------------------------------------------------------------------

_SNAPSHOT = """\
---
type: portfolio
---

| ID | Ativo | Classe | Quantidade | PM | Preço atual | Valor | Peso | Peso alvo | Status |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| BBSE3 | BBSE3 | acao | 10,0000 | 30,00 | 40,00 | 600,00 | 60,00% | | active |
| RF-BANCO-1 | CDB | renda_fixa | 1,0000 | 400,00 | 400,00 | 400,00 | 40,00% | | active |
| ANTIGA3 | ANTIGA3 | acao | 5,0000 | 1,00 | 1,00 | 5,00 | 0,50% | | closed |
"""


def _snapshot_file(tmp_path):
    path = tmp_path / "02_Portfolio" / "Current.md"
    path.parent.mkdir(parents=True)
    path.write_text(_SNAPSHOT, encoding="utf-8")
    return path


def test_command_reads_the_snapshot_and_prints_the_views_and_flags(tmp_path):
    _snapshot_file(tmp_path)

    out = CliRunner().invoke(cli, ["portfolio-exposure", "--vault", str(tmp_path)])

    assert out.exit_code == 0, out.output
    assert "2 posições" in out.output  # a posição encerrada não entra
    assert "Renda fixa bancária" in out.output
    assert "Alertas de concentração" in out.output
    assert "BBSE3" in out.output
    assert "defasado" in out.output
    assert not (tmp_path / "02_Portfolio" / "Exposicao.md").exists()


def test_command_writes_the_note_with_report(tmp_path):
    _snapshot_file(tmp_path)

    out = CliRunner().invoke(
        cli, ["portfolio-exposure", "--vault", str(tmp_path), "--report"]
    )

    assert out.exit_code == 0, out.output
    assert (tmp_path / "02_Portfolio" / "Exposicao.md").exists()


def test_command_limits_are_configurable(tmp_path):
    _snapshot_file(tmp_path)

    out = CliRunner().invoke(
        cli,
        ["portfolio-exposure", "--vault", str(tmp_path), "--limite-posicao", "0.9"],
    )

    assert out.exit_code == 0, out.output
    assert "posição · Posição" not in out.output


def test_command_reports_a_missing_snapshot(tmp_path):
    out = CliRunner().invoke(cli, ["portfolio-exposure", "--vault", str(tmp_path)])

    assert out.exit_code != 0
    assert "não encontrado" in out.output


def test_command_reports_a_snapshot_without_the_table(tmp_path):
    path = tmp_path / "02_Portfolio" / "Current.md"
    path.parent.mkdir(parents=True)
    path.write_text("sem tabela\n", encoding="utf-8")

    out = CliRunner().invoke(cli, ["portfolio-exposure", "--vault", str(tmp_path)])

    assert out.exit_code != 0
    assert "Não consegui ler o snapshot" in out.output
