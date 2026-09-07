from __future__ import annotations

from pathlib import Path

from iip.atlas.full_pipeline import FullIngestionReport, XPAssetKnowledgePipeline
from iip.atlas.knowledge_adapter import AtlasKnowledgeAdapter
from iip.atlas.pipeline import XPAssetAtlasPipeline
from iip.knowledge.bridge import KnowledgeBridge
from iip.sources.harvester import XPAssetHTTPHarvester
from iip.sources.registry import AssetRef, SourceRef

URL = "https://www.xpasset.com.br/fundos/xp-malls/"


class FakeResponse:
    status = 200

    def __init__(self, body: bytes):
        self.headers = {"Content-Type": "application/pdf; charset=binary"}
        self._body = body

    def read(self):
        return self._body

    def geturl(self):
        return URL


def make_asset() -> AssetRef:
    return AssetRef(
        ticker="XPML11",
        asset_class="FII",
        asset_subtype="Tijolo",
        segment="Shopping",
        manager="XP Asset",
        sources=(
            SourceRef(
                provider="xp_asset",
                role="institutional_primary",
                priority=1,
                url=URL,
                active=True,
            ),
        ),
    )


def make_atlas_pipeline() -> XPAssetAtlasPipeline:
    def opener(request, timeout):
        return FakeResponse(b"%PDF-XPML11-FULL-E2E")

    return XPAssetAtlasPipeline(harvester=XPAssetHTTPHarvester(opener))


def test_full_pipeline_persists_into_knowledge_bridge(tmp_path: Path):
    bridge = KnowledgeBridge(tmp_path / "vault")
    knowledge = AtlasKnowledgeAdapter(bridge)
    pipeline = XPAssetKnowledgePipeline(
        atlas_pipeline=make_atlas_pipeline(),
        knowledge_adapter=knowledge,
    )

    result = pipeline.ingest(make_asset(), range(2026, 2027))

    assert isinstance(result, FullIngestionReport)
    assert len(result.atlas_report.documents) == 1
    assert len(result.knowledge_results) == 1


def test_full_pipeline_returns_projection_result(tmp_path: Path):
    bridge = KnowledgeBridge(tmp_path / "vault")
    pipeline = XPAssetKnowledgePipeline(
        atlas_pipeline=make_atlas_pipeline(),
        knowledge_adapter=AtlasKnowledgeAdapter(bridge),
    )

    result = pipeline.ingest(make_asset(), range(2026, 2027))

    sync_result = result.knowledge_results[0]
    assert sync_result.status.value == "CREATED"


def test_second_run_is_idempotent(tmp_path: Path):
    bridge = KnowledgeBridge(tmp_path / "vault")
    pipeline = XPAssetKnowledgePipeline(
        atlas_pipeline=make_atlas_pipeline(),
        knowledge_adapter=AtlasKnowledgeAdapter(bridge),
    )

    first = pipeline.ingest(make_asset(), range(2026, 2027))
    second = pipeline.ingest(make_asset(), range(2026, 2027))

    assert first.knowledge_results[0].status.value == "CREATED"
    assert second.knowledge_results[0].status.value == "UNCHANGED"


def test_different_content_updates_projection(tmp_path: Path):
    body = {"value": b"%PDF-A"}

    def opener(request, timeout):
        return FakeResponse(body["value"])

    atlas = XPAssetAtlasPipeline(harvester=XPAssetHTTPHarvester(opener))
    bridge = KnowledgeBridge(tmp_path / "vault")
    pipeline = XPAssetKnowledgePipeline(
        atlas_pipeline=atlas,
        knowledge_adapter=AtlasKnowledgeAdapter(bridge),
    )

    first = pipeline.ingest(make_asset(), range(2026, 2027))

    body["value"] = b"%PDF-B"
    second = pipeline.ingest(make_asset(), range(2026, 2027))

    assert first.knowledge_results[0].status.value == "CREATED"
    assert second.knowledge_results[0].status.value == "UPDATED"


def test_multiple_years_preserve_order(tmp_path: Path):
    bridge = KnowledgeBridge(tmp_path / "vault")
    pipeline = XPAssetKnowledgePipeline(
        atlas_pipeline=make_atlas_pipeline(),
        knowledge_adapter=AtlasKnowledgeAdapter(bridge),
    )

    result = pipeline.ingest(make_asset(), range(2024, 2027))

    assert [doc.discovered_year for doc in result.atlas_report.documents] == [
        2024,
        2025,
        2026,
    ]
    assert len(result.knowledge_results) == 3


def test_source_metadata_survives_end_to_end(tmp_path: Path):
    bridge = KnowledgeBridge(tmp_path / "vault")
    pipeline = XPAssetKnowledgePipeline(
        atlas_pipeline=make_atlas_pipeline(),
        knowledge_adapter=AtlasKnowledgeAdapter(bridge),
    )

    result = pipeline.ingest(make_asset(), range(2026, 2027))
    document = result.atlas_report.documents[0]

    assert document.ticker == "XPML11"
    assert document.provider == "xp_asset"
    assert document.role == "institutional_primary"
    assert document.final_url == URL
