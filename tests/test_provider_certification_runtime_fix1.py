def test_provider_package_public_api_is_complete():
    from iip.providers import (
        ProviderCertifier,
        ProviderFactory,
        ProviderRuntime,
        ProviderStatus,
        RuntimeHealthService,
    )

    assert all(
        (
            ProviderFactory,
            ProviderStatus,
            ProviderCertifier,
            ProviderRuntime,
            RuntimeHealthService,
        )
    )


def test_pending_provider_is_incomplete_not_blocked():
    from iip.providers import CertificationStatus, ProviderCertifier

    result = ProviderCertifier().certify("sparta")
    assert result is not None
    assert result.status == CertificationStatus.INCOMPLETE


def test_pending_runtime_returns_incomplete():
    from iip.providers import ProviderRuntime

    result = ProviderRuntime().invoke("sparta", "discover", None, range(2026, 2027))
    assert result.success is False
    assert result.error == "incomplete"


def test_pending_runtime_health_is_incomplete_and_unhealthy():
    from iip.providers import CertificationStatus, RuntimeHealthService

    result = RuntimeHealthService().check("kinea")
    assert result.healthy is False
    assert result.status == CertificationStatus.INCOMPLETE
