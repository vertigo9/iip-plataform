from iip.decision.decision_engine import decide
from iip.decision.models import EvidenceRef, IntelligenceInput, Verdict
from iip.decision.opportunity import Opportunity, rank_opportunities
from iip.decision.pipeline import run
from iip.decision.portfolio_decision import summarize
from iip.decision.risk_bridge import RiskSnapshot, risk_penalty
from iip.decision.scoring import composite_score, confidence_score
from iip.decision.valuation_bridge import ValuationSnapshot, valuation_score


def make_item(**changes):
    values = {
        "ticker": "HGRU11",
        "thesis_signal": "Reforço",
        "risk_level": "Baixo",
        "valuation_score": 9.0,
        "dividend_score": 8.0,
        "quality_score": 9.0,
        "opportunity_score": 8.0,
        "evidence": (EvidenceRef("e1"), EvidenceRef("e2"), EvidenceRef("e3")),
    }
    values.update(changes)
    return IntelligenceInput(**values)


def test_composite_score():
    assert composite_score(make_item()) == 8.5


def test_confidence_uses_evidence_and_risk():
    assert confidence_score(make_item()) == 1.0
    assert confidence_score(make_item(risk_level="Alto")) == 0.8


def test_decision_buy():
    result = decide(make_item())
    assert result.verdict == Verdict.COMPRAR
    assert result.score == 8.5
    assert result.evidence


def test_thesis_change_overrides_high_score_toward_wait():
    result = decide(make_item(thesis_signal="Mudança de tese"))
    assert result.verdict == Verdict.AGUARDAR


def test_valuation_bridge():
    snapshot = ValuationSnapshot("CPFE3", fair_value=40, market_price=30)
    assert valuation_score(snapshot) > 8


def test_risk_penalty():
    assert risk_penalty(RiskSnapshot("CRAA11", "Alto")) == 1.5


def test_opportunity_ranking_is_deterministic():
    result = rank_opportunities(
        (
            Opportunity("B", 8, "b"),
            Opportunity("A", 8, "a"),
            Opportunity("C", 7, "c"),
        )
    )
    assert tuple(item.ticker for item in result) == ("A", "B", "C")


def test_portfolio_summary():
    decisions = (
        decide(make_item()),
        decide(
            make_item(
                ticker="ABCB4",
                valuation_score=2,
                dividend_score=2,
                quality_score=2,
                opportunity_score=2,
            )
        ),
    )
    summary = summarize(decisions)
    assert len(summary.buy) == 1
    assert len(summary.reduce) == 1


def test_validation_requires_evidence():
    result = run(make_item(evidence=()))
    assert result.validation.valid is False
    assert "missing_evidence" in result.validation.reasons
