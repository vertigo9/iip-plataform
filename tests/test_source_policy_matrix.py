from iip.registry.models import AssetClass
from iip.sources.policy import *


def test_all_known_fund_managers():
    names = {s.name for s in default_provider_specs()}
    assert {
        "xp_asset",
        "patria",
        "sparta",
        "capitania",
        "valora",
        "btg",
        "manati",
        "trx",
        "araujo_fontes",
        "hedge",
        "rio_bravo",
        "kinea",
    } <= names


def test_transversal_providers():
    names = {s.name for s in default_provider_specs()}
    assert {"cvm", "fnet", "b3", "ri_company", "sec", "issuer"} <= names


def test_fund_priority():
    assert default_priority_for(AssetClass.FUND) == (
        "cvm",
        "fnet",
        "institutional",
        "b3",
        "market_data",
    )


def test_equity_priority():
    assert default_priority_for(AssetClass.EQUITY) == (
        "cvm",
        "ri_company",
        "b3",
        "market_data",
    )


def test_adr_uses_sec():
    assert default_priority_for(AssetClass.ADR)[0] == "sec"


def test_policy_for_each_asset_class():
    assert {p.asset_class for p in build_default_policies()} == set(AssetClass)


def test_roles_are_explicit():
    specs = {s.name: s for s in default_provider_specs()}
    assert SourceRole.INSTITUTIONAL_PRIMARY in specs["xp_asset"].roles
    assert SourceRole.REGULATORY in specs["cvm"].roles


def test_managers_are_fund_scoped():
    specs = {s.name: s for s in default_provider_specs()}
    for name in (
        "xp_asset",
        "patria",
        "sparta",
        "capitania",
        "valora",
        "btg",
        "manati",
        "trx",
        "araujo_fontes",
        "hedge",
        "rio_bravo",
        "kinea",
    ):
        assert specs[name].asset_classes == (AssetClass.FUND,)
