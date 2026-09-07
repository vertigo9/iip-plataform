---
type: underlying_exposure_registry
schema_version: "0.1"
scope: portfolio
fund_count: 14
state: current
status: active
---

# Underlying Exposure Registry v0.1

Registro mestre das posiÃ§Ãµes prioritÃ¡rias para decomposiÃ§Ã£o de exposiÃ§Ã£o econÃ´mica.

## Regra metodolÃ³gica

Este registro nÃ£o inventa composiÃ§Ã£o de carteira.
Os campos de exposiÃ§Ã£o subjacente somente deverÃ£o ser preenchidos quando houver evidÃªncia documental.

## Fundos prioritÃ¡rios

| Ticker | FamÃ­lia | Prioridade | DocumentaÃ§Ã£o | Status |
|---|---|---|---|---|
| PCIP11 | credit_real_estate_hybrid | P1 | complete_asset_layer | ready_for_extraction |
| VGIP11 | credit_real_estate | P1 | registry_only | awaiting_evidence |
| AFHI11 | credit_real_estate | P1 | registry_only | awaiting_evidence |
| HGCR11 | credit_real_estate | P1 | registry_only | awaiting_evidence |
| BTCI11 | credit_real_estate | P1 | registry_only | awaiting_evidence |
| MANA11 | credit_real_estate | P1 | registry_only | awaiting_evidence |
| CDII11 | infrastructure | P2 | registry_only | awaiting_evidence |
| CPTI11 | infrastructure | P2 | registry_only | awaiting_evidence |
| JURO11 | infrastructure | P2 | registry_only | awaiting_evidence |
| HGRU11 | real_estate_hybrid | P3 | registry_only | awaiting_evidence |
| TRXF11 | real_estate_hybrid | P3 | registry_only | awaiting_evidence |
| RBVA11 | real_estate_hybrid | P3 | registry_only | awaiting_evidence |
| ALZR11 | real_estate_hybrid | P3 | registry_only | awaiting_evidence |
| KNRI11 | real_estate_hybrid | P3 | registry_only | awaiting_evidence |

## Estrutura de exposiÃ§Ã£o

| Fundo | Tipo de exposiÃ§Ã£o | Identificador subjacente | Valor / % PL | Indexador | Contraparte / Devedor | Setor | EvidÃªncia |
|---|---|---|---:|---|---|---|---|
| PCIP11 | gap | gap | gap | gap | gap | gap | gap |
| VGIP11 | gap | gap | gap | gap | gap | gap | gap |
| AFHI11 | gap | gap | gap | gap | gap | gap | gap |
| HGCR11 | gap | gap | gap | gap | gap | gap | gap |
| BTCI11 | gap | gap | gap | gap | gap | gap | gap |
| MANA11 | gap | gap | gap | gap | gap | gap | gap |
| CDII11 | gap | gap | gap | gap | gap | gap | gap |
| CPTI11 | gap | gap | gap | gap | gap | gap | gap |
| JURO11 | gap | gap | gap | gap | gap | gap | gap |
| HGRU11 | gap | gap | gap | gap | gap | gap | gap |
| TRXF11 | gap | gap | gap | gap | gap | gap | gap |
| RBVA11 | gap | gap | gap | gap | gap | gap | gap |
| ALZR11 | gap | gap | gap | gap | gap | gap | gap |
| KNRI11 | gap | gap | gap | gap | gap | gap | gap |

## Status da decomposiÃ§Ã£o

| Camada | Estado |
|---|---|
| EstratÃ©gia | parcial |
| Ativos subjacentes | gap |
| Devedores | gap |
| Contrapartes | gap |
| ImÃ³veis | gap |
| Setores | gap |
| Indexadores | parcial |
| Gestores | gap |
| Duration / prazo | gap |
| Overlap econÃ´mico | gap |

## Prioridade analÃ­tica

P1 = impacto direto na anÃ¡lise de crÃ©dito e substituiÃ§Ã£o entre FIIs.
P2 = impacto na diversificaÃ§Ã£o entre FI-Infra.
P3 = impacto na sobreposiÃ§Ã£o imobiliÃ¡ria com fundos hÃ­bridos.

## PCIP11

PCIP11 Ã© o primeiro ativo a ser decomposto, pois jÃ¡ possui camada documental prÃ³pria.
A extraÃ§Ã£o deverÃ¡ preservar Observed, Management Statement, Inference e Gap.

## Regra de decisÃ£o

Nenhuma posiÃ§Ã£o deverÃ¡ ser considerada economicamente diversificada apenas porque possui um ticker diferente.
A diversificaÃ§Ã£o efetiva serÃ¡ determinada pelos ativos, devedores, setores, imÃ³veis e demais exposiÃ§Ãµes subjacentes.
