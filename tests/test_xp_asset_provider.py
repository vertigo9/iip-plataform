from __future__ import annotations

import pytest

from iip.sources.registry import AssetRef, SourceRef
from iip.sources.xp_asset import DocumentTarget, XPAssetProvider

XPML11_URL = "https://www.xpasset.com.br/fundos/xp-malls/"


def make_asset(*, ticker="XPML11", manager="XP Asset", sources=()):
    return AssetRef(
        ticker=ticker,
        asset_class="FII",
        asset_subtype="Tijolo",
        segment="Shopping",
        manager=manager,
        sources=sources,
    )


def xp_source(*, url=XPML11_URL, role="institutional_primary", priority=1, active=True):
    return SourceRef(
        provider="xp_asset",
        role=role,
        priority=priority,
        url=url,
        active=active,
    )


def test_discover_returns_document_targets_for_requested_years():
    result = XPAssetProvider().discover(
        make_asset(sources=(xp_source(),)), range(2024, 2027)
    )
    assert result == (
        DocumentTarget("XPML11", "xp_asset", "institutional_primary", XPML11_URL, 2024),
        DocumentTarget("XPML11", "xp_asset", "institutional_primary", XPML11_URL, 2025),
        DocumentTarget("XPML11", "xp_asset", "institutional_primary", XPML11_URL, 2026),
    )


def test_discover_preserves_canonical_institutional_url():
    result = XPAssetProvider().discover(
        make_asset(sources=(xp_source(),)), range(2026, 2027)
    )
    assert result[0].url == XPML11_URL


def test_discover_orders_multiple_sources_by_priority():
    secondary = xp_source(
        url="https://www.xpasset.com.br/fundos/xp-malls/documentos/",
        role="regulatory",
        priority=2,
    )
    primary = xp_source(priority=1)
    result = XPAssetProvider().discover(
        make_asset(sources=(secondary, primary)), range(2026, 2027)
    )
    assert [item.role for item in result] == ["institutional_primary", "regulatory"]


def test_discover_ignores_inactive_sources():
    inactive = xp_source(active=False)
    active = xp_source(priority=2)
    result = XPAssetProvider().discover(
        make_asset(sources=(inactive, active)), range(2026, 2027)
    )
    assert len(result) == 1
    assert result[0].url == XPML11_URL


def test_discover_does_not_use_unrelated_provider_sources():
    other = SourceRef(
        provider="patria",
        role="institutional_primary",
        priority=1,
        url="https://example.com/patria",
        active=True,
    )
    result = XPAssetProvider().discover(
        make_asset(sources=(xp_source(), other)), range(2026, 2027)
    )
    assert len(result) == 1
    assert result[0].provider == "xp_asset"


def test_discover_without_years_keeps_source_target():
    result = XPAssetProvider().discover(
        make_asset(sources=(xp_source(),)), range(2026, 2026)
    )
    assert result == (
        DocumentTarget("XPML11", "xp_asset", "institutional_primary", XPML11_URL, None),
    )


def test_discover_rejects_unsupported_asset():
    with pytest.raises(ValueError, match="not supported"):
        XPAssetProvider().discover(
            make_asset(manager="Pátria", sources=()), range(2026, 2027)
        )


def test_discover_rejects_non_range_years():
    with pytest.raises(TypeError, match="years must be a range"):
        XPAssetProvider().discover(make_asset(sources=(xp_source(),)), [2026])


def test_discover_requires_active_institutional_source():
    with pytest.raises(ValueError, match="no active XP Asset institutional source"):
        XPAssetProvider().discover(
            make_asset(manager=None, sources=(xp_source(active=False),)),
            range(2026, 2027),
        )


def test_discover_uses_manager_classification_with_canonical_source():
    result = XPAssetProvider().discover(
        make_asset(manager="XP Asset", sources=(xp_source(),)),
        range(2026, 2027),
    )
    assert result[0].ticker == "XPML11"
    assert result[0].year == 2026


def test_document_target_is_immutable():
    target = DocumentTarget(
        "XPML11", "xp_asset", "institutional_primary", XPML11_URL, 2026
    )
    with pytest.raises(AttributeError):
        target.year = 2025  # type: ignore[misc]


def test_discovery_is_offline_and_deterministic():
    provider = XPAssetProvider()
    asset = make_asset(sources=(xp_source(),))
    assert provider.discover(asset, range(2024, 2027)) == provider.discover(
        asset, range(2024, 2027)
    )
