"""Leitura do que já existe no vault para a decisão da carteira: a evidência a citar e a
decisão anterior de cada ativo.

Só lê arquivos que o projeto mesmo gravou (``ObsidianRepository.save_evidence`` e
``save_decision``, frontmatter simples ``chave: valor``). Nada aqui cria evidência.
"""

from __future__ import annotations

from pathlib import Path

# quantas evidências uma decisão cita: as mais recentes de fontes diferentes, não as N mais
# recentes de uma só (o Informe Diário mensal sozinho encheria a lista)
MAX_EVIDENCE = 3


def _frontmatter(path: Path) -> dict[str, str]:
    """Só o bloco entre os dois ``---`` do topo, como ``chave -> valor`` (as listas do
    ``relevant_facts`` entram como linhas ``- ...`` e são guardadas em ``_facts``)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: dict[str, str] = {}
    facts: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("- "):
            facts.append(line[2:].strip())
        elif ":" in line:
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip()
    data["_facts"] = "\n".join(facts)
    return data


def _provider(meta: dict[str, str]) -> str:
    for fact in meta.get("_facts", "").splitlines():
        if fact.startswith("provider="):
            return fact.removeprefix("provider=")
    return meta.get("source_type", "")


def find_evidence_ids(
    vault_path: str | Path, ticker: str, *, limit: int = MAX_EVIDENCE
) -> tuple[str, ...]:
    """Ids de evidência que existem de fato em ``04_Evidence`` para ``ticker`` (comparação
    exata do campo ``ticker``, não do nome do arquivo): a mais recente de cada fonte, e das
    ``limit`` fontes de dado mais novo. Vazio se o ativo não tem nenhuma."""
    directory = Path(vault_path) / "04_Evidence"
    wanted = ticker.strip().upper()
    if not directory.is_dir():
        return ()
    newest_by_provider: dict[str, tuple[str, str]] = {}
    # o nome do arquivo carrega o ticker: só esses são abertos (a pasta tem milhares)
    for path in directory.glob(f"*{wanted}*.md"):
        meta = _frontmatter(path)
        if meta.get("type") != "evidence" or meta.get("ticker", "").upper() != wanted:
            continue
        evidence_id = meta.get("evidence_id", "")
        if not evidence_id:
            continue
        key = (meta.get("date", ""), evidence_id)
        provider = _provider(meta)
        if provider not in newest_by_provider or key > newest_by_provider[provider]:
            newest_by_provider[provider] = key
    newest = sorted(newest_by_provider.values(), reverse=True)[:limit]
    return tuple(evidence_id for _, evidence_id in newest)


def previous_decision_verdict(
    vault_path: str | Path, ticker: str, *, before
) -> str | None:
    """O veredito da decisão mais recente de ``ticker`` com data ANTERIOR a ``before``
    (uma ``datetime.date``), ou ``None``. Só valores que o vault de conhecimento
    reconhece."""
    from iip.knowledge.models import Verdict

    directory = Path(vault_path) / "03_Decisions"
    wanted = ticker.strip().upper()
    if not directory.is_dir():
        return None
    valid = {v.value for v in Verdict}
    best: tuple[str, str] | None = None
    cutoff = before.isoformat()
    for path in directory.glob(f"DEC-*{wanted}*.md"):
        meta = _frontmatter(path)
        if meta.get("type") != "decision" or meta.get("ticker", "").upper() != wanted:
            continue
        date, verdict = meta.get("date", ""), meta.get("new_verdict", "")
        if verdict not in valid or not date or date >= cutoff:
            continue
        if best is None or date > best[0]:
            best = (date, verdict)
    return best[1] if best else None
