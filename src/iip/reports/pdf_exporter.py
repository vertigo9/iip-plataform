"""Módulo de exportação de relatórios consolidados em HTML/PDF para o IIP Engine."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def generate_html_report(
    assets_summary: list[dict[str, Any]],
    output_path: Path | str,
) -> Path:
    """Gera um relatório HTML consolidado e formatado do portfólio."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    now_str = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")

    rows = []
    for asset in assets_summary:
        ticker = asset.get("ticker", "N/A")
        asset_class = asset.get("asset_class", "N/A")
        spot_brl = asset.get("spot_price_brl", 0.0)
        score = asset.get("score", "N/A")
        verdict = asset.get("verdict", "AGUARDAR")

        rows.append(
            f"<tr>"
            f"<td><strong>{ticker}</strong></td>"
            f"<td>{asset_class}</td>"
            f"<td>R$ {spot_brl:.2f}</td>"
            f"<td>{score}</td>"
            f"<td><span class='badge verdict-{verdict.lower()}'>{verdict}</span></td>"
            f"</tr>"
        )

    table_body = "\n".join(rows)

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Relatório Consolidado do Portfólio - IIP Engine</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 40px; color: #333; }}
        h1 {{ color: #1a202c; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }}
        .meta {{ color: #718096; font-size: 0.9em; margin-bottom: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
        th {{ background-color: #f7fafc; color: #4a5568; font-weight: 600; }}
        tr:hover {{ background-color: #f8fafc; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em; }}
        .verdict-comprar {{ background-color: #c6f6d5; color: #22543d; }}
        .verdict-manter {{ background-color: #feebc8; color: #744210; }}
        .verdict-reduzir {{ background-color: #fed7d7; color: #742a2a; }}
        .verdict-aguardar {{ background-color: #e2e8f0; color: #4a5568; }}
    </style>
</head>
<body>
    <h1>📊 IIP Engine — Relatório Consolidado do Portfólio</h1>
    <div class="meta">Gerado em: {now_str} | Versão da Plataforma: v1.2.1</div>

    <table>
        <thead>
            <tr>
                <th>Ativo</th>
                <th>Classe</th>
                <th>Preço Spot (BRL)</th>
                <th>Score</th>
                <th>Veredito</th>
            </tr>
        </thead>
        <tbody>
            {table_body}
        </tbody>
    </table>
</body>
</html>
"""

    out_file.write_text(html_content, encoding="utf-8")
    logger.info("Relatório HTML consolidado gerado em: %s", out_file)
    return out_file
