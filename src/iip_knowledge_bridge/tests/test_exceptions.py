from iip.exceptions import (
    ConfigurationException,
    IIPException,
    ModuleException,
    ValidationException,
)


def test_base():
    e = IIPException("erro")
    assert str(e) == "erro"


def test_config():
    assert isinstance(ConfigurationException("x"), IIPException)


def test_module():
    e = ModuleException("x", module="atlas")
    assert e.module == "atlas"


def test_validation():
    e = ValidationException("x", field="price")
    assert e.field == "price"
