# D-OBSIDIAN-06.24–06.30 — Accelerated Sequential Package R3

R3 corrige o BLOCKED do 06.24 usando a arquitetura de persistência já existente
e explicitamente documentada no pipeline 0695.7.

O executor histórico usa o Vault oficial em:
`D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1\vault`

A evidência persistida usa:
`vault/04_Evidence/evidence_metric_<Knowledge_Evidence_ID suffix>.md`

Os IDs são derivados pelas funções oficiais `metric_evidence_id()` e
`knowledge_evidence_id()`, sem IDs manuais.

06.24–06.29 permanecem read-only. 06.30 continua fail-closed e não grava.

## Instalação

Substitua os sete scripts R2 anteriores pelos sete scripts deste pacote.

## Execução

```powershell
python .\RUN_D-OBSIDIAN-06.24_0695_7_TARGET_BINDING.py
python .\RUN_D-OBSIDIAN-06.25_0695_7_AUTHORIZATION_MANIFEST.py
python .\RUN_D-OBSIDIAN-06.26_0695_7_PRE_EXECUTION_INTEGRITY.py
python .\RUN_D-OBSIDIAN-06.27_0695_7_IDEMPOTENCY_SIMULATION.py
python .\RUN_D-OBSIDIAN-06.28_0695_7_ATOMIC_DRY_RUN.py
python .\RUN_D-OBSIDIAN-06.29_0695_7_FINAL_READINESS.py
python .\RUN_D-OBSIDIAN-06.30_0695_7_CONTROLLED_PERSISTENCE.py
```

Pare se qualquer etapa retornar BLOCKED.

Nenhuma etapa deste pacote concede autorização de escrita.
