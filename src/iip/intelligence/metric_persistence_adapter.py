from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .metric_identity import (
    MetricObservationIdentity,
)
from .metric_persistence import (
    PersistenceBatch,
    PersistenceCandidate,
    build_knowledge_evidence,
)


class EvidenceSink(Protocol):
    def persist_evidence(self, evidence: object) -> None: ...


class ProjectionSink(Protocol):
    def sync_evidence_projection(self, evidence: object) -> None: ...


@dataclass
class AdapterResult:
    rows_read: int
    candidates: list[PersistenceCandidate]
    canonical_observations: int
    exact_duplicate_rows: int
    blocked_rows: int
    persistence_executed: bool = False
    knowledge_bridge_executed: bool = False
    vault_changed: bool = False


def _clean(value: object) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def _ticker_from_identity(
    original_identity: str,
) -> str:
    """
    Fallback used only when the CSV does not expose
    an explicit Original_Ticker column.

    Example:
        CVBI11_HISTORICAL -> CVBI11
        ABC11_HISTORICAL  -> ABC11

    The function does not hardcode any ticker.
    """

    value = _clean(original_identity)

    if not value:
        return ""

    return value.split("_", 1)[0].strip()


def _tickers_from_lineage(
    lineage: str,
) -> tuple[str, str]:
    """
    Resolve original/canonical tickers generically from
    a lineage such as:

        CVBI11 -> PCIP11

    Returns:

        (original_ticker, canonical_ticker)

    For a single ticker:

        ABC11

    returns:

        (ABC11, ABC11)
    """

    value = _clean(lineage)

    if not value:
        return "", ""

    parts = [item.strip() for item in value.split("->") if item.strip()]

    if not parts:
        return "", ""

    if len(parts) == 1:
        return parts[0], parts[0]

    return parts[0], parts[-1]


def _resolve_tickers(
    row: dict[str, str],
) -> tuple[str, str]:
    """
    Prefer explicit ticker columns when available.

    Otherwise resolve generically from Lineage and
    Original_Identity.
    """

    explicit_original = _clean(row.get("Original_Ticker"))

    explicit_canonical = _clean(row.get("Canonical_Ticker"))

    lineage_original, lineage_canonical = _tickers_from_lineage(row.get("Lineage", ""))

    original_identity_ticker = _ticker_from_identity(row.get("Original_Identity", ""))

    original_ticker = explicit_original or lineage_original or original_identity_ticker

    canonical_ticker = explicit_canonical or lineage_canonical or original_ticker

    return original_ticker, canonical_ticker


def _resolve_value(
    row: dict[str, str],
) -> str:
    """
    Preserve the source value.

    The FINAL_PROMOTION_GATE schema uses Value,
    whereas intermediate schemas may expose Value_Parsed.
    """

    return _clean(row.get("Value_Parsed")) or _clean(row.get("Value"))


def _identity_from_row(
    row: dict[str, str],
) -> MetricObservationIdentity:

    original_ticker, canonical_ticker = _resolve_tickers(row)

    semantic_dimension = (
        _clean(row.get("Semantic_Dimension_R4"))
        or _clean(row.get("Semantic_Dimension_R3"))
        or _clean(row.get("Semantic_Dimension"))
        or None
    )

    return MetricObservationIdentity(
        canonical_ticker=canonical_ticker,
        original_ticker=original_ticker or None,
        metric_name=_clean(row.get("Metric")),
        value=_resolve_value(row),
        unit=(_clean(row.get("Resolved_Unit")) or None),
        scale=(_clean(row.get("Scale")) or None),
        period=_clean(row.get("Resolved_Period")),
        semantic_dimension=semantic_dimension,
        document_hash=_clean(row.get("SHA256")),
        document_id=(_clean(row.get("Document_ID")) or None),
        source_locator=(_clean(row.get("Source_Locator")) or None),
        lineage=(_clean(row.get("Lineage")) or None),
    )


