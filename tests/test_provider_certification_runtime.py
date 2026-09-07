from iip.providers import (
    SOURCE_STATUS,
    CertificationStatus,
    ProviderCertifier,
    ProviderRuntime,
    RuntimeHealthService,
    build_source_records,
)


class FakeProvider:
    def discover(self, *args, **kwargs):
        return ("document",)


def test_source_status_keeps_12_managers_visible():
    assert len(SOURCE_STATUS) == 12
    assert SOURCE_STATUS["xp_asset"] == "validated"
    assert SOURCE_STATUS["patria"] == "validated"
    assert SOURCE_STATUS["sparta"] == "mapped"


def test_source_records_distinguish_validated_and_mapped():
    records = {item.provider: item for item in build_source_records()}
    assert records["xp_asset"].url_validated
    assert records["patria"].url_validated
    assert not records["sparta"].url_validated
    assert records["sparta"].requires_custom_adapter


def test_certifier_handles_unknown_provider():
    assert ProviderCertifier().certify("missing") is None


def test_certifier_does_not_certify_pending_provider():
    result = ProviderCertifier().certify("sparta")
    assert result is not None
    assert result.status == CertificationStatus.INCOMPLETE


def test_runtime_does_not_execute_pending_provider():
    result = ProviderRuntime().invoke("sparta", "discover", None, range(2026, 2027))
    assert result.success is False
    assert result.error == "incomplete"


def test_runtime_health_is_conservative_for_pending_provider():
    result = RuntimeHealthService().check("kinea")
    assert result.healthy is False
    assert result.status == CertificationStatus.INCOMPLETE
