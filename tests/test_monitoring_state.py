"""Testes de ``monitoring_state.py``: a camada que decide se um desvio é novidade.

Escopo desta etapa: persistência (``estado_monitoramento.json``), ``evaluate_run`` (pura) e o
arquivo de alerta. Nada aqui liga o job diário, o ``decide-portfolio`` nem
``rebalancing_alerts.py`` -- ver ``test_only_the_command_wires_monitoring_state_in``.
"""

from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

import pytest

from iip.portfolio.monitoring_event import build_monitoring_events
from iip.portfolio.monitoring_state import (
    CONTEXT_NOTICE,
    evaluate_run,
    load_state,
    save_state,
    write_alert_file,
)
from iip.portfolio.target_policy import (
    LineWeight,
    PolicyLine,
    Reconciliation,
    TargetPolicy,
)

TODAY = dt.date(2026, 9, 24)
TOMORROW = dt.date(2026, 9, 25)


def _line(**changes) -> PolicyLine:
    base = {
        "id": "X3",
        "name": "X3",
        "asset_class": "acao",
        "target_pct": 6.0,
        "tolerance_pp": 1.0,
        "min_pct": 3.0,
        "max_pct": 8.0,
        "status": "definido",
        "decided_on": "2026-09-20",
    }
    base.update(changes)
    return PolicyLine(**base)


def _policy(*lines: PolicyLine) -> TargetPolicy:
    return TargetPolicy(
        version="teste.1",
        origin="teste",
        lines=lines,
        sum_rule="referencias_individuais",
    )


def _events(*items: tuple[PolicyLine, float], today: dt.date = TODAY):
    lines = tuple(line for line, _ in items)
    policy = _policy(*lines)
    weights = tuple(
        LineWeight(line, value=weight * 1000, weight_pct=weight, present=(line.id,))
        for line, weight in items
    )
    rec = Reconciliation(100_000.0, weights, (), (), (), (), ())
    events = build_monitoring_events(policy, rec, today.isoformat())
    return events, policy.content_hash


# --- is_new: primeira entrada, permanência, saída, reentrada, mudança de tipo ----------------


def test_first_time_in_deviation_is_new():
    events, phash = _events((_line(), 7.5))  # fora_da_faixa

    run = evaluate_run(events, None, TODAY, phash)

    assert len(run.deviations) == 1
    tracked = run.deviations[0]
    assert tracked.is_new is True
    assert tracked.since == TODAY.isoformat()


def test_staying_in_the_same_deviation_is_not_new():
    events, phash = _events((_line(), 7.5))
    first = evaluate_run(events, None, TODAY, phash)

    second = evaluate_run(events, first.state, TOMORROW, phash)

    tracked = second.deviations[0]
    assert tracked.is_new is False
    assert tracked.since == TODAY.isoformat()  # preserva a data original


def test_leaving_the_deviation_removes_it_from_state():
    line = _line()
    deviated, phash = _events((line, 7.5))
    first = evaluate_run(deviated, None, TODAY, phash)

    back_in_band, _ = _events((line, 6.0), today=TOMORROW)
    second = evaluate_run(back_in_band, first.state, TOMORROW, phash)

    assert second.deviations == ()
    assert second.state["deviations"] == {}


def test_re_entering_the_same_deviation_is_new_again():
    line = _line()
    deviated, phash = _events((line, 7.5))
    first = evaluate_run(deviated, None, TODAY, phash)
    back_in_band, _ = _events((line, 6.0), today=TOMORROW)
    second = evaluate_run(back_in_band, first.state, TOMORROW, phash)

    deviated_again, _ = _events((line, 7.5), today=dt.date(2026, 9, 26))
    third = evaluate_run(deviated_again, second.state, dt.date(2026, 9, 26), phash)

    tracked = third.deviations[0]
    assert tracked.is_new is True
    assert tracked.since == "2026-09-26"


def test_changing_deviation_type_is_a_new_event():
    line = _line()
    fora_da_faixa, phash = _events((line, 7.5))  # acima_da_faixa
    first = evaluate_run(fora_da_faixa, None, TODAY, phash)

    acima_do_maximo, _ = _events((line, 8.5), today=TOMORROW)  # acima_do_maximo
    second = evaluate_run(acima_do_maximo, first.state, TOMORROW, phash)

    tracked = second.deviations[0]
    assert tracked.event.deviation_type == "acima_do_maximo"
    assert tracked.is_new is True
    assert tracked.since == TOMORROW.isoformat()


