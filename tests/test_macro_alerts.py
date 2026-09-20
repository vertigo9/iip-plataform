import ast
import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.macro.alerts import (
    CONTEXT_NOTICE,
    DEFAULT_RULES,
    AlertRule,
    DataQuality,
    RuleSet,
    alert_lines,
    load_rules,
    load_state,
    ntnb_impact,
    run_alerts,
    save_rules,
    save_state,
    validate,
    write_alert_file,
)
from iip.macro.store import MacroStore
from iip.obsidian import dashboard as dash
from iip.obsidian.macro_alerts_report import render_alerts_report, write_alerts_report
from iip.portfolio.valuation_inputs import BaseRate, PositionInputs, ValuationInputs

TODAY = date(2026, 9, 20)
NTNB = next(r for r in DEFAULT_RULES.rules if r.id == "ntnb_real_30d")
IPCA = next(r for r in DEFAULT_RULES.rules if r.id == "ipca_12m_acima")
SELIC = next(r for r in DEFAULT_RULES.rules if r.id == "selic_meta_mudou")
INADIMPLENCIA = next(r for r in DEFAULT_RULES.rules if r.id == "inadimplencia_12m")


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _rules(*rules, **extra):
    return RuleSet("teste.1", "teste", tuple(rules), **extra)


def _days(start, end):
    day = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while day <= stop:
        yield day.isoformat()
        day += timedelta(days=1)


def _daily(store, indicator, spans, *, collected="2026-09-18"):
    """``spans``: (início, fim, valor) inclusivos, um ponto por dia."""
    points = tuple(
        (day, value, False) for start, end, value in spans for day in _days(start, end)
    )
    return store.ingest(indicator, points, collected_at=collected)


def _monthly(store, indicator, points, *, collected="2026-09-18"):
    return store.ingest(
        indicator,
        tuple((ref, value, False) for ref, value in points),
        collected_at=collected,
    )


def _ntnb(store, *tail, collected="2026-09-18"):
    """A taxa em 7,00 até 09/09 e o resto em ``tail`` (início, fim, valor)."""
    _daily(
        store,
        "ntnb_longa_real",
        [("2026-06-01", "2026-09-09", 7.00), *tail],
        collected=collected,
    )


def _new_economic(run):
    return [a for a in run.new_alerts if a.category == "economico"]


def _run(store, state=None, today=TODAY, rules=None, inputs=None):
    return run_alerts(store, rules or _rules(NTNB), state, today, inputs=inputs)


# --- rules file: validation, hash, no silent fallback --------------------------------------


def test_the_default_rules_are_valid_and_survive_a_save_and_load(tmp_path):
    validate(DEFAULT_RULES)

    save_rules(tmp_path, DEFAULT_RULES)
    loaded = load_rules(tmp_path)

    assert loaded.content_hash == DEFAULT_RULES.content_hash
    assert [r.id for r in loaded.rules] == [r.id for r in DEFAULT_RULES.rules]
    assert loaded.rearm_fraction == 0.2


def test_no_rules_file_reads_as_none(tmp_path):
    assert load_rules(tmp_path) is None


def test_the_hash_changes_with_a_threshold_and_ignores_the_description():
    other = replace(NTNB, threshold=0.5)
    described = replace(NTNB, description="outra descrição")

    assert _rules(NTNB).content_hash != _rules(other).content_hash
    assert _rules(NTNB).content_hash == _rules(described).content_hash


def _write_rules(tmp_path, mutate):
    save_rules(tmp_path, DEFAULT_RULES)
    path = tmp_path / "07_Research" / "Macro" / "alertas_macro.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _first_rule(payload, **changes):
    payload["rules"][0].update(changes)


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda p: _first_rule(p, kind="inventada"), "tipo desconhecido"),
        (lambda p: _first_rule(p, indicator="nao_existe"), "fora do catálogo"),
        (lambda p: _first_rule(p, severidade="x"), "chave desconhecida"),
        (lambda p: _first_rule(p, severity="critico"), "severidade"),
        (lambda p: _first_rule(p, threshold=-0.3), "positivo"),
        (lambda p: _first_rule(p, threshold=None), "threshold"),
        (lambda p: _first_rule(p, unit="pct", threshold=500), "acima de 100"),
        (lambda p: _first_rule(p, window_days=0), "window_days"),
        (lambda p: _first_rule(p, confirmations=0), "confirmations"),
        (lambda p: _first_rule(p, confirmations=True), "confirmations"),
        (lambda p: _first_rule(p, message="valor {nao_existe}"), "campo desconhecido"),
        (lambda p: _first_rule(p, message="chave {aberta"), "mensagem mal formada"),
        (lambda p: _first_rule(p, impact="outro"), "impact desconhecido"),
        (lambda p: p.update(rearm_fraction=1.5), "rearm_fraction"),
        (lambda p: p.update(surpresa=1), "chave desconhecida na raiz"),
        (lambda p: p.update(data_quality={"stale": "sim"}), "true ou false"),
        (lambda p: p.update(data_quality={"outro": True}), "data_quality aceita"),
        (lambda p: p.update(rules=[]), "vazio"),
        (lambda p: p["rules"].append(dict(p["rules"][0])), "id repetido"),
    ],
)
def test_a_wrong_rules_file_is_an_explicit_error_never_a_silent_default(
    tmp_path, mutate, reason
):
    path = _write_rules(tmp_path, mutate)

    with pytest.raises(ValueError, match=reason) as error:
        load_rules(tmp_path)

    assert str(path) in str(error.value)


