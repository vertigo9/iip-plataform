from dataclasses import fields, is_dataclass


def _public(module):
    return [getattr(module, n) for n in dir(module) if not n.startswith("_")]


def _safe_construct(cls):
    values = {}
    for f in fields(cls):
        t = str(f.type)
        if "bool" in t:
            values[f.name] = False
        elif "int" in t:
            values[f.name] = 0
        elif "float" in t:
            values[f.name] = 0.0
        elif "tuple" in t:
            values[f.name] = ()
        elif "list" in t:
            values[f.name] = []
        else:
            values[f.name] = f.name
    try:
        return cls(**values)
    except Exception:
        return None


def test_sources_models_contract():
    import iip.sources.models as module

    classes = [
        obj for obj in _public(module) if isinstance(obj, type) and is_dataclass(obj)
    ]
    assert classes
    assert any(_safe_construct(cls) is not None for cls in classes)


def test_portfolio_data_public_contract():
    import iip.portfolio_data as module

    assert any(not n.startswith("_") for n in dir(module))


def test_universal_state_public_contract():
    import iip.universal.portfolio_state as module

    assert any(not n.startswith("_") for n in dir(module))


def test_source_namespace_imports():
    modules = (
        "iip.sources.adapter",
        "iip.sources.discovery",
        "iip.sources.health",
        "iip.sources.health_registry",
        "iip.sources.policy",
        "iip.sources.provider",
        "iip.sources.provider_registry",
        "iip.sources.registry",
        "iip.sources.router",
    )
    for path in modules:
        module = __import__(path, fromlist=["*"])
        assert any(not n.startswith("_") for n in dir(module))


def test_strategy_namespace_imports():
    modules = (
        "iip.strategy.allocation_planner",
        "iip.strategy.dividend_priority",
        "iip.strategy.history",
        "iip.strategy.income_plan",
        "iip.strategy.margin_matrix",
        "iip.strategy.pipeline",
        "iip.strategy.report",
        "iip.strategy.risk_budget",
        "iip.strategy.strategy_engine",
    )
    for path in modules:
        module = __import__(path, fromlist=["*"])
        assert any(not n.startswith("_") for n in dir(module))
