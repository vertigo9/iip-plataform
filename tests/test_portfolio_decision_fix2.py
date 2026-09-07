from iip.portfolio_decision.opportunity import build
from iip.portfolio_decision.risk_synthesis import RiskObservation, synthesize


def test_concentration_review_has_priority():
    result = synthesize(
        (
            RiskObservation("A", 7, 0.10, False),
            RiskObservation("B", 5, 0.20, True),
        )
    )
    assert result[0].ticker == "B"
    assert result[0].review_required


def test_opportunity_contract():
    result = build("hgru11", 9, 0.5, 0.5)
    assert result.ticker == "HGRU11"
    assert result.final_score == 7.875


def test_opportunity_bounds():
    result = build("cpfe3", 20, -1, 3)
    assert result.intrinsic_score == 10
    assert result.allocation_gap == 0
    assert result.income_need == 1
