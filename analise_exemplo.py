from iip.analysis.framework import AssetData, EquityAnalyzer

data = AssetData(
    symbol="CSUD3.SA",
    sector="Meu Setor",
    industry="Minha Industria",
    financials={
        "ebit": 1e9,
        "net_income": 800e6,
        "revenue": 10e9,
        "equity": 8e9,
        "revenue_growth_3y": 5.0,
        "earnings_growth_3y": 6.0,
        "dividend_yield": 7.5,
        "debt_to_equity": 0.5,
        "interest_coverage": 6.0,
    },
)

analyzer = EquityAnalyzer()
report = analyzer.analyze(data)

print("==========================================")
print("RESULTADO DA ANÁLISE")
print("==========================================")
print(f"Asset: {report.asset_symbol}")
print(f"Score Global: {report.overall_score:.1f}/100")
print(f"Recomendacao: {report.recommendation}")
print(f"Nivel de Risco: {report.risk_level}")
print("==========================================")
