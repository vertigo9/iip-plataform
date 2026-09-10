# D-OBSIDIAN-06.24 — FIX R2

Correção pontual do erro:

`UnboundLocalError: cannot access local variable 'b'`

A função SHA-256 tinha um sentinel incorreto:

`iter(lambda: f.read(1048576), b)`

Corrigido para:

`iter(lambda: f.read(1048576), b"")`

Nenhuma regra de negócio, identidade, destino ou autorização foi alterada.

## Aplicação

Substitua o arquivo existente por:

`RUN_D-OBSIDIAN-06.24_0695_7_TARGET_BINDING.py`

e execute:

```powershell
python .\RUN_D-OBSIDIAN-06.24_0695_7_TARGET_BINDING.py
```

O script continua read-only e não modifica o Vault.
