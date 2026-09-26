"""APORTE_PROPOSTO_V1 rev. 4: contrato, rodada completa, pré-condições, exclusões,
distribuição, invariantes, leitura do vault, relatório, comando manual e guards de arquitetura.

Contrato vinculante: SHA-256 63bbeda126534b80716bf4b477bedc1d530db4c44d09dea2e47f91ebc905f7a0.
"""

from __future__ import annotations

import ast
import datetime as dt
import json
from dataclasses import replace
from pathlib import Path

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.obsidian.aporte_report import render_aporte_report, write_aporte_report
from iip.portfolio import aporte as A
from iip.portfolio.aporte_contract import (
    CONTRACT_RELATIVE_PATH,
    AporteContract,
    build_contract,
    load_contract,
    save_contract,
    validate,
)
from iip.portfolio.class_budget import (
    CLASS_IDS,
    ClassBudget,
    ClassBudgetLine,
    save_budget,
)
from iip.portfolio.target_policy import (
    PolicyLine,
    RetiredPosition,
    SnapshotRow,
    TargetPolicy,
    save_policy,
)

CYCLE = "2026-09"
ROUND = "2026-09-26"

# --- fixtures em memória -------------------------------------------------------------------


def _contract(**changes) -> AporteContract:
    return replace(
        build_contract(), approval_status="aprovada", decided_on="2026-09-26", **changes
    )


def _asset(line_id, asset_class, target=5.0, **changes) -> PolicyLine:
    return replace(
        PolicyLine(
            line_id,
            line_id,
            asset_class,
            target_pct=target,
            tolerance_pp=1.0,
            min_pct=0.0,
            max_pct=10.0,
            status="definido",
            decided_on="2026-09-01",
        ),
        **changes,
    )


GROUP = PolicyLine(
    "RF-BANCARIA",
    "Renda fixa bancária",
    "renda_fixa",
    kind="group",
    members=("RF-1",),
    target_pct=8.0,
    tolerance_pp=2.0,
    min_pct=0.0,
    max_pct=70.0,
    status="definido",
    decided_on="2026-09-01",
)


def _policy(*extra: PolicyLine, lines=None, **changes) -> TargetPolicy:
    base = lines or (
        _asset("AAA11", "fii"),
        _asset("BBB11", "fii"),
        _asset("CCC3", "acao"),
        _asset("DDD3", "acao"),
        GROUP,
    )
    return replace(
        TargetPolicy(
            version="teste.1",
            origin="teste",
            lines=(*base, *extra),
            retired=(RetiredPosition("OLD11", "2026-09-01"),),
            approval_status="aprovada",
            sum_rule="referencias_individuais",
        ),
        **changes,
    )


_CLASS_NUMBERS = {
    "acao": (45.0, 5.0, 35.0, 50.0),
    "fii": (34.0, 4.0, 28.0, 40.0),
    "fi-infra": (8.0, 2.0, 4.0, 12.0),
    "fiagro": (2.0, 1.0, 0.0, 4.0),
    "renda_fixa": (8.0, 2.0, 4.0, 70.0),
    "etf": (0.0, 0.0, 0.0, 4.0),
    "fundo": (3.0, 1.0, 1.0, 5.0),
}


def _budget(**overrides) -> ClassBudget:
    lines = []
    for class_id in CLASS_IDS:
        target, tol, low, high = overrides.get(class_id, _CLASS_NUMBERS[class_id])
        lines.append(
            ClassBudgetLine(
                class_id, target, tol, low, high, "definido", "", "2026-09-01"
            )
        )
    return ClassBudget("teste.1", "teste", tuple(lines), approval_status="aprovada")


def _rows(**values) -> tuple[SnapshotRow, ...]:
    base = {
        "AAA11": ("fii", 1_000.0),
        "BBB11": ("fii", 2_000.0),
        "CCC3": ("acao", 3_000.0),
        "DDD3": ("acao", 30_000.0),
        "RF-1": ("renda_fixa", 64_000.0),
    }
    base.update(values)
    return tuple(SnapshotRow(i, i, klass, value) for i, (klass, value) in base.items())


def _dec(ticker, verdict="MANTER", score=7.0, date=ROUND) -> A.DecisionNote:
    return A.DecisionNote(ticker, date, verdict, score, f"DEC-{ticker}-{date}.md")


