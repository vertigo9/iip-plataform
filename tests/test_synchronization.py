"""Tests for IIP Synchronization Engine."""

from iip.synchronization import SynchronizationEngine


def test_full_sync_check():
    from iip.config import get_settings

    settings = get_settings()
    ok, issues = SynchronizationEngine.full_sync_check(settings)
    assert isinstance(ok, bool)
    assert isinstance(issues, list)


def test_report_empty():
    report = SynchronizationEngine.report([])
    assert "No synchronization issues" in report


def test_report_with_issues():
    from iip.synchronization import SyncIssue

    issues = [SyncIssue(severity="INFO", component="test", message="Test issue")]
    report = SynchronizationEngine.report(issues)
    assert "INFO" in report
    assert "test" in report
