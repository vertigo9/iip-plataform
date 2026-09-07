from __future__ import annotations

from iip.sources.health import SourceHealth
from iip.sources.health_registry import SourceHealthRegistry
from iip.sources.provider import DocumentProvider
from iip.sources.provider_registry import ProviderRegistry
from iip.sources.registry import AssetRef, SourceRef


class StubProvider(DocumentProvider):
    def __init__(self, name: str, supported: bool = True) -> None:
        self.provider_name = name
        self._supported = supported

    def supports(self, asset: AssetRef) -> bool:
        return self._supported

    def discover(self, asset: AssetRef, years: range):
        return ()


def make_asset() -> AssetRef:
    return AssetRef(
        ticker="XP_ASSET",
        asset_class="FII",
        asset_subtype="PAPEL",
        sources=(
            SourceRef(
                provider="xp_asset",
                role="primary",
                priority=1,
                url="https://example.test/xp_asset",
            ),
        ),
    )


def test_resolve_healthy_selects_healthy_provider() -> None:
    providers = ProviderRegistry()
    health = SourceHealthRegistry()

    provider = StubProvider("XP_ASSET")
    providers.register(provider)
    health.register(
        SourceHealth(
            provider="xp_asset",
            enabled=True,
            available=True,
        )
    )

    assert providers.resolve_healthy(make_asset(), health) is provider


def test_resolve_healthy_ignores_disabled_provider() -> None:
    providers = ProviderRegistry()
    health = SourceHealthRegistry()

    provider = StubProvider("XP_ASSET")
    providers.register(provider)
    health.register(
        SourceHealth(
            provider="xp_asset",
            enabled=False,
            available=True,
        )
    )

    assert providers.resolve_healthy(make_asset(), health) is None


def test_resolve_healthy_ignores_unavailable_provider() -> None:
    providers = ProviderRegistry()
    health = SourceHealthRegistry()

    provider = StubProvider("XP_ASSET")
    providers.register(provider)
    health.register(
        SourceHealth(
            provider="xp_asset",
            enabled=True,
            available=False,
        )
    )

    assert providers.resolve_healthy(make_asset(), health) is None


def test_resolve_healthy_does_not_treat_unknown_health_as_healthy() -> None:
    providers = ProviderRegistry()
    health = SourceHealthRegistry()

    provider = StubProvider("XP_ASSET")
    providers.register(provider)

    assert providers.resolve_healthy(make_asset(), health) is None


def test_resolve_healthy_falls_back_to_next_healthy_provider() -> None:
    providers = ProviderRegistry()
    health = SourceHealthRegistry()

    first = StubProvider("XP_ASSET")
    second = StubProvider("SECONDARY")

    providers.register(first)
    providers.register(second)

    health.register(
        SourceHealth(
            provider="xp_asset",
            enabled=True,
            available=False,
        )
    )
    health.register(
        SourceHealth(
            provider="secondary",
            enabled=True,
            available=True,
        )
    )

    assert providers.resolve_healthy(make_asset(), health) is second


def test_resolve_healthy_returns_none_when_no_healthy_provider_exists() -> None:
    providers = ProviderRegistry()
    health = SourceHealthRegistry()

    providers.register(StubProvider("XP_ASSET"))
    providers.register(StubProvider("SECONDARY"))

    health.register(SourceHealth(provider="xp_asset", available=False))
    health.register(SourceHealth(provider="secondary", enabled=False, available=True))

    assert providers.resolve_healthy(make_asset(), health) is None


def test_legacy_resolve_remains_unchanged() -> None:
    providers = ProviderRegistry()
    health = SourceHealthRegistry()

    provider = StubProvider("XP_ASSET")
    providers.register(provider)

    # No health record exists, but the legacy resolver still resolves.
    assert providers.resolve(make_asset()) is provider
    assert providers.resolve_healthy(make_asset(), health) is None


def test_health_provider_lookup_is_normalized() -> None:
    providers = ProviderRegistry()
    health = SourceHealthRegistry()

    provider = StubProvider("Xp_Asset")
    providers.register(provider)
    health.register(SourceHealth(provider="XP_ASSET", available=True))

    assert providers.resolve_healthy(make_asset(), health) is provider
