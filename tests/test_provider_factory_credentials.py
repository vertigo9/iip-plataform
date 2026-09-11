import pytest

from iip.config import IIPSettings
from iip.providers.factory import ProviderFactory
from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester
from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester


@pytest.fixture(autouse=True)
def _clear_real_env_credentials(monkeypatch):
    # _env_file=None below only disables .env file loading — pydantic
    # BaseSettings still reads real OS environment variables regardless.
    # If the person's shell already exported IIP_BOLSAI_API_KEY/
    # IIP_BRAPI_TOKEN (e.g. to test the CLI for real earlier), those
    # would otherwise leak into "without credential" test cases here.
    monkeypatch.delenv("IIP_BOLSAI_API_KEY", raising=False)
    monkeypatch.delenv("IIP_BRAPI_TOKEN", raising=False)


def make_settings(**kwargs):
    return IIPSettings(_env_file=None, **kwargs)


def test_create_b3_returns_none_without_credential():
    factory = ProviderFactory(settings=make_settings())
    handle = factory.create("b3")
    assert handle.provider is None


def test_create_b3_instantiates_with_credential():
    factory = ProviderFactory(settings=make_settings(bolsai_api_key="test-key"))
    handle = factory.create("b3")
    assert isinstance(handle.provider, BolsaiHTTPHarvester)


def test_create_b3_brapi_returns_none_without_credential():
    factory = ProviderFactory(settings=make_settings())
    handle = factory.create("b3_brapi")
    assert handle.provider is None


def test_create_b3_brapi_instantiates_with_credential():
    factory = ProviderFactory(settings=make_settings(brapi_token="test-token"))
    handle = factory.create("b3_brapi")
    assert isinstance(handle.provider, BrapiHTTPHarvester)


def test_create_b3_with_credential_does_not_affect_b3_brapi():
    factory = ProviderFactory(settings=make_settings(bolsai_api_key="test-key"))
    b3_brapi_handle = factory.create("b3_brapi")
    assert b3_brapi_handle.provider is None


def test_create_ri_company_stays_none_regardless_of_credentials():
    # mziq (ri_company) is PARTIAL for a different reason (missing
    # per-company config, not a missing credential) — declares no
    # credential_setting, so it must never be auto-instantiated just
    # because unrelated credentials happen to be set.
    factory = ProviderFactory(
        settings=make_settings(bolsai_api_key="test-key", brapi_token="test-token")
    )
    handle = factory.create("ri_company")
    assert handle.provider is None


def test_create_pending_provider_still_returns_none():
    factory = ProviderFactory(
        settings=make_settings(bolsai_api_key="test-key", brapi_token="test-token")
    )
    handle = factory.create("sparta")  # a PENDING fund manager
    assert handle.provider is None


def test_create_ready_provider_unaffected_by_credential_wiring():
    factory = ProviderFactory(settings=make_settings())
    handle = factory.create("bacen")  # READY, no credential needed
    assert handle.provider is not None


def test_create_unknown_provider_returns_none():
    factory = ProviderFactory(settings=make_settings())
    assert factory.create("does_not_exist") is None


def test_credential_kwargs_never_pass_empty_string_as_configured():
    # An explicitly empty string should be treated the same as "not set"
    # — never instantiate with a blank credential.
    factory = ProviderFactory(settings=make_settings(bolsai_api_key=""))
    handle = factory.create("b3")
    assert handle.provider is None


def test_factory_defaults_to_get_settings_when_none_given():
    # No settings passed — should not raise, falls back to get_settings().
    factory = ProviderFactory()
    handle = factory.create("bacen")
    assert handle.provider is not None
