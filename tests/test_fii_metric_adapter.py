from datetime import date
from typing import ClassVar

import pytest

from iip.atlas.models import AtlasDocument
from iip.intelligence.fii_metric_adapter import (
    CVM_REGULATORY_CONFIDENCE,
    NAV_CONSISTENCY_TOLERANCE_PCT,
    cvm_patrimonio_liquido_to_evidence,
)
from iip.intelligence.metric_evidence import (
    LineageStatus,
    PeriodStatus,
    PromotionStatus,
    UnitStatus,
    assess_promotion,
)
from iip.sources.cvm_fii import FiiComplemento


def make_complemento(valor=7_580_921_710.93, data_referencia="2026-07-01"):
    return FiiComplemento(
        cnpj_fundo_classe="11.839.593/0001-09",
        data_referencia=data_referencia,
        versao="1",
        valores={"Patrimonio_Liquido": valor} if valor is not None else {},
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
        body=b"fake-zip-body",
        discovered_year=2026,
    )


def test_returns_none_when_field_is_absent():
    complemento = make_complemento(valor=None)
    document = make_document()

    result = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )

    assert result is None


def test_produces_a_promotable_evidence_from_real_shaped_data():
    complemento = make_complemento()
    document = make_document()

    evidence = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-BTLG11-PL-2026"
    )

    assert evidence is not None
    assert evidence.observation.value == 7_580_921_710.93
    assert evidence.observation.metric_name == "patrimonio_liquido"
    assert evidence.observation.period == "2026-07-01"
    assert evidence.observation.period_status is PeriodStatus.EXPLICIT
    assert evidence.observation.unit_status is UnitStatus.EXPLICIT
    assert evidence.lineage.status is LineageStatus.CURRENT
    assert evidence.confidence == CVM_REGULATORY_CONFIDENCE


def test_provenance_comes_from_the_real_atlas_document_not_invented():
    complemento = make_complemento()
    document = make_document()

    evidence = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )

    assert evidence.document_id == document.document_id
    assert evidence.document_hash == document.content_hash


def test_source_locator_names_the_exact_field_and_fund():
    complemento = make_complemento()
    document = make_document()

    evidence = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )

    assert evidence.source_locator == (
        "complemento[11.839.593/0001-09].Patrimonio_Liquido"
    )


def test_source_date_matches_data_referencia():
    complemento = make_complemento(data_referencia="2026-08-01")
    document = make_document()

    evidence = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )

    assert evidence.source_date == date(2026, 8, 1)


def test_evidence_is_eligible_for_promotion():
    complemento = make_complemento()
    document = make_document()

    evidence = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )

    assessment = assess_promotion(evidence)

    assert assessment.status is PromotionStatus.ELIGIBLE
    assert assessment.reasons == ("all_promotion_prerequisites_satisfied",)


def test_confidence_below_promotion_gate_would_be_reviewed_not_eligible(monkeypatch):
    # Confirma que o Promotion Gate de verdade seria acionado se a
    # confianca um dia cair abaixo de 0.80 -- nao estamos escondendo
    # esse comportamento atras de um valor sempre alto.
    import iip.intelligence.fii_metric_adapter as mod

    monkeypatch.setattr(mod, "CVM_REGULATORY_CONFIDENCE", 0.5)

    complemento = make_complemento()
    document = make_document()

    evidence = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )
    assessment = assess_promotion(evidence)

    assert assessment.status is PromotionStatus.REVIEW
    assert "confidence_below_0_80" in assessment.reasons


@pytest.mark.parametrize("ticker", ["BTLG11", "HGRU11"])
def test_lineage_never_claims_ticker_changed_for_a_stable_ticker(ticker):
    complemento = make_complemento()
    document = make_document()

    evidence = cvm_patrimonio_liquido_to_evidence(
        complemento, ticker, document, evidence_id="EV-1"
    )

    assert evidence.original_ticker == ticker
    assert evidence.canonical_ticker == ticker
    assert not evidence.lineage.changed


def make_bridge(tmp_path):
    from iip.knowledge.bridge import KnowledgeBridge

    return KnowledgeBridge(str(tmp_path / "vault"))


