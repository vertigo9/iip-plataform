# IIP — Reconciliação: Blueprint vs. Código Real

Verificado diretamente no repositório (`iip_obsidian_integration_v1`, branch `fix/ruff-manual-safe` → `main`), lendo os arquivos-fonte, não a partir de descrições de sessões anteriores. Data original: 10/09/2026. **Atualizado em 18/09/2026** (seção "Fontes de Dados" e nova seção "Camadas superiores" abaixo — o resto do documento original permanece válido).

Legenda: 🟢 Real e funcional | 🟡 Existe parcialmente / difere do diagrama | 🔴 Não implementado (só no diagrama)

## Camada de Interfaces (Clients)

| Caixa do diagrama | Status | Evidência |
|---|---|---|
| CLI (iip, Typer) | 🟡 | `src/iip/cli/main.py` existe e é real (165 linhas, testado em `test_cli_main_coverage.py`, `test_cli_analyze.py`), mas usa **`click` + `rich`**, não Typer como o diagrama descreve. |
| Obsidian (vault local, leitura/escrita Markdown) | 🟢 | `knowledge/repository.py`, `knowledge/vault.py`, `knowledge/projection.py` — todos reais, testados, usados em produção nesta própria sessão. |
| Grafos e backlinks | 🔴 | Não encontrado nenhum código que gere grafo/backlink — isso é uma capacidade nativa do Obsidian como app, não algo que o IIP implementa. |
| Aplicações Externas (Scripts, APIs) | 🟡 | Não há uma "camada de API" dedicada; o que existe é o CLI e chamadas diretas aos módulos Python. |
| Plugins (extensões de coleta, novos provedores) | 🔴 | `src/iip/plugins/__init__.py` tem uma linha — só docstring. Não existe sistema de plugin/extensão. |

## Camada de Orquestração (Core)

| Caixa do diagrama | Status | Evidência |
|---|---|---|
| CLI / Main (ponto de entrada) | 🟢 | Confirmado acima. |
| Framework (pipeline de execução, coordenação de módulos) | 🟡 | Não existe um framework de orquestração central. O mais próximo é `enterprise/orchestrator.py`, com estágios `DISCOVERY → ATLAS → KNOWLEDGE → INTELLIGENCE`, mas é específico do pacote `enterprise/`, não um núcleo usado por todo o Core. |
| Registry (registro de componentes, descoberta de plugins, injeção de dependências) | 🟢 | `src/iip/registry/__init__.py` (76 linhas) — Module Registry + Blueprint Manager + Version Manager, real e testado. "Descoberta de plugins" não se aplica, já que Plugins não existe. |
| Events / Event Bus (publicação/assinatura, eventos de ciclo de vida) | 🟢 | `src/iip/events/__init__.py` — pub/sub assíncrono real, usado de fato por `knowledge/event_adapter.py`. |
| Config (pyproject, perfis de execução, ambientes e credenciais) | 🟢 | `src/iip/config/__init__.py` — `IIPSettings` via `pydantic-settings`, enum `Environment` (development/testing/production), variáveis via `.env`/prefixo `IIP_`. |

## Camada de Fontes e Coleta (Sources & Harvest)

| Caixa do diagrama | Status | Evidência |
|---|---|---|
| Catálogo de Fontes | 🟢 | `sources/catalog.py` real. |
| Source Registry | 🟢 | `sources/registry.py` real, testado. |
| Provider Registry | 🟢 | `providers/registry.py` real. |
| Providers | 🟢 | `providers/` com múltiplos adapters; `xp_asset.py` é o mais maduro (testado extensivamente). |
| Harvesters | 🟡 | `harvest/patria.py` real e testado (495 linhas). É o único harvester dedicado encontrado — o diagrama sugere uma família de harvesters, mas só há esse. |

## Camada de Processamento e Conhecimento (Knowledge)

| Caixa do diagrama | Status | Evidência |
|---|---|---|
| Normalização | 🟢 | `operational/normalization.py` real. |
| Análise (AgroAnalyzer, InfraAnalyzer) | 🟢 | `analysis/agro_analyzer.py`, `analysis/infra_analyzer.py`, `analysis/framework.py` — reais, testados. |
| Knowledge (Models, Repository, Redundancy, Event Adapter/Bridge) | 🟢 | Todo o pacote `knowledge/` — a camada mais madura e mais usada do projeto nesta sessão inteira. |
| Versioning | 🟢 | `versioning/__init__.py` (83 linhas) real. |
| Replication | 🟢 | `replication/__init__.py` (85 linhas) — motor real com `ChangeType`/`ChangeStatus`, não é conceitual. |