def test_a_rules_file_that_is_not_json_is_an_explicit_error(tmp_path):
    path = _write_rules(tmp_path, lambda p: None)
    path.write_text("{isto não é json", encoding="utf-8")

    with pytest.raises(ValueError, match="não é um JSON válido"):
        load_rules(tmp_path)


@pytest.mark.parametrize(
    ("rule", "reason"),
    [
        (
            AlertRule("x", "selic_mes", "level_above", "atencao", "m", threshold=1.0),
            "acumula no mês",
        ),
        (
            AlertRule("x", "ibc_br", "window_change", "atencao", "m", 1.0, "pct", 30),
            "só vale para séries diárias",
        ),
        (
            AlertRule("x", "usd_venda", "yoy_change", "atencao", "m", 1.0, "pp"),
            "compara 12 meses em 'pct'",
        ),
        (
            AlertRule("x", "selic_meta", "level_change", "atencao", "m", threshold=1.0),
            "level_change não usa",
        ),
        (
            AlertRule(
                "x",
                "ipca_12m",
                "level_above",
                "atencao",
                "m",
                threshold=4.0,
                direction="up",
            ),
            "direction só vale",
        ),
        (
            AlertRule(
                "x",
                "usd_venda",
                "window_change",
                "atencao",
                "m",
                5.0,
                "pct",
                30,
                impact="ntnb_valuation",
            ),
            "impact só vale",
        ),
    ],
)
def test_a_rule_that_does_not_fit_its_indicator_is_rejected(rule, reason):
    with pytest.raises(ValueError, match=reason):
        validate(_rules(rule))


def test_the_context_notice_closes_every_message_even_if_the_template_omits_it(
    tmp_path,
):
    store = MacroStore(tmp_path)
    _ntnb(store, ("2026-09-10", "2026-09-18", 7.40))

    alert = _run(store).active[0]

    assert alert.message.endswith(CONTEXT_NOTICE)
    assert CONTEXT_NOTICE not in NTNB.message


# --- confirmation: two distinct valid observations, not two job runs -----------------------


def test_a_window_move_confirmed_by_two_distinct_observations_fires(tmp_path):
    store = MacroStore(tmp_path)
    _ntnb(store, ("2026-09-10", "2026-09-18", 7.40))

    run = _run(store)

    [alert] = run.active
    assert alert.severity == "atencao" and alert.is_new and alert.notifies
    assert alert.trace["competencias_confirmadas"] == ["2026-09-17", "2026-09-18"]
    assert "subiu +0,40 p.p. em 30 dias" in alert.message
    assert "de 7,00% em 19/08/2026 para 7,40% em 18/09/2026" in alert.message


def test_one_breaching_observation_is_not_confirmed_even_after_two_job_runs(tmp_path):
    store = MacroStore(tmp_path)
    _ntnb(store, ("2026-09-18", "2026-09-18", 7.40))

    first = _run(store)
    second = _run(store, first.state)

    assert first.active == () and second.active == ()
    assert first.evaluations[0].status == "sem_alerta"
    assert second.new_alerts == ()


def test_running_the_job_again_on_the_same_data_creates_no_new_alert_or_notification(
    tmp_path,
):
    store = MacroStore(tmp_path)
    _ntnb(store, ("2026-09-10", "2026-09-18", 7.40))

    first = _run(store)
    second = _run(store, first.state)
    third = _run(store, second.state)

    assert len(_new_economic(first)) == 1 and len(first.notifiable) == 1
    assert _new_economic(second) == [] and second.notifiable == ()
    assert [a.key for a in second.active] == [
        "ntnb_real_30d"
    ]  # segue ativo, sem reavisar
    assert _new_economic(third) == [] and third.state == second.state


