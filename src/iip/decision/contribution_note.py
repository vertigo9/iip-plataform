"""Render a monthly ContributionCandidate (from
``integration.contribution.prioritize_contributions``) into note content.

Same posture as ``scoring_note.py``: this module only formats an
already-computed candidate, it does not rank or score anything itself.
"""

from __future__ import annotations

from datetime import date as _date

from iip.integration.contribution import ContributionCandidate


def format_contribution_note(candidate: ContributionCandidate, *, as_of: _date) -> str:
    return (
        f"- **Prioridade de aporte:** {candidate.score:.2f}\n"
        f"- Fatia do orçamento mensal: {candidate.monthly_budget_share:.2%}\n"
        f"- Atualizado em: {as_of.isoformat()}"
    )
