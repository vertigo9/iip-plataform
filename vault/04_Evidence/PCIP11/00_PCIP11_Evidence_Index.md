---
type: evidence_registry
asset_id: PCIP11
ticker: PCIP11
asset_class: FII
registry: evidence
schema_version: "0.1"
status: active
evidence_status: observed
---

# PCIP11 — Evidence Registry

## Objetivo

Registro estrutural das evidências utilizadas na reconstrução histórica e nas análises do PCIP11.

## Regra de integridade

Nenhuma evidência financeira deve ser criada por inferência silenciosa.

Cada evidência futura deverá indicar:

- identificação;
- data de observação;
- ativo;
- componente de origem;
- classificação;
- fonte;
- eventualmente localização da informação;
- confiança.

## Classificações permitidas

- observed
- management_statement
- inference
- gap

## Componentes de origem

- [[PCIP11 - Identidade e Estrutura]]
- [[PCIP11 - Performance Histórica]]
- [[PCIP11 - Distribuições]]
- [[PCIP11 - Carteira e Crédito - Jul 2026]]
- [[PCIP11 - Eventos e Reestruturações]]
- [[PCIP11 - Fontes]]

## Estado inicial

O registro estrutural está criado.

As evidências individuais deverão ser promovidas do conteúdo documental para entidades Evidence apenas quando houver suporte suficiente no material de origem.

## Controle

schema_version: 0.1
status: active
