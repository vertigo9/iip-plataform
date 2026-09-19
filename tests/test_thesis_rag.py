"""Testes unitários para o analisador RAG de teses de investimento."""

from iip.intelligence.thesis_rag import ThesisRAGAnalyzer


def test_thesis_rag_analysis_positive():
    analyzer = ThesisRAGAnalyzer()
    text = "O fundo apresentou forte crescimento no trimestre com receita acima do esperado."
    result = analyzer.analyze_report("HGLG11", text)

    assert result.ticker == "HGLG11"
    assert result.thesis_signal == "manutenção positiva"
    assert result.confidence == 0.90


def test_thesis_rag_analysis_thesis_change():
    analyzer = ThesisRAGAnalyzer()
    text = "Notamos uma deterioração nos fundamentos e potencial mudança de tese no médio prazo."
    result = analyzer.analyze_report("PETR4", text)

    assert result.ticker == "PETR4"
    assert result.thesis_signal == "mudança de tese"
    assert result.confidence == 0.85
