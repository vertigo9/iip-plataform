from iip.versioning import Version, VersionManager


def test_version_parse_full():
    v = Version.parse("1.2.3-beta")
    assert v.major == 1
    assert v.minor == 2
    assert v.patch == 3
    assert v.pre_release == "beta"


def test_version_compare_complex():
    assert Version.parse("1.0.0") < Version.parse("2.0.0")
    assert Version.parse("1.0.0") < Version.parse("1.1.0")
    assert Version.parse("1.0.0") < Version.parse("1.0.1")


def test_version_string():
    v = Version(major=0, minor=1, patch=0)
    assert str(v) == "0.1.0"


def test_version_with_prerelease():
    v = Version(major=0, minor=1, patch=0, pre_release="alpha")
    assert str(v) == "0.1.0-alpha"


def test_bump_operations():
    initial = VersionManager.current()
    VersionManager.bump_patch()
    current = VersionManager.current()
    assert current.patch >= initial.patch
    VersionManager.bump_patch()
    VersionManager.bump_minor()
    VersionManager.bump_major()
