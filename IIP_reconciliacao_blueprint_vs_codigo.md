# IIP — Reconciliação: Blueprint vs. Código Real

Verificado diretamente no repositório (`iip_obsidian_integration_v1`, branch `fix/ruff-manual-safe` → `main`), lendo os arquivos-fonte, não a partir de descrições de sessões anteriores. Data: 10/09/2026.

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

## Fontes de Dados (Externas)

| Caixa do diagrama | Status | Evidência |
|---|---|---|
| XP Asset | 🟢 | `sources/xp_asset.py` — o provider mais maduro do projeto. |
| B3 | 🔴 | Não encontrado em nenhum lugar do código. |
| IBGE | 🔴 | Não encontrado. |
| BACEN | 🔴 | Não encontrado. |
| Receita Federal | 🔴 | Não encontrado. |
| Outras Fontes | 🟡 | Existem sim, mas são outras: `cvm`, `fnet`, `sec`, e as gestoras (`patria`, `sparta`, `btg`, `capitania`, `rio_bravo`, `kinea`, `manati`, `hedge`, `araujo_fontes`) — confirmadas em `sources/policy.py`. |

## Resumo executivo

- **Muito mais maduro do que o diagrama sugere**: Knowledge, Replication, Versioning, Registry, Events, Config — todos reais e testados, alguns até mais ricos que a descrição do próprio diagrama.
- **Nomeado diferente do real**: CLI é `click`, não `Typer`.
- **Existe mas é menor que o desenhado**: Harvesters (só `patria.py`), Framework de orquestração (só dentro de `enterprise/`, não central).
- **Não existe, é 100% aspiracional**: Plugins, Grafos/backlinks (nativo do Obsidian, não do IIP), B3, IBGE, BACEN, Receita Federal.

## O que falta implementar, por ordem sugerida de impacto

1. **Fontes externas B3 / IBGE / BACEN / Receita Federal** — maior gap declarado no diagrama; cada uma é um provider novo seguindo o padrão já validado em `xp_asset.py`.
2. **Sistema de Plugins** — hoje é um pacote vazio; definir o contrato (o que um plugin registra, como é descoberto) antes de qualquer código.
3. **Framework de orquestração central no Core** — hoje cada pacote (`enterprise/`, `operational/`, etc.) tem sua própria mini-orquestração; consolidar seria uma extensão, não uma criação do zero.
4. **Harvesters adicionais** — replicar o padrão de `patria.py` para as gestoras que já têm `Provider` registrado mas não têm harvester dedicado.
