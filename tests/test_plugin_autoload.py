"""Plugins de provider carregados na inicialização do CLI (IIP_PLUGINS).

Cada teste usa módulos de plugin reais, escritos num diretório temporário e
importados de verdade -- o que se verifica é o caminho completo: variável de
ambiente -> CLI -> registro -> ``ProviderFactory`` instancia o provider."""

import itertools
import sys
import textwrap

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.health import PluginsHealthCheck
from iip.providers import registry as provider_registry
from iip.providers.factory import ProviderFactory
from iip.providers.registry import (
    PluginLoadReport,
    clear_runtime_manifests,
    last_plugin_report,
    load_plugins,
    manifest_map,
)

_counter = itertools.count()

GOOD_PLUGIN = textwrap.dedent("""
    from iip.providers.registry import ProviderKind, ProviderManifest, ProviderStatus


    class FakeProvider:
        def __init__(self, api_key=None):
            self.api_key = api_key

        def collect(self):
            return "coletado"


    def iip_plugin_manifests():
        return (
            ProviderManifest(
                name="@NAME@",
                kind=ProviderKind.MARKET,
                status=ProviderStatus.READY,
                asset_classes=("fund",),
                source_roles=("price",),
                implementation="@MODULE@.FakeProvider",
            ),
        )
    """)


@pytest.fixture(autouse=True)
def _isolated_plugin_state(monkeypatch):
    monkeypatch.delenv("IIP_PLUGINS", raising=False)
    monkeypatch.setattr(provider_registry, "_last_report", None)
    # get_settings() is cached: without this, a value read while IIP_PLUGINS was
    # set by one test leaks into every later test in the process
    get_settings.cache_clear()
    clear_runtime_manifests()
    yield
    clear_runtime_manifests()
    get_settings.cache_clear()
    # load_plugins() assigns the module global directly, so monkeypatch would
    # "restore" a stale report from the previous test -- reset it explicitly
    provider_registry._last_report = None


@pytest.fixture
def make_plugin(tmp_path, monkeypatch):
    """Escreve um módulo de plugin importável e devolve o nome dele."""
    monkeypatch.syspath_prepend(str(tmp_path))

    def _make(source: str, *, provider_name: str | None = None) -> str:
        module = f"iip_test_plugin_{next(_counter)}"
        body = source.replace("@NAME@", provider_name or f"prov_{module}")
        body = body.replace("@MODULE@", module)
        (tmp_path / f"{module}.py").write_text(body, encoding="utf-8")
        return module

    yield _make
    for name in [m for m in sys.modules if m.startswith("iip_test_plugin_")]:
        del sys.modules[name]


def test_cli_loads_the_plugin_and_the_factory_instantiates_its_provider(
    make_plugin, monkeypatch
):
    module = make_plugin(GOOD_PLUGIN, provider_name="meu_provider_real")
    monkeypatch.setenv("IIP_PLUGINS", module)

    result = CliRunner().invoke(cli, ["version"])

    assert result.exit_code == 0
    assert "meu_provider_real" in manifest_map()
    handle = ProviderFactory().create("meu_provider_real")
    assert handle is not None
    assert type(handle.provider).__name__ == "FakeProvider"
    assert handle.provider.collect() == "coletado"


def test_a_broken_plugin_is_reported_on_stderr_and_does_not_stop_the_command(
    make_plugin, monkeypatch
):
    good = make_plugin(GOOD_PLUGIN, provider_name="sobrevive")
    monkeypatch.setenv("IIP_PLUGINS", f"modulo_que_nao_existe_xyz,{good}")

    result = CliRunner().invoke(cli, ["version"])

    assert result.exit_code == 0
    assert "modulo_que_nao_existe_xyz" in result.stderr
    assert "modulo_que_nao_existe_xyz" not in result.stdout
    assert "sobrevive" in manifest_map()


def test_no_warning_and_no_plugins_when_none_are_configured():
    result = CliRunner().invoke(cli, ["version"])

    assert result.exit_code == 0
    assert result.stderr == ""
    assert last_plugin_report().configured == ()


def test_help_alone_does_not_load_plugins(make_plugin, monkeypatch):
    monkeypatch.setenv("IIP_PLUGINS", make_plugin(GOOD_PLUGIN))

    CliRunner().invoke(cli, [])

    assert last_plugin_report() is None


