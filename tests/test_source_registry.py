from iip.sources import AssetRef, SourceRef, SourceRegistry


def test_register_xpml11():
    registry = SourceRegistry()

    registry.register(
        AssetRef(
            ticker="xpml11",
            asset_class="FII",
            asset_subtype="Tijolo",
            segment="Shopping",
            manager="XP Asset",
            sources=(
                SourceRef(
                    provider="xp_asset",
                    role="institutional_primary",
                    priority=3,
                    url="https://www.xpasset.com.br/fundos/xp-malls/",
                ),
                SourceRef(
                    provider="fnet_cvm",
                    role="regulatory",
                    priority=1,
                    url="https://fnet.bmfbovespa.com.br/",
                ),
                SourceRef(
                    provider="b3",
                    role="market_validation",
                    priority=4,
                    url="https://www.b3.com.br/",
                ),
            ),
        )
    )

    asset = registry.get("XPML11")

    assert asset is not None
    assert asset.ticker == "XPML11"
    assert asset.asset_class == "FII"
    assert asset.asset_subtype == "Tijolo"
    assert asset.segment == "Shopping"
    assert asset.manager == "XP Asset"

    sources = registry.sources_for("xpml11")

    assert [source.provider for source in sources] == [
        "fnet_cvm",
        "xp_asset",
        "b3",
    ]


def test_registry_normalizes_ticker():
    registry = SourceRegistry()

    registry.register(
        AssetRef(
            ticker=" hgru11 ",
            asset_class="FII",
            asset_subtype="Tijolo",
            sources=(
                SourceRef(
                    provider="patria",
                    role="institutional_primary",
                    priority=3,
                    url="https://realestate.patria.com/tijolo/hgru",
                ),
            ),
        )
    )

    assert registry.get("HGRU11") is not None


def test_missing_ticker_returns_none():
    registry = SourceRegistry()

    assert registry.get("XPML11") is None
    assert registry.sources_for("XPML11") == ()


from iip.sources.catalog import default_assets


def test_register_many_loads_catalog():
    registry = SourceRegistry()

    registry.register_many(default_assets())

    assert registry.get("HGRU11") is not None
    assert registry.get("XPML11") is not None
    assert registry.get("CDII11") is not None
    assert registry.get("CRAA11") is not None


def test_from_assets_builds_registry_from_catalog():
    registry = SourceRegistry.from_assets(default_assets())

    xpml11 = registry.get("XPML11")

    assert xpml11 is not None
    assert xpml11.asset_subtype == "Tijolo"
    assert xpml11.segment == "Shopping"

    primary = next(
        source
        for source in registry.sources_for("XPML11")
        if source.role == "institutional_primary"
    )

    assert primary.provider == "xp_asset"
