# D-OBSIDIAN-06.24–06.30 — Accelerated Sequential Package R2

R2 corrige a geração anterior: nomes de arquivos de entrada/saída são agora
strings Python válidas (`Path / "arquivo.csv"`).

A cadeia permanece fail-closed e sequencial. Nenhum estágio concede autorização
por conta própria. O 06.30 continua exigindo `Explicit_Grant=GRANTED`.

Arquivos corrigidos:
- 06.24 Target Binding
- 06.25 Authorization Manifest
- 06.26 Pre-Execution Integrity
- 06.27 Idempotency Simulation
- 06.28 Atomic Dry-Run
- 06.29 Final Readiness
- 06.30 Controlled Persistence

Instalação: substitua os sete scripts R1 pelos sete scripts deste pacote na raiz
do repositório.

Primeiro comando:
```powershell
python .\RUN_D-OBSIDIAN-06.24_0695_7_TARGET_BINDING.py
```

Não execute 06.25 se 06.24 retornar BLOCKED.
