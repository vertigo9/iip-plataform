# D-OBSIDIAN-06.31 — 0695.7 Explicit Persistence Authorization R2 FIXED

Correção cirúrgica do gate 06.31.

## Problema corrigido

A versão anterior exigia que `Target_Status` fosse um dos valores `READY/BOUND/PASS`.
O Target Binding 06.24 possui vocabulário próprio para esse campo.

A R2 mantém a validação de segurança, mas valida `Target_Status` por presença,
sem impor vocabulário incompatível.

## Controles preservados

- exatamente 31 identidades;
- identidade `Row + SHA256 + Metric`;
- escopo exato entre contrato e binding;
- `Target_Relative` obrigatório;
- destino obrigatoriamente dentro de `vault/04_Evidence`;
- `Target_Binding` obrigatório;
- `Target_Status` obrigatório;
- fail-closed em qualquer falha;
- nenhum write no Vault;
- nenhuma alteração destrutiva.

## Execução

Copiar o script para a raiz do repositório e executar:

```powershell
python .\RUN-D-OBSIDIAN-06.31_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2_FIXED.py
```

Apenas se o gate produzir `AUTHORIZATION: GRANTED`, o artefato poderá ser
consumido pelo executor controlado da etapa seguinte.

