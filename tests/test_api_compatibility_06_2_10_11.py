def test_registry_legacy_api_is_restored():
    from iip.registry import ModuleManifest, ModuleRegistry, RegisteredModule

    assert ModuleRegistry is not None
    assert ModuleManifest is not None
    assert RegisteredModule is not None


def test_sources_legacy_and_new_apis_coexist():
    from iip.sources import (
        AssetRef,
        DocumentProvider,
        MultiProviderDiscovery,
        ProviderRegistry,
        SourceHealth,
        SourceHealthRegistry,
        SourceRef,
        SourceRegistry,
        SourceRouter,
    )

    assert all(
        [
            AssetRef,
            SourceRef,
            SourceRegistry,
            DocumentProvider,
            ProviderRegistry,
            SourceHealth,
            SourceHealthRegistry,
            SourceRouter,
            MultiProviderDiscovery,
        ]
    )
