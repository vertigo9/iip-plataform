import json

import pytest

from iip.sources.b3_bolsai import (
    build_fii_target,
    build_target,
    parse_fii_response,
    parse_fundamentals_response,
)


def test_build_target_formats_url_with_uppercase_ticker():
    target = build_target("petr4")

    assert target.url == "https://api.usebolsai.com/api/v1/fundamentals/PETR4"
    assert target.ticker == "PETR4"


def test_build_fii_target_uses_the_fiis_endpoint():
    target = build_fii_target("mxrf11")

    assert target.url == "https://api.usebolsai.com/api/v1/fiis/MXRF11"
    assert target.ticker == "MXRF11"


def test_build_target_rejects_empty_ticker():
    with pytest.raises(ValueError):
        build_target("")


def test_build_fii_target_rejects_empty_ticker():
    with pytest.raises(ValueError):
        build_fii_target("")


def test_build_target_rejects_blank_ticker():
    with pytest.raises(ValueError):
        build_target("   ")


def test_build_target_never_embeds_a_key():
    target = build_target("petr4")
    assert "key" not in target.url.lower()


def test_build_fii_target_never_embeds_a_key():
    target = build_fii_target("mxrf11")
    assert "key" not in target.url.lower()


def make_response(**overrides):
    result = {
        "ticker": "PETR4",
        "close_price": 45.67,
        "market_cap": 588628425194.87,
        "pl": 5.32,
        "pvp": 1.42,
        "ev_ebitda": 3.27,
        "roe": 26.6,
        "roic": 18.4,
        "net_margin": 22.23,
        "gross_margin": 50.7,
        "dividend_yield": 7.1,
        "net_debt_ebitda": 0.94,
        "lpa": 8.58,
        "vpa": 32.15,
        "ebitda": 281630000,
    }
    result.update(overrides)
    return json.dumps(result).encode("utf-8")


def test_parse_fundamentals_response_extracts_all_fields():
    fundamentals = parse_fundamentals_response(make_response())

    assert fundamentals.ticker == "PETR4"
    assert fundamentals.close_price == 45.67
    assert fundamentals.pl == 5.32
    assert fundamentals.pvp == 1.42
    assert fundamentals.dividend_yield == 7.1
    assert fundamentals.roe == 26.6
    assert fundamentals.ebitda == 281630000


def test_parse_fundamentals_response_handles_missing_field_as_none():
    fundamentals = parse_fundamentals_response(make_response(pl=None))
    assert fundamentals.pl is None


def test_parse_fundamentals_response_handles_garbage_value_as_none():
    fundamentals = parse_fundamentals_response(make_response(pvp="n/a"))
    assert fundamentals.pvp is None


def test_parse_fundamentals_response_is_a_single_object_not_a_list():
    # bolsai returns one object per ticker, unlike brapi's {"results": [...]}
    body = make_response()
    fundamentals = parse_fundamentals_response(body)
    assert fundamentals.ticker == "PETR4"


def make_fii_response(**overrides):
    # Shape confirmed from bolsai's own published docs example (HGLG11).
    result = {
        "ticker": "HGLG11",
        "name": "CSHG LOGISTICA FDO INV IMOB - FII",
        "reference_date": "2026-02-28",
        "close_price": 162.45,
        "book_value_per_share": 148.32,
        "pvp": 1.10,
        "dividend_yield_ttm": 8.74,
        "net_asset_value": 4523000000.0,
        "shares_outstanding": 30498200,
        "total_shareholders": 487523,
        "segment": "Logistica",
        "management_type": "Gestao Ativa",
    }
    result.update(overrides)
    return json.dumps(result).encode("utf-8")


def test_parse_fii_response_extracts_all_fields():
    fii = parse_fii_response(make_fii_response())

    assert fii.ticker == "HGLG11"
    assert fii.name == "CSHG LOGISTICA FDO INV IMOB - FII"
    assert fii.close_price == 162.45
    assert fii.pvp == 1.10
    assert fii.dividend_yield_ttm == 8.74
    assert fii.net_asset_value == 4523000000.0
    assert fii.total_shareholders == 487523
    assert fii.segment == "Logistica"


def test_parse_fii_response_has_no_pl_field():
    # P/L doesn't apply to FIIs; BolsaiFiiData must not carry it.
    fii = parse_fii_response(make_fii_response())
    assert not hasattr(fii, "pl")


def test_parse_fii_response_handles_missing_field_as_none():
    fii = parse_fii_response(make_fii_response(dividend_yield_ttm=None))
    assert fii.dividend_yield_ttm is None


def test_parse_fii_response_handles_garbage_value_as_none():
    fii = parse_fii_response(make_fii_response(pvp="n/a"))
    assert fii.pvp is None
