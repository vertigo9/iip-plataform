$ErrorActionPreference = "Continue"

$Report = ".\D-OBSIDIAN-06.7_BATCH_CLEANUP_VERIFY_FIX2.txt"
Remove-Item $Report -Force -ErrorAction SilentlyContinue

function W([string]$x) {
    Write-Host $x
    Add-Content $Report $x -Encoding ASCII
}

W "D-OBSIDIAN-06.7 BATCH CLEANUP VERIFY FIX2"
W "No source files will be moved or deleted."
W ""

W "=== PACKAGE SOURCE CHECK ==="
$init = ".\src\iip\__init__.py"
$pyproject = ".\pyproject.toml"
W ("src\iip\__init__.py exists: " + (Test-Path $init))
W ("pyproject.toml exists: " + (Test-Path $pyproject))
if (-not (Test-Path $init) -or -not (Test-Path $pyproject)) {
    W "STATUS: REQUIRED SOURCE FILE MISSING"
    exit 1
}

W ""
W "=== INSTALLED PACKAGE CHECK ==="
python -m pip show iip-platform 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0673_pip_show_fix2.txt") |
    Tee-Object $Report -Append

W ""
W "=== PYTHON PATH BEFORE OVERRIDE ==="
python -c "import sys; print(chr(10).join(sys.path))" 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0673_path_before_fix2.txt") |
    Tee-Object $Report -Append

W ""
W "=== TEMPORARY SOURCE PATH VALIDATION ==="
$oldPyPath = $env:PYTHONPATH
$srcPath = (Resolve-Path ".\src").Path
if ($oldPyPath) {
    $env:PYTHONPATH = "$srcPath;$oldPyPath"
} else {
    $env:PYTHONPATH = $srcPath
}

python -c "import iip; import iip.knowledge; print('iip=', iip.__file__); print('knowledge=', iip.knowledge.__file__)" 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0673_import_fix2.txt") |
    Tee-Object $Report -Append

if ($LASTEXITCODE -ne 0) {
    W ("STATUS: SOURCE IMPORT FAILED exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

W ""
W "=== CLI HEALTH WITH EXPLICIT SOURCE PATH ==="
python -m iip.cli.main health 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0673_health_fix2.txt") |
    Tee-Object $Report -Append

if ($LASTEXITCODE -ne 0) {
    W ("STATUS: CLI HEALTH FAILED exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

W ""
W "=== FULL REGRESSION WITH EXPLICIT SOURCE PATH ==="
python -m pytest --no-cov -q 2>&1 |
    Tee-Object (Join-Path $env:TEMP "iip_0673_regression_fix2.txt") |
    Tee-Object $Report -Append

if ($LASTEXITCODE -ne 0) {
    W ("STATUS: REGRESSION FAIL exit=" + $LASTEXITCODE)
    exit $LASTEXITCODE
}

W ""
W "STATUS: D-OBSIDIAN-06.7 CLEANUP VERIFY FIX2 PASS"
W "The source tree remains importable after cleanup."
W ("Finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Write-Host ""
Write-Host "Relatorio: $Report"
exit 0
