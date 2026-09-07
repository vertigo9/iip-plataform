# D-OBSIDIAN-06.17 — Post-06.16.2 Integrity / Regression Gate

## Objetivo

Fechar a reconciliação iniciada em D-OBSIDIAN-06.16.1/06.16.2 com uma validação
independente e read-only do estado após o commit:

`b177732 fix(iip): version critical intelligence architecture`

O gate confirma:

- branch `v2.1`;
- HEAD no commit corretivo `b177732` ou descendente imediato compatível;
- os 3 módulos críticos estão versionados;
- os 3 módulos existem no working tree;
- não há alterações staged;
- os 3 arquivos críticos não foram alterados após o commit corretivo;
- o commit `b177732` contém exatamente os 3 módulos críticos;
- suíte completa `pytest -q` continua passando;
- pelo menos os 872 testes anteriormente aprovados continuam passando.

## Segurança

Este script é **read-only em relação ao Git**.

Não executa:

- `git reset`
- `git restore`
- `git checkout`
- `git clean`
- `git rm`
- `git mv`
- `git rebase`
- `git commit`
- `git push`

Ele apenas executa a suíte e grava o relatório em
`reports/D-OBSIDIAN-06.17/`.

## Execução

No PowerShell:

```powershell
cd D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1
python .\RUN_D-OBSIDIAN-06.17_POST_06.16.2_INTEGRITY_GATE.py
```

## Critério de aceite

Todos os checks devem retornar `PASS`, incluindo:

- `BRANCH_V2_1`
- `HEAD_IS_06_16_2_OR_LATER`
- `HEAD_SUBJECT`
- `ALL_CRITICAL_FILES_TRACKED`
- `PRESENT:*` para os 3 módulos
- `NO_STAGED_CHANGES`
- `NO_WORKTREE_MODIFICATION_TO_CRITICAL`
- `06_16_2_COMMIT_SCOPE_EXACT`
- `PYTEST_EXIT_0`
- `PYTEST_EXPECTED_872_PLUS`

Resultado esperado da regressão:

`872 passed, 6 skipped`

com cobertura histórica protegida em aproximadamente 95%.

## Próximo passo após PASS

Com 06.17 PASS, o estado fica apto para o próximo marco de governança/documentação,
sem modificar código funcional.