@pytest.mark.parametrize(
    "source, expected",
    [
        ("raise RuntimeError('boom no import')", "RuntimeError: boom no import"),
        ("x = 1", "missing function iip_plugin_manifests"),
        (
            "def iip_plugin_manifests():\n    return ('nao sou um manifesto',)",
            "must return ProviderManifest items",
        ),
        (
            "def iip_plugin_manifests():\n    raise ValueError('falhou ao montar')",
            "ValueError: falhou ao montar",
        ),
    ],
)
def test_every_kind_of_plugin_failure_is_recorded_not_raised(
    make_plugin, monkeypatch, source, expected
):
    module = make_plugin(source)
    monkeypatch.setenv("IIP_PLUGINS", module)

    report = load_plugins()

    assert report.loaded == ()
    assert report.manifests == ()
    assert len(report.failures) == 1
    assert report.failures[0].module == module
    assert expected in report.failures[0].reason


def test_nothing_from_a_failed_plugin_is_registered(make_plugin, monkeypatch):
    source = GOOD_PLUGIN + "\nraise RuntimeError('quebra depois de definir tudo')\n"
    module = make_plugin(source, provider_name="nao_deve_registrar")
    monkeypatch.setenv("IIP_PLUGINS", module)

    load_plugins()

    assert "nao_deve_registrar" not in manifest_map()


def test_a_plugin_can_override_a_built_in_manifest_by_name(make_plugin, monkeypatch):
    built_in = next(iter(manifest_map()))
    module = make_plugin(GOOD_PLUGIN, provider_name=built_in)
    monkeypatch.setenv("IIP_PLUGINS", module)

    load_plugins()

    assert manifest_map()[built_in].implementation == f"{module}.FakeProvider"


def test_loading_twice_is_idempotent(make_plugin, monkeypatch):
    monkeypatch.setenv("IIP_PLUGINS", make_plugin(GOOD_PLUGIN, provider_name="dup"))

    load_plugins()
    before = dict(manifest_map())
    report = load_plugins()

    assert manifest_map() == before
    assert len(report.manifests) == 1


def test_plugins_can_come_from_the_settings_when_the_env_var_is_absent(
    make_plugin, monkeypatch
):
    module = make_plugin(GOOD_PLUGIN, provider_name="via_settings")
    monkeypatch.setattr(get_settings(), "plugins", module)

    report = load_plugins()

    assert report.loaded == (module,)
    assert "via_settings" in manifest_map()


def test_env_var_takes_precedence_over_the_settings(make_plugin, monkeypatch):
    from_env = make_plugin(GOOD_PLUGIN, provider_name="veio_do_env")
    from_settings = make_plugin(GOOD_PLUGIN, provider_name="veio_do_settings")
    monkeypatch.setattr(get_settings(), "plugins", from_settings)
    monkeypatch.setenv("IIP_PLUGINS", from_env)

    load_plugins()

    assert "veio_do_env" in manifest_map()
    assert "veio_do_settings" not in manifest_map()


def test_health_is_healthy_with_no_plugins_and_says_so():
    result = PluginsHealthCheck().check(get_settings())

    assert result.healthy
    assert "no plugins configured" in result.message


def test_health_is_healthy_when_every_plugin_loaded(make_plugin, monkeypatch):
    module = make_plugin(GOOD_PLUGIN)
    monkeypatch.setenv("IIP_PLUGINS", module)

    result = PluginsHealthCheck().check(get_settings())

    assert result.healthy
    assert module in result.message
    assert result.metadata["failed"] == ""


def test_health_is_unhealthy_and_names_the_plugin_that_failed(monkeypatch):
    monkeypatch.setenv("IIP_PLUGINS", "plugin_inexistente_abc")

    result = PluginsHealthCheck().check(get_settings())

    assert not result.healthy
    assert "plugin_inexistente_abc" in result.message
    assert result.metadata["failed"] == "plugin_inexistente_abc"


def test_health_command_lists_the_plugins_check(monkeypatch):
    monkeypatch.setenv("IIP_PLUGINS", "plugin_inexistente_abc")

    result = CliRunner().invoke(cli, ["health"])

    assert "plugins" in result.stdout


def test_discover_plugins_keeps_returning_only_the_manifests(make_plugin, monkeypatch):
    monkeypatch.setenv("IIP_PLUGINS", make_plugin(GOOD_PLUGIN, provider_name="antigo"))

    manifests = provider_registry.discover_plugins()

    assert [m.name for m in manifests] == ["antigo"]
    assert isinstance(last_plugin_report(), PluginLoadReport)