def _derive_status(
    row: dict[str, str],
    observation: MetricObservationIdentity,
) -> tuple[str, str]:

    final_gate = _clean(row.get("Final_Promotion_Gate"))

    if final_gate != "PASS":
        reason = (
            _clean(row.get("Final_Promotion_Gate_Reason"))
            or _clean(row.get("Validation_Reason"))
            or "final_promotion_gate_not_pass"
        )

        return "BLOCKED", reason

    temporal_gate = _clean(row.get("Temporal_Gate"))

    if temporal_gate != "PASS":
        return (
            "BLOCKED",
            _clean(row.get("Temporal_Gate_Reason")) or "temporal_gate_not_pass",
        )

    domain_status = _clean(row.get("Domain_Status"))

    if domain_status != "ELIGIBLE":
        return (
            "BLOCKED",
            _clean(row.get("Final_Promotion_Gate_Reason")) or "domain_not_eligible",
        )

    promotion_action = _clean(row.get("Domain_Promotion_Action"))

    if promotion_action != "ELIGIBLE_FOR_PROMOTION_GATE":
        return (
            "BLOCKED",
            "promotion_action_not_eligible",
        )

    resolution_status = _clean(row.get("Domain_Resolution_Status"))

    scale_state = _clean(row.get("Domain_Scale_State"))

    if resolution_status not in {
        "AUTO_RESOLVED",
        "AUTO_RESOLVED_REVIEW_REQUIRED",
    }:
        return (
            "BLOCKED",
            "resolution_not_auto_resolved",
        )

    if scale_state != "RESOLVED":
        return (
            "BLOCKED",
            "scale_not_resolved",
        )

    if not observation.canonical_ticker:
        return (
            "BLOCKED",
            "missing_canonical_ticker",
        )

    if not observation.metric_name:
        return (
            "BLOCKED",
            "missing_metric",
        )

    if not observation.value:
        return (
            "BLOCKED",
            "missing_value",
        )

    if not observation.period:
        return (
            "BLOCKED",
            "missing_period",
        )

    if not observation.document_hash:
        return (
            "BLOCKED",
            "missing_document_hash",
        )

    if not observation.unit:
        return (
            "BLOCKED",
            "missing_resolved_unit",
        )

    if observation.semantic_dimension:
        return (
            "IDENTITY_READY_WITH_DIMENSION",
            "promotion_gate_pass_with_semantic_dimension",
        )

    return (
        "IDENTITY_READY",
        "promotion_gate_pass",
    )


def inspect_final_gate(
    path: Path,
) -> AdapterResult:

    rows = _read_csv(path)

    candidates: list[PersistenceCandidate] = []

    for row in rows:
        observation = _identity_from_row(row)

        status, reason = _derive_status(
            row,
            observation,
        )

        knowledge = build_knowledge_evidence(
            observation,
            title=_clean(row.get("FileName")),
            relevant_facts={
                "legacy_period": _clean(row.get("Legacy_Period")),
                "validation_status": _clean(row.get("Validation_Status")),
                "validation_reason": _clean(row.get("Validation_Reason")),
                "final_promotion_gate": _clean(row.get("Final_Promotion_Gate")),
                "final_promotion_gate_reason": _clean(
                    row.get("Final_Promotion_Gate_Reason")
                ),
                "domain_status": _clean(row.get("Domain_Status")),
                "domain_resolution_status": _clean(row.get("Domain_Resolution_Status")),
                "domain_promotion_action": _clean(row.get("Domain_Promotion_Action")),
                "domain_scale_state": _clean(row.get("Domain_Scale_State")),
                "temporal_gate": _clean(row.get("Temporal_Gate")),
                "temporal_gate_reason": _clean(row.get("Temporal_Gate_Reason")),
                "metric_persistence_authorization": _clean(
                    row.get("Metric_Persistence_Authorization")
                ),
                "knowledgebridge_write_authorization": _clean(
                    row.get("KnowledgeBridge_Write_Authorization")
                ),
                "vault_write_authorization": _clean(
                    row.get("Vault_Write_Authorization")
                ),
                "original_identity": _clean(row.get("Original_Identity")),
                "lineage": _clean(row.get("Lineage")),
                "source_value": _clean(row.get("Value")),
            },
        )

        classification = (
            _clean(row.get("Identity_Classification_R4"))
            or _clean(row.get("Identity_Classification_R3"))
            or ""
        )

        candidates.append(
            PersistenceCandidate(
                observation=observation,
                knowledge_evidence=knowledge,
                classification=classification,
                status=status,
                reason=reason,
            )
        )

    batch = PersistenceBatch(candidates)

    canonical: dict[
        str,
        PersistenceCandidate,
    ] = {}

    exact_duplicate_rows = 0

    for candidate in batch.ready:
        key = candidate.observation.observation_key

        if key in canonical:
            existing = canonical[key]

            if existing.observation.value == candidate.observation.value:
                exact_duplicate_rows += 1

        else:
            canonical[key] = candidate

    return AdapterResult(
        rows_read=len(rows),
        candidates=candidates,
        canonical_observations=len(canonical),
        exact_duplicate_rows=(exact_duplicate_rows),
        blocked_rows=len(batch.blocked),
    )


