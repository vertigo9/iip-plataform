# IIP — Mapa de ligação ao CLI

Data: 20/09/2026. Pedido do usuário: "assim que for possível ligar tudo ao CLI". Este documento diz **o que** existe fora do CLI, **o que vale ligar, em que ordem e o que falta para cada item**, e o que **não** vale ligar. Nada foi ligado ainda; o mapa é para decidir.

## Como foi medido

`python scripts/diagnostics/cli_reachability.py` segue os imports estáticos (inclusive os feitos dentro de funções) a partir de `iip.cli.main`. Em 20/09/2026, depois do `decide-portfolio`:

- **168 de 457 módulos alcançados; 24.419 de 37.825 linhas (65%).** Em 19/09 eram 139 de 440 (58% das linhas; a contagem de hoje já exclui o módulo raiz, então a diferença de módulos é aproximada).
- Os 289 módulos restantes somam ~13.400 linhas. Quase todos têm testes, mas nenhum comando os usa.

**Limite do método:** "alcançado" é por import, não por uso em produção; e a classificação abaixo vem dos nomes, docstrings e assinaturas de cada módulo, com leitura mais atenta só dos candidatos a ligar (Nível 1 e 2). Não li as 13.400 linhas.

## Achado que muda o mapa

O vault **tem as posições**: `02_Portfolio/Current.md` (fonte Investidor10, lido por `portfolio/vault_snapshot.py`) traz quantidade, preço médio, preço atual, valor e peso de **46 posições ativas, incluindo as 10 de renda fixa bancária que o registro de ativos não acompanha**. (O `Position Registry.md`, ao lado, é um subconjunto de 35 linhas sem a renda fixa bancária e sem o AXIA3; não é a fonte certa.) Por isso as camadas de carteira (exposição, concentração, renda) **têm insumo real**. Três ressalvas:

- **Cobre 36 das 37 posições do registro de ativos**: falta só o **PVBI11**. Uma leitura de exposição precisa dizer isso, em vez de somar 100% de uma carteira incompleta.
- **É uma fotografia sem data no cabeçalho**: a data usada é a de modificação do arquivo (12/09/2026, 8 dias atrás). A regra 4 da nota diz que não é histórico, e hoje ninguém a atualiza automaticamente; os pesos valem tanto quanto a última atualização.
- **Peso-alvo vazio de propósito**: a regra 1 da nota diz "permanece vazio enquanto não existir política formal de alocação". Tudo que rebalanceia ou aporta até um alvo precisa dessa política, que é sua.

## Nível 1 — ligar já (insumo real no vault, sem decisão nova sua)

| # | O quê | Código que já existe | Insumo | Esforço | Por que primeiro |
|---|---|---|---|---|---|
| 1 | **Alerta de mudança de decisão** + `decide-portfolio` no agendador das 08:00 | `integration/decision_history.py` (`changed`), `adaptive/portfolio_alerts.py`; o `decide-portfolio` já traz a coluna "Anterior" | as `DEC-*` de `03_Decisions` | pequeno | fecha o que o PR #17 preparou; o histórico diário que ele gera é o insumo do item 7 |
| 2 | **Exposição e concentração** (por classe, gestora, segmento, risco; alerta acima de um limite), **FEITO em 20/09/2026: `iip portfolio-exposure`** (cobre 36 das 37 posições) | `portfolio_intelligence/{holdings,exposure,manager_intelligence,segment_intelligence}.py`, `intelligence/portfolio_intelligence.py` (`concentration_alerts`) | pesos do Position Registry + `PortfolioAsset` (`manager`, `segment`, `risk_profile`) | pequeno a médio | é a leitura de risco que a carteira ainda não tem; hoje só se sabe o score de cada ativo, não quanto pesa cada gestora |
| 3 | **Renda projetada** (próxima distribuição por cota × quantidade) | **FEITO em 20/09/2026: `iip portfolio-income` e `iip collect-fii-history`.** Fonte: série mensal da CVM (Informe Mensal de FII) já guardada em `02_Portfolio/Historical`, mas que **nenhum comando atualizava** (agora há o `collect-fii-history`). Cobre só FIIs: 12 dos 17 têm série regular o bastante para projetar (26% do valor da carteira); o resto fica sem projeção, com o motivo (CVM traz rendimento zero ou negativo, ou série irregular). Ações, FI-Infra, FI-Agro, ETF, FMP-FGTS e renda fixa bancária não têm série mensal por cota | série da CVM + `Current.md` | feito | a série existe, mas é ruidosa: ver a nota `Renda.md` |

Custo de cota: o 1 acrescenta uma rodada de busca por dia (uma por posição); os 2 e 3 não gastam cota do bolsai.

## Nível 2 — ligar depois, falta um insumo

