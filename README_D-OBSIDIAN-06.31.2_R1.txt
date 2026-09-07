D-OBSIDIAN-06.31.2 — Scope Dedup & Authorization Reconciliation R1

OBJETIVO
Resolver explicitamente a divergência estrutural 31 -> 28 sem alterar a autorização original,
sem colapsar silenciosamente linhas e sem executar persistência.

FONTES
- reports/PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2_1.csv
- reports/0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.csv
- reports/0695_GENERIC_METRIC_PERSISTENCE_GRANULARITY_AUDIT_R1.csv

POLÍTICA
1. Preserva as 31 linhas da autorização como escopo/evidência.
2. Reconcilia contra a identidade canônica READY.
3. Classifica duplicatas exatas como aliases, nunca como novas escritas.
4. Qualquer conflito semântico permanece BLOCKED.
5. Não concede autorização.
6. Não escreve no Vault.
7. Não executa KnowledgeBridge.
8. Não faz delete/rename/move/overwrite.

EXECUÇÃO
python .\RUN-D-OBSIDIAN-06.31.2_0695_7_SCOPE_DEDUP_AUTH_RECONCILIATION_R1.py

CRITÉRIO DE SAÍDA
READY_FOR_AUTHORIZATION_RECONCILIATION_REVIEW somente se houver 28 identidades
canônicas READY, IDs Metric/Knowledge únicos e zero conflitos bloqueados.
Caso contrário: BLOCKED_REQUIRES_SEMANTIC_REVIEW.

PRÓXIMO PASSO
Somente após resultado PASS desta reconciliação será possível preparar um novo artefato
de autorização explicitamente reconciliado. 06.32 permanece bloqueado até então.
