# D-OBSIDIAN-06.32 — Controlled Persistence Executor R2

## Correções em relação à R1

- A reconstrução de `MetricObservationIdentity` foi alinhada ao pipeline 0695.7 comprovado: ticker canônico, valor/unidade/escala/período resolvidos, dimensão, hash, document ID, source locator e lineage usam os mesmos aliases do pipeline.
- `Metric_ID` e `Knowledge_Evidence_ID` continuam sendo recalculados e comparados com o contrato; divergência bloqueia antes de qualquer escrita.
- `Target_Relative` agora resolve corretamente como `REPO/vault/04_Evidence/...`.
- O dry-run continua sem alterar o Vault.

## Execução

Primeiro:

```powershell
python .\RUN-D-OBSIDIAN-06.32_0695_7_CONTROLLED_PERSISTENCE_EXECUTOR_R2.py
```

Somente se retornar `DRY_RUN_PASS`:

```powershell
python .\RUN-D-OBSIDIAN-06.32_0695_7_CONTROLLED_PERSISTENCE_EXECUTOR_R2.py --execute
```

O `--execute` permanece fail-closed para conflito, divergência de identidade ou target diferente do autorizado.
