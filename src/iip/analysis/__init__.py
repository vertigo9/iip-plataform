from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class Pillar(Enum):
    BUSINESS_MODEL = "business_model"
    MOAT = "moat"
    GROWTH = "growth"
    MANAGEMENT = "management"
    CASH_FLOW = "cash_flow"
    GOVERNANCE = "governance"
    DIVIDENDS = "dividends"
    CAPITAL_ALLOCATION = "capital_allocation"
    RESILIENCE = "resilience"


@dataclass
class PillarScore:
    pillar: Pillar
    score: float
    weight: float
    indicators: dict[str, float] = field(default_factory=dict)
    comments: str = ""

    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass
class AnalysisReport:
    asset_symbol: str
    asset_type: str
    analyzed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    pillar_scores: list[PillarScore] = field(default_factory=list)
    overall_score: float = 0.0
    recommendation: str = ""
    risk_level: str = ""
    notes: str = ""

    def add_pillar(self, score: PillarScore) -> None:
        self.pillar_scores.append(score)

    def calculate_overall(self) -> float:
        total_weight = sum(p.weight for p in self.pillar_scores)
        weighted_sum = sum(p.weighted_score() for p in self.pillar_scores)
        self.overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        return self.overall_score

    def set_recommendation(self) -> None:
        score = self.overall_score
        if score >= 80:
            self.recommendation = "Strong Buy"
            self.risk_level = "Low"
        elif score >= 65:
            self.recommendation = "Buy"
            self.risk_level = "Low-Medium"
        elif score >= 50:
            self.recommendation = "Hold"
            self.risk_level = "Medium"
        elif score >= 35:
            self.recommendation = "Reduce"
            self.risk_level = "Medium-High"
        else:
            self.recommendation = "Sell"
            self.risk_level = "High"

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_symbol": self.asset_symbol,
            "asset_type": self.asset_type,
            "analyzed_at": self.analyzed_at,
            "overall_score": round(self.overall_score, 2),
            "recommendation": self.recommendation,
            "risk_level": self.risk_level,
            "pillar_scores": [
                {
                    "pillar": p.pillar.value,
                    "score": p.score,
                    "weight": p.weight,
                    "indicators": p.indicators,
                }
                for p in self.pillar_scores
            ],
            "notes": self.notes,
        }


# Import analyzers for convenience. These live below the dataclass
# definitions above (Pillar/PillarScore/AnalysisReport) on purpose: the
# analyzer modules import those names from this package, so importing
# them any earlier would create a circular import.
from iip.analysis.agro_analyzer import AgroAnalyzer
from iip.analysis.framework import AssetData, EquityAnalyzer, FIIAnalyzer
from iip.analysis.infra_analyzer import InfraAnalyzer

__all__ = [
    "AgroAnalyzer",
    "AnalysisReport",
    "AssetData",
    "EquityAnalyzer",
    "FIIAnalyzer",
    "InfraAnalyzer",
    "Pillar",
    "PillarScore",
]
