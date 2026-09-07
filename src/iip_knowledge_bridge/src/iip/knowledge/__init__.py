"""Persistent knowledge and decision layer for IIP."""

from .audit import DecisionAuditor
from .bridge import KnowledgeBridge
from .context import ContextAssembler, KnowledgeContext
from .models import (
    Decision,
    DecisionChange,
    Evidence,
    Exposure,
    PortfolioSnapshot,
    Position,
    Verdict,
)
from .redundancy import find_redundant_exposures
from .repository import ObsidianRepository

__all__ = [
    "ContextAssembler",
    "Decision",
    "DecisionAuditor",
    "DecisionChange",
    "Evidence",
    "Exposure",
    "KnowledgeBridge",
    "KnowledgeContext",
    "ObsidianRepository",
    "PortfolioSnapshot",
    "Position",
    "Verdict",
    "find_redundant_exposures",
]
