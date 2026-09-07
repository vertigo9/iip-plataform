from iip.sources import (
    AssetRef,
    DocumentProvider,
    ProviderRegistry,
    SourceRef,
    SourceRegistry,
    SourceRouter,
)


def test_legacy_source_exports_are_preserved():
    assert AssetRef is not None
    assert DocumentProvider is not None
    assert SourceRef is not None
    assert SourceRegistry is not None


def test_new_routing_exports_are_available():
    assert SourceRouter is not None
    assert ProviderRegistry is not None