| # | O quê | Código que já existe | O que falta | Quem resolve |
|---|---|---|---|---|
| 4 | **Aporte mensal e rebalanceamento** | `decision/contribution_{note,persistence}.py`, `integration/contribution.py`, `orchestration/{rebalancing,rebalancing_alerts}.py`, `strategy/{allocation_planner,dividend_priority}.py` | **peso-alvo por ativo ou classe** (coluna vazia) | você |
| 5 | **Sinal de tese real**, no lugar do `Neutro` fixo do `decide-portfolio` | `intelligence/{thesis_signal,event_chain,evidence_chain}.py` | eventos e fatos relevantes **classificados** (item 6) | depende do 6 |
| 6 | **Ciclo de vida documental** (classificar e enriquecer os documentos coletados) | `intelligence/{document_classification,document_enrichment,intelligence_pipeline}.py`, `operational/{normalization,quality,atlas_gateway}.py`, `atlas/{batch,history,full_pipeline}.py` | decidir onde entra no fluxo dos `collect-*-documents` | eu proponho, você aprova |
| 7 | **Validação histórica** (taxa de acerto, calibração, backtest) | `validation_engine/*` | **meses de decisões diárias**: hoje há 2 datas (18 e 20/09) | tempo; ligar o item 1 já começa a acumular |
| 8 | **Macro** (Selic, IPCA, IBGE, Receita) | `sources/{bacen,ibge,receita_federal}*.py` (coletores prontos, sem consumidor) | um **uso**: hoje a única taxa de mercado usada é a NTN-B do Tesouro; sem uma regra que peça Selic ou IPCA, ligar é só coletar por coletar | você |
| 9 | **Benchmark e atribuição de desempenho** | `benchmark/*` | série de retorno por posição (o preço médio e o atual estão no registro; a série vem do COTAHIST que já é evidência) | médio, sem decisão sua |

## Nível 3 — não ligar

**Dez pacotes de "contratos de produção e release" — 3.018 linhas, 109 módulos:** `enterprise`, `enterprise_consolidation`, `production`, `production_integration`, `hardening`, `coverage`, `system`, `platform`, `product`, `operational_integration`. São a mesma ideia desenhada várias vezes, sem consumidor:

- Uma classe `ReleaseGate` em 3 pacotes (`enterprise_consolidation`, `product`, `production`) e um `release.py` em 4 (`production`, `hardening`, `platform`, `product`); `reconciliation.py` em 3; `readiness.py` em 3; `AuditLog` em 2; `pipeline.py` em 6 pacotes; `models.py` em 8.
- O CLI já tem o que eles descrevem, de forma real: `iip health`, o agendador com log e notificação, os gates do CI.

**Pacotes de desenho sobreposto** (`strategy`, `orchestration`, `portfolio_decision`, `scenario_engine`, `cycle` e o `integration/portfolio_pipeline`): o `decide-portfolio` já cumpre o papel do pipeline deles com dado real. Só valem as peças isoladas citadas nos Níveis 1 e 2; o resto fica como está, sem consumidor.

**Recomendação:** tratar o Nível 3 como o motor legado das 18:00: propor a remoção **num PR separado e com o seu OK**, não religar. Não removo nada sem pedido. Antes, faz falta conferir uma vez, módulo a módulo, que nenhum tem chamador fora do `src` (scripts, notebooks).

## Lixo evidente (remoção pequena, para confirmar)

- `knowledge/repository_PATCH3C2.py` e `repository_PATCH3C2_FINAL.py`, `decision/knowledge_bridge.py.bak_PATCH3B`, `sources/patch/*`, `sources/tests_knowledge/*`: remendos e backups dentro do `src`.
- `automation/scheduler.py`: parece ser o agendador do motor legado das 18:00 (confirmar).
- `harvest/patria.py` (1.016 linhas, com `main()` próprio): o coletor da Pátria hoje é o `collect-patria-documents` via MZIQ; este parece o antecessor. **Confirmar** antes de tirar.

## Ordem que recomendo (revista em 20/09/2026, à noite)

**Feito:** itens 1 (alertas de decisão + `decide-portfolio` no agendador), 2 (exposição e concentração) e 3 (renda projetada + `collect-fii-history`).

**O que o item 3 mudou.** A renda deixou de ser algo a desenvolver: há um comando, uma nota persistida (`Renda.md`) e um comando de coleta. Mas duas coisas ficaram menores do que parecem:

- "Rotina de coleta disponível" é um **comando**, ainda não uma **rotina**: nada o roda sozinho. A série já ficou congelada uma vez por isso.
- A camada de dados cobre **26,4% do valor da carteira** na renda (12 FIIs). O resto não tem série mensal por cota, e a série que existe é ruidosa (zero, negativo, repetido).

