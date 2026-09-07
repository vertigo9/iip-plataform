from iip.providers.batch import (
    AdapterStatus,
    build_batch_registry,
    promoted_registry,
)


def test_batch_contains_ten_pending_fund_managers():
    registry = build_batch_registry()
    assert len(registry) == 10
    assert all(
        adapter.spec.status == AdapterStatus.MAPPED for adapter in registry.values()
    )


def test_sparta_manager_binding_is_normalized():
    registry = build_batch_registry()
    adapter = registry["sparta"]

    class Asset:
        manager = "Sparta"

    assert adapter.supports(Asset())


def test_btg_manager_binding_is_normalized():
    registry = build_batch_registry()
    adapter = registry["btg"]

    class Asset:
        manager = "BTG Pactual"

    assert adapter.supports(Asset())


def test_promoted_registry_requires_real_callable():
    def fake_discovery(*args, **kwargs):
        return ("document",)

    promoted = promoted_registry({"sparta": fake_discovery})
    assert list(promoted) == ["sparta"]
    assert promoted["sparta"].discover() == ("document",)
    assert promoted["sparta"].spec.status == AdapterStatus.IMPLEMENTED


def test_mapped_providers_are_not_promoted():
    def fake_discovery(*args, **kwargs):
        return ("document",)

    promoted = promoted_registry({"sparta": fake_discovery})
    assert "btg" not in promoted
    assert "kinea" not in promoted


def test_all_known_names_are_present():
    registry = build_batch_registry()
    expected = {
        "sparta",
        "btg",
        "kinea",
        "hedge",
        "rio_bravo",
        "capitania",
        "valora",
        "manati",
        "trx",
        "araujo_fontes",
    }
    assert set(registry) == expected
