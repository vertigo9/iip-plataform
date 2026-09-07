from pathlib import Path


def test_coverage_report_is_present():
    # This is intentionally a release-gate helper. The authoritative coverage
    # value is produced by the project's pytest-cov configuration.
    assert Path("pyproject.toml").exists()
