import ast
import datetime as dt
import json
from dataclasses import replace
from pathlib import Path

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.obsidian.layers_report import render_layers_report, write_layers_report
from iip.portfolio.layers import UNCLASSIFIED, build_layers
from iip.portfolio.registry import get_asset
from iip.portfolio.target_policy import (
    SnapshotRow,
    build_initial_policy,
    save_policy,
)

TODAY = dt.date(2026, 9, 20)
HEADER = (
    "| ID | Ativo | Classe | Quantidade | PM | Preço atual | Valor | Peso | Peso alvo | "
    "Status |"
)

# tickers reais do registro, com valores redondos: o total é R$ 100.000
ROWS = (
    SnapshotRow("BBSE3", "BBSE3", "acao", 40000.0),
    SnapshotRow("CXSE3", "CXSE3", "acao", 10000.0),
    SnapshotRow("ISAE4", "ISAE4", "acao", 10000.0),
    SnapshotRow("LVBI11", "LVBI11", "fii", 15000.0),
    SnapshotRow("HGCR11", "HGCR11", "fii", 5000.0),
    SnapshotRow("CDII11", "CDII11", "fi-infra", 6000.0),
    SnapshotRow("CRAA11", "CRAA11", "fiagro", 2000.0),
    SnapshotRow("LFTB11", "LFTB11", "etf", 4000.0),
    SnapshotRow("FMP-FGTS-DAYCOVAL", "DAYCOVAL FMP-FGTS", "fundo", 3000.0),
    SnapshotRow("RF-A", "CDB A", "renda_fixa", 3000.0),
    SnapshotRow("RF-B", "CDB B", "renda_fixa", 2000.0),
)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _group(groups, label):
    return next(g for g in groups if g.label == label)


def _defined(line, target):
    return replace(
        line,
        target_pct=target,
        tolerance_pp=1.0,
        min_pct=max(target - 2, 0),
        max_pct=target + 2,
        status="definido",
        decided_on="2026-09-20",
    )


def _policy_with(targets):
    policy = build_initial_policy(ROWS, version="teste.1")
    lines = tuple(
        _defined(ln, targets[ln.id]) if ln.id in targets else ln for ln in policy.lines
    )
    return replace(policy, lines=lines)


# --- layer 1 and 2: class and asset --------------------------------------------------------


def test_layer_1_shows_each_class_over_the_total():
    layers = build_layers(ROWS)

    by = {g.label: g for g in layers.classes}
    assert layers.total == pytest.approx(100000.0)
    assert by["Ações"].weight_total_pct == pytest.approx(60.0)
    assert by["FIIs"].weight_total_pct == pytest.approx(20.0)
    assert by["FI-Infra"].weight_total_pct == pytest.approx(6.0)
    assert by["FIAgro"].weight_total_pct == pytest.approx(2.0)
    assert by["ETFs"].weight_total_pct == pytest.approx(4.0)
    assert by["Fundos (FMP-FGTS)"].weight_total_pct == pytest.approx(3.0)
    assert by["Renda fixa bancária"].weight_total_pct == pytest.approx(5.0)
    assert sum(g.weight_total_pct for g in layers.classes) == pytest.approx(100.0)
    assert layers.classes[0].label == "Ações"  # do maior para o menor


def test_layer_2_groups_the_cds_in_one_line_like_the_policy():
    layers = build_layers(ROWS)

    ids = [h.id for h in layers.assets]
    assert len(layers.assets) == 10  # 11 linhas do snapshot, 2 CDBs viram 1
    assert "RF-BANCARIA" in ids and "RF-A" not in ids
    bank = next(h for h in layers.assets if h.id == "RF-BANCARIA")
    assert bank.members == ("RF-A", "RF-B") and bank.value == pytest.approx(5000.0)
    assert layers.position_count == len(ROWS)


def test_the_same_asset_carries_a_different_denominator_in_each_layer():
    layers = build_layers(ROWS)
    bbse3 = next(h for h in layers.stocks.holdings if h.id == "BBSE3")

    assert bbse3.weight_total_pct == pytest.approx(40.0)  # do patrimônio
    assert layers.stocks.weight_group_pct(bbse3) == pytest.approx(
        66.667, abs=1e-2
    )  # das ações
    financeiro = _group(layers.stock_sectors, "Financeiro")
    assert financeiro.weight_group_pct(bbse3) == pytest.approx(80.0)  # do setor
    segmento = _group(layers.stock_segments, "Previdência e Seguros")
    assert segmento.weight_group_pct(bbse3) == pytest.approx(80.0)  # do segmento


# --- layers 3, 4 and 5: stocks ------------------------------------------------------------


