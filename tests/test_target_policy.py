import ast
import datetime as dt
import json
from dataclasses import replace
from pathlib import Path

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.obsidian.target_policy_report import render_policy_report, write_policy_report
from iip.portfolio.target_policy import (
    BANK_FIXED_INCOME_ID,
    PolicyLine,
    RetiredPosition,
    TargetPolicy,
    build_initial_policy,
    load_policy,
    read_snapshot_rows,
    reconcile,
    save_policy,
    validate,
)

TODAY = dt.date(2026, 9, 20)

HEADER = (
    "| ID | Ativo | Classe | Quantidade | PM | Preço atual | Valor | Peso | Peso alvo | "
    "Status |"
)
ROWS = (
    ("BBSE3", "BBSE3", "acao", 40000.00),
    ("ISAE4", "ISAE4", "acao", 10000.00),
    ("LVBI11", "LVBI11", "fii", 15000.00),
    ("CDII11", "CDII11", "fi-infra", 10000.00),
    ("CRAA11", "CRAA11", "fiagro", 5000.00),
    ("LFTB11", "LFTB11", "etf", 10000.00),
    ("RF-NUBANK-120CDI", "CDB NuBank 120% CDI", "renda_fixa", 8000.00),
    ("RF-MP-115CDI", "CDB Mercado Pago 115% CDI", "renda_fixa", 2000.00),
    ("FMP-FGTS-DAYCOVAL", "DAYCOVAL FMP-FGTS", "fundo", 0.0),  # ajustado abaixo
)
FMP_VALUE = 0.0


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _brl(value: float) -> str:
    return "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _write_snapshot(vault, rows=ROWS, *, status="active", extra=()):
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
    total = sum(r[3] for r in (*rows, *extra)) or 1
    for row in (*rows, *extra):
        row_id, name, klass, value = row[:4]
        row_status = row[4] if len(row) > 4 else status
        weight = f"{value / total * 100:.2f}%".replace(".", ",")
        lines.append(
            f"| {row_id} | {name} | {klass} |  |  |  | {_brl(value)} | {weight} |  | "
            f"{row_status} |"
        )
    path = Path(vault) / "02_Portfolio" / "Current.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _rows(vault, **kwargs):
    return read_snapshot_rows(_write_snapshot(vault, **kwargs))


def _policy(tmp_path):
    return build_initial_policy(_rows(tmp_path), version="teste.1")


def _defined(line, target=5.0, tolerance=1.0, low=3.0, high=8.0):
    return replace(
        line,
        target_pct=target,
        tolerance_pp=tolerance,
        min_pct=low,
        max_pct=high,
        status="definido",
        decided_on="2026-09-20",
    )


# --- building the initial policy: nothing is invented --------------------------------------


def test_the_initial_policy_has_one_line_per_asset_and_one_group_for_the_cds(tmp_path):
    policy = _policy(tmp_path)

    ids = [ln.id for ln in policy.lines]
    assert ids == [
        "BBSE3",
        "ISAE4",
        "LVBI11",
        "CDII11",
        "CRAA11",
        "LFTB11",
        "FMP-FGTS-DAYCOVAL",
        BANK_FIXED_INCOME_ID,
    ]
    group = policy.line(BANK_FIXED_INCOME_ID)
    assert group.kind == "group" and group.asset_class == "renda_fixa"
    assert group.members == ("RF-NUBANK-120CDI", "RF-MP-115CDI")


def test_no_percentage_is_ever_filled_by_the_initial_policy(tmp_path):
    policy = _policy(tmp_path)

    assert all(ln.numbers == (None, None, None, None) for ln in policy.lines)
    assert {ln.status for ln in policy.lines} == {"pendente"}
    assert all(ln.decided_on is None and ln.rationale == "" for ln in policy.lines)
    assert policy.approval_status == "pendente"
    assert policy.monitoring_enabled is False
    assert policy.sum_rule is None


