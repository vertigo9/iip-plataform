# 0695.7 — Generic Metric Identity + Persistence Package

## Objetivo

Este pacote consolida a evolução do 0695.7 em uma arquitetura genérica para todos os ativos da carteira.

O pacote trata:

- identidade semântica de métricas;
- distinção entre duplicata exata e observação economicamente distinta;
- IDs estáveis para `Metric Evidence` e `Knowledge Evidence`;
- preservação de ticker histórico e linhagem;
- idempotência;
- contrato de persistência;
- adapter para o `KnowledgeBridge`;
- testes sem acesso ao Vault.

## Regra de segurança

Por padrão:

```text
Metric persistence      : NO
KnowledgeBridge         : NO
Vault changed           : NO
```

Nenhum script deste pacote autoriza escrita no Vault.

## Instalação

Copie o conteúdo do pacote para a raiz do repositório:

```text
D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1
```

Para integração automática, utilize `INSTALL_0695_7_PACKAGE.ps1` somente depois de revisar o conteúdo.

## Execução dos testes

Na raiz do repositório:

```powershell
python .\scripts\RUN_0695_7_CONTRACT_CHECK_R1.py
```

## Execução do dry-run

```powershell
python .\scripts\RUN_0695_7_SEMANTIC_PIPELINE_R1.py
```

e:

```powershell
python .\scripts\RUN_0695_7_PERSISTENCE_DRY_RUN_R1.py
```

O segundo comando gera:

```text
reports\0695_7_PERSISTENCE_CONTRACT_DRY_RUN_R1.csv
```

## Conceito de identidade

A identidade da observação é formada por:

```text
canonical_ticker
+ period
+ metric_name
+ semantic_dimension
+ value
+ unit
+ scale
+ document_hash
+ source_locator
```

A dimensão semântica é opcional para métricas não ambíguas.

Para métricas ambíguas, não se deve escolher uma dimensão apenas porque ela aparece em algum lugar do documento.

## Duplicação

Duplicação exata:

```text
mesmo documento
+ mesma métrica
+ mesmo período
+ mesmo valor
+ mesmo contexto de identidade
```

é tratada como `DEDUPLICABLE`.

Valores distintos não devem compartilhar silenciosamente a mesma identidade.

## Linhagem

A estrutura preserva:

```text
original_ticker = CVBI11
canonical_ticker = PCIP11
lineage = CVBI11 -> PCIP11
```

A lógica não é limitada a PCIP11.

## Próxima etapa

Somente depois de:

1. testes;
2. dry-run;
3. auditoria de duplicidade;
4. contrato do `KnowledgeBridge`;
5. Release Gate;

a persistência real deverá ser considerada.
