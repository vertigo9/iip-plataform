# IIP — Mapa de ligação ao CLI

Data: 20/09/2026. Pedido do usuário: "assim que for possível ligar tudo ao CLI". Este documento diz **o que** existe fora do CLI, **o que vale ligar, em que ordem e o que falta para cada item**, e o que **não** vale ligar. Nada foi ligado ainda; o mapa é para decidir.

## Como foi medido

`python scripts/diagnostics/cli_reachability.py` segue os imports estáticos (inclusive os feitos dentro de funções) a partir de `iip.cli.main`. Em 20/09/2026, depois do `decide-portfolio`:

- **168 de 457 módulos alcançados; 24.419 de 37.825 linhas (65%).** Em 19/09 eram 139 de 440 (58% das linhas; a contagem de hoje já exclui o módulo raiz, então a diferença de módulos é aproximada).
- Os 289 módulos restantes somam ~13.400 linhas. Quase todos têm testes, mas nenhum comando os usa.

**Limite do método:** "alcançado" é por import, não por uso em produção; e a classificação abaixo vem dos nomes, docstrings e assinaturas de cada módulo, com leitura mais atenta só dos candidatos a ligar (Nível 1 e 2). Não li as 13.400 linhas.

## Achado que muda o mapa

O vault **tem as posições**: `02_Portfolio/Position Registry.md` (fonte Investidor10) traz quantidade, preço médio, preço atual, valor e peso, e `portfolio/vault_snapshot.py` já sabe lê-lo. Por isso as camadas de carteira (exposição, concentração, renda) **têm insumo real**. Três ressalvas:

- **Cobre 35 das 37 posições da carteira**: faltam **AXIA3** (fundo do FGTS, que não está numa corretora) e **PVBI11**. Uma leitura de exposição precisa dizer isso, em vez de somar 100% de uma carteira incompleta.
- **É uma fotografia sem data no cabeçalho** (e a regra 4 da própria nota diz que não é histórico). Os pesos valem tanto quanto a última atualização dela; hoje ninguém a atualiza automaticamente.
- **Peso-alvo vazio de propósito**: a regra 1 da nota diz "permanece vazio enquanto não existir política formal de alocação". Tudo que rebalanceia ou aporta até um alvo precisa dessa política, que é sua.

## Nível 1 — ligar já (insumo real no vault, sem decisão nova sua)

| # | O quê | Código que já existe | Insumo | Esforço | Por que primeiro |
|---|---|---|---|---|---|
| 1 | **Alerta de mudança de decisão** + `decide-portfolio` no agendador das 08:00 | `integration/decision_history.py` (`changed`), `adaptive/portfolio_alerts.py`; o `decide-portfolio` já traz a coluna "Anterior" | as `DEC-*` de `03_Decisions` | pequeno | fecha o que o PR #17 preparou; o histórico diário que ele gera é o insumo do item 7 |
| 2 | **Exposição e concentração** (por classe, gestora, segmento, risco; alerta acima de um limite), com a ressalva de cobrir 35 das 37 posições | `portfolio_intelligence/{holdings,exposure,manager_intelligence,segment_intelligence}.py`, `intelligence/portfolio_intelligence.py` (`concentration_alerts`) | pesos do Position Registry + `PortfolioAsset` (`manager`, `segment`, `risk_profile`) | pequeno a médio | é a leitura de risco que a carteira ainda não tem; hoje só se sabe o score de cada ativo, não quanto pesa cada gestora |
| 3 | **Renda projetada** (próxima distribuição por cota × quantidade) | `portfolio_data/income_forecast.py`, `decision/income_forecast_{note,persistence}.py`, `portfolio_intelligence/income_intelligence.py` | quantidade (Position Registry, 35 de 37) + histórico de distribuição por cota | médio | **a verificar**: preciso confirmar de onde sai o histórico mensal por cota para os 37 ativos antes de prometer |

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

## Ordem que recomendo

1. **Item 1** (alertas + `decide-portfolio` no agendador): pequeno, fecha o PR #17 e começa a acumular o histórico do item 7.
2. **Item 2** (exposição e concentração): maior ganho de leitura de risco, com dado que já temos.
3. **Item 3** (renda projetada), depois de eu confirmar a fonte do histórico por cota.
4. Em paralelo, **você define o peso-alvo** (item 4 destrava aporte e rebalanceamento) e diz se quer o Macro (item 8).
5. Itens 5, 6, 7 e 9 quando houver o insumo, nessa ordem de dependência (6 → 5; 7 só depois de alguns meses).
6. Nível 3 e o lixo: PR de limpeza à parte, quando você autorizar.

## O que esta lista não promete

"Ligar tudo" não é o objetivo certo: cerca de metade das 13.400 linhas fora do CLI é redundante entre si. O objetivo é que **tudo o que gera valor com dado real** esteja num comando, e que o resto seja removido de forma consciente.
