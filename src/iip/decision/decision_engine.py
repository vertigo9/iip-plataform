"""Decision engine: evidence -> score -> verdict."""

from __future__ import annotations

from typing import Any

from .models import Decision, IntelligenceInput, Verdict
from .scoring import composite_score, confidence_score
from .thesis_exit_gate import ThesisExitState


def verdict_for(item: IntelligenceInput, score: float) -> Verdict:
    thesis = item.thesis_signal.casefold()

    if thesis == "mudança de tese":
        return Verdict.REDUZIR if score < 7 else Verdict.AGUARDAR

    if score >= 8.5:
        return Verdict.COMPRAR
    if score >= 7.0:
        return Verdict.MANTER
    if score >= 5.0:
        return Verdict.AGUARDAR
    if score >= 3.5:
        return Verdict.REDUZIR
    return Verdict.VENDER


def decide(item: IntelligenceInput) -> Decision:
    score = composite_score(item)
    confidence = confidence_score(item)

    verdict = verdict_for(item, score)

    thesis_exit = getattr(item, "thesis_exit", None)
    thesis_exit_reason = None

    if thesis_exit is not None:
        thesis_exit_reason = (
            f"thesis_exit={thesis_exit.state.value}",
            f"thesis_exit_failed={','.join(thesis_exit.failed_gates) or 'none'}",
            f"thesis_exit_attention={','.join(thesis_exit.attention_gates) or 'none'}",
        )

        if thesis_exit.state is ThesisExitState.BREAK:
            verdict = Verdict.VENDER

    reasons = (
        f"composite_score={score:.2f}",
        f"confidence={confidence:.2f}",
        f"thesis={item.thesis_signal}",
        f"risk={item.risk_level}",
    )

    if thesis_exit_reason is not None:
        reasons = reasons + thesis_exit_reason

    return Decision(
        ticker=item.ticker.upper(),
        verdict=verdict,
        score=score,
        confidence=confidence,
        reasons=reasons,
        evidence=item.evidence,
        thesis_exit=thesis_exit,
    )


def ingest_fii_harvest(
    fetched: Any,
    metrics_payload: dict[str, float],
) -> list[Any]:
    """Estende o motor para converter e ingerir colheitas brutas de FII via contratos de inteligência."""
    import hashlib
    from datetime import datetime, timezone
    from iip.decision.models import MetricObservationIdentity, SemanticDimension

    raw_body = getattr(fetched, "body", b"")
    payload_hash = hashlib.sha256(raw_body).hexdigest()[:16] if raw_body else "0" * 16

    ticker = getattr(fetched, "ticker", None)
    if not ticker and hasattr(fetched, "fii") and isinstance(fetched.fii, dict):
        ticker = fetched.fii.get("ticker")
    ticker = str(ticker or "UNKNOWN").upper()

    final_url = str(getattr(fetched, "final_url", getattr(fetched, "target", "")))
    status_code = getattr(fetched, "status_code", 200)
    observed_at = getattr(fetched, "fetched_at", datetime.now(timezone.utc))

    observations = []
    for metric_name, value in metrics_payload.items():
        metric_upper = metric_name.upper()
        semantic_dim = (
            SemanticDimension.NAV
            if metric_upper in ["VP_COTA", "VPA", "PATRIMONIO_LIQUIDO"]
            else SemanticDimension.MARKET_VALUE
        )
        obs = MetricObservationIdentity(
            ticker=ticker,
            metric_type=metric_upper,
            semantic_dimension=semantic_dim,
            value=float(value),
            confidence_score=0.95 if status_code == 200 else 0.0,
            source_provider="b3",
            source_url=final_url,
            raw_payload_hash=payload_hash,
            observed_at=observed_at,
        )
        observations.append(obs)
    return observations


