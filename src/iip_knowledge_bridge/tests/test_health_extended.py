from iip.config import get_settings
from iip.health import (
    ReplicationStatusHealthCheck,
    SynchronizationHealthCheck,
    VersionCompatibilityHealthCheck,
)


def test_version_health_check():
    settings = get_settings()
    check = VersionCompatibilityHealthCheck()
    result = check.check(settings)
    assert result.name == "version_compatibility"
    assert result.healthy is True


def test_replication_health_check():
    settings = get_settings()
    check = ReplicationStatusHealthCheck()
    result = check.check(settings)
    assert result.name == "replication"
    assert result.healthy is True


def test_synchronization_health_check():
    settings = get_settings()
    check = SynchronizationHealthCheck()
    result = check.check(settings)
    assert result.name == "synchronization"
    assert isinstance(result.healthy, bool)
