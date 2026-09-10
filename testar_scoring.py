"""Script de demonstração manual: gera um Opportunity Score, calcula uma
decisão e persiste tudo no vault (gate de elegibilidade incluso).

Rode com:
    python testar_scoring.py

Não usa o seu vault real — escreve numa pasta local "demo_vault" ao lado
deste script, para você poder inspecionar o resultado sem misturar com
dados de produção. Pode apagar essa pasta a qualquer momento.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from iip.decision.models import Decision, EvidenceRef, Verdict
from iip.decision.persistence import persist_decision_if_eligible
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


def main() -> None:
    print(f"1) Preparando vault de demonstração em: {VAULT_PATH}\n")
    bridge = KnowledgeBridge(str(VAULT_PATH))

    print("2) Persistindo a evidência que sustenta a decisão (exigida pela auditoria)...")
    evidencia = Evidence(
        evidence_id="EV-PCIP11-DEMO-001",
        ticker=TICKER,
        date=HOJE,
        source_type="atlas",
        source_url=None,
        title="Relatório de distribuições - demo",
        relevant_facts=("gerado pelo script de demonstração",),
    )
    caminho_evidencia = bridge.persist_evidence(evidencia)
    print(f"   -> evidência gravada em: {caminho_evidencia}\n")

    print("3) Montando o Opportunity Score (módulo canônico: portfolio_decision.opportunity)...")
    opportunity = build(
        TICKER,
        intrinsic_score=9.0,
        allocation_gap=0.5,
        income_need=0.5,
    )
    print(f"   -> {opportunity}\n")

    print("4) Montando a decisão do decision engine...")
    decisao = Decision(
        ticker=TICKER,
        verdict=Verdict.COMPRAR,
        score=opportunity.final_score,
        confidence=0.9,
        reasons=(f"opportunity_score={opportunity.final_score:.2f}",),
        evidence=(EvidenceRef(evidencia.evidence_id),),
    )
    print(f"   -> {decisao}\n")

    print("5) Simulando o resultado do Promotion Gate para este ticker...")
    observacao = MetricObservationIdentity(
        canonical_ticker=TICKER,
        original_ticker=TICKER,
        metric_name="Distribuicao_Mensal",
        value="1.05",
        unit="BRL",
        scale="unit",
        period="2026-07",
        semantic_dimension=None,
        document_hash="demo-hash-0001",
    )
    evidencia_conhecimento = build_knowledge_evidence(observacao, title="demo")
    candidato = PersistenceCandidate(
        observation=observacao,
        knowledge_evidence=evidencia_conhecimento,
        classification="",
        status="IDENTITY_READY",
        reason="promotion_gate_pass",
    )
    batch = PersistenceBatch([candidato])
    print("   -> ticker marcado como elegível (status IDENTITY_READY)\n")

    print("6) Persistindo a decisão + nota de scoring (só ocorre se elegível)...")
    resultado = persist_decision_if_eligible(
        decisao,
        batch=batch,
        bridge=bridge,
        asset_class=ASSET_CLASS,
        decision_id="DEC-PCIP11-DEMO-001",
        date=HOJE,
        opportunity=opportunity,
    )

    print("\n===== RESULTADO =====")
    print(f"Elegível: {resultado.eligibility.eligible} ({resultado.eligibility.reason})")
    print(f"Persistido: {resultado.persisted}")
    print(f"Decisão gravada em: {resultado.decision_path}")
    print(f"Nota de scoring gravada em: {resultado.scoring_note_path}")

    if resultado.scoring_note_path:
        print("\n----- conteúdo da nota de scoring -----")
        print(resultado.scoring_note_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
