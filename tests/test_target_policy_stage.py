import datetime as dt
import json
from dataclasses import replace
from pathlib import Path

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.obsidian.target_policy_report import render_policy_report
from iip.portfolio.target_policy import (
    STAGE_BUILDING,
    STAGE_ESTABLISHED,
    PolicyLine,
    TargetPolicy,
    _payload,
    build_initial_policy,
    load_policy,
    read_snapshot_rows,
    read_weight,
    reconcile,
    save_policy,
    validate,
)

TODAY = dt.date(2026, 9, 20)
HEADER = (
    "| ID | Ativo | Classe | Quantidade | PM | Preço atual | Valor | Peso | Peso alvo | "
    "Status |"
)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _snapshot(vault):
    lines = [HEADER, "|---|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for row_id, klass, value in (
        ("BBSE3", "acao", "R$ 90.000,00"),
        ("PASS3", "acao", "R$ 1.500,00"),
        ("LVBI11", "fii", "R$ 8.500,00"),
    ):
        lines.append(
            f"| {row_id} | {row_id} | {klass} |  |  |  | {value} | 0,00% |  | active |"
        )
    path = Path(vault) / "02_Portfolio" / "Current.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _policy(tmp_path):
    return build_initial_policy(
        read_snapshot_rows(_snapshot(tmp_path)), version="teste.1"
    )


def _line(**changes):
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


def _building(**changes):
    return _line(
        stage=STAGE_BUILDING,
        completion_date="2027-06-30",
        rationale="posição em formação",
        **changes,
    )


def _with(policy, index, line):
    return replace(
        policy, lines=(*policy.lines[:index], line, *policy.lines[index + 1 :])
    )


# --- the stage exists, defaults to established and keeps old policies valid ------------------


def test_every_line_starts_established_with_no_completion(tmp_path):
    policy = _policy(tmp_path)

    assert {ln.stage for ln in policy.lines} == {STAGE_ESTABLISHED}
    assert all(
        ln.completion_date is None and ln.completion_condition == ""
        for ln in policy.lines
    )


def test_the_file_shows_the_stage_fields_but_the_hash_ignores_the_defaults(tmp_path):
    policy = _policy(tmp_path)

    on_file = _payload(policy)["lines"][0]
    in_hash = _payload(policy, hash_view=True)["lines"][0]

    assert {"stage", "completion_date", "completion_condition"} <= set(on_file)
    assert not {"stage", "completion_date", "completion_condition"} & set(in_hash)


def test_a_policy_saved_before_the_stage_existed_loads_with_the_same_hash(tmp_path):
    policy = _policy(tmp_path)
    save_policy(tmp_path, policy)
    path = tmp_path / "02_Portfolio" / "Politica_Pesos_Alvo.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for line in payload["lines"]:  # o formato antigo não tinha os três campos
        for key in ("stage", "completion_date", "completion_condition"):
            del line[key]
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_policy(tmp_path)

    assert loaded.content_hash == policy.content_hash
    assert {ln.stage for ln in loaded.lines} == {STAGE_ESTABLISHED}


def test_a_building_line_survives_save_and_load_and_changes_the_hash(tmp_path):
    policy = _policy(tmp_path)
    building = _with(policy, 1, replace(_building(), id="PASS3", name="PASS3"))
    save_policy(tmp_path, building)

    loaded = load_policy(tmp_path)

    line = loaded.line("PASS3")
    assert line.stage == STAGE_BUILDING and line.completion_date == "2027-06-30"
    assert loaded.content_hash == building.content_hash != policy.content_hash


# --- validation ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"stage": "quase"}, "stage 'quase'"),
        (
            {"stage": STAGE_ESTABLISHED, "completion_date": "2027-01-01"},
            "só valem para",
        ),
        (
            {"stage": STAGE_ESTABLISHED, "completion_condition": "3 aportes"},
            "só valem para",
        ),
        ({"stage": STAGE_BUILDING}, "exige a previsão de conclusão"),
        ({"stage": STAGE_BUILDING, "completion_condition": "   "}, "exige a previsão"),
        (
            {"stage": STAGE_BUILDING, "completion_date": "em breve"},
            "completion_date 'em breve' não é AAAA-MM-DD",
        ),
        (
            {"stage": STAGE_BUILDING, "completion_date": "2026-09-01"},
            "anterior à data da decisão",
        ),
    ],
)
def test_a_wrong_stage_is_an_explicit_error(changes, reason):
    policy = TargetPolicy("v", "o", (_line(**changes),))

    with pytest.raises(ValueError, match=reason):
        validate(policy)


@pytest.mark.parametrize(
    "completion",
    [
        {"completion_date": "2027-06-30"},
        {"completion_condition": "após três aportes"},
        {"completion_date": "2027-06-30", "completion_condition": "após três aportes"},
    ],
)
def test_a_building_line_needs_a_date_or_a_condition_or_both(completion):
    validate(TargetPolicy("v", "o", (_line(stage=STAGE_BUILDING, **completion),)))


