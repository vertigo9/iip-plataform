"""Persist monthly contribution-ranking results (aportes) into the vault.

Composition, same pattern as ``persistence.py`` for decisions: reuses
``intelligence.decision_eligibility.check_ticker_eligibility`` for the
gate and ``KnowledgeBridge`` (already wired to ``AssetVaultLocator``) for
the write. No new ranking logic — ``integration.contribution.prioritize_contributions``
already computes the candidates; this module only decides whether/where
to persist each one.

``asset_class`` is not carried by ``ContributionCandidate`` (it is lost
by ``integration.allocation.rank`` upstream), so the caller supplies a
``ticker -> asset_class`` mapping built from the original ``AssetSignal``
tuple.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path

from iip.integration.contribution import ContributionCandidate
from iip.intelligence.decision_eligibility import (
    EligibilityResult,
    check_ticker_eligibility,
)
from iip.intelligence.metric_persistence import PersistenceBatch
from iip.knowledge.bridge import KnowledgeBridge

from .contribution_note import format_contribution_note


@dataclass(frozen=True)
class ContributionPersistenceOutcome:
    ticker: str
    eligibility: EligibilityResult
    persisted: bool
    note_path: Path | None


def persist_contributions_if_eligible(
    candidates: tuple[ContributionCandidate, ...],
    *,
    batch: PersistenceBatch,
    bridge: KnowledgeBridge,
    asset_classes: dict[str, str],
    date: _date,
) -> tuple[ContributionPersistenceOutcome, ...]:
    """Persist a "monthly_contribution" note per candidate, skipping any
    ticker that either lacks Promotion-Gate-eligible evidence or is
    missing from ``asset_classes``. Never raises for either condition —
    both are reported as a not-persisted outcome so one bad ticker does
    not abort the whole batch.
    """

    outcomes: list[ContributionPersistenceOutcome] = []

    for candidate in candidates:
        ticker = candidate.ticker.strip().upper()
        asset_class = asset_classes.get(ticker)

        if asset_class is None:
            outcomes.append(
                ContributionPersistenceOutcome(
                    ticker=ticker,
                    eligibility=EligibilityResult(ticker, False, "missing_asset_class"),
                    persisted=False,
                    note_path=None,
                )
            )
            continue

        eligibility = check_ticker_eligibility(batch, ticker)
        if not eligibility.eligible:
            outcomes.append(
                ContributionPersistenceOutcome(
                    ticker=ticker,
                    eligibility=eligibility,
                    persisted=False,
                    note_path=None,
                )
            )
            continue

        note = format_contribution_note(candidate, as_of=date)
        result = bridge.sync_asset_section(
            ticker, asset_class, "scoring", "monthly_contribution", note
        )

        outcomes.append(
            ContributionPersistenceOutcome(
                ticker=ticker,
                eligibility=eligibility,
                persisted=True,
                note_path=result.path,
            )
        )

    return tuple(outcomes)
