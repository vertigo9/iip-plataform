from iip.providers.integration import OperationalProviderPlanner


def test_binding_uses_legacy_public_provider_field():
    binding = OperationalProviderPlanner().binding("xp_asset")
    assert binding is not None
    assert binding.provider.name == "xp_asset"
    assert binding.implementation_available is True
    assert binding.production_ready is True


def test_planner_returns_primary_without_keyword_constructor_error():
    plan = OperationalProviderPlanner().plan_from_routes(
        "XPML11", ("xp_asset", "b3", "patria")
    )
    assert plan.primary is not None
    assert plan.primary.provider.name == "xp_asset"


def test_pending_provider_is_not_promoted():
    plan = OperationalProviderPlanner().plan_from_routes("BTLG11", ("btg", "b3"))
    assert plan.primary is None


def test_implementation_gap_is_only_fund_managers():
    gap = OperationalProviderPlanner().implementation_gap()
    assert len(gap) == 11
    assert "sparta" in gap
    assert "kinea" in gap
    assert "xp_asset" not in gap
    assert "patria" in gap
    assert "ri_company" not in gap
