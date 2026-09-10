"""Gate deciding whether a ticker has enough promoted evidence to persist
a decision or score.

Reuses the already-validated ``PersistenceBatch`` contract from
``metric_persistence``/``metric_persistence_adapter`` instead of
re-implementing evidence-quality checks. A ticker is eligible when at
least one of its metric observations made it through the Promotion Gate
(status IDENTITY_READY, IDENTITY_READY_WITH_DIMENSION or DEDUPLICABLE —
see ``PersistenceBatch.ready``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .metric_persistence import PersistenceBatch


@dataclass(frozen=True)
class EligibilityResult:
    ticker: str
    eligible: bool
    reason: str


def check_ticker_eligibility(batch: PersistenceBatch, ticker: str) -> EligibilityResult:
    """Check whether ``ticker`` has at least one promoted (ready) observation."""

    normalized = ticker.strip().upper()
    if not normalized:
        return EligibilityResult(ticker, False, "empty_ticker")

    for candidate in batch.ready:
        if candidate.observation.canonical_ticker.strip().upper() == normalized:
            return EligibilityResult(normalized, True, "has_promoted_observation")

    return EligibilityResult(normalized, False, "no_promoted_observation_for_ticker")
