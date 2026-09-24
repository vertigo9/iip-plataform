import ast
from dataclasses import replace
from pathlib import Path

import pytest

from iip.portfolio.class_budget import (
    BREACH_MIN_MAX,
    BREACH_TOLERANCE,
    BUDGET_RELATIVE_PATH,
    CLASS_IDS,
    ClassBudget,
    ClassBudgetLine,
    budget_target_sum,
    build_initial_budget,
    check_against_targets,
    class_sums,
    enforce,
    load_budget,
    prospective_class_targets,
    real_class_weights,
    save_budget,
    save_policy_guarded,
    validate,
)
from iip.portfolio.layers import CLASS_LABELS
from iip.portfolio.target_policy import (
    POLICY_RELATIVE_PATH,
    PolicyLine,
    TargetPolicy,
    build_initial_policy,
    read_snapshot_rows,
)

HEADER = (
    "| ID | Ativo | Classe | Quantidade | PM | Preço atual | Valor | Peso | Peso alvo | "
    "Status |"
)
# uma posição em cada uma das 7 classes de layers.py/CLASS_LABELS
ROWS = (
    ("BBSE3", "BBSE3", "acao", 40000.00),
    ("LVBI11", "LVBI11", "fii", 15000.00),
    ("CDII11", "CDII11", "fi-infra", 10000.00),
    ("CRAA11", "CRAA11", "fiagro", 5000.00),
    ("LFTB11", "LFTB11", "etf", 10000.00),
    ("RF-NUBANK-120CDI", "CDB NuBank 120% CDI", "renda_fixa", 8000.00),
    ("FMP-FGTS-DAYCOVAL", "DAYCOVAL FMP-FGTS", "fundo", 5000.00),
)


