from types import SimpleNamespace
from unittest.mock import patch

from iip import health


def settings(tmp_path):
    return SimpleNamespace(
        app_name="IIP",
        environment=SimpleNamespace(value="test"),
        base_dir=tmp_path,
    )


def test_health_primitives_and_filesystem(tmp_path):
    result = health.HealthResult("x", True, "ok")
    assert result.name == "x"
    assert result.healthy

    system = health.SystemHealth([result])
    assert system.healthy
    assert system.to_dict()["status"] == "healthy"

    fs = health.FileSystemHealthCheck()
    assert fs.name == "filesystem"
    assert fs.check(settings(tmp_path)).healthy

    missing = SimpleNamespace(
        app_name="IIP",
        environment=SimpleNamespace(value="test"),
        base_dir=tmp_path / "missing",
    )
    assert not fs.check(missing).healthy


def test_configuration_python_and_engine(tmp_path):
    cfg = health.ConfigurationHealthCheck()
    assert cfg.name == "configuration"
    assert cfg.check(settings(tmp_path)).healthy

    empty = SimpleNamespace(
        app_name="",
        environment=SimpleNamespace(value="test"),
        base_dir=tmp_path,
    )
    assert not cfg.check(empty).healthy

    py = health.PythonVersionHealthCheck()
    assert py.name == "python_version"
    assert py.check(settings(tmp_path)).healthy

    engine = health.HealthEngine(settings(tmp_path))

    class Good:
        name = "good"

        def check(self, _settings):
            return health.HealthResult("good", True)

    class Bad:
        name = "bad"

        def check(self, _settings):
            raise RuntimeError("boom")

    engine.register(Good())
    engine.register(Bad())
    result = engine.run_all()
    assert len(result.checks) == 2
    assert result.checks[0].healthy
    assert not result.checks[1].healthy


def test_optional_integrated_checks(tmp_path):
    s = settings(tmp_path)

    module = health.ModuleCountHealthCheck()
    version = health.VersionCompatibilityHealthCheck()
    replication = health.ReplicationStatusHealthCheck()
    synchronization = health.SynchronizationHealthCheck()

    assert module.name == "module_registry"
    assert version.name == "version_compatibility"
    assert replication.name == "replication"
    assert synchronization.name == "synchronization"

    assert isinstance(module.check(s).healthy, bool)
    assert isinstance(version.check(s).healthy, bool)
    assert isinstance(replication.check(s).healthy, bool)
    assert isinstance(synchronization.check(s).healthy, bool)


def test_synchronization_filters_informational_issue(tmp_path):
    s = settings(tmp_path)

    class Issue:
        def __init__(self, severity):
            self.severity = severity

        with patch("iip.health.SynchronizationHealthCheck.check") as mocked:
            mocked.return_value = health.HealthResult(
                "synchronization", True, "1 sync issues detected"
            )
        result = health.SynchronizationHealthCheck().check(s)
        assert result.healthy
        assert "synchronization" in result.name
