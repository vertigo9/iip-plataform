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

    assert check_against_targets(budget, policy) == ()


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

    breaches = check_against_targets(budget, policy)

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

    breaches = check_against_targets(budget, policy)

    assert len(breaches) == 7
    assert all(b.kind == BREACH_MIN_MAX for b in breaches)


def test_check_against_targets_ignores_pending_budget_lines(tmp_path):
    policy = _policy(tmp_path)
    lines = tuple(_defined_policy_line(ln, target=99.0) for ln in policy.lines[:1])
    policy = replace(policy, lines=lines + policy.lines[1:])
    budget = build_initial_budget(version="v1")  # todas pendentes

    assert check_against_targets(budget, policy) == ()


# --- ativação: só bloqueia com approval_status == aprovada ------------------------------


def _breaching_setup(tmp_path):
    policy = _policy(tmp_path)
    lines = tuple(_defined_policy_line(ln, target=15.0) for ln in policy.lines)
    # 7 linhas x 15% = 105%: só válido sob referencias_individuais (mesma regra usada na
    # política real); não é o foco deste teste, que é o cruzamento com o orçamento de classe
    policy = replace(policy, lines=lines, sum_rule="referencias_individuais")
    budget = replace(
        _budget(),
        lines=tuple(
            _budget_line(cid, target=5.0, tolerance=1.0, low=0.0, high=10.0)
            for cid in CLASS_IDS
        ),
    )
    return policy, budget


def test_enforce_is_silent_with_no_budget(tmp_path):
    policy, _ = _breaching_setup(tmp_path)
    enforce(None, policy)  # não levanta nada


def test_enforce_is_silent_while_the_budget_is_pending(tmp_path):
    policy, budget = _breaching_setup(tmp_path)
    assert budget.approval_status == "pendente"

    enforce(budget, policy)  # informativo só; não bloqueia


def test_enforce_blocks_once_the_budget_is_approved(tmp_path):
    policy, budget = _breaching_setup(tmp_path)
    approved = replace(budget, approval_status="aprovada")

    with pytest.raises(ValueError, match="fora do orçamento aprovado"):
        enforce(approved, policy)


def test_enforce_never_blocks_a_tolerance_only_breach_even_when_approved(tmp_path):
    policy = _policy(tmp_path)
    lines = tuple(_defined_policy_line(ln, target=9.0) for ln in policy.lines)
    policy = replace(policy, lines=lines)
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
    )  # 9% está fora da tolerância (4-6%) mas dentro de [0,10]: não bloqueia


# --- gravação atômica: tudo ou nada -------------------------------------------------------


def test_save_policy_guarded_writes_when_everything_passes(tmp_path):
    policy, _ = _breaching_setup(tmp_path)
    path = save_policy_guarded(tmp_path, policy, None)

    assert path == tmp_path / POLICY_RELATIVE_PATH
    assert path.exists()


def test_save_policy_guarded_writes_while_the_conflicting_budget_is_pending(tmp_path):
    policy, budget = _breaching_setup(tmp_path)

    path = save_policy_guarded(tmp_path, policy, budget)

    assert path.exists()


def test_save_policy_guarded_refuses_and_writes_nothing_when_the_approved_budget_breaks(
    tmp_path,
):
    """O requisito central: se o orçamento aprovado rejeita, a política individual não é
    gravada -- nem parcialmente. Nada no vault muda."""
    policy, budget = _breaching_setup(tmp_path)
    approved = replace(budget, approval_status="aprovada")
    policy_path = tmp_path / POLICY_RELATIVE_PATH

    with pytest.raises(ValueError, match="fora do orçamento aprovado"):
        save_policy_guarded(tmp_path, policy, approved)

    assert not policy_path.exists()


def test_save_policy_guarded_stops_at_individual_validation_before_looking_at_the_budget(
    tmp_path,
):
    """A ordem importa: uma política individualmente inválida nunca chega a olhar o
    orçamento -- e continua sem gravar nada."""
    policy, budget = _breaching_setup(tmp_path)
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
    policy, budget = _breaching_setup(tmp_path)
    # 1a gravação: sem orçamento, passa
    save_policy_guarded(tmp_path, policy, None)
    policy_path = tmp_path / POLICY_RELATIVE_PATH
    before = policy_path.read_text(encoding="utf-8")

    # 2a tentativa: agora com orçamento aprovado que rejeita a mesma política
    approved = replace(budget, approval_status="aprovada")
    with pytest.raises(ValueError, match="fora do orçamento aprovado"):
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
