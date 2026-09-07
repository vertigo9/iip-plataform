from datetime import UTC, date, datetime

from iip_knowledge_bridge.models import (
    Decision,
    DecisionChange,
    Exposure,
    PortfolioSnapshot,
    Position,
    Verdict,
)
from iip_knowledge_bridge.redundancy import find_redundant_exposures
from iip_knowledge_bridge.repository import ObsidianRepository


def test_decision(tmp_path):
    repo = ObsidianRepository(tmp_path)
    d = Decision(
        decision_id="DEC-ITUB4-20260826-001",
        ticker="ITUB4",
        date=date(2026, 8, 26),
        previous_verdict=Verdict.MANTER,
        new_verdict=Verdict.AUMENTAR,
        change_type=DecisionChange.UPGRADE,
        confidence=0.85,
        reasons=["valuation"],
    )
    assert "AUMENTAR" in repo.save_decision(d).read_text()


def test_redundancy():
    r = find_redundant_exposures(
        [
            Exposure(
                ticker="PCIP11",
                factor="credito_imobiliario",
                weight=0.12,
                confidence=0.9,
            ),
            Exposure(
                ticker="VGIP11",
                factor="credito_imobiliario",
                weight=0.11,
                confidence=0.9,
            ),
        ],
        0.20,
    )
    assert abs(r[0]["aggregate_weight"] - 0.23) < 1e-9


def test_snapshot(tmp_path):
    repo = ObsidianRepository(tmp_path)
    s = PortfolioSnapshot(
        snapshot_id="SNAP-20260826",
        created_at=datetime(2026, 8, 26, tzinfo=UTC),
        portfolio_value=100000,
        positions=[
            Position(
                ticker="ITUB4", asset_class="equity", market_value=100000, weight=1
            )
        ],
    )
    assert repo.save_snapshot(s).exists()