def test_the_user_decisions_are_recorded_in_the_initial_policy(tmp_path):
    policy = _policy(tmp_path)

    assert policy.base_id == "A" and "soma dos valores" in policy.base_description
    assert policy.line("LFTB11").kind == "asset"
    assert policy.line("FMP-FGTS-DAYCOVAL").aliases == ("AXIA3",)
    assert [(r.id, r.closed_on) for r in policy.retired] == [
        ("BTCI11", "2026-09-18"),
        ("PVBI11", "2026-08-14"),
    ]
    assert policy.line("AXIA3") is None  # o apelido não vira uma linha própria


def test_identifiers_resolve_through_aliases_and_group_members(tmp_path):
    policy = _policy(tmp_path)

    assert policy.resolve("AXIA3").id == "FMP-FGTS-DAYCOVAL"
    assert policy.resolve("FMP-FGTS-DAYCOVAL").id == "FMP-FGTS-DAYCOVAL"
    assert policy.resolve("RF-MP-115CDI").id == BANK_FIXED_INCOME_ID
    assert policy.resolve("PVBI11") is None


def test_inactive_snapshot_rows_are_not_in_the_universe(tmp_path):
    rows = _rows(tmp_path, extra=(("OLD3", "OLD3", "acao", 1000.0, "inactive"),))

    assert "OLD3" not in {r.id for r in rows}


def test_a_snapshot_without_table_or_positions_is_an_explicit_error(tmp_path):
    bad = tmp_path / "Current.md"
    bad.write_text("# nada aqui\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cabeçalho de tabela"):
        read_snapshot_rows(bad)

    empty = _write_snapshot(
        tmp_path / "v", rows=(("X3", "X3", "acao", 1.0, "inactive"),)
    )
    with pytest.raises(ValueError, match="nenhuma posição ativa"):
        read_snapshot_rows(empty)


# --- persistence: hash, strict loading ------------------------------------------------------


def test_the_policy_survives_a_save_and_load_with_the_same_hash(tmp_path):
    policy = _policy(tmp_path)

    save_policy(tmp_path, policy)
    loaded = load_policy(tmp_path)

    assert loaded == policy and loaded.content_hash == policy.content_hash


def test_no_policy_file_reads_as_none(tmp_path):
    assert load_policy(tmp_path) is None


def test_the_hash_follows_the_policy_and_ignores_the_origin(tmp_path):
    policy = _policy(tmp_path)
    other_origin = replace(policy, origin="outra origem")
    edited = replace(
        policy, lines=(replace(policy.lines[0], rationale="por quê"), *policy.lines[1:])
    )

    assert policy.content_hash == other_origin.content_hash
    assert policy.content_hash != edited.content_hash


