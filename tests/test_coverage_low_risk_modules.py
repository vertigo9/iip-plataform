def test_decision_surfaces():
    for path in (
        "iip.decision.models",
        "iip.decision.validation",
        "iip.decision.scoring",
        "iip.decision.decision_engine",
    ):
        module = __import__(path, fromlist=["*"])
        assert any(not n.startswith("_") for n in dir(module))


def test_universal_surfaces():
    for path in (
        "iip.universal.risk_model",
        "iip.universal.snapshot_diff",
        "iip.universal.taxonomy",
    ):
        module = __import__(path, fromlist=["*"])
        assert any(not n.startswith("_") for n in dir(module))


def test_system_surfaces():
    for path in (
        "iip.system.core_adapter",
        "iip.system.e2e",
        "iip.system.export_adapter",
        "iip.system.pipeline",
        "iip.system.regression",
    ):
        module = __import__(path, fromlist=["*"])
        assert any(not n.startswith("_") for n in dir(module))
