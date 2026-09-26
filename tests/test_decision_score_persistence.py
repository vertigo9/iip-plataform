"""Persistência durável do ``Decision.score`` na nota ``DEC-*`` (campo ``decision_score``).

O score gravado é o mesmo que o motor produziu -- sem recálculo, sem arredondar de novo --, as
notas antigas (sem o campo) continuam válidas e legíveis, e gravar o score não muda nada do que o
``batch_decide`` decide.
"""

from datetime import date

import pytest

import iip.decision.decision_engine as decision_engine
from iip.config import get_settings
from iip.decision.knowledge_bridge import to_knowledge_decision
from iip.decision.models import Decision as EngineDecision
from iip.decision.models import EvidenceRef
from iip.decision.models import Verdict as EngineVerdict
from iip.knowledge.models import Decision as KnowledgeDecision
from iip.knowledge.models import Verdict as KnowledgeVerdict
from iip.knowledge.repository import ObsidianRepository
from iip.portfolio.batch_decide import _Deps, decide_portfolio
from iip.portfolio.evidence_lookup import previous_decision_verdict
from iip.portfolio.registry import PortfolioAsset
from iip.sources.tesouro_direto import NtnbRate

TODAY = date(2026, 9, 20)
RATE = NtnbRate(
    reference_date=date(2026, 9, 17), maturity=date(2060, 8, 15), real_yield=0.073
)
# um valor com muitas casas: prova que nada arredonda no caminho
PRECISE_SCORE = 6.915318234567891


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _engine_decision(score=PRECISE_SCORE, verdict=EngineVerdict.MANTER):
    return EngineDecision(
        ticker="cxse3",
        verdict=verdict,
        score=score,
        confidence=0.57,
        reasons=(f"composite_score={score:.2f}",),
        evidence=(EvidenceRef("EV-CXSE3-1"),),
    )


def _knowledge_decision(**kw):
    return KnowledgeDecision(
        decision_id=kw.pop("decision_id", "DEC-CXSE3-2026-09-20"),
        ticker="CXSE3",
        date=TODAY,
        new_verdict=KnowledgeVerdict.MANTER,
        confidence=0.57,
        **kw,
    )


def _old_format_note(vault, ticker, day, verdict):
    """Uma nota como as gravadas antes do campo existir (sem ``decision_score``)."""
    path = vault / "03_Decisions" / f"DEC-{ticker}-{day}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntype: decision\ndecision_id: DEC-{ticker}-{day}\nticker: {ticker}\n"
        f"date: {day}\nnew_verdict: {verdict}\nconfidence: 0.5\n---\n",
        encoding="utf-8",
    )
    return path


# --- modelo e conversor -----------------------------------------------------------


def test_the_knowledge_decision_score_defaults_to_none():
    assert _knowledge_decision().decision_score is None


def test_the_converter_copies_the_engine_score_exactly():
    engine = _engine_decision()

    knowledge = to_knowledge_decision(
        engine, decision_id="DEC-CXSE3-2026-09-20", date=TODAY
    )

    assert knowledge.decision_score == engine.score == PRECISE_SCORE


# --- gravação e leitura -----------------------------------------------------------


def test_the_saved_note_carries_the_score_and_reads_it_back_exactly(tmp_path):
    repo = ObsidianRepository(tmp_path)
    engine = _engine_decision()
    knowledge = to_knowledge_decision(
        engine, decision_id="DEC-CXSE3-2026-09-20", date=TODAY
    )

    path = repo.save_decision(knowledge)

    assert f"decision_score: {PRECISE_SCORE!r}\n" in path.read_text(encoding="utf-8")
    # score antes da persistência == score recuperado da nota
    assert ObsidianRepository.read_decision_score(path) == engine.score


def test_a_decision_without_score_writes_exactly_the_previous_format(tmp_path):
    path = ObsidianRepository(tmp_path).save_decision(_knowledge_decision())

    assert path.read_text(encoding="utf-8") == (
        "---\n"
        "type: decision\n"
        "decision_id: DEC-CXSE3-2026-09-20\n"
        "ticker: CXSE3\n"
        "date: 2026-09-20\n"
        "new_verdict: MANTER\n"
        "confidence: 0.57\n"
        "---\n"
    )


def test_a_historical_note_without_the_field_reads_as_none(tmp_path):
    path = _old_format_note(tmp_path, "CXSE3", "2026-09-18", "MANTER")

    assert ObsidianRepository.read_decision_score(path) is None