def _decisions(date=ROUND, **verdicts) -> tuple[A.DecisionNote, ...]:
    base = {
        "AAA11": ("MANTER", 7.0),
        "BBB11": ("MANTER", 7.0),
        "CCC3": ("COMPRAR", 6.0),
        "DDD3": ("MANTER", 8.0),
    }
    base.update(verdicts)
    return tuple(_dec(t, v, s, date) for t, (v, s) in base.items())


def _inputs(**changes) -> A.AporteInputs:
    base = A.AporteInputs(
        cycle=CYCLE,
        contract=_contract(),
        policy=_policy(),
        budget=_budget(),
        rows=_rows(),
        current_snapshot_date=dt.date(2026, 9, 21),
        decisions=_decisions(),
        price_snapshot_date=dt.date(2026, 9, 26),
        prices={"AAA11": 10.0, "BBB11": 100.0, "CCC3": 30.0, "DDD3": 20.0},
    )
    return replace(base, **changes)


def _reasons(proposal) -> dict[str, str]:
    return {e.ticker: e.reason for e in proposal.exclusions}


# --- contrato (§2, §14) --------------------------------------------------------------------


def test_the_built_contract_is_the_rev4_v1_and_is_born_pending():
    contract = build_contract()

    validate(contract)
    assert contract.approval_status == "pendente"
    assert contract.monthly_budget_brl == 1350.0
    assert contract.eligible_verdicts == ("COMPRAR", "MANTER")
    assert contract.vetoed_verdicts == ("AGUARDAR", "REDUZIR", "ENCERRAR", "AUMENTAR")
    assert contract.monthly_asset_cap_brl == pytest.approx(337.5)
    assert contract.automatic_action == "nenhuma"
    assert contract.trigger == "manual_command"
    assert len(contract.content_hash) == 16


@pytest.mark.parametrize(
    "changes",
    [
        {"monthly_budget_brl": 0.0},
        {"monthly_budget_brl": float("nan")},
        {"intrinsic_weight": 0.8},
        {"intrinsic_weight": 1.5, "gap_weight": -0.5},
        {"income_component": True},
        {"monthly_asset_cap_pct": 0.0},
        {"monthly_asset_cap_pct": 101.0},
        {"decision_score_persistence": "optional"},
        {"decision_fallback": "previous_date"},
        {"class_source": "current_snapshot"},
        {"trigger": "scheduler"},
        {"automatic_action": "executar"},
        {"version": "2"},
        {
            "eligible_verdicts": ("COMPRAR", "MANTER", "AUMENTAR"),
            "vetoed_verdicts": ("AGUARDAR", "REDUZIR", "ENCERRAR"),
        },
        {"vetoed_verdicts": ("AGUARDAR", "REDUZIR", "VENDER", "AUMENTAR")},
        {"vetoed_verdicts": ("AGUARDAR", "REDUZIR", "AUMENTAR")},
        {"eligible_verdicts": ("COMPRAR", "MANTER", "AGUARDAR")},
        {"eligible_verdicts": ("MANTER", "MANTER")},
        {"vetoed_verdicts": ("AGUARDAR", "REDUZIR", "ENCERRAR", "AUMENTAR", "XPTO")},
        {"approval_status": "ativada"},
        {"approval_status": "aprovada", "decided_on": None},
        {"decided_on": "26/09/2026"},
    ],
)
def test_the_contract_is_rejected_by_every_rule_of_section_14(changes):
    with pytest.raises(ValueError):
        validate(replace(build_contract(), **changes))


def test_the_contract_hash_ignores_the_origin_and_changes_with_content():
    contract = build_contract()

    assert replace(contract, origin="outra").content_hash == contract.content_hash
    assert (
        replace(contract, monthly_budget_brl=1000.0).content_hash
        != contract.content_hash
    )


