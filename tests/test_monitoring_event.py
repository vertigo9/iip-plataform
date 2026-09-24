"""Testes do contrato de evento do monitoramento (``monitoring_event.py``).

Escopo desta etapa: só a camada de leitura estruturada (``MonitoringEvent`` +
``build_monitoring_events``). Nada aqui liga o monitoramento, chama o CLI, o job ou o
``decide-portfolio`` -- os testes cobrem exatamente o que o módulo faz: traduzir
``reconcile``/``read_weight`` num evento por linha, sem decidir nem executar.
"""

from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

import pytest

from iip.portfolio.monitoring_event import (
    AUTOMATIC_ACTION,
    SEVERITY_DEVIATION,
    SEVERITY_INFO,
    build_monitoring_events,
)
from iip.portfolio.target_policy import (
    STAGE_BUILDING,
    LineWeight,
    PolicyLine,
    Reconciliation,
    TargetPolicy,
)

GENERATED_AT = "2026-09-23T12:00:00"


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


def _policy(
    *lines: PolicyLine, sum_rule: str | None = "referencias_individuais"
) -> TargetPolicy:
    return TargetPolicy(
        version="teste.1", origin="teste", lines=lines, sum_rule=sum_rule
    )


def _rec(*items: tuple[PolicyLine, float]) -> Reconciliation:
    weights = tuple(
        LineWeight(line, value=weight * 1000, weight_pct=weight, present=(line.id,))
        for line, weight in items
    )
    return Reconciliation(
        total=100_000.0,
        weights=weights,
        uncovered=(),
        absent_lines=(),
        reopened=(),
        missing_members=(),
        new_members=(),
    )


def _single_event(line: PolicyLine, weight: float):
    policy = _policy(line)
    rec = _rec((line, weight))
    events = build_monitoring_events(policy, rec, GENERATED_AT)
    assert len(events) == 1
    return events[0]


# --- estados informativos: na_faixa e em_formacao não são desvio ---------------------------


def test_a_weight_inside_the_band_is_informative_na_faixa():
    event = _single_event(_line(), 6.0)

    assert event.state == "na_faixa"
    assert event.severity == SEVERITY_INFO
    assert event.deviation_type is None
    assert event.automatic_action == AUTOMATIC_ACTION


def test_a_building_position_below_the_band_is_informative_em_formacao():
    line = _line(stage=STAGE_BUILDING, completion_date="2027-06-30")

    event = _single_event(line, 1.5)

    assert event.state == "em_formacao"
    assert event.severity == SEVERITY_INFO
    assert event.deviation_type is None
    assert event.automatic_action == AUTOMATIC_ACTION


# --- estados de desvio: fora_da_faixa (nos dois sentidos), abaixo_do_minimo, acima_do_maximo


def test_above_the_band_but_within_the_max_is_a_deviation_acima_da_faixa():
    event = _single_event(_line(), 7.5)

    assert event.state == "fora_da_faixa"
    assert event.severity == SEVERITY_DEVIATION
    assert event.deviation_type == "acima_da_faixa"
    assert event.automatic_action == AUTOMATIC_ACTION


def test_below_the_band_but_within_the_min_is_a_deviation_abaixo_da_faixa():
    line = _line(target_pct=6.0, tolerance_pp=1.0, min_pct=3.0, max_pct=8.0)

    event = _single_event(line, 4.0)

    assert event.state == "fora_da_faixa"
    assert event.severity == SEVERITY_DEVIATION
    assert event.deviation_type == "abaixo_da_faixa"


def test_below_the_minimum_on_an_established_position_is_a_deviation():
    event = _single_event(_line(), 2.9)

    assert event.state == "abaixo_do_minimo"
    assert event.severity == SEVERITY_DEVIATION
    assert event.deviation_type == "abaixo_do_minimo"
    assert event.automatic_action == AUTOMATIC_ACTION


def test_above_the_maximum_is_a_deviation():
    event = _single_event(_line(), 8.1)

    assert event.state == "acima_do_maximo"
    assert event.severity == SEVERITY_DEVIATION
    assert event.deviation_type == "acima_do_maximo"
    assert event.automatic_action == AUTOMATIC_ACTION


# --- caso BBSE3: 12,64% vs faixa 3-7%, alvo 5%, tolerância 2 p.p., máx 15% -----------------


def test_the_bbse3_case_is_a_deviation_above_the_band_within_the_max():
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

    event = _single_event(bbse3, 12.64)

    assert event.current_weight_pct == 12.64
    assert event.target_pct == 5.0
    assert event.band_low == 3.0
    assert event.band_high == 7.0
    assert event.state == "fora_da_faixa"
    assert event.severity == SEVERITY_DEVIATION
    assert event.deviation_type == "acima_da_faixa"
    assert event.automatic_action == "nenhuma"


# --- caso RF-BANCARIA: 6,74% dentro da faixa 6-10% (reserva de liquidez) -------------------


