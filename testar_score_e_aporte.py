"""Demonstracao unificada: Opportunity Score + ranking de aportes,
persistidos juntos na mesma nota do ativo, com o gate de elegibilidade.

Rode com:
    python testar_score_e_aporte.py

Escreve num vault de demonstracao local ("demo_vault"), nao no seu vault
de producao. Pode apagar essa pasta a qualquer momento.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from iip.decision.contribution_persistence import persist_contributions_if_eligible
from iip.decision.models import Decision, EvidenceRef, Verdict
from iip.decision.persistence import persist_decision_if_eligible
from iip.integration.contribution import ContributionCandidate
from iip.intelligence.metric_identity import MetricObservationIdentity
from iip.intelligence.metric_persistence import (
    PersistenceBatch,
    PersistenceCandidate,
    build_knowledge_evidence,
)
from iip.knowledge.bridge import KnowledgeBridge
from iip.knowledge.models import Evidence
from iip.portfolio_decision.opportunity import build

VAULT_PATH = Path(__file__).parent / "demo_vault"
TICKER = "PCIP11"
ASSET_CLASS = "FII"
HOJE = date(2026, 7, 31)


def promoted_batch_for(ticker: str) -> PersistenceBatch:
    """Simula um resultado do Promotion Gate: ticker elegivel."""
    observacao = MetricObservationIdentity(
        canonical_ticker=ticker,
        original_ticker=ticker,
        metric_name="Distribuicao_Mensal",
        value="1.05",
        unit="BRL",
        scale="unit",
        period="2026-07",
        semantic_dimension=None,
        document_hash="demo-hash-0001",
    )
    knowledge_evidence = build_knowledge_evidence(observacao, title="demo")
    candidato = PersistenceCandidate(
        observation=observacao,
        knowledge_evidence=knowledge_evidence,
        classification="",
        status="IDENTITY_READY",
        reason="promotion_gate_pass",
    )
    return PersistenceBatch([candidato])


def main() -> None:
    print(f"Vault de demonstração: {VAULT_PATH}\n")
    bridge = KnowledgeBridge(str(VAULT_PATH))
    batch = promoted_batch_for(TICKER)

    print("1) Persistindo evidência (exigida pela auditoria de decisões)...")
    bridge.persist_evidence(
        Evidence(
            evidence_id="EV-PCIP11-DEMO-001",
            ticker=TICKER,
            date=HOJE,
            source_type="atlas",
            source_url=None,
            relevant_facts=("gerado pelo script de demonstração",),
        )
    )

    print("2) Opportunity Score + decisão...")
    opportunity = build(TICKER, intrinsic_score=9.0, allocation_gap=0.5, income_need=0.5)
    decisao = Decision(
        ticker=TICKER,
        verdict=Verdict.COMPRAR,
        score=opportunity.final_score,
        confidence=0.9,
        reasons=(f"opportunity_score={opportunity.final_score:.2f}",),
        evidence=(EvidenceRef("EV-PCIP11-DEMO-001"),),
    )
    resultado_decisao = persist_decision_if_eligible(
        decisao,
        batch=batch,
        bridge=bridge,
        asset_class=ASSET_CLASS,
        decision_id="DEC-PCIP11-DEMO-001",
        date=HOJE,
        opportunity=opportunity,
    )
    print(f"   -> decisão persistida: {resultado_decisao.persisted}")

    print("3) Ranking de aportes...")
    candidato_aporte = ContributionCandidate(
        ticker=TICKER, score=8.5, monthly_budget_share=1.0
    )
    resultados_aporte = persist_contributions_if_eligible(
        (candidato_aporte,),
        batch=batch,
        bridge=bridge,
        asset_classes={TICKER: ASSET_CLASS},
        date=HOJE,
    )
    print(f"   -> aporte persistido: {resultados_aporte[0].persisted}")

    print("\n===== NOTA FINAL DO ATIVO (as duas seções juntas) =====")
    print(resultado_decisao.scoring_note_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
