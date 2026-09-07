from iip.sources.health import SourceHealth
from iip.sources.health_registry import SourceHealthRegistry


def test_register_and_get_health() -> None:
    registry = SourceHealthRegistry()
    health = SourceHealth(provider="XP_ASSET")

    registry.register(health)

    assert registry.get("xp_asset") == health


def test_provider_lookup_is_case_insensitive() -> None:
    registry = SourceHealthRegistry()
    health = SourceHealth(provider="xp_asset")

    registry.register(health)

    assert registry.get("XP_ASSET") == health
    assert registry.get("Xp_Asset") == health


def test_provider_lookup_ignores_surrounding_spaces() -> None:
    registry = SourceHealthRegistry()
    health = SourceHealth(provider="xp_asset")

    registry.register(health)

    assert registry.get("  XP_ASSET  ") == health


def test_unknown_provider_returns_none() -> None:
    registry = SourceHealthRegistry()

    assert registry.get("unknown") is None


def test_empty_provider_lookup_returns_none() -> None:
    registry = SourceHealthRegistry()

    assert registry.get("   ") is None


def test_register_replaces_existing_health_state() -> None:
    registry = SourceHealthRegistry()

    first = SourceHealth(
        provider="xp_asset",
        available=False,
    )
    second = SourceHealth(
        provider="XP_ASSET",
        available=True,
    )

    registry.register(first)
    registry.register(second)

    assert registry.get("xp_asset") == second
    assert registry.get("xp_asset").available is True


def test_clear_removes_all_health_states() -> None:
    registry = SourceHealthRegistry()
    registry.register(SourceHealth(provider="xp_asset"))

    registry.clear()

    assert registry.get("xp_asset") is None


def test_registry_stores_independent_provider_states() -> None:
    registry = SourceHealthRegistry()

    xp = SourceHealth(provider="xp_asset")
    another = SourceHealth(provider="another_provider")

    registry.register(xp)
    registry.register(another)

    assert registry.get("xp_asset") == xp
    assert registry.get("another_provider") == another