def test_the_reader_refuses_what_is_not_a_decision_or_not_a_number(tmp_path):
    evidence = tmp_path / "EV-1.md"
    evidence.write_text("---\ntype: evidence\nticker: CXSE3\n---\n", encoding="utf-8")
    broken = tmp_path / "DEC-X.md"
    broken.write_text(
        "---\ntype: decision\nticker: X\ndecision_score: alto\n---\n", encoding="utf-8"
    )
    plain = tmp_path / "plain.md"
    plain.write_text("sem front matter\n", encoding="utf-8")

    for path in (evidence, broken, plain):
        with pytest.raises(ValueError):
            ObsidianRepository.read_decision_score(path)


@pytest.mark.parametrize("raw", ["nan", "inf", "-inf"])
def test_the_reader_refuses_a_non_finite_score(tmp_path, raw):
    path = tmp_path / "DEC-X.md"
    path.write_text(
        f"---\ntype: decision\nticker: X\ndecision_score: {raw}\n---\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="finite"):
        ObsidianRepository.read_decision_score(path)


def test_the_previous_verdict_reads_old_and_new_notes_alike(tmp_path):
    _old_format_note(tmp_path, "CXSE3", "2026-09-17", "REDUZIR")
    ObsidianRepository(tmp_path).save_decision(
        KnowledgeDecision(
            decision_id="DEC-CXSE3-2026-09-19",
            ticker="CXSE3",
            date=date(2026, 9, 19),
            new_verdict=KnowledgeVerdict.MANTER,
            decision_score=PRECISE_SCORE,
        )
    )

    assert previous_decision_verdict(tmp_path, "CXSE3", before=TODAY) == "MANTER"
    assert (
        previous_decision_verdict(tmp_path, "CXSE3", before=date(2026, 9, 18))
        == "REDUZIR"
    )


# --- batch_decide -----------------------------------------------------------------


def _evidence(vault, ticker):
    path = vault / "04_Evidence" / f"EV-{ticker}-1.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntype: evidence\nevidence_id: EV-{ticker}-1\nticker: {ticker}\n"
        "date: 2026-08-01\nsource_type: atlas\nrelevant_facts:\n- provider=cvm_fii\n---\n",
        encoding="utf-8",
    )


def _equity(ticker):
    return PortfolioAsset(
        ticker,
        "equity",
        cnpj="00.000.000/0000-00",
        sector="Materiais Básicos",
        industry="Madeiras e Papel",
    )


def _fetch_equity(symbol, cnpj, ano, bolsai_api_key, brapi_token):
    template = {
        "price": 20.0,
        "market_cap": 1e9,
        "financials": {"lpa": 1.51, "vpa": 4.60},
    }
    return template, object()


def _run(vault, tickers, **kw):
    for ticker in tickers:
        _evidence(vault, ticker)
    return decide_portfolio(
        bolsai_api_key="k",
        brapi_token=None,
        vault_path=str(vault),
        positions=tuple(_equity(t) for t in tickers),
        today=TODAY,
        deps=_Deps(fetch_equity=_fetch_equity, fetch_rate=lambda: RATE),
        **kw,
    )


def test_batch_decide_persists_the_score_it_decided_without_deciding_again(
    tmp_path, monkeypatch
):
    real_decide = decision_engine.decide
    produced = []

    def counting_decide(item):
        decision = real_decide(item)
        produced.append((decision.ticker, decision.score))
        return decision

    monkeypatch.setattr(decision_engine, "decide", counting_decide)

    result = _run(tmp_path, ["CXSE3", "KLBN4"], persist=True)

    # uma chamada a decide() por posição -- nenhuma segunda chamada para gravar
    assert [ticker for ticker, _ in produced] == ["CXSE3", "KLBN4"]
    for outcome, (ticker, score) in zip(result.outcomes, produced, strict=True):
        note = tmp_path / "03_Decisions" / f"DEC-{ticker}-{TODAY.isoformat()}.md"
        assert outcome.persisted == "gravada"
        assert ObsidianRepository.read_decision_score(note) == score == outcome.score


def test_persisting_the_score_changes_no_verdict_or_outcome(tmp_path):
    without = _run(tmp_path / "a", ["CXSE3", "KLBN4"])
    with_persist = _run(tmp_path / "b", ["CXSE3", "KLBN4"], persist=True)

    def comparable(outcome):
        return {k: v for k, v in vars(outcome).items() if k != "persisted"}

    assert [comparable(o) for o in without.outcomes] == [
        comparable(o) for o in with_persist.outcomes
    ]
    assert [o.persisted for o in with_persist.outcomes] == ["gravada", "gravada"]
