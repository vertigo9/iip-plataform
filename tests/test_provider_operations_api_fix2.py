def test_provider_operations_imports_and_public_api():
    from iip.providers import (
        OperationalProviderPlanner,
        ProviderFactory,
        ProviderHealthService,
        ProviderOperations,
        ProviderStatus,
        ProviderValidator,
    )

    assert all(
        (
            ProviderFactory,
            ProviderOperations,
            ProviderHealthService,
            OperationalProviderPlanner,
            ProviderValidator,
            ProviderStatus,
        )
    )


def test_portfolio_package_does_not_depend_on_provider_manifests():
    from iip.portfolio import PORTFOLIO_ASSETS, get_asset

    assert get_asset("XPML11") is not None
    assert len(PORTFOLIO_ASSETS) == 35  # 37 no registro, 2 encerrados (BTCI11 e PVBI11)