def make_complemento_fase_b(
    patrimonio_liquido=7_580_921_710.93,
    valor_patrimonial_cotas=106.86346,
    cotas_emitidas=70_940_261.0,
    data_referencia="2026-07-01",
):
    return FiiComplemento(
        cnpj_fundo_classe="11.839.593/0001-09",
        data_referencia=data_referencia,
        versao="1",
        valores={
            "Patrimonio_Liquido": patrimonio_liquido,
            "Valor_Patrimonial_Cotas": valor_patrimonial_cotas,
            "Cotas_Emitidas": cotas_emitidas,
        },
    )


def test_valor_patrimonial_cotas_returns_none_when_field_absent():
    from iip.intelligence.fii_metric_adapter import (
        cvm_valor_patrimonial_cotas_to_evidence,
    )

    complemento = make_complemento_fase_b(valor_patrimonial_cotas=None)
    document = make_document()

    result = cvm_valor_patrimonial_cotas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )
    assert result is None


def test_valor_patrimonial_cotas_produces_eligible_evidence():
    from iip.intelligence.fii_metric_adapter import (
        cvm_valor_patrimonial_cotas_to_evidence,
    )

    complemento = make_complemento_fase_b()
    document = make_document()

    evidence = cvm_valor_patrimonial_cotas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )

    assert evidence is not None
    assert evidence.observation.metric_name == "valor_patrimonial_cotas"
    assert evidence.observation.value == 106.86346
    assert evidence.observation.unit == "BRL"
    assert evidence.source_locator == (
        "complemento[11.839.593/0001-09].Valor_Patrimonial_Cotas"
    )
    assert assess_promotion(evidence).status is PromotionStatus.ELIGIBLE


def test_cotas_emitidas_returns_none_when_field_absent():
    from iip.intelligence.fii_metric_adapter import cvm_cotas_emitidas_to_evidence

    complemento = make_complemento_fase_b(cotas_emitidas=None)
    document = make_document()

    result = cvm_cotas_emitidas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )
    assert result is None


def test_cotas_emitidas_uses_cotas_as_unit_not_brl():
    from iip.intelligence.fii_metric_adapter import cvm_cotas_emitidas_to_evidence

    complemento = make_complemento_fase_b()
    document = make_document()

    evidence = cvm_cotas_emitidas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )

    assert evidence is not None
    assert evidence.observation.metric_name == "cotas_emitidas"
    assert evidence.observation.value == 70_940_261.0
    assert evidence.observation.unit == "cotas"  # nao BRL -- e' uma contagem
    assert evidence.source_locator == ("complemento[11.839.593/0001-09].Cotas_Emitidas")
    assert assess_promotion(evidence).status is PromotionStatus.ELIGIBLE


def test_all_three_fase_a_b_metrics_are_internally_consistent_with_real_shape():
    """PL / Cotas deveria bater aproximadamente com Valor_Patrimonial_Cotas
    -- confirmado com dado real do BTLG11 antes de escrever o codigo
    (7.580.921.710,93 / 70.940.261 ~= 106,8635 vs 106,86346 real)."""
    from iip.intelligence.fii_metric_adapter import (
        cvm_cotas_emitidas_to_evidence,
        cvm_patrimonio_liquido_to_evidence,
        cvm_valor_patrimonial_cotas_to_evidence,
    )

    complemento = make_complemento_fase_b()
    document = make_document()

    pl = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )
    vp = cvm_valor_patrimonial_cotas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-2"
    )
    cotas = cvm_cotas_emitidas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-3"
    )

    calculado = pl.observation.value / cotas.observation.value
    assert round(calculado, 2) == round(vp.observation.value, 2)


def test_fase_b_metrics_persist_through_the_same_real_mechanism(tmp_path):
    from iip.intelligence.fii_metric_adapter import (
        cvm_cotas_emitidas_to_evidence,
        cvm_valor_patrimonial_cotas_to_evidence,
        persist_if_eligible,
    )

    complemento = make_complemento_fase_b()
    document = make_document()
    bridge = make_bridge(tmp_path)

    vp = cvm_valor_patrimonial_cotas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-VP"
    )
    cotas = cvm_cotas_emitidas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-COTAS"
    )

    persistiu_vp, caminho_vp = persist_if_eligible(vp, bridge)
    persistiu_cotas, caminho_cotas = persist_if_eligible(cotas, bridge)

    assert persistiu_vp is True
    assert persistiu_cotas is True
    from pathlib import Path

    assert "106.86346" in Path(caminho_vp).read_text(encoding="utf-8")
    assert "70940261.0" in Path(caminho_cotas).read_text(encoding="utf-8")


