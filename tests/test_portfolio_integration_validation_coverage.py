"""
Testes de cobertura para iip.portfolio.integration e iip.portfolio.validation.

Estratégia: ambas as classes sob teste (OperationalProviderPlanner e
ProviderValidator) recebem sua dependência via injeção no __init__ e só
usam duck typing sobre ela (chamam .manifest(), .create(), .manifests,
.diagnostic()) — então testamos com fakes simples, sem precisar dos
internals reais de ProviderFactory/ProviderOperations/registry.

Ajuste os caminhos de import abaixo se os módulos não estiverem em
iip.portfolio.integration / iip.portfolio.validation no seu repositório.
"""

from __future__ import annotations

from types import SimpleNamespace

from iip.portfolio import integration as integration_module
from iip.portfolio.integration import (
    OperationalProviderPlanner,
    ProviderRoutingPlan,
)
from iip.portfolio.validation import ProviderValidation, ProviderValidator

# Usa o MESMO ProviderStatus que o código sob teste importou, garantindo
# que as comparações de igualdade (`manifest.status == ProviderStatus.READY`)
# funcionem independentemente da implementação real do enum.
ProviderStatus = integration_module.ProviderStatus


def _manifest(**kwargs) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def _kind(value: str) -> SimpleNamespace:
    return SimpleNamespace(value=value)


class _FakeFactory:
    """Dublê de ProviderFactory: só implementa manifest(), create(), manifests."""

    def __init__(self, manifests: dict, handles: dict | None = None):
        self.manifests = manifests
        self._handles = handles or {}

    def manifest(self, name):
        return self.manifests.get(name)

    def create(self, name):
        return self._handles.get(name)


# ---------------------------------------------------------------------------
# OperationalProviderPlanner.binding()
# ---------------------------------------------------------------------------


def test_binding_returns_none_when_manifest_missing():
    factory = _FakeFactory(manifests={}, handles={})
    planner = OperationalProviderPlanner(provider_factory=factory)

    assert planner.binding("ghost") is None


def test_binding_is_ready_when_implemented_and_status_ready():
    manifest = _manifest(
        implementation=True,
        status=ProviderStatus.READY,
        kind=_kind("institutional"),
    )
    handle = SimpleNamespace(provider=object())
    factory = _FakeFactory(manifests={"xp": manifest}, handles={"xp": handle})
    planner = OperationalProviderPlanner(provider_factory=factory)

    binding = planner.binding("xp")

    assert binding.provider is manifest
    assert binding.implementation_available is True
    assert binding.production_ready is True


def test_binding_not_ready_when_status_is_pending():
    manifest = _manifest(
        implementation=True,
        status=ProviderStatus.PENDING,
        kind=_kind("institutional"),
    )
    handle = SimpleNamespace(provider=object())
    factory = _FakeFactory(manifests={"btlg": manifest}, handles={"btlg": handle})
    planner = OperationalProviderPlanner(provider_factory=factory)

    binding = planner.binding("btlg")

    assert binding.implementation_available is True
    assert binding.production_ready is False


def test_binding_not_implemented_when_handle_has_no_provider():
    manifest = _manifest(
        implementation=True,
        status=ProviderStatus.READY,
        kind=_kind("institutional"),
    )
    handle = SimpleNamespace(provider=None)
    factory = _FakeFactory(manifests={"pcip": manifest}, handles={"pcip": handle})
    planner = OperationalProviderPlanner(provider_factory=factory)

    binding = planner.binding("pcip")

    assert binding.implementation_available is False
    assert binding.production_ready is False


def test_binding_not_implemented_when_manifest_lacks_implementation_flag():
    manifest = _manifest(
        implementation=False,
        status=ProviderStatus.READY,
        kind=_kind("institutional"),
    )
    handle = SimpleNamespace(provider=object())
    factory = _FakeFactory(manifests={"cvbi": manifest}, handles={"cvbi": handle})
    planner = OperationalProviderPlanner(provider_factory=factory)

    binding = planner.binding("cvbi")

    assert binding.implementation_available is False
    assert binding.production_ready is False


# ---------------------------------------------------------------------------
# OperationalProviderPlanner.plan_from_routes()
# ---------------------------------------------------------------------------


def test_plan_from_routes_picks_first_ready_as_primary_and_rest_as_fallback():
    manifest_a = _manifest(
        implementation=True, status=ProviderStatus.READY, kind=_kind("institutional")
    )
    manifest_b = _manifest(
        implementation=True, status=ProviderStatus.READY, kind=_kind("institutional")
    )
    manifest_c = _manifest(
        implementation=True, status=ProviderStatus.PENDING, kind=_kind("institutional")
    )
    handle = SimpleNamespace(provider=object())

    factory = _FakeFactory(
        manifests={"a": manifest_a, "b": manifest_b, "c": manifest_c},
        handles={"a": handle, "b": handle, "c": handle},
    )
    planner = OperationalProviderPlanner(provider_factory=factory)

    plan = planner.plan_from_routes("pcip11", ("a", "c", "b"))

    assert isinstance(plan, ProviderRoutingPlan)
    assert plan.ticker == "PCIP11"
    assert len(plan.bindings) == 3
    assert plan.primary.provider is manifest_a
    assert [b.provider for b in plan.fallbacks] == [manifest_b]