class DryRunPersistenceAdapter:
    def run(
        self,
        path: Path,
    ) -> AdapterResult:
        return inspect_final_gate(path)


class SimulatedKnowledgeBridgeAdapter:
    """
    Contract-only adapter.

    In-memory only.
    Never touches the Vault.
    """

    def __init__(self) -> None:
        self.persisted_ids: set[str] = set()
        self.projections: set[str] = set()

    def persist_evidence(
        self,
        evidence: object,
    ) -> None:

        evidence_id = getattr(
            evidence,
            "evidence_id",
            None,
        )

        if not evidence_id:
            raise ValueError("Evidence requires evidence_id.")

        self.persisted_ids.add(str(evidence_id))

    def sync_evidence_projection(
        self,
        evidence: object,
    ) -> None:

        evidence_id = getattr(
            evidence,
            "evidence_id",
            None,
        )

        if evidence_id:
            self.projections.add(str(evidence_id))

    @property
    def size(self) -> int:
        return len(self.persisted_ids)


def to_knowledge_evidence(metric_evidence: KnowledgeMetricEvidence):
    """Convert a ``KnowledgeMetricEvidence`` (this module's own
    persistence-candidate shape) into a real ``iip.knowledge.models.Evidence``
    -- the type ``KnowledgeBridge.persist_evidence``/``sync_evidence_projection``
    actually accept. The two shapes differ only in ``relevant_facts``:
    a ``dict[str, str]`` here vs. the tuple-of-strings ``Evidence`` expects
    (same ``key=value`` convention already used by
    ``AtlasKnowledgeAdapter.to_evidence``); blank values are dropped rather
    than persisted as noise.
    """
    from iip.knowledge.models import Evidence

    return Evidence(
        evidence_id=metric_evidence.evidence_id,
        ticker=metric_evidence.ticker,
        date=metric_evidence.date,
        source_type=metric_evidence.source_type,
        source_url=metric_evidence.source_url,
        title=metric_evidence.title,
        document_hash=metric_evidence.document_hash,
        relevant_facts=tuple(
            f"{key}={value}"
            for key, value in metric_evidence.relevant_facts.items()
            if value
        ),
    )