def test_layer_3_is_the_stock_class_with_the_share_inside_it():
    layers = build_layers(ROWS)

    assert layers.stocks.value == pytest.approx(60000.0)
    assert [h.id for h in layers.stocks.holdings] == ["BBSE3", "CXSE3", "ISAE4"]
    assert {h.asset_class for h in layers.stocks.holdings} == {"acao"}


def test_layer_4_groups_stocks_by_the_registry_sector():
    layers = build_layers(ROWS)

    financeiro = _group(layers.stock_sectors, "Financeiro")
    utilidade = _group(layers.stock_sectors, "Utilidade Pública")
    assert get_asset("BBSE3").sector == "Financeiro"
    assert (financeiro.weight_total_pct, financeiro.weight_class_pct) == (
        pytest.approx(50.0),
        pytest.approx(83.333, abs=1e-2),
    )
    assert utilidade.weight_total_pct == pytest.approx(10.0)
    assert {h.id for h in financeiro.holdings} == {"BBSE3", "CXSE3"}


def test_layer_5_groups_stocks_by_segment_and_keeps_the_parent_sector():
    layers = build_layers(ROWS)

    seguros = _group(layers.stock_segments, "Previdência e Seguros")
    energia = _group(layers.stock_segments, "Energia Elétrica")
    assert seguros.parent == "Financeiro" and energia.parent == "Utilidade Pública"
    assert seguros.weight_total_pct == pytest.approx(50.0)
    assert energia.weight_class_pct == pytest.approx(16.667, abs=1e-2)


# --- layer 6: only real estate funds ------------------------------------------------------


def test_layer_6_has_only_real_estate_funds_and_the_infra_and_agro_classes_stay_apart():
    layers = build_layers(ROWS)

    fii_ids = {h.id for h in layers.fiis.holdings}
    assert fii_ids == {"LVBI11", "HGCR11"}
    assert not fii_ids & {"CDII11", "CRAA11"}  # FI-Infra e FIAgro: classes próprias
    assert layers.fiis.weight_total_pct == pytest.approx(20.0)
    assert {g.label for g in layers.classes} >= {"FI-Infra", "FIAgro"}


def test_layer_6_splits_the_funds_by_registry_type_and_segment():
    layers = build_layers(ROWS)

    tijolo = _group(layers.fii_types, get_asset("LVBI11").structure)
    papel = _group(layers.fii_types, get_asset("HGCR11").structure)
    assert tijolo.weight_class_pct == pytest.approx(75.0)  # dentro dos FIIs
    assert papel.weight_total_pct == pytest.approx(5.0)  # no patrimônio
    logistico = _group(layers.fii_segments, get_asset("LVBI11").segment)
    assert logistico.value == pytest.approx(15000.0)


def test_etf_fmp_and_cds_appear_only_in_the_class_and_asset_layers():
    layers = build_layers(ROWS)

    in_layers_3_to_6 = {
        h.id
        for g in (layers.stocks, layers.fiis, *layers.stock_sectors, *layers.fii_types)
        for h in g.holdings
    }
    assert not in_layers_3_to_6 & {"LFTB11", "FMP-FGTS-DAYCOVAL", "RF-BANCARIA"}
    assert {"LFTB11", "FMP-FGTS-DAYCOVAL", "RF-BANCARIA"} <= {
        h.id for h in layers.assets
    }


def test_the_fgts_fund_uses_the_canonical_id_and_needs_no_stock_classification():
    layers = build_layers(ROWS)

    fund = next(h for h in layers.assets if h.id == "FMP-FGTS-DAYCOVAL")
    assert fund.asset_class == "fundo" and fund.sector == ""  # não é ação: sem setor
    assert layers.unclassified == ()


def test_an_asset_missing_from_the_registry_is_shown_as_unclassified_never_hidden():
    rows = (*ROWS, SnapshotRow("ZZZZ3", "ZZZZ3", "acao", 1000.0))

    layers = build_layers(rows)

    assert layers.unclassified == ("ZZZZ3",)
    sem = _group(layers.stock_sectors, UNCLASSIFIED)
    assert [h.id for h in sem.holdings] == ["ZZZZ3"]
    assert sum(g.weight_total_pct for g in layers.stock_sectors) == pytest.approx(
        layers.stocks.weight_total_pct
    )


def test_a_snapshot_without_value_is_an_error_and_missing_classes_are_none():
    with pytest.raises(ValueError, match="nada a mostrar"):
        build_layers((SnapshotRow("BBSE3", "BBSE3", "acao", 0.0),))

    only_bonds = build_layers((SnapshotRow("RF-A", "CDB", "renda_fixa", 100.0),))
    assert only_bonds.stocks is None and only_bonds.fiis is None
    assert only_bonds.stock_sectors == () and only_bonds.fii_types == ()


# --- derived targets: only when every asset in the group is defined -----------------------