def test_plan_from_routes_primary_is_none_when_nothing_is_ready():
    manifest = _manifest(
        implementation=False, status=ProviderStatus.PENDING, kind=_kind("institutional")
    )
    factory = _FakeFactory(manifests={"x": manifest}, handles={"x": None})
    planner = OperationalProviderPlanner(provider_factory=factory)

    plan = planner.plan_from_routes("xpml11", ("x",))

    assert plan.primary is None
    assert plan.fallbacks == ()
    assert len(plan.bindings) == 1


def test_plan_from_routes_skips_unknown_provider_names():
    factory = _FakeFactory(manifests={}, handles={})
    planner = OperationalProviderPlanner(provider_factory=factory)

    plan = planner.plan_from_routes("xpml11", ("ghost1", "ghost2"))

    assert plan.bindings == ()
    assert plan.primary is None
    assert plan.fallbacks == ()


def test_plan_from_routes_uppercases_ticker():
    factory = _FakeFactory(manifests={}, handles={})
    planner = OperationalProviderPlanner(provider_factory=factory)

    plan = planner.plan_from_routes("cvbi11", ())

    assert plan.ticker == "CVBI11"


# ---------------------------------------------------------------------------
# OperationalProviderPlanner.implementation_gap()
# ---------------------------------------------------------------------------


def test_implementation_gap_lists_pending_institutional_providers_sorted():
    manifests = {
        "zeta": _manifest(kind=_kind("institutional"), status=ProviderStatus.PENDING),
        "alpha": _manifest(kind=_kind("institutional"), status=ProviderStatus.PENDING),
        "beta": _manifest(kind=_kind("retail"), status=ProviderStatus.PENDING),
        "gamma": _manifest(kind=_kind("institutional"), status=ProviderStatus.READY),
    }
    factory = _FakeFactory(manifests=manifests, handles={})
    planner = OperationalProviderPlanner(provider_factory=factory)

    gap = planner.implementation_gap()

    assert gap == ("alpha", "zeta")


def test_implementation_gap_is_empty_when_nothing_pending():
    manifests = {
        "a": _manifest(kind=_kind("institutional"), status=ProviderStatus.READY),
    }
    factory = _FakeFactory(manifests=manifests, handles={})
    planner = OperationalProviderPlanner(provider_factory=factory)

    assert planner.implementation_gap() == ()


# ---------------------------------------------------------------------------
# ProviderValidator.validate() / validate_all()
# ---------------------------------------------------------------------------


class _FakeOperations:
    """Dublê de ProviderOperations: só implementa .diagnostic() e .factory.manifests."""

    def __init__(self, diagnostics: dict, manifest_names):
        self._diagnostics = diagnostics
        self.factory = SimpleNamespace(
            manifests={name: None for name in manifest_names}
        )

    def diagnostic(self, name):
        return self._diagnostics.get(name)


def test_validate_registers_provider_when_diagnostic_missing():
    ops = _FakeOperations(diagnostics={}, manifest_names=[])
    validator = ProviderValidator(operations=ops)

    result = validator.validate("ghost")

    assert result == ProviderValidation(
        "ghost", False, False, False, "register_provider"
    )


def test_validate_asks_for_implementation_when_not_implemented():
    diagnostic = SimpleNamespace(implemented=False, usable_for_production=False)
    ops = _FakeOperations(diagnostics={"xp": diagnostic}, manifest_names=["xp"])
    validator = ProviderValidator(operations=ops)

    result = validator.validate("xp")

    assert result == ProviderValidation("xp", True, False, False, "implement_provider")


def test_validate_asks_for_promotion_when_not_yet_production_ready():
    diagnostic = SimpleNamespace(implemented=True, usable_for_production=False)
    ops = _FakeOperations(diagnostics={"btlg": diagnostic}, manifest_names=["btlg"])
    validator = ProviderValidator(operations=ops)

    result = validator.validate("btlg")

    assert result == ProviderValidation(
        "btlg", True, True, False, "promote_after_validation"
    )


def test_validate_returns_ready_when_fully_validated():
    diagnostic = SimpleNamespace(implemented=True, usable_for_production=True)
    ops = _FakeOperations(diagnostics={"pcip": diagnostic}, manifest_names=["pcip"])
    validator = ProviderValidator(operations=ops)

    result = validator.validate("pcip")

    assert result == ProviderValidation("pcip", True, True, True, "ready")


def test_validate_all_returns_tuple_sorted_by_name():
    diagnostics = {
        "zeta": SimpleNamespace(implemented=True, usable_for_production=True),
        "alpha": SimpleNamespace(implemented=False, usable_for_production=False),
    }
    ops = _FakeOperations(diagnostics=diagnostics, manifest_names=["zeta", "alpha"])
    validator = ProviderValidator(operations=ops)

    results = validator.validate_all()

    assert isinstance(results, tuple)
    assert [r.name for r in results] == ["alpha", "zeta"]
    assert results[0].action == "implement_provider"
    assert results[1].action == "ready"


def test_validate_all_is_empty_when_no_providers_registered():
    ops = _FakeOperations(diagnostics={}, manifest_names=[])
    validator = ProviderValidator(operations=ops)

    assert validator.validate_all() == ()