def _brl(value: float) -> str:
    return "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _write_snapshot(vault, rows=ROWS):
    lines = [
        "---",
        "type: portfolio",
        "---",
        "",
        "# Carteira Atual",
        "",
        HEADER,
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    total = sum(r[3] for r in rows) or 1
    for row_id, name, klass, value in rows:
        weight = f"{value / total * 100:.2f}%".replace(".", ",")
        lines.append(
            f"| {row_id} | {name} | {klass} |  |  |  | {_brl(value)} | {weight} |  | active |"
        )
    path = Path(vault) / "02_Portfolio" / "Current.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _policy(tmp_path) -> TargetPolicy:
    rows = read_snapshot_rows(_write_snapshot(tmp_path))
    return build_initial_policy(rows, version="teste.1")


def _defined_policy_line(line: PolicyLine, target: float) -> PolicyLine:
    return replace(
        line,
        target_pct=target,
        tolerance_pp=1.0,
        min_pct=max(0.0, target - 5.0),
        max_pct=target + 5.0,
        status="definido",
        decided_on="2026-09-24",
    )


def _budget_line(class_id: str, target=5.0, tolerance=1.0, low=3.0, high=8.0):
    return ClassBudgetLine(
        class_id=class_id,
        target_pct=target,
        tolerance_pp=tolerance,
        min_pct=low,
        max_pct=high,
        status="definido",
        decided_on="2026-09-24",
    )


def _budget(**overrides):
    lines = tuple(ClassBudgetLine(class_id=cid) for cid in CLASS_IDS)
    return replace(
        ClassBudget(version="teste.1", origin="teste", lines=lines), **overrides
    )


# --- taxonomia -------------------------------------------------------------------------


def test_class_ids_are_exactly_the_seven_layers_classes():
    assert set(CLASS_IDS) == set(CLASS_LABELS)
    assert len(CLASS_IDS) == 7


# --- construção inicial: nada é inventado -----------------------------------------------


def test_initial_budget_has_all_seven_classes_pending_and_empty():
    budget = build_initial_budget(version="v1")

    assert {ln.class_id for ln in budget.lines} == set(CLASS_IDS)
    assert all(ln.status == "pendente" for ln in budget.lines)
    assert all(not ln.complete for ln in budget.lines)


def test_a_budget_missing_a_class_is_refused():
    lines = tuple(ClassBudgetLine(class_id=cid) for cid in CLASS_IDS if cid != "fii")
    budget = ClassBudget(version="v1", origin="teste", lines=lines)

    with pytest.raises(ValueError, match="faltam classes"):
        validate(budget)


def test_a_repeated_class_is_refused():
    lines = tuple(ClassBudgetLine(class_id=cid) for cid in CLASS_IDS) + (
        ClassBudgetLine(class_id=CLASS_IDS[0]),
    )
    budget = ClassBudget(version="v1", origin="teste", lines=lines)

    with pytest.raises(ValueError, match="classe repetida"):
        validate(budget)


def test_an_unknown_class_id_is_refused():
    lines = tuple(ClassBudgetLine(class_id=cid) for cid in CLASS_IDS)
    lines = (*lines[:-1], ClassBudgetLine(class_id="cripto"))
    budget = ClassBudget(version="v1", origin="teste", lines=lines)

    with pytest.raises(ValueError, match="classe desconhecida"):
        validate(budget)


# --- faixa: mesma regra do target_policy, via helper compartilhado ----------------------


@pytest.mark.parametrize(
    "line, match",
    [
        (_budget_line("acao", low=9, high=3), "maior que max_pct"),
        (_budget_line("acao", target=2, low=3), "abaixo do mínimo"),
        (_budget_line("acao", target=9, high=8), "acima do máximo"),
        (
            _budget_line("acao", target=4, tolerance=3, low=3, high=8),
            "abaixo do mínimo",
        ),
        (
            _budget_line("acao", target=7, tolerance=3, low=3, high=8),
            "passa do máximo",
        ),
    ],
)
def test_invalid_ranges_are_refused_with_the_reason(line, match):
    budget = _budget()
    budget = replace(
        budget,
        lines=tuple(line if ln.class_id == "acao" else ln for ln in budget.lines),
    )

    with pytest.raises(ValueError, match=match):
        validate(budget)


def test_defined_requires_all_four_numbers_and_decided_on():
    incomplete = ClassBudgetLine(class_id="acao", target_pct=5.0, status="definido")
    budget = _budget()
    budget = replace(
        budget,
        lines=tuple(incomplete if ln.class_id == "acao" else ln for ln in budget.lines),
    )

    with pytest.raises(ValueError, match="definido exige"):
        validate(budget)


# --- soma: teto, nunca meta --------------------------------------------------------------


def test_defined_class_targets_can_stay_below_100_percent():
    """As 7 classes não precisam somar 100% -- é um teto, não uma meta (decisão do usuário,
    24/09/2026)."""
    lines = tuple(
        _budget_line(cid, target=5.0, low=0.0, high=10.0) for cid in CLASS_IDS
    )
    budget = ClassBudget(version="v1", origin="teste", lines=lines)

    validate(budget)  # 35% no total; não levanta nada
    assert budget_target_sum(budget) == pytest.approx(35.0)


def test_defined_class_targets_summing_past_100_percent_are_refused():
    lines = tuple(
        _budget_line(cid, target=20.0, low=0.0, high=100.0) for cid in CLASS_IDS
    )
    budget = ClassBudget(version="v1", origin="teste", lines=lines)  # 7 x 20% = 140%

    with pytest.raises(ValueError, match="passa de 100%"):
        validate(budget)


def test_an_approved_budget_requires_every_class_defined():
    budget = build_initial_budget(version="v1")  # todas pendentes

    with pytest.raises(ValueError, match="classes não definidas"):
        validate(replace(budget, approval_status="aprovada"))


# --- serialização ------------------------------------------------------------------------


def test_save_and_load_round_trip(tmp_path):
    lines = tuple(_budget_line(cid) for cid in CLASS_IDS)
    budget = ClassBudget(version="v1", origin="teste", lines=lines)

    path = save_budget(tmp_path, budget)
    assert path == tmp_path / BUDGET_RELATIVE_PATH

    loaded = load_budget(tmp_path)
    assert loaded.content_hash == budget.content_hash
    assert loaded.lines == budget.lines


def test_load_budget_without_a_file_returns_none(tmp_path):
    assert load_budget(tmp_path) is None


def test_load_budget_with_a_broken_file_raises_with_the_reason(tmp_path):
    path = tmp_path / BUDGET_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="não é um JSON válido"):
        load_budget(tmp_path)


