import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from iip.adaptive.anomaly import detect
from iip.adaptive.signal_fusion import Signal, fuse
from iip.portfolio.matrix import build_provider_roadmap
from iip.portfolio_data.benchmark import BenchmarkComparison
from iip.portfolio_data.currency import normalize_currency_weight
from iip.portfolio_data.data_quality import validate_weight
from iip.portfolio_data.income import IncomeEvent, annualized_income
from iip.portfolio_data.market_data import normalize_quote
from iip.portfolio_data.portfolio_data_pipeline import AssetDataBundle, to_report
from iip.portfolio_data.refresh import RefreshTask, prioritize
from iip.portfolio_data.valuation import (
    ValuationMethod,
    build_snapshot,
    margin_of_safety,
)
from iip.portfolio_data.yield_metrics import yield_on_cost, yield_on_price
from iip.providers.certification import (
    CertificationStatus,
    ProviderCertification,
    ProviderCertifier,
)
from iip.providers.registry import (
    ProviderKind,
    ProviderManifest,
    ProviderStatus,
)
from iip.providers.runtime import ProviderRuntime
from iip.registry import ModuleManifest, ModuleRegistry
from iip.sources.discovery import MultiProviderDiscovery
from iip.sources.registry import AssetRef, SourceRef
from iip.sources.router import SourceRoute


def test_portfolio_provider_roadmap():
    roadmap = build_provider_roadmap()
    assert roadmap
    assert all(item.has_source_mapping for item in roadmap)
    assert any(item.next_step == "maintain_and_expand_tests" for item in roadmap)
    assert any(
        item.next_step == "validate_institutional_source_then_implement"
        for item in roadmap
    )


def test_portfolio_data_error_and_normalization_edges():
    assert normalize_currency_weight("usd", 0.25).currency == "USD"
    assert validate_weight(0.25).valid
    assert not validate_weight(float("nan")).valid
    assert normalize_quote("cpfe3", 10, "brl", "2026-08-29").ticker == "CPFE3"
    assert BenchmarkComparison("CPFE3", 0.12, 0.08).excess_return == 0.04

    with pytest.raises(ValueError):
        normalize_currency_weight("USD", 1.1)
    with pytest.raises(ValueError):
        normalize_quote("CPFE3", -1, "BRL", "2026-08-29")


def test_income_valuation_and_yield_edges():
    events = (
        IncomeEvent("CPFE3", "DIV", 0.50),
        IncomeEvent("CPFE3", "DIV", -0.10),
    )
    assert annualized_income(events) == 6.0
    with pytest.raises(ValueError):
        annualized_income(events, 0)

    assert margin_of_safety(120, 100) == 0.2
    snap = build_snapshot("cpfe3", ValuationMethod.DCF, 120, 100)
    assert snap.margin_of_safety == 0.2
    assert (
        build_snapshot("cpfe3", ValuationMethod.NAV, None, None).margin_of_safety
        is None
    )

    assert yield_on_price(10, 100) == 0.1
    assert yield_on_cost(12, 100) == 0.12
    with pytest.raises(ValueError):
        yield_on_price(1, 0)
    with pytest.raises(ValueError):
        yield_on_cost(1, 0)


def test_refresh_and_portfolio_report_pipeline():
    tasks = (
        RefreshTask("B", "src", 2),
        RefreshTask("A", "src", 1),
    )
    assert [t.ticker for t in prioritize(tasks)] == ["A", "B"]

    bundles = (
        AssetDataBundle(
            "cpfe3",
            normalize_quote("cpfe3", 100, "BRL", "2026-08-29"),
            (IncomeEvent("CPFE3", "DIV", 1.0),),
            None,
            score=8.0,
            action="APORTAR",
        ),
    )
    report = to_report("2026-08-29", bundles)
    assert report.total_value == 100
    assert report.total_income == 12
    assert report.rows[0].yield_on_price == 0.12


def test_adaptive_anomaly_and_signal_fusion_edges():
    assert detect((), 10).anomalous is False
    assert detect((10, 10, 10), 11).anomalous is True
    result = detect((10, 11, 12, 11, 10), 20, threshold=2.0)
    assert result.anomalous
    assert fuse(()).score == 0
    assert fuse((Signal("zero", 9, 0),)).contributors == ()
    fused = fuse(
        (
            Signal("a", 8, 1),
            Signal("b", 6, 3),
            Signal("ignored", 100, -1),
        )
    )
    assert fused.contributors == ("a", "b")
    assert fused.score == 6.5


