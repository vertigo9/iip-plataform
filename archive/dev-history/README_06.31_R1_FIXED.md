# D-OBSIDIAN-06.31 R1 FIXED

Correção do 06.31 após o primeiro teste.

## Causa

O 06.31 R1 original procurava `Target_Path`/`Target`, mas o contrato real
produzido pelo 06.24 usa:

- `Target_Relative` — destino relativo canônico;
- `Target_Binding` — decisão de binding;
- `Target_Status` — estado do binding.

O primeiro 06.31, portanto, falhou por incompatibilidade de schema, e não por
problema nos 31 registros.

## Correção

O R1 FIXED usa `Target_Relative` como campo de destino e valida também
`Target_Binding`/`Target_Status` quando presentes.

Não modifica o Vault.

Execute na raiz do repositório:

    python .\RUN_D-OBSIDIAN-06.31_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R1_FIXED.py

Resultado esperado:

    D-OBSIDIAN-06.31: PASS
    Authorization: GRANTED
    Vault modified: NO
