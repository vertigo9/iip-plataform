from iip.decision.income_forecast_persistence import (
    persist_income_forecast_if_eligible,
)
from iip.intelligence.metric_identity import MetricObservationIdentity
from iip.intelligence.metric_persistence import (
    PersistenceBatch,
    PersistenceCandidate,
    build_knowledge_evidence,
)
from iip.knowledge.bridge import KnowledgeBridge
from iip.portfolio_data.income_forecast import IncomeForecast


def make_metric_candidate(
    ticker: str, status: str = "IDENTITY_READY"
) -> PersistenceCandidate:
    observation = MetricObservationIdentity(
        canonical_ticker=ticker,
        original_ticker=ticker,
        metric_name="Distribuicao_Mensal",
        value="1.05",
        unit="BRL",
        scale="unit",
        period="2026-07",
        semantic_dimension=None,
        document_hash="abc123",
    )
    knowledge = build_knowledge_evidence(observation, title="t")
    return PersistenceCandidate(
        observation=observation,
        knowledge_evidence=knowledge,
        classification="",
        status=status,
        reason="promotion_gate_pass",
    )


def make_forecast(ticker: str = "PCIP11") -> IncomeForecast:
    return IncomeForecast(
        ticker=ticker,
        method="moving_average_3m",
        window=3,
        sample_size=3,
        periods_used=("2026-05", "2026-06", "2026-07"),
        projected_amount_per_unit=0.99,
    )


def test_eligible_forecast_is_persisted(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path / "vault"))
    batch = PersistenceBatch([make_metric_candidate("PCIP11")])

    outcome = persist_income_forecast_if_eligible(
        make_forecast(), batch=batch, bridge=bridge, asset_class="FII"
    )

    assert outcome.persisted is True
    assert outcome.note_path.exists()
    assert "0.99" in outcome.note_path.read_text("utf-8")


def test_ineligible_forecast_persists_nothing(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path / "vault"))
    batch = PersistenceBatch([])  # no promoted observations

    outcome = persist_income_forecast_if_eligible(
        make_forecast(), batch=batch, bridge=bridge, asset_class="FII"
    )

    assert outcome.persisted is False
    assert outcome.note_path is None
    assert outcome.eligibility.reason == "no_promoted_observation_for_ticker"


def test_forecast_coexists_with_opportunity_score_section(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path / "vault"))
    batch = PersistenceBatch([make_metric_candidate("PCIP11")])

    bridge.sync_asset_section(
        "PCIP11", "FII", "scoring", "opportunity_score", "- placeholder score"
    )
    outcome = persist_income_forecast_if_eligible(
        make_forecast(), batch=batch, bridge=bridge, asset_class="FII"
    )

    content = outcome.note_path.read_text("utf-8")
    assert "placeholder score" in content
    assert "0.99" in content
