from iip.sources.catalog import default_assets


def test_default_catalog_contains_core_asset_types():
    assets = {asset.ticker: asset for asset in default_assets()}

    assert assets["HGRU11"].asset_class == "FII"
    assert assets["HGRU11"].asset_subtype == "Tijolo"

    assert assets["XPML11"].asset_class == "FII"
    assert assets["XPML11"].asset_subtype == "Tijolo"
    assert assets["XPML11"].segment == "Shopping"

    assert assets["CDII11"].asset_class == "FI-Infra"
    assert assets["CRAA11"].asset_class == "FI-Agro"


def test_xpml11_uses_xp_asset_as_institutional_source():
    assets = {asset.ticker: asset for asset in default_assets()}
    xpml11 = assets["XPML11"]

    primary = next(
        source for source in xpml11.sources if source.role == "institutional_primary"
    )

    assert primary.provider == "xp_asset"
    assert primary.url == "https://www.xpasset.com.br/fundos/xp-malls/"