def test_two_runs_the_same_day_do_not_duplicate_the_alert():
    events, phash = _events((_line(), 7.5))
    first = evaluate_run(events, None, TODAY, phash)

    second = evaluate_run(events, first.state, TODAY, phash)

    assert len(first.notifiable) == 1
    assert len(second.notifiable) == 0  # já estava no estado da primeira rodada


def test_policy_hash_is_preserved_in_the_state():
    events, phash = _events((_line(), 7.5))

    run = evaluate_run(events, None, TODAY, phash)

    assert run.policy_hash == phash
    assert run.state["policy_hash"] == phash


def test_multiple_lines_in_deviation_are_all_tracked():
    a = _line(id="A", name="A")
    b = _line(id="B", name="B")
    events, phash = _events((a, 7.5), (b, 8.5))  # A fora_da_faixa, B acima_do_maximo

    run = evaluate_run(events, None, TODAY, phash)

    assert {t.event.line_id for t in run.deviations} == {"A", "B"}
    assert all(t.is_new for t in run.deviations)


def test_informative_lines_are_not_tracked_and_not_alerted():
    events, phash = _events((_line(), 6.0))  # na_faixa

    run = evaluate_run(events, None, TODAY, phash)

    assert run.deviations == ()
    assert run.notifiable == ()
    assert run.state["deviations"] == {}


# --- caso BBSE3 como cenário real: notifica uma vez, depois fica em silêncio ------------------


def test_the_bbse3_case_notifies_once_then_stays_silent_while_still_flagged():
    bbse3 = PolicyLine(
        id="BBSE3",
        name="BBSE3",
        asset_class="acao",
        target_pct=5.0,
        tolerance_pp=2.0,
        min_pct=3.0,
        max_pct=15.0,
        status="definido",
        decided_on="2026-01-02",
    )
    events, phash = _events((bbse3, 12.64))

    day1 = evaluate_run(events, None, TODAY, phash)
    day2 = evaluate_run(events, day1.state, TOMORROW, phash)

    assert len(day1.notifiable) == 1 and day1.notifiable[0].event.line_id == "BBSE3"
    assert day2.notifiable == ()  # mesmo desvio, sem novidade
    assert day2.deviations[0].since == TODAY.isoformat()  # "em desvio desde" preservado


# --- o arquivo de alerta: uma linha por novidade, ASCII simples, some sem novidade ---------


def test_alert_file_has_one_line_per_new_deviation_with_plain_ascii(tmp_path):
    events, phash = _events((_line(), 7.5))
    run = evaluate_run(events, None, TODAY, phash)
    path = tmp_path / "alerta.txt"

    lines = write_alert_file(path, run)

    assert len(lines) == 1
    assert "X3" in lines[0] and CONTEXT_NOTICE in lines[0]
    assert "→" not in lines[0] and "−" not in lines[0]
    assert path.read_text(encoding="utf-8").strip() == lines[0]


def test_alert_file_is_removed_when_there_is_nothing_new(tmp_path):
    events, phash = _events((_line(), 6.0))  # sem desvio
    run = evaluate_run(events, None, TODAY, phash)
    path = tmp_path / "alerta.txt"
    path.write_text("alerta antigo\n", encoding="utf-8")

    lines = write_alert_file(path, run)

    assert lines == ()
    assert not path.exists()


# --- o estado: persistência, primeira execução, arquivo ilegível ------------------------------


def test_load_state_returns_none_on_first_run(tmp_path):
    assert load_state(tmp_path) is None


def test_save_and_load_state_round_trips(tmp_path):
    events, phash = _events((_line(), 7.5))
    run = evaluate_run(events, None, TODAY, phash)

    save_state(tmp_path, run.state)
    loaded = load_state(tmp_path)

    assert loaded == run.state


def test_a_corrupted_state_file_raises_instead_of_silently_restarting(tmp_path):
    path = tmp_path / "02_Portfolio" / "estado_monitoramento.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="ilegível"):
        load_state(tmp_path)


# --- isolamento: só o comando importa monitoring_state -----------------------------------


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_only_the_command_wires_monitoring_state_in():
    """O job diário, o decide-portfolio e o rebalancing_alerts órfão continuam fora --
    só o comando manual `iip monitoring-events` consome esta camada de novidade."""
    users = {
        str(path).replace("\\", "/")
        for path in Path("src/iip").rglob("*.py")
        if any(n.startswith("iip.portfolio.monitoring_state") for n in _imports(path))
    }

    assert users == {"src/iip/cli/main.py"}
