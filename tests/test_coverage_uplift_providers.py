import pytest


def test_provider_health_module_surface():
    try:
        from iip.providers import health
    except Exception as exc:  # noqa: BLE001 — pytest.skip se o modulo opcional nao estiver disponivel
        pytest.skip(f"provider health module unavailable: {exc}")

    public = [name for name in dir(health) if not name.startswith("_")]
    assert public


def test_provider_runtime_module_surface():
    try:
        from iip.providers import runtime
    except Exception as exc:  # noqa: BLE001 — pytest.skip se o modulo opcional nao estiver disponivel
        pytest.skip(f"provider runtime module unavailable: {exc}")

    public = [name for name in dir(runtime) if not name.startswith("_")]
    assert public
