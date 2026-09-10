from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

INPUT_CSV = REPORTS / "IIP_HISTORICAL_IDENTITY_RECONSTRUCTION_R3.csv"
OUTPUT_CSV = REPORTS / "IIP_HISTORICAL_IDENTITY_RECONSTRUCTION_R4_3.csv"
OUTPUT_MD = REPORTS / "IIP_HISTORICAL_IDENTITY_RECONSTRUCTION_R4_3.md"


# ---------------------------------------------------------------------------
# Identity / event vocabulary
# ---------------------------------------------------------------------------

EVENT_WORDS = (
    "SUBSCR",
    "SUBS",
    "EMISSAO",
    "EMISS",
    "OFERTA",
    "BONIFIC",
    "BONUS",
    "DIREITO",
    "DIREITOS",
    "RECIBO",
    "FRACAO",
    "FRAC",
    "EVENT",
    "TEMP",
    "PROVIS",
    "TRANSITOR",
)

# Tickers de evento da B3 podem aparecer com extensÃµes numÃ©ricas.
# Ex.: ABCD11 / ABCD12 / ABCD13.
TICKER_RE = re.compile(r"^[A-Z]{4}[0-9]{1,2}$")


def clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def split_pipe(value: object) -> list[str]:
    text = clean(value)
    if not text:
        return []

    result = []
    for item in text.split("|"):
        item = item.strip().upper()
        if item and item not in result:
            result.append(item)

    return result


def normalize_ticker(value: object) -> str:
    text = clean(value).upper()
    text = re.sub(r"[^A-Z0-9]", "", text)
    return text


def ticker_base(ticker: str) -> str:
    """
    Retorna uma base comparÃ¡vel do ticker.

    NÃ£o usamos isso como prova de identidade.
    Serve apenas para detectar possÃ­veis famÃ­lias de tickers.
    """
    ticker = normalize_ticker(ticker)

    if not ticker:
        return ""

    match = re.match(r"^([A-Z]{4})[0-9]{1,2}$", ticker)
    if match:
        return match.group(1)

    return ticker


def ticker_number(ticker: str) -> int | None:
    ticker = normalize_ticker(ticker)
    match = re.match(r"^[A-Z]{4}([0-9]{1,2})$", ticker)

    if not match:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None


def is_possible_event_ticker(ticker: str) -> bool:
    """
    HeurÃ­stica conservadora.

    IMPORTANTE:
    O fato de um ticker terminar em 12/13 etc. NÃƒO prova sozinho
    que seja ticker temporÃ¡rio. A classificaÃ§Ã£o definitiva depende
    do contexto do evento.
    """
    ticker = normalize_ticker(ticker)

    number = ticker_number(ticker)

    if number is None:
        return False

    if number in {12, 13, 14, 15, 16, 17, 18, 19}:
        return True

    return False


def detect_event_from_text(row: dict) -> tuple[str, str]:
    """
    Procura indÃ­cios de eventos corporativos nos campos disponÃ­veis.
    """
    text_parts = []

    for key in (
        "event_class",
        "reason",
        "identity_evidence",
        "source_file",
        "historical_tickers",
        "event_tickers",
    ):
        text_parts.append(clean(row.get(key)).upper())

    text = " ".join(text_parts)

    for word in EVENT_WORDS:
        if word in text:
            return "POSSIBLE_CORPORATE_EVENT", word

    return "", ""


def build_identity_key(
    canonical_ticker: str,
    historical_tickers: list[str],
    normal_tickers: list[str],
    event_tickers: list[str],
    previous_identity_key: str,
    identity_evidence: str,
) -> tuple[str, str]:
    """
    ConstrÃ³i uma chave histÃ³rica estÃ¡vel.

    Prioridade:

    1. identidade anterior explicitamente herdada;
    2. conjunto de tickers normais/histÃ³ricos;
    3. ticker canÃ´nico;
    4. fallback determinÃ­stico.

    A chave NÃƒO usa o ticker atual isoladamente quando existem
    tickers histÃ³ricos associados.
    """

    previous = clean(previous_identity_key)

    if previous:
        return "PREVIOUS_IDENTITY", previous

    candidates = []

    for ticker in normal_tickers + historical_tickers:
        ticker = normalize_ticker(ticker)
        if ticker and ticker not in candidates:
            candidates.append(ticker)

    if candidates:
        payload = "|".join(sorted(candidates))
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
        return "TICKER_FAMILY", f"TICKER_FAMILY:{digest}"

    canonical = normalize_ticker(canonical_ticker)

    if canonical:
        return "CANONICAL_TICKER", f"TICKER:{canonical}"

    if identity_evidence:
        digest = hashlib.sha1(identity_evidence.encode("utf-8")).hexdigest()[:16]

        return "EVIDENCE_HASH", f"EVIDENCE:{digest}"

    return "NONE", ""


