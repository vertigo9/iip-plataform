# D-OBSIDIAN-06.19 — 0695.7 Release Readiness

## Objetivo

Executar o estágio já existente `RELEASE_0695_7_READINESS_R1.py` como um
gate de integração pós-baseline, sem promover métricas e sem alterar o Vault.

## O que é validado

- `PCIP11_0695_7_FINAL_PROMOTION_GATE_R1.csv` presente;
- script de Release Readiness presente;
- execução do Release Readiness;
- Vault byte-for-byte equivalente antes/depois;
- CSV e MD de readiness gerados;
- todas as linhas `Final_Promotion_Gate == PASS` classificadas como `READY`;
- zero chaves duplicadas `(Row, SHA256, Metric)`;
- zero linhas `REVIEW`;
- autorização de persistência/KnowledgeBridge/Vault continua não concedida.

`EXPECTED_BLOCK` é aceito como resultado normal de candidatos bloqueados pelo
Promotion Gate; não é convertido artificialmente em READY.

## Segurança

Este runner não executa Git e não faz:

- `git add`
- `git commit`
- `git reset`
- `git restore`
- `git clean`
- `git checkout`
- `git rm`
- `git mv`
- `git rebase`

O estágio 0695.7 continua read-only em relação ao Vault.

## Execução

Coloque/extrair o runner na raiz do repositório:

```powershell
cd D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1
python .\RUN_D-OBSIDIAN-06.19_0695_7_RELEASE_READINESS.py
```

O script existente `RELEASE_0695_7_READINESS_R1.py` deve estar na mesma raiz.

## Critério

PASS significa que o conjunto que passou pelo Final Promotion Gate também
passou pelo Release Readiness, sem alteração do Vault.

Isso ainda NÃO concede autorização para persistência.
