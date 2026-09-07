from iip.registry import ModuleManifest, ModuleRegistry


def test_register_module():
    ModuleRegistry.initialize()
    manifest = ModuleManifest(name="test", version="1.0.0", description="Test module")
    ModuleRegistry.register("test_module", manifest)
    reg = ModuleRegistry.get("test_module")
    assert reg is not None
    assert reg.manifest.name == "test"
    assert reg.manifest.version == "1.0.0"


def test_list_modules():
    mods = ModuleRegistry.list(enabled_only=True)
    assert isinstance(mods, list)


def test_status():
    status = ModuleRegistry.status()
    assert "total" in status
    assert "enabled" in status
    assert "loaded" in status
