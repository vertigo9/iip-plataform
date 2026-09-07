$ErrorActionPreference = "Continue"

$Report = ".\D-OBSIDIAN-06.7_RELEASE_CHECKPOINT_RESTORE_VERIFY.txt"
Remove-Item $Report -Force -ErrorAction SilentlyContinue

function W([string]$x) {
    Write-Host $x
    Add-Content $Report $x -Encoding ASCII
}

W "D-OBSIDIAN-06.7 RELEASE CHECKPOINT RESTORE VERIFY"
W ""

W "=== CHECKPOINT ==="
if (-not (Test-Path ".\POST95_RELEASE_CHECKPOINT.json")) {
    W "FAIL: POST95_RELEASE_CHECKPOINT.json missing"
    exit 1
}
W "POST95_RELEASE_CHECKPOINT.json present"

W "=== FOCUSED COMPATIBILITY TEST ==="
python -m pytest ".\tests\test_post95_stabilization_700001_740000.py" --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0674_post95.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) {
    W ("Focused compatibility test FAIL exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

W ""
W "=== INTEGRATED SUITE ==="
python -m pytest ".\tests\test_d064_integrated_suite.py" --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0674_integrated.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) {
    W ("Integrated suite FAIL exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

W ""
W "STATUS: D-OBSIDIAN-06.7 RELEASE CHECKPOINT RESTORE VERIFY PASS"
W ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Write-Host "Relatorio: $Report"