def test_the_contract_round_trips_and_loads_strictly(tmp_path):
    save_contract(tmp_path, _contract())
    assert load_contract(tmp_path) == _contract()
    assert load_contract(tmp_path / "sem_vault") is None

    path = tmp_path / CONTRACT_RELATIVE_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    for broken in (
        {**raw, "extra": 1},
        {k: v for k, v in raw.items() if k != "trigger"},
        {**raw, "type": "outro"},
        {**raw, "eligible_verdicts": "COMPRAR"},
        {**raw, "automatic_action": "executar"},
    ):
        path.write_text(json.dumps(broken), encoding="utf-8")
        with pytest.raises(ValueError):
            load_contract(tmp_path)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        load_contract(tmp_path)


# --- rodada completa (§3.1) ----------------------------------------------------------------


def test_the_round_is_the_latest_date_where_the_whole_universe_has_a_scored_dec():
    decisions = (*_decisions("2026-09-20"), *_decisions(ROUND))

    round_ = A.find_decision_round(_policy(), decisions, CYCLE)

    assert round_.date == ROUND
    assert set(round_.decisions) == {"AAA11", "BBB11", "CCC3", "DDD3"}
    assert round_.universe_size == 4  # o grupo RF-BANCARIA fica fora do universo
    assert round_.discarded == ()


def test_a_partial_ticker_run_on_a_later_date_does_not_form_a_round():
    decisions = (*_decisions(ROUND), _dec("AAA11", date="2026-09-27"))

    round_ = A.find_decision_round(_policy(), decisions, CYCLE)

    assert round_.date == ROUND
    [discarded] = round_.discarded
    assert discarded.date == "2026-09-27"
    assert ("BBB11", A.ROUND_MISSING) in discarded.problems


def test_there_is_no_fallback_per_asset_the_whole_round_moves():
    later = tuple(n for n in _decisions("2026-09-27") if n.ticker != "CCC3")
    decisions = (*_decisions("2026-09-20"), *later)

    round_ = A.find_decision_round(_policy(), decisions, CYCLE)

    assert round_.date == "2026-09-20"
    assert all(n.date == "2026-09-20" for n in round_.decisions.values())


@pytest.mark.parametrize(
    ("bad", "problem"),
    [
        (_dec("AAA11", score=None), A.ROUND_NO_SCORE),
        (_dec("AAA11", score=float("inf")), A.ROUND_NO_SCORE),
        (_dec("AAA11", verdict="VENDER"), A.ROUND_BAD_VERDICT),
    ],
)
def test_a_date_with_an_invalid_dec_is_not_a_round(bad, problem):
    decisions = (*(n for n in _decisions() if n.ticker != "AAA11"), bad)

    round_ = A.find_decision_round(_policy(), decisions, CYCLE)

    assert round_.date is None
    assert ("AAA11", problem) in round_.discarded[0].problems


def test_two_decs_for_one_line_via_id_and_alias_make_the_date_incomplete():
    policy = _policy(
        lines=(
            _asset("FMP-FGTS", "fundo", aliases=("AXIA3",)),
            _asset("AAA11", "fii"),
        )
    )
    decisions = (_dec("FMP-FGTS"), _dec("AXIA3"), _dec("AAA11"))

    round_ = A.find_decision_round(policy, decisions, CYCLE)

    assert round_.date is None
    assert ("FMP-FGTS", A.ROUND_DUPLICATED) in round_.discarded[0].problems


def test_the_alias_links_a_dec_to_its_policy_line():
    policy = _policy(lines=(_asset("FMP-FGTS", "fundo", aliases=("AXIA3",)),))

    round_ = A.find_decision_round(policy, (_dec("AXIA3"),), CYCLE)

    assert round_.decisions["FMP-FGTS"].ticker == "AXIA3"


def test_a_round_from_another_month_is_never_used():
    round_ = A.find_decision_round(_policy(), _decisions("2026-08-31"), CYCLE)

    assert round_.date is None


def test_a_policy_change_after_the_round_is_judged_against_the_current_policy():
    policy = _policy(_asset("EEE11", "fii"))

    proposal = A.build_proposal(
        _inputs(policy=policy, rows=_rows(EEE11=("fii", 500.0)))
    )

    assert proposal.state == A.STATE_EMPTY
    assert proposal.reason == A.REASON_NO_ROUND


def test_decs_outside_the_universe_are_listed_but_never_candidates():
    decisions = (*_decisions(), _dec("OLD11"), _dec("RF-1"))

    proposal = A.build_proposal(_inputs(decisions=decisions))

    outside = {n.ticker for n in proposal.decision_round.outside_universe}
    assert outside == {"OLD11", "RF-1"}
    assert {ln.ticker for ln in proposal.lines}.isdisjoint(outside)


