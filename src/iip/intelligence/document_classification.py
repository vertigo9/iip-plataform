"""Document classification for Atlas ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DocumentType(StrEnum):
    RELATORIO_GERENCIAL = "relatorio_gerencial"
    FATO_RELEVANTE = "fato_relevante"
    COMUNICADO = "comunicado"
    RESULTADOS = "resultados"
    INFORME = "informe"
    OUTROS = "outros"


@dataclass(frozen=True)
class ClassifiedDocument:
    document_id: str
    ticker: str
    title: str
    provider: str
    document_type: DocumentType
    confidence: float


def classify_title(
    document_id: str, ticker: str, title: str, provider: str
) -> ClassifiedDocument:
    normalized = title.casefold()
    if "relatório gerencial" in normalized or "relatorio gerencial" in normalized:
        kind = DocumentType.RELATORIO_GERENCIAL
    elif "fato relevante" in normalized:
        kind = DocumentType.FATO_RELEVANTE
    elif "comunicado" in normalized:
        kind = DocumentType.COMUNICADO
    elif "resultado" in normalized:
        kind = DocumentType.RESULTADOS
    elif "informe" in normalized:
        kind = DocumentType.INFORME
    else:
        kind = DocumentType.OUTROS
    return ClassifiedDocument(
        document_id, ticker.upper(), title.strip(), provider, kind, 1.0
    )
