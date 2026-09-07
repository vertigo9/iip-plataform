import asyncio
from types import SimpleNamespace

from iip.events import Event, EventBus
from iip.registry import ModuleManifest, ModuleRegistry
from iip.versioning import CompatibilityMatrix, Version, VersionManager


def test_event_bus_sync_async_and_lifecycle():
    EventBus.clear()
    seen = []

    def sync_handler(event):
        seen.append(("sync", event.payload["x"]))

    async def async_handler(event):
        seen.append(("async", event.payload["x"]))

    EventBus.subscribe("asset", sync_handler)
    EventBus.subscribe("asset", async_handler)
    event = Event("asset", {"x": 7}, source="test")
    assert event.timestamp is not None
    assert EventBus.subscriber_count("asset") == 2

    asyncio.run(EventBus.publish(event))
    assert ("sync", 7) in seen
    assert ("async", 7) in seen

    EventBus.unsubscribe("asset", sync_handler)
    EventBus.unsubscribe("asset", sync_handler)
    assert EventBus.subscriber_count("asset") == 1
    EventBus.clear()
    assert EventBus.subscriber_count("asset") == 0


def test_registry_crud_status_and_filters():
    ModuleRegistry._modules = {}
    manifest_a = ModuleManifest("alpha", "1.0", "A", True)
    manifest_b = ModuleManifest("beta", "1.0", "B", False)

    ModuleRegistry.initialize(SimpleNamespace())
    ModuleRegistry.register("alpha", manifest_a)
    ModuleRegistry.register("beta", manifest_b)

    assert ModuleRegistry.get("alpha").manifest.description == "A"
    assert len(ModuleRegistry.list()) == 2
    assert [m.manifest.name for m in ModuleRegistry.list(True)] == ["alpha"]

    status = ModuleRegistry.status()
    assert status["total"] == 2
    assert status["enabled"] == 1
    assert status["loaded"] == 0
    assert status["modules"]["beta"]["enabled"] is False


def test_registry_load_failure_paths():
    ModuleRegistry._modules = {}
    ModuleRegistry.register(
        "disabled_mod", ModuleManifest("disabled_mod", "1", "d", False)
    )
    ModuleRegistry.register(
        "consumer", ModuleManifest("consumer", "1", "c", True, ["missing"])
    )
    assert asyncio.run(ModuleRegistry.load_module("unknown")) is False
    assert asyncio.run(ModuleRegistry.load_module("disabled_mod")) is False
    assert asyncio.run(ModuleRegistry.load_module("consumer")) is False


def test_registry_successful_load(monkeypatch):
    ModuleRegistry._modules = {}
    # Use a real module present in the IIP package. ModuleRegistry imports
    # iip.<name>, so a fictitious name would correctly exercise failure only.
    ModuleRegistry.register(
        "config",
        ModuleManifest("config", "1", "configuration", True),
    )

    async def publish(_event):
        return None

    monkeypatch.setattr(EventBus, "publish", publish)
    assert asyncio.run(ModuleRegistry.load_module("config")) is True
    assert ModuleRegistry.get("config").loaded_at


def test_version_parse_compare_and_prerelease():
    stable = Version.parse("1.2.3")
    alpha = Version.parse("1.2.3-alpha")
    newer = Version.parse("1.3.0")
    assert str(stable) == "1.2.3"
    assert str(alpha) == "1.2.3-alpha"
    assert alpha < stable
    assert stable < newer


def test_version_manager_state_machine():
    original = VersionManager._current_version
    original_matrix = VersionManager._matrix
    try:
        VersionManager._current_version = Version(1, 0, 0, "alpha")
        VersionManager._matrix = CompatibilityMatrix(1, 0, 2, 9)

        VersionManager.set_pre_release("beta")
        assert VersionManager.current().pre_release == "beta"

        VersionManager.bump_patch()
        assert VersionManager.current().patch == 1

        VersionManager.bump_minor()
        assert VersionManager.current().minor == 1
        assert VersionManager.current().patch == 0
        assert VersionManager.current().pre_release is None

        VersionManager.bump_major()
        assert VersionManager.current().major == 2
        assert VersionManager.current().minor == 0
        assert VersionManager.current().patch == 0

        assert VersionManager.is_compatible(Version(2, 5, 0))
        assert not VersionManager.is_compatible(Version(3, 0, 0))

        ok, errors = VersionManager.check_dependencies({"x": "2.1.0"})
        assert ok and errors == []

        ok, errors = VersionManager.check_dependencies({"x": "3.0.0"})
        assert not ok and errors
        status = VersionManager.status()
        assert status["major"] == 2
    finally:
        VersionManager._current_version = original
        VersionManager._matrix = original_matrix
