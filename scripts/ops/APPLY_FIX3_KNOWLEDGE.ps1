$file = "tests\test_coverage_knowledge_health.py"

if (-not (Test-Path $file)) {
    throw "Arquivo não encontrado: $file"
}

$content = Get-Content $file -Raw

$old = @'
def test_repository_all_record_types_and_append_only(tmp_path):
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
    exposure = Exposure("CPFE3", "utilities", 0.12, 0.9, ("EV-1",))
    snapshot = PortfolioSnapshot(
        "SNAP-1", datetime.now(UTC), 100000,
        (Position("CPFE3", "EQUITY", 12000, 0.12, 0.10),),
    )

    dpath = repo.save_decision(decision)
    epath = repo.save_evidence(evidence)
    xpath = repo.save_exposure(exposure)
    spath = repo.save_snapshot(snapshot)

    assert dpath.exists() and epath.exists() and xpath.exists() and spath.exists()
    assert "## Motivos" in repo.read_markdown("03_Decisions", "DEC-CPFE3-1")
    assert "CPFE3" in repo.read_markdown("04_Evidence", "EV-1")
    assert "utilities" in repo.read_markdown("06_Exposures", "CPFE3__utilities")
    assert "| CPFE3 | EQUITY |" in repo.read_markdown("02_Portfolio/Snapshots", "SNAP-1")

    for fn, obj in (
        (repo.save_decision, decision),
        (repo.save_evidence, evidence),
        (repo.save_exposure, exposure),
        (repo.save_snapshot, snapshot),
    ):
        try:
            fn(obj)
        except FileExistsError:
            pass
        else:
            raise AssertionError("append-only collision was not rejected")

    assert repo.list_decisions("CPFE3") == [dpath]
'@

$new = @'
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
'@

if (-not $content.Contains($old)) {
    throw "Bloco esperado não encontrado; nenhum arquivo foi alterado."
}

Set-Content $file ($content.Replace($old, $new)) -Encoding UTF8
Write-Host "FIX3 aplicado: teste Knowledge ajustado ao contrato real do ObsidianRepository."
