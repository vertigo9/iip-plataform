# Contratos

## Eventos consumidos
- atlas.document.processed.v1
- atlas.event.materiality_evaluated.v1
- iip.decision.created.v1
- iip.portfolio.snapshot_created.v1

## Eventos produzidos
- knowledge.sync.completed.v1
- knowledge.sync.failed.v1
- knowledge.redundancy.detected.v1

## Responsabilidades
Atlas: detectar, validar, classificar, processar, avaliar materialidade, sincronizar, auditar e notificar quando aplicável.
Research/Portfolio: interpretar, atualizar tese, valuation, score e decisão de alocação.
Knowledge Bridge: persistir, versionar, relacionar, recuperar contexto e projetar para Obsidian.
