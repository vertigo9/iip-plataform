---
type: economic_exposure_map
schema_version: "0.1"
scope: portfolio
position_count: 46
portfolio_value: 286845.39
state: current
status: active
---

# Economic Exposure Map v0.1

Mapa quantitativo inicial das exposiÃ§Ãµes econÃ´micas reconhecidas na carteira.

## Regra metodolÃ³gica

A classificaÃ§Ã£o abaixo utiliza somente categorias explicitamente presentes na base operacional.
Ela nÃ£o representa ainda a exposiÃ§Ã£o econÃ´mica final dos ativos subjacentes.

## ExposiÃ§Ã£o por Economic Bucket

| Bucket | Valor | Peso | Qtde. | Ativos |
|---|---:|---:|---:|---|
| equity | R$ 125.811,47 | 43,86% | 14 | BBSE3, ISAE4, CXSE3, ABCB4, CMIG4, CPFE3, ALOS3, CSUD3, SAUD3, VBBR3, KLBN4, FESA4, LEVE3, PASS3 |
| etf | R$ 11.718,00 | 4,09% | 1 | LFTB11 |
| fiagro | R$ 4.650,00 | 1,62% | 1 | CRAA11 |
| fixed_income | R$ 19.106,20 | 6,66% | 10 | RF-NUBANK-120CDI, RF-DIGIMAIS-123CDI, RF-MP-115CDI, RF-JF-CDI2_60, RF-MB-BINVEST03, RF-MB-JEITTO14, RF-MB-ROOFTOP04, RF-MB-MULTIPLIKE12, RF-MB-JEITTO03, RF-BMG-IPCA14_50 |
| fund | R$ 6.551,93 | 2,28% | 1 | FMP-FGTS-DAYCOVAL |
| infrastructure | R$ 21.271,40 | 7,42% | 3 | CDII11, CPTI11, JURO11 |
| real_estate_hybrid | R$ 32.984,19 | 11,50% | 6 | HGRU11, TRXF11, PCIP11, RBVA11, ALZR11, KNRI11 |
| real_estate_logistics | R$ 24.409,23 | 8,51% | 2 | LVBI11, BTLG11 |
| real_estate_shopping | R$ 12.823,31 | 4,47% | 3 | HSML11, XPML11, HGBS11 |
| securities | R$ 27.519,66 | 9,59% | 5 | AFHI11, MANA11, VGIP11, HGCR11, BTCI11 |

## ExposiÃ§Ã£o por categoria operacional

| Classe | Categoria | Valor | Peso | Qtde. |
|---|---|---:|---:|---:|
| acao | acao | R$ 125.811,47 | 43,86% | 14 |
| etf | ETF | R$ 11.718,00 | 4,09% | 1 |
| fi_infra | Infraestrutura (FI-Infra) | R$ 21.271,40 | 7,42% | 3 |
| fiagro | Fiagro | R$ 4.650,00 | 1,62% | 1 |
| fii | HÃ­brido | R$ 32.984,19 | 11,50% | 6 |
| fii | LogÃ­stico | R$ 24.409,23 | 8,51% | 2 |
| fii | Shoppings | R$ 12.823,31 | 4,47% | 3 |
| fii | TÃ­tulos e Valores MobiliÃ¡rios | R$ 27.519,66 | 9,59% | 5 |
| fundo | FMP-FGTS | R$ 6.551,93 | 2,28% | 1 |
| renda_fixa | CDB | R$ 19.106,20 | 6,66% | 10 |

## DimensÃµes documentais

| DimensÃ£o | Estado atual |
|---|---|
| Classe | observado |
| Categoria operacional | observado |
| Economic bucket | classificaÃ§Ã£o operacional |
| Indexador | parcial |
| Emissor | parcial |
| Gestor | gap |
| EstratÃ©gia detalhada | gap |
| Devedor final | gap |
| Grupo econÃ´mico | gap |
| Setor econÃ´mico | gap |
| ConcentraÃ§Ã£o indireta | gap |

## ObservaÃ§Ã£o sobre PCIP11

PCIP11 estÃ¡ classificado no bucket eal_estate_hybrid.
Valor operacional: R$ 4.845,75.
Peso na carteira operacional: 1,6893%.
Sua exposiÃ§Ã£o econÃ´mica detalhada continuarÃ¡ sendo obtida a partir da camada prÃ³pria do ativo e das respectivas evidÃªncias.

## PrÃ³xima camada

A prÃ³xima evoluÃ§Ã£o deverÃ¡ mapear gestores, emissores, devedores, setores, ativos subjacentes e overlap real entre posiÃ§Ãµes.