def test_a_pending_line_that_declares_construction_still_needs_the_completion():
    pending = PolicyLine("X3", "X3", "acao", stage=STAGE_BUILDING)

    with pytest.raises(ValueError, match="exige a previsão de conclusão"):
        validate(TargetPolicy("v", "o", (pending,)))


def test_an_inactive_building_line_needs_no_completion():
    inactive = PolicyLine("X3", "X3", "acao", status="inativo", stage=STAGE_BUILDING)

    validate(TargetPolicy("v", "o", (inactive,)))


def test_a_building_line_keeps_the_same_limit_rules_as_any_other():
    for changes, reason in (
        ({"min_pct": 7.0}, "acima do mínimo|abaixo do mínimo"),
        ({"max_pct": 5.0}, "acima do máximo"),
        ({"tolerance_pp": 4.0}, "fica abaixo do mínimo"),
    ):
        with pytest.raises(ValueError, match=reason):
            validate(TargetPolicy("v", "o", (_building(**changes),)))


def test_a_building_line_has_the_final_numbers_the_definido_status_asks_for():
    incomplete = _building(tolerance_pp=None)

    with pytest.raises(ValueError, match="definido exige alvo, tolerância"):
        validate(TargetPolicy("v", "o", (incomplete,)))


def test_the_file_rejects_an_unknown_stage_value(tmp_path):
    save_policy(tmp_path, _policy(tmp_path))
    path = tmp_path / "02_Portfolio" / "Politica_Pesos_Alvo.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["lines"][0]["stage"] = "em_obras"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="stage 'em_obras'") as error:
        load_policy(tmp_path)

    assert str(path) in str(error.value)


# --- reading the current weight: "em formação" is not a deviation -------------------------


def _read(line, weight):
    return read_weight(line, weight)


def test_the_users_example_a_small_building_position_is_in_formation_not_a_deviation():
    # alvo final 6%, mínimo final 3%, máximo 8%, hoje em 1,5%
    line = _building(target_pct=6.0, tolerance_pp=1.0, min_pct=3.0, max_pct=8.0)

    reading = _read(line, 1.5)

    assert reading.state == "em_formacao"
    assert reading.label == "em formação: abaixo do mínimo final"
    assert reading.is_deviation is False


def test_the_same_weight_on_an_established_position_is_a_deviation():
    line = _line(target_pct=6.0, tolerance_pp=1.0, min_pct=3.0, max_pct=8.0)

    reading = _read(line, 1.5)

    assert reading.state == "abaixo_do_minimo" and reading.is_deviation is True


@pytest.mark.parametrize(
    ("weight", "state"),
    [
        (2.9, "abaixo_do_minimo"),
        (3.0, "fora_da_faixa"),  # no mínimo: dentro dos limites, mas abaixo da faixa
        (4.9, "fora_da_faixa"),
        (5.0, "na_faixa"),  # borda inferior da faixa (6 - 1)
        (6.0, "na_faixa"),
        (7.0, "na_faixa"),  # borda superior (6 + 1)
        (7.5, "fora_da_faixa"),
        (8.0, "fora_da_faixa"),  # no máximo: ainda dentro dos limites
        (8.1, "acima_do_maximo"),
    ],
)
def test_an_established_position_is_read_against_the_band_and_the_limits(weight, state):
    line = _line(target_pct=6.0, tolerance_pp=1.0, min_pct=3.0, max_pct=8.0)

    assert _read(line, weight).state == state


@pytest.mark.parametrize(
    ("weight", "state", "deviation"),
    [
        (0.5, "em_formacao", False),
        (2.9, "em_formacao", False),
        (3.5, "em_formacao", False),  # acima do mínimo final, ainda abaixo da faixa
        (5.0, "na_faixa", False),
        (6.0, "na_faixa", False),
        (7.5, "fora_da_faixa", True),  # passar da faixa continua sendo desvio
        (8.5, "acima_do_maximo", True),
    ],
)
def test_a_building_position_only_forgives_being_below_the_band(
    weight, state, deviation
):
    line = _building(target_pct=6.0, tolerance_pp=1.0, min_pct=3.0, max_pct=8.0)

    reading = _read(line, weight)

    assert (reading.state, reading.is_deviation) == (state, deviation)


def test_the_label_says_below_the_band_when_it_is_above_the_final_minimum():
    line = _building()

    assert _read(line, 3.5).label == "em formação: abaixo da faixa"
    assert _read(line, 2.0).label == "em formação: abaixo do mínimo final"


def test_the_tolerance_moves_the_band_but_never_the_limits():
    narrow = _line(target_pct=6.0, tolerance_pp=0.5, min_pct=3.0, max_pct=8.0)
    wide = _line(target_pct=6.0, tolerance_pp=2.0, min_pct=3.0, max_pct=8.0)

    assert _read(narrow, 5.0).state == "fora_da_faixa"
    assert _read(wide, 5.0).state == "na_faixa"
    for line in (narrow, wide):  # abaixo do mínimo e acima do máximo não dependem dela
        assert _read(line, 2.5).state == "abaixo_do_minimo"
        assert _read(line, 8.5).state == "acima_do_maximo"