def test_nav_consistency_check_confirms_real_shaped_data():
    from iip.intelligence.fii_metric_adapter import (
        check_nav_consistency,
        cvm_cotas_emitidas_to_evidence,
        cvm_patrimonio_liquido_to_evidence,
        cvm_valor_patrimonial_cotas_to_evidence,
    )

    complemento = make_complemento_fase_b()
    document = make_document()

    pl = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )
    cotas = cvm_cotas_emitidas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-2"
    )
    vp = cvm_valor_patrimonial_cotas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-3"
    )

    check = check_nav_consistency(pl, cotas, vp)

    assert check.ticker == "BTLG11"
    assert check.period == "2026-07-01"
    assert check.declared_nav_per_share == 106.86346
    assert round(check.calculated_nav_per_share, 4) == 106.8635
    assert check.consistent is True
    assert check.relative_difference_pct < 0.01


def test_nav_consistency_check_flags_a_real_discrepancy():
    from iip.intelligence.fii_metric_adapter import (
        check_nav_consistency,
        cvm_cotas_emitidas_to_evidence,
        cvm_patrimonio_liquido_to_evidence,
        cvm_valor_patrimonial_cotas_to_evidence,
    )

    # Valor_Patrimonial_Cotas propositalmente errado (fora da tolerancia)
    complemento = make_complemento_fase_b(valor_patrimonial_cotas=999.0)
    document = make_document()

    pl = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )
    cotas = cvm_cotas_emitidas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-2"
    )
    vp = cvm_valor_patrimonial_cotas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-3"
    )

    check = check_nav_consistency(pl, cotas, vp)

    assert check.consistent is False
    assert check.declared_nav_per_share == 999.0
    assert check.relative_difference_pct > NAV_CONSISTENCY_TOLERANCE_PCT


def test_nav_consistency_check_never_overwrites_the_declared_value():
    """O ponto arquitetural central: o valor calculado nunca substitui
    o declarado -- os dois ficam visiveis separadamente no resultado,
    mesmo quando divergem."""
    from iip.intelligence.fii_metric_adapter import (
        check_nav_consistency,
        cvm_cotas_emitidas_to_evidence,
        cvm_patrimonio_liquido_to_evidence,
        cvm_valor_patrimonial_cotas_to_evidence,
    )

    complemento = make_complemento_fase_b(valor_patrimonial_cotas=999.0)
    document = make_document()

    pl = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )
    cotas = cvm_cotas_emitidas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-2"
    )
    vp = cvm_valor_patrimonial_cotas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-3"
    )

    check = check_nav_consistency(pl, cotas, vp)

    assert check.declared_nav_per_share == 999.0  # o declarado continua intacto
    assert check.calculated_nav_per_share != 999.0  # nao foi substituido


def test_nav_consistency_check_rejects_mismatched_tickers():
    from iip.intelligence.fii_metric_adapter import (
        check_nav_consistency,
        cvm_cotas_emitidas_to_evidence,
        cvm_patrimonio_liquido_to_evidence,
        cvm_valor_patrimonial_cotas_to_evidence,
    )

    complemento = make_complemento_fase_b()
    document = make_document()

    pl = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )
    cotas = cvm_cotas_emitidas_to_evidence(
        complemento, "HGRU11", document, evidence_id="EV-2"  # ticker diferente
    )
    vp = cvm_valor_patrimonial_cotas_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-3"
    )

    with pytest.raises(ValueError, match="mesmo ticker"):
        check_nav_consistency(pl, cotas, vp)


