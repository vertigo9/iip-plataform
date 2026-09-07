---
type: metric_registry
asset_id: PCIP11
ticker: PCIP11
asset_class: FII
registry: metrics
schema_version: "0.1"
status: active
evidence_status: observed
---

# PCIP11 — Metric Registry

## Objetivo

Registrar métricas financeiras utilizadas pelo IIP, preservando a distinção entre:

1. valor observado em fonte;
2. valor informado pela gestão;
3. cálculo derivado;
4. inferência analítica;
5. lacuna.

## Componentes de origem

### Performance

[[PCIP11 - Performance Histórica]]

### Distribuições

[[PCIP11 - Distribuições]]

### Carteira e Crédito

[[PCIP11 - Carteira e Crédito - Jul 2026]]

## Classes de métrica

- performance;
- distribuição;
- patrimônio;
- valuation;
- crédito;
- carteira;
- risco;
- exposição.

## Regra de integridade

Uma métrica estruturada não deve ser criada apenas porque existe um conceito conhecido pelo IIP.

Ela deverá possuir suporte documental ou ser explicitamente marcada como inferência/cálculo.

## Estado inicial

Registry estrutural criado.

A promoção dos valores históricos para entidades Metric será feita somente quando a origem e a unidade estiverem identificadas de maneira inequívoca.
