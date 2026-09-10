# D-OBSIDIAN-06.32 — Controlled Persistence Executor R1

Executor controlado para o lote autorizado pelo D-OBSIDIAN-06.31 R2.1.

## Segurança

O executor consome obrigatoriamente:

- `reports/PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2_1.csv`
- `reports/PCIP11_0695_7_EXECUTION_CONTRACT_R1.csv`

Valida:

- 31 registros;
- identidade exata;
- autorização GRANTED;
- autorização de Metric Persistence;
- autorização de KnowledgeBridge;
- autorização de Vault;
- destino não vazio;
- destino dentro de `vault/04_Evidence`;
- Target_Binding e Target_Status presentes.

Para arquivo existente:

- conteúdo compatível com a identidade -> `NO_OP_IDENTICAL`;
- conteúdo incompatível -> `BLOCK_CONFLICT`;
- nunca sobrescreve.

Por padrão é DRY-RUN.

## Primeiro passo

```powershell
python .\RUN-D-OBSIDIAN-06.32_0695_7_CONTROLLED_PERSISTENCE_EXECUTOR_R1.py
```

Somente o dry-run aprovado permite avançar para a execução real:

```powershell
python .\RUN-D-OBSIDIAN-06.32_0695_7_CONTROLLED_PERSISTENCE_EXECUTOR_R1.py --execute
```

O executor prepara todos os objetos antes da primeira escrita e para novas escritas diante de falha.

Não existe rollback destrutivo automático.
