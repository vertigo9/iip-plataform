$ErrorActionPreference = "Stop"

$Report = ".\D-OBSIDIAN-06.7_BATCH_CLEANUP_VERIFY.txt"
Remove-Item $Report -Force -ErrorAction SilentlyContinue

function W([string]$x) {
    Write-Host $x
    Add-Content $Report $x -Encoding ASCII
}

W "D-OBSIDIAN-06.7 BATCH CLEANUP VERIFY"
W "No files are moved by this script."
W ""

W "=== ROOT ==="
Get-ChildItem . -File -Force |
    Sort-Object Name |
    Select-Object -ExpandProperty Name |
    ForEach-Object { W $_ }

W ""
W "=== SOURCE BACKUP CHECK ==="
$remaining = Get-ChildItem .\src -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '(\.bak\d*|\.bak-|backup|_old$)' }
W ("Remaining source backup candidates: " + @($remaining).Count)
$remaining | ForEach-Object { W $_.FullName }

W ""
W "=== PYTHON IMPORT SANITY ==="
python -c "import iip; import iip.knowledge; print(iip.__file__); print(iip.knowledge.__file__)"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

W ""
W "=== FULL REGRESSION ==="
python -m pytest --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0672_verify_regression.txt") |
    Tee-Object $Report -Append
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

W ""
W "STATUS: D-OBSIDIAN-06.7 BATCH CLEANUP VERIFY PASS"
Write-Host "Relatorio: $Report"
