from iip.sources import AssetRef, DocumentProvider


class ExampleProvider(DocumentProvider):
    provider_name = "example"

    def supports(self, asset: AssetRef) -> bool:
        return asset.ticker == "TEST11"

    def discover(self, asset: AssetRef, years: range):
        return []


def test_document_provider_contract():
    provider = ExampleProvider()

    asset = AssetRef(
        ticker="TEST11",
        asset_class="FII",
        asset_subtype="Tijolo",
    )

    assert provider.provider_name == "example"
    assert provider.supports(asset) is True
    assert provider.discover(asset, range(2024, 2026)) == []
