from iip.portfolio.capabilities import Capability, ProviderCapabilities
from iip.portfolio.incremental import IncrementalDocument, IncrementalTracker


def test_capabilities_are_explicit():
    caps = ProviderCapabilities(
        "xp_asset",
        frozenset(
            {
                Capability.DISCOVERY,
                Capability.DOCUMENT_DOWNLOAD,
                Capability.HISTORICAL,
                Capability.INCREMENTAL,
            }
        ),
    )
    assert caps.supports(Capability.HISTORICAL)
    assert not caps.supports(Capability.MARKET_DATA)


def test_incremental_tracker_created_unchanged_updated():
    tracker = IncrementalTracker()
    first = IncrementalDocument("xp_asset:XPML11:2026:1", "hash-a")
    same = IncrementalDocument("xp_asset:XPML11:2026:1", "hash-a")
    changed = IncrementalDocument("xp_asset:XPML11:2026:1", "hash-b")

    assert tracker.remember(first) == "CREATED"
    assert tracker.remember(same) == "UNCHANGED"
    assert tracker.remember(changed) == "UPDATED"


def test_incremental_tracker_is_content_hash_based():
    tracker = IncrementalTracker()
    content = b"xpml11"
    h = tracker.hash_content(content)
    assert len(h) == 64
    assert tracker.remember(IncrementalDocument("id", h)) == "CREATED"
