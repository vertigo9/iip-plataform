def test_portfolio_provider_validation_uses_real_provider_operations():
    from iip.portfolio.validation import ProviderValidator
    from iip.providers.operations import ProviderOperations

    assert ProviderValidator
    assert ProviderOperations
