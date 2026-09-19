"""Testes unitários para o gateway de integração B3."""

from iip.data.b3_gateway import B3Gateway, B3Position


def test_fetch_user_positions_returns_structured_data():
    gateway = B3Gateway()
    positions = gateway.fetch_user_positions("12345678900")

    assert isinstance(positions, list)
    assert len(positions) > 0

    first = positions[0]
    assert isinstance(first, B3Position)
    assert first.ticker == "HGLG11"
    assert isinstance(first.quantity, float)
    assert isinstance(first.total_value_brl, float)
    assert first.quantity == 100.0