Por isso o próximo bloco não é mais funcionalidade, e sim **confiabilidade**:

### Bloco A — confiabilidade e frescor dos dados de renda (novo, o próximo)

| # | O quê | Situação hoje | Esforço |
|---|---|---|---|
| A1 | **Rodar o `collect-fii-history` sozinho** | **FEITO (20/09/2026)**: passo no `executar_atualizacao_diaria.ps1` com `--min-age-days 6` (só baixa quando a última atualização tem mais de 6 dias); o mesmo job agora gera `Renda.md` e `Exposicao.md` | pequeno |
| A2 | **Estado de cada série** | **FEITO (20/09/2026)**: `Historical/_estado.json` (situação, última competência, meses, data da atualização, defasada) e a nota `02_Portfolio/Series.md` | pequeno |
| A3 | **Alerta** de série ausente, defasada, zerada ou que piorou | **FEITO (20/09/2026)**: `--alert-file` e notificação do Windows, por MUDANÇA para pior (uma série que já estava ruim não reavisa toda semana). Defasada = última competência com mais de 2 meses de calendário | pequeno |
| A4 | **Validação cruzada com o relatório do gestor**, começando pelos 4 fundos sem projeção (AFHI11, BTCI11, VGIP11, XPML11) | conferido só com o balanço da CVM, em 2 fundos | médio (depende dos PDFs de cada gestora) |
| A5 | **Painel**: `Decisoes`, `Exposicao`, `Renda` e `Series` no `Dashboard.md` | **FEITO (20/09/2026)**: seção "Acompanhamento da Carteira" com 4 blocos que leem o cabeçalho de cada nota (chaves e caminhos definidos uma vez em `obsidian/dashboard.py`); nota ausente ou de versão anterior vira aviso, não tabela vazia; novo `iip dashboard`, rodado pelo job depois das notas. Achado: nenhum comando atual gerava o `Dashboard.md` (só o agendador do motor legado) | pequeno a médio |

**Ressalva sobre A5:** integrar "conforme os contratos existentes" não é pelos pacotes do Nível 3 (contratos duplicados, sem consumidor). O caminho é o `obsidian/dashboard.py`, que já roda.

### Bloco B — cobertura (depois do A)

- **Ações**: dividendo anual do balanço (DFC/bolsai), método diferente do mensal; 14 posições, 43,9% do valor.
- **FI-Infra, FI-Agro**: ver se os relatórios da Sparta trazem a distribuição mensal por cota (hoje só a cota patrimonial).
- Só então o total de renda deixa de ser "26% da carteira".

### Continuam como antes

4. **Peso-alvo** (você define; destrava aporte e rebalanceamento) e **Macro** (você diz o uso).
5. **Ciclo documental → sinal de tese real** (6 → 5) e **validação histórica** (7, só depois de meses de decisões diárias: o item 1 já as acumula).
6. **Nível 3 e o lixo**: PR de limpeza à parte, com o seu OK.

**Ordem:** A1 → A3 → A2 → A5 → A4; depois B; o resto conforme os insumos que dependem de você.

## Decisões do usuário (20/09/2026)

Sobre a proposta de política de peso-alvo e integração macroeconômica:

- **Prioridade da alocação: renda recorrente** (sustentabilidade dos proventos primeiro; crescimento e preservação de capital secundários).
- **Macro: contexto, cenários e ajuste das premissas de valuation.** Não influencia aportes nem pesos.
- **Autonomia do Decision Engine: propor aportes e rebalanceamentos para aprovação.** Nada é executado sozinho (o projeto não tem integração com corretora).
- **Ordem: Bloco A (confiabilidade) e a Entrega B (macro) agora**; o contrato da política de peso-alvo entra quando o usuário definir os pesos.

**Restrições que estas decisões trazem para o desenho** (registradas para não se perderem):

- A política é um **contrato versionado** (classes reais da carteira, peso-alvo, mínimo, máximo, banda, limites por ativo, gestora, setor e emissor, regras de exceção), não constantes no código, e os pesos são **do usuário**.
- **Macro versionado**: os coletores de BACEN/IBGE guardam só data e valor, sem data de publicação nem revisão. Ao persistir, gravar a **data de coleta** de cada observação; só o que foi coletado a partir de então é "conhecido em tal data". Dado macro anterior não serve para backtest de decisão.
- Renda recorrente como prioridade reforça o Bloco A (a renda projetada e a qualidade dela) e faz da sustentabilidade dos proventos o critério central de elegibilidade na política.

## O que esta lista não promete

"Ligar tudo" não é o objetivo certo: cerca de metade das 13.400 linhas fora do CLI é redundante entre si. O objetivo é que **tudo o que gera valor com dado real** esteja num comando, e que o resto seja removido de forma consciente.
