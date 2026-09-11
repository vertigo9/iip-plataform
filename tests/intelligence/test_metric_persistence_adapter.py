import csv

import pytest

from iip.intelligence.metric_identity import MetricObservationIdentity
from iip.intelligence.metric_persistence_adapter import (
    AdapterResult,
    DryRunPersistenceAdapter,
    SimulatedKnowledgeBridgeAdapter,
    _clean,
    _derive_status,
    _identity_from_row,
    _read_csv,
    _resolve_tickers,
    _resolve_value,
    _ticker_from_identity,
    _tickers_from_lineage,
    inspect_final_gate,
)

# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------

PASSING_ROW: dict[str, str] = {
    "Original_Ticker": "CVBI11",
    "Canonical_Ticker": "PCIP11",
    "Lineage": "CVBI11 -> PCIP11",
    "Original_Identity": "CVBI11_HISTORICAL",
    "Metric": "Distribuicao_Mensal",
    "Value": "1.05",
    "Value_Parsed": "1.05",
    "Resolved_Unit": "BRL",
    "Scale": "unit",
    "Resolved_Period": "2026-07",
    "Semantic_Dimension_R4": "",
    "Semantic_Dimension_R3": "",
    "Semantic_Dimension": "",
    "SHA256": "abc123def456",
    "Document_ID": "DOC-0695-001",
    "Source_Locator": "p.1",
    "FileName": "pcip11_2026_07.pdf",
    "Final_Promotion_Gate": "PASS",
    "Final_Promotion_Gate_Reason": "",
    "Temporal_Gate": "PASS",
    "Temporal_Gate_Reason": "",
    "Domain_Status": "ELIGIBLE",
    "Domain_Promotion_Action": "ELIGIBLE_FOR_PROMOTION_GATE",
    "Domain_Resolution_Status": "AUTO_RESOLVED",
    "Domain_Scale_State": "RESOLVED",
    "Identity_Classification_R4": "",
    "Identity_Classification_R3": "",
    "Legacy_Period": "",
    "Validation_Status": "",
    "Validation_Reason": "",
    "Metric_Persistence_Authorization": "",
    "KnowledgeBridge_Write_Authorization": "",
    "Vault_Write_Authorization": "",
}


def make_row(**overrides: str) -> dict[str, str]:
    row = dict(PASSING_ROW)
    row.update(overrides)
    return row


def write_csv(tmp_path, rows: list[dict[str, str]]):
    path = tmp_path / "final_gate.csv"
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


# ---------------------------------------------------------------------------
# _clean / _read_csv
# ---------------------------------------------------------------------------

def test_clean_strips_and_handles_none():
    assert _clean("  value  ") == "value"
    assert _clean(None) == ""
    assert _clean("") == ""


def test_read_csv_returns_rows_with_bom_handled(tmp_path):
    path = write_csv(tmp_path, [make_row()])

    rows = _read_csv(path)

    assert len(rows) == 1
    assert rows[0]["Original_Ticker"] == "CVBI11"


# ---------------------------------------------------------------------------
# _ticker_from_identity
# ---------------------------------------------------------------------------

def test_ticker_from_identity_splits_on_underscore():
    assert _ticker_from_identity("CVBI11_HISTORICAL") == "CVBI11"
    assert _ticker_from_identity("ABC11_HISTORICAL") == "ABC11"


def test_ticker_from_identity_handles_empty_value():
    assert _ticker_from_identity("") == ""
    assert _ticker_from_identity(None) == ""


def test_ticker_from_identity_without_underscore_returns_whole_value():
    assert _ticker_from_identity("ABC11") == "ABC11"


# ---------------------------------------------------------------------------
# _tickers_from_lineage
# ---------------------------------------------------------------------------

def test_tickers_from_lineage_resolves_original_and_canonical():
    assert _tickers_from_lineage("CVBI11 -> PCIP11") == ("CVBI11", "PCIP11")


def test_tickers_from_lineage_single_ticker_returns_same_value_twice():
    assert _tickers_from_lineage("ABC11") == ("ABC11", "ABC11")


def test_tickers_from_lineage_empty_returns_empty_pair():
    assert _tickers_from_lineage("") == ("", "")
    assert _tickers_from_lineage(None) == ("", "")


def test_tickers_from_lineage_with_multiple_arrows_uses_first_and_last():
    assert _tickers_from_lineage("A -> B -> C") == ("A", "C")


def test_tickers_from_lineage_only_separator_returns_empty_pair():
    assert _tickers_from_lineage("->") == ("", "")
    assert _tickers_from_lineage("  ->  ") == ("", "")


# ---------------------------------------------------------------------------
# _resolve_tickers
# ---------------------------------------------------------------------------

def test_resolve_tickers_prefers_explicit_columns():
    row = make_row(Original_Ticker="CVBI11", Canonical_Ticker="PCIP11", Lineage="X -> Y")
    assert _resolve_tickers(row) == ("CVBI11", "PCIP11")


