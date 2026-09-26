from pathlib import Path


def test_campaign_files_present():
    required = [
        Path("pyproject.toml"),
        Path("tests/test_coverage_core_export.py"),
        Path("tests/test_coverage_registry_events_versioning.py"),
        Path("tests/test_coverage_knowledge_health.py"),
    ]
    assert all(path.exists() for path in required)
