"""Receita Federal CNPJ lookup via BrasilAPI.

Audit finding: the Receita Federal itself has no free public REST API
for individual CNPJ lookups (confirmed by an independent comparison
source, not assumed). What exists is the open-data bulk CNPJ registry
(monthly files), which third parties process and expose as APIs —
BrasilAPI, minhaReceita, ReceitaWS, CNPJá. Per the same discipline
applied to B3 (brapi.dev/bolsai), this is a third-party channel, not
Receita Federal directly.

Chosen: BrasilAPI (https://brasilapi.com.br/api/cnpj/v1/{cnpj}) — open
source, free, no signup/token required, no published rate limit
(abuse-blocked only). This differs from the CNPJ-dedicated services
(ReceitaWS: 3 req/min free, CNPJá: 5 req/min free), which all require
signup.

Known reliability caveat (a real, documented BrasilAPI issue, not
speculation): the underlying data can lag the live Receita Federal
registry — a company registered since March/2021 was reported "not
found" well after that date. Treat a 404 as "not found in this
snapshot", not proof a CNPJ is invalid or unregistered.

Same request/response split as the other sources: this module builds
the request URL and parses the response; it performs no HTTP request
itself (see ``.receita_federal_harvester`` for the transport).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

BASE_URL = "https://brasilapi.com.br/api/cnpj/v1"


@dataclass(frozen=True)
class CnpjTarget:
    cnpj: str
    url: str


@dataclass(frozen=True)
class CnaeSecundario:
    codigo: int | None
    descricao: str | None


@dataclass(frozen=True)
class CnpjRecord:
    cnpj: str
    razao_social: str | None
    nome_fantasia: str | None
    situacao_cadastral: str | None
    natureza_juridica: str | None
    porte: str | None
    capital_social: float | None
    data_inicio_atividade: str | None
    cnae_fiscal: int | None
    cnae_fiscal_descricao: str | None
    cnaes_secundarios: tuple[CnaeSecundario, ...]
    logradouro: str | None
    numero: str | None
    bairro: str | None
    municipio: str | None
    uf: str | None
    cep: str | None
    email: str | None
    ddd_telefone_1: str | None
    opcao_pelo_mei: bool | None


def _normalize_cnpj(cnpj: str) -> str:
    digits = re.sub(r"\D", "", cnpj)
    if len(digits) != 14:
        raise ValueError(f"CNPJ must have 14 digits, got {len(digits)}: {cnpj!r}")
    return digits


def build_target(cnpj: str) -> CnpjTarget:
    """Build the request URL for a CNPJ lookup. Accepts the CNPJ with
    or without punctuation (dots, slash, dash) — normalizes to 14
    digits before building the URL.
    """

    normalized = _normalize_cnpj(cnpj)
    url = f"{BASE_URL}/{normalized}"
    return CnpjTarget(cnpj=normalized, url=url)


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_cnpj_response(body: bytes) -> CnpjRecord:
    raw = json.loads(body.decode("utf-8"))

    secundarios = tuple(
        CnaeSecundario(
            codigo=item.get("codigo") if isinstance(item.get("codigo"), int) else None,
            descricao=item.get("descricao"),
        )
        for item in raw.get("cnaes_secundarios", []) or []
    )

    return CnpjRecord(
        cnpj=str(raw.get("cnpj", "")),
        razao_social=raw.get("razao_social"),
        nome_fantasia=raw.get("nome_fantasia") or None,
        situacao_cadastral=raw.get("descricao_situacao_cadastral"),
        natureza_juridica=raw.get("natureza_juridica"),
        porte=raw.get("porte") or raw.get("descricao_porte"),
        capital_social=_as_float(raw.get("capital_social")),
        data_inicio_atividade=raw.get("data_inicio_atividade"),
        cnae_fiscal=raw.get("cnae_fiscal")
        if isinstance(raw.get("cnae_fiscal"), int)
        else None,
        cnae_fiscal_descricao=raw.get("cnae_fiscal_descricao"),
        cnaes_secundarios=secundarios,
        logradouro=raw.get("logradouro"),
        numero=raw.get("numero"),
        bairro=raw.get("bairro"),
        municipio=raw.get("municipio"),
        uf=raw.get("uf"),
        cep=raw.get("cep"),
        email=raw.get("email") or None,
        ddd_telefone_1=raw.get("ddd_telefone_1") or None,
        opcao_pelo_mei=raw.get("opcao_pelo_mei"),
    )
