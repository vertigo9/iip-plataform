import json

import pytest

from iip.sources.ibge import build_target, parse_agregados_response


def test_build_target_formats_url_correctly():
    target = build_target(1705, 63, periodos="-6", localidades="BR")

    assert target.url == (
        "https://servicodados.ibge.gov.br/api/v3/agregados/1705"
        "/periodos/-6/variaveis/63?localidades=BR"
    )
    assert target.agregado == 1705
    assert target.variavel == 63


def test_build_target_default_periodos_is_last_six():
    target = build_target(1705, 63)
    assert target.periodos == "-6"
    assert target.localidades == "BR"


def test_build_target_omits_variavel_when_not_given():
    target = build_target(1705)

    assert target.variavel is None
    assert target.url == (
        "https://servicodados.ibge.gov.br/api/v3/agregados/1705"
        "/periodos/-6/variaveis?localidades=BR"
    )


def test_build_target_accepts_explicit_period_range_and_locality():
    target = build_target(1705, 63, periodos="202001-202012", localidades="N6[3550308]")
    assert "periodos/202001-202012" in target.url
    assert "localidades=N6[3550308]" in target.url


@pytest.mark.parametrize(
    ("agregado", "variavel", "periodos", "localidades"),
    [
        (0, 63, "-6", "BR"),
        (1705, -1, "-6", "BR"),
        (1705, 63, "", "BR"),
        (1705, 63, "-6", ""),
    ],
)
def test_build_target_rejects_invalid_arguments(
    agregado, variavel, periodos, localidades
):
    with pytest.raises(ValueError):
        build_target(agregado, variavel, periodos=periodos, localidades=localidades)


def make_response(*, value="0.83"):
    """Mimics the real (nested) shape of an IBGE Agregados JSON response."""
    return json.dumps(
        [
            {
                "id": "63",
                "variavel": "IPCA - Variação mensal",
                "unidade": "%",
                "resultados": [
                    {
                        "classificacoes": [],
                        "series": [
                            {
                                "localidade": {"id": "1", "nome": "Brasil"},
                                "serie": {"202607": value},
                            }
                        ],
                    }
                ],
            }
        ]
    ).encode("utf-8")


def test_parse_agregados_response_flattens_nested_structure():
    points = parse_agregados_response(make_response())

    assert len(points) == 1
    point = points[0]
    assert point.variavel_id == "63"
    assert point.variavel_nome == "IPCA - Variação mensal"
    assert point.unidade == "%"
    assert point.localidade_id == "1"
    assert point.localidade_nome == "Brasil"
    assert point.periodo == "202607"
    assert point.value == 0.83


@pytest.mark.parametrize("marker", ["...", "..", "-", "X", ""])
def test_parse_agregados_response_treats_missing_markers_as_none(marker):
    points = parse_agregados_response(make_response(value=marker))
    assert points[0].value is None


def test_parse_agregados_response_treats_unparseable_garbage_as_none():
    points = parse_agregados_response(make_response(value="não-numérico"))
    assert points[0].value is None


def test_parse_agregados_response_handles_empty_list():
    assert parse_agregados_response(b"[]") == ()


def test_parse_agregados_response_handles_multiple_localities_and_periods():
    body = json.dumps(
        [
            {
                "id": "9324",
                "variavel": "População residente estimada",
                "unidade": "Pessoas",
                "resultados": [
                    {
                        "classificacoes": [],
                        "series": [
                            {
                                "localidade": {"id": "3550308", "nome": "São Paulo"},
                                "serie": {"2024": "12325232", "2025": "12396372"},
                            },
                            {
                                "localidade": {
                                    "id": "3304557",
                                    "nome": "Rio de Janeiro",
                                },
                                "serie": {"2024": "6211423"},
                            },
                        ],
                    }
                ],
            }
        ]
    ).encode("utf-8")

    points = parse_agregados_response(body)

    assert len(points) == 3
    sao_paulo_2025 = next(
        p for p in points if p.localidade_nome == "São Paulo" and p.periodo == "2025"
    )
    assert sao_paulo_2025.value == 12396372.0