# --- leitura contra a política individual (informativa, sempre computada) ---------------


def test_class_sums_aggregates_defined_targets_by_asset_class(tmp_path):
    policy = _policy(tmp_path)
    lines = tuple(_defined_policy_line(ln, target=5.0) for ln in policy.lines)
    policy = replace(policy, lines=lines)

    sums = class_sums(policy)

    assert sums == {
        "acao": 5.0,
        "fii": 5.0,
        "fi-infra": 5.0,
        "fiagro": 5.0,
        "etf": 5.0,
        "renda_fixa": 5.0,
        "fundo": 5.0,
    }


def test_class_sums_ignores_inactive_and_undefined_lines(tmp_path):
    policy = _policy(tmp_path)
    stock_line = next(ln for ln in policy.lines if ln.asset_class == "acao")
    lines = tuple(
        replace(ln, status="inativo") if ln.id == stock_line.id else ln
        for ln in policy.lines
    )
    policy = replace(policy, lines=lines)

    assert "acao" not in class_sums(policy)


def test_check_against_targets_is_silent_when_inside_tolerance(tmp_path):
    policy = _policy(tmp_path)
    lines = tuple(_defined_policy_line(ln, target=5.0) for ln in policy.lines)
    policy = replace(policy, lines=lines)
    budget = replace(
        _budget(),
        lines=tuple(
            _budget_line(cid, target=5.0, tolerance=1.0, low=0.0, high=10.0)
            for cid in CLASS_IDS
        ),
    )

    assert check_against_targets(budget, class_sums(policy)) == ()


def test_check_against_targets_reports_a_tolerance_breach(tmp_path):
    policy = _policy(tmp_path)
    lines = tuple(_defined_policy_line(ln, target=9.0) for ln in policy.lines)
    policy = replace(policy, lines=lines)
    budget = replace(
        _budget(),
        lines=tuple(
            _budget_line(cid, target=5.0, tolerance=1.0, low=0.0, high=10.0)
            for cid in CLASS_IDS
        ),
    )

    breaches = check_against_targets(budget, class_sums(policy))

    assert len(breaches) == 7
    assert all(b.kind == BREACH_TOLERANCE for b in breaches)
    assert all(b.automatic_action == "nenhuma" for b in breaches)


def test_check_against_targets_reports_a_min_max_breach(tmp_path):
    policy = _policy(tmp_path)
    lines = tuple(_defined_policy_line(ln, target=15.0) for ln in policy.lines)
    policy = replace(policy, lines=lines)
    budget = replace(
        _budget(),
        lines=tuple(
            _budget_line(cid, target=5.0, tolerance=1.0, low=0.0, high=10.0)
            for cid in CLASS_IDS
        ),
    )

    breaches = check_against_targets(budget, class_sums(policy))

    assert len(breaches) == 7
    assert all(b.kind == BREACH_MIN_MAX for b in breaches)


def test_check_against_targets_ignores_pending_budget_lines(tmp_path):
    policy = _policy(tmp_path)
    lines = tuple(_defined_policy_line(ln, target=99.0) for ln in policy.lines[:1])
    policy = replace(policy, lines=lines + policy.lines[1:])
    budget = build_initial_budget(version="v1")  # todas pendentes

    assert check_against_targets(budget, class_sums(policy)) == ()


def test_check_against_targets_ignores_a_class_absent_from_the_value_map():
    """Uma classe ausente do dict é "sem dado", nunca "dado zero" -- por isso min_pct > 0
    não gera um falso MIN_MAX aqui."""
    budget = replace(
        _budget(),
        lines=tuple(
            _budget_line(cid, target=5.0, tolerance=1.0, low=3.0, high=10.0)
            for cid in CLASS_IDS
        ),
    )

    assert check_against_targets(budget, {}) == ()