def test_collecting_the_same_values_again_does_not_add_observations(tmp_path):
    store = MacroStore(tmp_path)
    _ntnb(store, ("2026-09-10", "2026-09-18", 7.40))

    again = _daily(
        store,
        "ntnb_longa_real",
        [("2026-09-10", "2026-09-18", 7.40)],
        collected="2026-09-19",
    )

    assert again.new == 0 and again.revised == 0


def test_a_series_shorter_than_the_window_is_insufficient_not_a_zero(tmp_path):
    store = MacroStore(tmp_path)
    _daily(store, "ntnb_longa_real", [("2026-09-10", "2026-09-18", 7.40)])

    run = _run(store)

    assert run.evaluations[0].status == "insuficiente" and run.active == ()


def test_the_boundary_value_counts_despite_floating_point_error(tmp_path):
    store = MacroStore(tmp_path)
    _ntnb(store, ("2026-09-10", "2026-09-18", 7.30))  # 7,30 - 7,00 = 0,3000000000000007

    assert (
        _run(store).active
        and not _run(store, rules=_rules(replace(NTNB, threshold=0.31))).active
    )


# --- direction, rearm ----------------------------------------------------------------------


def test_the_rearm_needs_the_measure_to_recede_by_twenty_percent_of_the_threshold(
    tmp_path,
):
    store = MacroStore(tmp_path)
    _ntnb(store, ("2026-09-10", "2026-09-18", 7.40))
    fired = _run(store)
    assert [a.is_new for a in fired.active] == [True]

    # +0,28: abaixo do limiar (0,30) mas acima de 0,24 -> ainda não rearmou
    _daily(store, "ntnb_longa_real", [("2026-09-19", "2026-09-20", 7.28)])
    dead_band = _run(store, fired.state, date(2026, 9, 21))
    assert dead_band.active == () and [w.rule_id for w in dead_band.watching] == [
        "ntnb_real_30d"
    ]
    assert dead_band.state["rules"]["ntnb_real_30d"]["latched"] is True

    # volta a passar do limiar sem ter rearmado: continua ativo, mas não é novo
    _daily(store, "ntnb_longa_real", [("2026-09-21", "2026-09-22", 7.40)])
    again = _run(store, dead_band.state, date(2026, 9, 23))
    assert [a.is_new for a in again.active] == [False] and again.notifiable == ()

    # recua para +0,20 (dentro de 0,24): rearma
    _daily(store, "ntnb_longa_real", [("2026-09-23", "2026-09-23", 7.20)])
    rearmed = _run(store, again.state, date(2026, 9, 24))
    assert rearmed.active == () and rearmed.watching == ()
    assert rearmed.state["rules"]["ntnb_real_30d"]["latched"] is False

    # agora um novo movimento é um alerta novo
    _daily(store, "ntnb_longa_real", [("2026-09-24", "2026-09-25", 7.40)])
    fresh = _run(store, rearmed.state, date(2026, 9, 26))
    assert [a.is_new for a in fresh.active] == [True] and fresh.notifiable


def test_a_two_sided_limit_treats_the_opposite_side_as_a_new_alert(tmp_path):
    store = MacroStore(tmp_path)
    _ntnb(store, ("2026-09-10", "2026-09-18", 6.60))
    latched_up = {
        "rules": {
            "ntnb_real_30d": {"latched": True, "direction": "up", "since": "2026-09-01"}
        }
    }

    run = _run(store, latched_up)

    [alert] = run.active
    assert alert.is_new and "caiu -0,40 p.p." in alert.message
    assert run.state["rules"]["ntnb_real_30d"]["direction"] == "down"


def test_an_up_only_rule_ignores_a_fall_of_the_same_size(tmp_path):
    store = MacroStore(tmp_path)
    _monthly(
        store,
        "inadimplencia_total",
        [("2025-06", 5.0), ("2025-07", 5.0), ("2026-06", 3.9), ("2026-07", 3.9)],
    )

    run = _run(store, rules=_rules(INADIMPLENCIA))

    assert run.evaluations[0].latest.measure == pytest.approx(-1.1)
    assert run.active == ()


