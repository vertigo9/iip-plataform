from iip.sources import AssetRef, DocumentProvider
from iip.sources.provider_registry import ProviderRegistry


class PatriaProvider(DocumentProvider):
    provider_name = "patria"

    def supports(self, asset: AssetRef) -> bool:
        return asset.ticker == "HGRU11"

    def discover(self, asset: AssetRef, years: range):
        return []


class XPAssetProvider(DocumentProvider):
    provider_name = "xp_asset"

    def supports(self, asset: AssetRef) -> bool:
        return asset.ticker == "XPML11"

    def discover(self, asset: AssetRef, years: range):
        return []


def test_register_and_get_provider():
    registry = ProviderRegistry()
    provider = XPAssetProvider()

    registry.register(provider)

    assert registry.get("xp_asset") is provider
    assert registry.get("XP_ASSET") is provider


def test_resolve_provider_for_asset():
    registry = ProviderRegistry()

    patria = PatriaProvider()
    xp_asset = XPAssetProvider()

    registry.register(patria)
    registry.register(xp_asset)

    hgru11 = AssetRef(
        ticker="HGRU11",
        asset_class="FII",
        asset_subtype="Tijolo",
    )

    xpml11 = AssetRef(
        ticker="XPML11",
        asset_class="FII",
        asset_subtype="Tijolo",
        segment="Shopping",
    )

    assert registry.resolve(hgru11) is patria
    assert registry.resolve(xpml11) is xp_asset


def test_resolve_returns_none_when_no_provider_supports_asset():
    registry = ProviderRegistry()
    registry.register(XPAssetProvider())

    asset = AssetRef(
        ticker="BTLG11",
        asset_class="FII",
        asset_subtype="Tijolo",
    )

    assert registry.resolve(asset) is None


def test_duplicate_provider_is_rejected():
    registry = ProviderRegistry()

    registry.register(XPAssetProvider())

    try:
        registry.register(XPAssetProvider())
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("Expected duplicate provider registration to fail")
