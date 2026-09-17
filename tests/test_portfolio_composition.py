from __future__ import annotations

import pytest

from iip.decision.models import Decision, EvidenceRef, Verdict
from iip.integration.models import Action
from iip.integration.portfolio_composition import PortfolioCompositionError, compose
from iip.portfolio.registry import PortfolioAsset


def _decision(
    ticker: str = "BBSE3",
    *,
    verdict: Verdict = Verdict.MANTER,
    score: float = 7.5,
    confidence: float = 0.8,
    evidence_ids: tuple[str, ...] = ("ev-1", "ev-2"),
) -> Decision:
    return Decision(
        ticker=ticker,
        verdict=verdict,
        score=score,
        confidence=confidence,
        reasons=("reason",),
        evidence=tuple(
            EvidenceRef(evidence_id, 1.0) for evidence_id in evidence_ids
        ),
    )


def _asset(ticker: str = "BBSE3") -> PortfolioAsset:
    return PortfolioAsset(ticker, "equity")


def test_compose_projects_decision_into_existing_portfolio_pipeline():
    result = compose((_decision(verdict=Verdict.COMPRAR),), (_asset(),))

    assert result.top is not None
    assert result.top.ticker == "BBSE3"
    assert result.top.action is Action.APORTAR


def test_compose_preserves_thesis_exit_projection():
    result = compose((_decision(),), (_asset(),))

    assert result.top is not None
    assert result.top.thesis_exit_state is None


def test_compose_uses_portfolio_asset_class_from_registry():
    result = compose((_decision(),), (PortfolioAsset("BBSE3", "equity"),))

    assert result.top is not None
    assert result.top.ticker == "BBSE3"


def test_compose_rejects_missing_portfolio_asset():
    with pytest.raises(PortfolioCompositionError, match="portfolio_asset_not_found:BBSE3"):
        compose((_decision(),), ())


def test_compose_rejects_duplicate_portfolio_asset():
    with pytest.raises(PortfolioCompositionError, match="duplicate_portfolio_asset:BBSE3"):
        compose((_decision(),), (_asset(), _asset()))


def test_compose_rejects_duplicate_decision():
    with pytest.raises(PortfolioCompositionError, match="duplicate_decision:BBSE3"):
        compose((_decision(), _decision()), (_asset(),))


def test_compose_accepts_multiple_decisions_and_assets():
    result = compose(
        (
            _decision("BBSE3", verdict=Verdict.MANTER),
            _decision("CPFE3", verdict=Verdict.REDUZIR),
        ),
        (_asset("BBSE3"), _asset("CPFE3")),
    )

    assert {item.ticker for item in result.rankings} == {"BBSE3", "CPFE3"}


def test_compose_empty_input_returns_existing_pipeline_result():
    result = compose((), ())

    assert result.rankings == ()
    assert result.contribution_candidates == ()
