from iip.portfolio_decision.action_plan import ActionPlanItem, prioritize
from iip.portfolio_decision.decision_matrix import DecisionCell, DecisionMatrix
from iip.portfolio_decision.income_intelligence import IncomeObservation, summarize
from iip.portfolio_decision.opportunity import Opportunity, build, rank
from iip.portfolio_decision.pipeline import PortfolioDecisionInput, run
from iip.portfolio_decision.risk_synthesis import RiskObservation, synthesize
from iip.portfolio_decision.score_aggregation import ScoreComponent, aggregate
from iip.portfolio_decision.thesis_quality import ThesisQuality, readiness


def test_score_aggregation():
    result = aggregate(
        (
            ScoreComponent("hgru11", "valuation", 9, 1),
            ScoreComponent("HGRU11", "quality", 7, 1),
        )
    )
    assert result[0].ticker == "HGRU11"
    assert result[0].score == 8
    assert result[0].confidence == 0.5


def test_income_summary():
    result = summarize(
        (
            IncomeObservation("A", 60, 0.2),
            IncomeObservation("B", 40, 0.1),
        )
    )
    assert result[0].income_share == 0.6


def test_thesis_quality_readiness():
    result = readiness(ThesisQuality("CPFE3", "Reforço", 0.9, 9, 3))
    assert result == 0.933333333333


def test_risk_synthesis():
    result = synthesize(
        (
            RiskObservation("A", 7, 0.1, False),
            RiskObservation("B", 5, 0.2, True),
        )
    )
    assert result[0].ticker == "B"
    assert result[0].adjusted_risk == 6.5
    assert result[0].review_required


def test_opportunity():
    result = build("hgru11", 9, 0.5, 0.5)
    assert result.final_score == 7.875
    assert rank((result,))[0].ticker == "HGRU11"


def test_decision_matrix():
    matrix = DecisionMatrix(
        (
            DecisionCell("HGRU11", "fund", 9, 0.9, 2, "APORTAR"),
            DecisionCell("CPFE3", "equity", 7, 0.8, 3, "MANTER"),
        )
    )
    assert len(matrix.actionable()) == 1


def test_action_plan():
    result = prioritize(
        (
            ActionPlanItem("B", "APORTAR", 7, "b"),
            ActionPlanItem("A", "APORTAR", 8, "a"),
        )
    )
    assert result[0].ticker == "A"


def test_integrated_pipeline():
    data = PortfolioDecisionInput(
        "2026-08-29",
        (
            ScoreComponent("HGRU11", "valuation", 9),
            ScoreComponent("HGRU11", "quality", 8),
        ),
        (IncomeObservation("HGRU11", 120, 0.2),),
        (RiskObservation("HGRU11", 3, 0.2, False),),
        (Opportunity("HGRU11", 9, 0.5, 0.2, 7.83),),
    )
    report = run(data)
    assert report.top_opportunity.ticker == "HGRU11"
    assert report.score_summaries[0].score == 8.5
