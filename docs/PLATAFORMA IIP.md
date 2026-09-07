# Implementação no Atlas-IIP

## Fundação entregue
- Modelos Decision, Evidence, Exposure e PortfolioSnapshot
- Repositório Obsidian por filesystem
- Histórico append-only
- Detecção inicial de redundância econômica
- Testes unitários

## Integração com módulos existentes
1. Platform Core publica eventos versionados.
2. Atlas publica somente eventos factuais após auditoria.
3. Knowledge Bridge consome document.processed, event.materiality_evaluated, decision.created e portfolio.snapshot_created.
4. Research grava Decision + Evidence.
5. Portfolio grava PortfolioSnapshot.
6. Exposure Engine recalcula fatores econômicos.
7. Obsidian recebe projeções Markdown.
8. PostgreSQL permanece como fonte estruturada.

## Recuperação entre chats
O ContextAssembler deve recuperar: estado atual do ativo, última decisão, decisões anteriores relevantes, evidências, último snapshot da carteira e exposições.

## Auditoria
- nenhuma decisão sem evidência;
- nenhuma decisão substitui decisão anterior;
- nenhum snapshot é sobrescrito;
- toda mudança de veredito gera DecisionChange;
- todo evento material possui cadeia documental;
- divergência PostgreSQL ↔ Obsidian gera alerta.

## Git
Versionar o vault; commits opcionais após sincronização; tags para snapshots; Git não substitui PostgreSQL.
