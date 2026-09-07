"""Portfolio strategy engine with explicit contribution threshold."""

from __future__ import annotations

from .models import StrategyDecision, StrategyInput, StrategySignal


def build_signal(item: StrategyInput) -> StrategySignal:
    quality = max(0.0, min(10.0, item.score * item.confidence))
    income = max(0.0, min(10.0, item.income_yield * 100.0))
    valuation = max(0.0, min(10.0, (1.0 + item.margin_of_safety) * 5.0))
    risk = max(0.0, min(10.0, item.risk_score))
    gap = max(0.0, min(1.0, item.target_weight - item.current_weight))
    return StrategySignal(
        item.ticker.upper(),
        round(quality, 12),
        round(income, 12),
        round(valuation, 12),
        round(risk, 12),
        round(gap, 12),
    )


def decide(item: StrategyInput) -> StrategyDecision:
    signal = build_signal(item)
    priority = (
        signal.quality_score * 0.35
        + signal.income_score * 0.20
        + signal.valuation_score * 0.30
        + signal.allocation_gap * 10.0 * 0.15
        - signal.risk_score * 0.10
    )

    rationale = []
    if signal.quality_score >= 7:
        rationale.append("quality")
    if signal.income_score >= 6:
        rationale.append("income")
    if signal.valuation_score >= 6:
        rationale.append("valuation")
    if signal.allocation_gap > 0:
        rationale.append("underweight")
    if signal.risk_score >= 7:
        rationale.append("high_risk")

    # Contribution contract:
    # priority >= 6.0 + positive allocation gap -> APORTAR.
    # This is intentionally separate from the >= 7.0 high-priority band.
    if signal.risk_score >= 9:
        action = "REVISAR"
    elif priority >= 6.0 and signal.allocation_gap > 0:
        action = "APORTAR"
    elif priority >= 6.0:
        action = "MANTER"
    else:
        action = "AGUARDAR"

    return StrategyDecision(
        signal.ticker,
        round(priority, 12),
        action,
        tuple(rationale),
    )
