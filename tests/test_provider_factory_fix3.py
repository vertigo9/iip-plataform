from iip.providers import ProviderFactory, ProviderStatus
from iip.providers.integration import OperationalProviderPlanner


def test_patria_is_pending_after_legacy_harvester_retirement():
    # O raspador legado (iip.harvest.patria) foi aposentado; a coleta de
    # documentos da Pátria é feita pelo patria_mziq, que segue READY no
    # catálogo de adaptadores.
    handle = ProviderFactory().create("patria")
    assert handle is not None
    assert handle.manifest.status == ProviderStatus.PENDING
    assert handle.manifest.implementation is None
    assert handle.provider is None


def test_planner_marks_patria_ready_without_calling_module_as_class():
    plan = OperationalProviderPlanner().plan_from_routes(
        "XPML11", ("xp_asset", "b3", "patria")
    )
    assert plan.primary is not None
    assert plan.primary.provider.name == "xp_asset"


def test_implementation_gap_contains_exactly_unimplemented_managers():
    gap = OperationalProviderPlanner().implementation_gap()
    assert len(gap) == 11
    assert "sparta" in gap
    assert "kinea" in gap
    assert "xp_asset" not in gap
    assert "patria" in gap
