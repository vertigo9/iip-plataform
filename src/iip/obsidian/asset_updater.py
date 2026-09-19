"""Módulo de atualização cirúrgica e idempotente das notas individuais de ativos no Obsidian."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def update_asset_note(
    vault_path: Path | str,
    ticker: str,
    asset_class: str,
    metrics: dict[str, Any],
    verdict_data: dict[str, Any] | None = None,
) -> Path:
    """Sincroniza metadados e blocos de decisão na nota individual do ativo no Obsidian Vault."""
    vault = Path(vault_path)
    asset_dir = vault / "01 - Portfolio/Assets"
    asset_dir.mkdir(parents=True, exist_ok=True)

    ticker_upper = ticker.upper()
    note_path = asset_dir / f"{ticker_upper}.md"
    verdict_data = verdict_data or {}

    frontmatter = (
        f"---\n"
        f"ticker: {ticker_upper}\n"
        f"asset_class: {asset_class.upper()}\n"
        f"score: {verdict_data.get('score', 'N/A')}\n"
        f"verdict: {verdict_data.get('verdict', 'AGUARDAR')}\n"
        f"confidence: {verdict_data.get('confidence', 0.0)}\n"
        f"currency: {metrics.get('CURRENCY', 'BRL')}\n"
        f"spot_price_brl: {metrics.get('SPOT_PRICE_BRL', 0.0)}\n"
        f"dividend_yield_ttm: {metrics.get('dividend_yield_ttm', 0.0)}\n"
        f"monthly_payout_brl: {metrics.get('monthly_payout_brl', 0.0)}\n"
        f"tags:\n"
        f"  - iip/asset\n"
        f"  - iip/{asset_class.lower()}\n"
        f"---"
    )

    metrics_block = (
        "<!-- IIP:BEGIN:METRICS -->\n"
        f"### 📊 Métricas Consolidadas ({ticker_upper})\n"
        f"- **Preço Spot (BRL):** R$ {metrics.get('SPOT_PRICE_BRL', 0.0):.2f}\n"
        f"- **Câmbio Aplicado (FX):** {metrics.get('FX_RATE', 1.0):.2f}\n"
        f"- **Dividend Yield TTM:** {metrics.get('dividend_yield_ttm', 0.0) * 100:.2f}%\n"
        f"- **Projeção Mensal Estimada:** R$ {metrics.get('monthly_payout_brl', 0.0):.2f}\n"
        "<!-- IIP:END:METRICS -->"
    )

    if note_path.exists():
        existing_content = note_path.read_text(encoding="utf-8")

        if existing_content.startswith("---"):
            parts = existing_content.split("---", 2)
            body = parts[2].lstrip("\n") if len(parts) >= 3 else existing_content
        else:
            body = existing_content

        pattern = r"<!-- IIP:BEGIN:METRICS -->.*?<!-- IIP:END:METRICS -->"
        if re.search(pattern, body, flags=re.DOTALL):
            new_body = re.sub(pattern, metrics_block, body, flags=re.DOTALL)
        else:
            new_body = f"{body.rstrip()}\n\n{metrics_block}\n"

        full_content = f"{frontmatter}\n\n{new_body}"
    else:
        full_content = f"{frontmatter}\n\n# 🟢 {ticker_upper} — Ficha do Ativo\n\n{metrics_block}\n"

    note_path.write_text(full_content, encoding="utf-8")
    logger.info("Nota do ativo %s atualizada em: %s", ticker_upper, note_path)
    return note_path