def _write_policy(tmp_path, mutate):
    save_policy(tmp_path, _policy(tmp_path))
    path = tmp_path / "02_Portfolio" / "Politica_Pesos_Alvo.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _line(payload, index=0, **changes):
    payload["lines"][index].update(changes)


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda p: p.update(surpresa=1), "chave desconhecida na raiz"),
        (lambda p: p.update(schema="outro"), "schema"),
        (lambda p: p.update(approval_status="talvez"), "approval_status"),
        (lambda p: p.update(sum_rule="metade"), "sum_rule"),
        (lambda p: p["base"].update(id="B"), "base 'B' desconhecida"),
        (lambda p: p["monitoring"].update(enabled="sim"), "true ou false"),
        (
            lambda p: p["monitoring"].update(enabled=True),
            "só pode ligar com a política",
        ),
        (lambda p: p.update(lines=[]), "não tem linhas"),
        (lambda p: _line(p, chave_nova=1), "chave desconhecida"),
        (lambda p: _line(p, status="quase"), "status"),
        (lambda p: _line(p, kind="grupo"), "kind"),
        (lambda p: _line(p, target_pct=120), "fora do intervalo"),
        (lambda p: _line(p, target_pct=-1), "fora do intervalo"),
        (lambda p: _line(p, tolerance_pp=-0.5), "fora do intervalo"),
        (lambda p: _line(p, target_pct=True), "precisa ser um número"),
        (lambda p: _line(p, target_pct="4"), "precisa ser um número"),
        (lambda p: _line(p, min_pct=9, max_pct=3), "maior que max_pct"),
        (lambda p: _line(p, target_pct=2, min_pct=3), "abaixo do mínimo"),
        (lambda p: _line(p, target_pct=9, max_pct=8), "acima do máximo"),
        (
            lambda p: _line(p, target_pct=4, tolerance_pp=2, min_pct=3, max_pct=8),
            "abaixo do mínimo",
        ),
        (
            lambda p: _line(p, target_pct=7, tolerance_pp=2, min_pct=3, max_pct=8),
            "passa do máximo",
        ),
        (lambda p: _line(p, status="definido"), "definido exige alvo"),
        (
            lambda p: _line(
                p,
                status="definido",
                target_pct=5,
                tolerance_pp=1,
                min_pct=3,
                max_pct=8,
            ),
            "data da decisão",
        ),
        (lambda p: _line(p, decided_on="ontem"), "AAAA-MM-DD"),
        (lambda p: _line(p, 1, id="BBSE3"), "já pertence"),
        (lambda p: _line(p, 1, aliases=["BBSE3"]), "já pertence"),
        (lambda p: _line(p, 1, members=["X"]), "members só vale para grupos"),
        (lambda p: _line(p, -1, members=[]), "grupo precisa de members"),
        (lambda p: _line(p, -1, members=["BBSE3", "RF-MP-115CDI"]), "já pertence"),
        (
            lambda p: p["retired"].append({"id": "BBSE3", "closed_on": "2026-01-01"}),
            "retired",
        ),
        (lambda p: p["retired"].append({"id": "Z", "closed_on": "nunca"}), "closed_on"),
        (lambda p: p["retired"].append({"id": "Z", "extra": 1}), "retired mal formado"),
        (
            lambda p: [
                _line(p, i, target_pct=20, tolerance_pp=1, min_pct=1, max_pct=30)
                for i in range(6)
            ],
            "passa de 100%",
        ),
    ],
)
def test_a_wrong_policy_file_is_an_explicit_error_never_a_silent_default(
    tmp_path, mutate, reason
):
    path = _write_policy(tmp_path, mutate)

    with pytest.raises(ValueError, match=reason) as error:
        load_policy(tmp_path)

    assert str(path) in str(error.value)


def test_a_policy_file_that_is_not_json_is_an_explicit_error(tmp_path):
    path = _write_policy(tmp_path, lambda p: None)
    path.write_text("{quebrado", encoding="utf-8")

    with pytest.raises(ValueError, match="não é um JSON válido"):
        load_policy(tmp_path)


# --- approval and the sum rule --------------------------------------------------------------


def _all_defined(policy, targets):
    lines = tuple(
        _defined(ln, target=t, tolerance=0.5, low=max(t - 2, 0), high=t + 2)
        for ln, t in zip(policy.lines, targets, strict=True)
    )
    return replace(policy, lines=lines)


def test_an_approved_policy_needs_every_active_line_defined(tmp_path):
    policy = _policy(tmp_path)

    with pytest.raises(ValueError, match="linhas não definidas"):
        validate(replace(policy, approval_status="aprovada", sum_rule="total_100"))


def test_an_approved_policy_needs_the_sum_rule_and_respects_it(tmp_path):
    policy = _policy(tmp_path)
    targets = [20.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]  # soma 90
    defined = _all_defined(policy, targets)

    with pytest.raises(ValueError, match="regra de soma"):
        validate(replace(defined, approval_status="aprovada"))
    with pytest.raises(ValueError, match="total_100: os alvos somam 90"):
        validate(replace(defined, approval_status="aprovada", sum_rule="total_100"))
    validate(replace(defined, approval_status="aprovada", sum_rule="reserva"))


