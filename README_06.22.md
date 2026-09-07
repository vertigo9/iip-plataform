# D-OBSIDIAN-06.22 — Execution Contract R1

Este marco define o contrato operacional que deverá reger uma futura
persistência dos 31 registros, mas não executa nenhuma escrita.

## Entrada

`reports/PCIP11_0695_7_EXECUTION_AUTHORIZATION_GATE_R1.csv`

Esperado: 31 registros, todos estruturalmente bloqueados porque o target ainda
não foi vinculado.

## Contrato

- Target explícito antes da autorização.
- Identidade: `Row + SHA256 + Metric`.
- Idempotência por `SHA256 + Metric`.
- Existente idêntico: NO-OP + auditoria.
- Existente conflitante: BLOCK, sem overwrite.
- Collision: BLOCK_AND_ESCALATE.
- Overwrite: DENY_BY_DEFAULT.
- Atomicidade: um registro por vez.
- Falha parcial: parar novas escritas e preservar auditoria.
- Rollback destrutivo: proibido sem autorização separada.
- Auditoria individual obrigatória.
- Scope lock pelo SHA-256 do input.

## Autorização

O contrato NÃO concede autorização.

Estado após 06.22:

`CONTRACT_DEFINED_NOT_AUTHORIZED`

## Segurança

Não executa Git, não escreve no KnowledgeBridge e não modifica o Vault.

## Execução

```powershell
cd D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1
python .\RUN_D-OBSIDIAN-06.22_0695_7_EXECUTION_CONTRACT.py
```
