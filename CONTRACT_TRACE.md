# Contract Trace — AnalysisReport -> Decision -> Knowledge

> Rastreamento pedido em 12/09/2026: seguir a cadeia
> `AnalysisReport -> analyzer_bridge -> IntelligenceInput -> Decision ->
> Opportunity/Score -> Validation/Audit -> Knowledge` usando só os
> arquivos e testes reais do repositório, sem assumir nada — cada elo
> abaixo tem arquivo, linha e teste citados. Onde a cadeia pedida não
> corresponde ao que o código realmente faz, isso está dito
> explicitamente, não escondido.
>
> Resultado principal: **existem DOIS caminhos reais e testados**, não
> um. Um roda hoje de ponta a ponta (validado com dado real do usuário
> nesta sessão). O outro é mais completo e o próprio código se declara
> "canônico" — mas nunca foi exposto a nenhuma interface de usuário.

## Elo 1 — AnalysisReport -> IntelligenceInput

**Arquivo**: `src/iip/decision/analysis_bridge.py` (construído nesta
sessão, em resposta a um achado da auditoria: buscas por
`analysis.*decision` e `valuation.*decision` em todo `src/iip` davam
zero resultado antes disso).

**Função**: `analysis_to_intelligence_input(report, *, thesis_signal,
evidence, valuation_score=None)`.

**Teste real**: `tests/test_analysis_decision_bridge.py` (7 testes) +
`tests/test_cli_analyze_decide.py` (6 testes, via CLI).

**Achado honesto preservado no código**: não existe pilar de
"valuation" nos 9 pilares dos 5 analisadores (confirmado por busca
exata: zero resultado pra `intrinsic_value`, `price_target`, `DCF`,
`Graham`, `Bazin` no projeto inteiro). `valuation_score` nunca é
derivado de outro pilar por proxy — fica neutro (5.0) com aviso
explícito quando não fornecido.

## Elo 2 — IntelligenceInput -> Decision

**Arquivo**: `src/iip/decision/decision_engine.py::decide()` +
`src/iip/decision/scoring.py::composite_score()`/`confidence_score()`.

**Teste real**: `tests/test_decision_301_500.py` (`test_decision_buy`,
`test_composite_score`, `test_confidence_uses_evidence_and_risk`,
`test_thesis_change_overrides_high_score_toward_wait`).

**Confirmado**: escala 0-10 (não 0-100), `risk_level` só reconhece
`"Baixo"/"Médio"/"Alto"` — qualquer outro valor recebe penalidade de
confiança de 0.15 silenciosamente (é por isso que `analysis_bridge`
mapeia explicitamente em vez de repassar o inglês do
`AnalysisReport.risk_level`).

## Elo 3 — Decision -> Knowledge (Caminho A: o que roda hoje)

**Arquivo**: `src/iip/decision/knowledge_bridge.py::to_knowledge_decision()`
+ `src/iip/knowledge/bridge.py::KnowledgeBridge.persist_decision()`
(que por sua vez chama `src/iip/knowledge/audit.py::DecisionAuditor.audit()`
antes de gravar).

**Comando CLI real**: `iip analyze --decide --persist` (construído
nesta sessão) + `iip persist-evidence` (idem).

**Teste real**: `tests/test_cli_analyze_decide.py::
test_decide_persist_succeeds_with_real_pre_existing_evidence` — e
**validado com dado real do usuário nesta mesma sessão**: BTLG11 gerou
`DEC-BTLG11-2026-09-12`, reconstruído depois via
`KnowledgeBridge.assemble()`.

**Contrato enforçado**: `DecisionAuditor` exige que todo `evidence_id`
citado já exista persistido no vault — se não existir, a persistência
falha com `ValueError`, confirmado ao vivo com `EV-RELATORIO-2026-08`
não existente antes de ser criado via `iip persist-evidence`.

## Elo 3 (variante) — Decision -> Opportunity/Score -> Knowledge (Caminho B: existe, nunca exposto)

Aqui a cadeia pedida pelo usuário não bate 1:1 com o código — existe
algo **mais rico** que isso, com um nome diferente, e ele nunca
chegou a nenhum comando CLI.

**Arquivo**: `src/iip/decision/persistence.py::persist_decision_if_eligible()`

**O que essa função faz de verdade** (confirmado lendo o código e o
teste):
1. Recebe um `EngineDecision` (o mesmo `Decision` do Elo 2).
2. Checa elegibilidade via
   `iip.intelligence.decision_eligibility.check_ticker_eligibility()`
   — exige que o ticker tenha pelo menos uma observação de métrica
   "Promotion-Gate-eligible" num `PersistenceBatch`
   (`iip.intelligence.metric_persistence`). **Isso é um portão de
   qualidade que o Caminho A (o que está no CLI hoje) não tem.**
3. Se elegível: persiste via `to_knowledge_decision` +
   `KnowledgeBridge.persist_decision` (mesmíssimo mecanismo do Elo 3A).
4. Opcionalmente aceita um `Opportunity` — mas **não qualquer um**: o
   próprio `portfolio_decision/opportunity.py` se autodeclara no
   docstring como "Canonical Opportunity Score implementation — use
   this for any new scoring/ranking work", citando explicitamente que
   é usado por esta mesma função. Formata a nota via
   `format_opportunity_note()` e grava na seção `opportunity_score` da
   nota de scoring do ativo — a MESMA nota `{ticker} - Score e
   Ranking.md` onde `sync_analysis_projection` (usado por `iip analyze
   --persist`) grava a seção `IIP:analysis`.