def test_a_fully_defined_policy_that_sums_to_100_can_be_approved_and_monitored(
    tmp_path,
):
    policy = _all_defined(
        _policy(tmp_path), [30.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    )
    approved = replace(
        policy,
        approval_status="aprovada",
        sum_rule="total_100",
        monitoring_enabled=True,
    )

    validate(approved)
    save_policy(tmp_path, approved)
    assert load_policy(tmp_path).monitoring_enabled is True


def test_an_inactive_line_does_not_block_approval_or_count_in_the_sum(tmp_path):
    policy = _policy(tmp_path)
    inactive = replace(policy.lines[0], status="inativo")
    rest = [
        _defined(ln, target=t, tolerance=0.5, low=t - 2, high=t + 2)
        for ln, t in zip(
            policy.lines[1:], [15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 10.0], strict=True
        )
    ]
    approved = replace(
        policy,
        lines=(inactive, *rest),
        approval_status="aprovada",
        sum_rule="total_100",
    )

    validate(approved)


# --- reconciliation with the snapshot (read only) ------------------------------------------


def test_the_current_weights_use_base_a_and_group_the_cds(tmp_path):
    policy = _policy(tmp_path)
    rec = reconcile(policy, _rows(tmp_path))

    assert rec.total == pytest.approx(100000.0 - 0.0)
    assert sum(w.weight_pct for w in rec.weights) == pytest.approx(100.0)
    by_id = {w.line.id: w for w in rec.weights}
    assert by_id["BBSE3"].weight_pct == pytest.approx(40.0)
    assert by_id[BANK_FIXED_INCOME_ID].value == pytest.approx(10000.0)
    assert by_id[BANK_FIXED_INCOME_ID].present == ("RF-NUBANK-120CDI", "RF-MP-115CDI")
    assert rec.consistent and rec.missing_members == ()


def test_a_position_without_a_line_is_reported_and_not_silently_absorbed(tmp_path):
    policy = _policy(tmp_path)
    rows = _rows(tmp_path, extra=(("NOVO11", "NOVO11", "fii", 3000.0),))

    rec = reconcile(policy, rows)

    assert [r.id for r in rec.uncovered] == ["NOVO11"] and not rec.consistent
    assert rec.total == pytest.approx(103000.0)


def test_a_line_whose_position_left_the_snapshot_is_reported(tmp_path):
    policy = _policy(tmp_path)
    rows = tuple(r for r in _rows(tmp_path) if r.id != "ISAE4")

    rec = reconcile(policy, rows)

    assert [ln.id for ln in rec.absent_lines] == ["ISAE4"] and not rec.consistent


def test_a_retired_position_that_reappears_is_flagged(tmp_path):
    policy = _policy(tmp_path)
    rows = _rows(tmp_path, extra=(("BTCI11", "BTCI11", "fii", 2500.0),))

    rec = reconcile(policy, rows)

    assert [r.id for r in rec.reopened] == ["BTCI11"] and not rec.consistent
    assert rec.uncovered == ()


def test_a_new_cd_counts_in_the_group_but_is_flagged_and_a_missing_one_too(tmp_path):
    policy = _policy(tmp_path)
    rows = _rows(
        tmp_path,
        rows=tuple(r for r in ROWS if r[0] != "RF-MP-115CDI"),
        extra=(("RF-NOVO-100CDI", "CDB Novo 100% CDI", "renda_fixa", 1500.0),),
    )

    rec = reconcile(policy, rows)

    assert [(g, r.id) for g, r in rec.new_members] == [
        (BANK_FIXED_INCOME_ID, "RF-NOVO-100CDI")
    ]
    assert (BANK_FIXED_INCOME_ID, "RF-MP-115CDI") in rec.missing_members
    group = next(w for w in rec.weights if w.line.id == BANK_FIXED_INCOME_ID)
    assert group.value == pytest.approx(
        9500.0
    )  # 8000 + 1500, o novo já conta na renda fixa


def test_the_legacy_alias_in_the_snapshot_reaches_the_canonical_line(tmp_path):
    policy = _policy(tmp_path)
    rows = tuple(
        replace(r, id="AXIA3") if r.id == "FMP-FGTS-DAYCOVAL" else r
        for r in _rows(tmp_path)
    )

    rec = reconcile(policy, rows)

    assert rec.uncovered == () and rec.absent_lines == ()


# --- the note -------------------------------------------------------------------------------


def _frontmatter(text):
    out = {}
    for line in text.split("---")[1].strip().splitlines():
        key, _, value = line.partition(": ")
        try:
            out[key] = json.loads(value)
        except json.JSONDecodeError:
            out[key] = value
    return out


def test_the_note_is_a_decision_table_with_empty_fields_and_states_its_limits(tmp_path):
    policy = _policy(tmp_path)
    text = render_policy_report(policy, reconcile(policy, _rows(tmp_path)), TODAY)

    fm = _frontmatter(text)
    assert fm["politica_status"] == "pendente" and fm["monitoramento_ativo"] is False
    assert fm["linhas"] == 8 and fm["linhas_por_status"] == {"pendente": 8}
    assert fm["posicoes_sem_linha"] == [] and fm["regra_de_soma"] is None
    assert "não compra, vende, aporta nem rebalanceia" in text
    assert (
        "Os campos vazios (—) são seus: nenhum percentual foi preenchido pelo IIP"
        in text
    )
    assert (
        "| Peso atual (base A) | Alvo | Tolerância | Mínimo | Máximo | Status |" in text
    )
    assert "| — | — | — | — | pendente |" in text
    assert "apelido legado: AXIA3" in text and "2 de 2 registros" in text
    assert "`BTCI11`: zerada em 2026-09-18" in text
    assert "Monitoramento** (sinalizar qualquer saída da faixa): desligado" in text


def test_the_note_reports_reconciliation_problems(tmp_path):
    policy = _policy(tmp_path)
    rows = _rows(tmp_path, extra=(("NOVO11", "NOVO11", "fii", 3000.0),))
    text = render_policy_report(policy, reconcile(policy, rows), TODAY)

    assert "Posição sem linha na política**: `NOVO11`" in text
    assert _frontmatter(text)["posicoes_sem_linha"] == ["NOVO11"]


def test_the_note_is_written_next_to_the_policy(tmp_path):
    policy = _policy(tmp_path)

    path = write_policy_report(
        tmp_path, policy, reconcile(policy, _rows(tmp_path)), TODAY
    )

    assert (
        path == tmp_path / "02_Portfolio" / "Politica_Pesos_Alvo.md" and path.exists()
    )


# --- CLI -----------------------------------------------------------------------------------


def _flat(text):
    """O texto sem espaços nem quebras: o rich quebra linhas longas (caminhos do runner)."""
    return "".join(text.split())


def _invoke(tmp_path, *args):
    return CliRunner().invoke(cli, ["target-policy", "--vault", str(tmp_path), *args])


def test_the_command_asks_for_init_when_there_is_no_policy(tmp_path):
    _write_snapshot(tmp_path)

    result = _invoke(tmp_path)

    assert result.exit_code == 1 and "--init" in _flat(result.output)
    assert load_policy(tmp_path) is None


def test_init_creates_the_empty_policy_and_the_note(tmp_path):
    _write_snapshot(tmp_path)

    result = _invoke(tmp_path, "--init", "--report")

    assert result.exit_code == 0, result.output
    policy = load_policy(tmp_path)
    assert len(policy.lines) == 8 and all(
        ln.numbers == (None,) * 4 for ln in policy.lines
    )
    assert (tmp_path / "02_Portfolio" / "Politica_Pesos_Alvo.md").exists()
    assert "Políticaesnapshotbatem" in _flat(result.output)
    assert "nadaécomprado,vendido,aportadonemrebalanceado" in _flat(result.output)


def test_init_never_overwrites_a_policy_the_user_edited(tmp_path):
    _write_snapshot(tmp_path)
    _invoke(tmp_path, "--init")
    path = tmp_path / "02_Portfolio" / "Politica_Pesos_Alvo.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    _line(payload, target_pct=12.5, tolerance_pp=2, min_pct=8, max_pct=15)
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = _invoke(tmp_path, "--init")

    assert result.exit_code == 0
    assert load_policy(tmp_path).lines[0].target_pct == 12.5


def test_an_invalid_policy_stops_the_command_with_the_reason(tmp_path):
    _write_snapshot(tmp_path)
    _write_policy(tmp_path, lambda p: _line(p, min_pct=9, max_pct=3))

    result = _invoke(tmp_path, "--report")

    assert result.exit_code == 1
    assert "Políticadepesos-alvoinválida" in _flat(
        result.output
    ) and "maiorquemax_pct" in _flat(result.output)
    assert not (tmp_path / "02_Portfolio" / "Politica_Pesos_Alvo.md").exists()


def test_a_missing_snapshot_stops_the_command_with_the_reason(tmp_path):
    result = _invoke(tmp_path, "--init")

    assert result.exit_code == 1 and "Políticadepesos-alvoinválida" in _flat(
        result.output
    )
    assert "Current.md" in _flat(result.output)
    assert "arquivodosnapshotnãoencontrado" in _flat(result.output)


def test_a_reconciliation_problem_is_a_warning_not_a_failure(tmp_path):
    _write_snapshot(tmp_path)
    _invoke(tmp_path, "--init")
    _write_snapshot(tmp_path, extra=(("NOVO11", "NOVO11", "fii", 3000.0),))

    result = _invoke(tmp_path)

    assert result.exit_code == 0
    assert (
        "Posiçãosemlinhanapolítica" in _flat(result.output)
        and "NOVO11" in result.output
    )


# --- limits: a policy layer, separate from decisions, contributions and rebalancing --------

_FORBIDDEN = (
    "iip.decision",
    "iip.integration",
    "iip.strategy",
    "iip.orchestration",
    "iip.portfolio_decision",
    "iip.portfolio.batch_decide",
    "iip.portfolio.decision_alerts",
    "iip.portfolio.exposure",
    "iip.portfolio.income",
    "iip.knowledge",
    "iip.macro",
)


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_the_policy_code_does_not_import_decision_contribution_or_rebalancing_code():
    root = Path("src/iip")
    files = [
        root / "portfolio" / "target_policy.py",
        root / "obsidian" / "target_policy_report.py",
        root / "portfolio" / "monitoring_event.py",
        root / "obsidian" / "monitoring_event_report.py",
    ]

    offenders = {
        (f.name, name)
        for f in files
        for name in _imports(f)
        if any(name == bad or name.startswith(bad + ".") for bad in _FORBIDDEN)
    }

    assert offenders == set()


def test_only_the_command_and_the_note_use_the_policy_module():
    users = {
        str(path).replace("\\", "/")
        for path in Path("src/iip").rglob("*.py")
        if any(n.startswith("iip.portfolio.target_policy") for n in _imports(path))
    }

    # o layers.py só LÊ os tipos da política (alvos definidos, para as camadas); não a grava
    # monitoring_event.py é a camada de leitura estruturada do monitoramento: só usa
    # reconcile()/read_weight() (puro, sem I/O). monitoring_event_report.py é a nota do vault
    # que ela alimenta (comando `iip monitoring-events --report`, manual, fora do job diário) --
    # ver test_monitoring_event.py
    assert users == {
        "src/iip/obsidian/target_policy_report.py",
        "src/iip/obsidian/monitoring_event_report.py",
        "src/iip/portfolio/layers.py",
        "src/iip/portfolio/monitoring_event.py",
        "src/iip/cli/main.py",
    }


def test_the_daily_job_does_not_run_the_policy_or_any_monitoring():
    script = Path("executar_atualizacao_diaria.ps1").read_text(encoding="utf-8")

    assert "target-policy" not in script


def test_the_policy_carries_no_retired_id_as_a_line_and_retired_is_typed():
    assert RetiredPosition("X", "2026-01-01").note == ""
    assert PolicyLine("A", "A", "acao").status == "pendente"
    assert (
        TargetPolicy("v", "o", (PolicyLine("A", "A", "acao"),)).monitoring_enabled
        is False
    )


# --- the individual-references sum rule ----------------------------------------------------


def _over_100(policy):
    """Todas as linhas com alvo 30 (soma 240%), cada uma válida por si só."""
    lines = tuple(
        _defined(ln, target=30.0, tolerance=2.0, low=20.0, high=40.0)
        for ln in policy.lines
    )
    return replace(policy, lines=lines)


def test_the_individual_references_rule_lets_the_targets_sum_past_100(tmp_path):
    policy = _over_100(_policy(tmp_path))

    validate(replace(policy, sum_rule="referencias_individuais"))


@pytest.mark.parametrize("rule", [None, "total_100", "reserva"])
def test_without_the_explicit_rule_the_sum_past_100_is_still_refused(tmp_path, rule):
    policy = _over_100(_policy(tmp_path))

    with pytest.raises(ValueError, match="passa de 100%"):
        validate(replace(policy, sum_rule=rule))


def test_each_line_is_still_validated_under_the_individual_references_rule(tmp_path):
    policy = _policy(tmp_path)
    broken = replace(
        policy,
        sum_rule="referencias_individuais",
        lines=(
            _defined(policy.lines[0], target=5.0, tolerance=2.0, low=3.0, high=5.0),
            *policy.lines[1:],
        ),
    )

    with pytest.raises(ValueError, match="acima do máximo|passa do máximo|fica acima"):
        validate(broken)


def test_the_individual_references_rule_can_be_approved_with_a_sum_past_100(tmp_path):
    policy = _over_100(_policy(tmp_path))
    approved = replace(
        policy, approval_status="aprovada", sum_rule="referencias_individuais"
    )

    validate(approved)
    save_policy(tmp_path, approved)
    loaded = load_policy(tmp_path)
    assert loaded.sum_rule == "referencias_individuais"
    assert loaded.monitoring_enabled is False  # aprovar não liga o monitoramento


def test_the_individual_references_rule_does_not_switch_monitoring_on(tmp_path):
    policy = _policy(tmp_path)

    assert (
        replace(policy, sum_rule="referencias_individuais").monitoring_enabled is False
    )
    with pytest.raises(ValueError, match="só pode ligar com a política aprovada"):
        validate(
            replace(
                _over_100(policy),
                sum_rule="referencias_individuais",
                monitoring_enabled=True,
            )
        )


def test_the_rule_changes_the_policy_hash_and_survives_a_round_trip(tmp_path):
    policy = _over_100(_policy(tmp_path))
    with_rule = replace(policy, sum_rule="referencias_individuais")

    assert with_rule.content_hash != policy.content_hash
    save_policy(tmp_path, with_rule)
    assert load_policy(tmp_path).content_hash == with_rule.content_hash


def test_the_target_sum_ignores_inactive_lines_and_lines_without_a_target(tmp_path):
    from iip.portfolio.target_policy import target_sum

    policy = _policy(tmp_path)
    assert target_sum(policy) == 0
    mixed = replace(
        policy,
        lines=(
            _defined(policy.lines[0], target=5.0),
            replace(_defined(policy.lines[1], target=7.0), status="inativo"),
            *policy.lines[2:],
        ),
    )

    assert target_sum(mixed) == 5.0


def test_the_note_shows_the_sum_as_informative_under_the_individual_rule(tmp_path):
    policy = replace(_over_100(_policy(tmp_path)), sum_rule="referencias_individuais")

    text = render_policy_report(policy, reconcile(policy, _rows(tmp_path)), TODAY)

    assert "referências individuais por ativo, não uma carteira-alvo" in text
    assert "soma atual dos alvos individuais definidos: 240%, informativa" in text
    assert "desligado" in text  # o monitoramento segue desligado


def test_the_command_says_the_sum_is_informative_under_the_individual_rule(tmp_path):
    _write_snapshot(tmp_path)
    save_policy(
        tmp_path,
        replace(_over_100(_policy(tmp_path)), sum_rule="referencias_individuais"),
    )

    result = _invoke(tmp_path)

    assert result.exit_code == 0, result.output
    flat = _flat(result.output)
    assert "regradesoma:referencias_individuais" in flat
    assert "240%(informativa" in flat