def test_without_a_policy_or_with_no_target_defined_everything_is_pending():
    for policy in (None, build_initial_policy(ROWS, version="t")):
        layers = build_layers(ROWS, policy)

        assert all(h.target_pct is None for h in layers.assets)
        assert all(g.target.state == "pendente" for g in layers.classes)
        assert layers.class_targets["acao"].sum_pct is None


def test_a_group_is_partial_until_every_asset_in_it_has_a_defined_target():
    layers = build_layers(ROWS, _policy_with({"BBSE3": 10.0}))

    acoes = layers.class_targets["acao"]
    assert (acoes.members, acoes.defined, acoes.sum_pct, acoes.state) == (
        3,
        1,
        10.0,
        "parcial",
    )
    financeiro = _group(layers.stock_sectors, "Financeiro")
    assert financeiro.target.state == "parcial" and financeiro.target.sum_pct == 10.0


def test_the_sector_total_is_complete_only_when_all_its_assets_are_defined():
    layers = build_layers(ROWS, _policy_with({"BBSE3": 10.0, "CXSE3": 5.0}))

    financeiro = _group(layers.stock_sectors, "Financeiro")
    assert (financeiro.target.state, financeiro.target.sum_pct) == ("completo", 15.0)
    assert _group(layers.stock_sectors, "Utilidade Pública").target.state == "pendente"
    assert layers.class_targets["acao"].state == "parcial"  # ISAE4 ainda falta


def test_the_share_inside_the_class_needs_the_whole_class_defined():
    partial = build_layers(ROWS, _policy_with({"BBSE3": 10.0, "CXSE3": 5.0}))
    bbse3 = next(h for h in partial.assets if h.id == "BBSE3")
    assert partial.derived_class_share(bbse3) is None  # falta o ISAE4

    complete = build_layers(
        ROWS, _policy_with({"BBSE3": 10.0, "CXSE3": 5.0, "ISAE4": 5.0})
    )
    bbse3 = next(h for h in complete.assets if h.id == "BBSE3")
    assert complete.derived_class_share(bbse3) == pytest.approx(50.0)  # 10 de 20


def test_a_target_on_a_line_that_is_not_definido_does_not_count():
    policy = build_initial_policy(ROWS, version="t")
    lines = tuple(
        replace(ln, target_pct=9.0) if ln.id == "BBSE3" else ln for ln in policy.lines
    )  # alvo solto numa linha ainda pendente

    layers = build_layers(ROWS, replace(policy, lines=lines))

    assert next(h for h in layers.assets if h.id == "BBSE3").target_pct is None


def test_building_the_layers_never_touches_the_policy():
    policy = _policy_with({"BBSE3": 10.0})
    before = policy.content_hash

    build_layers(ROWS, policy)

    assert policy.content_hash == before and policy.monitoring_enabled is False


# --- the note ----------------------------------------------------------------------------


