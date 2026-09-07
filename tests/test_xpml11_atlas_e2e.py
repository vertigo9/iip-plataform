from __future__ import annotations

from iip.atlas import AtlasIngestionReport, XPAssetAtlasPipeline
from iip.sources.harvester import XPAssetHTTPHarvester
from iip.sources.registry import AssetRef, SourceRef

XPML11_URL = "https://www.xpasset.com.br/fundos/xp-malls/"


class FakeResponse:
    status = 200

    def __init__(self, body: bytes, url: str = XPML11_URL):
        self.headers = {"Content-Type": "application/pdf; charset=binary"}
        self._body = body
        self._url = url

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._url


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
                url=XPML11_URL,
                active=True,
            ),
        ),
    )


def make_harvester() -> XPAssetHTTPHarvester:
    def opener(request, timeout):
        return FakeResponse(b"%PDF-XPML11-2026")

    return XPAssetHTTPHarvester(opener)


def test_pipeline_returns_typed_report():
    report = XPAssetAtlasPipeline(harvester=make_harvester()).ingest(
        make_asset(), range(2026, 2027)
    )

    assert isinstance(report, AtlasIngestionReport)
    assert len(report.targets) == 1
    assert len(report.fetched) == 1
    assert len(report.documents) == 1


def test_pipeline_connects_all_three_layers():
    report = XPAssetAtlasPipeline(harvester=make_harvester()).ingest(
        make_asset(), range(2026, 2027)
    )

    assert report.targets[0].ticker == "XPML11"
    assert report.fetched[0].target == report.targets[0]
    assert report.documents[0].ticker == "XPML11"
    assert report.documents[0].provider == "xp_asset"
    assert report.documents[0].content_type == "application/pdf"


def test_pipeline_preserves_document_identity_for_same_payload():
    pipeline = XPAssetAtlasPipeline(harvester=make_harvester())

    first = pipeline.ingest(make_asset(), range(2026, 2027))
    second = pipeline.ingest(make_asset(), range(2026, 2027))

    assert first.documents[0].document_id == second.documents[0].document_id
    assert first.documents[0].content_hash == second.documents[0].content_hash


def test_pipeline_produces_one_document_per_discovered_target():
    pipeline = XPAssetAtlasPipeline(harvester=make_harvester())

    report = pipeline.ingest(make_asset(), range(2024, 2027))

    assert [doc.discovered_year for doc in report.documents] == [2024, 2025, 2026]
    assert len(report.targets) == len(report.fetched) == len(report.documents) == 3


def test_pipeline_keeps_target_order():
    pipeline = XPAssetAtlasPipeline(harvester=make_harvester())

    report = pipeline.ingest(make_asset(), range(2024, 2027))

    assert [target.year for target in report.targets] == [2024, 2025, 2026]
    assert [doc.discovered_year for doc in report.documents] == [2024, 2025, 2026]


def test_pipeline_does_not_modify_source_asset():
    asset = make_asset()

    XPAssetAtlasPipeline(harvester=make_harvester()).ingest(asset, range(2026, 2027))

    assert asset.ticker == "XPML11"
    assert asset.manager == "XP Asset"
    assert asset.sources[0].active is True