**Teste real**: `tests/test_decision_persistence.py` (5 testes,
incluindo `test_opportunity_is_formatted_automatically_into_scoring_note`
e `test_ineligible_ticker_persists_nothing` — prova que o portão de
elegibilidade genuinamente bloqueia, não é decorativo).

**Achado honesto**: `grep` confirma **zero** referência a
`PersistenceBatch`, `metric_persistence` ou `decision_eligibility` em
`src/iip/cli/main.py`. Essa é uma biblioteca real, internamente
coesa, com 6 módulos de produção se referenciando de verdade
(`intelligence.metric_persistence`, `.metric_persistence_adapter`,
`.decision_eligibility`, `decision.persistence`,
`.income_forecast_persistence`, `.contribution_persistence`) — mas
**nenhuma interface de usuário jamais a alcança**. O que constrói o
`PersistenceBatch` de entrada é um pipeline de ingestão de CSV de
métricas (`intelligence.metric_persistence_adapter`) que também nunca
foi conectado a nenhum comando real.

## Duplicatas genuínas encontradas no caminho (não a mesma coisa por acaso)

`Opportunity` existe em **pelo menos 4 lugares**, cada um com formato
e propósito diferente — o próprio código já documenta isso, não é
achado novo, mas vale consolidar aqui:

| Módulo | O que é | Status (segundo o próprio código) |
|---|---|---|
| `portfolio_decision.opportunity` | Fórmula real: `intrinsic*(0.75 + 0.125*gap + 0.125*income)` | **Canônico**, autodeclarado, wired em `decision.persistence` |
| `decision.opportunity` | `Opportunity(ticker, score, rationale)` — só ordena, não calcula | Utilitário de ranking puro, não é a mesma coisa (docstring já avisa) |
| `orchestration.opportunity_map` | Fórmula própria, mais antiga | **Legado**, autodeclarado no docstring de `portfolio_decision.opportunity` |
| `portfolio_intelligence.opportunity_radar` | Fórmula própria, mais antiga | **Legado**, idem |

`ScoreComponent`/`AssetScoreSummary` — verificado por busca direta
(`grep -rl "class ScoreComponent\|class AssetScoreSummary"`): existem
só em `portfolio_decision.score_aggregation`, um lugar só. Não são
duplicata — a lista de "Duplicate candidate" da auditoria estava
quebrada por escape de regex (relatado antes) e teria sugerido o
contrário sem essa checagem direta.

## Elo 4 — "Validation/Audit" pedido na cadeia: não existe como um bloco só

A cadeia pedida junta "Validation" e "Audit" num elo só, mas no código
real são **duas coisas completamente desconectadas**:

- **Audit real, conectado a Decision**: `knowledge.audit.DecisionAuditor`
  (Elo 3A/3B acima) — sempre executa antes de qualquer
  `persist_decision`.
- **Validation**: `src/iip/validation_engine/` (backtest, hit rate,
  calibration, regime, returns, stress) — confirmado por busca
  direta: **zero** importação em qualquer direção entre
  `src/iip/decision/` e `src/iip/validation_engine/`. O único
  consumidor real de `validation_engine` é `src/iip/benchmark/performance.py`,
  não o pipeline de decisão.

Ou seja: uma `Decision` real, persistida hoje, **nunca passa** por
`validation_engine` — não há backtest, hit rate ou calibração
aplicada a nenhuma decisão de verdade neste momento.

## Conclusão — qual é o caminho canônico real do IIP hoje

**Caminho que roda de ponta a ponta, testado, e confirmado com dado
real do usuário nesta sessão** (Caminho A):

```
AnalysisReport
  -> analysis_bridge.analysis_to_intelligence_input()
  -> IntelligenceInput
  -> decision_engine.decide()
  -> Decision (EngineDecision)
  -> decision.knowledge_bridge.to_knowledge_decision()
  -> KnowledgeBridge.persist_decision()
       -> DecisionAuditor.audit()  [único portão de qualidade neste caminho]
  -> vault (03_Decisions/, reconstruível via KnowledgeBridge.assemble())
```

Acessível hoje via `iip analyze --decide --persist` +
`iip persist-evidence`.

**Caminho mais completo, real e testado, mas sem nenhuma porta de
entrada de usuário** (Caminho B):

```
[CSV de métricas] -> intelligence.metric_persistence_adapter
  -> PersistenceCandidate / PersistenceBatch
  -> intelligence.decision_eligibility.check_ticker_eligibility()  [portão extra: Promotion-Gate]
       + Decision (do mesmo decision_engine.decide() do Caminho A)
       + portfolio_decision.opportunity.build()  [fórmula canônica de Opportunity Score]
  -> decision.persistence.persist_decision_if_eligible()
  -> vault (decisão + nota de scoring "opportunity_score" na mesma nota do Caminho A)
```

Existe só como biblioteca — nenhum comando CLI o alcança.

**Recomendação, não decisão tomada aqui**: se o objetivo é ter um
único caminho canônico de verdade, as opções honestas são (a) expor o
Caminho B via CLI/automação, aposentando o Caminho A mais simples, ou
(b) manter os dois deliberadamente (A para decisão pontual/manual via
CLI, B para o pipeline de ingestão em lote) e documentar essa
distinção — mas escolher às cegas sem decidir isso deixa dois sistemas
de persistência de decisão coexistindo sem que ninguém tenha decidido
qual é o de verdade.
