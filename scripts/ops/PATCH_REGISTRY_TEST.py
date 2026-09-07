from pathlib import Path

path = Path("tests/test_coverage_registry_events_versioning.py")
text = path.read_text(encoding="utf-8")

old = """def test_registry_successful_load(monkeypatch):
    ModuleRegistry._modules = {}
    ModuleRegistry.register("math", ModuleManifest("math", "1", "math", True))

    async def publish(_event):
        return None

    monkeypatch.setattr(EventBus, "publish", publish)
    assert asyncio.run(ModuleRegistry.load_module("math")) is True
    assert ModuleRegistry.get("math").loaded_at
"""

new = """def test_registry_successful_load(monkeypatch):
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
"""

if old not in text:
    raise SystemExit("Expected registry test block not found.")
path.write_text(text.replace(old, new), encoding="utf-8")
print("Patched registry success-path test.")
