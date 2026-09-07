import pytest


def test_universal_branch_edges():
    from iip.universal.concentration import (
        all_concentrations,
        concentration,
        concentration_alerts,
    )
    from iip.universal.portfolio_state import PositionState

    positions = (
        PositionState("A", 1, 600, 0.60, "EQUITY", segment="S1", manager="M1"),
        PositionState("B", 1, 250, 0.25, "EQUITY", segment="S2", manager="M1"),
        PositionState("C", 1, 150, 0.15, "FII", segment="S1", manager="M2"),
    )

    items = concentration(positions, "manager", 0.50)
    assert len(items) == 1
    assert items[0].value == "M1"
    assert items[0].breached is True

    alerts = concentration_alerts(
        positions, manager_limit=0.50, segment_limit=0.70, class_limit=0.70
    )
    assert alerts

    full = all_concentrations(
        positions, manager_limit=0.50, segment_limit=0.70, class_limit=0.70
    )
    assert full


def test_source_registry_and_router_edges():
    from iip.sources.provider_registry import ProviderRegistry
    from iip.sources.registry import AssetRef, SourceRef, SourceRegistry
    from iip.sources.router import SourceRouter

    source = SourceRef("fnet", "regulatory", 1, "https://example.invalid")
    asset = AssetRef(
        "CPFE3",
        "fund",
        "equity",
        sources=(source,),
    )

    registry = SourceRegistry()
    registry.register(asset)

    assert registry.get("cpfe3") == asset
    assert registry.sources_for("CPFE3") == (source,)
    assert registry.sources_for("UNKNOWN") == ()

    router = SourceRouter(
        source_registry=registry,
        provider_registry=ProviderRegistry(),
    )
    assert router.routes_for(asset) == ()
    assert router.primary_route(asset) is None
    assert router.fallback_routes(asset) == ()


def test_provider_health_and_validation_edges():
    from iip.providers.health import OperationalHealth, ProviderHealthService
    from iip.providers.validation import ProviderValidator

    class Operations:
        def diagnostic(self, provider):
            if provider == "unknown":
                return None
            return type(
                "Diagnostic",
                (),
                {
                    "usable_for_production": provider == "ready",
                    "implemented": provider == "partial",
                },
            )()

    service = ProviderHealthService(Operations())
    assert service.check("unknown") == OperationalHealth(
        "unknown", False, "unknown_provider"
    )
    assert service.check("ready").reason == "ready"
    assert service.check("partial").reason == "implementation_not_ready"
    assert service.check("other").reason == "provider_not_implemented"

    assert ProviderValidator


def test_validation_engine_returns_edges():
    from iip.validation_engine.returns import (
        ReturnPoint,
        cumulative_return,
        max_drawdown,
        simple_return,
    )

    points = (
        ReturnPoint("2026-01-01", 100),
        ReturnPoint("2026-02-01", 110),
        ReturnPoint("2026-03-01", 90),
    )
    assert simple_return(100, 110) == pytest.approx(0.10)
    assert cumulative_return(points) == pytest.approx(-0.10)
    assert cumulative_return((ReturnPoint("x", 100),)) == 0.0
    assert max_drawdown(points) == pytest.approx(0.181818181818)
    with pytest.raises(ValueError):
        simple_return(0, 1)


def test_hardening_determinism_and_scenario_helpers():
    from iip.hardening.determinism import equivalent, stable_results

    assert equivalent({"a": 1}, {"a": 1})
    assert not equivalent({"a": 1}, {"a": 2})
    assert stable_results((1, 1, 1))
    assert not stable_results(())
    assert not stable_results((1, 2))


def test_system_and_production_small_edges():
    from dataclasses import dataclass

    from iip.production.recovery import RetryPolicy, should_retry
    from iip.production.schedule import ScheduleSpec, validate_schedule
    from iip.system.export_adapter import SystemExportAdapter

    @dataclass
    class Payload:
        x: int

    adapter = SystemExportAdapter()
    assert adapter.export(Payload(7)) == {"x": 7}
    assert adapter.export({"x": 8}) == {"x": 8}
    with pytest.raises(TypeError):
        adapter.export(object())

    assert should_retry(0, RetryPolicy(2))
    assert not should_retry(2, RetryPolicy(2))
    assert not should_retry(0, RetryPolicy(0))

    good, errors = validate_schedule(ScheduleSpec("daily", "DAILY"))
    assert good and errors == ()
    bad, errors = validate_schedule(ScheduleSpec("", "", ""))
    assert not bad
    assert set(errors) == {"missing_name", "missing_cadence", "missing_timezone"}
