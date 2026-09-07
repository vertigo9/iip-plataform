from iip.portfolio_decision.opportunity import build, rank


def test_required_opportunity_contract():
    result = build("hgru11", 9, 0.5, 0.5)
    assert result.ticker == "HGRU11"
    assert result.final_score == 7.875


def test_bounds_are_preserved():
    result = build("cpfe3", 20, -1, 3)
    assert result.intrinsic_score == 10
    assert result.allocation_gap == 0
    assert result.income_need == 1
    assert result.final_score == 8.75


def test_ranking_is_deterministic():
    a = build("A", 9, 0.5, 0.5)
    b = build("B", 8, 0.5, 0.5)
    assert tuple(item.ticker for item in rank((b, a))) == ("A", "B")
