"""Testes unitários para o gerador de alertas de rebalanceamento."""

from iip.orchestration.rebalancing_alerts import generate_rebalancing_alerts


def test_generate_rebalancing_alerts():
    current = {"FII": 0.40, "EQUITY": 0.50, "FIXED_INCOME": 0.10}
    target = {"FII": 0.30, "EQUITY": 0.40, "FIXED_INCOME": 0.30}

    alerts = generate_rebalancing_alerts(current, target, tolerance=0.05)

    actions = {a.asset_or_class: a.action for a in alerts}
    assert actions["FII"] == "REDUZIR"
    assert actions["EQUITY"] == "REDUZIR"
    assert actions["FIXED_INCOME"] == "APORTAR"
