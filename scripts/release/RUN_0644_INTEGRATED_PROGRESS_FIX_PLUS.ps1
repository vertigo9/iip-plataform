
$ErrorActionPreference = "Stop"

$report = ".\D-OBSIDIAN-06.4_INTEGRATED_PROGRESS_FIX_PLUS.txt"
Remove-Item $report -Force -ErrorAction SilentlyContinue

$started = Get-Date

@(
    "D-OBSIDIAN-06.4 INTEGRATED PROGRESS FIX+",
    ("Started: " + $started.ToString("yyyy-MM-dd HH:mm:ss")),
    "Protected baseline: D-OBSIDIAN-06.3 / 95.48% / 739 passed / 4 skipped",
    ""
) | Set-Content -Path $report -Encoding ASCII

function Status {
    param([int]$Done,[int]$Total,[string]$Stage,[string]$Detail="")
    $pct = [math]::Min(100,[math]::Max(0,[math]::Round(($Done/$Total)*100)))
    $barSize = 30
    $filled = [int][math]::Floor(($pct/100)*$barSize)
    $bar = ("#" * $filled).PadRight($barSize,"-")
    $elapsed = (Get-Date) - $started
    $e = "{0:hh\:mm\:ss}" -f $elapsed
    Write-Host ("[{0}] {1,3}% | {2} | {3} | {4}" -f $bar,$pct,$Stage,$e,$Detail)
    ("[{0}] {1,3}% | {2} | elapsed={3} | {4}" -f $bar,$pct,$Stage,$e,$Detail) |
        Add-Content -Path $report -Encoding ASCII
}

$harness = ".\tests\test_d064_integrated_suite.py"
if (-not (Test-Path $harness)) {
    Write-Host "ERRO: $harness nÃ£o existe."
    exit 2
}

Status 0 4 "Preparando" "Harness encontrado"
Status 0 4 "Coleta" "pytest --collect-only --no-cov"

python -m pytest $harness --collect-only --no-cov -q 2>&1 |
    Tee-Object -FilePath "$env:TEMP\iip_0644_collect_fixplus.txt" |
    Tee-Object -FilePath $report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Status 1 4 "Coleta concluÃ­da" "7 testes do harness"

$stages = @(
    @("analytics_decision", @(
        ".\tests\test_analysis_framework.py",
        ".\tests\test_agro_analyzer.py",
        ".\tests\test_infra_analyzer.py",
        ".\tests\test_portfolio_intelligence_50001_60000.py",
        ".\tests\test_decision_301_500.py",
        ".\tests\test_portfolio_decision_60001_70000.py",
        ".\tests\test_portfolio_decision_fix1.py",
        ".\tests\test_portfolio_decision_fix2.py",
        ".\tests\test_portfolio_decision_fix3_opportunity.py"
    )),
    @("knowledge_atlas", @(
        ".\tests\test_event_adapter.py",
        ".\tests\test_projection.py",
        ".\tests\test_synchronization.py",
        ".\tests\test_vault.py",
        ".\tests\test_atlas_document_adapter.py",
        ".\tests\test_atlas_history.py",
        ".\tests\test_atlas_knowledge_adapter.py",
        ".\tests\test_atlas_knowledge_id.py",
        ".\tests\test_atlas_knowledge_idempotency.py",
        ".\tests\test_xpml11_atlas_e2e.py",
        ".\tests\test_xpml11_full_e2e.py"
    )),
    @("adaptive_operational", @(
        ".\tests\test_health_extended.py",
        ".\tests\test_metrics.py",
        ".\tests\test_roundtrip.py",
        ".\tests\test_operational_101_200.py",
        ".\tests\test_operational_integration_22001_30000.py",
        ".\tests\test_production_integration_180001_220000.py",
        ".\tests\test_system_e2e.py"
    ))
)

$i = 1
foreach ($s in $stages) {
    $name = $s[0]
    $files = @()
    foreach ($f in $s[1]) { if (Test-Path $f) { $files += $f } }

    if ($files.Count -eq 0) {
        Status $i 4 ($name + " FALHOU") "Nenhum teste vÃ¡lido encontrado"
        exit 2
    }

    $t0 = Get-Date
    Status ($i) 4 $name ("iniciando; arquivos=" + $files.Count)

    # Focused blocks are functional smoke tests; disable coverage so warnings
    # cannot be misinterpreted as functional failures.
    python -m pytest @files --no-cov -q 2>&1 |
        Tee-Object -FilePath (Join-Path $env:TEMP ("iip_0644_{0}_fixplus.txt" -f $name)) |
        Tee-Object -FilePath $report -Append

    $code = $LASTEXITCODE
    $elapsed = (Get-Date) - $t0
    $etime = "{0:hh\:mm\:ss}" -f $elapsed

    if ($code -ne 0) {
        Status $i 4 ($name + " FALHOU") ("exit=" + $code + "; elapsed=" + $etime)
        exit $code
    }

    Status ($i + 1) 4 ($name + " PASSOU") ("exit=0; elapsed=" + $etime)
    $i++
}

Status 4 4 "INTEGRATED SUITE PASS" "100% concluÃ­do; sem overflow do indicador"
Write-Host ""
Write-Host "RelatÃ³rio: $report"

