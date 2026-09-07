from types import SimpleNamespace

from iip.config import Environment, IIPSettings
from iip.health import (
    ConfigurationHealthCheck,
    FileSystemHealthCheck,
    HealthEngine,
    HealthResult,
    ModuleCountHealthCheck,
    PythonVersionHealthCheck,
    ReplicationStatusHealthCheck,
    SynchronizationHealthCheck,
    SystemHealth,
    VersionCompatibilityHealthCheck,
)
from iip.portfolio.validation import ProviderValidator


def test_health_result_and_system_health_paths():
    healthy = HealthResult("a", True, "ok")
    unhealthy = HealthResult("b", False, "bad")
    system = SystemHealth([healthy, unhealthy])

    assert system.healthy is False
    payload = system.to_dict()
    assert payload["status"] == "unhealthy"
    assert len(payload["checks"]) == 2

    empty = SystemHealth([])
    assert empty.healthy is True


def test_health_configuration_filesystem_and_python(monkeypatch, tmp_path):
    settings = IIPSettings(
        environment=Environment.TESTING,
        app_name="IIP Platform",
        base_dir=tmp_path,
    )

    configuration = ConfigurationHealthCheck()
    assert configuration.name == "configuration"
    assert configuration.check(settings).healthy is True

    filesystem = FileSystemHealthCheck()
    assert filesystem.name == "filesystem"
    assert filesystem.check(settings).healthy is True

    missing = IIPSettings(
        environment=Environment.TESTING,
        app_name="",
        base_dir=tmp_path / "missing",
    )
    assert configuration.check(missing).healthy is False
    assert filesystem.check(missing).healthy is False

    python_check = PythonVersionHealthCheck()
    assert python_check.name == "python_version"
    assert python_check.check(settings).healthy is True

    class Broken:
        @property
        def app_name(self):
            raise RuntimeError("broken")

        @property
        def environment(self):
            raise RuntimeError("broken")

    class BrokenPath:
        @property
        def base_dir(self):
            raise RuntimeError("broken")

    assert configuration.check(Broken()).healthy is False
    assert filesystem.check(BrokenPath()).healthy is False


def test_health_module_version_replication_and_sync(monkeypatch):
    settings = IIPSettings(environment=Environment.TESTING)

    class Registry:
        @staticmethod
        def status():
            return {"total": 4, "loaded": 3}

    monkeypatch.setattr("iip.registry.ModuleRegistry", Registry, raising=False)
    module_check = ModuleCountHealthCheck()
    assert module_check.name == "module_registry"
    assert module_check.check(settings).message == "4 registered, 3 loaded"

    class VersionManager:
        @staticmethod
        def current():
            return "1.2.3"

    monkeypatch.setattr("iip.versioning.VersionManager", VersionManager, raising=False)
    version_check = VersionCompatibilityHealthCheck()
    assert version_check.name == "version_compatibility"
    assert version_check.check(settings).healthy is True

    class Replication:
        @staticmethod
        def status():
            return {"replications_total": 5, "replications_certified": 4}

    monkeypatch.setattr("iip.replication.ReplicationEngine", Replication, raising=False)
    replication_check = ReplicationStatusHealthCheck()
    assert replication_check.name == "replication"
    assert "5 replications" in replication_check.check(settings).message


def test_health_sync_info_and_warning_paths(monkeypatch):
    settings = IIPSettings(environment=Environment.TESTING)

    class Issue:
        def __init__(self, severity):
            self.severity = severity

    class SyncEngine:
        @staticmethod
        def full_sync_check(_settings):
            return True, [Issue("INFO"), Issue("INFORMATIONAL")]

    monkeypatch.setattr(
        "iip.synchronization.SynchronizationEngine",
        SyncEngine,
        raising=False,
    )

    check = SynchronizationHealthCheck()
    result = check.check(settings)
    assert result.healthy is True
    assert result.message == "No synchronization issues detected"

    class SyncEngineWarn:
        @staticmethod
        def full_sync_check(_settings):
            return False, [Issue("WARNING"), Issue("ERROR"), Issue("INFO")]

    monkeypatch.setattr(
        "iip.synchronization.SynchronizationEngine",
        SyncEngineWarn,
        raising=False,
    )
    result = check.check(settings)
    assert result.healthy is False
    assert result.message == "2 sync issues detected"


def test_health_engine_register_and_exception_path():
    settings = IIPSettings(environment=Environment.TESTING)
    engine = HealthEngine(settings)

    class Good:
        @property
        def name(self):
            return "good"

        def check(self, _settings):
            return HealthResult("good", True)

    class Bad:
        @property
        def name(self):
            return "bad"

        def check(self, _settings):
            raise RuntimeError("boom")

    engine.register(Good())
    engine.register(Bad())

    result = engine.run_all()
    assert len(result.checks) == 2
    assert result.checks[0].healthy is True
    assert result.checks[1].healthy is False
    assert "Check failed: boom" in result.checks[1].message


class DiagnosticOps:
    def __init__(self, mapping):
        self.mapping = mapping
        self.factory = SimpleNamespace(manifests={name: object() for name in mapping})

    def diagnostic(self, name):
        return self.mapping.get(name)


def test_provider_validator_all_paths():
    missing = DiagnosticOps(
        {
            "unknown": None,
            "pending": SimpleNamespace(
                implemented=False,
                usable_for_production=False,
            ),
            "validated": SimpleNamespace(
                implemented=True,
                usable_for_production=False,
            ),
            "ready": SimpleNamespace(
                implemented=True,
                usable_for_production=True,
            ),
        }
    )
    validator = ProviderValidator(missing)

    assert validator.validate("unknown").action == "register_provider"
    assert validator.validate("pending").action == "implement_provider"
    assert validator.validate("validated").action == "promote_after_validation"
    assert validator.validate("ready").action == "ready"

    names = [item.name for item in validator.validate_all()]
    assert names == ["pending", "ready", "unknown", "validated"]


def test_provider_validator_custom_diagnostic_values():
    validator = ProviderValidator(
        DiagnosticOps(
            {
                "X": SimpleNamespace(implemented=True, usable_for_production=True),
            }
        )
    )
    result = validator.validate("X")
    assert result.registered
    assert result.implemented
    assert result.ready
    assert result.action == "ready"
