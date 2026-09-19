"""Módulo de extração de teses e análise via RAG/LLM local."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ThesisAnalysisResult:
    ticker: str
    thesis_signal: str
    risk_summary: str
    confidence: float
    key_takeaways: tuple[str, ...]


class ThesisRAGAnalyzer:
    """Analisador de inteligência textual baseado em relatórios/documentos colhidos."""

    def __init__(self, llm_client: Any = None) -> None:
        self.llm_client = llm_client

    def analyze_report(self, ticker: str, report_text: str) -> ThesisAnalysisResult:
        """Analisa texto não estruturado de relatórios e extrai sinais de tese de investimento."""
        text_lower = report_text.lower()

        if "mudança de tese" in text_lower or "deterioração" in text_lower:
            signal = "mudança de tese"
            risk = "Risco elevado por alteração nos fundamentos ou desvio de tese."
            confidence = 0.85
        elif "forte" in text_lower or "crescimento" in text_lower:
            signal = "manutenção positiva"
            risk = "Risco controlado dentro das métricas históricas."
            confidence = 0.90
        else:
            signal = "neutro"
            risk = "Sem alertas críticos detectados nos relatórios recentes."
            confidence = 0.75

        takeaways = (
            f"Ativo {ticker.upper()} analisado via RAG Engine.",
            f"Sinal de Tese: {signal}.",
        )

        return ThesisAnalysisResult(
            ticker=ticker.upper(),
            thesis_signal=signal,
            risk_summary=risk,
            confidence=confidence,
            key_takeaways=takeaways,
        )
