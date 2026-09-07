from pathlib import Path
import re

path = Path("tests/test_coverage_knowledge_health.py")
if not path.exists():
    raise SystemExit(f"Arquivo não encontrado: {path}")

text = path.read_text(encoding="utf-8")

replacement = r"""
def test_repository_decision_evidence_and_append_only(tmp_path):
    repo = ObsidianRepository(tmp_path / "vault")

    decision = Decision(
        "DEC-CPFE3-1", "CPFE3", date.today(), Verdict.MANTER,
        change_type=DecisionChange.NO_CHANGE, confidence=0.8,
        reasons=("r1",), risks=("risk",), evidence_ids=("EV-1",),
        review_triggers=("trigger",),
    )
    evidence = Evidence(
        "EV-1", "CPFE3", date.today(), "FNET",
        source_url="https://example.invalid", document_hash="abc",
        relevant_facts=("fact",),
    )

    dpath = repo.save_decision(decision)
    epath = repo.save_evidence(evidence)

    assert dpath.exists()
    assert epath.exists()
    assert "CPFE3" in repo.read_markdown("03_Decisions", "DEC-CPFE3-1")
    assert "fact" in repo.read_markdown("04_Evidence", "EV-1")

    try:
        repo.save_decision(decision)
    except FileExistsError:
        pass
    else:
        raise AssertionError("decision repository is not append-only")

    try:
        repo.save_evidence(evidence)
    except FileExistsError:
        pass
    else:
        raise AssertionError("evidence repository is not append-only")
""".strip()

pattern = re.compile(
    r"(?ms)^def test_repository_all_record_types_and_append_only\(tmp_path\):.*?(?=^def test_decision_auditor_missing_and_invalid)",
)
match = pattern.search(text)
if not match:
    raise SystemExit("Função antiga não encontrada; nenhum arquivo foi alterado.")

path.write_text(text[:match.start()] + replacement + "\n\n" + text[match.end():], encoding="utf-8")
print("FIX4 aplicado com sucesso.")