@pytest.mark.parametrize("approval_status", ["pendente", "aprovada"])
def test_a_real_weight_min_max_breach_is_pure_observation_never_a_sell_signal(
    approval_status,
):
    """Propriedade arquitetural (auditoria pós-governança de 24/09/2026, achado do ETF real:
    4,13% de peso vs máximo de 4% do orçamento aprovado): um desvio de min/máx lido contra o
    PESO REAL (``real_class_weights``, camada A de monitoramento) é sempre só observação --
    nunca uma recomendação de venda, nunca um bloqueio -- e isso NÃO MUDA com
    ``approval_status``. Só ``enforce()``, alimentado por ``prospective_class_targets()``
    (nunca por peso real), pode levantar ``ValueError``; ``check_against_targets`` em si
    jamais levanta nada, para nenhuma fonte de dado."""
    budget = replace(
        _budget(),
        approval_status=approval_status,
        lines=tuple(
            _budget_line(cid, target=0.0, tolerance=0.0, low=0.0, high=4.0)
            for cid in CLASS_IDS
        ),
    )
    real_weights = {cid: 4.13 for cid in CLASS_IDS}  # acima do max=4 em toda classe

    breaches = check_against_targets(budget, real_weights)  # nunca levanta, so retorna

    assert len(breaches) == len(CLASS_IDS)
    assert all(b.kind == BREACH_MIN_MAX for b in breaches)
    assert all(b.automatic_action == "nenhuma" for b in breaches)
    # a leitura e IDENTICA pendente ou aprovada: aprovar B nao muda o que a camada A relata
    assert breaches == check_against_targets(
        replace(budget, approval_status="pendente"), real_weights
    )


# --- a ponte entre orçamento de classe e política individual (auditoria de 24/09/2026) --------
#
# Achado: a política real usa a regra uniforme 3/5/15 (cada ativo com um placeholder de 5%,
# sum_rule = "referencias_individuais"). Somar esses placeholders por classe (14 ações x 5% =
# 70%, 15 FIIs x 5% = 75%) e comparar contra o orçamento de classe fabrica um "alvo de classe"
# que a política nunca pretendeu representar. prospective_class_targets() só produz um sinal
# quando sum_rule autoriza a soma como alocação real (total_100/reserva); do contrário, {}.


def test_prospective_class_targets_is_empty_for_the_real_uniform_placeholder_shape(
    tmp_path,
):
    """A -- o teste de regressão mais importante desta correção: 14 ações e 15 FIIs, cada um
    com o placeholder uniforme 5% (a mesma forma da política real 3/5/15). A soma mecânica
    (70% e 75%) NÃO pode virar alvo de classe sob referencias_individuais."""
    rows = tuple((f"ACAO{i}", f"ACAO{i}", "acao", 1000.0) for i in range(14)) + tuple(
        (f"FII{i}", f"FII{i}", "fii", 1000.0) for i in range(15)
    )
    policy = build_initial_policy(
        read_snapshot_rows(_write_snapshot(tmp_path, rows=rows)), version="teste.1"
    )
    lines = tuple(_defined_policy_line(ln, target=5.0) for ln in policy.lines)
    policy = replace(policy, lines=lines, sum_rule="referencias_individuais")

    assert class_sums(policy) == {
        "acao": pytest.approx(70.0),
        "fii": pytest.approx(75.0),
    }
    assert prospective_class_targets(policy) == {}


@pytest.mark.parametrize("sum_rule", [None, "referencias_individuais"])
def test_prospective_class_targets_is_empty_without_an_aggregating_sum_rule(
    tmp_path, sum_rule
):
    policy = _policy(tmp_path)
    lines = tuple(_defined_policy_line(ln, target=8.0) for ln in policy.lines)
    policy = replace(policy, lines=lines, sum_rule=sum_rule)

    assert prospective_class_targets(policy) == {}


