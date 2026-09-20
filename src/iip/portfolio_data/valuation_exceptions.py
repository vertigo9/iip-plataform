"""Exceções metodológicas de valuation: declaradas, com motivo, data e revisão.

A classificação cadastral (setor, segmento) DESCREVE o ativo; qual método de valuation é
apropriado para ele é outra pergunta. Sem este arquivo, as palavras do setor decidiam sozinhas
o método líder e as exclusões (``valuation_methods``): corrigir um setor no registro podia
trocar, em silêncio, o método e a decisão de uma empresa. Aqui uma exceção é DADO explícito,
versionado e rastreável, nunca um ``if ticker == ...`` no código.

O contrato (``02_Portfolio/Excecoes_Valuation.json``):
  - ``schema``, ``version``, ``origin`` e a lista ``exceptions``; o conteúdo tem um hash que os
    resultados podem citar. Chave ou valor inválido é ``ValueError`` com o motivo, nunca um
    padrão silencioso. Arquivo AUSENTE = sem exceções (as regras por setor seguem valendo).
  - cada exceção: ``id`` único, ``ticker``, ``method`` (Graham ou Bazin), ``action``
    (``exclude`` ou ``lead``), ``reason``, ``decided_on``, ``decided_by`` e ``review_by``
    (a data de revisão é OBRIGATÓRIA).
  - escopo da primeira versão: só AÇÕES (o ticker precisa ser uma ação do registro).
  - no máximo uma exceção por (ticker, método) e um só método líder por ticker.

Precedência: uma exceção explícita prevalece sobre as regras por palavra-chave do setor.
``exclude`` tira o método da lista (com o motivo citado no resultado); ``lead`` coloca o método
em primeiro, seja qual for a ordem que o setor daria. A ordem dos demais métodos é mantida.

Vencimento: passada a ``review_by`` a exceção CONTINUA aplicada, e é sinalizada como vencida
(na nota e no comando). Nunca é removida nem reativada automaticamente.

O ``reason`` descreve a PREMISSA METODOLÓGICA (por que o método não serve ou lidera), não uma
conclusão sobre o valor justo nem sobre o que fazer com o ativo. O resultado recalculado é a
consequência da regra aplicada, com a exceção e o hash citados.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

EXCEPTIONS_RELATIVE_PATH = Path("02_Portfolio") / "Excecoes_Valuation.json"
SCHEMA = "valuation-exceptions-1"
ACTIONS = ("exclude", "lead")
# só os métodos que existem para ações e têm calculador
METHODS = ("Graham", "Bazin")

_ROOT_KEYS = frozenset({"type", "schema", "version", "origin", "exceptions"})
_ITEM_KEYS = frozenset(
    {
        "id",
        "ticker",
        "method",
        "action",
        "reason",
        "decided_on",
        "decided_by",
        "review_by",
    }
)


@dataclass(frozen=True)
class MethodException:
    id: str
    ticker: str
    method: str
    action: str
    reason: str
    decided_on: str
    decided_by: str
    review_by: str

    def overdue(self, today: _dt.date) -> bool:
        return _dt.date.fromisoformat(self.review_by) < today

    def citation(self) -> str:
        """O que o resultado mostra quando esta exceção decide algo."""
        return (
            f"exceção metodológica {self.id}: {self.reason} (decidida em {self.decided_on} "
            f"por {self.decided_by}; revisão até {self.review_by})"
        )


@dataclass(frozen=True)
class ValuationExceptions:
    version: str
    origin: str
    items: tuple[MethodException, ...] = field(default_factory=tuple)

    @property
    def content_hash(self) -> str:
        """Hash do que define os resultados. Duas rodadas com o mesmo hash usaram as mesmas
        exceções."""
        canonical = json.dumps(
            {
                "version": self.version,
                "exceptions": [_item_payload(i) for i in self.items],
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def for_ticker(self, ticker: str) -> tuple[MethodException, ...]:
        target = ticker.strip().upper()
        return tuple(i for i in self.items if i.ticker == target)

    def exclusion(self, ticker: str, method: str) -> MethodException | None:
        return next(
            (
                i
                for i in self.for_ticker(ticker)
                if i.action == "exclude" and i.method == method
            ),
            None,
        )

    def leader(self, ticker: str) -> MethodException | None:
        return next((i for i in self.for_ticker(ticker) if i.action == "lead"), None)

    def overdue(self, today: _dt.date) -> tuple[MethodException, ...]:
        return tuple(i for i in self.items if i.overdue(today))


NO_EXCEPTIONS = ValuationExceptions("nenhuma", "sem arquivo de exceções", ())

DEFAULT_EXCEPTIONS = ValuationExceptions(
    version="2026-09-20.1",
    origin="declaradas pelo usuário; cada uma com motivo metodológico e data de revisão",
    items=(
        MethodException(
            id="CSUD3-graham-excluir",
            ticker="CSUD3",
            method="Graham",
            action="exclude",
            reason=(
                "o Graham parte do valor patrimonial (LPA x VPA), que não representa bem uma "
                "empresa de ativos majoritariamente intangíveis (processamento de pagamentos "
                "e serviços); restrição metodológica, não uma conclusão sobre o valor justo "
                "do ativo"
            ),
            decided_on="2026-09-20",
            decided_by="usuário",
            review_by="2027-03-20",
        ),
    ),
)


# --- validação -----------------------------------------------------------------------------


def _fail(label: str, reason: str) -> ValueError:
    return ValueError(f"exceção {label!r}: {reason}")


def _parse_date(label: str, name: str, value: object) -> _dt.date:
    if not isinstance(value, str):
        raise _fail(label, f"{name} precisa ser uma data AAAA-MM-DD")
    try:
        return _dt.date.fromisoformat(value)
    except ValueError as exc:
        raise _fail(label, f"{name} {value!r} não é AAAA-MM-DD") from exc


def validate(
    exceptions: ValuationExceptions, *, equity_tickers: set[str] | None = None
) -> None:
    """Levanta ``ValueError`` com o motivo. ``equity_tickers`` (as ações do registro) liga a
    checagem de escopo; sem ele só a forma é validada."""
    if not exceptions.version.strip():
        raise ValueError("o conjunto de exceções precisa de uma versão")
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    leaders: dict[str, str] = {}
    for item in exceptions.items:
        label = item.id
        if not item.id.strip():
            raise ValueError("exceção sem id")
        if item.id in seen_ids:
            raise _fail(label, "id repetido")
        seen_ids.add(item.id)
        if item.method not in METHODS:
            raise _fail(label, f"método {item.method!r} (use {' ou '.join(METHODS)})")
        if item.action not in ACTIONS:
            raise _fail(label, f"action {item.action!r} (use {' ou '.join(ACTIONS)})")
        for name in ("ticker", "reason", "decided_by"):
            if not getattr(item, name).strip():
                raise _fail(label, f"{name} é obrigatório")
        if item.ticker != item.ticker.strip().upper():
            raise _fail(label, f"ticker {item.ticker!r} precisa estar em maiúsculas")
        decided = _parse_date(label, "decided_on", item.decided_on)
        review = _parse_date(label, "review_by", item.review_by)
        if review < decided:
            raise _fail(label, "review_by é anterior a decided_on")
        pair = (item.ticker, item.method)
        if pair in seen_pairs:
            raise _fail(
                label, f"já existe uma exceção para {item.ticker} e {item.method}"
            )
        seen_pairs.add(pair)
        if item.action == "lead":
            if item.ticker in leaders:
                raise _fail(
                    label,
                    f"{item.ticker} já tem um método líder declarado ({leaders[item.ticker]})",
                )
            leaders[item.ticker] = item.method
        if equity_tickers is not None and item.ticker not in equity_tickers:
            raise _fail(
                label,
                f"{item.ticker} não é uma ação do registro (esta versão só cobre ações)",
            )


# --- serialização --------------------------------------------------------------------------


def _item_payload(item: MethodException) -> dict:
    return {
        "id": item.id,
        "ticker": item.ticker,
        "method": item.method,
        "action": item.action,
        "reason": item.reason,
        "decided_on": item.decided_on,
        "decided_by": item.decided_by,
        "review_by": item.review_by,
    }


def _equity_tickers() -> set[str]:
    # import tardio: iip.portfolio importa o avaliador, que importa este módulo
    from iip.portfolio.registry import ALL_PORTFOLIO_ASSETS

    return {a.ticker for a in ALL_PORTFOLIO_ASSETS if a.asset_class == "equity"}


def save_exceptions(vault_path: str | Path, exceptions: ValuationExceptions) -> Path:
    validate(exceptions, equity_tickers=_equity_tickers())
    path = Path(vault_path) / EXCEPTIONS_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "type": "valuation_method_exceptions",
        "schema": SCHEMA,
        "version": exceptions.version,
        "origin": exceptions.origin,
        "exceptions": [_item_payload(i) for i in exceptions.items],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _parse_item(raw: object) -> MethodException:
    if not isinstance(raw, dict):
        raise ValueError(f"exceção mal formada (não é um objeto): {raw!r}")
    label = str(raw.get("id", "?"))
    unknown = set(raw) - _ITEM_KEYS
    if unknown:
        raise _fail(label, f"chave desconhecida {sorted(unknown)}")
    missing = sorted(_ITEM_KEYS - set(raw))
    if missing:
        raise _fail(label, f"faltam as chaves {missing}")
    if not all(isinstance(raw[k], str) for k in _ITEM_KEYS):
        raise _fail(label, "todos os campos são texto")
    return MethodException(**{k: raw[k] for k in _ITEM_KEYS})


def load_exceptions(vault_path: str | Path) -> ValuationExceptions | None:
    """As exceções gravadas, ou ``None`` se não há arquivo. Um arquivo que existe mas está
    errado levanta ``ValueError`` com o motivo: nunca cai em silêncio para 'sem exceções'.
    """
    path = Path(vault_path) / EXCEPTIONS_RELATIVE_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: não é um JSON válido ({exc})") from exc
    try:
        if not isinstance(raw, dict):
            raise ValueError("a raiz precisa ser um objeto")
        unknown = set(raw) - _ROOT_KEYS
        if unknown:
            raise ValueError(f"chave desconhecida na raiz {sorted(unknown)}")
        if raw.get("schema") != SCHEMA:
            raise ValueError(f"schema {raw.get('schema')!r}, esperado {SCHEMA!r}")
        if not isinstance(raw.get("exceptions"), list):
            raise ValueError("`exceptions` precisa ser uma lista")
        loaded = ValuationExceptions(
            version=str(raw["version"]),
            origin=str(raw.get("origin", "")),
            items=tuple(_parse_item(i) for i in raw["exceptions"]),
        )
        validate(loaded, equity_tickers=_equity_tickers())
    except KeyError as exc:
        raise ValueError(f"{path}: falta a chave {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    return loaded


def exceptions_for(vault_path: str | Path | None) -> ValuationExceptions:
    """As exceções a aplicar num cálculo: as do vault, ou ``NO_EXCEPTIONS`` se não há arquivo
    (ou vault). Arquivo inválido levanta ``ValueError``."""
    if not vault_path:
        return NO_EXCEPTIONS
    return load_exceptions(vault_path) or NO_EXCEPTIONS
