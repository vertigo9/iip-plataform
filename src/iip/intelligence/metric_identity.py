from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum


class IdentityClassification(str, Enum):
    UNIQUE = "UNIQUE"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    SEMANTICALLY_DISTINCT = "SEMANTICALLY_DISTINCT"
    SEMANTIC_CONTEXT_UNRESOLVED = "SEMANTIC_CONTEXT_UNRESOLVED"


class IdentityStatus(str, Enum):
    READY = "IDENTITY_READY"
    READY_WITH_DIMENSION = "IDENTITY_READY_WITH_DIMENSION"
    DEDUPLICABLE = "DEDUPLICABLE"
    REVIEW = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED_SEMANTIC_IDENTITY"


class SemanticDimension(str, Enum):
    MARKET_VALUE = "MARKET_VALUE"
    NAV = "NAV"
    LTM = "LTM"


@dataclass(frozen=True)
class SourceContext:
    text: str
    locator: str | None = None
    source_role: str | None = None


@dataclass(frozen=True)
class MetricObservationIdentity:
    canonical_ticker: str
    original_ticker: str | None
    metric_name: str
    value: str
    unit: str | None
    scale: str | None
    period: str
    semantic_dimension: str | None
    document_hash: str
    document_id: str | None = None
    source_locator: str | None = None
    lineage: str | None = None

    def canonical_payload(self) -> str:
        parts = (
            self.canonical_ticker,
            self.metric_name,
            self.period,
            self.semantic_dimension or "",
            self.value,
            self.unit or "",
            self.scale or "",
            self.document_hash,
            self.source_locator or "",
        )
        return "|".join(parts)

    @property
    def observation_key(self) -> str:
        digest = hashlib.sha256(self.canonical_payload().encode("utf-8")).hexdigest()[
            :24
        ]
        return f"obs:{self.canonical_ticker}:{self.period}:{self.metric_name}:{digest}"


@dataclass
class IdentityResolutionResult:
    identity: MetricObservationIdentity
    classification: IdentityClassification
    status: IdentityStatus
    semantic_dimension: str | None
    semantic_dimension_status: str
    reason: str
    context_hits: list[SourceContext] = field(default_factory=list)


_DIMENSION_PATTERNS: dict[str, tuple[str, ...]] = {
    SemanticDimension.MARKET_VALUE.value: (
        r"dividend\s+yield\s+anualizado\s+pelo\s+valor\s+do\s+mercado",
        r"pelo\s+valor\s+do\s+mercado",
        r"valor\s+de\s+mercado",
        r"cota\s+mercado",
        r"market\s+value",
        r"market\s+price",
    ),
    SemanticDimension.NAV.value: (
        r"dividend\s+yield\s+anualizado\s+pelo\s+valor\s+patrimonial",
        r"pelo\s+valor\s+patrimonial",
        r"valor\s+patrimonial",
        r"cota\s+patrimonial",
        r"net\s+asset\s+value",
        r"\bnav\b",
    ),
    SemanticDimension.LTM.value: (
        r"dividend\s+yield\s+ltm",
        r"yield\s+ltm",
        r"\bltm\b",
    ),
}


def _normalize(text: str) -> str:
    text = (text or "").lower()
    replacements = {
        "ý": "i",
        "ÿ": "i",
        "í": "i",
        "ú": "u",
        "ù": "u",
        "ã": "a",
        "õ": "o",
        "ç": "c",
        "ô": "o",
        "ó": "o",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text)


def _value_variants(value_raw: str | None, value_parsed: str | None) -> set[str]:
    variants: set[str] = set()
    for value in (value_raw, value_parsed):
        if not value:
            continue
        normalized = _normalize(value)
        variants.add(normalized)
        if "." in normalized:
            variants.add(normalized.replace(".", ","))
    return {value for value in variants if value}


def _dimensions_in(text: str) -> set[str]:
    normalized = _normalize(text)
    result: set[str] = set()
    for dimension, patterns in _DIMENSION_PATTERNS.items():
        if any(re.search(pattern, normalized) for pattern in patterns):
            result.add(dimension)
    return result


