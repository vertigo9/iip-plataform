from types import SimpleNamespace

import pytest

from iip.portfolio_data.currency import normalize_currency_weight
from iip.portfolio_data.data_quality import validate_weight
from iip.portfolio_data.income import IncomeEvent, annualized_income
from iip.portfolio_data.market_data import normalize_quote
from iip.portfolio_data.portfolio_data_pipeline import AssetDataBundle, to_report
from iip.portfolio_data.valuation import (
    ValuationMethod,
    build_snapshot,
    margin_of_safety,
)
from iip.portfolio_data.yield_metrics import yield_on_cost, yield_on_price
from iip.sources.adapter import AtlasDocumentAdapter
from iip.sources.discovery import MultiProviderDiscovery
from iip.sources.harvester import XPAssetHTTPHarvester
from iip.sources.health import SourceHealth
from iip.sources.health_registry import SourceHealthRegistry
from iip.sources.policy import (
    build_default_policies,
    default_priority_for,
    default_provider_specs,
)
from iip.sources.provider_registry import ProviderRegistry
from iip.sources.registry import AssetRef, SourceRef, SourceRegistry
from iip.sources.router import SourceRouter
from iip.sources.xp_asset import DocumentTarget, XPAssetProvider
from iip.strategy.allocation_planner import plan
from iip.strategy.e2e import execute as execute_e2e
from iip.strategy.income_plan import build as build_income
from iip.strategy.models import StrategyInput
from iip.strategy.pipeline import StrategyPipelineInput
from iip.strategy.pipeline import run as run_strategy
from iip.strategy.risk_budget import assess as assess_risk
from iip.strategy.strategy_engine import build_signal, decide
from iip.universal.concentration import (
    all_concentrations,
    concentration,
    concentration_alerts,
)
from iip.universal.contribution_policy import ContributionRule
from iip.universal.contribution_policy import evaluate as evaluate_contribution
from iip.universal.portfolio_state import PortfolioState, PositionState
from iip.universal.risk_model import RiskFactors, RiskLevel, assess_overall
from iip.universal.snapshot_diff import diff


def strategy_input(**kw):
    base = dict(
        ticker="cpfe3",
        score=8,
        confidence=0.9,
        income_yield=0.06,
        margin_of_safety=0.20,
        risk_score=3,
        current_weight=0.05,
        target_weight=0.10,
    )
    base.update(kw)
    return StrategyInput(**base)


def test_strategy_engine_all_action_bands():
    strong = strategy_input(
        score=10, confidence=1, income_yield=0.10, margin_of_safety=1.0
    )
    assert build_signal(strong).ticker == "CPFE3"
    assert decide(strong).action == "APORTAR"
    assert decide(strategy_input(risk_score=9)).action == "REVISAR"
    assert decide(strategy_input(target_weight=0.05, current_weight=0.05)).action in {
        "MANTER",
        "AGUARDAR",
    }
    assert (
        decide(
            strategy_input(
                score=1,
                confidence=0.1,
                income_yield=0,
                margin_of_safety=-1,
                risk_score=3,
                current_weight=0.5,
                target_weight=0.5,
            )
        ).action
        == "AGUARDAR"
    )


def test_strategy_planning_and_income():
    result = plan(
        (("A", 0.10), ("B", 0.30)),
        (("A", 0.20), ("B", 0.20), ("C", 0.10)),
        threshold=0.01,
    )
    assert [x.ticker for x in result] == ["A", "C", "B"]
    assert result[0].action == "AUMENTAR"
    assert result[2].action == "REDUZIR"
    assert build_income(100, 120).gap == 20
    assert build_income(120, 100).coverage_ratio == 1.2
    assert build_income(0, 0).coverage_ratio == 1.0
    assert assess_risk("cpfe3", 1.2, 0.8, 12).breach
    assert assess_risk("cpfe3", -1, 0.8, -1).current_weight == 0


def test_strategy_pipeline_and_e2e():
    data = StrategyPipelineInput(
        "2026-08-29",
        (
            strategy_input(),
            strategy_input(ticker="hgru11", score=7, target_weight=0.05),
        ),
        1000,
        1200,
        (("CPFE3", 0.05),),
        (("CPFE3", 0.08),),
    )
    report = run_strategy(data)
    assert len(report.decisions) == 2
    assert execute_e2e(data).success
    bad = SimpleNamespace(
        assets=(),
    )
    assert execute_e2e(bad).success is False


def test_portfolio_data_primitives():
    assert normalize_currency_weight("usd", 0.1234).weight == 0.1234
    with pytest.raises(ValueError):
        normalize_currency_weight("BRL", 1.1)
    assert validate_weight(0.5).valid
    assert not validate_weight(float("nan")).valid
    assert not validate_weight(-0.1).valid
    assert normalize_quote("cpfe3", 42, "brl", "2026").ticker == "CPFE3"
    with pytest.raises(ValueError):
        normalize_quote("x", -1, "BRL", "2026")


