from datetime import date

import pytest

from iip.sources.bacen import (
    CDI,
    IPCA,
    SELIC,
    build_target,
    parse_series_response,
)


def test_build_target_uses_correct_series_codes():
    assert SELIC == 11
    assert CDI == 12
    assert IPCA == 433


def test_build_target_formats_url_with_brazilian_date_format():
    target = build_target(SELIC, date(2026, 1, 1), date(2026, 7, 31))

    assert target.url == (
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados"
        "?formato=json&dataInicial=01/01/2026&dataFinal=31/07/2026"
    )
    assert target.code == SELIC
    assert target.start_date == date(2026, 1, 1)
    assert target.end_date == date(2026, 7, 31)


def test_build_target_rejects_end_before_start():
    with pytest.raises(ValueError):
        build_target(SELIC, date(2026, 7, 31), date(2026, 1, 1))


def test_build_target_rejects_ranges_over_ten_years():
    with pytest.raises(ValueError):
        build_target(IPCA, date(2010, 1, 1), date(2026, 1, 1))


def test_build_target_allows_exactly_ten_years():
    # should not raise
    target = build_target(IPCA, date(2016, 7, 31), date(2026, 7, 31))
    assert target.code == IPCA


def test_parse_series_response_converts_dates_and_values():
    body = (
        b'[{"data":"01/07/2026","valor":"13.75"},'
        b'{"data":"02/07/2026","valor":"13.75"}]'
    )

    points = parse_series_response(body)

    assert len(points) == 2
    assert points[0].date == date(2026, 7, 1)
    assert points[0].value == 13.75
    assert points[1].date == date(2026, 7, 2)


def test_parse_series_response_handles_empty_series():
    assert parse_series_response(b"[]") == ()
