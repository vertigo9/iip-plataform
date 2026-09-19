"""Testes unitários para o atualizador individual de notas de ativos no Obsidian."""

import tempfile

from iip.obsidian.asset_updater import update_asset_note


def test_update_asset_note_creates_and_preserves():
    with tempfile.TemporaryDirectory() as tmpdir:
        metrics = {
            "SPOT_PRICE_BRL": 160.50,
            "FX_RATE": 1.0,
            "CURRENCY": "BRL",
            "dividend_yield_ttm": 0.09,
            "monthly_payout_brl": 1.20,
        }
        verdict = {"score": 8.5, "verdict": "COMPRAR", "confidence": 0.95}

        note_path = update_asset_note(
            vault_path=tmpdir,
            ticker="HGLG11",
            asset_class="FII",
            metrics=metrics,
            verdict_data=verdict,
        )

        assert note_path.exists()
        content = note_path.read_text(encoding="utf-8")
        assert "ticker: HGLG11" in content
        assert "verdict: COMPRAR" in content
        assert "<!-- IIP:BEGIN:METRICS -->" in content
        assert "Preço Spot (BRL):** R$ 160.50" in content