def ingest_equity_harvest(
    fetched: Any,
    metrics_payload: dict[str, float],
) -> list[Any]:
    """Estende o motor para converter e ingerir colheitas brutas de Ações (Equities)."""
    import hashlib
    from datetime import datetime, timezone
    from iip.decision.models import MetricObservationIdentity, SemanticDimension

    raw_body = getattr(fetched, "body", b"")
    payload_hash = hashlib.sha256(raw_body).hexdigest()[:16] if raw_body else "0" * 16

    ticker = getattr(fetched, "ticker", None)
    if not ticker and hasattr(fetched, "equity") and isinstance(fetched.equity, dict):
        ticker = fetched.equity.get("ticker")
    ticker = str(ticker or "UNKNOWN").upper()

    final_url = str(getattr(fetched, "final_url", getattr(fetched, "target", "")))
    status_code = getattr(fetched, "status_code", 200)
    observed_at = getattr(fetched, "fetched_at", datetime.now(timezone.utc))

    observations = []
    for metric_name, value in metrics_payload.items():
        metric_upper = metric_name.upper()
        semantic_dim = (
            SemanticDimension.NAV
            if metric_upper in ["P_L", "PE", "LPA", "ROIC", "ROE", "MARGEM_LIQUIDA", "VP_COTA", "VPA"]
            else SemanticDimension.MARKET_VALUE
        )
        obs = MetricObservationIdentity(
            ticker=ticker,
            metric_type=metric_upper,
            semantic_dimension=semantic_dim,
            value=float(value),
            confidence_score=0.95 if status_code == 200 else 0.0,
            source_provider="b3",
            source_url=final_url,
            raw_payload_hash=payload_hash,
            observed_at=observed_at,
        )
        observations.append(obs)
    return observations


def ingest_etf_harvest(
    fetched: Any,
    metrics_payload: dict[str, float],
) -> list[Any]:
    """Estende o motor para converter e ingerir colheitas brutas de ETFs / Fundos de Índice."""
    import hashlib
    from datetime import datetime, timezone
    from iip.decision.models import MetricObservationIdentity, SemanticDimension

    raw_body = getattr(fetched, "body", b"")
    payload_hash = hashlib.sha256(raw_body).hexdigest()[:16] if raw_body else "0" * 16

    ticker = getattr(fetched, "ticker", None)
    if not ticker and hasattr(fetched, "etf") and isinstance(fetched.etf, dict):
        ticker = fetched.etf.get("ticker")
    ticker = str(ticker or "UNKNOWN").upper()

    final_url = str(getattr(fetched, "final_url", getattr(fetched, "target", "")))
    status_code = getattr(fetched, "status_code", 200)
    observed_at = getattr(fetched, "fetched_at", datetime.now(timezone.utc))

    observations = []
    for metric_name, value in metrics_payload.items():
        metric_upper = metric_name.upper()
        semantic_dim = (
            SemanticDimension.NAV
            if metric_upper in ["TAXA_ADMINISTRACAO", "TER", "TRACKING_ERROR", "AUM", "PATRIMONIO_LIQUIDO", "VP_COTA", "VPA"]
            else SemanticDimension.MARKET_VALUE
        )
        obs = MetricObservationIdentity(
            ticker=ticker,
            metric_type=metric_upper,
            semantic_dimension=semantic_dim,
            value=float(value),
            confidence_score=0.95 if status_code == 200 else 0.0,
            source_provider="b3",
            source_url=final_url,
            raw_payload_hash=payload_hash,
            observed_at=observed_at,
        )
        observations.append(obs)
    return observations


def ingest_fixed_income_harvest(
    fetched: Any,
    metrics_payload: dict[str, float],
) -> list[Any]:
    """Estende o motor para converter e ingerir colheitas de Renda Fixa, FI-Agro e FI-Infra."""
    import hashlib
    from datetime import datetime, timezone
    from iip.decision.models import MetricObservationIdentity, SemanticDimension

    raw_body = getattr(fetched, "body", b"")
    payload_hash = hashlib.sha256(raw_body).hexdigest()[:16] if raw_body else "0" * 16

    ticker = getattr(fetched, "ticker", None)
    if not ticker and hasattr(fetched, "asset") and isinstance(fetched.asset, dict):
        ticker = fetched.asset.get("ticker")
    ticker = str(ticker or "UNKNOWN").upper()

    final_url = str(getattr(fetched, "final_url", getattr(fetched, "target", "")))
    status_code = getattr(fetched, "status_code", 200)
    observed_at = getattr(fetched, "fetched_at", datetime.now(timezone.utc))

    observations = []
    for metric_name, value in metrics_payload.items():
        metric_upper = metric_name.upper()
        semantic_dim = (
            SemanticDimension.NAV
            if metric_upper in ["TAXA_INDICATIVA", "DURATION", "CUPOM", "SPREAD", "VP_COTA", "VPA", "PATRIMONIO_LIQUIDO"]
            else SemanticDimension.MARKET_VALUE
        )
        obs = MetricObservationIdentity(
            ticker=ticker,
            metric_type=metric_upper,
            semantic_dimension=semantic_dim,
            value=float(value),
            confidence_score=0.95 if status_code == 200 else 0.0,
            source_provider="cvm",
            source_url=final_url,
            raw_payload_hash=payload_hash,
            observed_at=observed_at,
        )
        observations.append(obs)
    return observations