def test_an_inactive_line_is_outside_the_universe():
    policy = _policy(_asset("EEE11", "fii", status="inativo"))

    assert "EEE11" not in {ln.id for ln in A.decision_universe(policy)}


# --- pré-condições (§4) --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"contract": None}, A.REASON_CONTRACT),
        ({"contract": build_contract()}, A.REASON_CONTRACT),
        ({"policy": _policy(approval_status="pendente")}, A.REASON_POLICY),
        ({"policy": None}, A.REASON_POLICY),
        ({"budget": replace(_budget(), approval_status="pendente")}, A.REASON_BUDGET),
        ({"budget": None}, A.REASON_BUDGET),
        ({"decisions": _decisions(DDD3=("MANTER", None))}, A.REASON_NO_ROUND),
        ({"decisions": ()}, A.REASON_NO_ROUND),
        ({"price_snapshot_date": None}, A.REASON_NO_PRICE_SNAPSHOT),
        ({"price_snapshot_date": dt.date(2026, 8, 31)}, A.REASON_NO_PRICE_SNAPSHOT),
        ({"rows": ()}, A.REASON_RECONCILIATION),
        ({"current_snapshot_date": None}, A.REASON_CURRENT_DATE_MISSING),
        (
            {"current_snapshot_date": dt.date(2026, 8, 31)},
            A.REASON_CURRENT_OUT_OF_CYCLE,
        ),
    ],
)
def test_each_failed_precondition_makes_the_proposal_empty(changes, reason):
    proposal = A.build_proposal(_inputs(**changes))

    assert proposal.state == A.STATE_EMPTY
    assert proposal.reason == reason
    assert proposal.lines == ()


def test_all_failed_preconditions_are_listed_and_the_first_is_the_reason():
    proposal = A.build_proposal(_inputs(contract=None, current_snapshot_date=None))

    assert proposal.failed_preconditions == (
        A.REASON_CONTRACT,
        A.REASON_CURRENT_DATE_MISSING,
    )
    assert proposal.reason == A.REASON_CONTRACT


@pytest.mark.parametrize(
    ("rows", "kind"),
    [
        (_rows(ZZZ11=("fii", 100.0)), A.INCONS_UNRESOLVED),
        (_rows(OLD11=("fii", 100.0)), A.INCONS_REOPENED),
        (_rows(**{"RF-2": ("renda_fixa", 100.0)}), A.INCONS_NEW_MEMBER),
    ],
)
def test_each_structural_inconsistency_blocks_with_its_detail(rows, kind):
    proposal = A.build_proposal(_inputs(rows=rows))

    assert proposal.reason == A.REASON_RECONCILIATION
    [inconsistency] = proposal.inconsistencies
    assert inconsistency.kind == kind
    assert inconsistency.detail


def test_a_line_without_position_and_a_class_divergence_do_not_block():
    rows = tuple(r for r in _rows(CCC3=("fii", 3_000.0)) if r.id != "BBB11")

    proposal = A.build_proposal(_inputs(rows=rows))

    assert proposal.state != A.STATE_EMPTY
    assert _reasons(proposal)["BBB11"] == A.EXCL_NO_POSITION
    assert _reasons(proposal)["CCC3"] == A.EXCL_CLASS_DIVERGENT
    assert proposal.inconsistencies == ()


def test_the_cycle_must_be_a_month():
    with pytest.raises(ValueError):
        A.build_proposal(_inputs(cycle="2026-13"))


# --- elegibilidade (§5) --------------------------------------------------------------------


@pytest.mark.parametrize("verdict", ["AGUARDAR", "REDUZIR", "ENCERRAR", "AUMENTAR"])
def test_every_vetoed_verdict_excludes_the_line(verdict):
    proposal = A.build_proposal(_inputs(decisions=_decisions(AAA11=(verdict, 9.0))))

    assert _reasons(proposal)["AAA11"] == f"{A.EXCL_VETOED}:{verdict}"