def _note(policy=None, **kwargs):
    return render_layers_report(
        build_layers(ROWS, policy),
        today=TODAY,
        snapshot_date=TODAY,
        policy_hash=policy.content_hash if policy else None,
        policy_status=policy.approval_status if policy else None,
        **kwargs,
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


def test_the_note_names_the_denominator_of_every_percentage_column():
    text = _note()

    assert "## Como ler os percentuais" in text
    for name in (
        "peso_total_pct",
        "peso_classe_pct",
        "peso_setor_pct",
        "peso_segmento_pct",
    ):
        assert f"`{name}`" in text or name in text
    assert "o patrimônio total, a base A" in text
    assert "R$ 100.000,00" in text


def test_the_note_has_the_six_layers():
    text = _note()

    for heading in (
        "## 1. Patrimônio por classe",
        "## 2. Patrimônio por ativo",
        "## 3. Ações — consolidado",
        "## 4. Ações — por setor",
        "## 5. Ações — por segmento",
        "## 6. FIIs — consolidado, tipo e segmento",
        "### Por tipo",
        "### Por segmento",
    ):
        assert heading in text


def test_the_note_shows_bbse3_in_each_layer_without_mixing_the_denominators():
    text = _note()

    assert "| `BBSE3` | Ações | R$ 40.000,00 | 40,00% | 66,67% |" in text  # camada 2
    assert "| Financeiro | `BBSE3` | 40,00% | 66,67% | 80,00% |" in text  # camada 4
    assert (
        "| Previdência e Seguros | `BBSE3` | 40,00% | 66,67% | 80,00% |" in text
    )  # camada 5


def test_the_note_separates_current_weight_from_target_and_marks_what_is_pending():
    text = _note(_policy_with({"BBSE3": 10.0}))

    assert (
        "| `BBSE3` | Ações | R$ 40.000,00 | 40,00% | 66,67% | 10,00% | pendente |"
        in text
    )
    assert "parcial: 10,00% (1 de 3 definidos)" in text
    assert "pendente (0 de 1 definidos)" in text
    assert "(hoje pendente)" in text
    assert _fm(text)["ativos_com_alvo_definido"] == 1


def test_the_note_states_it_is_read_only_and_has_no_layer_limits():
    text = _note()

    assert "É só LEITURA do peso ATUAL" in text
    assert (
        "não define alvo nem limite" in text
        and "não decide, aporta nem rebalanceia" in text
    )
    assert "**Limites por camada:** não existem" in text
    assert "FI-Infra, FIAgro, ETF, FMP-FGTS e os CDBs só têm as camadas 1 e 2" in text
    assert "(ainda não criada)" in text  # sem política


def test_the_note_frontmatter_and_the_unclassified_notice():
    rows = (*ROWS, SnapshotRow("ZZZZ3", "ZZZZ3", "acao", 1000.0))
    text = render_layers_report(build_layers(rows), today=TODAY, snapshot_date=TODAY)

    fm = _fm(text)
    assert fm["posicoes"] == 12 and fm["linhas_de_ativo"] == 11
    assert fm["ativos_sem_classificacao"] == ["ZZZZ3"]
    assert {c["classe"] for c in fm["classes"]} >= {"Ações", "FIIs", "FI-Infra"}
    assert "Sem classificação no registro: `ZZZZ3`" in text


def test_the_note_is_written_next_to_the_other_portfolio_notes(tmp_path):
    path = write_layers_report(tmp_path, build_layers(ROWS), today=TODAY)

    assert path == tmp_path / "02_Portfolio" / "Camadas.md" and path.exists()


# --- CLI -----------------------------------------------------------------------------------


def _vault(tmp_path):
    lines = [HEADER, "|---|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for row in ROWS:
        value = (
            f"R$ {row.value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        lines.append(
            f"| {row.id} | {row.name} | {row.asset_class} |  |  |  | {value} | 0,00% |  | active |"
        )
    path = tmp_path / "02_Portfolio" / "Current.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path


def _flat(text):
    return "".join(text.split())


def test_the_command_shows_the_layers_without_a_policy(tmp_path):
    result = CliRunner().invoke(
        cli, ["portfolio-layers", "--vault", str(_vault(tmp_path))]
    )

    assert result.exit_code == 0, result.output
    flat = _flat(result.output)
    assert "peso_total_pct" in flat and "peso_classe_pct" in flat
    assert "sempolítica" in flat and "nadaédefinido,sinalizado" in flat


def test_the_command_writes_the_note_and_leaves_the_policy_untouched(tmp_path):
    vault = _vault(tmp_path)
    policy_path = save_policy(vault, build_initial_policy(ROWS, version="teste.1"))
    before = policy_path.read_bytes()

    result = CliRunner().invoke(
        cli, ["portfolio-layers", "--vault", str(vault), "--report"]
    )

    assert result.exit_code == 0, result.output
    assert (vault / "02_Portfolio" / "Camadas.md").exists()
    assert policy_path.read_bytes() == before  # a política não é tocada
    assert "0comalvodefinido" in _flat(result.output)


def test_the_command_stops_with_the_reason_when_the_snapshot_is_missing(tmp_path):
    result = CliRunner().invoke(cli, ["portfolio-layers", "--vault", str(tmp_path)])

    assert result.exit_code == 1 and "Camadasdopatrimônio" in _flat(result.output)


# --- limits: read only, no decisions, contributions, rebalancing or new limits ------------

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


def test_the_layers_code_does_not_import_decision_contribution_or_rebalancing_code():
    files = [
        Path("src/iip/portfolio/layers.py"),
        Path("src/iip/obsidian/layers_report.py"),
    ]

    offenders = {
        (f.name, name)
        for f in files
        for name in _imports(f)
        if any(name == bad or name.startswith(bad + ".") for bad in _FORBIDDEN)
    }

    assert offenders == set()


def test_the_layers_code_only_reads_the_policy_it_never_saves_or_edits_it():
    for path in (
        Path("src/iip/portfolio/layers.py"),
        Path("src/iip/obsidian/layers_report.py"),
    ):
        names = {
            node.id
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig")))
            if isinstance(node, ast.Name)
        } | {
            node.attr
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig")))
            if isinstance(node, ast.Attribute)
        }
        # ler a política é do comando; gravá-la ou editá-la não é de nenhum dos dois módulos
        assert not names & {"save_policy", "load_policy"}, path


def test_only_the_command_and_the_note_use_the_layers_and_the_job_does_not_run_them():
    users = {
        str(path).replace("\\", "/")
        for path in Path("src/iip").rglob("*.py")
        if any(n.startswith("iip.portfolio.layers") for n in _imports(path))
    }

    assert users == {"src/iip/obsidian/layers_report.py", "src/iip/cli/main.py"}
    assert "portfolio-layers" not in Path("executar_atualizacao_diaria.ps1").read_text(
        encoding="utf-8"
    )