@pytest.mark.parametrize("sum_rule", ["total_100", "reserva"])
def test_prospective_class_targets_equals_class_sums_under_an_aggregating_sum_rule(
    tmp_path, sum_rule
):
    policy = _policy(tmp_path)
    lines = tuple(_defined_policy_line(ln, target=8.0) for ln in policy.lines)
    policy = replace(policy, lines=lines, sum_rule=sum_rule)

    assert prospective_class_targets(policy) == class_sums(policy)


def test_an_isolated_edit_is_not_rejected_by_other_placeholders_in_the_same_class(
    tmp_path,
):
    """B -- mesmo com várias linhas na mesma classe usando o placeholder uniforme, editar SÓ
    UMA delas não pode ser rejeitada pela soma mecânica das outras: sob
    referencias_individuais, prospective_class_targets() é {} e enforce() nunca olha essa
    soma, mesmo que ela "pareça" estourar o orçamento se mal interpretada."""
    rows = (
        ("BBSE3", "BBSE3", "acao", 40000.0),
        ("ISAE4", "ISAE4", "acao", 10000.0),
        ("CXSE3", "CXSE3", "acao", 10000.0),
    )
    policy = build_initial_policy(
        read_snapshot_rows(_write_snapshot(tmp_path, rows=rows)), version="teste.1"
    )
    lines = tuple(_defined_policy_line(ln, target=5.0) for ln in policy.lines)
    policy = replace(policy, lines=lines, sum_rule="referencias_individuais")
    # edita só o ISAE4; a soma "ingênua" da classe (5+6+5=16%) estouraria o max=10 se fosse
    # tratada como agregado -- mas sob referencias_individuais isso nunca é checado
    edited = replace(
        next(ln for ln in policy.lines if ln.id == "ISAE4"), target_pct=6.0
    )
    candidate = replace(
        policy, lines=tuple(edited if ln.id == "ISAE4" else ln for ln in policy.lines)
    )
    budget = replace(
        _budget(),
        approval_status="aprovada",
        lines=tuple(
            _budget_line(cid, target=5.0, tolerance=1.0, low=0.0, high=10.0)
            for cid in CLASS_IDS
        ),
    )

    enforce(budget, candidate)  # não levanta nada


# --- real_class_weights: peso real, para a camada A de monitoramento (nunca bloqueia) ------


def test_real_class_weights_matches_the_snapshot(tmp_path):
    rows = read_snapshot_rows(_write_snapshot(tmp_path))
    total = sum(r.value for r in rows)

    weights = real_class_weights(rows)

    for row in rows:
        assert weights[row.asset_class] == pytest.approx(row.value / total * 100)


def test_real_class_weights_sums_multiple_rows_in_the_same_class(tmp_path):
    rows = read_snapshot_rows(
        _write_snapshot(
            tmp_path,
            rows=(
                ("RF-A", "RF-A", "renda_fixa", 1000.0),
                ("RF-B", "RF-B", "renda_fixa", 3000.0),
                ("BBSE3", "BBSE3", "acao", 6000.0),
            ),
        )
    )

    weights = real_class_weights(rows)

    assert weights == {"renda_fixa": pytest.approx(40.0), "acao": pytest.approx(60.0)}


# --- ativação: só bloqueia com approval_status == aprovada E um sinal prospectivo real -----


def _breaching_setup(tmp_path):
    """A regra real de hoje (referencias_individuais): a soma dos placeholders "estoura" o
    orçamento se mal interpretada, mas prospective_class_targets() é {} -- enforce() nunca
    deve bloquear por aqui, aprovado ou não (regressão A/B)."""
    policy = _policy(tmp_path)
    lines = tuple(_defined_policy_line(ln, target=15.0) for ln in policy.lines)
    policy = replace(policy, lines=lines, sum_rule="referencias_individuais")
    budget = replace(
        _budget(),
        lines=tuple(
            _budget_line(cid, target=5.0, tolerance=1.0, low=0.0, high=10.0)
            for cid in CLASS_IDS
        ),
    )
    return policy, budget