def test_a_level_rule_uses_a_strict_limit_and_a_wide_rearm_band(tmp_path):
    store = MacroStore(tmp_path)
    _monthly(store, "ipca_12m", [("2026-06", 4.3), ("2026-07", 4.4), ("2026-08", 4.5)])
    assert _run(store, rules=_rules(IPCA)).active == ()  # 4,5 não é > 4,5

    _monthly(store, "ipca_12m", [("2026-08", 4.6)], collected="2026-09-19")
    fired = _run(store, rules=_rules(IPCA))
    [alert] = fired.active
    assert alert.message == (
        "IPCA em 12 meses (4,60% em 2026-08) acima do limiar de monitoramento "
        f"configurado (4,50%). {CONTEXT_NOTICE}"
    )

    _monthly(store, "ipca_12m", [("2026-09", 4.4)])
    below = _run(store, fired.state, rules=_rules(IPCA))
    assert below.active == () and [w.rule_id for w in below.watching] == [
        "ipca_12m_acima"
    ]

    _monthly(store, "ipca_12m", [("2026-10", 4.7)])
    back = _run(store, below.state, date(2026, 10, 20), rules=_rules(IPCA))
    assert [a.is_new for a in back.active] == [False]

    _monthly(store, "ipca_12m", [("2026-11", 3.5)])
    rearmed = _run(store, back.state, date(2026, 11, 20), rules=_rules(IPCA))
    assert rearmed.state["rules"]["ipca_12m_acima"]["latched"] is False


def test_a_twelve_month_change_at_the_threshold_fires(tmp_path):
    store = MacroStore(tmp_path)
    _monthly(store, "inadimplencia_total", [("2025-07", 3.96), ("2026-07", 4.96)])

    run = _run(store, rules=_rules(INADIMPLENCIA))

    [alert] = run.active
    assert alert.severity == "informativo" and not alert.notifies
    assert "+1,00 p.p. sobre 12 meses antes" in alert.message


# --- events: level change ------------------------------------------------------------------


def _selic(store, *spans, collected="2026-09-18"):
    _daily(store, "selic_meta", list(spans), collected=collected)


def test_a_level_change_is_one_event_emitted_once_and_retired_after_the_window(
    tmp_path,
):
    store = MacroStore(tmp_path)
    _selic(
        store, ("2026-08-01", "2026-09-16", 14.0), ("2026-09-17", "2026-09-20", 13.75)
    )

    first = _run(store, rules=_rules(SELIC))
    [alert] = first.active
    assert alert.is_new and alert.notifies and alert.reference == "2026-09-17"
    assert alert.message.startswith(
        "Meta Selic alterada de 14,00% para 13,75% ao ano (a partir de 17/09/2026)."
    )

    same_day = _run(store, first.state, rules=_rules(SELIC))
    later = _run(store, same_day.state, date(2026, 9, 25), rules=_rules(SELIC))
    assert same_day.new_alerts == () and later.new_alerts == ()
    assert [a.key for a in later.active] == ["selic_meta_mudou"]

    _selic(store, ("2026-09-21", "2026-10-04", 13.75))
    retired = _run(store, later.state, date(2026, 10, 5), rules=_rules(SELIC))
    assert retired.active == ()  # 18 dias > retain_days (14)

    _selic(store, ("2026-10-05", "2026-10-06", 13.50))
    second = _run(store, retired.state, date(2026, 10, 7), rules=_rules(SELIC))
    assert [a.is_new for a in second.active] == [True]
    assert second.active[0].trace["nivel_anterior"] == 13.75
    assert second.active[0].trace["nivel_novo"] == 13.5


def test_a_series_without_a_level_change_raises_no_event(tmp_path):
    store = MacroStore(tmp_path)
    _selic(store, ("2026-08-01", "2026-09-20", 14.0))

    run = _run(store, rules=_rules(SELIC))

    assert run.active == () and run.evaluations[0].status == "sem_alerta"


# --- a revision of a competência is not a new one ------------------------------------------


def test_an_event_that_exists_only_because_of_a_revision_is_flagged_and_not_notified(
    tmp_path,
):
    store = MacroStore(tmp_path)
    _selic(store, ("2026-09-10", "2026-09-17", 14.0), collected="2026-09-18")
    _selic(store, ("2026-09-18", "2026-09-19", 13.75), collected="2026-09-19")
    # a fonte corrige 17/09 para 13,75: agora o "evento" aparece um dia antes
    _selic(store, ("2026-09-17", "2026-09-17", 13.75), collected="2026-09-20")

    run = _run(store, rules=_rules(SELIC))

    [alert] = run.active
    assert alert.by_revision and not alert.notifies
    assert alert_lines(run) == ()
    assert "por revisão" in render_alerts_report(run)


def test_a_level_alert_that_only_exists_after_a_revision_is_flagged(tmp_path):
    store = MacroStore(tmp_path)
    _monthly(store, "ipca_12m", [("2026-08", 4.4)], collected="2026-09-10")
    _monthly(store, "ipca_12m", [("2026-08", 4.6)], collected="2026-09-19")

    run = _run(store, rules=_rules(IPCA))

    [alert] = run.active
    assert alert.by_revision and not alert.notifies
    assert run.state["rules"]["ipca_12m_acima"]["latched"] is True  # não reavisa depois


