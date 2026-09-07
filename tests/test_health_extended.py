from iip.config import get_settings
from iip.health import (
    ReplicationStatusHealthCheck,
    SynchronizationHealthCheck,
    VersionCompatibilityHealthCheck,
)
from iip.synchronization import SynchronizationEngine, SyncIssue


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


def test_synchronization_health_ignores_info_issues(monkeypatch):
    """INFO diagnostics must not be reported as synchronization problems."""
    settings = get_settings()
    info_issues = [
        SyncIssue(
            severity="INFO",
            component="version",
            message="Using pre-release version: 0.1.0-alpha",
        ),
        SyncIssue(
            severity="INFO",
            component="contracts",
            message="Contract integrity checks configured",
        ),
    ]

    monkeypatch.setattr(
        SynchronizationEngine,
        "full_sync_check",
        classmethod(lambda cls, settings=None: (True, info_issues)),
    )

    result = SynchronizationHealthCheck().check(settings)

    assert result.name == "synchronization"
    assert result.healthy is True
    assert result.message == "No synchronization issues detected"


def test_synchronization_health_reports_warning(monkeypatch):
    """WARNING diagnostics must still be reported as synchronization issues."""
    settings = get_settings()
    warning_issue = SyncIssue(
        severity="WARNING",
        component="module_registry",
        message="Module example is loaded but disabled",
    )

    monkeypatch.setattr(
        SynchronizationEngine,
        "full_sync_check",
        classmethod(lambda cls, settings=None: (True, [warning_issue])),
    )

    result = SynchronizationHealthCheck().check(settings)

    assert result.name == "synchronization"
    assert result.healthy is True
    assert result.message == "1 sync issues detected"


def test_synchronization_health_reports_error(monkeypatch):
    """ERROR diagnostics must make the synchronization health check unhealthy."""
    settings = get_settings()
    error_issue = SyncIssue(
        severity="ERROR",
        component="synchronization",
        message="Synchronization failed",
    )

    monkeypatch.setattr(
        SynchronizationEngine,
        "full_sync_check",
        classmethod(lambda cls, settings=None: (False, [error_issue])),
    )

    result = SynchronizationHealthCheck().check(settings)

    assert result.name == "synchronization"
    assert result.healthy is False
    assert result.message == "1 sync issues detected"