def _genuine_breach_setup(tmp_path, sum_rule):
    """Sob um sum_rule que autoriza agregação (total_100/reserva), os alvos individuais
    representam alocação real -- uma soma que estoura o max da classe é uma violação de
    verdade (regressão C/D). Soma total = 7 x 8% = 56%, sob 100% (não esbarra na checagem de
    soma do target_policy); só a classe "acao" tem o max do orçamento mais apertado (6%), para
    o alvo individual de 8% estourar de fato."""
    policy = _policy(tmp_path)
    lines = tuple(_defined_policy_line(ln, target=8.0) for ln in policy.lines)
    policy = replace(policy, lines=lines, sum_rule=sum_rule)
    budget_lines = tuple(
        _budget_line(cid, target=5.0, tolerance=1.0, low=0.0, high=10.0)
        for cid in CLASS_IDS
    )
    budget_lines = tuple(
        (
            _budget_line("acao", target=5.0, tolerance=1.0, low=0.0, high=6.0)
            if ln.class_id == "acao"
            else ln
        )
        for ln in budget_lines
    )
    budget = replace(_budget(), lines=budget_lines)
    return policy, budget


def test_enforce_is_silent_with_no_budget(tmp_path):
    policy, _ = _breaching_setup(tmp_path)
    enforce(None, policy)  # não levanta nada


def test_enforce_is_silent_while_the_budget_is_pending_under_individual_references(
    tmp_path,
):
    policy, budget = _breaching_setup(tmp_path)
    assert budget.approval_status == "pendente"

    enforce(budget, policy)  # informativo só; não bloqueia


def test_enforce_never_blocks_under_individual_references_even_when_approved(
    tmp_path,
):
    """A/B -- a regressão mais importante: sob referencias_individuais (a regra real de
    hoje), aprovar o orçamento NÃO passa a bloquear a soma mecânica dos placeholders 3/5/15.
    """
    policy, budget = _breaching_setup(tmp_path)
    approved = replace(budget, approval_status="aprovada")

    enforce(approved, policy)  # não levanta nada


@pytest.mark.parametrize("sum_rule", ["total_100", "reserva"])
def test_enforce_is_silent_while_pending_even_with_a_genuine_prospective_violation(
    tmp_path, sum_rule
):
    """E."""
    policy, budget = _genuine_breach_setup(tmp_path, sum_rule)
    assert budget.approval_status == "pendente"

    enforce(budget, policy)  # informativo só; não bloqueia


@pytest.mark.parametrize("sum_rule", ["total_100", "reserva"])
def test_enforce_blocks_a_genuine_prospective_violation_when_approved(
    tmp_path, sum_rule
):
    """C/D/F -- prova de que o guard continua funcional quando o dado é legítimo, para
    total_100 e para reserva (não uma implementação específica de um só sum_rule)."""
    policy, budget = _genuine_breach_setup(tmp_path, sum_rule)
    approved = replace(budget, approval_status="aprovada")

    with pytest.raises(ValueError, match="alvo agregado prospectivo"):
        enforce(approved, policy)


def test_enforce_never_blocks_a_tolerance_only_breach_even_with_an_aggregating_rule(
    tmp_path,
):
    """G -- mesmo com um sum_rule que autoriza agregação e o orçamento aprovado, um desvio só
    de tolerância (dentro de min/máx) continua informativo."""
    policy = _policy(tmp_path)
    lines = tuple(
        _defined_policy_line(ln, target=7.0) for ln in policy.lines
    )  # 7x7%=49%
    policy = replace(policy, lines=lines, sum_rule="total_100")
    budget = replace(
        _budget(),
        approval_status="aprovada",
        lines=tuple(
            _budget_line(cid, target=5.0, tolerance=1.0, low=0.0, high=10.0)
            for cid in CLASS_IDS
        ),
    )

    enforce(
        budget, policy
    )  # 7% está fora da tolerância (4-6%) mas dentro de [0,10]: não bloqueia


# --- gravação atômica: tudo ou nada (H) -----------------------------------------------------


