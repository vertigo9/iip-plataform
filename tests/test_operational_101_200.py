from iip.operational.atlas_gateway import AtlasGateway
from iip.operational.checkpoint import OperationalCheckpoint
from iip.operational.discovery_chain import DiscoveryChain
from iip.operational.knowledge_sink import OperationalEvidenceSink
from iip.operational.normalization import normalize
from iip.operational.portfolio_runner import PortfolioOperationalRunner
from iip.operational.provider_adapter import (
    AdapterExecutionStatus,
    ProviderAdapter,
    RawDocument,
)
from iip.operational.provider_catalog import SOURCE_ENTRIES, source_entry
from iip.operational.quality import validate_document


def test_source_catalog_has_twelve_managers():
    assert len(SOURCE_ENTRIES) == 12
    assert source_entry("SPARTA").provider == "sparta"


def test_mapped_adapter_does_not_claim_ready():
    adapter = ProviderAdapter("sparta", "https://sparta.example")
    result = adapter.discover("CDII11", range(2026, 2027))
    assert result.status == AdapterExecutionStatus.MAPPED
    assert result.documents == ()


def test_real_discovery_callable_promotes_only_that_adapter():
    def discover(ticker, years):
        return (
            RawDocument(
                "sparta:CDII11:2026:1",
                ticker,
                "Relatório Mensal",
                "https://example.test/cdii.pdf",
                category="Relatórios",
                year=2026,
                content=b"abc",
                provider="sparta",
            ),
        )

    adapter = ProviderAdapter("sparta", "https://example.test", discover)
    result = adapter.discover("CDII11", range(2026, 2027))
    assert result.status == AdapterExecutionStatus.READY
    assert len(result.documents) == 1


def test_normalization_is_canonical():
    doc = RawDocument(
        "id", "hgru11", "  Relatório  ", " https://x.test ", provider="patria"
    )
    normalized = normalize(doc)
    assert normalized.ticker == "HGRU11"
    assert normalized.title == "Relatório"
    assert normalized.url == "https://x.test"
    assert normalized.category == "Outros"


def test_discovery_chain_falls_back_after_failed_or_mapped_provider():
    first = ProviderAdapter(
        "sparta",
        None,
        lambda ticker, years: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    second = ProviderAdapter(
        "b3",
        None,
        lambda ticker, years: (
            RawDocument("b3:1", ticker, "Documento", "https://b3.test", provider="b3"),
        ),
    )
    report = DiscoveryChain((first, second)).discover("CDII11", range(2026, 2027))
    assert len(report.attempts) == 2
    assert report.documents[0].provider == "b3"


def test_atlas_gateway_keeps_ingest_boundary():
    gateway = AtlasGateway(lambda document: document.document_id)
    doc = normalize(
        RawDocument("id", "XPML11", "R", "https://x.test", provider="xp_asset")
    )
    result = gateway.ingest(doc)
    assert result.success
    assert result.value == "id"


def test_portfolio_runner_executes_discovery_and_atlas():
    adapter = ProviderAdapter(
        "b3",
        None,
        lambda ticker, years: (
            RawDocument("b3:1", ticker, "Documento", "https://b3.test", provider="b3"),
        ),
    )
    gateway = AtlasGateway(lambda document: ("ingested", document.document_id))
    runner = PortfolioOperationalRunner(
        lambda ticker: DiscoveryChain((adapter,)), gateway
    )
    result = runner.run_asset("XPML11", range(2026, 2027))
    assert result.ticker == "XPML11"
    assert len(result.discovery.documents) == 1
    assert result.atlas_results[0].success


def test_portfolio_runner_persists_successful_documents_to_knowledge(tmp_path):
    from iip.knowledge import KnowledgeBridge

    adapter = ProviderAdapter(
        "b3",
        None,
        lambda ticker, years: (
            RawDocument(
                "b3:XPML11:2026:real",
                ticker,
                "Documento real",
                "https://b3.test/documento.pdf",
                category="Relatorios",
                year=2026,
                content=b"documento real",
            ),
        ),
    )
    bridge = KnowledgeBridge(tmp_path / "vault")
    runner = PortfolioOperationalRunner(
        lambda ticker: DiscoveryChain((adapter,)),
        AtlasGateway(lambda document: document.document_id),
        OperationalEvidenceSink(bridge),
    )

    result = runner.run_asset("XPML11", range(2026, 2027))

    paths = bridge.repository.list_evidence("XPML11")
    assert len(result.knowledge_results) == 1
    assert len(paths) == 1
    text = paths[0].read_text(encoding="utf-8")
    assert "title: Documento real" in text
    assert "document_hash:" in text
    assert "b3:XPML11:2026:real" in bridge.assemble("XPML11").evidence[0]


def test_portfolio_runner_does_not_persist_failed_atlas_documents(tmp_path):
    from iip.knowledge import KnowledgeBridge

    adapter = ProviderAdapter(
        "b3",
        None,
        lambda ticker, years: (
            RawDocument("b3:1", ticker, "Documento", "https://b3.test"),
        ),
    )
    bridge = KnowledgeBridge(tmp_path / "vault")
    runner = PortfolioOperationalRunner(
        lambda ticker: DiscoveryChain((adapter,)),
        AtlasGateway(lambda document: (_ for _ in ()).throw(RuntimeError("offline"))),
        OperationalEvidenceSink(bridge),
    )

    result = runner.run_asset("XPML11", range(2026, 2027))

    assert result.atlas_results[0].success is False
    assert result.knowledge_results == ()
    assert bridge.repository.list_evidence("XPML11") == ()


def test_quality_gate_accepts_complete_document():
    doc = normalize(
        RawDocument("id", "HGRU11", "R", "https://x.test", provider="patria")
    )
    result = validate_document(doc)
    assert result.valid


def test_quality_gate_rejects_unknown_provider():
    doc = normalize(RawDocument("id", "HGRU11", "R", "https://x.test"))
    result = validate_document(doc)
    assert not result.valid
    assert "missing_provider" in result.errors


def test_checkpoint_requires_legacy_suite_green():
    good = OperationalCheckpoint(10, 10, 2, 10, True)
    bad = OperationalCheckpoint(10, 10, 2, 10, False)
    assert good.safe_to_continue
    assert not bad.safe_to_continue
