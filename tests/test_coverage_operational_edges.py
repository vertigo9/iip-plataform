def test_operational_surfaces():
    modules = (
        "iip.operational.atlas_gateway",
        "iip.operational.discovery_chain",
        "iip.operational.quality",
        "iip.operational.portfolio_runner",
        "iip.operational.provider_adapter",
        "iip.operational.provider_catalog",
        "iip.operational.normalization",
        "iip.operational.checkpoint",
    )
    for path in modules:
        module = __import__(path, fromlist=["*"])
        assert any(not n.startswith("_") for n in dir(module))


def test_operational_integration_surfaces():
    modules = (
        "iip.operational_integration.cli_commands",
        "iip.operational_integration.export_pipeline",
        "iip.operational_integration.health_runtime",
        "iip.operational_integration.portfolio_e2e",
        "iip.operational_integration.portfolio_integration",
        "iip.operational_integration.provider_runtime_matrix",
        "iip.operational_integration.regression_gate",
        "iip.operational_integration.system_reconciliation",
        "iip.operational_integration.validation_matrix",
    )
    for path in modules:
        module = __import__(path, fromlist=["*"])
        assert any(not n.startswith("_") for n in dir(module))
