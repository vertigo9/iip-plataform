from datetime import date

from iip.decision.scoring_note import format_opportunity_note
from iip.portfolio_decision.opportunity import build


def test_format_opportunity_note_includes_all_components():
    opportunity = build("pcip11", intrinsic_score=9.0, allocation_gap=0.5, income_need=0.5)

    note = format_opportunity_note(opportunity, as_of=date(2026, 7, 31))

    assert "7.88" in note  # final_score rounds to 7.875 -> 7.88 at 2 decimals
    assert "9.00" in note  # intrinsic_score
    assert "0.50" in note  # allocation_gap and income_need share this value
    assert "2026-07-31" in note


def test_format_opportunity_note_reflects_bounded_inputs():
    opportunity = build("XPML11", intrinsic_score=15, allocation_gap=-1, income_need=2)

    note = format_opportunity_note(opportunity, as_of=date(2026, 7, 31))

    assert "10.00" in note  # intrinsic_score clamped to 10
    assert "0.00" in note  # allocation_gap clamped to 0