def test_nav_consistency_check_rejects_mismatched_periods():
    from iip.intelligence.fii_metric_adapter import (
        check_nav_consistency,
        cvm_cotas_emitidas_to_evidence,
        cvm_patrimonio_liquido_to_evidence,
        cvm_valor_patrimonial_cotas_to_evidence,
    )

    complemento_julho = make_complemento_fase_b(data_referencia="2026-07-01")
    complemento_agosto = make_complemento_fase_b(data_referencia="2026-08-01")
    document = make_document()

    pl = cvm_patrimonio_liquido_to_evidence(
        complemento_julho, "BTLG11", document, evidence_id="EV-1"
    )
    cotas = cvm_cotas_emitidas_to_evidence(
        complemento_agosto, "BTLG11", document, evidence_id="EV-2"
    )
    vp = cvm_valor_patrimonial_cotas_to_evidence(
        complemento_julho, "BTLG11", document, evidence_id="EV-3"
    )

    with pytest.raises(ValueError, match="mesmo período"):
        check_nav_consistency(pl, cotas, vp)


def test_real_cvm_zip_nav_consistency_is_within_tolerance():
    """Fecha 15.15 com dado real: BTLG11 do ZIP real da CVM."""
    from pathlib import Path

    from iip.atlas.adapter import AtlasDocumentAdapter
    from iip.intelligence.fii_metric_adapter import (
        check_nav_consistency,
        cvm_cotas_emitidas_to_evidence,
        cvm_patrimonio_liquido_to_evidence,
        cvm_valor_patrimonial_cotas_to_evidence,
    )
    from iip.sources.cvm_fii import build_target
    from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester

    zip_path = Path("/mnt/user-data/uploads/inf_mensal_fii_2026.zip")
    if not zip_path.exists():
        pytest.skip("ZIP real da CVM não disponível neste ambiente")

    zip_bytes = zip_path.read_bytes()

    class FakeResponse:
        status = 200
        headers: ClassVar[dict[str, str]] = {
            "Content-Type": "application/zip; charset=binary"
        }

        def read(self):
            return zip_bytes

        def geturl(self):
            return "https://dados.cvm.gov.br/dataset/fii-doc-inf_mensal/inf_mensal_fii_2026.zip"

    result = CvmFiiHTTPHarvester(opener=lambda req, timeout: FakeResponse()).fetch(
        build_target(2026)
    )
    document = AtlasDocumentAdapter().from_fetched(result)

    cnpj_btlg11 = "11.839.593/0001-09"
    registros = sorted(
        (c for c in result.complemento if c.cnpj_fundo_classe == cnpj_btlg11),
        key=lambda c: c.data_referencia,
        reverse=True,
    )
    mais_recente = registros[0]

    pl = cvm_patrimonio_liquido_to_evidence(
        mais_recente, "BTLG11", document, evidence_id="EV-PL"
    )
    cotas = cvm_cotas_emitidas_to_evidence(
        mais_recente, "BTLG11", document, evidence_id="EV-COTAS"
    )
    vp = cvm_valor_patrimonial_cotas_to_evidence(
        mais_recente, "BTLG11", document, evidence_id="EV-VP"
    )

    check = check_nav_consistency(pl, cotas, vp)

    assert check.consistent is True
    assert check.relative_difference_pct < 0.01


def test_persist_if_eligible_writes_a_real_file(tmp_path):
    from iip.intelligence.fii_metric_adapter import persist_if_eligible

    complemento = make_complemento()
    document = make_document()
    evidence = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )
    bridge = make_bridge(tmp_path)

    persistiu, caminho = persist_if_eligible(evidence, bridge)

    assert persistiu is True
    from pathlib import Path

    assert Path(caminho).exists()


def test_persist_if_eligible_preserves_relevant_fact_values_not_just_keys(tmp_path):
    """Regressao do bug real encontrado: KnowledgeMetricEvidence.relevant_facts
    e' um dict, mas Evidence.relevant_facts e' uma tupla -- passar o
    dict direto perderia os VALORES, so' sobreviveriam as chaves."""
    from iip.intelligence.fii_metric_adapter import persist_if_eligible

    complemento = make_complemento(valor=7_580_921_710.93)
    document = make_document()
    evidence = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )
    bridge = make_bridge(tmp_path)

    _, caminho = persist_if_eligible(evidence, bridge)

    from pathlib import Path

    content = Path(caminho).read_text(encoding="utf-8")
    assert "7580921710.93" in content  # o VALOR, nao so' a chave "value"
    assert "patrimonio_liquido" in content
    assert "BRL" in content


