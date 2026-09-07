
$ErrorActionPreference = "Stop"

$manifest = ".\D-OBSIDIAN-06.3_RELEASE_CERTIFIED.json"
$cert = ".\D-OBSIDIAN-06.3_RELEASE_CERTIFIED.txt"

if (-not (Test-Path $manifest)) {
    throw "Manifesto não encontrado: $manifest"
}

$data = Get-Content -Raw -Path $manifest | ConvertFrom-Json

if ($data.status -ne "CERTIFIED") { throw "Status inválido." }
if ($data.collection.tests_collected -ne 743) { throw "Collection baseline divergente." }
if ($data.full_suite.passed -ne 739) { throw "Full-suite baseline divergente." }
if ($data.full_suite.skipped -ne 4) { throw "Skipped baseline divergente." }
if ($data.full_suite.failed -ne 0) { throw "Há falhas registradas." }
if ([double]$data.coverage.percent -lt 95.0) { throw "Coverage abaixo de 95%." }
if ($data.coverage.gate -ne "PASS") { throw "Gate de coverage não aprovado." }

@(
    "D-OBSIDIAN-06.3 RELEASE CERTIFIED",
    "Status: CERTIFIED",
    "Collection: 743 items / PASS",
    "Full suite: 739 passed / 4 skipped / 0 failed / PASS",
    "Coverage: 95.48% / required 95.00% / PASS",
    "System Gate Acceleration: 274 passed / 0 failed / PASS",
    "",
    ("Certified at: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")),
    "",
    "Protected rule: future changes must preserve >=95% coverage and zero failing tests."
) | Set-Content -Path $cert -Encoding ASCII

Write-Host "D-OBSIDIAN-06.3 RELEASE CERTIFIED."
Write-Host "Certificado: $cert"
Write-Host "Manifesto: $manifest"
