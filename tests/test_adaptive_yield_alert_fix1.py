from iip.adaptive.portfolio_alerts import yield_alert


def test_yield_alert_medium_band():
    result = yield_alert("HGRU11", 0.08, 0.10)
    assert result is not None
    assert result.severity == "medium"


def test_yield_alert_high_band():
    result = yield_alert("HGRU11", 0.07, 0.10)
    assert result is not None
    assert result.severity == "high"


def test_yield_alert_no_alert():
    assert yield_alert("HGRU11", 0.095, 0.10) is None


def test_yield_alert_invalid_reference():
    assert yield_alert("HGRU11", 0.08, 0.0) is None
