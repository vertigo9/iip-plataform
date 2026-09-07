# D-OBSIDIAN-06.32 — Controlled Persistence Executor R3

## Correção

O R2 encontrou 28 destinos idênticos e apenas 3 novos. A preparação foi bloqueada porque esses três registros não carregam `Ticker` no contrato de execução.

O R3 **não inventa o ticker**: quando o campo estiver ausente, extrai o ticker canônico do próprio `Metric_ID` já autorizado, no formato `metric:<TICKER>:...`. Em seguida, recalcula `Metric_ID` pela `MetricObservationIdentity` e exige igualdade com o `Metric_ID` autorizado. Qualquer divergência continua bloqueando antes da escrita.

Os 28 registros já existentes permanecem `NO_OP_IDENTICAL`.

## Comandos

Dry-run:

```powershell
python .\RUN-D-OBSIDIAN-06.32_0695_7_CONTROLLED_PERSISTENCE_EXECUTOR_R3.py
```

Somente se `DRY_RUN_PASS`:

```powershell
python .\RUN-D-OBSIDIAN-06.32_0695_7_CONTROLLED_PERSISTENCE_EXECUTOR_R3.py --execute
```