def test_income_valuation_and_yield():
    events = (
        IncomeEvent("CPFE3", "dividend", 0.50),
        IncomeEvent("CPFE3", "jcp", -0.10),
    )
    assert annualized_income(events, 12) == 6.0
    with pytest.raises(ValueError):
        annualized_income(events, 0)
    assert margin_of_safety(120, 100) == 0.2
    with pytest.raises(ValueError):
        margin_of_safety(100, 0)
    snap = build_snapshot("cpfe3", ValuationMethod.DCF, 120, 100)
    assert snap.margin_of_safety == 0.2
    assert (
        build_snapshot("cpfe3", ValuationMethod.NAV, None, None).margin_of_safety
        is None
    )
    assert yield_on_price(10, 100) == 0.1
    assert yield_on_cost(10, 50) == 0.2
    with pytest.raises(ValueError):
        yield_on_price(1, 0)
    with pytest.raises(ValueError):
        yield_on_cost(1, 0)


def test_portfolio_data_pipeline():
    quote = normalize_quote("cpfe3", 100, "BRL", "2026")
    bundle = AssetDataBundle(
        "cpfe3",
        quote,
        (IncomeEvent("CPFE3", "dividend", 1.0),),
        build_snapshot("cpfe3", ValuationMethod.DCF, 120, 100),
        8.0,
        "APORTAR",
    )
    report = to_report("2026-08-29", (bundle,))
    assert report.rows[0].ticker == "CPFE3"
    assert report.total_value == 100
    assert report.total_income == 12
    assert report.rows[0].yield_on_price == 0.12


def positions():
    return (
        PositionState("A", 1, 50, 0.30, "FUND", manager="M1", segment="S1"),
        PositionState("B", 1, 40, 0.25, "FUND", manager="M1", segment="S2"),
        PositionState("C", 1, 20, 0.15, "EQUITY", manager="M2", segment="S1"),
    )


def test_universal_state_and_concentration():
    state = PortfolioState("2026", positions(), 110)
    assert [p.ticker for p in state.by_asset_class("FUND")] == ["A", "B"]
    assert [p.ticker for p in state.by_manager("m1")] == ["A", "B"]
    over = concentration(positions(), "manager", 0.50)
    assert over[0].breached
    all_items = all_concentrations(positions())
    alerts = concentration_alerts(positions(), manager_limit=0.50)
    assert all_items
    assert alerts


def test_universal_contribution_risk_and_diff():
    rule = ContributionRule(7, 0.8, 0.20)
    assert evaluate_contribution("CPFE3", 8, 0.9, 0.10, rule).eligible
    assert (
        evaluate_contribution("CPFE3", 6, 0.9, 0.10, rule).reason
        == "score_below_minimum"
    )
    assert (
        evaluate_contribution("CPFE3", 8, 0.7, 0.10, rule).reason
        == "confidence_below_minimum"
    )
    assert (
        evaluate_contribution("CPFE3", 8, 0.9, 0.20, rule).reason
        == "position_above_limit"
    )

    assert assess_overall(RiskFactors()) == RiskLevel.MEDIO
    assert assess_overall(RiskFactors(market=RiskLevel.ALTO)) == RiskLevel.ALTO
    assert (
        assess_overall(RiskFactors(market=RiskLevel.MEDIO, liquidity=RiskLevel.MEDIO))
        == RiskLevel.MEDIO
    )
    assert assess_overall(RiskFactors(market=RiskLevel.BAIXO)) == RiskLevel.BAIXO

    prev = PortfolioState("d1", (PositionState("A", 1, 1, 0.1, "FUND"),), 1)
    cur = PortfolioState(
        "d2",
        (
            PositionState("A", 1, 1, 0.2, "FUND"),
            PositionState("B", 1, 1, 0.1, "EQUITY"),
        ),
        2,
    )
    changes = diff(prev, cur)
    assert changes[0].ticker == "A"
    assert changes[0].change == 0.1
    assert changes[1].previous_weight is None

    changes_from_none = diff(None, cur)
    assert changes_from_none[1].previous_weight is None


class FakeProvider:
    provider_name = "fake"

    def __init__(self, documents=(), raises=False):
        self.documents = documents
        self.raises = raises

    def supports(self, asset):
        return asset.ticker.upper() == "CPFE3"

    def discover(self, asset, years):
        if self.raises:
            raise RuntimeError("boom")
        return self.documents


def asset_with_sources(*sources, manager=None):
    return AssetRef("CPFE3", "fund", "FII", manager=manager, sources=tuple(sources))