def test_a_breach_present_in_the_first_collected_values_is_not_a_revision(tmp_path):
    store = MacroStore(tmp_path)
    _monthly(store, "ipca_12m", [("2026-08", 4.6)], collected="2026-09-10")
    _monthly(store, "ipca_12m", [("2026-08", 4.7)], collected="2026-09-19")

    [alert] = _run(store, rules=_rules(IPCA)).active

    assert not alert.by_revision and alert.notifies


# --- data quality: separate from the economic alerts --------------------------------------


def test_stale_data_does_not_fire_an_economic_alert_and_is_reported_as_data(tmp_path):
    store = MacroStore(tmp_path)
    _daily(
        store,
        "usd_venda",
        [("2026-06-01", "2026-08-01", 5.0), ("2026-08-02", "2026-08-10", 5.6)],
    )
    usd = next(r for r in DEFAULT_RULES.rules if r.id == "usd_30d")

    run = _run(store, rules=_rules(usd))

    assert run.evaluations[0].status == "defasado" and run.active == ()
    [warning] = [a for a in run.data_alerts if a.indicator == "usd_venda"]
    assert warning.category == "dado" and warning.severity == "dado"
    assert warning.key == "defasado:usd_venda" and "atrasado" in warning.message
    assert not warning.notifies and run.notifiable == ()


def test_every_missing_indicator_is_a_data_notice_and_nothing_crashes(tmp_path):
    run = _run(MacroStore(tmp_path), rules=DEFAULT_RULES)

    assert run.active == ()
    assert {e.status for e in run.evaluations} == {"sem_dados"}
    assert {a.key.split(":")[0] for a in run.data_alerts} == {"sem_dados"}
    assert all("sem dados guardados" in a.message for a in run.data_alerts)


def test_diverging_sources_are_a_data_notice_with_the_reason(tmp_path):
    store = MacroStore(tmp_path)
    _monthly(store, "ipca_mensal", [("2026-07", 0.07), ("2026-08", -0.32)])
    _monthly(store, "ipca_mensal_ibge", [("2026-07", 0.07), ("2026-08", 0.30)])

    run = _run(store)

    [notice] = [a for a in run.data_alerts if a.key.startswith("divergencia:")]
    assert (
        "Fontes divergem" in notice.message and notice.trace["motivo"] == "divergencia"
    )


def test_data_notices_can_be_switched_off_per_reason_and_are_tracked_by_state(tmp_path):
    store = MacroStore(tmp_path)
    quiet = _rules(NTNB, data_quality=DataQuality(False, False, False))

    assert _run(store, rules=quiet).data_alerts == ()

    first = _run(store)
    second = _run(store, first.state)
    assert all(a.is_new for a in first.data_alerts)
    assert not any(a.is_new for a in second.data_alerts)
    assert {a.since for a in second.data_alerts} == {TODAY.isoformat()}


# --- traceability --------------------------------------------------------------------------


def test_the_alert_carries_the_rule_the_window_the_compared_values_and_the_version(
    tmp_path,
):
    store = MacroStore(tmp_path)
    _ntnb(store, ("2026-09-10", "2026-09-18", 7.40))

    [alert] = _run(store).active

    trace = alert.trace
    assert trace["regra"] == "ntnb_real_30d" and trace["indicador"] == "ntnb_longa_real"
    assert trace["versao_regras"] == "teste.1"
    assert trace["hash_regras"] == _rules(NTNB).content_hash
    assert (trace["tipo"], trace["janela_dias"], trace["limiar"]) == (
        "window_change",
        30,
        0.30,
    )
    assert trace["sentido"] == "both" and trace["confirmacoes"] == 2
    assert (trace["valor"], trace["competencia"]) == (7.40, "2026-09-18")
    assert (trace["valor_base"], trace["competencia_base"]) == (7.00, "2026-08-19")
    assert trace["medida"] == pytest.approx(0.40) and trace["por_revisao"] is False
    assert alert.severity == "atencao" and alert.reference == "2026-09-18"
    assert alert.since == TODAY.isoformat()


# --- impact on the valuation models --------------------------------------------------------


def _inputs(*positions, rate=0.10):
    base = BaseRate(rate, "2026-09-18", "2060-08-15", "Tesouro IPCA+") if rate else None
    return ValuationInputs("2026-09-20", base, tuple(positions))


_EQUITY = PositionInputs(
    "EQ3",
    "equity",
    "Materiais Básicos",
    "Madeiras e Papel",
    10.0,
    {"dividend_per_share": 1.0, "lpa": 1.5, "vpa": 4.6},
)
_FII = PositionInputs(
    "FII11",
    "fii",
    "Tijolo",
    "Logístico",
    95.0,
    {"dividend_per_share": 9.0, "nav_per_share": 100.0},
)


