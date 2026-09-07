import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from iip.intelligence.metric_persistence_adapter import SimulatedKnowledgeBridgeAdapter


class FakeEvidence:
    def __init__(self, evidence_id):
        self.evidence_id = evidence_id


class PersistenceContractTests(unittest.TestCase):
    def test_simulated_bridge_is_idempotent(self):
        bridge = SimulatedKnowledgeBridgeAdapter()
        evidence = FakeEvidence("evidence:metric:test")

        bridge.persist_evidence(evidence)
        bridge.persist_evidence(evidence)

        self.assertEqual(bridge.size, 1)

    def test_projection_does_not_create_second_persisted_evidence(self):
        bridge = SimulatedKnowledgeBridgeAdapter()
        evidence = FakeEvidence("evidence:metric:test")

        bridge.persist_evidence(evidence)
        bridge.sync_evidence_projection(evidence)
        bridge.sync_evidence_projection(evidence)

        self.assertEqual(bridge.size, 1)
        self.assertEqual(len(bridge.projections), 1)

    def test_no_files_are_written_by_fake_bridge(self):
        bridge = SimulatedKnowledgeBridgeAdapter()
        self.assertEqual(bridge.size, 0)
        self.assertEqual(len(bridge.projections), 0)


if __name__ == "__main__":
    unittest.main()
