from iip.providers import ProviderFactory, ProviderStatus
from iip.providers.integration import OperationalProviderPlanner
from iip.providers.matrix import build_provider_roadmap
from iip.providers.validation import ProviderValidator


def test_ready_providers_have_real_implementations():
    factory = ProviderFactory()

    xp = factory.create("xp_asset")

    assert xp is not None and xp.provider is not None


def test_pending_providers_are_not_instantiated():
    factory = ProviderFactory()
    for name in (
        "sparta",
        "capitania",
        "valora",
        "btg",
        "manati",
        "trx",
        "araujo_fontes",
        "hedge",
        "rio_bravo",
        "kinea",
    ):
        handle = factory.create(name)
        assert handle is not None
        assert handle.provider is None
        assert handle.manifest.status == ProviderStatus.PENDING


def test_planner_marks_only_ready_providers_production_ready():
    planner = OperationalProviderPlanner()
    plan = planner.plan_from_routes(
        "XPML11",
        ("xp_asset", "b3", "patria"),
    )
    assert plan.ticker == "XPML11"
    assert plan.primary is not None
    assert plan.primary.provider.name == "xp_asset"


def test_planner_does_not_promote_pending_fallback():
    planner = OperationalProviderPlanner()
    plan = planner.plan_from_routes(
        "BTLG11",
        ("btg", "b3"),
    )
    assert plan.primary is None


def test_gap_lists_pending_institutional_managers():
    gap = OperationalProviderPlanner().implementation_gap()
    assert "sparta" in gap
    assert "kinea" in gap
    assert "patria" in gap
    assert len(gap) == 11


def test_validator_action_for_unknown_provider():
    result = ProviderValidator().validate("missing")
    assert result.action == "register_provider"


def test_validator_action_for_pending_provider():
    result = ProviderValidator().validate("sparta")
    assert result.registered
    assert not result.implemented
    assert result.action == "implement_provider"


def test_validator_action_for_ready_provider():
    result = ProviderValidator().validate("xp_asset")
    assert result.ready
    assert result.action == "ready"


def test_roadmap_has_all_twelve_fund_managers():
    roadmap = build_provider_roadmap()
    assert len(roadmap) == 12
    assert sum(item.status == ProviderStatus.READY for item in roadmap) == 1


def test_roadmap_requires_validation_before_implementation():
    pending = [
        item
        for item in build_provider_roadmap()
        if item.status == ProviderStatus.PENDING
    ]
    assert pending
    assert all(
        item.next_step == "validate_institutional_source_then_implement"
        for item in pending
    )