def test_registry_load_all_and_status(monkeypatch):
    ModuleRegistry._modules = {}
    ModuleRegistry.register("events", ModuleManifest("events", "1", "events", True))
    ModuleRegistry.register(
        "disabled", ModuleManifest("disabled", "1", "disabled", False)
    )
    monkeypatch.setattr(ModuleRegistry, "_settings", None)

    async def publish(_event):
        return None

    monkeypatch.setattr(
        "iip.registry.EventBus.publish",
        publish,
    )
    loaded = asyncio.run(ModuleRegistry.load_all())
    assert loaded == ["events"]
    status = ModuleRegistry.status()
    assert status["total"] == 2
    assert status["enabled"] == 1
    assert status["loaded"] == 1


def test_source_discovery_fallback_and_discover_all():
    class Provider:
        def __init__(self, mode):
            self.provider_name = mode
            self.mode = mode

        def supports(self, _asset):
            return True

        def discover(self, _asset, _years):
            if self.mode == "error":
                raise RuntimeError("x")
            if self.mode == "empty":
                return ()
            return ("doc", self.mode)

    asset = AssetRef(
        "CPFE3",
        "equity",
        "equity",
        sources=(
            SourceRef("error", "primary", 1, "u1"),
            SourceRef("empty", "secondary", 2, "u2"),
            SourceRef("good", "tertiary", 3, "u3"),
        ),
    )
    routes = (
        SourceRoute(asset.sources[0], Provider("error")),
        SourceRoute(asset.sources[1], Provider("empty")),
        SourceRoute(asset.sources[2], Provider("good")),
    )

    router = SimpleNamespace(routes_for=lambda _asset: routes)
    discovery = MultiProviderDiscovery(router)
    result = discovery.discover(asset, range(2025, 2027))
    assert len(result) == 1
    assert result[0].documents == ("doc", "good")

    all_result = discovery.discover_all(asset, range(2025, 2027))
    assert len(all_result) == 1
    assert all_result[0].documents == ("doc", "good")


@dataclass(frozen=True)
class FakeProvider:
    supports: object = lambda self, *_: True
    discover: object = lambda self, *_: ()
    collect: object = lambda self, *_: ()
    harvest: object = lambda self, *_: ()
    fetch: object = lambda self, *_: None


class FakeFactory:
    def __init__(self, manifest, provider=None, error=None):
        self.manifest_value = manifest
        self.provider = provider
        self.error = error

    def manifest(self, _name):
        return self.manifest_value

    def create(self, _name):
        if self.error:
            raise self.error
        return SimpleNamespace(provider=self.provider)


def test_provider_certification_branches():
    missing = FakeFactory(None)
    assert ProviderCertifier(missing).certify("x") is None

    pending_manifest = ProviderManifest(
        "x",
        ProviderKind.INSTITUTIONAL,
        ProviderStatus.PENDING,
        ("fund",),
        ("primary",),
        None,
    )
    pending = ProviderCertifier(FakeFactory(pending_manifest)).certify("x")
    assert pending.status == CertificationStatus.INCOMPLETE

    ready_manifest = ProviderManifest(
        "x",
        ProviderKind.INSTITUTIONAL,
        ProviderStatus.READY,
        ("fund",),
        ("primary",),
        "fake.Provider",
    )
    error = ProviderCertifier(
        FakeFactory(ready_manifest, error=RuntimeError("boom"))
    ).certify("x")
    assert error.status == CertificationStatus.INCOMPLETE
    assert "factory_error" in error.notes[0]

    no_surface = ProviderCertifier(
        FakeFactory(ready_manifest, provider=object())
    ).certify("x")
    assert no_surface.status == CertificationStatus.INCOMPLETE

    certified = ProviderCertifier(
        FakeFactory(ready_manifest, provider=FakeProvider())
    ).certify("x")
    assert certified.status == CertificationStatus.CERTIFIED
    assert "discover" in certified.callable_surface


def test_provider_runtime_guardrails():
    class Certifier:
        def __init__(self, result):
            self.result = result

        def certify(self, _name):
            return self.result

    runtime = ProviderRuntime.__new__(ProviderRuntime)
    runtime.factory = SimpleNamespace(
        create=lambda _name: SimpleNamespace(provider=FakeProvider())
    )
    runtime.certifier = Certifier(None)
    assert runtime.invoke("x", "discover").error == "unknown_provider"

    runtime.certifier = Certifier(
        ProviderCertification("x", CertificationStatus.INCOMPLETE, ())
    )
    assert runtime.invoke("x", "discover").error == "incomplete"

    runtime.certifier = Certifier(
        ProviderCertification("x", CertificationStatus.CERTIFIED, ("discover",))
    )
    assert runtime.invoke("x", "unsupported").error == "method_not_certified"
    ok = runtime.invoke("x", "discover", "CPFE3", range(2026, 2027))
    assert ok.success


def test_portfolio_source_ref_contracts():
    source = SourceRef("fnet", "regulatory", 1, "https://example.invalid")
    asset = AssetRef(
        "cpfe3",
        "equity",
        "equity",
        sources=(source,),
    )
    assert asset.ticker == "cpfe3"
    assert source.active
