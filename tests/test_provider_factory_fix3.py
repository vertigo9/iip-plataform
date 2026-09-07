from iip.providers import ProviderFactory, ProviderStatus
from iip.providers.integration import OperationalProviderPlanner


def test_patria_legacy_module_is_supported_as_implementation():
    handle = ProviderFactory().create("patria")
    assert handle is not None
    assert handle.manifest.status == ProviderStatus.READY
    assert handle.provider is not None


def test_planner_marks_patria_ready_without_calling_module_as_class():
    plan = OperationalProviderPlanner().plan_from_routes(
        "XPML11", ("xp_asset", "b3", "patria")
    )
    assert plan.primary is not None
    assert plan.primary.provider.name == "xp_asset"


def test_implementation_gap_contains_exactly_unimplemented_managers():
    gap = OperationalProviderPlanner().implementation_gap()
    assert len(gap) == 10
    assert "sparta" in gap
    assert "kinea" in gap
    assert "xp_asset" not in gap
    assert "patria" not in gap
