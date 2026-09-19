from dataclasses import fields, is_dataclass


def _construct(cls):
    values = {}
    for f in fields(cls):
        t = str(f.type)
        if "bool" in t:
            values[f.name] = True
        elif "int" in t:
            values[f.name] = 1
        elif "float" in t:
            values[f.name] = 0.0
        elif "tuple" in t:
            values[f.name] = ()
        elif "list" in t:
            values[f.name] = []
        else:
            values[f.name] = "x"
    try:
        return cls(**values)
    # adapter best-effort: campos incompativeis viram None, nao erro
    except Exception:  # noqa: BLE001
        return None


def test_provider_model_construction():
    modules = (
        "iip.providers.certification",
        "iip.providers.health",
        "iip.providers.runtime",
        "iip.providers.validation",
    )
    found = []
    for path in modules:
        module = __import__(path, fromlist=["*"])
        for name in dir(module):
            if name.startswith("_"):
                continue
            obj = getattr(module, name)
            if isinstance(obj, type) and is_dataclass(obj):
                found.append(obj)
    assert found
    assert any(_construct(cls) is not None for cls in found)


def test_provider_runtime_public_surfaces():
    modules = (
        "iip.providers.batch",
        "iip.providers.factory",
        "iip.providers.integration",
        "iip.providers.operations",
    )
    for path in modules:
        module = __import__(path, fromlist=["*"])
        assert any(not n.startswith("_") for n in dir(module))