def test_the_rf_bancaria_case_is_within_the_band():
    rf_bancaria = PolicyLine(
        id="RF-BANCARIA",
        name="Renda fixa bancária (CDBs)",
        asset_class="renda_fixa",
        kind="group",
        members=("RF-NUBANK-120CDI", "RF-MP-115CDI"),
        target_pct=8.0,
        tolerance_pp=2.0,
        min_pct=5.0,
        max_pct=12.0,
        status="definido",
        decided_on="2026-09-23",
        rationale="colchao de emergencia e liquidez imediata",
    )

    event = _single_event(rf_bancaria, 6.74)

    assert event.state == "na_faixa"
    assert event.severity == SEVERITY_INFO
    assert event.deviation_type is None
    assert event.band_low == 6.0
    assert event.band_high == 10.0


# --- cobertura de todas as linhas, ordem, e nenhum efeito colateral ------------------------


def test_one_event_is_produced_per_line_in_order():
    lines = tuple(
        _line(
            id=f"L{i}",
            name=f"L{i}",
            target_pct=5.0,
            tolerance_pp=1.0,
            min_pct=2.0,
            max_pct=9.0,
        )
        for i in range(36)
    )
    policy = _policy(*lines)
    rec = _rec(*((line, 5.0) for line in lines))

    events = build_monitoring_events(policy, rec, GENERATED_AT)

    assert len(events) == 36
    assert [event.line_id for event in events] == [line.id for line in lines]


def test_every_event_carries_the_current_policy_hash():
    lines = (
        _line(id="A", name="A"),
        _line(
            id="B", name="B", target_pct=4.0, tolerance_pp=1.0, min_pct=2.0, max_pct=6.0
        ),
    )
    policy = _policy(*lines)
    rec = _rec((lines[0], 6.0), (lines[1], 20.0))  # B em desvio (acima do máximo)

    events = build_monitoring_events(policy, rec, GENERATED_AT)

    assert all(event.policy_hash == policy.content_hash for event in events)
    # duas políticas com conteúdo diferente têm hashes diferentes -- o hash não é um valor fixo
    other = _policy(*lines, sum_rule="total_100")
    assert other.content_hash != policy.content_hash


def test_every_event_has_the_locked_automatic_action_of_none():
    lines = (
        _line(id="A", name="A"),  # na_faixa
        _line(
            id="B", name="B", stage=STAGE_BUILDING, completion_date="2027-01-01"
        ),  # em_formacao
        _line(id="C", name="C"),  # desvio
    )
    policy = _policy(*lines)
    rec = _rec((lines[0], 6.0), (lines[1], 1.0), (lines[2], 8.1))

    events = build_monitoring_events(policy, rec, GENERATED_AT)

    assert {event.automatic_action for event in events} == {"nenhuma"}


def test_generated_at_accepts_a_datetime_and_is_stored_as_iso_text():
    line = _line()
    policy = _policy(line)
    rec = _rec((line, 6.0))

    events = build_monitoring_events(policy, rec, dt.datetime(2026, 9, 23, 12, 0, 0))

    assert events[0].generated_at == "2026-09-23T12:00:00"


def test_building_events_is_pure_and_deterministic():
    line = _line()
    policy = _policy(line)
    rec = _rec((line, 6.0))

    first = build_monitoring_events(policy, rec, GENERATED_AT)
    second = build_monitoring_events(policy, rec, GENERATED_AT)

    assert first == second


# --- isolamento: nada além deste teste consome o módulo ainda -----------------------------


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_nothing_in_src_wires_the_monitoring_event_module_in_yet():
    """Etapa autorizada: só o módulo puro + seus testes. Nenhum CLI, job ou motor de decisão
    consome ``monitoring_event`` ainda -- isso é uma integração futura, separada, não
    autorizada nesta etapa."""
    users = {
        str(path).replace("\\", "/")
        for path in Path("src/iip").rglob("*.py")
        if any(n.startswith("iip.portfolio.monitoring_event") for n in _imports(path))
    }

    assert users == set()


def test_the_daily_job_does_not_run_the_monitoring_event_module():
    script = Path("executar_atualizacao_diaria.ps1").read_text(encoding="utf-8")

    assert "monitoring" not in script.lower()


@pytest.mark.parametrize(
    ("weight", "expected_state", "expected_severity"),
    [
        (2.9, "abaixo_do_minimo", SEVERITY_DEVIATION),
        (3.0, "fora_da_faixa", SEVERITY_DEVIATION),
        (5.0, "na_faixa", SEVERITY_INFO),
        (6.0, "na_faixa", SEVERITY_INFO),
        (7.0, "na_faixa", SEVERITY_INFO),
        (7.5, "fora_da_faixa", SEVERITY_DEVIATION),
        (8.0, "fora_da_faixa", SEVERITY_DEVIATION),
        (8.1, "acima_do_maximo", SEVERITY_DEVIATION),
    ],
)
def test_the_full_band_is_read_the_same_way_read_weight_reads_it(
    weight, expected_state, expected_severity
):
    event = _single_event(_line(), weight)

    assert event.state == expected_state
    assert event.severity == expected_severity
