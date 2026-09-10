"""Render the canonical Opportunity Score as the note content projected
into an asset's "scoring" section.

Uses ``iip.portfolio_decision.opportunity.Opportunity`` — the one chosen
as canonical among the four pre-existing Opportunity Score
implementations found during the persistence audit. This module does not
compute the score; it only formats an already-built ``Opportunity`` for
persistence.
"""

from __future__ import annotations

from datetime import date as _date

from iip.portfolio_decision.opportunity import Opportunity


def format_opportunity_note(opportunity: Opportunity, *, as_of: _date) -> str:
    return (
        f"- **Opportunity Score final:** {opportunity.final_score:.2f}\n"
        f"- Score intrínseco: {opportunity.intrinsic_score:.2f}\n"
        f"- Gap de alocação: {opportunity.allocation_gap:.2f}\n"
        f"- Necessidade de renda: {opportunity.income_need:.2f}\n"
        f"- Atualizado em: {as_of.isoformat()}"
    )