def test_lines_without_a_band_or_inactive_have_nothing_to_read():
    pending = PolicyLine(
        "X3", "X3", "acao", min_pct=3.0, max_pct=8.0
    )  # só mínimo e máximo
    inactive = replace(_line(), status="inativo")

    assert (
        _read(pending, 1.0).state == "sem_faixa"
        and not _read(pending, 1.0).is_deviation
    )
    assert (
        _read(inactive, 1.0).state == "inativa"
        and not _read(inactive, 1.0).is_deviation
    )


# --- the note -------------------------------------------------------------------------------


def _report(policy, tmp_path):
    return render_policy_report(
        policy, reconcile(policy, read_snapshot_rows(_snapshot(tmp_path))), TODAY
    )


def _fm(text):
    out = {}
    for line in text.split("---")[1].strip().splitlines():
        key, _, value = line.partition(": ")
        try:
            out[key] = json.loads(value)
        except json.JSONDecodeError:
            out[key] = value
    return out


def test_the_note_shows_the_stage_and_the_reading_and_bolds_only_real_deviations(
    tmp_path,
):
    policy = _policy(tmp_path)
    policy = _with(
        policy, 1, replace(_building(), id="PASS3", name="PASS3")
    )  # 1,5% de 100
    policy = _with(
        policy, 0, replace(_line(), id="BBSE3", name="BBSE3")
    )  # 90% > máximo

    text = _report(policy, tmp_path)

    assert "| Estágio | Leitura do peso atual |" in text
    assert "| em construção | em formação: abaixo do mínimo final |" in text
    assert "| estabelecida | **acima do máximo** |" in text
    assert "**em formação" not in text  # "em formação" nunca é destacado como desvio
    assert "| pendente | estabelecida | — |" in text  # linha sem faixa: nada a ler


def test_the_note_lists_the_building_positions_with_their_completion(tmp_path):
    policy = _with(_policy(tmp_path), 1, replace(_building(), id="PASS3", name="PASS3"))

    text = _report(policy, tmp_path)

    assert _fm(text)["linhas_em_construcao"] == ["PASS3"]
    assert "## Posições em construção" in text
    assert (
        "`PASS3`: peso atual 1,50%, alvo final 6,00% (mín. 3,00%, máx. 8,00%)" in text
    )
    assert "conclusão prevista: até 2027-06-30" in text
    assert "Justificativa: posição em formação" in text


def test_the_note_says_when_no_position_is_being_built(tmp_path):
    text = _report(_policy(tmp_path), tmp_path)

    assert _fm(text)["linhas_em_construcao"] == []
    assert "Nenhuma posição em construção." in text


def test_the_note_states_that_the_reading_is_informative_and_monitoring_stays_off(
    tmp_path,
):
    text = _report(_policy(tmp_path), tmp_path)

    assert "É informativa: o monitoramento continua desligado" in text
    assert "nada é sinalizado nem executado" in text
    assert "estar abaixo da faixa é" in text and "não desvio" in text
    assert "a tolerância segue sendo só a margem de atenção" in text


# --- CLI -----------------------------------------------------------------------------------


def _flat(text):
    return "".join(text.split())


def test_the_command_accepts_a_building_line_and_writes_the_note(tmp_path):
    _snapshot(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["target-policy", "--vault", str(tmp_path), "--init"])
    path = tmp_path / "02_Portfolio" / "Politica_Pesos_Alvo.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    line = next(item for item in payload["lines"] if item["id"] == "PASS3")
    line.update(
        target_pct=6,
        tolerance_pp=1,
        min_pct=3,
        max_pct=8,
        status="definido",
        decided_on="2026-09-20",
        stage="em_construcao",
        completion_date="2027-06-30",
    )
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = runner.invoke(cli, ["target-policy", "--vault", str(tmp_path), "--report"])

    assert result.exit_code == 0, result.output
    note = (tmp_path / "02_Portfolio" / "Politica_Pesos_Alvo.md").read_text(
        encoding="utf-8"
    )
    assert "em formação: abaixo do mínimo final" in note


def test_the_command_stops_with_the_reason_on_a_building_line_without_completion(
    tmp_path,
):
    _snapshot(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["target-policy", "--vault", str(tmp_path), "--init"])
    path = tmp_path / "02_Portfolio" / "Politica_Pesos_Alvo.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["lines"][0]["stage"] = "em_construcao"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = runner.invoke(cli, ["target-policy", "--vault", str(tmp_path)])

    assert result.exit_code == 1
    assert "exigeaprevisãodeconclusão" in _flat(result.output)


# --- still a policy layer: nothing here decides, contributes or rebalances ----------------


def test_reading_a_weight_never_changes_the_line_or_the_policy(tmp_path):
    policy = _policy(tmp_path)
    line = _building()
    before = (line, policy.content_hash)

    _read(line, 0.5)

    assert (line, policy.content_hash) == before


def test_the_daily_job_still_does_not_run_the_policy():
    script = Path("executar_atualizacao_diaria.ps1").read_text(encoding="utf-8")

    assert "target-policy" not in script
