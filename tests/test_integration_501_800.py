from iip.integration.allocation import apply_constraints, rank
from iip.integration.analyzer_bridge import normalize_analyzer_output
from iip.integration.contribution import prioritize_contributions
from iip.integration.decision_history import DecisionRecord, changed
from iip.integration.models import Action, AssetSignal, PortfolioConstraint
from iip.integration.portfolio_bridge import context
from iip.integration.portfolio_pipeline import run
from iip.integration.risk_budget import RiskBudget


def test_analyzer_bridge_bounds_values():
    snapshot = normalize_analyzer_output(
        "cpfe3",
        valuation=12,
        dividend=-1,
        quality=8,
        risk=6,
        opportunity=9,
        thesis="Reforço",
        evidence_count=2,
    )
    assert snapshot.ticker == "CPFE3"
    assert snapshot.valuation == 10
    assert snapshot.dividend == 0
    assert snapshot.evidence_count == 2


def test_portfolio_context_uses_registry_data():
    from iip.portfolio.registry import get_asset

    asset = get_asset("HGRU11")
    ctx = context(asset)
    assert ctx.ticker == "HGRU11"
    assert ctx.structure == "Tijolo"
    assert ctx.segment == "Renda Urbana"


def test_allocation_rank_is_deterministic():
    signals = (
        AssetSignal("B", "equity", 8.0, 0.9, Action.APORTAR),
        AssetSignal("A", "fund", 8.0, 0.9, Action.APORTAR),
        AssetSignal("C", "fund", 7.0, 0.9, Action.MANTER),
    )
    ranked = rank(signals)
    assert tuple(item.ticker for item in ranked) == ("A", "B", "C")


def test_contribution_candidates_sum_to_one():
    signals = (
        AssetSignal("A", "fund", 9.0, 1.0, Action.APORTAR),
        AssetSignal("B", "fund", 6.0, 1.0, Action.APORTAR),
        AssetSignal("C", "fund", 8.0, 1.0, Action.MANTER),
    )
    decisions = rank(signals)
    candidates = prioritize_contributions(decisions)
    assert sum(item.monthly_budget_share for item in candidates) == 1.0


def test_risk_budget():
    budget = RiskBudget(total=10, used=6.5)
    assert budget.available == 3.5
    assert budget.utilization == 0.65


def test_decision_history_change_detection():
    previous = DecisionRecord("XPML11", 8.0, "APORTAR", ("e1",))
    same = DecisionRecord("XPML11", 8.0, "APORTAR", ("e1",))
    new = DecisionRecord("XPML11", 7.0, "AGUARDAR", ("e2",))
    assert not changed(previous, same)
    assert changed(previous, new)


def test_constraints_do_not_invent_weights():
    decisions = rank((AssetSignal("A", "fund", 9, 1, Action.APORTAR),))
    result = apply_constraints(
        decisions,
        (PortfolioConstraint("max_manager", maximum=0.25),),
    )
    assert result == decisions


def test_integrated_pipeline():
    signals = (
        AssetSignal("HGRU11", "fund", 9, 1, Action.APORTAR, 3),
        AssetSignal("CPFE3", "equity", 8, 0.8, Action.MANTER, 2),
    )
    result = run(signals)
    assert result.top.ticker == "HGRU11"
    assert result.contribution_candidates[0].ticker == "HGRU11"

def test_asset_signal_preserves_thesis_exit_projection():
    signal = AssetSignal(
        "PCIP11",
        "fund",
        7.5,
        0.9,
        Action.MANTER,
        4,
        "REVIEW",
        ("fundamentals",),
        ("valuation", "dividends"),
        ("opportunity_cost",),
        False,
    )

    assert signal.thesis_exit_state == "REVIEW"
    assert signal.thesis_exit_failed_gates == ("fundamentals",)
    assert signal.thesis_exit_attention_gates == ("valuation", "dividends")
    assert signal.thesis_exit_unknown_gates == ("opportunity_cost",)
    assert signal.thesis_exit_critical_failure is False


def test_rank_preserves_thesis_exit_projection():
    signal = AssetSignal(
        "PCIP11",
        "fund",
        7.5,
        0.9,
        Action.MANTER,
        4,
        "BREAK",
        ("fundamentals", "governance"),
        (),
        (),
        True,
    )

    decision = rank((signal,))[0]

    assert decision.ticker == "PCIP11"
    assert decision.thesis_exit_state == "BREAK"
    assert decision.thesis_exit_failed_gates == ("fundamentals", "governance")
    assert decision.thesis_exit_critical_failure is True


def test_integrated_pipeline_preserves_thesis_exit_projection():
    signal = AssetSignal(
        "PCIP11",
        "fund",
        7.5,
        0.9,
        Action.MANTER,
        4,
        "INSUFFICIENT_EVIDENCE",
        (),
        (),
        ("valuation", "opportunity_cost"),
        False,
    )

    result = run((signal,))

    decision = result.top

    assert decision is not None
    assert decision.thesis_exit_state == "INSUFFICIENT_EVIDENCE"
    assert decision.thesis_exit_unknown_gates == (
        "valuation",
        "opportunity_cost",
    )


def test_asset_signal_without_thesis_exit_remains_backward_compatible():
    signal = AssetSignal(
        "HGRU11",
        "fund",
        9.0,
        1.0,
        Action.APORTAR,
        3,
    )

    assert signal.thesis_exit_state is None
    assert signal.thesis_exit_failed_gates == ()
    assert signal.thesis_exit_attention_gates == ()
    assert signal.thesis_exit_unknown_gates == ()
    assert signal.thesis_exit_critical_failure is None
