from iip.orchestration.cycle_report import summarize
from iip.orchestration.decision_gate import DecisionGateInput, evaluate
from iip.orchestration.opportunity_map import build_point
from iip.orchestration.portfolio_cycle import (
    OrchestrationStage,
    PortfolioCycleOrchestrator,
)
from iip.orchestration.portfolio_matrix import MatrixEntry, sort_matrix
from iip.orchestration.rebalancing import compute_needs
from iip.orchestration.snapshot_store import SnapshotStore


def make_handlers():
    return {
        stage: (lambda ticker, ctx, previous, stage=stage: f"{stage.value}:{ticker}")
        for stage in PortfolioCycleOrchestrator.ORDER
    }


def test_full_portfolio_cycle():
    result = PortfolioCycleOrchestrator(make_handlers()).run("c1", "hgru11")
    assert result.success
    assert len(result.results) == 6
    assert result.results[-1].stage == OrchestrationStage.REPORT


def test_cycle_stops_on_missing_stage():
    handlers = make_handlers()
    handlers.pop(OrchestrationStage.DECISION)
    result = PortfolioCycleOrchestrator(handlers).run("c2", "CPFE3")
    assert not result.success
    assert result.results[-1].stage == OrchestrationStage.DECISION


def test_decision_gate():
    good = evaluate(DecisionGateInput(8, 0.8, 2, "Baixo", "Reforço"))
    bad = evaluate(DecisionGateInput(4, 0.8, 2, "Baixo", "Reforço"))
    review = evaluate(DecisionGateInput(8, 0.8, 2, "Alto", "Mudança de tese"))
    assert good.allowed
    assert not bad.allowed
    assert "high_risk_review" in review.reasons


def test_matrix_sort():
    entries = (
        MatrixEntry("B", "fund", "Logística", "Baixo", 8, "MANTER"),
        MatrixEntry("A", "equity", None, "Baixo", 8, "APORTAR"),
    )
    result = sort_matrix(entries)
    assert tuple(x.ticker for x in result) == ("A", "B")


def test_rebalancing_delta():
    result = compute_needs(
        (("HGRU11", 0.10), ("CPFE3", 0.10)),
        (("HGRU11", 0.15), ("CPFE3", 0.05)),
    )
    assert result[0].delta == 0.05
    assert result[1].delta == -0.05


def test_opportunity_map():
    point = build_point("cpfe3", 8, 0.5)
    assert point.ticker == "CPFE3"
    assert point.combined_score == 6.0


def test_snapshot_store():
    store = SnapshotStore()
    store.put("2026-08-29", {"value": 1})
    assert store.get("2026-08-29")["value"] == 1
    assert store.keys() == ("2026-08-29",)


def test_cycle_summary():
    good = PortfolioCycleOrchestrator(make_handlers()).run("c1", "HGRU11")
    summary = summarize("c1", (good,))
    assert summary.assets_processed == 1
    assert summary.success