def test_individual_exclusions_carry_their_reason():
    budget = _budget()
    budget = replace(
        budget,
        lines=tuple(
            replace(ln, status="pendente") if ln.class_id == "acao" else ln
            for ln in budget.lines
        ),
    )
    proposal = A.build_proposal(
        _inputs(budget=budget, prices={"AAA11": 10.0, "BBB11": None, "CCC3": 30.0})
    )

    reasons = _reasons(proposal)
    assert reasons["DDD3"] == A.EXCL_AT_TARGET
    assert reasons["BBB11"] == A.EXCL_NO_PRICE
    assert reasons["CCC3"] == A.EXCL_CLASS_NOT_BUDGETED
    assert [ln.ticker for ln in proposal.lines] == ["AAA11"]


def test_weight_equal_to_target_is_excluded():
    proposal = A.build_proposal(
        _inputs(
            policy=_policy(
                lines=(
                    _asset("AAA11", "fii", target=1.0),
                    _asset("BBB11", "fii"),
                    _asset("CCC3", "acao"),
                    _asset("DDD3", "acao"),
                    GROUP,
                )
            )
        )
    )

    assert _reasons(proposal)["AAA11"] == A.EXCL_AT_TARGET


def test_no_eligible_line_is_an_empty_proposal():
    decisions = _decisions(
        AAA11=("AGUARDAR", 7.0), BBB11=("REDUZIR", 7.0), CCC3=("ENCERRAR", 6.0)
    )

    proposal = A.build_proposal(_inputs(decisions=decisions))

    assert proposal.state == A.STATE_EMPTY
    assert proposal.reason == A.REASON_NO_ELIGIBLE
    assert proposal.failed_preconditions == ()


# --- ranking, limites e distribuição (§7-§9, §11) -----------------------------------------


def test_the_ranking_uses_the_persisted_score_and_the_gap():
    proposal = A.build_proposal(_inputs())

    aaa, bbb, ccc = proposal.lines
    assert [aaa.ticker, bbb.ticker, ccc.ticker] == ["AAA11", "BBB11", "CCC3"]
    assert aaa.gap == pytest.approx(0.8)
    assert aaa.opportunity_score == pytest.approx(7.0 * (0.75 + 0.25 * 0.8))
    assert ccc.opportunity_score == pytest.approx(6.0 * (0.75 + 0.25 * 0.4))


def test_ties_break_by_score_then_ticker():
    rows = _rows(AAA11=("fii", 2_000.0))
    decisions = _decisions(AAA11=("MANTER", 7.0), BBB11=("MANTER", 7.0))

    proposal = A.build_proposal(_inputs(rows=rows, decisions=decisions))

    assert [ln.ticker for ln in proposal.lines][:2] == ["AAA11", "BBB11"]


def test_the_monthly_cap_limits_each_asset_and_leaves_a_partial_proposal():
    proposal = A.build_proposal(_inputs())

    assert [ln.ideal for ln in proposal.lines] == pytest.approx([337.5] * 3)
    assert proposal.state == A.STATE_PARTIAL
    assert proposal.leftover_by_limit == pytest.approx(1350 - 1012.5)


def test_whole_shares_and_explicit_leftover_that_is_never_redistributed():
    proposal = A.build_proposal(_inputs(contract=_contract(monthly_asset_cap_pct=50.0)))

    aaa, bbb, ccc = proposal.lines
    assert (aaa.ideal, aaa.shares, aaa.value) == (675.0, 67, 670.0)
    assert (bbb.ideal, bbb.shares, bbb.value) == (675.0, 6, 600.0)
    assert (ccc.ideal, ccc.shares, ccc.value) == (0.0, 0, 0.0)
    assert proposal.state == A.STATE_COMPLETE
    assert proposal.sum_value == 1270.0
    assert proposal.leftover_by_rounding == pytest.approx(80.0)
    assert proposal.unallocated == pytest.approx(80.0)


def test_a_share_more_expensive_than_the_ideal_gets_zero_shares():
    proposal = A.build_proposal(
        _inputs(prices={"AAA11": 400.0, "BBB11": 100.0, "CCC3": 30.0})
    )

    assert proposal.lines[0].shares == 0
    assert proposal.lines[0].value == 0.0


