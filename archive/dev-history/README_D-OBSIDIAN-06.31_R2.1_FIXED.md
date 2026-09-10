# D-OBSIDIAN-06.31 R2.1 FIXED

Esta versão corrige o segundo problema encontrado no R2:

A R2 anterior selecionava `TARGET_BINDING_R1` antes de versões posteriores.
Esse arquivo pode não possuir `Target_Relative`, embora o binding mais recente possua
o destino necessário.

A R2.1 seleciona, em ordem de preferência, o artefato de binding mais recente compatível
com o contrato: 31 linhas + campo de target.

Também aceita aliases de target, mas normaliza tudo para `Target_Relative` no artefato
de autorização.

Execute na raiz do repositório:

```powershell
python .\RUN-D-OBSIDIAN-06.31_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2_1_FIXED.py
```

Nenhuma escrita no Vault é realizada.
