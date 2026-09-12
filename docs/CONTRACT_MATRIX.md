# Matriz de Contratos por Dominio

> Complementa (nao substitui) o `docs/CONTRACTS.md`, que lista nomes de
> evento e responsabilidades numa frase. Esta matriz mapeia cada
> dominio do blueprint pra codigo real, e classifica o status de prova
> em tres niveis, sem arredondar pra cima:
>
> - **Provado ponta-a-ponta**: existe teste que encadeia o dominio com
>   pelo menos um vizinho real (nao so unidades isoladas).
> - **Provado isoladamente**: tem teste real, mas nunca foi encadeado
>   com o resto do sistema numa jornada so.
> - **Sem uso real / so scaffolding**: modulo existe, as vezes ate com
>   teste proprio, mas nenhum caller real fora do proprio teste (mesmo
>   padrao encontrado varias vezes ao longo do projeto: orquestradores,
>   scheduler shells etc.).
>
> Levantado em 12/09/2026, por auditoria direta do codigo (grep +
> leitura + execucao de teste), nao por inferencia do nome dos
> pacotes.

## 1. Fontes de dados (sources)

| Modulo | Contrato | Status |
|---|---|---|
| `sources/cvm_fii.py` + harvester | Informe Mensal FII (CVM) | Provado ponta-a-ponta (dado real validado ao vivo + usado por `fetch-template`/`refresh-portfolio`) |
| `sources/cvm_fiagro.py` + harvester | Informe Mensal FIAGRO (CVM) | Provado isoladamente (validado ao vivo, nunca conectado a `fetch-template`) |
| `sources/cvm_renda_fixa.py` + harvester | Informe Diario + Perfil Mensal (ICVM 555) | Provado ponta-a-ponta (usado por ETF e fixed_income no `fetch-template`) |
| `sources/bacen.py`, `sources/ibge.py` | SGS / Agregados | Provado isoladamente (validado ao vivo, sem consumidor no produto ainda) |
| `sources/b3_bolsai.py`, `sources/b3_brapi.py` | Cotacao/fundamentos B3 | Provado ponta-a-ponta (FII/ETF/equity no `fetch-template`) |
| `sources/receita_federal.py` | Cadastro CNPJ | Provado isoladamente |
| `sources/mziq.py` | Documentos de RI | Provado isoladamente |
| `providers/registry.py`, `providers/factory.py` | Plugin manifest + injecao de credencial | Provado ponta-a-ponta (usado pelo sistema de credenciais desta sessao) |

## 2. Atlas (deteccao e ingestao documental)

| Modulo | Contrato | Status |
|---|---|---|
| `atlas/pipeline.py` (`XPAssetAtlasPipeline`) | `atlas.document.processed.v1` (implicito, sem emissor de evento literal) | Provado ponta-a-ponta (via `test_seven_state_acceptance.py` e `test_xpml11_full_e2e.py`) |
| `atlas/knowledge_adapter.py` | Projecao Atlas -> Knowledge | Provado ponta-a-ponta |
| `harvest/patria.py` | Scraper institucional (Playwright) | Provado isoladamente (48 testes proprios, nunca encadeado com Atlas/Knowledge num teste so) |
| `atlas.event.materiality_evaluated.v1` (citado no CONTRACTS.md) | -- | **Nao existe implementacao alguma.** Zero ocorrencias de "materiality"/"materialidade" no codigo fonte inteiro. O conceito mais proximo que de fato existe e' `intelligence.thesis_signal` + `decision.decision_engine`, que nao emitem esse evento nomeado. |

## 3. Research / Intelligence

| Modulo | Contrato | Status |
|---|---|---|
| `intelligence/document_classification.py` | Classificacao de titulo -> `DocumentType` | Provado ponta-a-ponta |
| `intelligence/document_enrichment.py` | Metadado + tags dedupe | Provado ponta-a-ponta |
| `intelligence/evidence_chain.py` | Evidencia idempotente por documento | Provado ponta-a-ponta |
| `intelligence/thesis_signal.py` | Observacao de tese com evidencia associada | Provado ponta-a-ponta |
| `intelligence/intelligence_pipeline.py` (`stage_document`) | Encadeia classificacao+enriquecimento+evidencia | Provado ponta-a-ponta -- essa e' a peca central que a jornada de aceite reutiliza |
| `intelligence/event_chain.py` | Grafo de eventos (nos + arestas) | Provado isoladamente |
| `intelligence/credit_intelligence.py` | Flags de risco de credito | Provado isoladamente |
| `intelligence/portfolio_intelligence.py` | Alertas de concentracao | Provado isoladamente |

## 4. Decision

| Modulo | Contrato | Status |
|---|---|---|
| `decision/decision_engine.py` (`decide`) | `IntelligenceInput` -> `Decision` (verdict/score/confidence) | Provado ponta-a-ponta |
| `decision/knowledge_bridge.py` (`to_knowledge_decision`) | Converte decisao do engine pro formato persistivel | Provado ponta-a-ponta |
| `decision/opportunity.py` | Ranking deterministico de oportunidades | Provado isoladamente |
| `decision/valuation_bridge.py`, `decision/risk_bridge.py` | Score de valuation / penalidade de risco | Provado isoladamente |
| `decision/portfolio_decision.py` | Sumario de carteira a partir de decisoes | Provado isoladamente |
| `decision/pipeline.py` (`run`) | Pipeline generico de decisao | Existe, sem teste de encadeamento real verificado nesta auditoria |
| "`iip.decision.created.v1`" (citado no CONTRACTS.md) | -- | Nomeado no contrato, sem emissor de evento literal encontrado -- o que existe de fato e' a chamada direta `to_knowledge_decision` + `persist_decision`, nao um barramento de evento publicando esse nome |