def test_resolve_tickers_falls_back_to_lineage():
    row = make_row(Original_Ticker="", Canonical_Ticker="", Lineage="CVBI11 -> PCIP11")
    assert _resolve_tickers(row) == ("CVBI11", "PCIP11")


def test_resolve_tickers_falls_back_to_original_identity():
    row = make_row(
        Original_Ticker="",
        Canonical_Ticker="",
        Lineage="",
        Original_Identity="ABC11_HISTORICAL",
    )
    assert _resolve_tickers(row) == ("ABC11", "ABC11")


def test_resolve_tickers_canonical_falls_back_to_original_when_missing():
    row = make_row(Original_Ticker="ABC11", Canonical_Ticker="", Lineage="")
    assert _resolve_tickers(row) == ("ABC11", "ABC11")


# ---------------------------------------------------------------------------
# _resolve_value
# ---------------------------------------------------------------------------

def test_resolve_value_prefers_value_parsed():
    row = make_row(Value_Parsed="1.05", Value="1.0")
    assert _resolve_value(row) == "1.05"


def test_resolve_value_falls_back_to_value():
    row = make_row(Value_Parsed="", Value="1.0")
    assert _resolve_value(row) == "1.0"


# ---------------------------------------------------------------------------
# _identity_from_row
# ---------------------------------------------------------------------------

def test_identity_from_row_builds_expected_identity():
    identity = _identity_from_row(make_row())

    assert isinstance(identity, MetricObservationIdentity)
    assert identity.canonical_ticker == "PCIP11"
    assert identity.original_ticker == "CVBI11"
    assert identity.metric_name == "Distribuicao_Mensal"
    assert identity.value == "1.05"
    assert identity.unit == "BRL"
    assert identity.period == "2026-07"
    assert identity.document_hash == "abc123def456"
    assert identity.lineage == "CVBI11 -> PCIP11"


def test_identity_from_row_semantic_dimension_priority_r4_then_r3_then_plain():
    identity_r4 = _identity_from_row(make_row(Semantic_Dimension_R4="MARKET_VALUE"))
    assert identity_r4.semantic_dimension == "MARKET_VALUE"

    identity_r3 = _identity_from_row(
        make_row(Semantic_Dimension_R4="", Semantic_Dimension_R3="NAV")
    )
    assert identity_r3.semantic_dimension == "NAV"

    identity_plain = _identity_from_row(
        make_row(Semantic_Dimension_R4="", Semantic_Dimension_R3="", Semantic_Dimension="LTM")
    )
    assert identity_plain.semantic_dimension == "LTM"


def test_identity_from_row_missing_optional_fields_become_none():
    row = make_row(Resolved_Unit="", Scale="", Document_ID="", Source_Locator="", Lineage="")
    identity = _identity_from_row(row)

    assert identity.unit is None
    assert identity.scale is None
    assert identity.document_id is None
    assert identity.source_locator is None
    assert identity.lineage is None


# ---------------------------------------------------------------------------
# _derive_status — every gate branch
# ---------------------------------------------------------------------------

def test_derive_status_blocks_when_final_gate_not_pass():
    row = make_row(Final_Promotion_Gate="FAIL", Final_Promotion_Gate_Reason="scale_conflict")
    status, reason = _derive_status(row, _identity_from_row(row))
    assert status == "BLOCKED"
    assert reason == "scale_conflict"


def test_derive_status_blocks_when_final_gate_not_pass_uses_default_reason():
    row = make_row(Final_Promotion_Gate="FAIL", Final_Promotion_Gate_Reason="", Validation_Reason="")
    status, reason = _derive_status(row, _identity_from_row(row))
    assert status == "BLOCKED"
    assert reason == "final_promotion_gate_not_pass"


def test_derive_status_blocks_when_temporal_gate_not_pass():
    row = make_row(Temporal_Gate="FAIL", Temporal_Gate_Reason="period_ambiguous")
    status, reason = _derive_status(row, _identity_from_row(row))
    assert status == "BLOCKED"
    assert reason == "period_ambiguous"


def test_derive_status_blocks_when_domain_not_eligible():
    row = make_row(Domain_Status="NOT_ELIGIBLE")
    status, reason = _derive_status(row, _identity_from_row(row))
    assert status == "BLOCKED"
    assert reason == "domain_not_eligible"


def test_derive_status_blocks_when_promotion_action_not_eligible():
    row = make_row(Domain_Promotion_Action="BLOCKED_ACTION")
    status, reason = _derive_status(row, _identity_from_row(row))
    assert status == "BLOCKED"
    assert reason == "promotion_action_not_eligible"


def test_derive_status_blocks_when_resolution_not_auto_resolved():
    row = make_row(Domain_Resolution_Status="MANUAL_REVIEW")
    status, reason = _derive_status(row, _identity_from_row(row))
    assert status == "BLOCKED"
    assert reason == "resolution_not_auto_resolved"


def test_derive_status_allows_auto_resolved_review_required():
    row = make_row(Domain_Resolution_Status="AUTO_RESOLVED_REVIEW_REQUIRED")
    status, _ = _derive_status(row, _identity_from_row(row))
    assert status != "BLOCKED"