def test_a_rate_rise_lowers_the_fair_value_of_the_methods_that_use_the_rate():
    lines = ntnb_impact(_inputs(_EQUITY, _FII), 0.5)

    assert any(line.startswith("Bazin:") and "-" in line for line in lines)
    assert any(line.startswith("Yield:") and "mediana -" in line for line in lines)
    assert not any(line.startswith(("Graham", "NAV")) for line in lines)
    assert "insumos de 2026-09-20" in lines[-1] and "não previsão" in lines[-1]


def test_a_rate_fall_raises_them():
    lines = ntnb_impact(_inputs(_FII), -0.5)

    assert any(line.startswith("Yield:") and "mediana +" in line for line in lines)


def test_the_impact_says_why_it_was_not_estimated():
    assert "sem insumos" in ntnb_impact(None, 0.3)[0]
    assert "taxa-base" in ntnb_impact(_inputs(_FII, rate=None), 0.3)[0]


def test_the_ntnb_alert_carries_the_impact_and_the_direction(tmp_path):
    store = MacroStore(tmp_path)
    _ntnb(store, ("2026-09-10", "2026-09-18", 7.40))

    [alert] = _run(store, inputs=_inputs(_EQUITY, _FII)).active

    assert alert.impact and any(line.startswith("Yield:") for line in alert.impact)
    [line] = alert_lines(_run(store, inputs=_inputs(_EQUITY, _FII)))
    assert (
        line.startswith("ATENCAO Taxa real da NTN-B longa subiu") and "Bazin:" in line
    )


# --- state and alert file ------------------------------------------------------------------


