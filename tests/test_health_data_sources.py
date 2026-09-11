from urllib.error import HTTPError, URLError

from iip.config import IIPSettings
from iip.health import DataSourceReachabilityCheck, default_data_source_checks


def make_settings():
    return IIPSettings(_env_file=None)


class FakeResponse:
    status = 200


def test_reachability_check_healthy_on_2xx():
    def opener(request, timeout):
        return FakeResponse()

    check = DataSourceReachabilityCheck("teste", "https://exemplo.com", opener=opener)
    result = check.check(make_settings())

    assert result.healthy is True
    assert "200" in result.message


def test_reachability_check_name_is_prefixed_with_source():
    check = DataSourceReachabilityCheck("cvm", "https://dados.cvm.gov.br")
    assert check.name == "source_cvm"


def test_reachability_check_healthy_even_on_http_error_status():
    def opener(request, timeout):
        raise HTTPError("https://exemplo.com", 404, "Not Found", None, None)

    check = DataSourceReachabilityCheck("teste", "https://exemplo.com", opener=opener)
    result = check.check(make_settings())

    # A 404/405 still means the server answered — reachable, not down.
    assert result.healthy is True
    assert "404" in result.message


def test_reachability_check_unhealthy_on_connection_error():
    def opener(request, timeout):
        raise URLError("nome nao resolvido")

    check = DataSourceReachabilityCheck("teste", "https://exemplo.com", opener=opener)
    result = check.check(make_settings())

    assert result.healthy is False
    assert "Inalcançável" in result.message


def test_reachability_check_unhealthy_on_timeout():
    def opener(request, timeout):
        raise TimeoutError("demorou demais")

    check = DataSourceReachabilityCheck("teste", "https://exemplo.com", opener=opener)
    result = check.check(make_settings())

    assert result.healthy is False


def test_reachability_check_sends_head_request_with_short_timeout():
    captured = {}

    def opener(request, timeout):
        captured["method"] = request.get_method()
        captured["timeout"] = timeout
        return FakeResponse()

    check = DataSourceReachabilityCheck(
        "teste", "https://exemplo.com", timeout=3.0, opener=opener
    )
    check.check(make_settings())

    assert captured["method"] == "HEAD"
    assert captured["timeout"] == 3.0


def test_default_data_source_checks_covers_every_real_source():
    checks = default_data_source_checks()
    names = {c.name for c in checks}

    assert "source_cvm" in names
    assert "source_bacen" in names
    assert "source_ibge" in names
    assert "source_bolsai" in names
    assert "source_brapi" in names
    assert "source_brasilapi" in names
    assert "source_mziq" in names
    assert len(checks) == len(names)  # sem nomes duplicados
