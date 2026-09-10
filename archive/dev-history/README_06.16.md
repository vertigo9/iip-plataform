# D-OBSIDIAN-06.16 — Baseline Finalization

Macro-etapa consolidada para substituir os micro-ciclos 06.15.x.

## Execução

Copiar `RUN_D-OBSIDIAN-06.16_BASELINE_FINALIZATION.py` para a raiz do repositório.

### Auditoria
```powershell
python .\RUN_D-OBSIDIAN-06.16_BASELINE_FINALIZATION.py audit
```

### Autorização explícita
```powershell
python .\RUN_D-OBSIDIAN-06.16_BASELINE_FINALIZATION.py authorize
```

### Pipeline acelerado até staging + cached gate
```powershell
python .\RUN_D-OBSIDIAN-06.16_BASELINE_FINALIZATION.py all-safe
```

`all-safe` NÃO faz commit.

### Após revisar o diff staged
```powershell
git diff --cached
python .\RUN_D-OBSIDIAN-06.16_BASELINE_FINALIZATION.py commit --commit
```

### Pós-commit
```powershell
python .\RUN_D-OBSIDIAN-06.16_BASELINE_FINALIZATION.py post
```

## Proteções

Sem `reset --hard`, `clean`, checkout destrutivo, delete ou move automático.

O commit exige `--commit` explícito.
