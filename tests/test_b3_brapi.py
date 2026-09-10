import json

import pytest

from iip.sources.b3_brapi import build_target, parse_quote_response


def test_build_target_formats_url_with_uppercase_symbols():
    target = build_target(("petr4", "vale3"))

    assert target.url == "https://brapi.dev/api/quote/PETR4,VALE3"
    assert target.symbols == ("PETR4", "VALE3")


def test_build_target_single_symbol():
    target = build_target(("mxrf11",))
    assert target.url == "https://brapi.dev/api/quote/MXRF11"


def test_build_target_mixes_stock_and_fii_in_one_call():
    target = build_target(("petr4", "mxrf11"))
    assert target.url == "https://brapi.dev/api/quote/PETR4,MXRF11"


def test_build_target_rejects_empty_symbols_tuple():
    with pytest.raises(ValueError):
        build_target(())


def test_build_target_rejects_blank_ticker():
    with pytest.raises(ValueError):
        build_target(("petr4", "  "))


def test_build_target_never_embeds_a_token():
    target = build_target(("petr4",))
    assert "token" not in target.url.lower()


def make_response(**overrides):
    result = {
        "symbol": "PETR4",
        "shortName": "PETROBRAS PN",
        "currency": "BRL",
        "regularMarketPrice": 38.42,
        "regularMarketChangePercent": 1.25,
    }
    result.update(overrides)
    return json.dumps({"results": [result]}).encode("utf-8")


def test_parse_quote_response_extracts_expected_fields():
    quotes = parse_quote_response(make_response())

    assert len(quotes) == 1
    quote = quotes[0]
    assert quote.symbol == "PETR4"
    assert quote.short_name == "PETROBRAS PN"
    assert quote.currency == "BRL"
    assert quote.regular_market_price == 38.42
    assert quote.regular_market_change_percent == 1.25


def test_parse_quote_response_handles_missing_price_as_none():
    quotes = parse_quote_response(make_response(regularMarketPrice=None))
    assert quotes[0].regular_market_price is None


def test_parse_quote_response_handles_garbage_price_as_none():
    quotes = parse_quote_response(make_response(regularMarketPrice="n/a"))
    assert quotes[0].regular_market_price is None


def test_parse_quote_response_handles_empty_results():
    body = json.dumps({"results": []}).encode("utf-8")
    assert parse_quote_response(body) == ()


def test_parse_quote_response_handles_multiple_tickers():
    body = json.dumps(
        {
            "results": [
                {"symbol": "PETR4", "regularMarketPrice": 38.42},
                {"symbol": "VALE3", "regularMarketPrice": 61.10},
            ]
        }
    ).encode("utf-8")

    quotes = parse_quote_response(body)

    assert len(quotes) == 2
    assert {q.symbol for q in quotes} == {"PETR4", "VALE3"}
