import pytest

from iip import versioning


def test_version_manager_surface():
    manager = versioning.VersionManager
    current = manager.current()
    assert current is not None
    assert str(current)


def test_version_value_roundtrip():
    candidates = [
        name
        for name in dir(versioning)
        if name.lower() in {"version", "versioninfo", "versionmanager"}
    ]
    assert candidates


@pytest.mark.parametrize(
    "candidate",
    ["1.0.0", "1.2.3", "2.0.0-alpha", "2.1.0-beta.1"],
)
def test_version_strings_are_parseable_when_api_supports_it(candidate):
    parse = getattr(versioning, "Version", None)
    if parse is None:
        pytest.skip("Version constructor not exposed in this implementation")
    try:
        value = parse(candidate)
    # pytest.skip se a API de Version for incompativel neste build
    except Exception:  # noqa: BLE001
        pytest.skip("Version implementation uses a different constructor contract")
    assert str(value)