def resolve_value_dimension(
    value_raw: str | None,
    value_parsed: str | None,
    contexts: Sequence[SourceContext],
) -> tuple[str | None, str, str, list[SourceContext]]:
    """Resolve semantic dimension using context local to the numeric value.

    This function never maps a dimension from the document merely because the
    document contains that dimension somewhere else.
    """
    variants = _value_variants(value_raw, value_parsed)
    hits: list[SourceContext] = []

    for context in contexts:
        text = _normalize(context.text)
        for variant in variants:
            pos = text.find(variant)
            if pos < 0:
                continue
            left = max(0, pos - 260)
            right = min(len(text), pos + len(variant) + 360)
            local = text[left:right]
            dims = _dimensions_in(local)
            if dims:
                hits.append(
                    SourceContext(
                        text=local,
                        locator=context.locator,
                        source_role=context.source_role,
                    )
                )

    dimension_counts: dict[str, int] = {}
    for hit in hits:
        for dimension in _dimensions_in(hit.text):
            dimension_counts[dimension] = dimension_counts.get(dimension, 0) + 1

    if not dimension_counts:
        return None, "NOT_FOUND", "no_value_localized_semantic_context", hits

    ranked = sorted(
        dimension_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    if len(ranked) == 1 or ranked[0][1] > ranked[1][1]:
        return (
            ranked[0][0],
            "RESOLVED",
            "value_localized_explicit_semantic_context",
            hits,
        )

    return (
        None,
        "REVIEW_REQUIRED",
        "multiple_semantic_dimensions_equally_supported_near_value",
        hits,
    )


def resolve_identity(
    *,
    canonical_ticker: str,
    original_ticker: str | None,
    metric_name: str,
    value_raw: str,
    value_parsed: str,
    unit: str | None,
    scale: str | None,
    period: str,
    document_hash: str,
    document_id: str | None = None,
    source_locator: str | None = None,
    lineage: str | None = None,
    contexts: Sequence[SourceContext] = (),
    sibling_values: Iterable[str] = (),
    duplicate_count: int = 1,
) -> IdentityResolutionResult:
    distinct_values = {
        str(value).strip() for value in sibling_values if str(value).strip()
    }
    has_distinct_siblings = len(distinct_values) > 1

    if duplicate_count > 1 and not has_distinct_siblings:
        identity = MetricObservationIdentity(
            canonical_ticker=canonical_ticker,
            original_ticker=original_ticker,
            metric_name=metric_name,
            value=value_parsed,
            unit=unit,
            scale=scale,
            period=period,
            semantic_dimension=None,
            document_hash=document_hash,
            document_id=document_id,
            source_locator=source_locator,
            lineage=lineage,
        )
        return IdentityResolutionResult(
            identity=identity,
            classification=IdentityClassification.EXACT_DUPLICATE,
            status=IdentityStatus.DEDUPLICABLE,
            semantic_dimension=None,
            semantic_dimension_status="NOT_REQUIRED",
            reason="same source, metric, period and value",
        )

    dimension, dim_status, reason, hits = resolve_value_dimension(
        value_raw, value_parsed, contexts
    )

    classification = (
        IdentityClassification.SEMANTICALLY_DISTINCT
        if has_distinct_siblings
        else IdentityClassification.UNIQUE
    )

    if has_distinct_siblings and dim_status == "RESOLVED":
        status = IdentityStatus.READY_WITH_DIMENSION
    elif has_distinct_siblings:
        status = IdentityStatus.BLOCKED
    elif dim_status == "RESOLVED":
        status = IdentityStatus.READY_WITH_DIMENSION
    elif dim_status == "REVIEW_REQUIRED":
        status = IdentityStatus.REVIEW
    else:
        status = IdentityStatus.READY

    identity = MetricObservationIdentity(
        canonical_ticker=canonical_ticker,
        original_ticker=original_ticker,
        metric_name=metric_name,
        value=value_parsed,
        unit=unit,
        scale=scale,
        period=period,
        semantic_dimension=dimension,
        document_hash=document_hash,
        document_id=document_id,
        source_locator=source_locator,
        lineage=lineage,
    )

    return IdentityResolutionResult(
        identity=identity,
        classification=classification,
        status=status,
        semantic_dimension=dimension,
        semantic_dimension_status=dim_status,
        reason=reason,
        context_hits=hits,
    )