def test_save_policy_guarded_writes_when_everything_passes(tmp_path):
    policy, _ = _breaching_setup(tmp_path)
    path = save_policy_guarded(tmp_path, policy, None)

    assert path == tmp_path / POLICY_RELATIVE_PATH
    assert path.exists()


def test_save_policy_guarded_writes_while_the_conflicting_budget_is_pending(tmp_path):
    policy, budget = _genuine_breach_setup(tmp_path, "total_100")

    path = save_policy_guarded(tmp_path, policy, budget)

    assert path.exists()


def test_save_policy_guarded_refuses_and_writes_nothing_when_the_approved_budget_breaks(
    tmp_path,
):
    """O requisito central: se o orçamento aprovado rejeita uma violação prospectiva
    genuína, a política individual não é gravada -- nem parcialmente. Nada no vault muda.
    """
    policy, budget = _genuine_breach_setup(tmp_path, "total_100")
    approved = replace(budget, approval_status="aprovada")
    policy_path = tmp_path / POLICY_RELATIVE_PATH

    with pytest.raises(ValueError, match="alvo agregado prospectivo"):
        save_policy_guarded(tmp_path, policy, approved)

    assert not policy_path.exists()


def test_save_policy_guarded_stops_at_individual_validation_before_looking_at_the_budget(
    tmp_path,
):
    """A ordem importa: uma política individualmente inválida nunca chega a olhar o
    orçamento -- e continua sem gravar nada."""
    policy, budget = _genuine_breach_setup(tmp_path, "total_100")
    approved = replace(budget, approval_status="aprovada")
    broken_line = replace(policy.lines[0], min_pct=90.0, max_pct=10.0)  # min > max
    broken_policy = replace(policy, lines=(broken_line, *policy.lines[1:]))
    policy_path = tmp_path / POLICY_RELATIVE_PATH

    with pytest.raises(ValueError, match="maior que max_pct"):
        save_policy_guarded(tmp_path, broken_policy, approved)

    assert not policy_path.exists()


def test_save_policy_guarded_does_not_overwrite_a_previous_valid_policy_on_rejection(
    tmp_path,
):
    """Reforça a atomicidade: uma política já gravada com sucesso não é tocada quando uma
    gravação seguinte é rejeitada pelo orçamento aprovado."""
    policy, budget = _genuine_breach_setup(tmp_path, "total_100")
    # 1a gravação: sem orçamento, passa
    save_policy_guarded(tmp_path, policy, None)
    policy_path = tmp_path / POLICY_RELATIVE_PATH
    before = policy_path.read_text(encoding="utf-8")

    # 2a tentativa: agora com orçamento aprovado que rejeita a mesma política
    approved = replace(budget, approval_status="aprovada")
    with pytest.raises(ValueError, match="alvo agregado prospectivo"):
        save_policy_guarded(tmp_path, policy, approved)

    assert policy_path.read_text(encoding="utf-8") == before


# --- isolamento: quem pode importar este módulo -------------------------------------------


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_class_budget_is_not_imported_by_anything_in_src_yet():
    """Ainda não há CLI/relatório/integração ao job (etapa seguinte, autorizada à parte);
    hoje só os testes usam este módulo. Atualizar esta lista quando isso mudar."""
    root = Path("src/iip")
    users = {
        str(path).replace("\\", "/")
        for path in root.rglob("*.py")
        if any(
            n == "iip.portfolio.class_budget"
            or n.startswith("iip.portfolio.class_budget.")
            for n in _imports(path)
        )
    }
    assert users == set()


def test_class_budget_does_not_import_decision_or_execution_layers():
    forbidden = (
        "iip.decision",
        "iip.portfolio_decision",
        "iip.portfolio.batch_decide",
        "iip.portfolio.decision_alerts",
        "iip.portfolio.rebalancing_alerts",
    )
    names = _imports(Path("src/iip/portfolio/class_budget.py"))

    offenders = {
        n
        for n in names
        if any(n == bad or n.startswith(bad + ".") for bad in forbidden)
    }
    assert offenders == set()
