# Guia de Usuário — Atlas Monitor V11.0

## Índice

1. [Introdução](#introdução)
2. [Primeiros Passos](#primeiros-passos)
3. [Analisadores Disponíveis](#analisadores-disponíveis)
4. [Os 9 Pilares Explicados](#os-9-pilares-explicados)
5. [Exemplos Completos](#exemplos-completos)
6. [Interpretando Resultados](#interpretando-resultados)
7. [Melhores Práticas](#melhores-práticas)
8. [FAQ](#faq)

---

## Introdução

O **Atlas Monitor** é um framework de análise quantitativa institucional que avalia
investimentos através de 9 pilares fundamentais. Desenvolvido para análise de:

- **Ações B3** (EquityAnalyzer)
- **Fundos Imobiliários** (FIAnalyzer)
- **Fundos de Infraestrutura** (InfraAnalyzer)
- **Fundos Agrícolas** (AgroAnalyzer)

---

## Primeiros Passos

### 1. Importar Módulos

python from iip.analysis.framework import AssetData, EquityAnalyzer

from iip.analysis import FIIAnalyzer, InfraAnalyzer, AgroAnalyzer

### 2. Preparar Dados
python data = AssetData( symbol="PETR4.SA", sector="Petróleo", industry="Integrado", financials={ # Dicionário com indicadores financeiros "ebit": 50000000000, "net_income": 40000000000, # ... } )

### 3. Analisar
python analyzer = EquityAnalyzer() report = analyzer.analyze(data)

---

## Analisadores Disponíveis

### EquityAnalyzer (Ações)

**Indicadores Requeridos:**
- ebit, 
et_income, evenue, equity, invested_capital
- evenue_growth_3y, earnings_growth_3y
- dividend_yield, payout_ratio
- debt_to_equity, interest_coverage

### FIAnalyzer (Fundos Imobiliários)

**Indicadores Requeridos:**
- occupancy_rate, vg_lease_term_years
- dividend_yield, 
pa_growth_3y
- management_fee_ratio, leverage_to_npa

### InfraAnalyzer (Fundos de Infra)

**Indicadores Requeridos:**
- evenue_stability_score, concession_remaining_years
- cash_flow_predictability_score
- mandatory_payout_ratio

### AgroAnalyzer (Fundos Agrícolas)

**Indicadores Requeridos:**
- land_quality_score, crop_diversification_score
- yield_improvement_trend
- harvest_consistency_score
- dividend_yield_pct

---

## Os 9 Pilares Explicados

### 1. Business Model

**O que mede:** Qualidade e rentabilidade do modelo de negócios.

**Indicadores-chave:**
- ROIC (Return on Invested Capital)
- ROE (Return on Equity)
- Margem EBIT

**Pontuação alta:** >70 indica modelo robusto e lucrativo.

---

### 2. Moat

**O que mede:** Vantagens competitivas sustentáveis.

**Indicadores-chave:**
- Estabilidade da margem bruta
- Poder de precificação
- Custos de troca para clientes

**Pontuação alta:** >70 indica "fosso econômico" forte.

---

### 3. Growth

**O que mede:** Capacidade de crescimento sustentável.

**Indicadores-chave:**
- Crescimento de receita (3 anos)
- Crescimento de lucros (3 anos)
- Crescimento do valor patrimonial

**Pontuação alta:** >70 indica tração de crescimento sólida.

---

### 4. Management

**O que mede:** Alinhamento e qualidade da gestão.

**Indicadores-chave:**
- Participação acionária da gestão (skin in the game)
- Tempo de experiência
- Alinhamento de interesses

**Pontuação alta:** >70 indica gestão confiável.

---

### 5. Cash Flow

**O que mede:** Geração e qualidade do fluxo de caixa.

**Indicadores-chave:**
- Conversão de caixa livre
- Crescimento do caixa operacional
- Intensidade de CAPEX

**Pontuação alta:** >70 indica caixa saudável.

---

### 6. Governance

**O que mede:** Qualidade da governança corporativa.

**Indicadores-chave:**
- Independência do conselho
- Transações com partes relacionadas
- Qualidade da auditoria

**Pontuação alta:** >70 indica governança robusta.

---

### 7. Dividends

**O que mede:** Sustentabilidade e atratividade dos dividendos.

**Indicadores-chave:**
- Dividend yield
- Payout ratio
- Consistência histórica

**Pontuação alta:** >70 indica política de dividendos atraente.

---

### 8. Capital Allocation

**O que mede:** Eficiência na alocação de capital.

**Indicadores-chave:**
- Spread ROIC vs WACC
- Histórico de aquisições
- Eficácia de buybacks

**Pontuação alta:** >70 indica alocação inteligente.

---

### 9. Resilience

**O que mede:** Resistência financeira em cenários adversos.

**Indicadores-chave:**
- Endividamento
- Cobertura de juros
- Liquidez corrente

**Pontuação alta:** >70 indica resiliência sólida.

---

## Exemplos Completos

### Exemplo 1: Análise Completa de Ação
python from iip.analysis.framework import AssetData, EquityAnalyzer import json

Dados de PETR4 (simulados)
petr4_data = AssetData( symbol="PETR4.SA", sector="Petróleo e Gás", industry="Exploração e Refino", financials={ "ebit": 52000000000, "net_income": 41000000000, "revenue": 470000000000, "equity": 410000000000, "invested_capital": 520000000000, "revenue_growth_3y": 8.5, "earnings_growth_3y": 12.0, "book_value_growth_3y": 7.0, "gross_margin_stability": 65, "pricing_power": 60, "switching_costs": 55, "insider_ownership": 3, "management_tenure_years": 6, "skin_in_game_ratio": 2, "fcf_conversion_ratio": 0.82, "ocf_growth_3y": 7.5, "capex_to_revenue": 0.20, "board_independence": 0.55, "related_party_transactions_ratio": 0.03, "audit_quality_score": 72, "dividend_yield": 9.5, "payout_ratio": 0.75, "dividend_consistency_years": 8, "wacc": 9.0, "acquisition_success_score": 50, "buyback_effectiveness": 55, "debt_to_equity": 0.45, "interest_coverage": 5.5, "current_ratio": 1.4, } )

analyzer = EquityAnalyzer() report = analyzer.analyze(petr4_data)

Exibir resultados
print(f"Empresa: {report.asset_symbol}") print(f"Score Global: {report.overall_score:.1f}/100") print(f"Sugestão: {report.recommendation}") print(f"Nível de Risco: {report.risk_level}") print("") print("Detalhamento por Pilar:") for ps in report.pillar_scores: print(f" {ps.pillar.value}: {ps.score:.1f}/100 (peso: {ps.weight*100:.0f}%)")

Exportar JSON
report_json = report.to_dict() with open("petr4_analysis.json", "w") as f: json.dump(report_json, f, indent=2, ensure_ascii=False)

print("") print("Relatório exportado para: petr4_analysis.json")

---

---

## Interpretando Resultados

### Scores Gerais

| Faixa | Significado | Ação Recomendada |
|-------|-------------|------------------|
| 80-100 | Excelente | Strong Buy — Ativos premium |
| 65-79 | Bom | Buy — Boa relação risco/retorno |
| 50-64 | Adequado | Hold — Observar mudanças |
| 35-49 | Fraco | Reduce — Considerar redução |
| 0-34 | Ruim | Sell — Evitar ou vender |

### Scores por Pilar

| Score | Interpretação |
|-------|---------------|
| 80-100 | Forte vantagem competitiva |
| 65-79 | Acima da média do setor |
| 50-64 | Médio — dentro do esperado |
| 35-49 | Abaixo da média — atenção |
| 0-34 | Fraqueza crítica |

### Quando Investigar Mais

**Pilar abaixo de 50 merece investigação:**
1. É problema pontual ou estrutural?
2. Tendência de melhoria ou piora?
3. Compensado por outros pilares fortes?

---

## Melhores Práticas

### 1. Use Dados Consistente

- Prefira dados dos últimos 12 meses (LTM)
- Mantenha consistência metodológica
- Compare com benchmarks do setor

### 2. Combine com Análise Qualitativa

- O score não substitui leitura de relatórios
- Use como ferramenta complementar
- Considere contexto macroeconômico

### 3. Acompanhe Evolução Temporal

- Faça análises periódicas (trimestral)
- Compare com períodos anteriores
- Identifique tendências

### 4. Valide Hipóteses

- Entenda por que cada pilar pontua assim
- Verifique se dados refletem realidade
- Ajuste pesos conforme estratégia pessoal

---

## FAQ

### Q: Os pesos dos pilares são fixos?

**R:** Sim, atualmente fixos pelo Framework V11.0. Futuras versões permitirão customização.

### Q: Posso usar para ativos internacionais?

**R:** Atualmente otimizado para B3. Adaptação necessária para outros mercados.

### Q: Como obter dados financeiros reais?

**R:** Sugere-se integração com APIs como Brapi, Yahoo Finance, ou dados manuais de demonstrações.

### Q: Qual a frequência recomendada de análise?

**R:** Trimestralmente após divulgação de resultados ou quando houver mudança material significativa.

### Q: O score garante lucro?

**R:** Não. É ferramenta de avaliação quantitativa que deve ser combinada com outras análises.

---

## Suporte

Para dúvidas adicionais:
- GitHub Issues
- Email: iip-support@proton.me
- Docs completos: ./docs/