## Camada de Persistência e Exportação (Storage & Export)

| Caixa do diagrama | Status | Evidência |
|---|---|---|
| Obsidian Vault | 🟢 | Confirmado acima. |
| Export (relatórios, MD/JSON/CSV) | 🟢 | `export.py` (79 linhas) real, testado. |
| Metrics & Health | 🟡 | Ambos existem (`metrics/__init__.py`, `health/__init__.py`), mas **atenção**: `metrics/` é telemetria operacional (counters/gauges), não estatística financeira — não confundir os dois ao planejar a próxima etapa. |

## Fontes de Dados (Externas) — atualizado 18/09/2026

| Caixa do diagrama | Status | Evidência |
|---|---|---|
| XP Asset | 🟢 | `sources/xp_asset.py` — discovery real, sem parsing de conteúdo. |
| B3 | 🟢 | `sources/b3_bolsai.py`, `b3_brapi.py`, `b3_cotahist.py` (+ harvesters) — preço/fundamentos e histórico de cota real. |
| IBGE | 🟢 | `sources/ibge.py` (SIDRA) — real, sem tabela pré-fixada (API multidimensional, exige que o chamador informe agregado/variável). |
| BACEN | 🟢 | `sources/bacen.py` (SGS) — real, séries SELIC/CDI/IPCA verificadas ao vivo contra dadosabertos.bcb.gov.br. |
| Receita Federal | 🟢 | `sources/receita_federal.py` — via BrasilAPI (auditoria confirmou que a própria Receita não expõe API pública de CNPJ individual). |
| CVM | 🟢 | `cvm_fii.py`, `cvm_fiagro.py`, `cvm_renda_fixa.py` — Informe Mensal/FIAGRO/Diário, dataset aberto oficial. |
| Sparta (gestora) | 🟢 | `sparta_reports.py` — PDF parseado pra cota patrimonial real, único caso de extração estruturada de conteúdo desta sessão. Cobre CRAA11; JURO11/CDII11 usam layout de PDF diferente, não reconhecido (gap documentado, não bloqueante — CVM já cobre esses dois). |
| Pátria (gestora) | 🟢 | `patria_mziq.py` — 5 fundos (HGRU11, LVBI11, HGCR11, PVBI11, PCIP11) via API MZIQ real, sem Playwright em runtime. |
| BTG Pactual (gestora) | 🟢 | `btg_mziq.py` (BTLG11, via MZIQ) + `solutions_ir.py` (BTCI11, plataforma "Solutions IR" — API descoberta por leitura estática de bundle JS, sem executar navegador). |
| 7 gestoras FII restantes | 🟢 | `static_pdf_listing.py` — TRX, Valora, Capitânia, Manati, Rio Bravo, Hedge, Kinea, todas com listagem de PDF direto em HTML estático. |
| Ações (equity RI) | 🟡 | `equity_mziq.py` — 10 das 14 ações da carteira confirmadas na MZIQ (ABCB4, BBSE3, CXSE3, SAUD3, ALOS3, VBBR3, KLBN4, FESA4, LEVE3, PASS3); as outras 4 (ISAE4, CPFE3, CMIG4, CSUD3) usam plataformas próprias, confirmadas mas não implementadas. |

O gap "B3 / IBGE / BACEN / Receita Federal" listado como maior prioridade no resumo executivo abaixo **já foi fechado** — o texto do resumo/roadmap originais (10/09) ficou obsoleto nesse ponto específico.

## Camadas superiores do diagrama (Intelligence → Decision → Validation → Audit) — nota de 18/09/2026

Investigação adicional (não fazia parte do escopo original desta reconciliação, mas foi pedida numa sessão posterior): o repositório tem ~50 pacotes sob `src/iip/`, muito além dos ~15 cobertos acima. Pacotes como `intelligence/`, `decision/`, `portfolio_intelligence/`, `validation_engine/`, `scenario_engine/`, `enterprise_consolidation/` (com `audit_trail.py`) existem com código real — dataclasses e funções puras bem desenhadas, seguindo a mesma disciplina anti-invenção do resto do projeto (ex.: `intelligence/credit_intelligence.py::credit_risk_flags`, `intelligence/decision_eligibility.py::check_ticker_eligibility`).

