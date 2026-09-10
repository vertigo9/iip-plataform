"""IBGE — API de Dados Agregados (SIDRA) — target-building and response
parsing for statistical/economic tables published at
https://servicodados.ibge.gov.br/api/docs/agregados.

Much more complex than BACEN's SGS: this API is multidimensional
(agregado/tabela, variável, período, localidade geográfica), not a
single numeric series code. No specific table/variable is hardcoded
here as a "known useful" shortcut — unlike BACEN's SELIC/CDI/IPCA
codes, IBGE table IDs were not independently verifiable with the same
confidence during this audit (the catalog has thousands of tables).
Callers supply the ``agregado``/``variavel``/``periodos``/``localidades``
values explicitly; add a vetted shortcut constant here only after
confirming it live against the real API.

Same request/response split as BACEN and XP Asset: this module builds
the request URL and parses the response deterministically; it performs
no HTTP request itself (see ``.ibge_harvester`` for the transport).

Response shape (SIDRA convention): a list of variable blocks, each with
its own "resultados" (list of classification groups), each containing
"series" — one entry per geographic location, with a "serie" dict
mapping period -> value. Missing/not-applicable values are represented
by IBGE with placeholder strings (commonly "...", "-", "X") rather than
a number; those are parsed as ``None``, never silently coerced to 0.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

BASE_URL = "https://servicodados.ibge.gov.br/api/v3/agregados"

_MISSING_VALUE_MARKERS = {"...", "..", "-", "x", "X", ""}


@dataclass(frozen=True)
class IbgeTarget:
    agregado: int
    variavel: int | None
    periodos: str
    localidades: str
    url: str


@dataclass(frozen=True)
class IbgeDataPoint:
    variavel_id: str
    variavel_nome: str
    unidade: str
    localidade_id: str
    localidade_nome: str
    periodo: str
    value: float | None


def build_target(
    agregado: int,
    variavel: int | None = None,
    *,
    periodos: str = "-6",
    localidades: str = "BR",
) -> IbgeTarget:
    """Build the deterministic request URL for an IBGE aggregate table.

    ``variavel``: omit (``None``) to fetch every variable the table
    exposes — this is the safer default, since guessing a specific
    variable ID for a table you have not inspected can return a server
    error rather than a clean 4xx. Pass an explicit ID only once you
    have confirmed it exists for that table (e.g. via the table's
    ``/metadados`` endpoint).
    ``periodos``: "-6" for the last 6 available periods, "all" for every
    period, or an explicit period/range like "202001-202012" (per the
    IBGE API's own convention).
    ``localidades``: geographic level + location, e.g. "BR" for Brazil,
    or "N6[3550308]" for a specific município by IBGE code.
    """

    if agregado <= 0:
        raise ValueError("agregado must be positive")
    if variavel is not None and variavel <= 0:
        raise ValueError("variavel must be positive")
    if not periodos:
        raise ValueError("periodos must not be empty")
    if not localidades:
        raise ValueError("localidades must not be empty")

    variavel_segment = f"/{variavel}" if variavel is not None else ""
    url = (
        f"{BASE_URL}/{agregado}/periodos/{periodos}/variaveis{variavel_segment}"
        f"?localidades={localidades}"
    )
    return IbgeTarget(
        agregado=agregado,
        variavel=variavel,
        periodos=periodos,
        localidades=localidades,
        url=url,
    )


def _parse_value(raw: str) -> float | None:
    cleaned = raw.strip()
    if cleaned in _MISSING_VALUE_MARKERS:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_agregados_response(body: bytes) -> tuple[IbgeDataPoint, ...]:
    """Flatten the IBGE Agregados JSON into one IbgeDataPoint per
    (localidade, período) pair.
    """

    raw = json.loads(body.decode("utf-8"))
    points: list[IbgeDataPoint] = []

    for variable_block in raw:
        variavel_id = str(variable_block.get("id", ""))
        variavel_nome = str(variable_block.get("variavel", ""))
        unidade = str(variable_block.get("unidade", ""))

        for resultado in variable_block.get("resultados", []):
            for serie_entry in resultado.get("series", []):
                localidade = serie_entry.get("localidade", {})
                localidade_id = str(localidade.get("id", ""))
                localidade_nome = str(localidade.get("nome", ""))
                for periodo, valor in serie_entry.get("serie", {}).items():
                    points.append(
                        IbgeDataPoint(
                            variavel_id=variavel_id,
                            variavel_nome=variavel_nome,
                            unidade=unidade,
                            localidade_id=localidade_id,
                            localidade_nome=localidade_nome,
                            periodo=periodo,
                            value=_parse_value(str(valor)),
                        )
                    )

    return tuple(points)
