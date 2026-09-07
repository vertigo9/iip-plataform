from pathlib import Path

path = Path("tests/test_final95_behavior_460001_500000.py")
if not path.exists():
    raise SystemExit(f"Arquivo não encontrado: {path}")

text = path.read_text(encoding="utf-8")

old_universal = """def test_universal_branch_edges():
    from iip.universal.concentration import (
        concentration,
        concentration_alerts,
        all_concentrations,
    )
    from iip.universal.portfolio_state import PositionState

    positions = (
        PositionState("A", 0.60, manager="M1", segment="S1", asset_class="EQUITY"),
        PositionState("B", 0.25, manager="M1", segment="S2", asset_class="EQUITY"),
        PositionState("C", 0.15, manager="M2", segment="S1", asset_class="FII"),
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
"""

new_universal = """def test_universal_branch_edges():
    from iip.universal.concentration import (
        concentration,
        concentration_alerts,
        all_concentrations,
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
"""

old_source = """def test_source_registry_and_router_edges():
    from iip.sources.registry import SourceRegistry, SourceRef
    from iip.sources.router import SourceRouter

    registry = SourceRegistry()
    ref = SourceRef("fnet", "regulatory", 1, "https://example.invalid")
    registry.register(ref)

    assert registry.get("fnet") == ref
    router = SourceRouter(registry)
    assert router.registry is registry
"""

new_source = """def test_source_registry_and_router_edges():
    from iip.sources.registry import AssetRef, SourceRef, SourceRegistry
    from iip.sources.provider_registry import ProviderRegistry
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
"""

if old_universal not in text:
    raise SystemExit("Bloco universal esperado não encontrado.")
if old_source not in text:
    raise SystemExit("Bloco source esperado não encontrado.")

text = text.replace(old_universal, new_universal)
text = text.replace(old_source, new_source)

path.write_text(text, encoding="utf-8")
print("FIX2 aplicado: contratos de PositionState e SourceRegistry/Router ajustados.")
