---
type: portfolio_overlap_mapping
schema_version: "0.1"
scope: portfolio
portfolio_value: 286845.39
position_count: 46
state: current
status: active
---

# Portfolio Overlap Mapping v0.1

Mapa inicial de sobreposicoes documentais e candidatos de sobreposicao economica.

## Regra metodologica

Overlap confirmado exige uma identidade comum comprovada.
Adjacency representa exposicao a uma atividade economica semelhante, mas nao prova o mesmo ativo, devedor, emissor ou grupo economico.

## 1. Concentracao por gestora

| Gestora | Posicoes | Valor | Peso |
|---|---|---:|---:|
| Alianza | ALZR11 | R$ 3.190,74 | 1,11% |
| BTG Pactual | BTLG11, BTCI11 | R$ 13.576,73 | 4,73% |
| Capitania | CPTI11 | R$ 6.526,40 | 2,28% |
| Daycoval | FMP-FGTS-DAYCOVAL | R$ 6.551,93 | 2,28% |
| Hedge | HGBS11 | R$ 2.366,01 | 0,82% |
| HSI | HSML11 | R$ 5.324,80 | 1,86% |
| Investo | LFTB11 | R$ 11.718,00 | 4,09% |
| Kinea | KNRI11 | R$ 2.479,20 | 0,86% |
| Manati/ICM | MANA11 | R$ 6.373,20 | 2,22% |
| Patria | LVBI11, HGRU11, PCIP11, HGCR11 | R$ 32.501,70 | 11,33% |
| Rio Bravo | RBVA11 | R$ 3.848,67 | 1,34% |
| Sparta | CDII11, JURO11, CRAA11 | R$ 19.395,00 | 6,76% |
| TRX | TRXF11 | R$ 8.694,00 | 3,03% |
| Valora | VGIP11 | R$ 5.642,24 | 1,97% |
| XP Asset | XPML11 | R$ 5.132,50 | 1,79% |

A concentracao por gestora representa concentracao operacional/gerencial. Ela nao equivale a concentracao economica dos ativos subjacentes.

## 2. PCIP11 dentro da carteira

| Metrica | Valor |
|---|---:|
| Valor da posicao | R$ 4.845,75 |
| Peso na carteira | 1,6893% |
| Gestora | Patria |
| Peso sob Patria | 11,33% |

## 3. Sobreposicao direta de FIIs

| FII subjacente do PCIP11 | Peso no PCIP11 | Presente na carteira |
|---|---:|---|
| Nenhum overlap direto identificado | N/A | N/A |

O relatorio de julho/2026 identifica oito FIIs na carteira do PCIP11. Nesta carteira atual nenhum desses oito tickers foi encontrado como posicao direta.

## 4. Candidatos de sobreposicao economica

| Tema | Exposicao PCIP11 | Ativos da carteira | Relacao | Status |
|---|---|---|---|---|
| Retail | 20 percent of CRI portfolio | ALOS3 | economic_adjacency | partial |
| Shopping | 7 percent of CRI portfolio | ALOS3;HSML11;XPML11;HGBS11 | economic_adjacency | partial |
| Energy | energy segment exists in CRI portfolio | ISAE4;CMIG4;CPFE3 | economic_adjacency | partial |
| Logistics | 9 percent of CRI portfolio | LVBI11;BTLG11 | economic_adjacency | partial |
| Construction Finance | 13 percent of CRI portfolio | none directly identified | economic_adjacency | observed |

## 5. Dimensoes ainda nao confirmadas

- mesmo devedor
- mesma operacao de credito
- mesmo imovel
- mesmo grupo economico
- mesmo emissor de CRI
- mesma contraparte
- exposicao economica identica

Estas dimensoes somente serao elevadas de candidato para overlap confirmado quando houver evidencia especifica.

## 6. Proxima evolucao

Mapear devedores, emissores, indexadores e ativos subjacentes dos fundos de credito da carteira.
Prioridade: VGIP11, AFHI11, HGCR11, BTCI11 e MANA11.

## 7. Regra de decisao

Um novo aporte deve ser avaliado pela exposicao nova que acrescenta a carteira, e nao apenas pelo seu peso nominal.
