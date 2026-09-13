"""Testes unitários para o gerador de relatórios consolidados em HTML/PDF."""

import tempfile
from pathlib import Path

from iip.reports.pdf_exporter import generate_html_report


def test_generate_html_report_creates_file():
    summary = [
        {"ticker": "HGLG11", "asset_class": "FII", "spot_price_brl": 160.50, "score": 8.5, "verdict": "COMPRAR"},
        {"ticker": "AAPL", "asset_class": "STOCKS", "spot_price_brl": 900.00, "score": 7.0, "verdict": "REDUZIR"},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "relatorio.html"
        generated = generate_html_report(summary, out_path)

        assert generated.exists()
        content = generated.read_text(encoding="utf-8")
        assert "HGLG11" in content
        assert "AAPL" in content
        assert "COMPRAR" in content
        assert "REDUZIR" in content