def test_persist_if_eligible_uses_period_month_granularity(tmp_path):
    """month_date() em metric_persistence espera 'YYYY-MM' -- o
    data_referencia real da CVM vem 'YYYY-MM-DD'. Confirma que a
    conversao acontece sem quebrar."""
    from iip.intelligence.fii_metric_adapter import persist_if_eligible

    complemento = make_complemento(data_referencia="2026-07-01")
    document = make_document()
    evidence = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )
    bridge = make_bridge(tmp_path)

    persistiu, caminho = persist_if_eligible(evidence, bridge)

    assert persistiu is True
    from pathlib import Path

    content = Path(caminho).read_text(encoding="utf-8")
    assert "date: 2026-07-01" in content


def test_persist_if_eligible_does_not_persist_when_not_eligible(tmp_path, monkeypatch):
    import iip.intelligence.fii_metric_adapter as mod
    from iip.intelligence.fii_metric_adapter import persist_if_eligible

    monkeypatch.setattr(mod, "CVM_REGULATORY_CONFIDENCE", 0.5)
    complemento = make_complemento()
    document = make_document()
    evidence = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )
    bridge = make_bridge(tmp_path)

    persistiu, motivo = persist_if_eligible(evidence, bridge)

    assert persistiu is False
    assert "não elegível" in motivo
    assert not (tmp_path / "vault" / "04_Evidence").exists()


def test_persist_if_eligible_reports_when_already_persisted(tmp_path):
    from iip.intelligence.fii_metric_adapter import persist_if_eligible

    complemento = make_complemento()
    document = make_document()
    evidence = cvm_patrimonio_liquido_to_evidence(
        complemento, "BTLG11", document, evidence_id="EV-1"
    )
    bridge = make_bridge(tmp_path)

    persist_if_eligible(evidence, bridge)
    persistiu_de_novo, motivo = persist_if_eligible(evidence, bridge)

    assert persistiu_de_novo is False
    assert "já persistida" in motivo


def test_real_cvm_zip_persists_through_the_real_existing_mechanism(tmp_path):
    """Fecha a cadeia inteira com o ZIP real da CVM: dado real ->
    Atlas real -> evidencia real -> Promotion Gate -> persistencia
    real, usando so' o mecanismo de KnowledgeBridge ja existente."""
    from pathlib import Path

    from iip.atlas.adapter import AtlasDocumentAdapter
    from iip.intelligence.fii_metric_adapter import persist_if_eligible
    from iip.sources.cvm_fii import build_target
    from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester

    zip_path = Path("/mnt/user-data/uploads/inf_mensal_fii_2026.zip")
    if not zip_path.exists():
        pytest.skip("ZIP real da CVM não disponível neste ambiente")

    zip_bytes = zip_path.read_bytes()

    class FakeResponse:
        status = 200
        headers: ClassVar[dict[str, str]] = {
            "Content-Type": "application/zip; charset=binary"
        }

        def read(self):
            return zip_bytes

        def geturl(self):
            return "https://dados.cvm.gov.br/dataset/fii-doc-inf_mensal/inf_mensal_fii_2026.zip"

    result = CvmFiiHTTPHarvester(opener=lambda req, timeout: FakeResponse()).fetch(
        build_target(2026)
    )
    document = AtlasDocumentAdapter().from_fetched(result)

    cnpj_btlg11 = "11.839.593/0001-09"
    registros = sorted(
        (c for c in result.complemento if c.cnpj_fundo_classe == cnpj_btlg11),
        key=lambda c: c.data_referencia,
        reverse=True,
    )
    evidence = cvm_patrimonio_liquido_to_evidence(
        registros[0], "BTLG11", document, evidence_id="EV-BTLG11-REAL-PERSIST"
    )
    bridge = make_bridge(tmp_path)

    persistiu, caminho = persist_if_eligible(evidence, bridge)

    assert persistiu is True
    from pathlib import Path as _Path

    content = _Path(caminho).read_text(encoding="utf-8")
    assert str(evidence.observation.value) in content
