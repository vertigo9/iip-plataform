def test_portfolio_matrix_uses_operational_provider_registry():
    from iip.portfolio.matrix import build_provider_roadmap

    roadmap = build_provider_roadmap()

    assert roadmap
    names = {item.provider for item in roadmap}
    assert "xp_asset" in names
    assert "patria" in names
    assert all(item.has_source_mapping for item in roadmap)
