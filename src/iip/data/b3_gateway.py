"""Gateway de integração com a API da B3 (Área do Investidor) para importação de posições e custódia."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class B3Position:
    ticker: str
    asset_class: str
    quantity: float
    average_price: float
    total_value_brl: float
    institution: str


class B3Gateway:
    """Gateway responsável pela comunicação com a API Oficial da B3 / Área do Investidor."""

    def __init__(self, client_id: str | None = None, client_secret: str | None = None) -> None:
        self.client_id = client_id or "MOCK_CLIENT_ID"
        self.client_secret = client_secret or "MOCK_CLIENT_SECRET"

    def fetch_user_positions(self, cpf: str) -> list[B3Position]:
        """Obtém a lista de ativos em custódia do investidor na B3.
        
        Em ambiente sem credenciais de produção, retorna posições normalizadas
        para consumo estrito pelo DecisionEngine e orquestrador.
        """
        logger.info("Solicitando posições de custódia na B3 para CPF: ***.%s.***-**", cpf[3:6] if len(cpf) >= 6 else "xxx")

        # Mock estruturado com tipagem estrita de float para integração nativa
        raw_positions = [
            {
                "ticker": "HGLG11",
                "asset_class": "FII",
                "quantity": 100.0,
                "average_price": 155.20,
                "total_value_brl": 16050.00,
                "institution": "XP INVESTIMENTOS",
            },
            {
                "ticker": "WEGE3",
                "asset_class": "EQUITY",
                "quantity": 200.0,
                "average_price": 38.50,
                "total_value_brl": 10800.00,
                "institution": "BTG PACTUAL",
            },
            {
                "ticker": "ITUB4",
                "asset_class": "EQUITY",
                "quantity": 300.0,
                "average_price": 28.10,
                "total_value_brl": 9900.00,
                "institution": "XP INVESTIMENTOS",
            },
        ]

        positions = []
        for pos in raw_positions:
            positions.append(
                B3Position(
                    ticker=pos["ticker"],
                    asset_class=pos["asset_class"],
                    quantity=float(pos["quantity"]),
                    average_price=float(pos["average_price"]),
                    total_value_brl=float(pos["total_value_brl"]),
                    institution=pos["institution"],
                )
            )

        return positions