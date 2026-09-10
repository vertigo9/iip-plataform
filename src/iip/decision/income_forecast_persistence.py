"""Persist an income (proventos) forecast into the vault.

Same composition pattern as ``persistence.py`` and
``contribution_persistence.py``: reuses
``intelligence.decision_eligibility.check_ticker_eligibility`` for the
gate and ``KnowledgeBridge`` for the write. The forecast itself is
computed by ``portfolio_data.income_forecast.forecast_next_distribution``
— this module only decides whether/where to persist it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from iip.intelligence.decision_eligibility import (
    EligibilityResult,
    check_ticker_eligibility,
)
from iip.intelligence.metric_persistence import PersistenceBatch
from iip.knowledge.bridge import KnowledgeBridge
from iip.portfolio_data.income_forecast import IncomeForecast

from .income_forecast_note import format_income_forecast_note


@dataclass(frozen=True)
class IncomeForecastPersistenceOutcome:
    eligibility: EligibilityResult
    persisted: bool
    note_path: Path | None


def persist_income_forecast_if_eligible(
    forecast: IncomeForecast,
    *,
    batch: PersistenceBatch,
    bridge: KnowledgeBridge,
    asset_class: str,
) -> IncomeForecastPersistenceOutcome:
    """Project ``forecast`` onto the asset's scoring note, but only if
    the ticker has at least one Promotion-Gate-eligible observation in
    ``batch``. When not eligible, nothing is written.
    """

    eligibility = check_ticker_eligibility(batch, forecast.ticker)

    if not eligibility.eligible:
        return IncomeForecastPersistenceOutcome(
            eligibility=eligibility,
            persisted=False,
            note_path=None,
        )

    note = format_income_forecast_note(forecast)
    result = bridge.sync_asset_section(
        eligibility.ticker,
        asset_class,
        "scoring",
        "income_forecast",
        note,
    )

    return IncomeForecastPersistenceOutcome(
        eligibility=eligibility,
        persisted=True,
        note_path=result.path,
    )
