---
type: event_registry
asset_id: PCIP11
ticker: PCIP11
asset_class: FII
registry: events
schema_version: "0.1"
status: active
evidence_status: observed
---

# PCIP11 — Event Registry

## Objetivo

Índice estrutural dos eventos e reestruturações relevantes do PCIP11.

## Fonte documental

[[PCIP11 - Eventos e Reestruturações]]

## Regra

Eventos deverão ser registrados como fatos temporais independentes.

Cada evento futuro deverá preferencialmente possuir:

- event_id;
- date;
- event_type;
- description;
- evidence_status;
- source_ref;
- materiality;
- consequence;
- confidence.

## Estado inicial

O registro estrutural está criado.

Os eventos já documentados no componente histórico permanecem como fonte-base até serem promovidos individualmente para entidades Event.
