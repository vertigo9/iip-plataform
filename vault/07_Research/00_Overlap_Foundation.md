---
type: overlap_foundation
schema_version: "0.1"
scope: portfolio
position_count: 46
portfolio_value: 286845.39
state: current
status: active
---

# Overlap Foundation v0.1

FundaÃ§Ã£o para medir concentraÃ§Ã£o e sobreposiÃ§Ã£o econÃ´mica entre as posiÃ§Ãµes.

## O que jÃ¡ pode ser medido

- concentraÃ§Ã£o por classe
- concentraÃ§Ã£o por economic bucket
- concentraÃ§Ã£o por categoria operacional
- concentraÃ§Ã£o por emissor nos instrumentos de renda fixa explicitamente identificados

## O que ainda NÃƒO deve ser calculado como fato

- sobreposiÃ§Ã£o de imÃ³veis entre FIIs
- sobreposiÃ§Ã£o de CRIs e devedores
- concentraÃ§Ã£o por grupo econÃ´mico
- concentraÃ§Ã£o setorial indireta
- exposiÃ§Ã£o comum a um mesmo devedor
- overlap entre fundos por ativos subjacentes

Essas mÃ©tricas exigem evidÃªncia documental especÃ­fica.

## ConcentraÃ§Ã£o por Economic Bucket

| Bucket | Valor | Peso |
|---|---:|---:|
| equity | R$ 125.811,47 | 43,86% |
| etf | R$ 11.718,00 | 4,09% |
| fiagro | R$ 4.650,00 | 1,62% |
| fixed_income | R$ 19.106,20 | 6,66% |
| fund | R$ 6.551,93 | 2,28% |
| infrastructure | R$ 21.271,40 | 7,42% |
| real_estate_hybrid | R$ 32.984,19 | 11,50% |
| real_estate_logistics | R$ 24.409,23 | 8,51% |
| real_estate_shopping | R$ 12.823,31 | 4,47% |
| securities | R$ 27.519,66 | 9,59% |

## Indicadores de risco potencial

| Indicador | Estado |
|---|---|
| ConcentraÃ§Ã£o acionÃ¡ria | mensurÃ¡vel |
| ConcentraÃ§Ã£o imobiliÃ¡ria | parcialmente mensurÃ¡vel |
| ConcentraÃ§Ã£o em crÃ©dito | nÃ£o consolidada |
| ConcentraÃ§Ã£o por emissor | parcialmente mensurÃ¡vel |
| SobreposiÃ§Ã£o FII/FI-Infra | nÃ£o consolidada |
| SobreposiÃ§Ã£o econÃ´mica indireta | nÃ£o consolidada |

## Regra de decisÃ£o

Um novo aporte nÃ£o deve ser avaliado somente pelo peso individual do ativo.
Deve considerar quanto de exposiÃ§Ã£o nova o ativo realmente acrescenta Ã  carteira.

## Cadeia

Ativo -> PosiÃ§Ã£o -> Bucket -> ExposiÃ§Ã£o EconÃ´mica -> Overlap -> Risco -> Retorno -> DecisÃ£o