**Achado central**: essa camada superior é uma **camada de contratos/lógica pura, não um pipeline conectado à evidência real**. O próprio código já documenta isso — `decision/analysis_bridge.py` registra um achado de auditoria (12/09/2026): busca por `analysis.*decision`/`valuation.*decision` no repositório retornou zero resultados; "os dois sistemas são compatíveis em formato, mas nunca foram conectados". Não há também um pacote único correspondente a "Audit/Journal/Alerts" do diagrama — a lógica de auditoria está espalhada (`production/audit.py`, `product/audit.py`, `enterprise_consolidation/audit_trail.py`), e não há "Dashboard/API" — só o CLI.

**Implicação pra priorização**: a base da pirâmide (Data Sources → Atlas/discovery → Knowledge Base) está hoje mais madura e mais recentemente verificada do que o topo (Intelligence → Opportunity Intelligence → Capital/Decision → Validation → Audit). O maior gap real não é mais "faltam fontes de dados" — é a desconexão entre a evidência real já coletada (3467+ arquivos no vault) e as camadas de inteligência/decisão que deveriam consumi-la.

## Resumo executivo

- **Muito mais maduro do que o diagrama sugere**: Knowledge, Replication, Versioning, Registry, Events, Config, e (desde 18/09) toda a camada de Fontes de Dados — todos reais e testados, alguns até mais ricos que a descrição do próprio diagrama.
- **Nomeado diferente do real**: CLI é `click`, não `Typer`.
- **Existe mas é menor que o desenhado**: Framework de orquestração (só dentro de `enterprise/`, não central).
- **Não existe, é 100% aspiracional**: Plugins, Grafos/backlinks (nativo do Obsidian, não do IIP), Dashboard/API HTTP dedicado.
- **Existe como esqueleto, não como pipeline (achado de 18/09)**: Intelligence, Opportunity Intelligence, Decision Engine, Validation, Audit/Journal/Alerts — código real e bem desenhado, mas desconectado da evidência real que Atlas/Knowledge já produzem (ver seção "Camadas superiores" acima).

## O que falta implementar, por ordem sugerida de impacto (revisado 18/09/2026, noite)

1. ~~**Fontes externas B3 / IBGE / BACEN / Receita Federal**~~ — ✅ concluído (18/09/2026): todas as 4 existem como módulos reais, mais CVM, Sparta, Pátria, BTG/Solutions IR, 7 gestoras FII via listagem estática e 10 ações via MZIQ.
2. ~~**Conectar Intelligence/Decision à evidência real**~~ — ✅ concluído pra fundos (18/09/2026): `persist_ready_batch`/`persist_historical_series_metrics` (novos, reais, testados) promoveram 3512+ observações de NAV já coletadas a `Evidence` real; `iip analyze --decide --persist` rodou de ponta a ponta pra 20 fundos (FII/FI-Agro/FI-Infra), com scores genuinamente diferenciados (4,00-6,00/10) citando essa evidência.
3. ~~**Dados fundamentalistas reais de ações**~~ — ✅ concluído (18/09/2026, noite): novo provider `iip.sources.cvm_dfp` (+ harvester) lê a DFP real da CVM (mesmo canal aberto de `cvm_fii.py`) e preenche `equity`/`net_income`/`revenue`/`ebit`/`invested_capital`/crescimento 3y reais em `fetch_equity_template_live`. Rerodei as 14 `Decision` de ações: scores agora vão de 2,40 a 3,64/10, genuinamente diferenciados e coerentes com a realidade de cada empresa (SAUD3, com prejuízo líquido real, no piso; BBSE3, com o maior lucro líquido real do grupo, é a única fora do bucket "ENCERRAR"). Detalhe completo em `vault/07_Research/02_Limitacao_Decisoes_Equity.md`. `debt_to_equity` e os campos qualitativos (moat, governança, gestão, WACC) continuam fora de escopo — não invertidos a partir de demonstração financeira nenhuma.
4. **Sistema de Plugins** — hoje é um pacote vazio; definir o contrato (o que um plugin registra, como é descoberto) antes de qualquer código.
5. **Framework de orquestração central no Core** — hoje cada pacote (`enterprise/`, `operational/`, etc.) tem sua própria mini-orquestração; consolidar seria uma extensão, não uma criação do zero.
6. **Extração de conteúdo estruturado do restante dos documentos coletados** — a maior parte dos ~2000+ documentos de IR no vault (relatórios gerenciais, fatos relevantes etc.) ainda é evidência bruta (PDF), não dado estruturado; a promoção dos itens 2/3 usou dados já estruturados de outros providers (CVM DFP/Informe Mensal, Sparta, B3), não extração de PDF em si (exceto o piloto manual do PCIP11).
