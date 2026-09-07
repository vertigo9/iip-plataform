# D-OBSIDIAN-06.18 R2 — Post-Baseline Governance / Manifest Gate

## Correções em relação à R1

A R1 tinha dois problemas de diagnóstico:

1. `NO_STAGED_CHANGES` tratava qualquer saída de `git status --porcelain`
   como staged, bloqueando o gate por alterações apenas untracked/unstaged.
   A R2 consulta exclusivamente `git diff --cached --name-only`.

2. O parser da linha `TOTAL 8045 370 95%` exigia cinco campos, embora a saída
   real tenha quatro. A R2 aceita o formato real do pytest-cov.

Nenhuma dessas correções altera código funcional do IIP.

## Comportamento

A R2:

- permite trabalho untracked/unstaged preexistente;
- exige índice sem staging antes da operação;
- reconfirma os 3 módulos críticos;
- executa `pytest -q`;
- exige `872 passed` e `95%`;
- gera o manifesto e relatório;
- faz stage **somente** dos dois artefatos;
- valida o conjunto staged exatamente;
- cria o commit:
  `docs(iip): establish post-baseline governance manifest`;
- confirma que o índice ficou sem staged changes.

Não executa reset, restore, checkout, clean, rm, mv, rebase ou push.

## Execução

```powershell
cd D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1
python .\RUN_D-OBSIDIAN-06.18_POST_BASELINE_GOVERNANCE.py
```

## Critério final

`D-OBSIDIAN-06.18: PASS`
