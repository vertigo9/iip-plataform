import sys
import types

import pytest

from iip.providers.registry import (
    ProviderKind,
    ProviderManifest,
    ProviderStatus,
    clear_runtime_manifests,
    default_provider_manifests,
    discover_plugins,
    manifest_map,
    register_manifest,
    unregister_manifest,
)


@pytest.fixture(autouse=True)
def _isolate_runtime_manifests():
    clear_runtime_manifests()
    yield
    clear_runtime_manifests()


def make_manifest(name="fake_provider", status=ProviderStatus.READY):
    return ProviderManifest(
        name=name,
        kind=ProviderKind.MACRO,
        status=status,
        asset_classes=("fund",),
        source_roles=("enrichment",),
    )


# --- built-in manifests for the four providers built this session ---


def test_bacen_ibge_receita_federal_are_ready_built_ins():
    names_and_status = {m.name: m.status for m in default_provider_manifests()}
    assert names_and_status["bacen"] == ProviderStatus.READY
    assert names_and_status["ibge"] == ProviderStatus.READY
    assert names_and_status["receita_federal"] == ProviderStatus.READY


def test_bacen_ibge_use_the_macro_kind():
    by_name = {m.name: m for m in default_provider_manifests()}
    assert by_name["bacen"].kind == ProviderKind.MACRO
    assert by_name["ibge"].kind == ProviderKind.MACRO


def test_b3_manifest_is_partial_not_ready_due_to_required_api_key():
    by_name = {m.name: m for m in default_provider_manifests()}
    assert by_name["b3"].status == ProviderStatus.PARTIAL
    assert by_name["b3"].implementation is not None
    assert "api_key" in by_name["b3"].notes


# --- runtime registration ---


def test_register_manifest_adds_new_entry():
    register_manifest(make_manifest())
    assert "fake_provider" in manifest_map()


def test_register_manifest_does_not_mutate_built_ins():
    before = len(default_provider_manifests())
    register_manifest(make_manifest())
    after = len(default_provider_manifests())
    assert before == after  # built-in list itself is untouched


def test_register_manifest_can_override_a_built_in_by_name():
    register_manifest(make_manifest(name="b3", status=ProviderStatus.READY))
    assert manifest_map()["b3"].status == ProviderStatus.READY
    # the built-in function itself remains PARTIAL — only the merged view changes
    by_name = {m.name: m for m in default_provider_manifests()}
    assert by_name["b3"].status == ProviderStatus.PARTIAL


def test_unregister_manifest_removes_runtime_entry():
    register_manifest(make_manifest())
    unregister_manifest("fake_provider")
    assert "fake_provider" not in manifest_map()


def test_unregister_manifest_cannot_remove_a_built_in():
    unregister_manifest("bacen")
    assert "bacen" in manifest_map()  # built-in survives


def test_clear_runtime_manifests_removes_everything_registered():
    register_manifest(make_manifest("a"))
    register_manifest(make_manifest("b"))
    clear_runtime_manifests()
    merged = manifest_map()
    assert "a" not in merged
    assert "b" not in merged


# --- plugin discovery via environment variable ---


def test_discover_plugins_returns_empty_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("IIP_PLUGINS", raising=False)
    assert discover_plugins() == ()


def test_discover_plugins_imports_module_and_registers_its_manifests(monkeypatch):
    fake_module = types.ModuleType("fake_iip_plugin_for_test")
    fake_module.iip_plugin_manifests = lambda: (make_manifest("from_plugin"),)
    monkeypatch.setitem(sys.modules, "fake_iip_plugin_for_test", fake_module)
    monkeypatch.setenv("IIP_PLUGINS", "fake_iip_plugin_for_test")

    discovered = discover_plugins()

    assert len(discovered) == 1
    assert discovered[0].name == "from_plugin"
    assert manifest_map()["from_plugin"].status == ProviderStatus.READY


def test_discover_plugins_handles_multiple_comma_separated_modules(monkeypatch):
    first = types.ModuleType("fake_plugin_one")
    first.iip_plugin_manifests = lambda: (make_manifest("plugin_one"),)
    second = types.ModuleType("fake_plugin_two")
    second.iip_plugin_manifests = lambda: (make_manifest("plugin_two"),)
    monkeypatch.setitem(sys.modules, "fake_plugin_one", first)
    monkeypatch.setitem(sys.modules, "fake_plugin_two", second)
    monkeypatch.setenv("IIP_PLUGINS", "fake_plugin_one, fake_plugin_two")

    discovered = discover_plugins()

    assert {m.name for m in discovered} == {"plugin_one", "plugin_two"}


def test_discover_plugins_skips_module_without_manifest_function(monkeypatch):
    empty_module = types.ModuleType("fake_plugin_without_manifests")
    monkeypatch.setitem(sys.modules, "fake_plugin_without_manifests", empty_module)
    monkeypatch.setenv("IIP_PLUGINS", "fake_plugin_without_manifests")

    assert discover_plugins() == ()


def test_discover_plugins_skips_module_that_fails_to_import(monkeypatch):
    monkeypatch.setenv("IIP_PLUGINS", "this_module_does_not_exist_anywhere")
    # must not raise
    assert discover_plugins() == ()


def test_discover_plugins_one_broken_module_does_not_block_the_others(monkeypatch):
    good_module = types.ModuleType("fake_good_plugin")
    good_module.iip_plugin_manifests = lambda: (make_manifest("good_plugin"),)
    monkeypatch.setitem(sys.modules, "fake_good_plugin", good_module)
    monkeypatch.setenv(
        "IIP_PLUGINS", "this_module_does_not_exist_anywhere,fake_good_plugin"
    )

    discovered = discover_plugins()

    assert len(discovered) == 1
    assert discovered[0].name == "good_plugin"


def test_discover_plugins_uses_custom_env_var_name(monkeypatch):
    monkeypatch.delenv("IIP_PLUGINS", raising=False)
    fake_module = types.ModuleType("fake_plugin_custom_env")
    fake_module.iip_plugin_manifests = lambda: (make_manifest("custom_env_plugin"),)
    monkeypatch.setitem(sys.modules, "fake_plugin_custom_env", fake_module)
    monkeypatch.setenv("MY_CUSTOM_PLUGINS_VAR", "fake_plugin_custom_env")

    discovered = discover_plugins(env_var="MY_CUSTOM_PLUGINS_VAR")

    assert len(discovered) == 1
    assert discovered[0].name == "custom_env_plugin"
