from datetime import date

from iip.decision.contribution_note import format_contribution_note
from iip.integration.contribution import ContributionCandidate


def test_format_contribution_note_includes_score_and_share():
    candidate = ContributionCandidate(
        ticker="PCIP11", score=8.5, monthly_budget_share=0.4
    )

    note = format_contribution_note(candidate, as_of=date(2026, 7, 31))

    assert "8.50" in note
    assert "40.00%" in note
    assert "2026-07-31" in note
