# IIP — Institutional Investment Platform

**Versão:** 2.0.0-complete
**Status:** ✅ Production Ready
**Framework Análise:** V11.0 Consolidated

Plataforma institucional de análise de investimentos cobrindo **ações**, **FIIs**,
**FI-Infra** e **FI-Agro** listados na B3.

---

## 🚀 Instalação Rápida
bash pip install -e ".[dev]"
python -m iip.cli.main version      # Versão da plataforma
python -m iip.cli.main health       # Health checks (7 componentes)
python -m iip.cli.main status       # Status da plataforma
python -m iip.cli.main modules      # Módulos registrados
python -m iip.cli.main metrics      # Métricas operacionais
python -m iip.cli.main replication  # Status de replication
python -m iip.cli.main config       # Configuração ativa

---

## 📊 Atlas Monitor — Framework V11.0

### 4 Analyzers Disponíveis

| Analyzer | Tipo | Casos de Uso |
|----------|------|--------------|
| **EquityAnalyzer** | Ações B3 | VALE3, PETR4, ITUB4, etc. |
| **FIAnalyzer** | Fundos Imobiliários | HGLG11, MXRF11, KNCR11, etc. |
| **InfraAnalyzer** | FI-Infra | BTLG11, XPML11, VISC11, etc. |
| **AgroAnalyzer** | FI-Agro | RZAG11, LOGF11, HGRU11, etc. |

### 9 Pilares de Análise

1. **Business Model** — Modelo de negócio e rentabilidade
2. **Moat** — Vantagens competitivas sustentáveis
3. **Growth** — Crescimento sustentado
4. **Management** — Gestão alinhada aos acionistas
5. **Cash Flow** — Geração de caixa consistente
6. **Governance** — Governança corporativa
7. **Dividends** — Política de dividendos
8. **Capital Allocation** — Alocação eficiente de capital
9. **Resilience** — Resiliência financeira

### Recomendações Automáticas

| Score | Recommendation | Risk Level |
|-------|---------------|------------|
| ≥ 80 | Strong Buy | Low |
| 65-79 | Buy | Low-Medium |
| 50-64 | Hold | Medium |
| 35-49 | Reduce | Medium-High |
| < 35 | Sell | High |

---

## 💻 Exemplos de Uso

### Análise de Ação (Equity)
---

## 📊 Atlas Monitor — Framework V11.0

### 4 Analyzers Disponíveis

| Analyzer | Tipo | Casos de Uso |
|----------|------|--------------|
| **EquityAnalyzer** | Ações B3 | VALE3, PETR4, ITUB4, etc. |
| **FIAnalyzer** | Fundos Imobiliários | HGLG11, MXRF11, KNCR11, etc. |
| **InfraAnalyzer** | FI-Infra | BTLG11, XPML11, VISC11, etc. |
| **AgroAnalyzer** | FI-Agro | RZAG11, LOGF11, HGRU11, etc. |

### 9 Pilares de Análise

1. **Business Model** — Modelo de negócio e rentabilidade
2. **Moat** — Vantagens competitivas sustentáveis
3. **Growth** — Crescimento sustentado
4. **Management** — Gestão alinhada aos acionistas
5. **Cash Flow** — Geração de caixa consistente
6. **Governance** — Governança corporativa
7. **Dividends** — Política de dividendos
8. **Capital Allocation** — Alocação eficiente de capital
9. **Resilience** — Resiliência financeira

### Recomendações Automáticas

| Score | Recommendation | Risk Level |
|-------|---------------|------------|
| ≥ 80 | Strong Buy | Low |
| 65-79 | Buy | Low-Medium |
| 50-64 | Hold | Medium |
| 35-49 | Reduce | Medium-High |
| < 35 | Sell | High |

---

## 💻 Exemplos de Uso

### Análise de Ação (Equity)python from iip.analysis.framework import AssetData, EquityAnalyzer

data = AssetData( symbol="PETR4.SA", sector="Petróleo", industry="Integrado", financials={ "ebit": 50000000000, "net_income": 40000000000, "revenue": 450000000000, "equity": 400000000000, "invested_capital": 500000000000, "revenue_growth_3y": 8.5, "earnings_growth_3y": 12.0, "dividend_yield": 8.0, "debt_to_equity": 0.4, # ... outros indicadores } )

analyzer = EquityAnalyzer() report = analyzer.analyze(data)

print(f"Score: {report.overall_score:.1f}/100") print(f"Recommendation: {report.recommendation}") print(f"Risk Level: {report.risk_level}")

### Análise de FII
python from iip.analysis.framework import AssetData, FIIAnalyzer

data = AssetData( symbol="HGLG11.SA", sector="Imobiliário", industry="Logística", financials={ "occupancy_rate": 0.97, "avg_lease_term_years": 9, "dividend_yield": 10.5, "npa_growth_3y": 12.0, # ... outros indicadores } )

analyzer = FIIAnalyzer() report = analyzer.analyze(data)

print(f"Score: {report.overall_score:.1f}/100") print(f"Recommendation: {report.recommendation}")
---

---

## 🧪 Testes
bash
python -m pytest -v --cov=iip --cov-report=term-missing


Rodar todos os testes
python -m pytest -v --cov=iip --cov-report=term-missing

Teste específico
python -m pytest tests/test_analysis_framework.py -v


**Status Atual:** 54/54 testes passando (0.59 segundos)

---

## 📁 Estrutura do Projeto
src/iip/ ├── core/ # Runtime, lifecycle, context ├── config/ # Configuration Manager ├── events/ # Event Bus (pub/sub) ├── registry/ # Module Registry ├── health/ # Health Engine (7 checks) ├── versioning/ # Version Manager ├── metrics/ # Metrics Engine ├── replication/ # Replication Engine (RFC→ADR) ├── synchronization/ # Sync Engine ├── exceptions/ # Exception Framework ├── logging/ # Structured Logging ├── analysis/ # Atlas Monitor Framework V11.0 ⭐ │ ├── init.py │ ├── framework.py # Core + Equity + FII analyzers │ ├── infra_analyzer.py │ └── agro_analyzer.py ├── cli/ # CLI entrypoint └── plugins/ # Plugin Manager (reserved)


---

---

## 🔧 Arquitetura

A plataforma segue **DDD + Clean Architecture**:

- **Interfaces** → CLI, API (futuro)
- **Application** → Orchestration de use cases
- **Domain** → Regras de negócio (núcleo)
- **Infrastructure** → DB, APIs externas, file IO

---

## 📈 Próximas Versões

| Versão | Objetivo |
|--------|----------|
| v2.1.0 | Exportação PDF/HTML + Charts |
| v2.2.0 | Integração API B3/Yahoo Finance |
| v2.3.0 | Dashboard Web interativo |
| v3.0.0 | Multi-language support + ML predictions |

---

## 📝 Changelog Completo

Ver [CHANGELOG.md](CHANGELOG.md) para histórico detalhado de todas as versões.

---

## 🤝 Contribuição

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para guias de contribuição.

---

## 📞 Suporte

- Issues: GitHub Issues
- Docs: ./docs/
- Email: iip-support@proton.me

---

## 📄 Licença

Proprietary — IIP Team © 2026

