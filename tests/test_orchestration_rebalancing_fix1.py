from iip.orchestration.rebalancing import compute_needs


def test_rebalancing_delta_and_order_prioritize_increases():
    result = compute_needs(
        (("HGRU11", 0.10), ("CPFE3", 0.10)),
        (("HGRU11", 0.15), ("CPFE3", 0.05)),
    )
    assert result[0].ticker == "HGRU11"
    assert result[0].delta == 0.05
    assert result[1].ticker == "CPFE3"
    assert result[1].delta == -0.05


def test_new_position_is_positive_need():
    result = compute_needs(
        (),
        (("XPML11", 0.10),),
    )
    assert result[0].ticker == "XPML11"
    assert result[0].delta == 0.10


def test_removed_position_is_negative_need():
    result = compute_needs(
        (("XPML11", 0.10),),
        (),
    )
    assert result[0].ticker == "XPML11"
    assert result[0].delta == -0.10