def classify_record(row: dict) -> dict:
    """
    R4.3

    Reconstrói identidade histórica sem assumir que:
        múltiplos tickers = múltiplos ativos.

    Prioridade da evidência:

    1. CNPJ único
    2. identidade herdada explicitamente
    3. continuidade histórica por ticker
    4. evento corporativo/provisório
    5. revisão manual

    Importante:
    ticker provisório, ticker de emissão, bônus, subscrição,
    reorganização ou mudança de código não deve automaticamente
    criar uma nova identidade econômica.
    """

    canonical = normalize_ticker(row.get("canonical_ticker"))

    historical = split_pipe(row.get("historical_tickers"))

    normal = split_pipe(row.get("normal_tickers"))

    event = split_pipe(row.get("event_tickers"))

    previous = clean(row.get("previous_identity_key"))

    identity_evidence = clean(row.get("identity_evidence"))

    cnpj_values = split_pipe(row.get("cnpjs"))

    cnpj_count = len(cnpj_values)

    # --------------------------------------------------------------
    # Consolidar tickers
    # --------------------------------------------------------------

    all_tickers = []

    for ticker in [canonical] + historical + normal + event:
        ticker = normalize_ticker(ticker)

        if ticker and ticker not in all_tickers:
            all_tickers.append(ticker)

    # --------------------------------------------------------------
    # Detectar possíveis tickers de evento
    # --------------------------------------------------------------

    inferred_event_tickers = []

    for ticker in all_tickers:
        if ticker not in event:
            if is_possible_event_ticker(ticker):
                inferred_event_tickers.append(ticker)

    for ticker in inferred_event_tickers:
        if ticker not in event:
            event.append(ticker)

    # --------------------------------------------------------------
    # Evidência textual de evento
    # --------------------------------------------------------------

    event_marker, event_word = detect_event_from_text(row)

    ticker_count = len(all_tickers)

    has_multiple_tickers = ticker_count > 1
    has_event_ticker = bool(event)

    has_previous_identity = bool(previous)

    inherited_identity = identity_evidence.upper() == "INHERITED"

    # --------------------------------------------------------------
    # Identidade herdada
    #
    # Esta regra vem ANTES da análise de múltiplos tickers.
    #
    # Exemplo:
    #
    # CVBI11 | PCIP11
    #
    # previous_identity_key:
    # TICKER:CVBI11|PCIP11
    #
    # identity_evidence:
    # INHERITED
    #
    # Isso representa continuidade histórica.
    # --------------------------------------------------------------

    if has_previous_identity and inherited_identity:
        identity_key_type = "HISTORICAL_TICKER"

        identity_key = previous

        event_class = "TICKER_HISTORY_RENAME_OR_CONTINUITY"

        decision = "IDENTITY_RESOLVED"

        confidence = "HIGH"

        reason = (
            "historical identity inherited from previous "
            "canonicalization; multiple tickers are preserved "
            "as historical continuity rather than separate assets"
        )

    # --------------------------------------------------------------
    # CNPJ único
    # --------------------------------------------------------------

    elif cnpj_count == 1:
        identity_key_type = "CNPJ"

        identity_key = f"CNPJ:{cnpj_values[0]}"

        event_class = "SINGLE_LEGAL_ENTITY"

        decision = "IDENTITY_RESOLVED"

        confidence = "HIGH"

        reason = "single CNPJ provides strong legal identity evidence"

    # --------------------------------------------------------------
    # Múltiplos tickers sem identidade herdada
    # --------------------------------------------------------------

    elif has_multiple_tickers:
        if has_event_ticker or event_marker:
            event_class = "MULTI_TICKER_WITH_POSSIBLE_EVENT"

            decision = "REVIEW_REQUIRED"

            confidence = "MEDIUM"

            reason = (
                "multiple tickers detected with possible "
                "corporate/event ticker; preserve all tickers "
                "and require event validation"
            )

        else:
            event_class = "MULTI_TICKER_REQUIRES_EVENT_ANALYSIS"

            decision = "REVIEW_REQUIRED"

            confidence = "MEDIUM"

            reason = (
                "multiple tickers detected without sufficient "
                "continuity or legal identity evidence"
            )

        identity_key_type = "TICKER_SET"

        identity_key = "TICKER:" + "|".join(sorted(set(all_tickers)))

    # --------------------------------------------------------------
    # Ticker de evento isolado
    # --------------------------------------------------------------

    elif has_event_ticker:
        identity_key_type = "EVENT_TICKER"

        identity_key = f"TICKER:{canonical}" if canonical else ""

        event_class = "POSSIBLE_EVENT_TICKER"

        decision = "REVIEW_REQUIRED"

        confidence = "MEDIUM"

        reason = (
            "possible temporary/event ticker detected; "
            "must not be persisted as a separate asset "
            "automatically"
        )

    # --------------------------------------------------------------
    # Ticker único
    # --------------------------------------------------------------

    elif canonical:
        identity_key_type = "CANONICAL_TICKER"

        identity_key = f"TICKER:{canonical}"

        event_class = "SINGLE_TICKER"

        decision = "REVIEW_REQUIRED"

        confidence = "LOW"

        reason = (
            "single ticker without sufficient legal identity "
            "evidence for automatic high-confidence resolution"
        )

    # --------------------------------------------------------------
    # Sem identidade suficiente
    # --------------------------------------------------------------

    else:
        identity_key_type = "NONE"

        identity_key = ""

        event_class = "INSUFFICIENT_IDENTITY"

        decision = "REVIEW_REQUIRED"

        confidence = "LOW"

        reason = "no usable canonical ticker or identity evidence"

    # --------------------------------------------------------------
    # Resultado
    # --------------------------------------------------------------

    return {
        "decision": decision,
        "confidence": confidence,
        "identity_key_type": identity_key_type,
        "identity_key": identity_key,
        "canonical_ticker": canonical,
        "historical_tickers": "|".join(sorted(set(historical))),
        "normal_tickers": "|".join(sorted(set(normal))),
        "event_tickers": "|".join(sorted(set(event))),
        "ticker_count": str(ticker_count),
        "cnpjs": "|".join(cnpj_values),
        "cnpj_count": str(cnpj_count),
        "cnpj_status": clean(row.get("cnpj_status")),
        "previous_identity_key": previous,
        "event_class": event_class,
        "event_marker": event_word,
        "identity_evidence": identity_evidence,
        "reason": reason,
    }