def test_source_health_registry_and_policy():
    reg = SourceHealthRegistry()
    health = SourceHealth(" XP_ASSET ", available=True)
    reg.register(health)
    assert reg.get("xp_asset").available
    assert reg.get(" ").provider if reg.get(" ") else True
    reg.clear()
    assert reg.get("xp_asset") is None

    specs = default_provider_specs()
    assert any(x.name == "xp_asset" for x in specs)
    assert default_priority_for("fund")
    assert default_priority_for("unknown")
    assert len(build_default_policies()) >= 1


def test_source_registry_and_provider_registry():
    sr = SourceRegistry()
    source1 = SourceRef("xp_asset", "institutional_primary", 2, "https://b")
    source2 = SourceRef("xp_asset", "institutional_primary", 1, "https://a")
    asset = asset_with_sources(source1, source2)
    sr.register(asset)
    assert sr.get("cpfe3").sources[0].url == "https://a"
    assert sr.sources_for("missing") == ()
    sr.register_many((asset,))
    assert SourceRegistry.from_assets((asset,)).get("CPFE3")

    with pytest.raises(ValueError):
        sr.register(AssetRef("", "fund", "FII", sources=(source1,)))
    with pytest.raises(ValueError):
        sr.register(AssetRef("X", "fund", "FII"))

    pr = ProviderRegistry()
    fake = FakeProvider()
    pr.register(fake)
    assert pr.get("FAKE") is fake
    with pytest.raises(ValueError):
        pr.register(fake)
    assert pr.resolve(asset) is fake

    hr = SourceHealthRegistry()
    hr.register(SourceHealth("fake", enabled=True, available=True))
    assert pr.resolve_healthy(asset, hr) is fake
    hr.clear()
    assert pr.resolve_healthy(asset, hr) is None


def test_xp_asset_provider_and_router_discovery():
    xp = XPAssetProvider()
    source = SourceRef("xp_asset", "primary", 1, " https://institutional.example/doc ")
    asset = asset_with_sources(source)
    assert xp.supports(asset)
    targets = xp.discover(asset, range(2024, 2026))
    assert len(targets) == 2
    assert targets[0].year == 2024
    assert xp.discover(asset, range(0)).__len__() == 1

    with pytest.raises(TypeError):
        xp.discover(asset, [2024])
    with pytest.raises(ValueError):
        xp.discover(AssetRef("CPFE3", "fund", "FII"), range(2024, 2025))
    inactive = SourceRef("xp_asset", "primary", 1, "url", active=False)
    with pytest.raises(ValueError):
        xp.discover(asset_with_sources(inactive), range(2024, 2025))
    with pytest.raises(ValueError):
        xp.discover(
            asset_with_sources(SourceRef("other", "x", 1, "u")), range(2024, 2025)
        )

    pr = ProviderRegistry()
    pr.register(xp)
    sr = SourceRegistry()
    sr.register(asset)
    router = SourceRouter(source_registry=sr, provider_registry=pr)
    assert router.primary_route(asset).provider is xp
    assert router.fallback_routes(asset) == ()

    good = FakeProvider((DocumentTarget("CPFE3", "fake", "p", "u", 2026),))
    pr2 = ProviderRegistry()
    pr2.register(xp)
    pr2.register(good)
    source_other = SourceRef("fake", "fallback", 2, "u2")
    asset2 = asset_with_sources(source, source_other)
    router2 = SourceRouter(source_registry=sr, provider_registry=pr2)
    assert router2.routes_for(asset2)

    discovery = MultiProviderDiscovery(router2)
    result = discovery.discover(asset2, range(2026, 2027))
    assert result
    all_result = discovery.discover_all(asset2, range(2026, 2027))
    assert all_result

    bad = FakeProvider((), raises=True)
    pr3 = ProviderRegistry()
    pr3.register(bad)
    router3 = SourceRouter(source_registry=sr, provider_registry=pr3)
    assert MultiProviderDiscovery(router3).discover(asset2, range(2026, 2027)) == ()


def test_harvester_and_adapter():
    target = DocumentTarget("CPFE3", "xp_asset", "primary", "https://example/doc", 2026)

    class Response:
        status = None
        headers = {"Content-Type": "application/pdf; charset=utf-8"}

        def read(self):
            return b"abc"

        def geturl(self):
            return "https://final.example/doc"

    calls = []

    def opener(request, timeout):
        calls.append((request.get_method(), request.full_url, timeout))
        return Response()

    harvester = XPAssetHTTPHarvester(opener=opener, timeout=10, user_agent="TEST")
    fetched = harvester.fetch(target)
    assert fetched.status_code == 200
    assert fetched.content_type == "application/pdf"
    assert fetched.final_url.endswith("/doc")
    assert calls[0][0] == "GET"
    assert harvester.fetch_many((target, target))[0].body == b"abc"

    adapted = AtlasDocumentAdapter().from_fetched(fetched)
    assert adapted.ticker == "CPFE3"
    assert adapted.provider == "xp_asset"
    assert adapted.content_type == "application/pdf"
    assert adapted.body == b"abc"
