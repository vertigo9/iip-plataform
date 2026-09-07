import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from iip.intelligence.metric_identity import (
    IdentityClassification,
    IdentityStatus,
    SourceContext,
    resolve_identity,
)


class MetricIdentityTests(unittest.TestCase):
    def base(self, **overrides):
        values = dict(
            canonical_ticker="PCIP11",
            original_ticker="CVBI11",
            metric_name="market_price_per_share",
            value_raw="78,18",
            value_parsed="78.18",
            unit="BRL/share",
            scale="1",
            period="2025-01",
            document_hash="a" * 64,
            document_id="historical_document:test",
            lineage="CVBI11 -> PCIP11",
            contexts=[],
        )
        values.update(overrides)
        return values

    def test_exact_duplicate_is_deduplicable(self):
        result = resolve_identity(
            **self.base(
                sibling_values=["78.18"],
                duplicate_count=2,
            )
        )
        self.assertEqual(result.classification, IdentityClassification.EXACT_DUPLICATE)
        self.assertEqual(result.status, IdentityStatus.DEDUPLICABLE)

    def test_distinct_values_do_not_share_identity(self):
        context = SourceContext("Dividend Yield Anualizado pelo valor do mercado 13,4%")
        result = resolve_identity(
            **self.base(
                metric_name="dividend_yield_annualized",
                value_raw="13,4",
                value_parsed="13.4",
                unit="percent",
                period="2024-01",
                sibling_values=["13.4", "13.09"],
                contexts=[context],
            )
        )
        self.assertEqual(
            result.classification,
            IdentityClassification.SEMANTICALLY_DISTINCT,
        )
        self.assertEqual(
            result.semantic_dimension,
            "MARKET_VALUE",
        )
        self.assertEqual(
            result.status,
            IdentityStatus.READY_WITH_DIMENSION,
        )

    def test_unresolved_semantic_context_is_blocked_for_distinct_values(self):
        result = resolve_identity(
            **self.base(
                metric_name="dividend_yield_annualized",
                value_raw="13,09",
                value_parsed="13.09",
                unit="percent",
                period="2024-01",
                sibling_values=["13.4", "13.09"],
                contexts=[],
            )
        )
        self.assertEqual(result.status, IdentityStatus.BLOCKED)
        self.assertIsNone(result.semantic_dimension)

    def test_lineage_is_preserved(self):
        result = resolve_identity(**self.base())
        self.assertEqual(result.identity.original_ticker, "CVBI11")
        self.assertEqual(result.identity.canonical_ticker, "PCIP11")
        self.assertEqual(result.identity.lineage, "CVBI11 -> PCIP11")

    def test_legacy_and_resolved_periods_are_not_part_of_identity_object(self):
        # The persistence contract receives the already-resolved period.
        # Legacy period is a separate provenance field in the CSV layer.
        result = resolve_identity(**self.base(period="2025-01"))
        self.assertEqual(result.identity.period, "2025-01")


if __name__ == "__main__":
    unittest.main()