def test_derive_status_blocks_when_scale_not_resolved():
    row = make_row(Domain_Scale_State="UNRESOLVED")
    status, reason = _derive_status(row, _identity_from_row(row))
    assert status == "BLOCKED"
    assert reason == "scale_not_resolved"


@pytest.mark.parametrize(
    ("row_overrides", "expected_reason"),
    [
        ({"Original_Ticker": "", "Canonical_Ticker": "", "Lineage": "", "Original_Identity": ""}, "missing_canonical_ticker"),
        ({"Metric": ""}, "missing_metric"),
        ({"Value": "", "Value_Parsed": ""}, "missing_value"),
        ({"Resolved_Period": ""}, "missing_period"),
        ({"SHA256": ""}, "missing_document_hash"),
        ({"Resolved_Unit": ""}, "missing_resolved_unit"),
    ],
)
def test_derive_status_blocks_on_missing_required_fields(row_overrides, expected_reason):
    row = make_row(**row_overrides)
    status, reason = _derive_status(row, _identity_from_row(row))
    assert status == "BLOCKED"
    assert reason == expected_reason


def test_derive_status_ready_without_semantic_dimension():
    row = make_row()
    status, reason = _derive_status(row, _identity_from_row(row))
    assert status == "IDENTITY_READY"
    assert reason == "promotion_gate_pass"


def test_derive_status_ready_with_semantic_dimension():
    row = make_row(Semantic_Dimension_R4="MARKET_VALUE")
    status, reason = _derive_status(row, _identity_from_row(row))
    assert status == "IDENTITY_READY_WITH_DIMENSION"
    assert reason == "promotion_gate_pass_with_semantic_dimension"


# ---------------------------------------------------------------------------
# inspect_final_gate — end to end over a CSV file
# ---------------------------------------------------------------------------

def test_inspect_final_gate_counts_ready_and_blocked_rows(tmp_path):
    rows = [
        make_row(),
        make_row(Final_Promotion_Gate="FAIL", Metric="Outra_Metrica"),
    ]
    path = write_csv(tmp_path, rows)

    result = inspect_final_gate(path)

    assert isinstance(result, AdapterResult)
    assert result.rows_read == 2
    assert len(result.candidates) == 2
    assert result.blocked_rows == 1
    assert result.canonical_observations == 1
    assert result.persistence_executed is False
    assert result.knowledge_bridge_executed is False
    assert result.vault_changed is False


def test_inspect_final_gate_deduplicates_exact_duplicate_rows(tmp_path):
    rows = [make_row(), make_row()]
    path = write_csv(tmp_path, rows)

    result = inspect_final_gate(path)

    assert result.rows_read == 2
    assert result.canonical_observations == 1
    assert result.exact_duplicate_rows == 1
    assert result.blocked_rows == 0


def test_inspect_final_gate_same_key_different_value_is_not_counted_as_exact_duplicate(tmp_path):
    rows = [make_row(), make_row(Value="1.10", Value_Parsed="1.10")]
    path = write_csv(tmp_path, rows)

    result = inspect_final_gate(path)

    # Different value changes the canonical_payload/observation_key, so both
    # observations are distinct canonical observations, not exact duplicates.
    assert result.canonical_observations == 2
    assert result.exact_duplicate_rows == 0


def test_inspect_final_gate_knowledge_evidence_is_attached_to_each_candidate(tmp_path):
    path = write_csv(tmp_path, [make_row()])

    result = inspect_final_gate(path)

    candidate = result.candidates[0]
    assert candidate.knowledge_evidence.ticker == "PCIP11"
    assert candidate.knowledge_evidence.relevant_facts["final_promotion_gate"] == "PASS"
    assert candidate.knowledge_evidence.relevant_facts["lineage"] == "CVBI11 -> PCIP11"


# ---------------------------------------------------------------------------
# DryRunPersistenceAdapter
# ---------------------------------------------------------------------------

def test_dry_run_adapter_delegates_to_inspect_final_gate(tmp_path):
    path = write_csv(tmp_path, [make_row()])

    result = DryRunPersistenceAdapter().run(path)

    assert isinstance(result, AdapterResult)
    assert result.rows_read == 1


# ---------------------------------------------------------------------------
# SimulatedKnowledgeBridgeAdapter — error path not covered by
# tests/integration/test_persistence_contract.py
# ---------------------------------------------------------------------------

class _NoIdEvidence:
    evidence_id = None


def test_simulated_bridge_rejects_evidence_without_id():
    bridge = SimulatedKnowledgeBridgeAdapter()

    with pytest.raises(ValueError):
        bridge.persist_evidence(_NoIdEvidence())


def test_simulated_bridge_sync_projection_ignores_missing_evidence_id():
    bridge = SimulatedKnowledgeBridgeAdapter()

    bridge.sync_evidence_projection(_NoIdEvidence())

    assert len(bridge.projections) == 0
