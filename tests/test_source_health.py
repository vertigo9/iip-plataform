from datetime import UTC, datetime

import pytest

from iip.sources.health import SourceHealth


def test_source_health_defaults() -> None:
    health = SourceHealth(provider="XP_ASSET")

    assert health.provider == "xp_asset"
    assert health.enabled is True
    assert health.available is False
    assert health.last_success is None
    assert health.last_failure is None
    assert health.error_count == 0


def test_provider_name_is_normalized() -> None:
    assert SourceHealth(provider="XP_ASSET").provider == "xp_asset"
    assert SourceHealth(provider="Xp_Asset").provider == "xp_asset"
    assert SourceHealth(provider=" xp_asset ").provider == "xp_asset"


def test_enabled_and_available_are_independent() -> None:
    health = SourceHealth(
        provider="xp_asset",
        enabled=True,
        available=False,
    )

    assert health.enabled is True
    assert health.available is False


def test_health_accepts_success_and_failure_timestamps() -> None:
    success = datetime(2026, 8, 28, 17, 0, tzinfo=UTC)
    failure = datetime(2026, 8, 28, 16, 0, tzinfo=UTC)

    health = SourceHealth(
        provider="xp_asset",
        last_success=success,
        last_failure=failure,
    )

    assert health.last_success == success
    assert health.last_failure == failure


def test_error_count_defaults_to_zero() -> None:
    health = SourceHealth(provider="xp_asset")

    assert health.error_count == 0


def test_negative_error_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="error_count must not be negative"):
        SourceHealth(
            provider="xp_asset",
            error_count=-1,
        )


def test_empty_provider_is_rejected() -> None:
    with pytest.raises(ValueError, match="provider must not be empty"):
        SourceHealth(provider="   ")


def test_source_health_is_immutable() -> None:
    health = SourceHealth(provider="xp_asset")

    with pytest.raises(AttributeError):
        health.error_count = 1
