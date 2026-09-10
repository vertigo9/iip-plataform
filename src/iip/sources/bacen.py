"""BACEN SGS (Sistema Gerenciador de Séries Temporais) — target-building
and response parsing for Central Bank reference series (SELIC, CDI,
IPCA and other public series published at
https://dadosabertos.bcb.gov.br).

Deliberately not a ``DocumentProvider`` (see ``.provider``): BACEN
series are macro/reference data, not documents scoped to a single
``AssetRef``/ticker, so ``supports()``/``discover(asset)`` would not
fit — there is no asset to check against. This is a distinct kind of
source: a reference-series provider.

Follows the same request/response split already used for XP Asset:
this module builds the request URL and parses the response
deterministically; it performs no HTTP request itself (see
``.bacen_harvester`` for the transport, mirroring ``.harvester`` for
XP Asset).

Endpoint and series codes verified directly against BACEN's published
dataset pages (dadosabertos.bcb.gov.br), not assumed from memory:
  - https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados
    ?formato=json&dataInicial=DD/MM/AAAA&dataFinal=DD/MM/AAAA
  - Since 26/03/2025, BACEN requires date filters and limits
    date-range queries to 10 years per request.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
_MAX_RANGE_DAYS = 3653  # ~10 years, BACEN's documented limit

# Well-known SGS series codes (verified individually against
# dadosabertos.bcb.gov.br dataset pages).
SELIC = 11   # Taxa Selic, % ao dia
CDI = 12     # Taxa DI/CDI, % ao dia
IPCA = 433   # IPCA, variação mensal %


@dataclass(frozen=True)
class BacenSeriesTarget:
    code: int
    start_date: date
    end_date: date
    url: str


@dataclass(frozen=True)
class BacenSeriesPoint:
    date: date
    value: float


def build_target(code: int, start_date: date, end_date: date) -> BacenSeriesTarget:
    """Build the deterministic request URL for an SGS series."""

    if end_date < start_date:
        raise ValueError("end_date must not be before start_date")
    if (end_date - start_date).days > _MAX_RANGE_DAYS:
        raise ValueError("BACEN limits date-range queries to 10 years")

    url = (
        f"{BASE_URL.format(code=code)}"
        f"?formato=json"
        f"&dataInicial={start_date.strftime('%d/%m/%Y')}"
        f"&dataFinal={end_date.strftime('%d/%m/%Y')}"
    )
    return BacenSeriesTarget(code=code, start_date=start_date, end_date=end_date, url=url)


def parse_series_response(body: bytes) -> tuple[BacenSeriesPoint, ...]:
    """Parse the SGS JSON body (``[{"data": "dd/mm/aaaa", "valor": "x.xx"}, ...]``)."""

    raw = json.loads(body.decode("utf-8"))
    points = []
    for item in raw:
        day, month, year = item["data"].split("/")
        points.append(
            BacenSeriesPoint(
                date=date(int(year), int(month), int(day)),
                value=float(item["valor"]),
            )
        )
    return tuple(points)
