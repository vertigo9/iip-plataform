import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from iip.intelligence.metric_identity import MetricObservationIdentity
from iip.intelligence.metric_persistence import (
    build_knowledge_evidence,
    knowledge_evidence_id,
    metric_evidence_id,
)


class MetricPersistenceTests(unittest.TestCase):
    def observation(self, **overrides):
        values = {
            "canonical_ticker": "PCIP11",
            "original_ticker": "CVBI11",
            "metric_name": "dividend_yield_annualized",
            "value": "13.4",
            "unit": "percent",
            "scale": "1",
            "period": "2024-01",
            "semantic_dimension": "MARKET_VALUE",
            "document_hash": "b" * 64,
            "document_id": "historical_document:test",
            "source_locator": "page=6",
            "lineage": "CVBI11 -> PCIP11",
        }
        values.update(overrides)
        return MetricObservationIdentity(**values)

    def test_metric_id_is_stable(self):
        a = metric_evidence_id(self.observation())
        b = metric_evidence_id(self.observation())
        self.assertEqual(a, b)

    def test_semantic_dimension_changes_metric_id(self):
        market = metric_evidence_id(self.observation(semantic_dimension="MARKET_VALUE"))
        nav = metric_evidence_id(self.observation(semantic_dimension="NAV"))
        self.assertNotEqual(market, nav)

    def test_value_changes_metric_id(self):
        a = metric_evidence_id(self.observation(value="13.4"))
        b = metric_evidence_id(self.observation(value="13.09"))
        self.assertNotEqual(a, b)

    def test_knowledge_id_derives_from_metric_id(self):
        metric_id = metric_evidence_id(self.observation())
        evidence = knowledge_evidence_id(metric_id)
        self.assertTrue(evidence.startswith("evidence:metric:"))

    def test_knowledge_evidence_preserves_provenance(self):
        observation = self.observation()
        evidence = build_knowledge_evidence(
            observation,
            title="CVBI11 - Relatório Mensal de Gestão - Janeiro 2024.pdf",
        )
        self.assertEqual(evidence.ticker, "PCIP11")
        self.assertEqual(evidence.document_hash, "b" * 64)
        self.assertEqual(evidence.date, date(2024, 1, 1))
        self.assertEqual(
            evidence.relevant_facts["original_ticker"],
            "CVBI11",
        )
        self.assertEqual(
            evidence.relevant_facts["semantic_dimension"],
            "MARKET_VALUE",
        )


if __name__ == "__main__":
    unittest.main()