def persist_ready_batch(
    batch: PersistenceBatch,
    sink: EvidenceSink,
    *,
    sync_projection: bool = False,
) -> tuple[str, ...]:
    """Persist every ready (READY/READY_WITH_DIMENSION/DEDUPLICABLE)
    candidate in ``batch`` as real Evidence via ``sink`` -- the real
    ``KnowledgeBridge.persist_evidence`` (or any object satisfying the
    ``EvidenceSink`` protocol; ``SimulatedKnowledgeBridgeAdapter`` for
    tests that must never touch the Vault).

    This is the step the 0695.7 initiative built every other piece of
    this module up to but never wired -- its own release-readiness
    script (``archive/dev-history/RELEASE_0695_7_READINESS_R1.py``)
    required ``Metric_Persistence_Authorization``/
    ``KnowledgeBridge_Write_Authorization``/``Vault_Write_Authorization``
    to all read ``NOT_GRANTED`` to pass, as a deliberate pre-persistence
    safety gate. Only call this once that authorization has genuinely
    been given for the batch being persisted.

    ``persist_evidence`` is append-only per ``evidence_id`` (same content
    hash already persisted raises ``FileExistsError``) -- caught here and
    treated as already-done, not a failure, same convention as every
    other ``persist_evidence`` caller in this project.
    """
    persisted: list[str] = []
    for candidate in batch.ready:
        evidence = to_knowledge_evidence(candidate.knowledge_evidence)
        try:
            sink.persist_evidence(evidence)
        except FileExistsError:
            continue
        persisted.append(evidence.evidence_id)
        if sync_projection:
            projector = getattr(sink, "sync_evidence_projection", None)
            if projector is not None:
                projector(evidence)
    return tuple(persisted)


def persist_historical_series_metrics(
    series,
    sink: EvidenceSink,
    *,
    metric_name: str = "Cota_Patrimonial",
    sync_projection: bool = False,
) -> tuple[str, ...]:
    """Promote every ``valor_patrimonial_cotas`` observation in a real,
    already-collected ``iip.portfolio.historical_series.HistoricalSeries``
    straight to Evidence -- no FINAL_PROMOTION_GATE CSV round-trip
    needed, since each observation's own ``document_hash``/``document_id``
    already carries exactly the provenance a CSV row would (the series
    was built by a real provider -- Sparta, CVM -- from a real fetched
    document, never guessed).

    This is the scalable promotion path for tickers whose NAV history a
    provider has already collected: no PDF has to be re-read or
    hand-verified, unlike the PCIP11 pilot's CSV path (see
    ``persist_ready_batch``), which exists for cases with no structured
    series yet. Confirmed live (18/09/2026) against CRAA11's real
    19-observation Sparta series as a second, independent validation of
    the same underlying persist step.

    Observations with no ``valor_patrimonial_cotas`` (a month Sparta's
    report layout didn't match, see ``sparta_reports`` module docstring)
    are skipped, never guessed. ``period`` is truncated from the
    series' ``YYYY-MM-DD`` to ``YYYY-MM`` (``month_date`` only needs the
    month); semantic dimension is always ``NAV`` since
    ``valor_patrimonial_cotas`` is unambiguously cota patrimonial, no
    market-value/LTM confusion possible for this field.
    """
    persisted: list[str] = []
    for obs in series.observations:
        if obs.valor_patrimonial_cotas is None:
            continue
        identity = MetricObservationIdentity(
            canonical_ticker=series.ticker,
            original_ticker=series.ticker,
            metric_name=metric_name,
            value=str(obs.valor_patrimonial_cotas),
            unit="BRL_per_quota",
            scale="unit",
            period=obs.period[:7],
            semantic_dimension="NAV",
            document_hash=obs.document_hash,
            document_id=obs.document_id,
        )
        knowledge = build_knowledge_evidence(
            identity,
            title=obs.document_id,
            source_type="historical_metric",
            relevant_facts={
                "provider": series.provider,
                "discovered_year": str(obs.discovered_year),
            },
        )
        evidence = to_knowledge_evidence(knowledge)
        try:
            sink.persist_evidence(evidence)
        except FileExistsError:
            continue
        persisted.append(evidence.evidence_id)
        if sync_projection:
            projector = getattr(sink, "sync_evidence_projection", None)
            if projector is not None:
                projector(evidence)
    return tuple(persisted)
