from datetime import date

import pytest

from iip.atlas.models import AtlasDocument
from iip.intelligence.harvest_metric_adapter import (
    PROVIDER_CONFIDENCE_POLICY,
    MetricField,
    harvest_metrics_to_evidence,
)
from iip.intelligence.metric_evidence import (
    EvidenceSourceRole,
    LineageStatus,
    PromotionStatus,
    assess_promotion,
)


def make_document():
    return AtlasDocument.build(
        ticker="MULTI",
        provider="cvm",
        role="regulatory",
        url="https://dados.cvm.gov.br/x.zip",
        final_url="https://dados.cvm.gov.br/x.zip",
        content_type="application/zip",
        status_code=200,
        body=b"fake-body",
        discovered_year=2026,
    )


def test_produces_real_promotable_evidence_from_real_shaped_data():
    document = make_document()
    fields = [
        MetricField(
            "patrimonio_liquido",
            7_580_921_710.93,
            "BRL",
            "complemento[11.839.593/0001-09].Patrimonio_Liquido",
        ),
    ]

    evidences = harvest_metrics_to_evidence(
        ticker="BTLG11",
        period="2026-07-01",
        document=document,
        provider="cvm",
        source_role=EvidenceSourceRole.NAV_PL,
        fields=fields,
        evidence_id_prefix="EV-BTLG11",
    )

    assert len(evidences) == 1
    ev = evidences[0]
    assert ev.observation.metric_name == "patrimonio_liquido"
    assert ev.observation.value == 7_580_921_710.93
    assert ev.canonical_ticker == "BTLG11"
    assert ev.document_id == document.document_id
    assert ev.document_hash == document.content_hash
    assert ev.lineage.status is LineageStatus.CURRENT
    assert assess_promotion(ev).status is PromotionStatus.ELIGIBLE


def test_never_guesses_ticker_from_fetched_object():
    """Regressao do bug real: a versao anterior tentava
    fetched.fii.get('ticker') assumindo dict, mas fii e' um dataclass
    -- sempre caia em 'UNKNOWN'. Aqui o ticker e' sempre explicito,
    nunca adivinhado de um objeto de fetch."""
    document = make_document()
    fields = [MetricField("x", 1.0, "BRL", "loc")]

    evidences = harvest_metrics_to_evidence(
        ticker="HGRU11",
        period="2026-01-01",
        document=document,
        provider="cvm",
        source_role=EvidenceSourceRole.NAV_PL,
        fields=fields,
        evidence_id_prefix="EV",
    )

    assert evidences[0].canonical_ticker == "HGRU11"
    assert evidences[0].canonical_ticker != "UNKNOWN"


def test_rejects_unknown_provider_instead_of_fabricating_confidence():
    document = make_document()

    with pytest.raises(ValueError, match="sem política de confiança"):
        harvest_metrics_to_evidence(
            ticker="X",
            period="2026-01-01",
            document=document,
            provider="fonte_desconhecida",
            source_role=EvidenceSourceRole.NAV_PL,
            fields=[],
            evidence_id_prefix="EV",
        )


def test_confidence_never_derived_from_http_status_only_from_policy():
    """Regressao do bug real: a versao anterior usava
    '0.95 if status_code == 200 else 0.0' -- sem relacao com a
    natureza real da fonte. Aqui a confianca vem so' da politica por
    provedor, documentada."""
    document = make_document()
    fields = [MetricField("x", 1.0, "BRL", "loc")]

    ev_cvm = harvest_metrics_to_evidence(
        ticker="X",
        period="2026-01-01",
        document=document,
        provider="cvm",
        source_role=EvidenceSourceRole.NAV_PL,
        fields=fields,
        evidence_id_prefix="EV",
    )[0]
    ev_b3 = harvest_metrics_to_evidence(
        ticker="X",
        period="2026-01-01",
        document=document,
        provider="b3",
        source_role=EvidenceSourceRole.NAV_PL,
        fields=fields,
        evidence_id_prefix="EV",
    )[0]

    assert ev_cvm.confidence == PROVIDER_CONFIDENCE_POLICY["cvm"]
    assert ev_b3.confidence == PROVIDER_CONFIDENCE_POLICY["b3"]
    assert ev_cvm.confidence != ev_b3.confidence


def test_each_field_keeps_its_own_source_locator_not_a_generic_dict():
    """Regressao do bug real: a versao anterior recebia
    dict[str, float] generico, sem locator por campo. Aqui cada
    MetricField carrega seu proprio source_locator."""
    document = make_document()
    fields = [
        MetricField("a", 1.0, "BRL", "locator_a"),
        MetricField("b", 2.0, "BRL", "locator_b"),
    ]

    evidences = harvest_metrics_to_evidence(
        ticker="X",
        period="2026-01-01",
        document=document,
        provider="cvm",
        source_role=EvidenceSourceRole.NAV_PL,
        fields=fields,
        evidence_id_prefix="EV",
    )

    locators = {ev.observation.metric_name: ev.source_locator for ev in evidences}
    assert locators["a"] == "locator_a"
    assert locators["b"] == "locator_b"


def test_evidence_id_is_unique_per_field():
    document = make_document()
    fields = [
        MetricField("a", 1.0, "BRL", "loc_a"),
        MetricField("b", 2.0, "BRL", "loc_b"),
    ]

    evidences = harvest_metrics_to_evidence(
        ticker="X",
        period="2026-01-01",
        document=document,
        provider="cvm",
        source_role=EvidenceSourceRole.NAV_PL,
        fields=fields,
        evidence_id_prefix="EV-X-2026",
    )

    ids = {ev.evidence_id for ev in evidences}
    assert len(ids) == 2
    assert "EV-X-2026-a" in ids
    assert "EV-X-2026-b" in ids


def test_source_date_matches_period():
    document = make_document()
    fields = [MetricField("a", 1.0, "BRL", "loc")]

    evidence = harvest_metrics_to_evidence(
        ticker="X",
        period="2026-08-15",
        document=document,
        provider="cvm",
        source_role=EvidenceSourceRole.NAV_PL,
        fields=fields,
        evidence_id_prefix="EV",
    )[0]

    assert evidence.source_date == date(2026, 8, 15)


def test_empty_fields_produces_empty_list_not_an_error():
    document = make_document()

    evidences = harvest_metrics_to_evidence(
        ticker="X",
        period="2026-01-01",
        document=document,
        provider="cvm",
        source_role=EvidenceSourceRole.NAV_PL,
        fields=[],
        evidence_id_prefix="EV",
    )

    assert evidences == []