def test_the_class_cap_is_a_limit_and_zero_when_the_class_is_at_target():
    budget = _budget(fii=(3.0, 0.0, 0.0, 40.0))  # fii já em 3%: sem folga

    proposal = A.build_proposal(_inputs(budget=budget))

    by_ticker = {ln.ticker: ln for ln in proposal.lines}
    assert by_ticker["AAA11"].ideal == 0.0
    assert by_ticker["BBB11"].ideal == 0.0
    assert by_ticker["CCC3"].ideal == pytest.approx(337.5)
    assert proposal.class_caps["fii"] == 0.0


def test_the_asset_cap_stops_at_the_individual_target():
    rows = _rows(AAA11=("fii", 4_900.0))

    proposal = A.build_proposal(_inputs(rows=rows))

    aaa = next(ln for ln in proposal.lines if ln.ticker == "AAA11")
    assert aaa.ideal == pytest.approx(aaa.cap_asset)
    assert aaa.ideal < 337.5


def test_the_class_weight_comes_from_the_policy_class():
    proposal = A.build_proposal(_inputs())

    # fii: 3% de 100.000 -> até o alvo de 34%: 31.000
    assert proposal.class_caps["fii"] == pytest.approx(31_000.0)


# --- invariantes (§10) ---------------------------------------------------------------------


def _checked(proposal, **changes):
    inputs = _inputs()
    rec = A.reconcile(inputs.policy, inputs.rows)
    A.check_invariants(
        replace(proposal, **changes), inputs.policy, inputs.budget, rec, inputs.contract
    )


def test_a_valid_proposal_passes_every_invariant():
    _checked(A.build_proposal(_inputs()))


@pytest.mark.parametrize(
    "tamper",
    [
        lambda ln: replace(ln, value=ln.ideal + 1),
        lambda ln: replace(ln, ideal=10_000.0, value=0.0),
        lambda ln: replace(ln, decision_date="2026-09-20"),
        lambda ln: replace(ln, price_snapshot_date=""),
    ],
)
def test_a_tampered_line_breaks_an_invariant(tamper):
    proposal = A.build_proposal(_inputs())
    lines = (tamper(proposal.lines[0]), *proposal.lines[1:])

    with pytest.raises(A.AporteInvariantError):
        _checked(proposal, lines=lines)


def test_an_excluded_line_with_value_or_an_automatic_action_breaks_the_invariants():
    proposal = A.build_proposal(_inputs())
    ghost = A.Exclusion(proposal.lines[0].line_id, proposal.lines[0].ticker, "x")

    with pytest.raises(A.AporteInvariantError):
        _checked(proposal, exclusions=(*proposal.exclusions, ghost))
    with pytest.raises(A.AporteInvariantError):
        _checked(proposal, automatic_action="executar")


# --- leitura do vault ----------------------------------------------------------------------


HEADER = (
    "| ID | Ativo | Classe | Quantidade | PM | Preço atual | Valor | Peso | Peso alvo | "
    "Status |"
)