def main() -> int:
    print("=" * 90)
    print("IIP HISTORICAL IDENTITY RECONSTRUCTION R4.3")
    print("=" * 90)

    if not INPUT_CSV.exists():
        print(f"ERROR: input not found: {INPUT_CSV}")
        return 1

    with INPUT_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        source_rows = list(reader)

    output_rows = []

    for index, row in enumerate(source_rows, start=1):
        result = classify_record(row)

        output_rows.append(
            {
                "input_row": str(index),
                "source_file": clean(row.get("source_file")),
                "source_row": clean(row.get("source_row")),
                **result,
                "identity_evidence": clean(row.get("identity_evidence")),
                "corporate_event_source": clean(row.get("event_class")),
                "source_reason": clean(row.get("reason")),
            }
        )

    fieldnames = [
        "input_row",
        "source_file",
        "source_row",
        "decision",
        "confidence",
        "identity_key_type",
        "identity_key",
        "canonical_ticker",
        "historical_tickers",
        "normal_tickers",
        "event_tickers",
        "ticker_count",
        "cnpjs",
        "cnpj_count",
        "cnpj_status",
        "previous_identity_key",
        "event_class",
        "event_marker",
        "reason",
        "identity_evidence",
        "corporate_event_source",
        "source_reason",
    ]

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(output_rows)

    decisions = Counter(row["decision"] for row in output_rows)

    confidence = Counter(row["confidence"] for row in output_rows)

    events = Counter(row["event_class"] for row in output_rows)

    identity_keys = Counter(
        row["identity_key"] for row in output_rows if row["identity_key"]
    )

    multi_ticker = sum(1 for row in output_rows if int(row["ticker_count"] or 0) > 1)

    possible_events = sum(
        1
        for row in output_rows
        if row["event_tickers"] or "EVENT" in row["event_class"]
    )

    md_lines = [
        "# IIP HISTORICAL IDENTITY RECONSTRUCTION R4.3",
        "",
        "## Safety",
        "",
        "- Mode: READ-ONLY",
        "- Vault modified: NO",
        "- Persistence executed: NO",
        "- KnowledgeBridge executed: NO",
        "- Repository writes: NO",
        "",
        "## Input",
        "",
        f"- Source: `{INPUT_CSV}`",
        f"- Input records: {len(source_rows)}",
        "",
        "## Result",
        "",
        f"- IDENTITY_RESOLVED: {decisions.get('IDENTITY_RESOLVED', 0)}",
        f"- REVIEW_REQUIRED: {decisions.get('REVIEW_REQUIRED', 0)}",
        f"- BLOCKED: {decisions.get('BLOCKED', 0)}",
        "",
        f"- HIGH confidence: {confidence.get('HIGH', 0)}",
        f"- MEDIUM confidence: {confidence.get('MEDIUM', 0)}",
        f"- LOW confidence: {confidence.get('LOW', 0)}",
        "",
        f"- Unique identity keys: {len(identity_keys)}",
        f"- Multi-ticker records: {multi_ticker}",
        f"- Possible event records: {possible_events}",
        "",
        "## Event handling",
        "",
        "The reconstruction preserves historical tickers instead of "
        "treating a ticker change automatically as a new asset.",
        "",
        "Possible event tickers are retained and marked for review. "
        "The system does not automatically persist them as independent "
        "economic identities.",
        "",
        "This is intentionally conservative: ticker numbering alone "
        "does not prove a corporate event.",
        "",
        "## Important case: CVBI11 -> PCIP11",
        "",
        "If the source evidence contains both CVBI11 and PCIP11 under "
        "the same historical identity, the reconstruction preserves "
        "both tickers in the same identity family.",
        "",
        "The current ticker does not erase the historical ticker.",
        "",
        "## Event classes",
        "",
    ]

    for key, value in sorted(events.items()):
        md_lines.append(f"- {key}: {value}")

    md_lines.extend(
        [
            "",
            "## Next gate",
            "",
            "No record from this stage is persisted automatically.",
            "",
            "Records involving multiple tickers or possible corporate "
            "events must pass the event/identity validation gate before "
            "historical persistence.",
            "",
        ]
    )

    OUTPUT_MD.write_text(
        "\n".join(md_lines),
        encoding="utf-8",
    )

    print(f"Input records              : {len(source_rows)}")
    print(f"IDENTITY_RESOLVED          : {decisions.get('IDENTITY_RESOLVED', 0)}")
    print(f"REVIEW_REQUIRED            : {decisions.get('REVIEW_REQUIRED', 0)}")
    print(f"BLOCKED                    : {decisions.get('BLOCKED', 0)}")
    print(f"HIGH confidence            : {confidence.get('HIGH', 0)}")
    print(f"MEDIUM confidence          : {confidence.get('MEDIUM', 0)}")
    print(f"LOW confidence             : {confidence.get('LOW', 0)}")
    print(f"Unique identity keys       : {len(identity_keys)}")
    print(f"Multi-ticker records       : {multi_ticker}")
    print(f"Possible event records     : {possible_events}")
    print(f"CSV                        : {OUTPUT_CSV}")
    print(f"MD                         : {OUTPUT_MD}")
    print()
    print("Vault modified             : NO")
    print("Persistence executed       : NO")
    print("KnowledgeBridge executed   : NO")
    print("Repository writes          : NO")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