## 5. Knowledge

| Modulo | Contrato | Status |
|---|---|---|
| `knowledge/bridge.py` (`KnowledgeBridge`) | Fachada unica de persistencia (evidencia, decisao, snapshot, secao de ativo, analise) | Provado ponta-a-ponta |
| `knowledge/repository.py` (`ObsidianRepository`) | Grafia de arquivo append-only, nomes seguros pra Windows | Provado ponta-a-ponta |
| `knowledge/audit.py` (`DecisionAuditor`) | Decisao so persiste se toda evidencia citada ja existir | Provado ponta-a-ponta -- **e onde achamos e corrigimos o bug real de sanitizacao de nome de arquivo nesta sessao** |
| `knowledge/vault.py` | Localizacao canonica por classe de ativo (agora com etf/infra/agro tambem) | Provado ponta-a-ponta |
| `knowledge/projection.py`, `knowledge/sync.py` | Secao gerenciada idempotente (`IIP:BEGIN`/`IIP:END`) | Provado ponta-a-ponta |
| "`knowledge.sync.completed.v1`" / "`.failed.v1`" / "`knowledge.redundancy.detected.v1`" (citados no CONTRACTS.md) | -- | Mesma observacao: os NOMES existem no contrato, o comportamento real (status CREATED/UPDATED/UNCHANGED, deteccao de redundancia via `bridge.redundancy()`) existe e e' testado, mas nao ha um barramento de evento publicando literalmente esses nomes de topico |

## 6. Portfolio

| Modulo | Contrato | Status |
|---|---|---|
| `portfolio/registry.py` (`PORTFOLIO_ASSETS`) | Registro real da carteira do usuario, com CNPJ verificado | Provado ponta-a-ponta (validado com dado real nesta sessao) |
| `portfolio/refresh.py` | Atualizacao em lote por classe de ativo | Provado ponta-a-ponta |
| `portfolio_data/`, `portfolio_decision/`, `portfolio_intelligence/` | Concentracao, moeda, exposicao | Provado isoladamente cada um -- nunca encadeados entre si nem com `portfolio/registry.py` num teste so |

## 7. Treasury

| Modulo | Contrato | Status |
|---|---|---|
| -- | -- | **Nao existe.** Nenhum modulo, funcao ou mencao a caixa/liquidez/funding em todo o codigo fonte. Se esse dominio faz parte do escopo do produto, e' trabalho novo, nao uma lacuna de conexao entre pecas existentes. |

## 8. Validation

| Modulo | Contrato | Status |
|---|---|---|
| `validation_engine/backtest.py`, `hit_rate.py`, `regime.py`, `returns.py`, `stress.py` | Metricas de validacao de tese/decisao no tempo | Provado isoladamente |
| `hardening/scenario_harness.py`, `certification_pipeline.py`, `determinism.py` | Certificacao de cenario, determinismo | Provado isoladamente |
| `hardening/provider_failover.py` | Comportamento de fallback entre providers | Provado isoladamente |

## Infraestrutura transversal (nao e' um dominio de produto, da' suporte a todos)

`cli/`, `config/`, `core/`, `health/`, `events/`, `metrics/`, `registry/`,
`replication/`, `versioning/`, `logging/`, `common/`, `exceptions/` --
todos com teste proprio; a maioria com uso real comprovado nesta sessao
(config/credenciais, health/monitoramento, cli/comandos). `events/`,
`metrics/`, `registry/`, `replication/` sao registros globais via
`@classmethod` (confirmado na limpeza do Ruff RUF012) -- existem e
funcionam, mas sem consumidor real fora dos proprios testes ainda.

## Scaffolding sem dominio de produto claro (~20 pacotes)

`adaptive/`, `benchmark/`, `coverage/`, `cycle/`, `enterprise/`,
`enterprise_consolidation/`, `integration/`, `operational/`,
`operational_integration/`, `orchestration/`, `platform/`, `plugins/`,
`product/`, `production/`, `production_integration/`, `strategy/`,
`synchronization/`, `system/`, `universal/`.

Cobertura de teste geralmente alta em cada um isoladamente, mas -- como
ja documentado ao longo desta sessao (ver docstrings com "audit
finding" nesses modulos) -- a maioria nao tem nenhum caller real fora
do proprio arquivo de teste. Nao e' lixo pra apagar as cegas (varios
tem logica valida), mas tambem nao e' algo que o produto hoje usa de
verdade. Contribuiu boa parte dos ~57 BLE001 tratados na limpeza do
Ruff, todos no mesmo padrao de "isola falha, embrulha resultado" que
nunca chega a ser chamado por nada real.

## Resumo honesto

- **Maturidade real e comprovada de ponta a ponta**: fontes de dados
  (parcial), Atlas, Research/Intelligence, Decision, Knowledge,
  Portfolio (parcial).
- **Existe mas nunca foi encadeado**: boa parte de Portfolio
  (portfolio_data/decision/intelligence entre si), Validation inteiro,
  metade das fontes de dados (BACEN/IBGE/FIAGRO/MZIQ).
- **Nao existe**: Treasury.
- **Nomeado no contrato, sem implementacao literal**: os eventos
  especificos citados em `CONTRACTS.md` (materiality_evaluated,
  decision.created, knowledge.sync.*) -- o comportamento que eles
  descrevem existe via chamada direta de funcao, nao via barramento de
  evento publicando esses topicos exatos. Se o barramento de eventos
  literal importa pro produto, e' trabalho novo; se o que importa e' o
  comportamento, ja esta' coberto.