def test_the_state_round_trips_and_a_corrupt_one_is_an_error_not_a_reset(tmp_path):
    assert load_state(tmp_path) is None
    store = MacroStore(tmp_path)
    _ntnb(store, ("2026-09-10", "2026-09-18", 7.40))
    state = _run(store).state

    path = save_state(tmp_path, state)
    assert load_state(tmp_path) == state

    path.write_text("{corrompido", encoding="utf-8")
    with pytest.raises(ValueError, match="ilegível"):
        load_state(tmp_path)
    path.write_text('{"rules": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="mal formado"):
        load_state(tmp_path)


def test_the_alert_file_has_only_new_attention_alerts_and_is_removed_otherwise(
    tmp_path,
):
    store = MacroStore(tmp_path)
    _selic(
        store, ("2026-08-01", "2026-09-16", 14.0), ("2026-09-17", "2026-09-20", 13.75)
    )
    _monthly(store, "inadimplencia_total", [("2025-07", 3.96), ("2026-07", 4.96)])
    rules = _rules(SELIC, INADIMPLENCIA)
    target = tmp_path / "logs" / "alertas_macro.txt"

    first = _run(store, rules=rules)
    lines = write_alert_file(target, first)

    assert len(first.active) == 2 and len(_new_economic(first)) == 2  # dois novos...
    assert len(lines) == 1 and lines[0].startswith(
        "ATENCAO Meta Selic alterada"
    )  # ...um notifica
    assert "Inadimplência" not in target.read_text(encoding="utf-8")

    write_alert_file(target, _run(store, first.state, rules=rules))
    assert not target.exists()


def test_the_alert_file_is_plain_cp1252_safe_text(tmp_path):
    store = MacroStore(tmp_path)
    _ntnb(store, ("2026-09-10", "2026-09-18", 6.60))
    target = tmp_path / "alertas.txt"

    write_alert_file(target, _run(store, inputs=_inputs(_FII)))

    target.read_text(encoding="utf-8").encode("cp1252")  # o console do Windows é cp1252


# --- the note and the dashboard ------------------------------------------------------------


def _frontmatter(text):
    out = {}
    for line in text.split("---")[1].strip().splitlines():
        key, _, value = line.partition(": ")
        try:
            out[key] = json.loads(value)
        except json.JSONDecodeError:
            out[key] = value
    return out


def _active_run(tmp_path):
    store = MacroStore(tmp_path)
    _ntnb(store, ("2026-09-10", "2026-09-18", 7.40))
    _selic(
        store, ("2026-08-01", "2026-09-16", 14.0), ("2026-09-17", "2026-09-20", 13.75)
    )
    _monthly(store, "inadimplencia_total", [("2025-07", 3.96), ("2026-07", 4.96)])
    return _run(
        store,
        rules=_rules(NTNB, SELIC, INADIMPLENCIA, replace(IPCA, id="ipca_x")),
        inputs=_inputs(_EQUITY, _FII),
    )


def test_the_note_separates_alerts_from_data_notices_and_states_its_limits(tmp_path):
    text = render_alerts_report(_active_run(tmp_path))

    assert CONTEXT_NOTICE in text and "INFORMATIVOS" in text
    assert "## Alertas ativos" in text and "## Avisos de dado" in text
    assert "### Atenção" in text and "### Informativo" in text
    assert "Separados dos alertas econômicos" in text
    assert (
        "Rastreio: regra `ntnb_real_30d` v2026" not in text
    )  # a versão do teste é teste.1
    assert "Rastreio: regra `ntnb_real_30d` vteste.1" in text
    assert "confirmada em 17/09/2026, 18/09/2026" in text


def test_the_note_shows_every_rule_with_its_window_threshold_and_current_measure(
    tmp_path,
):
    text = render_alerts_report(_active_run(tmp_path))

    assert "| `ntnb_real_30d` |" in text and "30 dias" in text
    assert "±0,30 p.p." in text and "2 observações distintas" in text
    assert "+0,40 p.p. (7,00 em 19/08/2026 -> 7,40 em 18/09/2026)" in text
    assert "qualquer alteração" in text and "+1,00 p.p." in text
    assert "> 4,50" in text


def test_the_note_documents_the_rearm_for_two_sided_and_any_change_rules(tmp_path):
    text = render_alerts_report(_active_run(tmp_path))

    assert "20% do limiar" in text and "lado que disparou" in text
    assert "qualquer alteração" in text and "retain_days" in text


def test_the_note_frontmatter_feeds_the_dashboard(tmp_path):
    fm = _frontmatter(render_alerts_report(_active_run(tmp_path)))

    assert fm[dash.MACRO_ALERTS_RULES_KEY] == 4
    active = {a["regra"]: a for a in fm[dash.MACRO_ALERTS_ACTIVE_KEY]}
    assert set(active) == {"ntnb_real_30d", "selic_meta_mudou", "inadimplencia_12m"}
    assert (
        active["ntnb_real_30d"]["severidade"] == "Atenção"
        and active["ntnb_real_30d"]["novo"]
    )
    assert fm[dash.MACRO_ALERTS_NEW_KEY] >= 3
    assert isinstance(fm[dash.MACRO_ALERTS_DATA_KEY], list)
    assert isinstance(fm[dash.MACRO_ALERTS_WATCH_KEY], list)


def test_the_dashboard_has_a_block_that_reads_the_note_and_handles_its_absence():
    template = dash.DASHBOARD_TEMPLATE

    assert dash.MACRO_ALERTS_NOTE_DV_PATH in template
    assert f"p.{dash.MACRO_ALERTS_ACTIVE_KEY}" in template
    assert "iip macro-alerts --report" in template
    assert "não decidem aporte nem peso" in template


def test_the_note_is_written_to_the_research_folder(tmp_path):
    path = write_alerts_report(tmp_path / "vault", _active_run(tmp_path))

    assert path == tmp_path / "vault" / "07_Research" / "Macro" / "Alertas_Macro.md"
    assert path.exists()


# --- CLI -----------------------------------------------------------------------------------


def _today():
    return date.today()  # noqa: DTZ011 - o comando usa a data de calendário de hoje


def _cli_vault(tmp_path):
    """Uma Selic que mudou há dois dias e os demais dados em dia."""
    store = MacroStore(tmp_path)
    today = _today()
    start = (today - timedelta(days=30)).isoformat()
    changed = (today - timedelta(days=2)).isoformat()
    before = (today - timedelta(days=3)).isoformat()
    _selic(
        store,
        (start, before, 14.0),
        (changed, today.isoformat(), 13.75),
        collected=today.isoformat(),
    )
    return tmp_path


def test_the_command_asks_for_init_when_there_are_no_rules(tmp_path):
    result = CliRunner().invoke(cli, ["macro-alerts", "--vault", str(tmp_path)])

    assert result.exit_code == 1 and "--init" in result.output
    assert load_state(tmp_path) is None


def test_init_creates_the_rules_and_never_overwrites_an_edited_file(tmp_path):
    runner = CliRunner()
    _cli_vault(tmp_path)

    created = runner.invoke(cli, ["macro-alerts", "--vault", str(tmp_path), "--init"])
    assert created.exit_code == 0, created.output
    path = tmp_path / "07_Research" / "Macro" / "alertas_macro.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = "editada.7"
    path.write_text(json.dumps(payload), encoding="utf-8")

    again = runner.invoke(cli, ["macro-alerts", "--vault", str(tmp_path), "--init"])

    assert again.exit_code == 0
    assert "editada.7" in again.output


def test_an_invalid_rules_file_fails_the_command_with_the_reason_and_writes_nothing(
    tmp_path,
):
    _write_rules(tmp_path, lambda p: _first_rule(p, kind="inventada"))

    result = CliRunner().invoke(
        cli, ["macro-alerts", "--vault", str(tmp_path), "--report"]
    )

    assert result.exit_code == 1
    assert "Configuração dos alertas inválida" in result.output
    assert "ntnb_real_30d" in result.output and "tipo desconhecido" in result.output
    assert load_state(tmp_path) is None
    assert not (tmp_path / "07_Research" / "Macro" / "Alertas_Macro.md").exists()


def test_a_corrupt_state_fails_the_command_instead_of_re_alerting(tmp_path):
    save_rules(tmp_path, DEFAULT_RULES)
    (tmp_path / "07_Research" / "Macro" / "estado_alertas.json").write_text(
        "{corrompido", encoding="utf-8"
    )

    result = CliRunner().invoke(cli, ["macro-alerts", "--vault", str(tmp_path)])

    assert result.exit_code == 1 and "ilegível" in result.output


def test_an_active_alert_is_reported_but_never_fails_the_command(tmp_path):
    _cli_vault(tmp_path)
    save_rules(tmp_path, DEFAULT_RULES)
    alert_file = tmp_path / "logs" / "alertas_macro.txt"

    result = CliRunner().invoke(
        cli,
        [
            "macro-alerts",
            "--vault",
            str(tmp_path),
            "--report",
            "--alert-file",
            str(alert_file),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "ATENCAO" in result.output and "Meta Selic alterada" in result.output
    assert alert_file.read_text(encoding="utf-8").startswith("ATENCAO Meta Selic")
    assert (tmp_path / "07_Research" / "Macro" / "Alertas_Macro.md").exists()
    assert load_state(tmp_path)["rules"]["selic_meta_mudou"]["event_key"]


def test_running_the_command_twice_notifies_only_once(tmp_path):
    _cli_vault(tmp_path)
    save_rules(tmp_path, DEFAULT_RULES)
    alert_file = tmp_path / "alertas_macro.txt"
    args = ["macro-alerts", "--vault", str(tmp_path), "--alert-file", str(alert_file)]
    runner = CliRunner()

    first = runner.invoke(cli, args)
    assert alert_file.exists()
    state_after_first = load_state(tmp_path)
    second = runner.invoke(cli, args)

    assert first.exit_code == 0 and second.exit_code == 0
    assert not alert_file.exists()  # nada novo: o arquivo do dia anterior é apagado
    assert load_state(tmp_path) == state_after_first


def test_dry_run_evaluates_without_writing_state_note_or_alert_file(tmp_path):
    _cli_vault(tmp_path)
    save_rules(tmp_path, DEFAULT_RULES)
    alert_file = tmp_path / "alertas_macro.txt"

    result = CliRunner().invoke(
        cli,
        [
            "macro-alerts",
            "--vault",
            str(tmp_path),
            "--dry-run",
            "--report",
            "--alert-file",
            str(alert_file),
        ],
    )

    assert result.exit_code == 0 and "nada foi gravado" in result.output
    assert load_state(tmp_path) is None
    assert not alert_file.exists()
    assert not (tmp_path / "07_Research" / "Macro" / "Alertas_Macro.md").exists()


# --- limits: nothing here touches contributions, weights or decisions ---------------------

_FORBIDDEN = (
    "iip.decision",
    "iip.integration",
    "iip.strategy",
    "iip.orchestration",
    "iip.portfolio_decision",
    "iip.portfolio.batch_decide",
    "iip.portfolio.exposure",
    "iip.portfolio.decision_alerts",
    "iip.knowledge",
)


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_the_alert_code_does_not_import_decision_contribution_or_weight_code():
    root = Path("src/iip")
    files = [root / "macro" / "alerts.py", root / "obsidian" / "macro_alerts_report.py"]

    offenders = {
        (f.name, name)
        for f in files
        for name in _imports(f)
        if any(name == bad or name.startswith(bad + ".") for bad in _FORBIDDEN)
    }

    assert offenders == set()


def test_nothing_in_the_decision_or_income_layers_imports_the_alert_code():
    root = Path("src/iip")
    files = [
        root / "portfolio" / "batch_decide.py",
        root / "portfolio" / "decision_alerts.py",
        root / "portfolio" / "exposure.py",
        root / "portfolio" / "income.py",
    ]

    assert not any(n.startswith("iip.macro") for f in files for n in _imports(f))


def test_the_alert_run_reads_no_decision_or_weight_state(tmp_path):
    # o resultado é função só do armazenamento macro, das regras, do estado e dos insumos de
    # valuation: nenhum parâmetro de decisão, aporte ou peso entra na assinatura
    import inspect

    parameters = set(inspect.signature(run_alerts).parameters)

    assert parameters == {"store", "rule_set", "state", "today", "inputs"}