def _brl(value: float) -> str:
    return "R$ " + f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _write_vault(vault: Path, *, snapshot_date="2026-09-21", contract=True) -> None:
    portfolio = vault / "02_Portfolio"
    portfolio.mkdir(parents=True, exist_ok=True)
    front = ["---", "type: portfolio"]
    if snapshot_date:
        front.append(f"snapshot_date: {snapshot_date}")
    lines = [
        *front,
        "---",
        "",
        HEADER,
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in _rows():
        lines.append(
            f"| {row.id} | {row.name} | {row.asset_class} |  |  |  | {_brl(row.value)} "
            "| 0,00% |  | active |"
        )
    (portfolio / "Current.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    save_policy(vault, _policy())
    save_budget(vault, _budget())
    if contract:
        save_contract(vault, _contract())
    decisions = vault / "03_Decisions"
    decisions.mkdir(exist_ok=True)
    for note in _decisions():
        (decisions / f"DEC-{note.ticker}-{note.date}.md").write_text(
            "---\ntype: decision\n"
            f"decision_id: DEC-{note.ticker}-{note.date}\nticker: {note.ticker}\n"
            f"date: {note.date}\nnew_verdict: {note.verdict}\nconfidence: 0.5\n"
            f"decision_score: {note.score!r}\n---\n",
            encoding="utf-8",
        )


def _write_prices(base: Path, date="2026-09-26") -> Path:
    folder = base / date
    folder.mkdir(parents=True)
    for ticker, price in {
        "AAA11": 10.0,
        "BBB11": 100.0,
        "CCC3": 30.0,
        "DDD3": 20.0,
    }.items():
        (folder / f"{ticker}.json").write_text(
            json.dumps({"price": price}), encoding="utf-8"
        )
    return folder


def test_load_inputs_reads_the_vault_and_the_price_snapshot(tmp_path):
    vault, snaps = tmp_path / "vault", tmp_path / "snaps"
    _write_vault(vault)
    _write_prices(snaps, "2026-09-20")
    _write_prices(snaps, "2026-09-26")
    (snaps / "2026-10-01").mkdir()
    (snaps / "nao-e-data").mkdir()

    inputs = A.load_inputs(vault, snaps, CYCLE)

    assert inputs.current_snapshot_date == dt.date(2026, 9, 21)
    assert inputs.price_snapshot_date == dt.date(2026, 9, 26)
    assert inputs.prices["AAA11"] == 10.0
    assert {n.ticker for n in inputs.decisions} == {"AAA11", "BBB11", "CCC3", "DDD3"}
    assert A.build_proposal(inputs).state == A.STATE_PARTIAL


def test_the_current_snapshot_date_comes_only_from_the_header(tmp_path):
    vault = tmp_path / "vault"
    _write_vault(vault, snapshot_date=None)
    path = vault / "02_Portfolio" / "Current.md"

    assert A.read_current_snapshot_date(path) is None  # mtime nunca é usado
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "type: portfolio", "type: portfolio\nsnapshot_date: 21/09/2026"
        ),
        encoding="utf-8",
    )
    assert A.read_current_snapshot_date(path) is None


def test_an_unreadable_score_in_a_note_becomes_none(tmp_path):
    decisions = tmp_path / "03_Decisions"
    decisions.mkdir()
    (decisions / "DEC-AAA11-2026-09-26.md").write_text(
        "---\ntype: decision\nticker: AAA11\ndate: 2026-09-26\nnew_verdict: MANTER\n"
        "decision_score: nan\n---\n",
        encoding="utf-8",
    )
    (decisions / "DEC-NOTA-2026-09-26.md").write_text(
        "---\ntype: evidence\n---\n", encoding="utf-8"
    )

    [note] = A.read_decision_notes(tmp_path)

    assert note.score is None


def test_read_price_rejects_missing_or_invalid_prices(tmp_path):
    (tmp_path / "A.json").write_text(json.dumps({"price": 0}), encoding="utf-8")
    (tmp_path / "B.json").write_text(json.dumps({"price": "10"}), encoding="utf-8")
    (tmp_path / "C.json").write_text(json.dumps({"price": 9.5}), encoding="utf-8")

    assert A.read_price(tmp_path, "A") is None
    assert A.read_price(tmp_path, "B") is None
    assert A.read_price(tmp_path, "Z") is None
    assert A.read_price(tmp_path, "C") == 9.5


# --- relatório (§12) -----------------------------------------------------------------------


def test_the_report_records_the_full_trace(tmp_path):
    proposal = A.build_proposal(
        _inputs(
            current_snapshot_path="vault/02_Portfolio/Current.md",
            price_snapshot_path="snaps/2026-09-26",
        )
    )

    text = render_aporte_report(proposal)

    for key in (
        "cycle: 2026-09",
        "decision_round_date: 2026-09-26",
        "current_snapshot_date: 2026-09-21",
        "price_snapshot_date: 2026-09-26",
        "dias_entre_current_e_preco: 5",
        f"contract_hash: {proposal.contract_hash}",
        f"target_policy_hash: {proposal.target_policy_hash}",
        f"class_budget_hash: {proposal.class_budget_hash}",
        "universo_decisao: 4",
        "dec_na_rodada: 4",
        "automatic_action: nenhuma",
        "aprovacao_da_proposta: pendente",
        "state: PARCIALMENTE_ALOCADA",
    ):
        assert key in text
    assert "## Exclusões (1)" in text
    path = write_aporte_report(tmp_path, proposal)
    assert path == tmp_path / "02_Portfolio" / "Aporte_2026-09.md"


def test_an_empty_report_lists_the_failed_preconditions_and_inconsistencies():
    proposal = A.build_proposal(
        _inputs(rows=_rows(ZZZ11=("fii", 1.0)), current_snapshot_date=None)
    )

    text = render_aporte_report(proposal)

    assert "state: VAZIA" in text
    assert "reconciliacao_inconsistente" in text
    assert "current_snapshot_date_missing" in text
    assert "`ZZZ11`" in text


# --- comando manual ------------------------------------------------------------------------


def _invoke(vault, *args):
    return CliRunner().invoke(cli, ["aporte-proposto", "--vault", str(vault), *args])


def test_the_command_writes_the_report_only_when_asked(tmp_path):
    vault, snaps = tmp_path / "vault", tmp_path / "snaps"
    _write_vault(vault)
    _write_prices(snaps)
    args = ("--ciclo", CYCLE, "--snapshots-dir", str(snaps))

    result = _invoke(vault, *args)
    assert result.exit_code == 0, result.output
    assert "PARCIALMENTE_ALOCADA" in result.output
    assert not (vault / "02_Portfolio" / "Aporte_2026-09.md").exists()

    result = _invoke(vault, *args, "--report")
    assert result.exit_code == 0, result.output
    assert (vault / "02_Portfolio" / "Aporte_2026-09.md").exists()


def test_an_empty_proposal_is_not_an_error(tmp_path):
    vault = tmp_path / "vault"
    _write_vault(vault, contract=False)

    result = _invoke(vault, "--ciclo", CYCLE, "--snapshots-dir", str(tmp_path / "x"))

    assert result.exit_code == 0, result.output
    assert "VAZIA" in result.output
    assert "contrato_nao_aprovado" in result.output


def test_init_contract_writes_a_pending_contract_and_never_overwrites(tmp_path):
    result = _invoke(tmp_path, "--init-contrato")
    assert result.exit_code == 0, result.output
    assert load_contract(tmp_path).approval_status == "pendente"

    result = _invoke(tmp_path, "--init-contrato")
    assert result.exit_code == 1


def test_an_invalid_contract_file_stops_the_command(tmp_path):
    vault = tmp_path / "vault"
    _write_vault(vault)
    (vault / CONTRACT_RELATIVE_PATH).write_text("{}", encoding="utf-8")

    result = _invoke(vault, "--ciclo", CYCLE, "--snapshots-dir", str(tmp_path / "x"))

    assert result.exit_code == 1


# --- guards de arquitetura -----------------------------------------------------------------


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


APORTE_FILES = (
    Path("src/iip/portfolio/aporte.py"),
    Path("src/iip/portfolio/aporte_contract.py"),
    Path("src/iip/obsidian/aporte_report.py"),
)

_FORBIDDEN = (
    "iip.decision",
    "iip.integration",
    "iip.strategy",
    "iip.orchestration",
    "iip.portfolio_decision",
    "iip.portfolio_intelligence",
    "iip.intelligence",
    "iip.portfolio.batch_decide",
    "iip.portfolio.decision_alerts",
    "iip.cli",
)


def test_the_aporte_code_does_not_import_the_engine_or_the_old_aporte_modules():
    offenders = {
        (path.name, name)
        for path in APORTE_FILES
        for name in _imports(path)
        if any(name == bad or name.startswith(bad + ".") for bad in _FORBIDDEN)
    }

    assert offenders == set()


def test_only_the_command_and_the_report_use_the_aporte_modules():
    users = {
        str(path).replace("\\", "/")
        for path in Path("src/iip").rglob("*.py")
        if any(
            n.startswith(("iip.portfolio.aporte", "iip.obsidian.aporte_report"))
            for n in _imports(path)
        )
    }

    assert users == {
        "src/iip/portfolio/aporte.py",  # importa o contrato
        "src/iip/obsidian/aporte_report.py",
        "src/iip/cli/main.py",
    }


def test_the_aporte_command_is_manual_and_out_of_the_daily_job():
    script = Path("executar_atualizacao_diaria.ps1").read_text(encoding="utf-8")

    assert "aporte-proposto" not in script
    assert "aporte_contract" not in script
    assert "iip.portfolio.aporte" not in script
